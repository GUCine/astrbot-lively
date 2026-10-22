"""機器人控制面板：網頁看狀態、關係圖、開關、待審核和日誌。

- 網頁服務跑在容器內 0.0.0.0:6200，只在 docker 內網，不映射到宿主機；外網經 Cloudflare Tunnel 進來
- 登入交給 Cloudflare Access（郵箱驗證碼），這裡再核對 Cf-Access-Authenticated-User-Email 是否在允許名單裡
  （名單在插件配置 allowed_emails）；容器內 127.0.0.1 和宿主機訪問放行，方便自檢
- 改東西的請求必須是 POST 且帶 X-Lively: 1 頭（跨站頁面帶不了自定義頭），每次操作記到 audit.jsonl
- 密鑰一律不出現在頁面和介面裡
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from aiohttp import web

from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, StarTools, register

from .lively_common import DATA, PLUGIN_DATA as PD, Settings

TZ = timezone(timedelta(hours=8))
STATIC = Path(__file__).parent / "static"
FILLED_JS = ("app.js", "pet.js")
DEFAULT_TITLE = "〈名字〉的小账本"
STARTED = time.time()
AT_RE = re.compile(r"\[At:(\d{5,12})\]")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
VOICES = {
    "qiaopi_mengmei": "俏皮萌妹", "Chinese (Mandarin)_Soft_Girl": "软软女孩", "Chinese (Mandarin)_Warm_Girl": "温暖少女",
    "tianxin_xiaoling": "甜心小玲", "diadia_xuemei": "嗲嗲学妹", "Chinese (Mandarin)_Crisp_Girl": "清脆少女",
    "female-shaonv-jingpin": "少女 beta", "lovely_girl": "萌萌女童", "Arrogant_Miss": "嚣张小姐",
}
GROUP_NAMES: dict[str, str] = {}  # 群號 -> 群名，從 NapCat 拿（_group_names 定時刷新）


def _host_gateway() -> str:
    """docker 網橋的網關 = 宿主機本身（只有能 SSH 上伺服器的人才從這裡來）"""
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if f[1] == "00000000":
                g = int(f[2], 16)
                return ".".join(str((g >> s) & 255) for s in (0, 8, 16, 24))
    except Exception:
        pass
    return ""


TRUSTED = {"127.0.0.1", "::1", _host_gateway()} - {""}


KIND_NAMES = {
    "draw": "画了一张图", "draw_fail": "画图失败", "draft": "群漫画预览", "sent": "发到群里", "rejected": "主人没让发",
    "skip": "没画成", "fail": "失败", "friend_request": "好友申请", "friend_decided": "处理好友申请", "group_invite": "群邀请",
    "group_decided": "处理群邀请", "friend_auto": "自动通过好友", "preview": "主动聊天预览", "replied": "对方回了",
    "published": "发了说说", "edited": "改后发布", "deleted": "删了说说", "kicked": "被踢出群", "muted": "被禁言",
}
FIELD_NAMES = {"umo": "在", "group": "群", "model": "模型", "prompt": "内容", "with_self": "画自己", "qq": "QQ", "name": "名字",
               "result": "结果", "talks": "聊过", "action": "操作", "text": "内容", "what": "发的", "via": "来自", "offset": "第几天前",
               "reason": "原因", "error": "错误", "inviter": "邀请人", "id": "号码", "done": "成功"}


def _pretty(e: dict) -> str:
    parts = []
    for k, v in e.items():
        if k in ("kind", "auto"):
            continue
        if k in ("umo", "group"):
            v = str(v)
            gid = v.rsplit(":", 1)[-1]
            v = GROUP_NAMES.get(gid, "私聊" if "FriendMessage" in v else v)
        v = str(v)
        parts.append(f"{FIELD_NAMES.get(k, k)}：{v[:80] + ('…' if len(v) > 80 else '')}")
    return " · ".join(parts)[:260]


def _ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


class _Ring(logging.Handler):
    """收集 WARNING 以上的日誌給面板看"""

    def __init__(self, buf: deque):
        super().__init__(level=logging.WARNING)
        self.buf = buf

    def emit(self, record):
        try:
            self.buf.append({"ts": record.created, "level": record.levelname,
                             "src": record.name, "msg": ANSI_RE.sub("", record.getMessage())[:600]})
        except Exception:
            pass


@register(
    "astrbot_plugin_lively_panel",
    "GUCine",
    "網頁控制面板：狀態、關係圖、印象卡冊、開關、待審核、飯錢、日誌（建議經 Cloudflare Tunnel + Access 訪問）",
    "2.0.0",
)
class LivelyPanel(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.s = Settings(context, config)
        self.host = str(self.s.get("host", "0.0.0.0"))
        self.port = int(self.s.get("port", 6200))
        self.dir = Path(StarTools.get_data_dir("astrbot_plugin_lively_panel"))
        self.audit_file = self.dir / "audit.jsonl"
        self._av_sem = asyncio.Semaphore(6)  # 關係圖一次要幾十個頭像，別同時打太多請求
        self.logs: deque = deque(maxlen=400)
        self._ring = _Ring(self.logs)
        logging.getLogger("astrbot").addHandler(self._ring)
        self.runner: web.AppRunner | None = None
        self._task = asyncio.create_task(self._serve())

    async def terminate(self):
        logging.getLogger("astrbot").removeHandler(self._ring)
        self._task.cancel()
        if self.runner:
            await self.runner.cleanup()

    # ---------- 服務 ----------
    async def _serve(self):
        app = web.Application(middlewares=[self._guard], client_max_size=64 * 1024)
        r = app.router
        r.add_get("/", self.index)
        r.add_get("/healthz", lambda _: web.Response(text="ok"))
        # 頁面腳本里有人設佔位符，送出前換成配置裡的詞；其餘靜態文件原樣給
        for js in FILLED_JS:
            r.add_get(f"/static/{js}", self._filled_js)
        r.add_static("/static/", STATIC)
        r.add_get("/api/overview", self.overview)
        r.add_get("/api/graph", self.graph)
        r.add_get("/api/people", self.people)
        r.add_get("/api/person/{qq}", self.person)
        r.add_get("/api/settings", self.settings)
        r.add_post("/api/settings", self.set_setting)
        r.add_get("/api/pending", self.pending)
        r.add_post("/api/pending", self.act_pending)
        r.add_get("/api/logs", self.get_logs)
        r.add_post("/api/report", self.make_report)
        r.add_post("/api/comic", self.draw_comic)
        r.add_get("/api/image", self.image)
        r.add_get("/api/avatar/{qq}", self.avatar)
        r.add_get("/api/billing", self.billing)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        for _ in range(10):
            try:
                await web.TCPSite(self.runner, self.host, self.port).start()
                logger.info(f"[lively_panel] 面板已启动：{self.host}:{self.port}")
                await self.s.fetch_bot_qq()
                await self._group_names()
                return
            except OSError as e:  # 重載插件時舊的端口可能還沒放開
                logger.warning(f"[lively_panel] 端口占用，稍后重试: {e}")
                await asyncio.sleep(3)

    def _allowed(self) -> set[str]:
        return {str(e).strip().lower() for e in self.s.get("allowed_emails", []) if str(e).strip()}

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if request.path == "/healthz":
            return await handler(request)
        who = None
        if request.remote in TRUSTED:
            who = "local"
        else:
            email = (request.headers.get("Cf-Access-Authenticated-User-Email") or "").strip().lower()
            if email and email in self._allowed():
                who = email
        if not who:
            return web.Response(status=403, text="没有权限")
        request["who"] = who
        if request.method == "POST":
            if request.headers.get("X-Lively") != "1":
                return web.Response(status=400, text="缺少请求头")
            try:
                request["body"] = await request.json()
            except Exception:
                request["body"] = {}
            self._audit(who, request.path, request["body"])
        resp = await handler(request)
        if request.path.startswith("/static/") and resp.status == 200:
            # 靜態素材（桌寵動畫、字體、表情包）長快取；頁面裡的 js/css 帶 ?v= 版本號，換版本就重新拉
            resp.headers["Cache-Control"] = "private, max-age=2592000"
        elif request.path.startswith("/api/avatar/") and resp.status == 200:
            resp.headers["Cache-Control"] = "private, max-age=86400"
        else:
            resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    def _audit(self, who: str, path: str, body: dict):
        try:
            with self.audit_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": int(time.time()), "who": who, "path": path, "body": body}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    async def billing(self, request):
        b = self._star("lively_billing")
        if not b:
            return self._err("饭钱插件没加载", 503)
        return self._ok(await asyncio.to_thread(b.summary))

    def _me(self) -> dict:
        """頁面要知道的身份訊息（主人、機器人是誰）"""
        has = lambda d: (STATIC / d).is_dir() and any((STATIC / d).iterdir())
        # 桌寵動畫、表情包不隨倉庫發佈（見 README），沒放進來就不顯示
        return {"owner": self.s.owner(), "bot_qq": self.s.bot_qq(), "bot_name": self.s.bot_name() or self.s.bot_qq(),
                "pet": has("pet"), "meme": has("meme")}

    async def index(self, request):
        html = (STATIC / "index.html").read_text("utf-8")
        html = self.s.fill(html.replace("〈标题〉", str(self.s.get("title", DEFAULT_TITLE))))
        # 腳本內容（含人設用詞）變了，網址跟著變，瀏覽器才不會用快取裡的舊版
        for js in FILLED_JS:
            tag = hashlib.sha1(self.s.fill((STATIC / js).read_text("utf-8")).encode()).hexdigest()[:8]
            html = html.replace(f"/static/{js}?v=", f"/static/{js}?p={tag}&v=")
        me = json.dumps(self._me(), ensure_ascii=False).replace("<", "\\u003c")
        html = html.replace("<!--LIVELY_ME-->", f"<script>window.LIVELY_ME = {me};</script>", 1)
        return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})

    async def _filled_js(self, request):
        name = request.path.rsplit("/", 1)[-1]
        return web.Response(text=self.s.fill((STATIC / name).read_text("utf-8")), content_type="application/javascript")

    # ---------- 工具 ----------
    def _star(self, short: str):
        for name in (f"astrbot_plugin_{short}", short):
            meta = self.context.get_registered_star(name)
            if meta and getattr(meta, "star_cls", None):
                return meta.star_cls
        return None

    def _client(self):
        return self.s.client()

    @staticmethod
    def _ok(data=None, **kw):
        return web.json_response({"ok": True, **({"data": data} if data is not None else {}), **kw})

    @staticmethod
    def _err(msg: str, status: int = 400):
        return web.json_response({"ok": False, "error": msg}, status=status)

    # ---------- 總覽 ----------
    async def overview(self, request):
        now = datetime.now(TZ)
        out: dict = {"now": now.strftime("%Y-%m-%d %H:%M:%S"), "uptime": int(time.time() - STARTED)}
        client = self._client()
        try:
            info = await asyncio.wait_for(client.get_login_info(), timeout=3)
            out["online"] = True
            out["account"] = {"qq": str(info.get("user_id")), "name": info.get("nickname")}
        except Exception:
            out["online"] = False
        out["system"] = self._system()
        rep = self._star("lively_report")
        if rep:
            try:
                out["today"] = json.loads(self.s.fill(json.dumps(await asyncio.to_thread(rep.collect, now), ensure_ascii=False)))
            except Exception as e:
                out["today_error"] = str(e)[:200]
        out["hourly"] = await asyncio.to_thread(self._hourly, now)
        counts = {}
        c = self._star("lively_comic")
        if c:
            counts["今天画图"] = c.state.get("draw_count", 0) if c.state.get("draw_day") == now.strftime("%Y-%m-%d") else 0
        v = self._star("lively_voice")
        if v:
            counts["今天语音"] = v.state.get("count", 0) if v.state.get("day") == now.strftime("%Y-%m-%d") else 0
        p = self._star("lively_proactive")
        if p:
            counts["今天主动聊天"] = p.state.get("count", 0) if p.state.get("day") == now.strftime("%Y-%m-%d") else 0
        s = self._star("lively_social")
        if s:
            counts["待审申请"] = len(s.state.get("pending", {}))
        out["counts"] = counts
        out["feed"] = await asyncio.to_thread(self._feed)
        return self._ok(out)

    @staticmethod
    def _system() -> dict:
        info: dict = {}
        try:
            info["load"] = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
            info["cpus"] = os.cpu_count()
            mem = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) // 1024
            info["mem"] = {"total": mem["MemTotal"], "available": mem["MemAvailable"],
                           "swap_used": mem["SwapTotal"] - mem["SwapFree"], "swap_total": mem["SwapTotal"]}
            du = shutil.disk_usage(str(DATA))
            info["disk"] = {"total": du.total // 2**30, "used": du.used // 2**30, "free": du.free // 2**30}
        except Exception as e:
            info["error"] = str(e)[:100]
        return info

    @staticmethod
    def _hourly(now: datetime) -> dict:
        day0 = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        users, bot = [0] * 24, [0] * 24
        try:
            con = _ro(PD / "astrbot_plugin_livingmemory" / "conversations.db")
            for ts, role in con.execute("select timestamp, role from messages where timestamp >= ?", (day0,)):
                h = datetime.fromtimestamp(ts, TZ).hour
                (bot if role == "assistant" else users)[h] += 1
            con.close()
        except Exception:
            pass
        return {"users": users, "bot": bot}

    @staticmethod
    def _feed(limit: int = 40) -> list:
        """各插件 events.jsonl 合起來的最近動態"""
        names = {"astrbot_plugin_lively_social": "社交", "astrbot_plugin_lively_qzone": "空间", "astrbot_plugin_lively_proactive": "主动聊天", "astrbot_plugin_lively_comic": "画图"}
        items = []
        for d, label in names.items():
            f = PD / d / "events.jsonl"
            try:
                lines = f.read_text("utf-8").splitlines()[-30:]
            except Exception:
                continue
            for line in lines:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                e.pop("path", None)
                items.append({"ts": e.pop("ts", 0), "src": label, "kind": KIND_NAMES.get(e.get("kind"), e.get("kind", "")),
                              "detail": _pretty(e)})
        items.sort(key=lambda x: -x["ts"])
        return items[:limit]

    # ---------- 關係 ----------
    @staticmethod
    def _bond_rows() -> list[dict]:
        con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
        rows = [dict(r) for r in con.execute("select * from people")]
        con.close()
        return rows

    def _bond_mod(self):
        b = self._star("lively_bond")
        if not b:
            return None
        mod = sys.modules.get(type(b).__module__.rsplit(".", 1)[0] + ".core")
        return mod

    def _describe(self, p: dict) -> dict:
        mod = self._bond_mod()
        out = {}
        if mod:
            for fn in ("stage", "favor_desc", "mood_desc"):
                try:
                    out[fn] = getattr(mod, fn)(p)
                except Exception:
                    pass
        return out

    async def people(self, request):
        rows = await asyncio.to_thread(self._bond_rows)
        rows.sort(key=lambda r: (-(r.get("familiarity") or 0), -(r.get("favor") or 0)))
        for r in rows:
            r.update(self._describe(r))
        return self._ok(rows)

    async def graph(self, request):
        days = max(1, min(90, int(request.query.get("days", 30))))
        group = request.query.get("group", "all")
        if group not in ("all", "dm") and not group.isdigit():
            return self._err("群号不对")
        names = await self._group_names()
        return self._ok(await asyncio.to_thread(self._graph, days, group, names))

    async def _group_names(self) -> dict:
        """群名從 napcat 拿，十分鐘快取一次"""
        cache = getattr(self, "_gn_cache", None)
        if cache and time.time() - cache[0] < 600:
            return cache[1]
        names = dict(GROUP_NAMES)
        try:
            for g in await asyncio.wait_for(self._client().get_group_list(), timeout=5):
                names[str(g.get("group_id"))] = g.get("group_name") or names.get(str(g.get("group_id")), "")
        except Exception:
            return names  # NapCat 還沒連上：這次不快取，下次再問
        self._gn_cache = (time.time(), names)
        GROUP_NAMES.update({k: v for k, v in names.items() if v})
        return names

    def _graph(self, days: int, group: str = "all", gnames: dict | None = None) -> dict:
        """group = all（全部）/ 群號（只看這個群裡說過話的人和他們之間的聯繫）/ dm（私聊過的人）"""
        people = {str(r["qq"]): r for r in self._bond_rows()}
        since = time.time() - days * 86400
        since_iso = datetime.fromtimestamp(since, timezone.utc).isoformat()  # graph_edges.created_at 存的是 ISO 字串
        edges: dict[tuple, dict] = {}
        gnames = gnames or GROUP_NAMES
        bot_qq = self.s.bot_qq() or "bot"

        def sess_key(sid: str) -> str:
            if ":GroupMessage:" in sid:
                return sid.rsplit(":", 1)[-1]
            return "dm" if ":FriendMessage:" in sid else ""

        # 每個人在哪些群裡說過話（按條數）
        member: dict[str, dict] = {}
        try:
            con = _ro(PD / "astrbot_plugin_livingmemory" / "conversations.db")
            for sender, sid, n in con.execute(
                    "select sender_id, session_id, count(*) from messages where role='user' and timestamp >= ? group by 1, 2", (since,)):
                k = sess_key(sid or "")
                if k and str(sender) != bot_qq:
                    member.setdefault(str(sender), {})[k] = member.get(str(sender), {}).get(k, 0) + n
            con.close()
        except Exception as e:
            logger.warning(f"[lively_panel] 读群成员失败: {e}")
        in_scope = (lambda q: True) if group == "all" else (lambda q: group in member.get(q, {}))

        def add(a, b, kind, w=1):
            if a == b or not a or not b:
                return
            key = tuple(sorted((a, b)))
            e = edges.setdefault(key, {"at": 0, "memory": 0})
            e[kind] += w

        # 誰 @ 了誰
        try:
            con = _ro(PD / "astrbot_plugin_livingmemory" / "conversations.db")
            for sender, content, sid in con.execute(
                    "select sender_id, content, session_id from messages where role='user' and timestamp >= ? and content like '%[At:%'", (since,)):
                if group != "all" and sess_key(sid or "") != group:
                    continue
                for tgt in AT_RE.findall(content or ""):
                    if tgt != bot_qq and str(sender) != bot_qq:
                        add(str(sender), tgt, "at")
            con.close()
        except Exception as e:
            logger.warning(f"[lively_panel] 读 @ 关系失败: {e}")
        # 一起出現在同一段記憶裡
        try:
            con = _ro(PD / "astrbot_plugin_livingmemory" / "livingmemory.db")
            mem_people: dict[str, set] = {}
            for mid, canon in con.execute(
                    "select distinct e.source_memory_id, n.canonical_value from graph_edges e "
                    "join graph_nodes n on n.id in (e.source_node_id, e.target_node_id) "
                    "where n.node_type='person' and e.created_at >= ?", (since_iso,)):
                qq = str(canon).rsplit(":", 1)[-1]
                if qq.isdigit() and qq != bot_qq:
                    mem_people.setdefault(str(mid), set()).add(qq)
            if group != "all" and mem_people:
                # 只留這個群（或私聊）裡形成的記憶
                keep_mid = set()
                for did, meta in con.execute("select id, metadata from documents"):
                    try:
                        if sess_key(json.loads(meta or "{}").get("session_id", "")) == group:
                            keep_mid.add(str(did))
                    except Exception:
                        pass
                mem_people = {k: v for k, v in mem_people.items() if k in keep_mid}
            con.close()
            for qs in mem_people.values():
                qs = sorted(qs)
                for i in range(len(qs)):
                    for j in range(i + 1, len(qs)):
                        add(qs[i], qs[j], "memory")
        except Exception as e:
            logger.warning(f"[lively_panel] 读记忆关系失败: {e}")

        def strength(e):
            return e["at"] + 0.5 * e["memory"]

        # 留下有意思的人：和機器人有交情的，或者跟別人聯繫夠多的
        degree: dict[str, float] = {}
        for (a, b), e in edges.items():
            degree[a] = degree.get(a, 0) + strength(e)
            degree[b] = degree.get(b, 0) + strength(e)
        if group == "all":
            keep = {q for q, p in people.items() if (p.get("talks") or 0) > 0 or (p.get("familiarity") or 0) >= 3}
            keep |= {q for q, d in degree.items() if d >= 3 and q in people}
        else:
            # 分群看：這個群裡說過話、機器人認識的人都放進來
            keep = {q for q in people if in_scope(q)}
        keep.discard(bot_qq)
        keep = set(sorted(keep, key=lambda q: -((people.get(q) or {}).get("familiarity") or 0) - degree.get(q, 0))[:90])

        nodes = [{"id": bot_qq, "name": self.s.bot_name() or bot_qq, "bot": True}]
        for q in keep:
            p = people.get(q, {})
            nodes.append({"id": q, "name": p.get("name") or q, "favor": p.get("favor") or 0,
                          "familiarity": p.get("familiarity") or 0, "talks": p.get("talks") or 0,
                          "mood": p.get("mood") or "", "impression": p.get("impression") or "",
                          "owner": self.s.is_owner(q), "last_talk": p.get("last_talk") or 0,
                          "groups": sorted(member.get(q, {}), key=lambda k: -member[q][k])})
        links = []
        for q in keep:
            p = people.get(q, {})
            if (p.get("talks") or 0) > 0 or (p.get("familiarity") or 0) > 0:
                links.append({"source": bot_qq, "target": q, "kind": "bond",
                              "favor": p.get("favor") or 0, "familiarity": p.get("familiarity") or 0})
        for (a, b), e in edges.items():
            if a in keep and b in keep and strength(e) >= 1:
                links.append({"source": a, "target": b, "kind": "people", "at": e["at"], "memory": e["memory"],
                              "weight": strength(e)})
        # 分頁用的群列表：按這段時間裡說過話的人數排
        count: dict[str, int] = {}
        for q, gs in member.items():
            if q in people:
                for k in gs:
                    count[k] = count.get(k, 0) + 1
        groups = [{"id": k, "name": "私聊" if k == "dm" else (gnames.get(k) or f"群{k}"), "people": n}
                  for k, n in sorted(count.items(), key=lambda x: (x[0] == "dm", -x[1]))]
        return {"nodes": nodes, "links": links, "days": days, "group": group, "groups": groups,
                "group_names": {k: v for k, v in gnames.items() if k in count}}

    async def person(self, request):
        qq = request.match_info["qq"]
        if not qq.isdigit():
            return self._err("号码不对")
        return self._ok(await asyncio.to_thread(self._person, qq))

    def _person(self, qq: str) -> dict:
        con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
        row = con.execute("select * from people where qq=?", (qq,)).fetchone()
        p = dict(row) if row else {"qq": qq}
        events = [dict(r) for r in con.execute("select ts, kind, delta, after, note, source from events where qq=? order by ts", (qq,))]
        try:
            row = con.execute("select card from cards where qq=?", (qq,)).fetchone()
            mod = self._bond_mod()
            p["card"] = mod.card_text(json.loads(row[0])) if row and mod and hasattr(mod, "card_text") else ""
        except Exception:
            p["card"] = ""
        con.close()
        p.update(self._describe(p))
        out = {"profile": p, "events": events}
        # 記憶
        mems = []
        try:
            m = _ro(PD / "astrbot_plugin_livingmemory" / "livingmemory.db")
            ids = [r[0] for r in m.execute(
                "select distinct e.source_memory_id from graph_edges e join graph_nodes n on n.id in (e.source_node_id, e.target_node_id) "
                "where n.node_type='person' and n.canonical_value=?", (f"account:aiocqhttp:{qq}",))]
            if ids:
                marks = ",".join("?" * len(ids[-60:]))
                for r in m.execute(f"select id, text, metadata, created_at from documents where id in ({marks}) order by id desc limit 30", ids[-60:]):
                    meta = {}
                    try:
                        meta = json.loads(r["metadata"] or "{}")
                    except Exception:
                        pass
                    mems.append({"text": r["text"], "ts": meta.get("create_time") or 0,
                                 "where": ({"day": "日记忆", "week": "周记忆", "month": "月记忆", "quarter": "季记忆"}.get(meta.get("lively_tier"), "")
                                           + (f"（{meta.get('lively_label')}）・" if meta.get("lively_tier") else "")
                                           + self._where(meta.get("session_id", ""))), "importance": meta.get("importance")})
            m.close()
        except Exception as e:
            logger.warning(f"[lively_panel] 读记忆失败: {e}")
        out["memories"] = mems
        # 最近說的話
        msgs = []
        try:
            c = _ro(PD / "astrbot_plugin_livingmemory" / "conversations.db")
            for r in c.execute("select session_id, content, timestamp from messages where sender_id=? and role='user' "
                               "order by timestamp desc limit 40", (qq,)):
                msgs.append({"where": self._where(r["session_id"]), "text": (r["content"] or "")[:300], "ts": r["timestamp"]})
            c.close()
        except Exception:
            pass
        out["messages"] = msgs
        # 和誰有聯繫
        g = self._graph(30)
        names = {n["id"]: n["name"] for n in g["nodes"]}
        out["links"] = sorted(
            [{"qq": l["target"] if l["source"] == qq else l["source"],
              "name": names.get(l["target"] if l["source"] == qq else l["source"]), "at": l["at"], "memory": l["memory"]}
             for l in g["links"] if l["kind"] == "people" and qq in (l["source"], l["target"])],
            key=lambda x: -(x["at"] + 0.5 * x["memory"]))[:15]
        pr = self._star("lively_proactive")
        out["proactive_blocked"] = bool(pr and qq in pr.state.get("blocked", []))
        return out

    @staticmethod
    def _where(umo: str) -> str:
        if ":GroupMessage:" in umo:
            gid = umo.rsplit(":", 1)[-1]
            return GROUP_NAMES.get(gid, f"群{gid}")
        if ":FriendMessage:" in umo or umo.startswith("livingmemory:user:"):
            return "私聊"
        return umo or ""

    # ---------- 開關 ----------
    async def settings(self, request):
        await self._group_names()
        out = {}
        if (p := self._star("lively_proactive")):
            out["proactive"] = {"enabled": p.state.get("enabled"), "mode": p.state.get("mode"),
                                "blocked": p.state.get("blocked", [])}
        if (q := self._star("lively_qzone")):
            out["qzone"] = {"enabled": q.state.get("enabled"), "mode": q.state.get("mode")}
        if (c := self._star("lively_comic")):
            on = set(c._groups())
            out["comic"] = {"enabled": c.state.get("enabled"), "auto_post": c.state.get("auto_post"), "at": c.comic_at,
                            "groups": [{"gid": g, "name": GROUP_NAMES.get(g, f"群{g}"), "on": g in on} for g in c._served()]}
        if (v := self._star("lively_voice")):
            cfg = v._cfg() if hasattr(v, "_cfg") else {}
            out["voice"] = {"enabled": v.state.get("enabled"), "voice_id": cfg.get("voice_id"), "model": cfg.get("model"),
                            "configured": bool(cfg.get("api_key")), "voices": VOICES}
        if (b := self._star("lively_bond")):
            try:
                out["bond"] = {"mode": b.store.get_meta("mode")}
            except Exception:
                pass
        if (s := self._star("lively_social")):
            out["social"] = {"blacklist": s.state.get("blacklist", [])}
        return self._ok(out)

    async def set_setting(self, request):
        body = request["body"]
        plugin, key, value = body.get("plugin"), body.get("key"), body.get("value")
        allowed = {
            ("proactive", "enabled"): bool, ("proactive", "mode"): ("auto", "preview"),
            ("qzone", "enabled"): bool, ("qzone", "mode"): ("review", "auto"),
            ("comic", "enabled"): bool, ("comic", "auto_post"): bool,
            ("voice", "enabled"): bool, ("voice", "voice_id"): tuple(VOICES),
            ("proactive", "block"): str, ("proactive", "unblock"): str,
        }
        if plugin == "comic" and isinstance(key, str) and key.startswith("group:"):
            c = self._star("lively_comic")
            if not c:
                return self._err("插件没加载", 503)
            gid = key[6:]
            if not isinstance(value, bool) or gid not in c._served():
                return self._err("值不对")
            return self._ok(msg=c.set_group(gid, value))
        rule = allowed.get((plugin, key))
        if rule is None:
            return self._err("不能改这个")
        if rule is bool and not isinstance(value, bool):
            return self._err("值不对")
        if isinstance(rule, tuple) and value not in rule:
            return self._err("值不对")
        if rule is str and not (isinstance(value, str) and value.isdigit()):
            return self._err("号码不对")
        if plugin == "voice" and key == "voice_id":
            v = self._star("lively_voice")
            if not v:
                return self._err("插件没加载", 503)
            try:
                v.s.cfg["voice_id"] = value
                v.s.cfg.save_config()
            except Exception as e:
                return self._err(f"保存失败: {e}")
            return self._ok()
        inst = self._star(f"lively_{plugin}")
        if not inst:
            return self._err("插件没加载", 503)
        if key in ("block", "unblock"):
            bl = inst.state.setdefault("blocked", [])
            if key == "block" and value not in bl:
                bl.append(value)
            if key == "unblock" and value in bl:
                bl.remove(value)
        else:
            inst.state[key] = value
        inst._save()
        return self._ok()

    # ---------- 待審核 ----------
    async def pending(self, request):
        out = {}
        if (s := self._star("lively_social")):
            try:
                s._prune()
            except Exception:
                pass
            out["requests"] = [{"key": k, **{x: v.get(x) for x in ("type", "id", "name", "ts", "comment", "groups", "inviter", "inviter_name")}}
                               for k, v in s.state.get("pending", {}).items()]
        if (q := self._star("lively_qzone")):
            out["qzone_draft"] = q.state.get("draft")
            out["qzone_posted"] = q.state.get("posted", [])[-5:]
        if (c := self._star("lively_comic")):
            out["comic"] = [{"gid": g, "group": GROUP_NAMES.get(g, g), "label": v.get("label"), "ts": v.get("ts"),
                             "image": f"/api/image?f={Path(v['path']).name}" if not str(v.get("path", "")).startswith("http") else v.get("path")}
                            for g, v in c.state.get("pending", {}).items()]
        return self._ok(out)

    async def act_pending(self, request):
        b = request["body"]
        what, action = b.get("what"), b.get("action")
        if what == "request":
            s = self._star("lively_social")
            req = s.state.get("pending", {}).get(b.get("key")) if s else None
            if not req or action not in ("同意", "拒绝", "拉黑"):
                return self._err("申请不存在或已处理")
            s.state["pending"].pop(b["key"], None)
            ok = action == "同意"
            done = await s._approve(self._client(), req["type"], req["flag"], ok)
            if action == "拉黑" and req["type"] == "friend" and req["id"] not in s.state["blacklist"]:
                s.state["blacklist"].append(req["id"])
            s._save()
            s._log(f"{req['type']}_decided", id=req["id"], name=req["name"], action=action, done=done, via="panel")
            if ok and done and req["type"] == "friend":
                asyncio.create_task(s._greet(req["id"]))
            return self._ok(done=done) if done else self._err("操作没成功，申请可能已经过期")
        if what == "qzone":
            q = self._star("lively_qzone")
            draft = q.state.get("draft") if q else None
            if action == "write":
                msg = await q.new_draft(str(b.get("topic") or "")[:50])
                return self._ok(msg=msg)
            if not draft:
                return self._err("没有草稿")
            if action in ("publish", "edit"):
                text = draft["text"] if action == "publish" else str(b.get("text") or "").strip()
                if not text:
                    return self._err("内容是空的")
                tid = await q.publish(text)
                q.state["draft"] = None
                q._save()
                return self._ok(tid=tid)
            if action == "discard":
                q.state["draft"] = None
                q._log("rejected", text=draft["text"], via="panel")
                q._save()
                return self._ok()
            if action == "rewrite":
                q.state["draft"] = None
                q._save()
                msg = await q.new_draft()
                return self._ok(msg=msg)
            return self._err("不认识的操作")
        if what == "comic":
            c = self._star("lively_comic")
            if not c:
                return self._err("插件没加载", 503)
            if action == "post":
                return self._ok(msg=await c.post(comic_only=True))
            if action == "discard":
                gid = b.get("gid")
                if gid in c.state.get("pending", {}):
                    c.state["pending"].pop(gid)
                    c._save()
                    c._log("rejected", group=gid, via="panel")
                return self._ok()
            return self._err("不认识的操作")
        return self._err("不认识的类型")

    async def draw_comic(self, request):
        c = self._star("lively_comic")
        if not c:
            return self._err("插件没加载", 503)
        if c._busy.locked():
            return self._err("上一张还在画")
        offset = 1 if request["body"].get("day") == "yesterday" else 0
        groups = c._groups()
        if not groups:
            return self._err("群漫画还没设置群")
        for g in groups:
            asyncio.create_task(c._draw_and_report(g, offset))
        return self._ok(msg="开始画了，几分钟后私信主人预览")

    async def image(self, request):
        name = request.query.get("f", "")
        if not re.fullmatch(r"[\w.\-]+\.(png|jpg|jpeg)", name):
            return self._err("文件名不对")
        path = PD / "astrbot_plugin_lively_comic" / name
        if not path.exists():
            return self._err("没有这个图", 404)
        return web.FileResponse(path)

    async def avatar(self, request):
        """QQ 頭像代理：同源才能在關係圖裡裁成圓形；快取在插件資料目錄，三天刷新一次"""
        qq = request.match_info["qq"]
        if not re.fullmatch(r"\d{5,12}", qq):
            return self._err("QQ 号不对")
        path = self.dir / "avatars" / f"{qq}.jpg"
        if not path.exists() or time.time() - path.stat().st_mtime > 3 * 86400:
            try:
                async with self._av_sem, aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
                    async with s.get(f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100") as r:
                        body = await r.read()
                if r.status == 200 and body[:3] in (b"\xff\xd8\xff", b"\x89PN", b"GIF") and len(body) < 512 * 1024:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
            except Exception as e:
                logger.debug(f"[lively_panel] 头像拉取失败 {qq}: {e}")
        if not path.exists():
            return self._err("没有头像", 404)
        return web.FileResponse(path, headers={"Content-Type": "image/jpeg"})

    # ---------- 日誌與彙報 ----------
    async def get_logs(self, request):
        audit = []
        try:
            audit = [json.loads(x) for x in self.audit_file.read_text("utf-8").splitlines()[-30:]]
        except Exception:
            pass
        return self._ok({"logs": list(self.logs)[-200:], "audit": audit[::-1], "since": STARTED})

    async def make_report(self, request):
        rep = self._star("lively_report")
        if not rep:
            return self._err("汇报插件没加载", 503)
        try:
            text = await asyncio.wait_for(rep.build(datetime.now(TZ)), timeout=90)  # 面板是簡體，不轉繁體
        except Exception as e:
            return self._err(f"生成失败: {e}")
        return self._ok(text=text)
