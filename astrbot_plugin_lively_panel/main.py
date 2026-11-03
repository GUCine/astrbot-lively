"""機器人控制面板：網頁看機器人的「腦內」——此刻、心裡的人（魚友卡）、記憶、群裡、信箱（來信、說說，都帶記錄）、值班（開關、日誌、飯錢）。

- 頁面在 static/：index.html＋water.js（水光背景）＋fx.js（動畫）＋mind.js（各腦區），第三方庫在 static/vendor/
- 網頁服務跑在容器內 0.0.0.0:6200，只在 docker 內網，不映射到宿主機；外網經 Cloudflare Tunnel 進來
- 登入交給 Cloudflare Access（郵箱驗證碼），這裡再核對郵箱是否在允許名單裡（插件配置 allowed_emails）；
  填了 cf_team_domain 和 cf_aud 時，郵箱從 Cf-Access-Jwt-Assertion 驗過簽名再拿（不然同一個 docker 網路裡的容器
  自己帶個 Cf-Access-Authenticated-User-Email 頭就能進）；容器內 127.0.0.1 和宿主機訪問放行，方便自檢
- 改東西的請求必須是 POST 且帶 X-Lively: 1 頭（跨站頁面帶不了自定義頭），每次操作記到 audit.jsonl
- 密鑰一律不出現在頁面和介面裡
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from aiohttp import web

from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, StarTools, register

from .lively_common import BACKSTAGE_KIND, DATA, PLUGIN_DATA as PD, Settings, note_outbox, tail_lines

TZ = timezone(timedelta(hours=8))
STATIC = Path(__file__).parent / "static"
FILLED_JS = ("mind.js", "fx.js")
DEFAULT_TITLE = "〈名字〉的小账本"
STARTED = time.time()
# 面板只顯示最近 KEEP_DAYS 天的記錄；更舊的留在伺服器上（各插件的 events.jsonl 原樣不動，
# 面板自己的值班日誌、操作記錄每天把過期的搬進 archive/<名字>-<年-月>.jsonl）
KEEP_DAYS = 7
KEEP_SECS = KEEP_DAYS * 86400
ARCHIVE_EVERY = 6 * 3600
AT_RE = re.compile(r"\[At:(\d{5,12})\]")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
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

CF_CERTS_TTL = 3600
SHA256_DI = bytes.fromhex("3031300d060960864801650304020105000420")  # PKCS#1 v1.5 裡 SHA-256 的 DigestInfo 前綴


def _b64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _rs256_ok(key: dict, signed: bytes, sig: bytes) -> bool:
    """RS256（RSASSA-PKCS1-v1_5＋SHA-256）驗簽：還原出整塊編碼再整塊比對，不用另裝套件"""
    n = int.from_bytes(_b64url(key["n"]), "big")
    e = int.from_bytes(_b64url(key["e"]), "big")
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False
    em = pow(int.from_bytes(sig, "big"), e, n).to_bytes(k, "big")
    want = b"\x00\x01" + b"\xff" * (k - len(SHA256_DI) - 35) + b"\x00" + SHA256_DI + hashlib.sha256(signed).digest()
    return hmac.compare_digest(em, want)


KIND_NAMES = {
    "draw": "画了一张图", "draw_fail": "画图失败", "draft": "群漫画预览", "sent": "发到群里", "rejected": "主人没让发", "held": "看过没发", "look_fail": "没看成，照旧发了",
    "skip": "没画成", "fail": "失败", "friend_request": "好友申请", "friend_decided": "处理好友申请", "group_invite": "群邀请",
    "group_decided": "处理群邀请", "friend_auto": "自动通过好友", "preview": "主动聊天预览", "replied": "对方回了",
    "published": "发了说说", "edited": "改后发布", "deleted": "删了说说", "kicked": "被踢出群", "muted": "被禁言",
    "report": "群漫画的事交给她", "fix": "她看了要改", "storyboard": "写了分镜", "storyboard_fail": "自己的分镜没画成",
    "redo": "主人请她补画",
}
FIELD_NAMES = {"umo": "在", "group": "群", "model": "模型", "prompt": "内容", "with_self": "画自己", "qq": "QQ", "name": "名字",
               "result": "结果", "talks": "聊过", "action": "操作", "text": "内容", "what": "发的", "via": "来自", "offset": "第几天前",
               "reason": "原因", "error": "错误", "inviter": "邀请人", "id": "号码", "done": "成功",
               "why": "为什么", "saw": "她看到的", "looked": "看过", "to_owner": "她私信主人的话", "facts": "发生的事",
               "said": "她私信主人的话", "how": "怎么改", "change": "改什么", "n": "第几次", "secs": "花了几秒",
               "ok": "改成了", "taken": "用了改过的", "fixes": "她改过", "panels": "格数", "cast": "出场", "fix": "第几次改"}


def _pretty(e: dict) -> str:
    parts = []
    for k, v in e.items():
        if k in ("kind", "auto", "storyboard"):
            continue
        if k == "redo":  # 群漫畫：主人請她補畫的那張
            if v:
                parts.append("主人请她补画的")
            continue
        if k == "fixes" and isinstance(v, list):  # 群漫畫看了要改的：一次一句
            v = "；".join(f"{f.get('how')}「{str(f.get('change') or '')[:20]}」"
                         + (("改好了" if f.get("taken", True) else "改过的没用") if f.get("ok") else f"没改成（{f.get('why', '')}）")
                         for f in v if isinstance(f, dict))
        if k in ("umo", "group"):
            v = str(v)
            gid = v.rsplit(":", 1)[-1]
            v = GROUP_NAMES.get(gid, "私聊" if "FriendMessage" in v else v)
        v = str(v)
        parts.append(f"{FIELD_NAMES.get(k, k)}：{v[:80] + ('…' if len(v) > 80 else '')}")
    return " · ".join(parts)[:260]



# ---------- 按人用量的畫像 ----------
HOUR_BANDS = (("深夜", range(0, 6)), ("早上", range(6, 12)), ("下午", range(12, 18)), ("晚上", range(18, 24)))


def _profile(u: dict, days: int, now: float, max_turns: int, med_per_turn: float) -> dict:
    """一個人的畫像：常來的時段、標籤"""
    turns, hours, wd = u["turns"] or 0, u["hours"], u["wdays"]
    first = u.get("first") or now
    span = max(7.0, min(float(days), (now - first) / 86400 + 1))
    band = max(HOUR_BANDS, key=lambda b: sum(hours[h] for h in b[1]))[0] if turns else ""
    peak = max(range(24), key=lambda h: hours[h]) if turns else None
    share = lambda xs: sum(xs) / turns if turns else 0.0
    night, day9, eve, wkend = share(hours[0:6]), share(hours[9:18]), share(hours[18:24]), share(wd[5:7])
    private, called = (u["private"] / turns if turns else 0.0), (u["called"] / turns if turns else 0.0)
    per_turn = u["cost"] / turns if turns else 0.0
    idle = (now - u["last"]) / 86400 if u["last"] else 99
    tags = []
    if turns >= 3:
        if night >= .4: tags.append("夜猫子")
        elif eve >= .5: tags.append("下班后来")
        elif day9 >= .6: tags.append("白天摸鱼")
        if wkend >= .45: tags.append("周末型")
        if private >= .5: tags.append("私聊为主")
        elif not u["private"]: tags.append("只在群里")
        if called >= .8: tags.append("常叫〈我〉")
        if u["active_days"] / span >= .6: tags.append("常驻")
        if med_per_turn and per_turn > med_per_turn * 1.6: tags.append("聊得深")
    if max_turns and turns >= max(10, max_turns * .5): tags.append("话痨")
    if now - first < 7 * 86400: tags.append("新面孔")
    if idle > 7 and u["active_days"] >= 3: tags.append("好久没来")
    return {"band": band, "peak_hour": peak, "night": round(night, 2), "weekend": round(wkend, 2), "private_share": round(private, 2),
            "called_share": round(called, 2), "per_turn": round(per_turn, 5), "idle_days": round(idle, 1), "tags": tags}

def _thumb(src: Path, dst: Path, w: int):
    from PIL import Image
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((w, w * 3))
        tmp = dst.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=82, optimize=True)
        tmp.replace(dst)


def _feed_thumb(src: Path, dst: Path, w: int, blur: bool):
    """投喂檔位〈卡〉、專屬〈卡〉的背景：縮到 w 寬；blur 是霧面玻璃底下那層（先糊好，卡上就不用 CSS filter）"""
    from PIL import Image, ImageFilter
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((w, w * 3))
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(max(6, w // 40)))
        tmp = dst.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=84, optimize=True)
        tmp.replace(dst)


def _made_thumb(data: bytes, dst: Path, w: int):
    """定做的虛擬形象（bond made_faces 給的 JPEG）縮到 w 寬"""
    from io import BytesIO
    from PIL import Image
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((w, w * 3))
        tmp = dst.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=86, optimize=True)
        tmp.replace(dst)


PC_TOOLS = {"/run": "跑程序", "/files": "文件", "/fetch": "抓网页", "/get": "发文件", "/screen": "屏幕", "/web": "浏览器"}
PC_IDLE = 180


def _pc_clip(v, n: int) -> str:
    """一個欄位一行；字串照原樣（代碼、網頁字帶換行的直接看得懂），別的寫成 JSON"""
    if isinstance(v, dict):
        s = "\n".join(f"{k}: {x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)}" for k, x in v.items())
    else:
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)
    return s if len(s) <= n else s[:n] + f"……（还有 {len(s) - n} 字，见工作记录）"


def pc_rounds(rows: list) -> list[dict]:
    """她電腦的工作記錄（一天）→ 一輪一輪（10-29，面板「电脑记录」）。分法和 DSH 裡那份一樣：
    有 asker.turn 的按它分；沒有的（她的程序直接叫橋、運維調試）按時間挨著的分一組"""
    out: dict[str, dict] = {}
    raw = None
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict) or r.get("op") == "start":
            continue
        a = r.get("asker") or None
        if a and a.get("turn"):
            key = a["turn"]
        else:
            ts = float(r.get("ts") or 0)
            if not raw or ts - raw[1] > PC_IDLE:
                raw = [f"raw-{int(ts)}", ts]
            raw[1] = ts
            key = raw[0]
        g = out.get(key)
        if g is None:
            g = out[key] = {"key": key, "direct": not a, "who": "", "qq": "", "owner": False, "beat": False, "group": "",
                            "umo": "", "msg": "", "start": r.get("at") or "", "end": "", "lines": [i, i], "steps": [], "reply": []}
        if a:
            for k in ("qq", "group", "umo"):
                g[k] = g[k] or str(a.get(k) or "")
            g["who"] = g["who"] or str(a.get("name") or "")
            g["owner"] = g["owner"] or bool(a.get("owner"))
            g["beat"] = g["beat"] or bool(a.get("beat"))
            g["msg"] = g["msg"] or str(a.get("msg") or "")
        g["end"] = r.get("at") or g["end"]
        g["lines"][1] = i
        req = dict(r.get("req") or {}) if isinstance(r.get("req"), dict) else {}
        req.pop("_asker", None)
        if r.get("op") == "/note":
            if req.get("kind") == "reply" and req.get("text"):
                g["reply"].append(str(req["text"])[:2000])
            continue
        g["steps"].append({"at": r.get("at") or "", "tool": PC_TOOLS.get(r.get("op"), str(r.get("op") or "")), "action": str(req.get("action") or req.get("lang") or ""),
                           "ok": bool(r.get("ok")), "ms": r.get("ms"), "args": _pc_clip(req, 1500), "res": _pc_clip(r.get("res"), 2000),
                           "shot": r.get("shot_copy") if isinstance(r.get("shot_copy"), str) and r["shot_copy"].startswith("shots/") else ""})
    return list(out.values())


def _ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


# AstrBot 記成 ERRO、其實是 QQ 那邊拿不到東西的：被引用的那條撤回了或太舊、被 @ 的號查不到。
# 它跳過那一段、消息照常處理，面板記成警告，不算錯誤
# 被 @ 的號群裡查不到：NapCat 4.18 起說成「群(…)成員N不存在」，多半是剛進群、成員名單還沒刷新（群管家 @ 新人歡迎）
# QQ 那邊這一刻自己掉了一下狀態（NapCat「账号状态变更为离线」），查 @ 的人時報「reading 'coreInfo'」，馬上又好了（10-29 14:45）
# QQ 商城表情的圖 QQ 那邊給的鏈接 404（gxh.vip.qq.com）：AstrBot 每條消息都先下載圖，下載不到就印 ERRO，消息照常處理
QQ_SIDE_RE = re.compile(
    r"获取引用消息失败.*消息为空|获取 @ 用户信息失败.*(?:Uin2Uid Error|成员\d+不存在|reading 'coreInfo')"
    r"|Failed to download file from https URL host='gxh\.vip\.qq\.com'",
    re.S,
)
# 斷網、DeepSeek 連不上：AstrBot 重試 5 次都不通記 ERRO。是網路那頭的事，記成警告；連得上了自己標「恢复了」（10-31 用戶定）
NET_RE = re.compile(r"Network connection failed \(APIConnectionError\)|Request failed with retryable error.*Connection error")
NET_PROBE = "https://api.deepseek.com"
# 熱重載（10-31）：部署時往 reload.req 寫插件名（一行一個），面板叫 AstrBot 重載那幾個插件、結果寫進 reload.done。
# 不用重啟、QQ 不斷線；重載自己也行（另開一個不歸面板管的任務做，面板被卸載時它不會被一起取消）
RELOAD_EVERY = 2
_RELOADS: set = set()
# AstrBot 臨時資料夾滿了自己清掉舊檔：平常的打掃，不記
HOUSEKEEP_RE = re.compile(r"^Temp dir exceeded limit")
LOG_MAX = 600


def _clip_log(msg: str) -> str:
    """太長的只留頭尾：Traceback 真正的錯誤在最後一行，以前只留開頭就看不出是什麼錯"""
    if len(msg) <= LOG_MAX:
        return msg
    head = msg.split("\n", 1)[0][:120]
    return head + "\n…\n" + msg[-(LOG_MAX - len(head) - 3):]


class _Ring(logging.Handler):
    """收集 WARNING 以上的日誌給面板看；同時寫進 logs.jsonl，重啟以後最近幾天的還看得到"""

    def __init__(self, buf: deque, path: Path, lock):
        super().__init__(level=logging.WARNING)
        self.buf, self.path, self.file_lock = buf, path, lock  # 不能叫 self.lock：logging.Handler 自己用這個名字

    def emit(self, record):
        try:
            msg = ANSI_RE.sub("", record.getMessage())
            if HOUSEKEEP_RE.search(msg):
                return
            if record.exc_info:
                msg += "\n" + logging.Formatter().formatException(record.exc_info)
            msg = _clip_log(msg)
            level = "WARNING" if QQ_SIDE_RE.search(msg) or NET_RE.search(msg) else record.levelname
            e = {"ts": record.created, "level": level, "src": record.name, "msg": msg}
            self.buf.append(e)
            with self.file_lock, self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except Exception:
            pass


def _recent(path: Path, lines: int = 5000) -> list[dict]:
    """jsonl 檔尾裡最近 KEEP_DAYS 天的記錄，舊的在前"""
    cut, out = time.time() - KEEP_SECS, []
    for line in tail_lines(path, lines):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if isinstance(e, dict) and (e.get("ts") or 0) >= cut:
            out.append(e)
    return out


def _archive(path: Path, lock=None) -> int:
    """把超過 KEEP_DAYS 天的行搬進同目錄 archive/<檔名>-<年-月>.jsonl，回傳搬了幾行"""
    cut = time.time() - KEEP_SECS
    with (lock or threading.Lock()):
        try:
            lines = path.read_text("utf-8").splitlines()
        except FileNotFoundError:
            return 0
        keep, old = [], {}
        for line in lines:
            try:
                ts = float(json.loads(line).get("ts") or 0)
            except Exception:
                continue  # 寫到一半的壞行丟掉
            if ts >= cut:
                keep.append(line)
            else:
                old.setdefault(datetime.fromtimestamp(ts, TZ).strftime("%Y-%m"), []).append(line)
        if not old:
            return 0
        adir = path.parent / "archive"
        adir.mkdir(exist_ok=True)
        for month, rows in old.items():
            with (adir / f"{path.stem}-{month}.jsonl").open("a", encoding="utf-8") as f:
                f.write("\n".join(rows) + "\n")
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""), "utf-8")
        tmp.replace(path)
        return sum(len(r) for r in old.values())


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
        self.log_file = self.dir / "logs.jsonl"
        self._log_lock = threading.Lock()
        self.logs: deque = deque(_recent(self.log_file, 3000), maxlen=3000)
        self._ring = _Ring(self.logs, self.log_file, self._log_lock)
        logging.getLogger("astrbot").addHandler(self._ring)
        self.runner: web.AppRunner | None = None
        self._cf_cache: tuple[str, float, dict] = ("", 0.0, {})  # (團隊域名, 拉的時間, kid -> 公鑰)
        self.gn_file = self.dir / "group_names.json"
        GROUP_NAMES.update(self._saved_group_names())
        self.qq_file = self.dir / "qq.json"  # QQ 登著沒有、從幾點開始：重啟也不丟
        # 飯錢頁那兩個介面要把幾萬行記錄重算一遍（/api/usage 約 1.7 秒），一分鐘內重複打就用上次算好的；
        # 任何一次寫（POST）都清掉，記了投喂、改了設定馬上看得到（10-29）
        self._heavy: dict[str, tuple[float, bytes]] = {}
        try:
            self.qq = json.loads(self.qq_file.read_text("utf-8"))
        except Exception:
            self.qq = {"online": None, "since": 0}
        self._task = asyncio.create_task(self._serve())
        self._archive_task = asyncio.create_task(self._archive_loop())
        self._qq_task = asyncio.create_task(self._qq_loop())
        self._net_task = asyncio.create_task(self._net_loop())
        self._reload_task = asyncio.create_task(self._reload_loop())

    async def terminate(self):
        logging.getLogger("astrbot").removeHandler(self._ring)
        self._task.cancel()
        self._archive_task.cancel()
        self._qq_task.cancel()
        self._net_task.cancel()
        self._reload_task.cancel()
        if self.runner:
            await self.runner.cleanup()

    # ---------- 服務 ----------
    async def _archive_loop(self):
        """面板自己的值班日誌、操作記錄：超過 KEEP_DAYS 天的搬進 archive/"""
        while True:
            for path, lock in ((self.log_file, self._log_lock), (self.audit_file, None)):
                try:
                    n = _archive(path, lock)
                    if n:
                        logger.info(f"[lively_panel] {path.name} 里 {n} 条超过 {KEEP_DAYS} 天的记录搬进了 archive/")
                except Exception as e:
                    logger.debug(f"[lively_panel] 归档 {path.name} 失败: {e}")
            await asyncio.sleep(ARCHIVE_EVERY)

    async def _qq_online(self) -> bool:
        try:
            await asyncio.wait_for(self._client().get_login_info(), timeout=5)
            return True
        except Exception:
            return False

    async def _qq_loop(self):
        """每分鐘看一次 QQ 登著沒有。掉線記一條錯誤（值班記錄、小紅點看得到），連回來記一條、把那條錯誤標成已恢復"""
        await asyncio.sleep(60)  # 開機時適配器要半分鐘才連上
        while True:
            try:
                on = await self._qq_online()
                if on != self.qq.get("online"):
                    was, since, now = self.qq.get("online"), float(self.qq.get("since") or 0), time.time()
                    self.qq = {"online": on, "since": now}
                    self.qq_file.write_text(json.dumps(self.qq), "utf-8")
                    if not on:
                        logger.error(f"[lively_panel] QQ 掉线了（{datetime.now(TZ):%m-%d %H:%M} 发现）：收不到也发不出消息。"
                                     "要在 NapCat 那边重新登录（扫码），登上以后会自己恢复")
                    elif was is False:
                        mins = int((now - since) / 60) if since else 0
                        logger.warning(f"[lively_panel] QQ 重新连上了" + (f"（掉线约 {mins} 分钟）" if mins else ""))
                        self._mark_fixed(lambda e: str(e.get("msg", "")).startswith("[lively_panel] QQ 掉线了"),
                                         f"QQ {datetime.now(TZ):%m-%d %H:%M} 重新连上了")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"[lively_panel] 看 QQ 在不在线失败: {e}")
            await asyncio.sleep(60)

    async def _reload_loop(self):
        req, done = self.dir / "reload.req", self.dir / "reload.done"
        while True:
            try:
                if req.exists():
                    names = [x.strip() for x in req.read_text("utf-8").split() if x.strip()]
                    req.unlink()
                    t = asyncio.get_running_loop().create_task(self._reload(names, done))
                    _RELOADS.add(t)
                    t.add_done_callback(_RELOADS.discard)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[lively_panel] 读热重载请求失败: {e}")
            await asyncio.sleep(RELOAD_EVERY)

    async def _reload(self, names: list[str], done: Path):
        mgr = getattr(self.context, "_star_manager", None)
        out = []
        for name in names:
            # 短名補成 lively 的全名；第三方插件（meme_manager 這種）照登記的名字寫就是（10-31）
            if not name.startswith("astrbot_plugin_") and not any(m.name == name for m in self.context.get_all_stars()):
                name = f"astrbot_plugin_lively_{name}"
            t0 = time.time()
            try:
                if mgr is None:
                    raise RuntimeError("拿不到插件管理器")
                if any(m.name == name for m in self.context.get_all_stars()):
                    res = await mgr.reload(name)
                elif (Path(__file__).resolve().parent.parent / name).is_dir():
                    res = await mgr.reload_failed_plugin(name)  # 上次載入失敗的不在名單裡；名字不對時 reload 會把全部插件重載一遍
                else:
                    raise RuntimeError("没有这个插件")
                ok, err = (res if isinstance(res, tuple) else (bool(res), None))[:2]
            except Exception as e:
                ok, err = False, f"{type(e).__name__}: {e}"
            out.append({"name": name, "ok": bool(ok), "err": str(err or "")[:500], "secs": round(time.time() - t0, 1)})
            (logger.info if ok else logger.error)(f"[lively_panel] 热重载 {name}：{'好了' if ok else '失败 ' + str(err)}")
        try:
            done.write_text(json.dumps({"ts": int(time.time()), "results": out}, ensure_ascii=False), "utf-8")
        except Exception as e:
            logger.warning(f"[lively_panel] 写热重载结果失败: {e}")

    @staticmethod
    def _net_down(e: dict) -> bool:
        return not e.get("fixed") and bool(NET_RE.search(str(e.get("msg", ""))))

    async def _net_loop(self):
        """值班記錄裡有還沒標的「連不上」，每分鐘試一下連不連得上 DeepSeek（回什麼都算連上），連上了就把那些標成恢复了"""
        await asyncio.sleep(60)
        while True:
            try:
                if any(self._net_down(e) for e in list(self.logs)):
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                        async with s.get(NET_PROBE) as r:
                            await r.read()
                    logger.info("[lively_panel] 又连得上 DeepSeek 了，之前连不上的标成恢复了")
                    self._mark_fixed(self._net_down, f"网络恢复了，又连得上 DeepSeek（{datetime.now(TZ):%m-%d %H:%M} 恢复）")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"[lively_panel] 试连 DeepSeek 还不通: {e}")
            await asyncio.sleep(60)

    def _mark_fixed(self, match, text: str):
        """值班記錄裡對得上的、還沒標過的記錄標成已修復（記憶體裡和 logs.jsonl 都改）"""
        hit = False
        for e in self.logs:
            if not e.get("fixed") and match(e):
                e["fixed"] = text
                hit = True
        if not hit:
            return
        with self._log_lock:
            try:
                rows = []
                for line in self.log_file.read_text("utf-8").splitlines():
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if not e.get("fixed") and match(e):
                        e["fixed"] = text
                    rows.append(json.dumps(e, ensure_ascii=False))
                tmp = self.log_file.with_suffix(".tmp")
                tmp.write_text("\n".join(rows) + "\n", "utf-8")
                tmp.replace(self.log_file)
            except Exception as e:
                logger.debug(f"[lively_panel] 标已恢复失败: {e}")

    @web.middleware
    async def _gzip(self, request: web.Request, handler):
        """JSON、填過字的腳本和頁面壓一下再送：從外面連進來時慢在傳輸（人物表 200KB，壓完 20 多 KB）"""
        resp = await handler(request)
        if (type(resp) is web.Response and "gzip" in request.headers.get("Accept-Encoding", "")
                and resp.body is not None and len(resp.body) > 1500
                and resp.content_type in ("application/json", "text/html", "application/javascript", "text/javascript")):
            resp.enable_compression(web.ContentCoding.gzip)
        return resp

    async def _serve(self):
        app = web.Application(middlewares=[self._guard, self._gzip], client_max_size=64 * 1024)
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
        r.add_get("/api/heart", self.heart)
        r.add_get("/api/settings", self.settings)
        r.add_post("/api/settings", self.set_setting)
        r.add_get("/api/pending", self.pending)
        r.add_post("/api/pending", self.act_pending)
        r.add_get("/api/logs", self.get_logs)
        r.add_post("/api/report", self.make_report)
        r.add_post("/api/comic", self.draw_comic)
        r.add_get("/api/image", self.image)
        r.add_get("/api/feedbg/{tier}", self.feed_bg)
        r.add_get("/api/cardbg/{qq}", self.card_bg)
        r.add_get("/api/madeav/{qq}", self.made_av)
        r.add_get("/api/avatar/{qq}", self.avatar)
        r.add_get("/api/billing", self.billing)
        r.add_get("/api/usage", self.usage)
        r.add_get("/api/ledger", self.ledger)
        r.add_post("/api/feeds", self.feeds_act)
        r.add_get("/api/meme", self.meme_thumb)
        r.add_post("/api/memepref", self.meme_pref_act)
        r.add_get("/api/memes", self.memes)
        r.add_post("/api/memes", self.memes_act)
        r.add_get("/api/mind", self.mind)
        r.add_get("/api/evolve", self.evolve)
        r.add_post("/api/asks", self.asks_act)
        r.add_post("/api/bot", self.bot_act)
        r.add_post("/api/selfnotes", self.self_notes_act)
        r.add_get("/api/memline", self.memline)
        r.add_get("/api/memline/node", self.memline_node)
        r.add_get("/api/memline/point", self.memline_point)
        r.add_get("/api/memline/time", self.memline_time)
        r.add_post("/api/memline", self.memline_act)
        r.add_post("/api/evolve", self.evolve_act)
        r.add_post("/api/mind/beat", self.mind_beat)
        r.add_post("/api/mind/review", self.mind_review)
        r.add_post("/api/mind/try", self.mind_try)
        r.add_post("/api/brain", self.brain_set)
        r.add_get("/api/pclog", self.pclog)
        r.add_get("/api/pcshot", self.pcshot)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        for _ in range(10):
            try:
                await web.TCPSite(self.runner, self.host, self.port).start()
                logger.info(f"[lively_panel] 面板已启动：{self.host}:{self.port}")
                if self._allowed() and not all(self._cf_conf()):
                    logger.warning("[lively_panel] 没填 cf_team_domain / cf_aud：外网来的请求只看 Cf-Access 邮箱头、"
                                   "不验签名，同一个 docker 网络里的容器伪造这个头就能进。建议在插件配置里填上")
                await self.s.fetch_bot_qq()
                await self._group_names()
                return
            except OSError as e:  # 重載插件時舊的端口可能還沒放開
                logger.warning(f"[lively_panel] 端口占用，稍后重试: {e}")
                await asyncio.sleep(3)

    def _allowed(self) -> set[str]:
        return {str(e).strip().lower() for e in self.s.get("allowed_emails", []) if str(e).strip()}

    def _cf_conf(self) -> tuple[str, str]:
        """(團隊域名 xxx.cloudflareaccess.com, Access 應用的 AUD)"""
        team = str(self.s.get("cf_team_domain", "") or "").strip().lower()
        team = re.sub(r"^https?://", "", team).strip("/")
        return team, str(self.s.get("cf_aud", "") or "").strip()

    async def _cf_keys(self, team: str, refresh: bool = False) -> dict:
        """Access 的簽名公鑰，快取一小時；簽名用的 kid 對不上時重拉（最多一分鐘一次，Cloudflare 會輪換）"""
        cached_team, at, keys = self._cf_cache
        age = time.time() - at
        if cached_team == team and (age < 60 or (age < CF_CERTS_TTL and not refresh)):
            return keys
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
                async with s.get(f"https://{team}/cdn-cgi/access/certs") as r:
                    data = await r.json(content_type=None)
        except Exception:
            self._cf_cache = (team, time.time(), keys if cached_team == team else {})  # 拉不到也記時間，別每個請求都去拉
            raise
        keys = {k["kid"]: k for k in data.get("keys") or [] if k.get("kty") == "RSA" and k.get("kid")}
        self._cf_cache = (team, time.time(), keys)
        return keys

    async def _cf_email(self, request: web.Request, team: str, aud: str) -> str:
        """驗 Cloudflare Access 給的 JWT（簽名、aud、iss、有效期），過了回裡面的郵箱，不過回空字串"""
        token = request.headers.get("Cf-Access-Jwt-Assertion") or request.cookies.get("CF_Authorization") or ""
        try:
            h64, p64, s64 = token.split(".")
            head, claims = json.loads(_b64url(h64)), json.loads(_b64url(p64))
            if head.get("alg") != "RS256":
                return ""
            key = (await self._cf_keys(team)).get(head.get("kid"))
            if key is None:
                key = (await self._cf_keys(team, refresh=True)).get(head.get("kid"))
            if key is None or not _rs256_ok(key, f"{h64}.{p64}".encode(), _b64url(s64)):
                return ""
            auds = claims.get("aud") if isinstance(claims.get("aud"), list) else [claims.get("aud")]
            now = time.time()
            if (aud not in auds or claims.get("iss") != f"https://{team}"
                    or float(claims.get("exp") or 0) < now - 30 or float(claims.get("nbf") or 0) > now + 30):
                return ""
            return str(claims.get("email") or "").strip().lower()
        except Exception as e:
            logger.debug(f"[lively_panel] Access 令牌没验过: {e}")
            return ""

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if request.path == "/healthz":
            return await handler(request)
        who = None
        if request.remote in TRUSTED:
            who = "local"
        else:
            team, aud = self._cf_conf()
            if team and aud:
                email = await self._cf_email(request, team, aud)
            else:  # 沒填就只看頭（開機時日誌會提醒）
                email = (request.headers.get("Cf-Access-Authenticated-User-Email") or "").strip().lower()
            if email and email in self._allowed():
                who = email
        if not who:
            return web.Response(status=403, text="没有权限")
        request["who"] = who
        if request.method == "POST":
            if request.headers.get("X-Lively") != "1":
                return web.Response(status=400, text="缺少请求头")
            self._heavy.clear()
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
        elif request.path.startswith(("/api/feedbg/", "/api/cardbg/", "/api/madeav/")) and resp.status == 200:
            resp.headers["Cache-Control"] = "private, max-age=3600"
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

    HEAVY_TTL = 60

    async def _cached(self, key: str, make):
        # 存的是算好的正文：同一個 Response 只能送出去一次
        hit = self._heavy.get(key)
        if hit and time.time() - hit[0] < self.HEAVY_TTL:
            return web.Response(body=hit[1], content_type="application/json")
        resp = await make()
        if resp.status == 200 and isinstance(resp.body, (bytes, bytearray)):
            self._heavy[key] = (time.time(), bytes(resp.body))
        return resp

    async def usage(self, request):
        """按人看聊天回覆花了多少、什麼時候來，加上畫像"""
        b = self._star("lively_billing")
        if not b or not hasattr(b, "users"):
            return self._err("饭钱插件没加载，或者版本太旧，还不会按人记", 503)
        try:
            days = max(1, min(60, int(request.query.get("days", 30))))
        except ValueError:
            days = 30
        return await self._cached(f"usage:{days}", lambda: self._usage(b, days))

    async def _usage(self, b, days: int):
        data = await asyncio.to_thread(b.users, days)
        try:
            bond = {str(r["qq"]): r for r in await asyncio.to_thread(self._bond_rows)}
        except Exception:
            bond = {}
        rels = self._rel_map()
        for q, r in bond.items():
            self._with_rel(r, rels.get(q))
        gnames = await self._group_names()
        owners, now = set(self.s.owners()), time.time()
        us = data["users"]
        max_turns = max((u["turns"] for u in us if u["qq"] not in owners), default=0)
        pts = sorted(u["cost"] / u["turns"] for u in us if u["turns"])
        med = pts[len(pts) // 2] if pts else 0.0
        for u in us:
            p = bond.get(u["qq"], {})
            u["name"] = p.get("name") or u["name"] or u["qq"]
            u["favor"] = p.get("favor")
            u["owner"] = u["qq"] in owners
            u.update(_profile(u, days, now, max_turns, med))
            u["tags"] = [self.s.fill(t) for t in u["tags"]]
        data["group_names"] = {**data.get("group_names", {}), **gnames}
        # 錢花在哪（按做的事分類）、投餵記錄
        if hasattr(b, "spend"):
            try:
                data["spend"] = self._fill_deep(await asyncio.to_thread(b.spend, days))
            except Exception as e:
                logger.warning(f"[lively_panel] 算钱花在哪失败: {e}")
        if hasattr(b, "feeds"):
            feeds = await asyncio.to_thread(b.feeds)
            for f in feeds:
                f["name"] = (bond.get(f["qq"]) or {}).get("name") or f.get("name") or f["qq"]
                if hasattr(b, "feed_from"):  # 怎麼記下的：〈我〉聽誰說的、主人在後台記的
                    f["from"] = self.s.fill(b.feed_from(f))
            fed = {}
            for f in feeds:
                fed[f["qq"]] = round(fed.get(f["qq"], 0) + f["amount"], 2)
            for u in us:
                u["fed"] = fed.get(u["qq"], 0)
            data["feeds"] = feeds
            # 投喂榜：按累計排，帶筆數、最近一次、檔位（檔位是 bond 關係讀口算的，和〈卡〉上的一樣）
            by = {}
            for f in feeds:  # feeds 已按時間新到舊排
                r = by.setdefault(f["qq"], {"qq": f["qq"], "name": f["name"], "total": 0.0, "n": 0,
                                            "last": f.get("ts", 0), "owner": f["qq"] in owners})
                r["total"] = round(r["total"] + f["amount"], 2)
                r["n"] += 1
            for q, r in by.items():
                t = (rels.get(q) or {}).get("fed") or {}
                if t.get("tier"):
                    r.update(tier=t["tier"], tier_name=self.s.fill(t.get("tier_name") or ""))
            data["feeders"] = sorted(by.values(), key=lambda r: (-r["total"], -r["last"]))
        return self._ok(data)

    async def ledger(self, request):
        """按天的帳：每天餘額實際掉了多少、花在哪、每個鐘點、誰、最貴的幾次（飯錢插件的 ledger）"""
        b = self._star("lively_billing")
        if not b or not hasattr(b, "ledger"):
            return self._err("饭钱插件没加载，或者版本太旧，还不会按天记账", 503)
        try:
            days = max(1, min(60, int(request.query.get("days", 30))))
        except ValueError:
            days = 30
        return await self._cached(f"ledger:{days}", lambda: self._ledger(b, days))

    async def _ledger(self, b, days: int):
        data = await asyncio.to_thread(b.ledger, days)
        try:
            names = await asyncio.to_thread(self._people_names)
        except Exception:
            names = {}
        for d in data.get("list", []):
            for p in d.get("people", []) + d.get("feeds", []):
                p["name"] = names.get(str(p.get("qq"))) or p.get("name") or p.get("qq")
        return self._ok(self._fill_deep(data))

    async def feeds_act(self, request):
        """記一筆投餵、刪一筆記錯的（帳本在飯錢插件，面板只是幫著記）"""
        b = self._star("lively_billing")
        if not b or not hasattr(b, "add_feed"):
            return self._err("饭钱插件没加载，或者版本太旧，还不会记投喂", 503)
        body = request["body"]
        a = body.get("action")
        try:
            if a == "add":
                qq, ts, day = str(body.get("qq", "")).strip(), None, str(body.get("date") or "")
                if day and day != datetime.now(TZ).strftime("%Y-%m-%d"):
                    try:
                        ts = datetime.strptime(day, "%Y-%m-%d").replace(hour=12, tzinfo=TZ).timestamp()
                    except ValueError:
                        return self._err("日期不对")
                name = (await asyncio.to_thread(self._people_names)).get(qq) or ""
                r = await asyncio.to_thread(b.add_feed, qq, float(body.get("amount") or 0), ts, str(body.get("note") or ""), name, "panel")
                return self._ok(r, msg=f"记下了：{r['name'] or qq} 投喂 ¥{r['amount']:g}")
            if a == "del":
                r = await asyncio.to_thread(b.del_feed, str(body.get("id", "")))
                return self._ok(msg=f"删掉了 {r.get('name') or r['qq']} 那笔 ¥{r['amount']:g}") if r else self._err("没有这一笔")
        except (ValueError, TypeError) as e:
            return self._err(str(e))
        return self._err("值不对")

    def _me(self) -> dict:
        """頁面要知道的身份訊息（主人、機器人是誰）"""
        has = lambda d: (STATIC / d).is_dir() and any((STATIC / d).iterdir())
        # 表情包不隨倉庫發佈（見 README），沒放進來就不顯示
        return {"owner": self.s.owner(), "bot_qq": self.s.bot_qq(), "bot_name": self.s.bot_name() or self.s.bot_qq(),
                "meme": has("meme")}

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

    def _fill_deep(self, v):
        """結果裡的每個字串都換成人設用詞（整包 json 換字的話，填入的詞帶引號或反斜線會把 JSON 弄壞）"""
        if isinstance(v, str):
            return self.s.fill(v)
        if isinstance(v, dict):
            return {k: self._fill_deep(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [self._fill_deep(x) for x in v]
        return v

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
        if not out["online"]:
            out["offline_since"] = self.qq.get("since") if self.qq.get("online") is False else None
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
            counts["待审申请"] = sum(1 for v in s.state.get("pending", {}).values() if not v.get("her"))
        out["counts"] = counts
        m = self._star("lively_mind")
        if m:
            out["mind"] = {"thought": m.state.get("thought"), "enabled": m.state.get("enabled", True)}
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
            for line in tail_lines(PD / d / "events.jsonl", 30):
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

    def _rel_map(self) -> dict:
        """bond 的關係讀口：qq -> 好感度、檔位、態度……（要在事件迴圈裡叫，bond 的連線不跨執行緒）。舊版 bond 沒有就空的"""
        b = self._star("lively_bond")
        if not b or not hasattr(b, "relations"):
            return {}
        try:
            return {r["qq"]: r for r in b.relations()}
        except Exception as e:
            logger.warning(f"[lively_panel] 问 bond 的关系失败: {e}")
            return {}

    def _rel_one(self, qq: str) -> dict | None:
        b = self._star("lively_bond")
        if not b or not hasattr(b, "relation"):
            return None
        try:
            return b.relation(qq)
        except Exception as e:
            logger.warning(f"[lively_panel] 问 bond 的关系失败: {e}")
            return None

    def _with_rel(self, row: dict, rel: dict | None) -> dict:
        """好感度、檔位、說明換成關係讀口的（舊好感留在 favor_old）；頁面照舊讀 favor"""
        if not rel:
            return row
        row["favor_old"] = row.get("favor")
        row["favor"] = row["score"] = rel["score"]
        row["score_parts"] = {"base": rel["base"], "live": rel["live"], "adjust": rel["adjust"],
                              "lean": rel.get("lean", 0), "lean_why": rel.get("lean_why", ""), "raw": rel.get("raw"),
                              "grow_cap": rel.get("grow_cap")}
        row["tier"] = rel["tier"]
        row["stage"] = self.s.fill(rel["stage"])
        row["favor_desc"] = self.s.fill(rel["desc"])
        if rel["attitude"]:
            row["attitude"] = rel["attitude"]
        if rel.get("impression"):  # 心裡的 TA 的印象優先，和說話時、〈卡〉正面一致
            row["impression"] = rel["impression"]
        if rel.get("fed"):  # 投喂過的：累計、檔位（〈卡〉換成這一檔的樣子）
            row["fed"] = rel["fed"]
        f = rel.get("feel")  # 〈我〉跟 TA 的感情換成的字：line 是說話時給她看的那句，words 是〈卡〉上的短字
        if f:
            mod = self._heart_mod()
            got = mod.feel_pick(f.get("feelings") or {}) if mod and hasattr(mod, "feel_pick") else {}
            row["feel"] = {"line": self.s.fill(f.get("line") or ""), "public": f.get("public") or [],
                           "chips": [[d, got[d][1], (f.get("feelings") or {}).get(d, 0)] for d in got]}
        if rel.get("known_days") is not None:
            row["known_days"] = rel["known_days"]
        if rel.get("bot"):  # TA 是 bot（11-03）：〈卡〉、卡册、人泡泡畫那家的標誌（不知道哪家畫小機器人）
            row["bot"] = True
            info = rel.get("bot_info") or {}
            row["bot_vendor"], row["bot_model"] = info.get("vendor") or "", info.get("model") or ""
            row["bot_by"] = "主人标的" if info.get("owner_set") else ("她记的" + (f"：{info['how']}" if info.get("how") else ""))
        return row

    def _card_bgs(self) -> dict:
        """bond 的專屬〈卡〉背景：qq -> {path, v, dark, deep, look}；舊版 bond 沒有就空的"""
        b = self._star("lively_bond")
        if not b or not hasattr(b, "card_bgs"):
            return {}
        try:
            return b.card_bgs()
        except Exception as e:
            logger.warning(f"[lively_panel] 读专属卡背景失败: {e}")
            return {}

    def _made_avs(self) -> dict:
        """群友定做的虛擬形象（bond 讀 comic 的 avatars/）：qq -> {card, sheet, v}；主人不在裡面；舊版 bond 沒有就空的"""
        b = self._star("lively_bond")
        if not b or not hasattr(b, "made_avatars"):
            return {}
        try:
            return b.made_avatars()
        except Exception as e:
            logger.warning(f"[lively_panel] 读定做的形象失败: {e}")
            return {}

    @staticmethod
    def _with_av(row: dict, avs: dict) -> dict:
        """定做了虛擬形象的：〈卡〉和卡冊放那張（v 是修改時間，重做了網址跟著變）"""
        if (a := avs.get(str(row.get("qq")))):
            row["made_av"] = {"v": a["v"]}
        return row

    @staticmethod
    def _with_bg(row: dict, bgs: dict) -> dict:
        """有專屬背景的：〈卡〉用這張畫（v 是修改時間，換了圖網址跟著變；dark 配深色玻璃；deep 是畫底下的顏色）"""
        if (b := bgs.get(str(row.get("qq")))):
            row["card_bg"] = {"v": b["v"], "dark": b["dark"], "deep": b["deep"]}
        return row

    def _describe(self, p: dict) -> dict:
        mod = self._bond_mod()
        out = {}
        if mod:
            for fn in ("stage", "favor_desc", "mood_desc"):
                try:
                    out[fn] = self.s.fill(getattr(mod, fn)(p))  # bond 的說明文字帶〈我〉〈主人〉佔位符
                except Exception:
                    pass
        return out

    # ---------- 情感（bond 的 heart.py：片段、感情、心裡的 TA、態度） ----------
    def _heart_mod(self):
        b = self._star("lively_bond")
        mod = b and sys.modules.get(type(b).__module__.rsplit(".", 1)[0] + ".heart")
        return mod if mod and hasattr(mod, "HeartStore") else None

    def _heart_ro(self, con):
        """借 bond 的 HeartStore 讀資料：只用它的讀方法，不跑 __init__（那裡會建表），連線是唯讀的"""
        mod = self._heart_mod()
        if not mod:
            return None
        hs = object.__new__(mod.HeartStore)
        hs.db = con
        return hs

    def _heart_meta(self) -> dict:
        mod = self._heart_mod()
        return {"dims": list(mod.DIMS), "half_life": dict(mod.HALF_LIFE), "attitudes": list(mod.ATTITUDES),
                "kinds": list(mod.KINDS)} if mod else {}

    @staticmethod
    def _moment_out(m: dict, names: dict) -> dict:
        scope = str(m.get("scope") or "")
        where = "私聊" if scope == "dm" else GROUP_NAMES.get(scope.split(":", 1)[-1], scope.replace("group:", "群")) if scope else ""
        return {"id": m["id"], "qq": m["qq"], "name": names.get(m["qq"]) or m["qq"], "ts": m["ts"], "where": where,
                "private": bool(m["private"]), "text": m["text"], "feeling": m["feeling"], "kind": m["kind"],
                "weight": m["weight"], "impacts": m["impacts"],
                "others": [{"qq": q, "name": names.get(q) or q} for q in m["others"]]}

    def _heart_rows(self) -> dict:
        """卡冊用：每個人的態度和各種感情"""
        con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
        try:
            hs = self._heart_ro(con)
            if not hs:
                return {}
            out = {r["qq"]: {"feelings": self._shown_feelings(hs, r["qq"]), "moments": r["n"]}
                   for r in con.execute("select qq, count(*) n from moments group by qq")}
            for r in con.execute("select qq, attitude from stance where attitude>0"):
                out.setdefault(r["qq"], {})["attitude"] = r["attitude"]
            return out
        except sqlite3.Error:  # bond 還是舊版，沒有這幾張表
            return {}
        finally:
            con.close()

    def _heart_person(self, con, qq: str, names: dict) -> dict | None:
        hs = self._heart_ro(con)
        if not hs:
            return None
        try:
            st = hs.get_stance(qq)
            h = hs.get_heart(qq)
            return {"heart": h, "feelings": self._shown_feelings(hs, qq), "feelings_all": hs.feelings(qq),
                    "stance": st, "unsent": self._heart_unsent(h),
                    "balance": hs.balance(qq) if hasattr(hs, "balance") else None,
                    "moments": [self._moment_out(m, names) for m in hs.moments(qq, 120)],
                    "moment_count": hs.moment_count(qq), "meta": self._heart_meta()}
        except sqlite3.Error:
            return None

    @staticmethod
    def _shown_feelings(hs, qq: str) -> dict:
        """給她看的那份感情（不算疙瘩的片段的芥蒂不算，見 bond heart.not_grudge）；舊版 bond 沒有就全部的"""
        try:
            return hs.feelings(qq, shown=True)
        except TypeError:
            return hs.feelings(qq)

    def _heart_unsent(self, h: dict | None) -> dict:
        """心裡的 TA 說話時按欄位挑（bond heart_fit），放不下的欄這次沒帶給她：群裡、私聊各哪幾欄"""
        mod = self._heart_mod()
        if not h or not mod or not hasattr(mod, "heart_fit"):
            return {}
        budget = getattr(sys.modules.get(mod.__name__.rsplit(".", 1)[0] + ".core"), "HEART_MAX", 260)
        return {"group": mod.heart_fit(h, private=False, memories=False, budget=budget)[1],
                "dm": mod.heart_fit(h, private=True, memories=False, budget=budget)[1]}

    async def heart(self, request):
        await self._group_names()
        return self._ok(await asyncio.to_thread(self._heart_overview))

    def _heart_overview(self) -> dict:
        con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
        try:
            hs = self._heart_ro(con)
            if not hs:
                return {"ready": False}
            names = {r["qq"]: r["name"] for r in con.execute("select qq, name from people")}
            one = lambda sql, *a: con.execute(sql, a).fetchone()[0]
            day0 = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            meta = con.execute("select v from meta where k='reflect_init'").fetchone()
            out = {"ready": True, "meta": self._heart_meta(),
                   "moments": one("select count(*) from moments"),
                   "today": one("select count(*) from moments where created>=?", day0),
                   "people": one("select count(distinct qq) from moments"),
                   "hearts": one("select count(*) from hearts"),
                   "hearts_today": one("select count(*) from hearts where updated>=?", day0),
                   "digested": one("select count(*) from digested"),
                   "last_digest": one("select max(ts) from digested") or 0,
                   "init_done": bool(meta and meta[0])}
            out["feelings_week"] = dict(con.execute(
                "select feeling, count(*) from moments where ts>=? group by feeling order by 2 desc", (time.time() - 7 * 86400,)).fetchall())
            out["recent"] = [self._moment_out(m, names) for m in (
                dict(r, impacts=json.loads(r["impacts"] or "{}"), others=json.loads(r["others"] or "[]"))
                for r in con.execute("select * from moments order by ts desc limit 12"))]
            out["stanced"] = [dict(s, name=names.get(s["qq"]) or s["qq"]) for s in hs.stanced(1)]
        except sqlite3.Error as e:
            return {"ready": False, "error": str(e)[:120]}
        finally:
            con.close()
        try:
            m = _ro(PD / "astrbot_plugin_livingmemory" / "livingmemory.db")
            out["memories"] = m.execute("select count(*) from documents").fetchone()[0]
            # 每一層現在有幾條（壓進上一層的另算）；改名 lively 前 memtier 寫的是 xfy_*
            tiers, merged = {"raw": 0, "day": 0, "week": 0, "month": 0, "quarter": 0}, 0
            for (md,) in m.execute("select metadata from documents"):
                try:
                    d = json.loads(md or "{}")
                except Exception:
                    d = {}
                if d.get("lively_merged_into") or d.get("xfy_merged_into"):
                    merged += 1
                    continue
                t = d.get("lively_tier") or d.get("xfy_tier") or "raw"
                tiers[t] = tiers.get(t, 0) + 1
            out["tiers"], out["merged"] = tiers, merged
            m.close()
        except Exception:
            out["memories"] = 0
        out["forgotten"] = self._forgotten(names)
        out["asks"] = self._asks_ro(names)
        out["self_notes"] = self._self_notes_ro(names)
        return out

    def _asks_ro(self, names: dict) -> list[dict]:
        """〈主人〉交代的事（bond 的 owner_asks 表，她用 lively_owner_rule 記的）：掛在誰、哪個群、到哪都算"""
        try:
            con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
            try:
                rows = con.execute("select id, text, targets, ts, updated, src from owner_asks order by id").fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return []
        gn = GROUP_NAMES
        out = []
        for r in rows:
            try:
                ts_ = json.loads(r["targets"] or "[]")
            except Exception:
                ts_ = []
            where = []
            for t in ts_:
                kind, _, num = str(t).partition(":")
                if t == "all":
                    where.append("到哪都算")
                elif kind == "qq":
                    where.append(f"{names.get(num) or ('〈主人〉' if self.s.is_owner(num) else '还不认识')}（{num}）")
                elif kind == "group":
                    where.append(f"群「{gn.get(num) or num}」")
            out.append({"id": r["id"], "text": r["text"], "where": "、".join(where) or "到哪都算", "ts": r["ts"],
                        "updated": r["updated"], "src": "群里" if str(r["src"] or "").startswith("group") else "私聊里"})
        return out

    async def asks_act(self, request):
        """刪一條〈主人〉交代的事：走 bond 自己的連線（面板的連線是唯讀的）；刪了記一筆讓她知道"""
        b = self._star("lively_bond")
        if not b or not getattr(b, "asks", None):
            return self._err("情感插件没加载", 503)
        body = request["body"]
        if body.get("action") != "del" or not str(body.get("id", "")).isdigit():
            return self._err("action 要是 del，id 要是数字")
        a = b.asks.drop(int(body["id"]))
        if not a:
            return self._err("没有这一条")
        try:
            b.store.log(self.s.owner() or "", "owner_ask", 0, 0, f"面板删 交代{a['id']}｜{a['text']}"[:200], "panel")
            b.store.db.commit()
        except Exception as e:
            logger.warning(f"[lively_panel] 记删交代失败: {e}")
        if self.s.owner():
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在后台删了一条交代（交代{a['id']}）：「{a['text']}」，以后不会再带着"), f"{BACKSTAGE_KIND}:交代")
        return self._ok(msg="删了")


    async def bot_act(self, request):
        """人的頁面「TA 是 bot」：寫到 bond 的 bots 表；她那邊記一筆"""
        b = self._star("lively_bond")
        if not b or not hasattr(b, "set_bot"):
            return self._err("情感插件没加载", 503)
        body = request["body"]
        qq, on = str(body.get("qq") or ""), bool(body.get("on"))
        if not qq.isdigit() or self.s.is_owner(qq):
            return self._err("号码不对")
        vendor = body.get("vendor") if "vendor" in body else None
        model = body.get("model") if "model" in body else None
        if b.set_bot(qq, on, "〈主人〉在面板上标的", "panel", vendor, model) and self.s.owner():
            name = (b.relation(qq) or {}).get("name") or qq
            info = b.bot_info(qq) if on and hasattr(b, "bot_info") else None
            what = "真人（不是 bot）" if not on else "bot" + (f"（{info['vendor']}{' ' + info['model'] if info.get('model') else ''}）" if info and info.get("vendor") else "")
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在后台把「{name}」标成了{what}"), f"{BACKSTAGE_KIND}:bot")
        return self._ok(msg="标好了" if on else "不是 bot 了")

    def _self_notes_ro(self, names: dict) -> list[dict]:
        """〈我〉自己的事（bond 的 self_notes 表，她用 lively_self_note 記的）：每條誰告訴的、在哪記的"""
        try:
            con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
            try:
                rows = con.execute("select id, text, ts, updated, src, told_by, told_name from self_notes order by id").fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return []
        gn = GROUP_NAMES
        out = []
        for r in rows:
            by = str(r["told_by"] or "")
            if by == "self":
                who = "〈我〉自己知道的"
            elif self.s.is_owner(by):
                who = "〈主人〉说的"
            elif by:
                who = f"{names.get(by) or r['told_name'] or '还不认识'}（{by}）说的"
            else:
                who = ""
            kind, _, num = str(r["src"] or "").partition(":")
            where = f"群「{gn.get(num) or num}」" if kind == "group" else (
                "〈主人〉私聊" if self.s.is_owner(num) else f"和{names.get(num) or num}的私聊") if kind == "dm" else ""
            out.append({"id": r["id"], "text": r["text"], "ts": r["ts"], "updated": r["updated"], "who": who, "where": where,
                        "owner": self.s.is_owner(by) or by == "self"})
        return out

    async def self_notes_act(self, request):
        """刪一條〈我〉自己的事：走 bond 自己的連線；刪了記一筆讓她知道"""
        b = self._star("lively_bond")
        if not b or not getattr(b, "self_notes", None):
            return self._err("情感插件没加载", 503)
        body = request["body"]
        if body.get("action") != "del" or not str(body.get("id", "")).isdigit():
            return self._err("action 要是 del，id 要是数字")
        n = b.self_notes.drop(int(body["id"]))
        if not n:
            return self._err("没有这一条")
        try:
            b.store.log(self.s.owner() or "", "self_note", 0, 0, f"面板删 S{n['id']}｜{n['text']}"[:200], "panel")
            b.store.db.commit()
        except Exception as e:
            logger.warning(f"[lively_panel] 记删自己的事失败: {e}")
        if self.s.owner():
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在后台删了〈我〉本子上一条自己的事（S{n['id']}）：「{n['text']}」，以后不会再带着"),
                        f"{BACKSTAGE_KIND}:自己的事")
        return self._ok(msg="删了")

    # ---------- 記憶線：〈我〉自己的記憶（記憶插件的 view），面板不自己開它的庫 ----------
    def _memview(self):
        m = self._star("lively_memory")
        return getattr(m, "view", None) if m else None

    async def memline(self, request):
        v = self._memview()
        if not v:
            return self._err("记忆插件没加载", 503)
        return self._ok({**await asyncio.to_thread(v.graph), "unknowns": await asyncio.to_thread(v.unknowns)})

    async def memline_node(self, request):
        v = self._memview()
        if not v:
            return self._err("记忆插件没加载", 503)
        d = await asyncio.to_thread(v.node, request.query.get("id", ""))
        return self._ok(d) if d else self._err("没有这个点", 404)

    async def memline_point(self, request):
        v = self._memview()
        if not v:
            return self._err("记忆插件没加载", 503)
        d = await asyncio.to_thread(v.point, request.query.get("id", ""))
        return self._ok(d) if d else self._err("没有这一条", 404)

    async def memline_time(self, request):
        v = self._memview()
        if not v:
            return self._err("记忆插件没加载", 503)
        try:
            hours = float(request.query.get("hours", 48))
        except ValueError:
            hours = 48
        return self._ok(await asyncio.to_thread(v.timeline, hours))

    async def memline_act(self, request):
        """〈主人〉改一条（記一條新的取代它）、忘掉、找回、認人；都不真刪，做了記一筆讓她知道"""
        v = self._memview()
        if not v:
            return self._err("记忆插件没加载", 503)
        b = request["body"]
        a = b.get("action")
        try:
            if a == "claim":
                r = v.owner_claim(b.get("node", ""), b.get("to", ""))
                who = f"「{r['name']}」这个人" if r["to"].startswith("qq:") else "一件事、一个梗"
                tell, msg = f"〈主人〉认出来〈我〉记忆里的「{r['alias']}」是{who}，{r['points']} 条记忆挂到了那边", "认好了"
            else:
                if not str(b.get("id", "")).isdigit():
                    return self._err("id 要是数字")
                pid = int(b["id"])
                if a == "fix":
                    r = v.owner_fix(pid, b.get("text", ""))
                    tell, msg = f"〈主人〉把〈我〉记的 #{pid}「{r['old'][:80]}」改成了 #{r['new']}「{r['text']}」（旧的留着）", f"改好了，新的是 #{r['new']}"
                elif a == "forget":
                    r = v.owner_forget(pid)
                    tell, msg = f"〈主人〉让〈我〉忘掉 #{pid}「{r['text'][:80]}」，以后不会再想起来（找得回来）", "忘掉了"
                elif a == "restore":
                    r = v.owner_restore(pid)
                    tell, msg = f"〈主人〉把〈我〉忘掉的 #{pid}「{r['text'][:80]}」找回来了", "找回来了"
                else:
                    return self._err("action 要是 fix／forget／restore／claim")
        except (TypeError, ValueError) as e:
            return self._err(str(e) or "参数不对")
        if self.s.owner():
            note_outbox(self.s.private_umo(self.s.owner()), self.s.fill(tell), f"{BACKSTAGE_KIND}:记忆")
        return self._ok(r, msg=msg)

    def _forgotten(self, names: dict) -> list[dict]:
        """〈主人〉私聊裡讓〈我〉忘掉的記憶（mind 的 forgotten.jsonl，最近 KEEP_DAYS 天），加上記下要忘、還在等〈主人〉確認的。
        新的在前；只給看，不能找回（備份留在 forgotten.jsonl）"""
        d = PD / "astrbot_plugin_lively_mind"
        backup, out = {}, []
        for e in _recent(d / "forgotten.jsonl"):
            if e.get("stage") == "backup":
                backup[e.get("id")] = e
            elif e.get("result") in ("done", "failed"):
                b = backup.get(e.get("id")) or {}
                md = {}
                try:
                    md = json.loads(((b.get("record") or {}).get("metadata")) or "{}")
                except Exception:
                    pass
                out.append({"ts": e.get("ts"), "id": e.get("id"), "result": e["result"],
                            "why": e.get("why") or b.get("why") or "", "error": e.get("error") or "",
                            "summary": str(md.get("canonical_summary") or e.get("summary") or "")[:120],
                            "where": self._mem_where(str(md.get("session_id") or ""), names),
                            "date": str(md.get("source_time_label") or ""),
                            "moments": e.get("moments", len(b.get("moments") or []))})
        # 記下要忘、30 分鐘內還沒確認也沒刪的
        cut = time.time() - 30 * 60
        asked = {}
        for e in _recent(d / "events.jsonl", 3000):
            if e.get("kind") != "memory_forget":
                continue
            if e.get("result") == "asked" and (e.get("ts") or 0) >= cut:
                asked[e.get("id")] = e
            elif e.get("result") in ("done", "failed"):
                asked.pop(e.get("id"), None)
        for mid, e in asked.items():
            out.append({"ts": e.get("ts"), "id": mid, "result": "asked", "why": e.get("why") or "",
                        "summary": "", "where": "", "date": "", "moments": 0})
        out.sort(key=lambda r: -(r.get("ts") or 0))
        return out[:30]

    def _mem_where(self, sid: str, names: dict) -> str:
        tail = sid.rsplit(":", 1)[-1]
        if ":GroupMessage:" in sid:
            return f"群「{GROUP_NAMES.get(tail) or tail}」"
        if sid.startswith("livingmemory:user:"):
            return self.s.fill("和〈主人〉的私聊") if self.s.is_owner(tail) else f"和{names.get(tail) or tail}的私聊"
        return ""

    async def people(self, request):
        rows = await asyncio.to_thread(self._bond_rows)
        hearts = await asyncio.to_thread(self._heart_rows)
        rels = self._rel_map()
        bgs = await asyncio.to_thread(self._card_bgs)
        avs = await asyncio.to_thread(self._made_avs)
        for r in rows:
            r.update(self._describe(r))
            r.update(hearts.get(str(r["qq"]), {}))
            self._with_rel(r, rels.get(str(r["qq"])))
            self._with_bg(r, bgs)
            self._with_av(r, avs)
        rows.sort(key=lambda r: (-(r.get("familiarity") or 0), -(r.get("favor") or 0)))
        return self._ok(rows)

    async def graph(self, request):
        days = max(1, min(90, int(request.query.get("days", 30))))
        group = request.query.get("group", "all")
        if group not in ("all", "dm") and not group.isdigit():
            return self._err("群号不对")
        names = await self._group_names()
        return self._ok(await asyncio.to_thread(self._graph, days, group, names, self._rel_map()))

    def _saved_group_names(self) -> dict:
        """上次從 NapCat 拿到的群名（存在檔案裡）；沒有就用 AstrBot 自己記的會話名。QQ 掉線時也有名字可用"""
        names = {}
        try:
            con = _ro(DATA / "data_v4.db")
            for umo, name in con.execute("select umo, auto_name from umo_aliases"):
                if ":GroupMessage:" in str(umo) and name:
                    names[str(umo).rsplit(":", 1)[-1]] = name
            con.close()
        except Exception:
            pass
        try:
            names.update(json.loads(self.gn_file.read_text("utf-8")))
        except Exception:
            pass
        return names

    async def _group_names(self) -> dict:
        """群名從 napcat 拿，十分鐘快取一次；拿不到用上次記住的，一分鐘內不再重問（不然每次都要等 5 秒逾時）"""
        cache = getattr(self, "_gn_cache", None)
        if cache and time.time() - cache[0] < (600 if cache[2] else 60):
            return cache[1]
        names = dict(GROUP_NAMES)
        try:
            for g in await asyncio.wait_for(self._client().get_group_list(), timeout=5):
                names[str(g.get("group_id"))] = g.get("group_name") or names.get(str(g.get("group_id")), "")
        except Exception:
            self._gn_cache = (time.time(), names, False)
            return names
        self._gn_cache = (time.time(), names, True)
        GROUP_NAMES.update({k: v for k, v in names.items() if v})
        try:
            self.gn_file.write_text(json.dumps(GROUP_NAMES, ensure_ascii=False), "utf-8")
        except Exception:
            pass
        return names

    def _graph(self, days: int, group: str = "all", gnames: dict | None = None, rels: dict | None = None) -> dict:
        """group = all（全部）/ 群號（只看這個群裡說過話的人和他們之間的聯繫）/ dm（私聊過的人）"""
        people = {str(r["qq"]): self._with_rel(r, (rels or {}).get(str(r["qq"]))) for r in self._bond_rows()}
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
        out = await asyncio.to_thread(self._person, qq, self._rel_one(qq))
        self._with_bg(out["profile"], await asyncio.to_thread(self._card_bgs))
        self._with_av(out["profile"], await asyncio.to_thread(self._made_avs))
        return self._ok(out)

    def _person(self, qq: str, rel: dict | None = None) -> dict:
        con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
        try:
            row = con.execute("select * from people where qq=?", (qq,)).fetchone()
            p = dict(row) if row else {"qq": qq}
            events = [dict(r) for r in con.execute("select ts, kind, delta, after, note, source from events where qq=? order by ts", (qq,))]
            heart = self._heart_person(con, qq, {r["qq"]: r["name"] for r in con.execute("select qq, name from people")})
            try:
                cards = [(r["gid"], r["card"]) for r in con.execute("select gid, card from group_cards where qq=? order by ts desc", (qq,))]
            except sqlite3.Error:
                cards = []  # 舊 bond.db 還沒有這張表
        finally:
            con.close()
        # 名字是 QQ 暱稱（10-27 起）；TA 在各群的群名片另外列，和暱稱一樣的不列
        if cards:
            gn = self._saved_group_names()
            p["group_cards"] = [{"gid": g, "group": gn.get(g) or f"群{g}", "card": c} for g, c in cards if c and c != p.get("name")]
        p.update(self._describe(p))
        self._with_rel(p, rel)
        out = {"profile": p, "events": events, "heart": heart}
        # 記憶
        mems = []
        try:
            m = _ro(PD / "astrbot_plugin_livingmemory" / "livingmemory.db")
            ids = [r[0] for r in m.execute(
                "select distinct e.source_memory_id from graph_edges e join graph_nodes n on n.id in (e.source_node_id, e.target_node_id) "
                "where n.node_type='person' and n.canonical_value=?", (f"account:aiocqhttp:{qq}",))]
            if ids:
                # 全拿：壓過的分層記憶不能被當天一大堆零碎記憶擠掉，前端再按分層摺疊
                marks = ",".join("?" * len(ids))
                for r in m.execute(f"select id, text, metadata, created_at from documents where id in ({marks}) order by id desc", ids):
                    meta = {}
                    try:
                        meta = json.loads(r["metadata"] or "{}")
                    except Exception:
                        pass
                    # 改名 lively 前 memtier 寫的是 xfy_*
                    tier = meta.get("lively_tier") or meta.get("xfy_tier") or ""
                    label = meta.get("lively_label") or meta.get("xfy_label") or ""
                    mems.append({"text": r["text"], "ts": meta.get("create_time") or 0, "tier": tier, "label": label,
                                 "where": ({"day": "日记忆", "week": "周记忆", "month": "月记忆", "quarter": "季记忆"}.get(tier, "")
                                           + (f"（{label}）・" if tier else "")
                                           + self._where(meta.get("session_id", ""))), "importance": meta.get("importance")})
            m.close()
        except Exception as e:
            logger.warning(f"[lively_panel] 读记忆失败: {e}")
        out["memories"] = mems
        mind = self._star("lively_mind")
        st = getattr(mind, "stickers", None)
        if st and hasattr(st, "prefs_of"):  # TA 喜不喜歡〈我〉的哪幾張表情包（〈我〉聊天時自己記的）
            try:
                out["meme_prefs"] = sorted(({"file": k, **v} for k, v in st.prefs_of(qq).items() if isinstance(v, dict)),
                                           key=lambda x: -(x.get("ts") or 0))
            except Exception as e:
                logger.warning(f"[lively_panel] 读表情包偏好失败: {e}")
        b = self._star("lively_billing")
        if b and hasattr(b, "feeds"):
            out["feeds"] = [{**f, "from": self.s.fill(b.feed_from(f))} if hasattr(b, "feed_from") else f
                            for f in b.feeds() if f.get("qq") == qq]
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
            m_ = self._star("lively_mind")
            out["proactive"] = {"enabled": p.state.get("enabled"), "mode": p.state.get("mode"),
                                "blocked": p.state.get("blocked", []),
                                "by_heartbeat": bool(m_ and hasattr(m_, "reach_in_heartbeat") and m_.reach_in_heartbeat())}
        if (q := self._star("lively_qzone")):
            out["qzone"] = {"enabled": q.state.get("enabled"), "mode": q.state.get("mode")}
        if (c := self._star("lively_comic")):
            on = set(c._groups())
            out["comic"] = {"enabled": c.state.get("enabled"), "at": c.comic_at,
                            "groups": [{"gid": g, "name": GROUP_NAMES.get(g, f"群{g}"), "on": g in on} for g in c._served()]}
            if hasattr(c, "draw_brief"):
                try:
                    out["draw"] = c.draw_brief()
                except Exception as e:
                    logger.warning(f"[lively_panel] 读不到画图设置: {e}")
        if (v := self._star("lively_voice")):
            # 11-03 起只有 BreezeBlue 雲端；舊的 MiniMax 音色選單拿掉了
            out["voice"] = {"enabled": v.state.get("enabled"), "voice_id": str(v.s.get("breeze_voice_cute", "") or ""),
                            "configured": bool(v.s.get("breeze_key", "")), "ready": "" if not hasattr(v, "_ready") else v._ready()}
        if (b := self._star("lively_bond")):
            try:
                out["bond"] = {"mode": b.store.get_meta("mode")}
            except Exception:
                pass
        if (s := self._star("lively_social")):
            out["social"] = {"blacklist": s.state.get("blacklist", [])}
        if (m := self._star("lively_mind")):
            out["mind"] = self._mind_brief(m)
        # 以前只能私信打指令改的：查图、日报、例行
        if (sr := self._star("lively_search")):
            out["search"] = {"enabled": sr.state.get("enabled", True), "today": sr._today(),
                             "daily_max": int(sr._num("daily_max", 40)), "min_score": int(sr._num("min_score", 70))}
        if (rp := self._star("lively_report")) and hasattr(rp, "brief"):
            out["report"] = rp.brief()
        if (ev := self._star("lively_evolve")):
            out["routines"] = [{"id": r.get("id"), "name": r.get("name"), "at": r.get("at"),
                                "desc": self.s.fill(ev._desc(r)) if hasattr(ev, "_desc") else r.get("name"),
                                "enabled": bool(r.get("enabled")), "today": bool(r.get("today")), "runs": r.get("runs", 0)}
                               for r in ev.state.get("routines", [])]
        try:
            out["brain"] = self._brain_brief()
        except Exception as e:
            logger.warning(f"[lively_panel] 读不到降智版状态: {e}")
        try:
            out["bg"] = self._bg_brief()
        except Exception as e:
            logger.warning(f"[lively_panel] 读不到后台开关: {e}")
        return self._ok(out)

    # ---------- 降智版：群聊用便宜的模型，面板可切、可錄入、可按群開 ----------
    WB_SOURCE_ID = "workbuddy"
    WB_PROVIDER = "workbuddy-flash"
    WB_PROVIDERS = ("workbuddy-flash", "workbuddy-glm", "workbuddy-kimi")
    WB_DEFAULT_BASE = "http://172.18.0.1:7863/v1"
    WB_DEFAULT_MODEL = "global:deepseek-v4.1-flash"

    def _brain_path(self) -> Path:
        return PD / "astrbot_plugin_lively_panel" / "brain.json"

    def _brain_state(self) -> dict:
        try:
            return json.loads(self._brain_path().read_text("utf-8"))
        except Exception:
            return {}

    def _brain_save_state(self, st: dict):
        try:
            self._brain_path().parent.mkdir(parents=True, exist_ok=True)
            self._brain_path().write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")
        except Exception as e:
            logger.warning(f"[lively_panel] 存降智版狀態失敗: {e}")

    @staticmethod
    def _brain_map(lines) -> dict:
        out = {}
        for line in lines or []:
            gid, _, pid = str(line).replace("：", ":").replace(":", "=").partition("=")
            if gid.strip().isdigit() and pid.strip():
                out[gid.strip()] = pid.strip()
        return out

    def _brain_provider_conf(self, pid: str) -> dict:
        pm = getattr(self.context, "provider_manager", None)
        if pm is None:
            return {}
        try:
            return pm.get_provider_config_by_id(pid, merged=True) or {}
        except Exception:
            return {}

    @staticmethod
    def _brain_mask(k) -> str:
        k = k[0] if isinstance(k, list) and k else (k if isinstance(k, str) else "")
        if not isinstance(k, str) or not k:
            return "沒設"
        return (k[:6] + "…" + k[-4:]) if len(k) > 12 else "已設"

    def _brain_brief(self) -> dict:
        g = self._star("lively_gate")
        cfg = getattr(g, "cfg", None) or {}
        gmap = self._brain_map(cfg.get("group_providers"))
        default_id = str(cfg.get("group_provider_id") or "")
        try:
            served = list(g.s.groups()) if g and hasattr(g.s, "groups") else []
        except Exception:
            served = []
        pc = self._brain_provider_conf(self.WB_PROVIDER)
        st = self._brain_state()
        groups = []
        for gid in served:
            pid = gmap.get(gid) or default_id
            groups.append({"gid": gid, "name": GROUP_NAMES.get(gid, f"群{gid}"),
                           "full": pid not in self.WB_PROVIDERS, "pid": pid,
                           "explicit": gid in gmap})
        return {
            "default_full": default_id not in self.WB_PROVIDERS,
            "default_id": default_id,
            "full_id": str(st.get("full_id") or ""),
            "base": str(pc.get("api_base") or self.WB_DEFAULT_BASE),
            "model": str(pc.get("model") or self.WB_DEFAULT_MODEL),
            "key_hint": self._brain_mask(pc.get("key")),
            "loaded": self.context.get_provider_by_id(self.WB_PROVIDER) is not None,
            "providers": [{"id": p, "loaded": self.context.get_provider_by_id(p) is not None}
                          for p in self.WB_PROVIDERS],
            "groups": groups,
        }

    def _brain_commit_gate(self, g) -> str:
        """寫回 gate 的配置：先讓它自己存（AstrBotConfig.save_config），失敗就手寫文件"""
        try:
            if hasattr(g.cfg, "save_config"):
                g.cfg.save_config()
                return ""
        except Exception as e:
            logger.warning(f"[lively_panel] 存 gate 配置失敗: {e}")
        try:
            path = Path(DATA) / "config" / "astrbot_plugin_lively_gate_config.json"
            cur = json.loads(path.read_text("utf-8-sig")) if path.exists() else {}
            cur["group_providers"] = list(g.cfg.get("group_providers") or [])
            cur["group_provider_id"] = str(g.cfg.get("group_provider_id") or "")
            path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), "utf-8")
            return ""
        except Exception as e:
            return f"存檔失敗: {e}"

    async def _brain_toggle(self, key: str, value) -> web.Response:
        g = self._star("lively_gate")
        if not g or not hasattr(g, "cfg"):
            return self._err("gate 插件沒加載", 503)
        cfg, st = g.cfg, self._brain_state()
        if key == "default":
            if not isinstance(value, bool):
                return self._err("值不對")
            cur = str(cfg.get("group_provider_id") or "")
            if cur and cur not in self.WB_PROVIDERS:
                st["full_id"] = cur
                self._brain_save_state(st)
            if value:  # 開 = 群聊默認用滿血版
                back = str(st.get("full_id") or "")
                if not back:
                    return self._err("還不知道滿血版是哪個模型")
                cfg["group_provider_id"] = back
            else:      # 關 = 回降智版
                cfg["group_provider_id"] = self.WB_PROVIDER
            bad = self._brain_commit_gate(g)
            if bad:
                return self._err(bad)
            return self._ok(msg="群聊默認：" + ("滿血版" if value else "降智版"))
        if key.startswith("group:"):
            gid = key[6:]
            if not gid.isdigit() or not isinstance(value, bool):
                return self._err("值不對")
            gmap = self._brain_map(cfg.get("group_providers"))
            if value:  # 開 = 這個群用滿血版（優先復用它原來那把分帳密鑰）
                back = str((st.get("full_map") or {}).get(gid) or st.get("full_id") or "")
                if not back:
                    return self._err("還不知道滿血版是哪個模型")
                gmap[gid] = back
            else:      # 關 = 這個群回降智版（顯式寫，免得默認是滿血時關不掉）
                gmap[gid] = self.WB_PROVIDER
            cfg["group_providers"] = [f"{k}={v}" for k, v in gmap.items()]
            bad = self._brain_commit_gate(g)
            if bad:
                return self._err(bad)
            return self._ok(msg=f"{GROUP_NAMES.get(gid, '群' + gid)}：" + ("滿血版" if value else "降智版"))
        return self._err("不認得這個開關")

    # ---------- 後台開關：看圖、心跳走降智版（出錯自動換回原來的模型） ----------
    BG_CAPTION_PID = "workbuddy-caption"
    BG_MIND_PID = "workbuddy-mind"
    BG_FULL_CAPTION_PID = "deepseek-flash-caption"
    BG_FULL_MIND_PID = "deepseek-flash-mind"

    def _bg_brief(self) -> dict:
        g = self._star("lively_gate")
        cap_pid = str((getattr(g, "cfg", None) or {}).get("caption_provider") or "")
        m = self._star("lively_mind")
        mind_pid = ""
        if m and getattr(m, "s", None):
            try:
                mind_pid = str(m.s.get("provider_id", "") or "")
            except Exception:
                mind_pid = ""
        return {
            "caption": cap_pid == self.BG_CAPTION_PID,
            "caption_pid": cap_pid or self.BG_FULL_CAPTION_PID,
            "mind": mind_pid == self.BG_MIND_PID,
            "mind_pid": mind_pid or self.BG_FULL_MIND_PID,
            "caption_loaded": self.context.get_provider_by_id(self.BG_CAPTION_PID) is not None,
            "mind_loaded": self.context.get_provider_by_id(self.BG_MIND_PID) is not None,
        }

    def _commit_plugin_cfg(self, cfg, fname: str, kv: dict) -> str:
        """寫回某個插件的配置：先讓它自己存，存完核對；不對就手寫文件"""
        try:
            if hasattr(cfg, "save_config"):
                cfg.save_config()
                path = Path(DATA) / "config" / fname
                if path.exists():
                    cur = json.loads(path.read_text("utf-8-sig"))
                    if all(cur.get(k) == v for k, v in kv.items()):
                        return ""
        except Exception as e:
            logger.warning(f"[lively_panel] 存 {fname} 失敗: {e}")
        try:
            path = Path(DATA) / "config" / fname
            cur = json.loads(path.read_text("utf-8-sig")) if path.exists() else {}
            cur.update(kv)
            path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), "utf-8")
            return ""
        except Exception as e:
            return f"存檔失敗: {e}"

    async def _bg_toggle(self, key: str, value: bool) -> web.Response:
        if key == "caption":
            g = self._star("lively_gate")
            if not g or not hasattr(g, "cfg"):
                return self._err("gate 插件沒加載", 503)
            if value and self.context.get_provider_by_id(self.BG_CAPTION_PID) is None:
                return self._err("降智版看圖模型沒加載（workbuddy-caption）", 503)
            g.cfg["caption_provider"] = self.BG_CAPTION_PID if value else ""
            bad = self._commit_plugin_cfg(g.cfg, "astrbot_plugin_lively_gate_config.json",
                                          {"caption_provider": g.cfg["caption_provider"]})
            if bad:
                return self._err(bad)
            return self._ok(msg="看圖：" + ("降智版（出錯換回原來的）" if value else "原來的模型"))
        m = self._star("lively_mind")
        if not m or not getattr(m, "s", None):
            return self._err("mind 插件沒加載", 503)
        if value and self.context.get_provider_by_id(self.BG_MIND_PID) is None:
            return self._err("降智版心跳模型沒加載（workbuddy-mind）", 503)
        m.s.cfg["provider_id"] = self.BG_MIND_PID if value else self.BG_FULL_MIND_PID
        m.s.cfg["fallback_provider_id"] = self.BG_FULL_MIND_PID if value else ""
        bad = self._commit_plugin_cfg(m.s.cfg, "astrbot_plugin_lively_mind_config.json",
                                      {"provider_id": m.s.cfg["provider_id"],
                                       "fallback_provider_id": m.s.cfg["fallback_provider_id"]})
        if bad:
            return self._err(bad)
        return self._ok(msg="心跳：" + ("降智版（出錯換回原來的）" if value else "原來的模型"))

    async def brain_set(self, request):
        """降智版的 API 錄入與連通測試（POST /api/brain）"""
        body = request["body"]
        action = str(body.get("action") or "api")
        base = (str(body.get("base") or "").strip().rstrip("/")) or self.WB_DEFAULT_BASE
        if not base.startswith("http"):
            return self._err("地址要 http(s) 開頭")
        model = str(body.get("model") or "").strip() or self.WB_DEFAULT_MODEL
        key = str(body.get("key") or "").strip()
        if action == "probe":
            pc = self._brain_provider_conf(self.WB_PROVIDER)
            k = pc.get("key")
            k = k[0] if isinstance(k, list) and k else (k if isinstance(k, str) else "")
            b = str(pc.get("api_base") or base)
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as sess:
                    async with sess.get(f"{b.rstrip('/')}/models",
                                        headers={"Authorization": f"Bearer {k}"}) as r:
                        txt = await r.text()
                        if r.status != 200:
                            return self._err(f"不通：HTTP {r.status} {txt[:120]}")
                        try:
                            n = len(json.loads(txt).get("data") or [])
                        except Exception:
                            n = 0
                        return self._ok(msg=f"通了，看到 {n} 個模型")
            except Exception as e:
                return self._err(f"連不上：{e}")
        ac = None
        try:
            from astrbot.core import astrbot_config as ac  # type: ignore
        except Exception:
            try:
                ac = self.context.get_config()
            except Exception:
                ac = None
        if ac is None:
            return self._err("拿不到 AstrBot 配置，只有直接跑 AstrBot 時能錄入")
        srcs = ac.setdefault("provider_sources", [])
        src = next((s for s in srcs if s.get("id") == self.WB_SOURCE_ID), None)
        if src is None:
            src = {"id": self.WB_SOURCE_ID, "provider": "workbuddy",
                   "type": "openai_chat_completion", "provider_type": "chat_completion",
                   "enable": True, "key": [], "api_base": base, "timeout": 120,
                   "proxy": "", "custom_headers": {}}
            srcs.append(src)
        src["api_base"] = base
        src["enable"] = True
        if key:
            src["key"] = [key]
        provs = ac.setdefault("provider", [])
        for pid in self.WB_PROVIDERS:
            pv = next((x for x in provs if x.get("id") == pid), None)
            if pv is None:
                pv = {"id": pid, "provider_source_id": self.WB_SOURCE_ID, "model": model,
                      "modalities": ["text", "image", "tool_use"], "custom_extra_body": {},
                      "enable": True, "provider_type": "chat_completion", "max_context_tokens": 24000}
                provs.append(pv)
            if pid == self.WB_PROVIDER:
                pv["model"] = model
        try:
            ac.save_config()
        except Exception as e:
            logger.warning(f"[lively_panel] 存 AstrBot 配置失敗: {e}")
        hot = []
        pm = getattr(self.context, "provider_manager", None)
        if pm is not None:
            for pid in self.WB_PROVIDERS:
                pv = next((x for x in provs if x.get("id") == pid), None)
                if not pv:
                    continue
                try:
                    await pm.reload(dict(pv))
                    hot.append(pid)
                except Exception as e:
                    logger.warning(f"[lively_panel] 熱加載 {pid} 失敗: {e}")
        st = self._brain_state()
        st["base"], st["model"] = base, model
        self._brain_save_state(st)
        return self._ok(msg="存好了" + ("" if hot else "（重啟 AstrBot 後生效）"), hot=hot)

    async def set_setting(self, request):
        body = request["body"]
        plugin, key, value = body.get("plugin"), body.get("key"), body.get("value")
        allowed = {
            ("proactive", "enabled"): bool, ("proactive", "mode"): ("auto", "preview"),
            ("qzone", "enabled"): bool, ("qzone", "mode"): ("review", "auto"),
            ("comic", "enabled"): bool,
            ("voice", "enabled"): bool,
            ("proactive", "block"): str, ("proactive", "unblock"): str,
        }
        if plugin == "brain" and isinstance(key, str):
            return await self._brain_toggle(key, value)
        if plugin == "bg" and isinstance(key, str) and key in ("caption", "mind"):
            if not isinstance(value, bool):
                return self._err("值不对")
            return await self._bg_toggle(key, value)
        if plugin == "mind" and isinstance(key, str) and (key == "enabled" or key.startswith("mode:")):
            m = self._star("lively_mind")
            if not m:
                return self._err("插件没加载", 503)
            if key == "enabled":
                if not isinstance(value, bool):
                    return self._err("值不对")
                m.state["enabled"] = value
                m._save()
                return self._ok()
            ok, msg = m.hands.set_mode(key[5:], str(value))
            return self._ok(msg=self.s.fill(msg)) if ok else self._err(self.s.fill(msg))
        if plugin == "search" and key == "enabled":
            sr = self._star("lively_search")
            if not sr:
                return self._err("插件没加载", 503)
            if not isinstance(value, bool):
                return self._err("值不对")
            sr.state["enabled"] = value
            sr._save()
            return self._ok(msg="查图" + ("开了，她想查的时候可以用工具" if value else "关了，她这边的查图工具拿掉了"))
        if plugin == "report" and key == "enabled":
            rp = self._star("lively_report")
            if not rp or not hasattr(rp, "set_enabled"):
                return self._err("插件没加载", 503)
            if not isinstance(value, bool):
                return self._err("值不对")
            rp.set_enabled(value)
            return self._ok(msg="每晚日报" + ("开了" if value else "关了，私信问「日报」照样能看"))
        if plugin == "evolve" and isinstance(key, str) and key.split(":")[0] in ("routine", "today"):
            ev = self._star("lively_evolve")
            if not ev:
                return self._err("插件没加载", 503)
            what, _, rid = key.partition(":")
            r = next((x for x in ev.state.get("routines", []) if str(x.get("id")) == rid), None)
            if not r or not isinstance(value, bool):
                return self._err("值不对")
            op = ("开" if value else "停") if what == "routine" else ("看今天" if value else "不看今天")
            r["enabled" if what == "routine" else "today"] = value
            ev._save()
            ev._log("routine", text=f"〈主人〉{op}了例行 #{r['id']} {r['name']}（面板）")
            return self._ok(msg=f"#{r['id']} {r['name']} " + {"开": "开了", "停": "停了", "看今天": "以后先看今天的聊天再说",
                                                               "不看今天": "以后不看今天的聊天了"}[op])
        if plugin == "comic" and key in ("draw_chat", "draw_min_score", "draw_daily_max"):
            c = self._star("lively_comic")
            if not c or not hasattr(c, "set_draw"):
                return self._err("插件没加载", 503)
            ok, msg = c.set_draw(key, value)
            return self._ok(msg=self.s.fill(msg)) if ok else self._err(self.s.fill(msg))
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

    # ---------- 自主（lively_mind）：開關、每個動作的模式、最近幾跳 ----------
    def _mind_brief(self, m) -> dict:
        mod = sys.modules.get(type(m).__module__.rsplit(".", 1)[0] + ".hands")
        actions = getattr(mod, "ACTIONS", {}) if mod else {}
        counts = m.hands.today_counts()
        rv = m.review_stats() if hasattr(m, "review_stats") else {}
        return {"enabled": m.state.get("enabled", True), "sleeping": m.sleeping(), "beats_today": m.heart.beats_today(),
                "next_beat": m.state.get("next_beat", 0),
                "actions": [{"id": a, "label": self.s.fill(spec["label"]), "mode": m.hands.mode(a), "ready": spec["ready"],
                             "today": counts.get(a, 0), "day": spec.get("day"), "rv": rv.get(a, [0, 0])}
                            for a, spec in actions.items()]}

    async def mind(self, request):
        m = self._star("lively_mind")
        if not m:
            return self._err("插件没加载", 503)
        if request.query.get("only") == "thoughts":  # 此刻只要最近幾次想的事，不用整包（150KB）
            bs = [b for b in m._tail("beats.jsonl", 120) if b.get("thought")][-8:]
            return self._ok(self._fill_deep({"sleeping": m.sleeping(), "thoughts": [{"ts": b["ts"], "text": b["thought"]} for b in bs[::-1]]}))
        beats = [b for b in m._tail("beats.jsonl", 200) if b.get("result") not in ("没有新动静", "QQ 掉线了，没看成", "QQ 掉线了，没看手机")][-20:]
        if hasattr(m, "settle"):  # 排队中的換成做完的結果
            m.settle(beats)
        reviews = m.reviews() if hasattr(m, "reviews") else {}
        for b in beats:
            for i, a in enumerate(b.get("actions") or []):
                if (r := reviews.get(f"{b.get('beat')}#{i}")):
                    a["rv"] = {"ok": r.get("ok"), "note": r.get("note", "")}
        cut = time.time() - KEEP_SECS
        acts = [e for e in m._tail("events.jsonl", 3000) if e.get("kind") == "act" and (e.get("ts") or 0) >= cut][-300:]
        # 發完再看一眼：只列撤了的和模型覺得有問題的（模型那層只記錄）
        checks = [c for c in m._tail("recheck.jsonl", 3000) if (c.get("ts") or 0) >= cut]
        flagged = [c for c in checks if c.get("rules") or (c.get("model") or {}).get("ok") is False][-40:]
        out = {**self._mind_brief(m), "thought": m.state.get("thought"), "beats": beats[::-1], "acts": acts[::-1],
               "notes": m.state.get("notes", []), "quiet": m.quiet_people() if hasattr(m, "quiet_people") else m.state.get("quiet", {}),
               "quiet_groups": m.state.get("quiet_groups", {}),
               "rechecks": flagged[::-1], "rechecked": len(checks),
               "outages": m.outages_recent(14) if hasattr(m, "outages_recent") else []}
        return self._ok(self._fill_deep(out))

    async def mind_beat(self, request):
        m = self._star("lively_mind")
        if not m:
            return self._err("插件没加载", 503)
        b = await m.heart.beat(manual=True)
        if not b.get("ts"):
            return self._err(b.get("result") or "没跳成")
        return self._ok(beat=self._fill_deep(b))

    async def mind_review(self, request):
        """點評她某一跳想做的某件事：ok 是 true/false，null 撤掉"""
        m = self._star("lively_mind")
        if not m or not hasattr(m, "review"):
            return self._err("插件没加载", 503)
        body = request["body"]
        ok, i = body.get("ok"), body.get("i")
        if not isinstance(body.get("beat"), str) or not isinstance(i, int) or ok not in (True, False, None):
            return self._err("值不对")
        try:
            r = m.review(body["beat"], i, ok, str(body.get("note") or ""))
        except ValueError as e:
            return self._err(str(e))
        return self._ok(review=r, rv=m.review_stats())

    async def mind_try(self, request):
        """實測一個動作：不看模式、不等，當場做一次（關卡照跑）"""
        m = self._star("lively_mind")
        if not m or not hasattr(m, "try_act"):
            return self._err("插件没加载", 503)
        try:
            rec = await m.try_act(request["body"])
        except Exception as e:  # NapCat、空間報錯：告訴頁面，不回 500
            logger.warning(f"[lively_panel] 实测动作失败: {e}")
            return self._err(f"没做成：{str(e)[:100]}")
        return self._ok(rec=self._fill_deep(json.loads(json.dumps(rec, ensure_ascii=False, default=str))))

    # ---------- 待審核 ----------
    @staticmethod
    def _events(plugin: str, kinds: set, n: int = 300) -> list:
        """某個插件 events.jsonl 裡最近 KEEP_DAYS 天的幾種事件，新的在前（n 只是防止一次給太多）"""
        return [e for e in reversed(_recent(PD / plugin / "events.jsonl")) if e.get("kind") in kinds][:n]

    def _people_names(self) -> dict:
        try:
            con = _ro(PD / "astrbot_plugin_lively_bond" / "bond.db")
            try:
                return {str(r["qq"]): r["name"] for r in con.execute("select qq, name from people") if r["name"]}
            finally:
                con.close()
        except Exception:
            return {}

    async def pending(self, request):
        out = {}
        if (s := self._star("lively_social")):
            try:
                s._prune()
            except Exception:
                pass
            out["requests"] = [{"key": k, **{x: v.get(x) for x in ("type", "id", "name", "ts", "comment", "groups", "inviter", "inviter_name", "her")}}
                               for k, v in s.state.get("pending", {}).items()]
        # 加好友、拉進群、進群退群的記錄（處理過的也留著看）；號碼換成名字
        who = self._people_names()
        out["request_log"] = self._fill_deep([{**{k: e.get(k) for k in ("ts", "kind", "qq", "id", "name", "result", "talks", "action", "done", "via", "inviter", "operator", "late")},
                               "group": e.get("group"), "group_name": GROUP_NAMES.get(str(e.get("group") or e.get("id") or ""), ""),
                               "inviter_name": who.get(str(e.get("inviter") or ""), ""), "operator_name": who.get(str(e.get("operator") or ""), "")}
                              for e in self._events("astrbot_plugin_lively_social",
                                                    {"friend_request", "friend_decided", "group_invite", "group_decided", "joined", "kicked"})])
        if (ev := self._star("lively_evolve")):
            # 等主人回的，和最近定了的（同意、不要、學會了）連同主人定的做法
            ps = ev.state.get("proposals", [])
            keys = ("n", "title", "status", "ts", "who", "idea", "risk", "effort", "note")
            out["proposals"] = self._fill_deep([{k: p.get(k) for k in keys} for p in ps if p.get("status") == "pending"])
            out["proposals_done"] = self._fill_deep([{k: p.get(k) for k in keys}
                                                     for p in ps if p.get("status") in ("ok", "no", "done")][-6:][::-1])
        if (q := self._star("lively_qzone")):
            d = q.state.get("draft")
            # 圖在說說插件的資料目錄，前端只拿檔名，經 /api/image?from=qzone 取
            out["qzone_draft"] = {**d, "image": Path(d["image"]).name} if d and d.get("image") else d
            out["qzone_posted"] = q.state.get("posted", [])[-5:]
        # 說說記錄：寫過、發過、改過、沒發、刪掉的；events 開始記之前發的從 state 補上
        # image 是圖檔名；以前只記了 true（有圖但沒記檔名）
        ql = [{k: e.get(k) for k in ("ts", "kind", "tid", "text", "before", "after", "via", "image", "image_prompt")}
              for e in self._events("astrbot_plugin_lively_qzone", {"posted", "rejected", "edited", "deleted", "draft"})]
        # 配圖的畫面描述記在草稿那條，帶到發出去／沒發的那條上
        prompts = {e["image"]: e.get("image_prompt") for e in ql if e["kind"] == "draft" and isinstance(e.get("image"), str)}
        ql = [{**e, "image_prompt": e.get("image_prompt") or prompts.get(e.get("image"))} for e in ql if e["kind"] != "draft"]
        seen = {e["tid"] for e in ql if e.get("tid")}
        ql += [{"ts": x.get("ts"), "kind": "posted", "tid": x.get("tid"), "text": x.get("text"), "image": x.get("image") or x.get("has_image")}
               for x in (q.state.get("posted", []) if q else [])
               if x.get("tid") not in seen and (x.get("ts") or 0) >= time.time() - KEEP_SECS]
        out["qzone_log"] = sorted(ql, key=lambda e: -(e.get("ts") or 0))[:300]
        out["keep_days"] = KEEP_DAYS
        return self._ok(out)

    async def act_pending(self, request):
        b = request["body"]
        what, action = b.get("what"), b.get("action")
        if what == "request":
            s = self._star("lively_social")
            req = s.state.get("pending", {}).get(b.get("key")) if s else None
            if not req or action not in ("同意", "拒绝", "拉黑"):
                return self._err("申请不存在或已处理")
            # 社交插件自己處理（記錄、黑名單、加了好友讓〈我〉知道）；以前這裡叫的 _greet 10-26 拿掉了，同意好友會 500
            done, fact = await s.decide(b["key"], action, self._client(), via="panel")
            return self._ok(done=done) if done else self._err(self.s.fill(fact))
        if what == "qzone":
            q = self._star("lively_qzone")
            draft = q.state.get("draft") if q else None
            if action == "write":
                # image 沒給就讓她自己決定配不配圖
                msg = await q.new_draft(str(b.get("topic") or "")[:50], image=None if b.get("image") is None else bool(b.get("image")), review=bool(b.get("review")))
                return self._ok(msg=msg)
            if not draft:
                return self._err("没有草稿")
            if action in ("publish", "edit"):
                text = draft["text"] if action == "publish" else str(b.get("text") or "").strip()
                if not text:
                    return self._err("内容是空的")
                tid = await q.publish(text, draft.get("image"))
                q.state["draft"] = None
                q._save()
                if hasattr(q, "settled"):  # 她自己送的：結果記進她發起的那個聊天
                    q.settled(draft, "posted" if action == "publish" else "edited", text)
                return self._ok(tid=tid)
            if action == "discard":
                q.state["draft"] = None
                q._log("rejected", text=draft["text"], via="panel", image=Path(draft["image"]).name if draft.get("image") else None)
                q._save()
                if hasattr(q, "settled"):
                    q.settled(draft, "rejected")
                return self._ok()
            if action == "rewrite":
                q.state["draft"] = None
                q._save()
                if draft.get("via") in ("chat", "heartbeat") and hasattr(q, "settled"):
                    # 她自己送的：重不重寫、寫什麼還是她定，這裡只告訴她
                    q._log("rejected", text=draft["text"], via="panel", rewrite=True,
                           image=Path(draft["image"]).name if draft.get("image") else None)
                    q.settled(draft, "rewrite")
                    return self._ok(msg=self.s.fill("跟〈我〉说了要重写"))
                msg = await q.new_draft(draft.get("topic") or "", draft.get("want_image"))
                return self._ok(msg=msg)
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
        if request["body"].get("test"):  # 試畫：只畫一個群、存成 comic_test_*，不發給誰（看日誌「试画好了」）
            gid = str(request["body"].get("group") or groups[0])

            async def run():
                try:
                    logger.info(f"[lively_panel] 群漫画试画：{await c.draw(gid, offset, test=True)}")
                except Exception as e:
                    logger.error(f"[lively_panel] 群漫画试画失败: {e}", exc_info=True)
            if "test" not in c.draw.__code__.co_varnames:
                return self._err("漫画插件还不支持试画")
            asyncio.create_task(run())
            return self._ok(msg="开始试画了，几分钟后看日志")
        return self._err("群漫画只有每天定时那张（10-26 拿掉了手动补画）；要看效果用试画（test）")

    # ---------- 自我成長：相處經驗、例行、提案 ----------
    async def evolve(self, request):
        ev = self._star("lively_evolve")
        if not ev:
            return self._err("自我成长插件没加载", 503)
        st = ev.state
        basis = ev._basis()[1] if hasattr(ev, "_basis") else None
        evs = [e for e in reversed(_recent(PD / "astrbot_plugin_lively_evolve" / "events.jsonl"))
               if e.get("kind") in ("notes", "notes_align")][:6]
        out = {"enabled": st.get("enabled", True), "notes": st.get("notes", []),
               "aligned": basis is None or st.get("notes_basis") == basis,
               "rules": ev._owner_rules() if hasattr(ev, "_owner_rules") else [],
               "changes": [{k: e.get(k) for k in ("ts", "kind", "text", "dropped")} for e in evs],
               "routines": [{"id": r.get("id"), "desc": ev._desc(r) if hasattr(ev, "_desc") else r.get("name"), "enabled": r.get("enabled"),
                             "runs": r.get("runs", 0)} for r in st.get("routines", [])],
               "proposals": [{k: p.get(k) for k in ("n", "title", "status", "ts", "who", "idea", "risk", "effort", "note")}
                             for p in st.get("proposals", [])][-8:][::-1],
               "wishes": len(ev._week_wishes()) if hasattr(ev, "_week_wishes") else 0,
               "busy": ev._busy.locked()}
        return self._ok(self._fill_deep(out))

    async def evolve_act(self, request):
        """刪一條經驗、按最新的人設重整／重寫經驗、回提案：都走自我成長插件自己的主人指令"""
        ev = self._star("lively_evolve")
        if not ev or not hasattr(ev, "_owner_cmd"):
            return self._err("自我成长插件没加载", 503)
        body = request["body"]
        a = body.get("action")
        if a == "del_note" and isinstance(body.get("i"), int):
            cmd = f"成长 删经验 {body['i'] + 1}"
        elif a in ("align", "rewrite"):
            if ev._busy.locked():
                return self._err(self.s.fill("〈我〉正在整理，等一下再点"))
            cmd = "成长 " + ("重整经验" if a == "align" else "重写经验")

            async def run():
                try:
                    r = await ev._owner_cmd(cmd)
                    logger.info(self.s.fill(f"[lively_panel] 面板让〈我〉{cmd[3:]}：{str(r or '')[:200]}"))
                except Exception as e:
                    logger.error(f"[lively_panel] {cmd[3:]}失败: {e}")
            asyncio.create_task(run())
            return self._ok(msg=self.s.fill("〈我〉在按最新的人设和规矩" + ("重整" if a == "align" else "重写") + "经验，一两分钟后刷新"))
        elif a == "proposal" and str(body.get("n", "")).isdigit() and isinstance(body.get("ok"), bool):
            # note：說好時是主人定的做法，說不要時是為什麼；一行、最多 300 字，跟在指令後面（「提案 N 好 怎么做」）
            note = re.sub(r"\s+", " ", str(body.get("note") or "")).strip()[:300]
            p = next((x for x in ev.state.get("proposals", []) if str(x.get("n")) == str(body["n"])), None)
            if not p:
                return self._err("没有这个提案")
            if p.get("status") == "done":
                return self._err(self.s.fill("这个〈我〉已经学会了，不用再定"))
            cmd = f"提案 {body['n']} {'好' if body['ok'] else '不要'}" + (f" {note}" if note else "")
        else:
            return self._err("值不对")
        try:
            r = await ev._owner_cmd(cmd)
        except Exception as e:
            return self._err(f"没办成：{e}")
        if a == "proposal" and self.s.owner():  # 讓〈我〉知道（主人接著在私聊問起時不會一臉茫然）
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在面板{'同意' if body['ok'] else '不要'}了成长提案【{body['n']}】{p.get('title', '')}"
                                    + (f"（{note}）" if note else "")), f"{BACKSTAGE_KIND}:成长")
        if a == "proposal" and note:
            return self._ok(msg=self.s.fill(f"记下了：【{body['n']}】" + ("〈主人〉定的做法" if body["ok"] else "为什么不要")))
        return self._ok(msg=self.s.fill(str(r or "好")).split("\n")[0][:80])

    async def pclog(self, request):
        """她電腦的工作記錄（10-29）：從橋讀，按一輪一輪排好，新的在前"""
        pc = self._star("lively_pc")
        if not pc or not hasattr(pc, "worklog_day"):
            return self._err("电脑插件没载入", 503)
        days = await pc.worklog_days()
        if not days.get("ok"):
            return self._err("电脑那边没连上：" + str(days.get("error") or ""), 503)
        ds = days.get("days") or []
        day = request.query.get("day", "")
        if day not in ds:
            day = ds[0] if ds else ""
        if not day:
            return self._ok({"days": [], "day": "", "rounds": [], "total": 0})
        r = await pc.worklog_day(day, 0, 3000)
        if not r.get("ok"):
            return self._err("读不到那一天的记录：" + str(r.get("error") or ""), 503)
        rows = []
        for line in r.get("lines") or []:
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append(None)
        rounds = pc_rounds(rows)
        return self._ok({"days": ds[:30], "day": day, "total": r.get("total", len(rows)), "rounds": rounds[::-1][:200]})

    async def pcshot(self, request):
        f = request.query.get("f", "")
        if not re.fullmatch(r"shots/\d{4}-\d\d-\d\d/[\w.\-]+\.(png|jpg|jpeg|webp)", f):
            return self._err("文件名不对")
        pc = self._star("lively_pc")
        if not pc or not hasattr(pc, "worklog_shot"):
            return self._err("电脑插件没载入", 503)
        r = await pc.worklog_shot(f)
        if not r.get("ok"):
            return self._err(str(r.get("error") or "没有这张"), 404)
        ext = f.rsplit(".", 1)[-1]
        return web.Response(body=base64.b64decode(r["b64"]), content_type="image/" + ("jpeg" if ext == "jpg" else ext),
                            headers={"Cache-Control": "private, max-age=86400"})

    async def image(self, request):
        name = request.query.get("f", "")
        src = {"comic": "astrbot_plugin_lively_comic", "qzone": "astrbot_plugin_lively_qzone"}.get(request.query.get("from", "comic"))
        if not src or not re.fullmatch(r"[\w.\-]+\.(png|jpg|jpeg)", name):
            return self._err("文件名不对")
        path = PD / src / name
        if not path.exists():  # 10-29 起群漫畫在 comics/<群號>/、畫的圖在 drawn/（她電腦上）
            path = next((p for p in [PD / src / "drawn" / name, *(PD / src / "comics").glob(f"*/{name}")] if p.is_file()), path)
        if not path.exists():
            return self._err("没有这个图", 404)
        w = request.query.get("w", "")
        if w.isdigit():  # 列表里用縮圖（原圖 1.5MB，從外面連進來一張要十幾秒）
            w = max(160, min(1200, int(w)))
            thumb = self.dir / "thumbs" / f"{src.rsplit('_', 1)[-1]}-{path.stem}-{w}.jpg"
            if not thumb.exists() or thumb.stat().st_mtime < path.stat().st_mtime:
                try:
                    await asyncio.to_thread(_thumb, path, thumb, w)
                except Exception as e:
                    logger.debug(f"[lively_panel] 缩图失败 {name}: {e}")
                    return web.FileResponse(path)
            return web.FileResponse(thumb, headers={"Content-Type": "image/jpeg", "Cache-Control": "private, max-age=2592000"})
        return web.FileResponse(path)

    async def meme_thumb(self, request):
        """表情包縮圖：f 是「分類/檔名」（在庫裡找，找不到再去隔離區找）或「quarantine_xxx/分類/檔名」；raw=1 給原圖（動圖照樣動）"""
        f = request.query.get("f", "")
        if not re.fullmatch(r"(quarantine[\w\-]*/)?[\w\-]+/[\w.\-]+\.(png|jpe?g|gif|webp)", f, re.I) or ".." in f:
            return self._err("文件名不对")
        root = PD / "meme_manager"
        cands = [root / f] if f.startswith("quarantine") else [root / "memes" / f] + sorted(root.glob(f"quarantine*/{f}"))
        path = next((p for p in cands if p.is_file()), None)
        if not path:
            return self._err("没有这张", 404)
        if request.query.get("raw") == "1":
            return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})
        w = request.query.get("w", "")
        w = max(48, min(320, int(w))) if w.isdigit() else 120
        thumb = self.dir / "thumbs" / f"meme-{hashlib.sha1(f.encode()).hexdigest()[:12]}-{w}.jpg"
        if not thumb.exists() or thumb.stat().st_mtime < path.stat().st_mtime:
            try:
                await asyncio.to_thread(_thumb, path, thumb, w)
            except Exception as e:
                logger.debug(f"[lively_panel] 表情包缩图失败 {f}: {e}")
                return self._err("这张打不开", 404)
        return web.FileResponse(thumb, headers={"Content-Type": "image/jpeg", "Cache-Control": "private, max-age=2592000"})

    async def meme_pref_act(self, request):
        """去掉一條〈我〉記錯的表情包偏好（記在自主插件，面板只是幫著改）"""
        mind = self._star("lively_mind")
        st = getattr(mind, "stickers", None)
        if not st or not hasattr(st, "drop_pref"):
            return self._err("自主插件没加载，或者版本太旧", 503)
        body = request["body"]
        qq, f = str(body.get("qq") or ""), str(body.get("file") or "")
        if body.get("action") != "del" or not qq.isdigit() or not f:
            return self._err("值不对")
        r = await asyncio.to_thread(st.drop_pref, qq, f)
        if not r:
            return self._err("没有这一条")
        return self._ok(msg=f"去掉了：{'不喜欢' if r.get('pref') == 'dislike' else '喜欢'}「{f}」")

    def _stickers(self):
        st = getattr(self._star("lively_mind"), "stickers", None)
        return st if st is not None and hasattr(st, "manage") else None

    async def memes(self, request):
        """表情包那頁：庫裡每張（q=1 是隔離區每張）"""
        st = self._stickers()
        if not st:
            return self._err("自主插件没加载，或者版本太旧", 503)
        try:
            if request.query.get("q") == "1":
                return self._ok(await asyncio.to_thread(st.quarantine))
            names = await self._group_names()
            return self._ok(self._fill_deep(await asyncio.to_thread(st.manage, names)))
        except ValueError as e:
            return self._err(str(e), 503)

    async def memes_act(self, request):
        """換分類、拿下來（放進隔離區，不刪）、從隔離區放回；動完記一筆給〈我〉（主人私聊下一輪看得到）"""
        st = self._stickers()
        if not st:
            return self._err("自主插件没加载，或者版本太旧", 503)
        body = request["body"]
        a, files, to = body.get("action"), body.get("files"), str(body.get("to") or "").strip()
        if a not in ("move", "out", "back") or not isinstance(files, list) or not files:
            return self._err("值不对")
        if len(files) > 60:
            return self._err("一次最多 60 张")
        try:
            r = await asyncio.to_thread(st.manage_act, a, files, to)
        except ValueError as e:
            return self._err(str(e))
        done, skip = r["done"], r["skip"]
        if not done:
            return self._err("没动：" + "；".join(f"{s['src']} {s['why']}" for s in skip[:3]))
        what = {"move": f"换到了「{to}」", "out": "从库里拿下来了（放进隔离区，没删）", "back": "放回了库里"}[a]
        listed = "、".join(f"{d['src'].split('/')[-2]} 的 {Path(d['src']).stem}" + (f"「{d['desc'][:20]}」" if d.get("desc") else "")
                          for d in done[:6]) + (f" 等 {len(done)} 张" if len(done) > 6 else "")
        if self.s.owner():
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在面板把 {len(done)} 张表情包{what}：{listed}；库里现在 {r['total']} 张"),
                        f"{BACKSTAGE_KIND}:表情包")
        msg = f"{len(done)} 张{what}，库里现在 {r['total']} 张" + (f"；{len(skip)} 张没动（{skip[0]['why']}）" if skip else "")
        return self._ok(r, msg=msg)

    def _feed_bg_src(self, tier: int) -> Path | None:
        """bond 帶的投喂檔位背景畫（card_assets/feed/bg<N>）；bond 沒載入就按插件目錄找"""
        dirs = []
        b = self._star("lively_bond")
        fx = sys.modules.get(type(b).__module__.rsplit(".", 1)[0] + ".card_fx") if b else None
        if fx is not None and getattr(fx, "BG_DIR", None):
            dirs.append(Path(fx.BG_DIR))
        dirs.append(Path(__file__).resolve().parent.parent / "astrbot_plugin_lively_bond" / "card_assets" / "feed")
        for d in dirs:
            for ext in ("webp", "png", "jpg"):
                if (f := d / f"bg{tier}.{ext}").exists():
                    return f
        return None

    async def feed_bg(self, request):
        t = request.match_info["tier"]
        if not re.fullmatch(r"[1-5]", t):
            return self._err("档位不对")
        src = self._feed_bg_src(int(t))
        if not src:
            return self._err("没有这一档的背景", 404)
        w = request.query.get("w", "")
        w = max(160, min(900, int(w))) if w.isdigit() else 720
        blur = request.query.get("blur") == "1"
        dst = self.dir / "thumbs" / f"feed-bg{t}-{w}{'-blur' if blur else ''}.jpg"
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            try:
                await asyncio.to_thread(_feed_thumb, src, dst, w, blur)
            except Exception as e:
                logger.warning(f"[lively_panel] 投喂背景缩图失败 bg{t}: {e}")
                return self._err("背景读不出来", 500)
        return web.FileResponse(dst, headers={"Content-Type": "image/jpeg"})

    async def card_bg(self, request):
        """專屬〈卡〉背景（bond 資料目錄 card_bg/<QQ>）：跟投喂背景一樣縮、糊"""
        qq = request.match_info["qq"]
        if not re.fullmatch(r"\d{5,12}", qq):
            return self._err("QQ 号不对")
        b = (await asyncio.to_thread(self._card_bgs)).get(qq)
        if not b:
            return self._err("TA 没有专属背景", 404)
        src = Path(b["path"])
        w = request.query.get("w", "")
        w = max(160, min(900, int(w))) if w.isdigit() else 720
        blur = request.query.get("blur") == "1"
        dst = self.dir / "thumbs" / f"card-bg{qq}-{w}{'-blur' if blur else ''}.jpg"
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            try:
                await asyncio.to_thread(_feed_thumb, src, dst, w, blur)
            except Exception as e:
                logger.warning(f"[lively_panel] 专属卡背景缩图失败 {qq}: {e}")
                return self._err("背景读不出来", 500)
        return web.FileResponse(dst, headers={"Content-Type": "image/jpeg"})

    async def made_av(self, request):
        """定做的虛擬形象：大圖是卡面圖，face=1 是圓圈裡那張臉（跟 bond 發的印象卡一樣裁）"""
        qq = request.match_info["qq"]
        if not re.fullmatch(r"\d{5,12}", qq):
            return self._err("QQ 号不对")
        a = (await asyncio.to_thread(self._made_avs)).get(qq)
        b = self._star("lively_bond")
        ci = sys.modules.get(type(b).__module__.rsplit(".", 1)[0] + ".card_img") if b else None
        if not a or ci is None or not hasattr(ci, "made_faces"):
            return self._err("TA 没有定做的形象", 404)
        w = request.query.get("w", "")
        w = max(80, min(900, int(w))) if w.isdigit() else 640
        face = request.query.get("face") == "1"
        dst = self.dir / "thumbs" / f"made-{qq}-{w}{'-face' if face else ''}.jpg"
        if not dst.exists() or dst.stat().st_mtime < a["v"]:
            try:
                art, ring = await asyncio.to_thread(ci.made_faces, a)
                if (ring if face else art) is None:
                    return self._err("形象读不出来", 500)
                await asyncio.to_thread(_made_thumb, ring if face else art, dst, w)
            except Exception as e:
                logger.warning(f"[lively_panel] 定做的形象缩图失败 {qq}: {e}")
                return self._err("形象读不出来", 500)
        return web.FileResponse(dst, headers={"Content-Type": "image/jpeg"})

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
        cut = time.time() - KEEP_SECS
        logs = [x for x in list(self.logs) if (x.get("ts") or 0) >= cut]
        audit = _recent(self.audit_file, 3000)[::-1][:300]
        return self._ok({"logs": logs, "audit": audit, "since": STARTED, "keep_days": KEEP_DAYS})

    async def make_report(self, request):
        rep = self._star("lively_report")
        if not rep:
            return self._err("汇报插件没加载", 503)
        try:
            text = await asyncio.wait_for(rep.build(datetime.now(TZ)), timeout=90)  # 面板是簡體，不轉繁體
        except Exception as e:
            return self._err(f"生成失败: {e}")
        return self._ok(text=text)
