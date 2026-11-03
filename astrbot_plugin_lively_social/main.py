"""機器人的社交管家：好友申請、群邀請、被禁言/踢出/設管理的通知。

- 聊過天的熟人加好友：自動通過（每天有上限）；〈我〉討厭 TA（好感度 <−8）或態度到了戒備，
  就不自動通過，私信主人時帶上原因（問 bond 的關係讀口）
- 加上好友後不替〈我〉發招呼語（10-26 起）：TA 的私聊裡記一筆、心跳看手機時列在「新加的好友」，打不打招呼、怎麼說〈我〉自己定
- 其他好友申請、別人拉〈我〉進群：告訴主人等主人定。插件不寫固定句（10-26 用戶定）：事實交給〈我〉寫一句（可以帶她的看法），
  再發一張【后台】資料卡（名字、號碼、驗證信息、在哪些群）；主人怎麼回都交給〈我〉，她用 lively_requests 去辦，
  沒有「同意 / 拒絕 / 拉黑」固定指令了。面板信箱照舊能處理
- 主人拉〈我〉進群：不找主人審批，記在主人的私聊裡讓〈我〉知道，進不進〈我〉自己定（10-26 用戶定）
- 工具 lively_requests：〈我〉看還在等的申請、同意、拒絕、拉黑。同意、拉黑別人的申請要主人說了才做得成；主人拉的群和拒絕〈我〉自己就能做
- 重啟、斷線那半分鐘來的群邀請事件收不到，QQ 那邊還留著：每 5 分鐘問一次 NapCat，漏掉的照現場來的處理
- 被踢、沒經過審批就進了群：一定告訴主人（她寫一句＋一行【后台】）；禁言、解禁、審批過的進群、管理員變動、自動通過的好友：
  說不說她定，不說就只記一筆讓她知道。禁言期間那個群的消息不再交給模型（反正發不出去）
- 所有事件記進 events.jsonl，給每日彙報用
"""
import asyncio
import json
import sqlite3
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, StarTools, register

from .lively_common import BACKSTAGE_KIND, Settings, T2S, note_outbox, tail_lines, tell_owner

AUTO_MIN_TALKS = 1  # 和機器人直接聊過至少這麼多次，才算熟人
AUTO_DAILY_MAX = 10
PENDING_TTL = 7 * 86400
INVITE_SYNC = 300  # 多久問一次 NapCat 還沒處理的群邀請
SEEN_KEEP = 50  # 處理過的邀請記住最近幾個（flag），過期丟掉的不再撈回來
# 全員禁言、沒帶時長的禁言不知道哪時解：先當作這麼久。解禁那刻剛好重啟或斷線、漏了事件，也不會在那個群一直不說話
UNKNOWN_BAN = 12 * 3600
NEW_FRIEND_KEEP = 3 * 86400  # 新加的好友記多久（自主插件的心跳看手機時會看到）


def _now() -> float:
    return time.time()


def _ago(ts: float) -> str:
    s = max(0, _now() - (ts or 0))
    return "刚刚" if s < 60 else f"{int(s // 60)} 分钟前" if s < 3600 else f"{int(s // 3600)} 小时前" if s < 86400 else f"{int(s // 86400)} 天前"


@register(
    "astrbot_plugin_lively_social",
    "GUCine",
    "好友申請、群邀請、禁言踢出通知，熟人自動通過，其餘私信主人決定",
    "2.0.0",
)
class LivelySocial(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.s = Settings(context, config)
        self.dir = Path(StarTools.get_data_dir("astrbot_plugin_lively_social"))
        self.state_file = self.dir / "state.json"
        self.events_file = self.dir / "events.jsonl"
        self.state = self._load()
        self.bond_db = Path(StarTools.get_data_dir("astrbot_plugin_lively_bond")) / "bond.db"
        self._tasks: set = set()
        self._task = asyncio.create_task(self._loop())

    async def terminate(self):
        if getattr(self, "_task", None):
            self._task.cancel()
        for t in list(getattr(self, "_tasks", ())):
            t.cancel()

    # ---------- 存儲 ----------
    def _load(self) -> dict:
        try:
            s = json.loads(self.state_file.read_text("utf-8"))
        except Exception:
            s = {}
        s.setdefault("pending", {})  # key: "friend:QQ" / "group:群號"
        s.setdefault("blacklist", [])
        s.setdefault("muted", {})  # 群號 -> 解除時間
        for gid, until in s["muted"].items():
            if not until:  # 舊版記的 0（直到解禁）
                s["muted"][gid] = int(_now()) + UNKNOWN_BAN
        s.setdefault("auto_day", "")
        s.setdefault("auto_count", 0)
        s.setdefault("seen_invites", [])
        s.setdefault("new_friends", [])
        return s

    def _save(self):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), "utf-8")
            tmp.replace(self.state_file)
        except Exception as e:
            logger.error(f"[lively_social] 保存状态失败: {e}")

    def _log(self, kind: str, **data):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with self.events_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": int(_now()), "kind": kind, **data}, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[lively_social] 记录事件失败: {e}")

    # ---------- 告訴主人 ----------
    def _notify(self, facts: str, what: str, must: bool = False, card: str = "", kind: str = ""):
        """後台的事告訴主人（在背景問她要說什麼，事件處理不等）：must 的一定發（她的話＋【后台】卡片），
        不是 must 的說不說她定。插件不寫冒充她口吻的句子"""
        async def run():
            try:
                said = await tell_owner(self.s, facts, what, must=must, card=card, kind=kind or what)
                self._log("report", what=what, must=must, said=said[:300])
            except Exception as e:
                logger.error(f"[lively_social] 告诉主人「{what}」失败: {e}", exc_info=True)
        t = asyncio.create_task(run())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _rel_text(self, qq: str) -> str:
        """〈我〉和 TA 怎麼樣（關係讀口那句，不帶私下）；舊版 bond 沒有就空字串"""
        b = self._star("lively_bond")
        rel = getattr(b, "rel", None) if b else None
        if not b or not hasattr(b, "relation") or rel is None or not hasattr(rel, "say_about"):
            return ""
        try:
            return self.s.fill(rel.say_about(b.relation(qq)))
        except Exception as e:
            logger.warning(f"[lively_social] 问 bond 的关系失败: {e}")
            return ""

    def _star(self, short: str):
        meta = self.context.get_registered_star(f"astrbot_plugin_{short}")
        return getattr(meta, "star_cls", None) if meta and getattr(meta, "activated", True) else None

    def _wary(self, qq: str) -> str:
        """〈我〉不想自動加 TA 的原因（討厭、戒備以上）；沒有就空字串。舊版 bond 沒有讀口就不管"""
        b = self._star("lively_bond")
        if not b or not hasattr(b, "relation"):
            return ""
        try:
            r = b.relation(qq)
        except Exception as e:
            logger.warning(f"[lively_social] 问 bond 的关系失败: {e}")
            return ""
        bits = []
        if r.get("tier") == "讨厌":
            bits.append(f"讨厌 TA（好感度 {r['score']:g}）")
        if (r.get("attitude") or 0) >= 2:
            bits.append(f"对 TA {r['attitude_name']}" + (f"（{r['attitude_reason'][:30]}）" if r.get("attitude_reason") else ""))
        return "、".join(bits)

    def _talks(self, qq: str) -> int:
        try:
            con = sqlite3.connect(f"file:{self.bond_db}?mode=ro", uri=True)
            row = con.execute("select talks from people where qq=?", (qq,)).fetchone()
            con.close()
            return int(row[0] or 0) if row else 0
        except Exception:
            return 0

    async def _group_name(self, bot, gid: str) -> str:
        try:
            return (await bot.get_group_info(group_id=int(gid)) or {}).get("group_name") or gid
        except Exception:
            return gid

    async def _gnames(self, bot, gids: list[str]) -> str:
        return "、".join([f"「{n}」" if (n := await self._group_name(bot, g)) != g else g for g in gids])

    async def _where(self, bot, gid: str) -> str:
        """「群名」（群號）；查不到名字就只寫群號"""
        name = await self._group_name(bot, gid) if bot else gid
        return f"「{name}」（{gid}）" if name and name != gid else f" {gid}"

    async def _who(self, bot, qq: str) -> str:
        if not qq or qq == "0":
            return "管理员"
        name = await self._nickname(bot, qq) if bot else qq
        return f"{name}（QQ {qq}）" if name and name != qq else f"QQ {qq}"

    async def _nickname(self, bot, qq: str) -> str:
        try:
            return (await bot.get_stranger_info(user_id=int(qq)) or {}).get("nickname") or qq
        except Exception:
            return qq

    def _decided_group(self, gid: str, within: float = 3600) -> dict | None:
        """最近一小時在〈我〉這邊處理過這個群的邀請（主人審批或〈我〉在聊天裡同意的）；回傳那筆記錄"""
        for line in reversed(tail_lines(self.events_file, 50)):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("kind") == "group_decided" and str(d.get("id")) == gid and d.get("ts", 0) > _now() - within:
                return d
        return None

    async def _common_groups(self, bot, qq: str) -> list[str]:
        found = []
        for gid in sorted(self.s.groups()):
            try:
                await bot.get_group_member_info(group_id=int(gid), user_id=int(qq), no_cache=False)
                found.append(gid)
            except Exception:
                pass
        return found

    def _auto_quota_left(self) -> bool:
        day = time.strftime("%Y-%m-%d")
        if self.state["auto_day"] != day:
            self.state["auto_day"], self.state["auto_count"] = day, 0
        return self.state["auto_count"] < AUTO_DAILY_MAX

    def _prune(self):
        cut = _now() - PENDING_TTL
        for k in [k for k, v in self.state["pending"].items() if v.get("ts", 0) < cut]:
            self.state["pending"].pop(k, None)
        for gid, until in list(self.state["muted"].items()):
            if until and until < _now():
                self.state["muted"].pop(gid, None)

    # ---------- 入口：在閘門插件（1000）之前，群邀請事件帶的是新群號，會被閘門攔掉 ----------
    @filter.event_message_type(filter.EventMessageType.ALL, priority=2000)
    async def on_event(self, event: AstrMessageEvent):
        raw = getattr(event.message_obj, "raw_message", None)
        post = raw.get("post_type") if isinstance(raw, dict) else None
        if post == "request":
            event.stop_event()
            await self._on_request(event, raw)
            return
        if post == "notice":
            await self._on_notice(event, raw)
            return
        # 主人審批不再攔成指令（10-26 用戶定）：主人怎麼回都交給〈我〉，她用 lively_requests 去辦
        # 禁言中的群：消息不交給模型
        gid = str(event.get_group_id() or "")
        if gid and gid in self.state["muted"]:
            until = self.state["muted"][gid]
            if until > _now():
                event.stop_event()
            else:
                self.state["muted"].pop(gid, None)
                self._save()

    # ---------- 申請 ----------
    async def _on_request(self, event: AstrMessageEvent, raw: dict):
        self._prune()
        bot = getattr(event, "bot", None)
        rtype = raw.get("request_type")
        qq = str(raw.get("user_id") or "")
        flag = raw.get("flag", "")
        comment = (raw.get("comment") or "").strip() or "无"
        nickname = qq
        try:
            info = await bot.get_stranger_info(user_id=int(qq)) or {}
            nickname = info.get("nickname") or qq
        except Exception:
            pass

        if rtype == "friend":
            if qq in self.state["blacklist"]:
                await self._approve(bot, "friend", flag, False)
                self._log("friend_request", qq=qq, name=nickname, result="黑名单拒绝")
                return
            talks = self._talks(qq)
            groups = await self._common_groups(bot, qq) if bot else []
            wary = "" if self.s.is_owner(qq) else self._wary(qq)
            if self.s.is_owner(qq) or (talks >= AUTO_MIN_TALKS and not wary and self._auto_quota_left()):
                if await self._approve(bot, "friend", flag, True):
                    if not self.s.is_owner(qq):
                        self.state["auto_count"] += 1
                    self._save()
                    self._log("friend_request", qq=qq, name=nickname, result="自动通过", talks=talks)
                    if not self.s.is_owner(qq):
                        gn = await self._gnames(bot, groups)
                        self._notify(f"〈我〉自己通过了一个好友申请：{nickname}，之前和〈我〉直接聊过 {talks} 次"
                                     + (f"，在群 {gn}" if gn else "") + "（聊过的人加好友会自动通过）",
                                     "自己通过了好友申请", kind="好友申请")
                    self._friend_added(qq, nickname, f"之前聊过 {talks} 次，按「聊过的人自动通过」通过的")
                return
            key = f"friend:{qq}"
            self.state["pending"][key] = {
                "type": "friend", "id": qq, "name": nickname, "flag": flag,
                "comment": comment, "ts": int(_now()), "groups": groups,
            }
            self._save()
            self._log("friend_request", qq=qq, name=nickname, result="等主人决定", talks=talks, **({"wary": wary} if wary else {}))
            gn = await self._gnames(bot, groups)
            where = f"在群 {gn}" if gn else "不在〈我〉服务的群里"
            rel = self._rel_text(qq)
            self._notify(
                f"有人想加〈我〉QQ 好友，在等〈主人〉决定（〈主人〉同意了才加得上）\n名字：{nickname}\n验证信息：{comment}\n"
                f"{where}，和〈我〉直接聊过 {talks} 次" + (f"\n没自动通过，因为〈我〉{wary}" if wary else "")
                + (f"\n{rel}" if rel else ""),
                "有人想加好友", must=True, kind="好友申请",
                card=(f"好友申请 · 等你定\n{nickname}（QQ {qq}）\n验证信息：{comment}\n{where.replace('〈我〉', '她')}；和她聊过 {talks} 次"
                      + (f"\n没自动通过：她{wary}" if wary else "")),
            )
            return

        if rtype == "group" and raw.get("sub_type") == "invite":
            await self._on_invite(bot, str(raw.get("group_id") or ""), qq, nickname, str(flag))

    async def _on_invite(self, bot, gid: str, qq: str, nickname: str, flag: str, gname: str = "", late: bool = False):
        """有人拉〈我〉進群。主人拉的：記在主人私聊裡，進不進〈我〉自己定；別人拉的：私信主人審批。
        late：事件當時沒收到，事後從 NapCat 撈到的"""
        seen = self.state["seen_invites"]
        if flag and flag in seen:
            return
        if flag:
            seen.append(flag)
            del seen[:-SEEN_KEEP]
        if bot and (not gname or gname == gid):
            gname = await self._group_name(bot, gid)
        gname = gname or gid
        mine = self.s.is_owner(qq)
        self.state["pending"][f"group:{gid}"] = {
            "type": "group", "id": gid, "name": gname, "flag": flag,
            "inviter": qq, "inviter_name": nickname, "ts": int(_now()), **({"her": True} if mine else {}),
        }
        self._save()
        self._log("group_invite", group=gid, name=gname, inviter=qq,
                  result="等〈我〉决定" if mine else "等主人决定", **({"late": True} if late else {}))
        where = f"「{gname}」（{gid}）" if gname != gid else f"群 {gid}"
        late_note = "（是〈我〉重启或掉线那会儿来的，刚刚才看到）" if late else ""
        if mine:
            note_outbox(self.s.private_umo(qq), self.s.fill(
                f"〈主人〉拉〈我〉进群{where}的邀请到了{late_note}，还没同意也没拒绝，进不进由〈我〉自己定"), "群邀请")
            logger.info(f"[lively_social] 主人拉她进群 {gid}，等她自己决定" + ("（补上漏掉的）" if late else ""))
            return
        rel = self._rel_text(qq) if qq else ""
        self._notify(
            f"{nickname} 拉〈我〉进群{where}，在等〈主人〉决定{late_note}\n"
            "进了群也先不在那边说话：要在那边说话，得〈主人〉把这个群加进〈我〉服务的群里" + (f"\n{rel}" if rel else ""),
            "有人拉进群", must=True, kind="群邀请",
            card=(f"群邀请 · 等你定\n{nickname}" + (f"（QQ {qq}）" if qq else "") + f"拉她进群{where}"
                  + ("（重启或掉线那会儿来的，刚刚才看到）" if late else "") + "\n进了群也先不说话，要她在那边说话得把群加进服务的群"),
        )

    # ---------- 漏掉的群邀請：重啟、斷線那會兒來的事件收不到，QQ 那邊還留著 ----------
    async def _loop(self):
        await asyncio.sleep(60)  # 等 QQ 連上
        failing = 0  # 連著失敗幾次：QQ 掉線時每 5 分鐘都會失敗，只在第一次和恢復時說
        while True:
            try:
                n = await self._sync_invites()
                if failing:
                    logger.info(f"[lively_social] 查漏掉的群邀请恢复了（之前连着失败 {failing} 次）")
                failing = 0
                if n:
                    logger.info(f"[lively_social] 补上了 {n} 个漏掉的群邀请")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failing += 1
                if failing == 1:
                    logger.warning(f"[lively_social] 查漏掉的群邀请失败: {type(e).__name__}: {e}"
                                   "（QQ 掉线时会一直失败，之后不再重复报，恢复了再说一声）")
            await asyncio.sleep(INVITE_SYNC)

    async def _sync_invites(self, bot=None) -> int:
        """問 NapCat 還沒處理的群邀請，沒收到事件的照現場來的處理；回傳補上了幾個"""
        bot = bot or self.s.client()
        if bot is None:
            return 0
        res = await bot.api.call_action("get_group_system_msg")
        rows = (res or {}).get("invited_requests") or (res or {}).get("InvitedRequest") or []
        me = str(self.s.bot_qq() or "")
        self._prune()
        n = 0
        for r in rows:
            gid, flag = str(r.get("group_id") or ""), str(r.get("request_id") or "")
            if r.get("checked") or not gid or not flag or flag in self.state["seen_invites"]:
                continue
            old = self.state["pending"].get(f"group:{gid}")
            if old and old.get("flag") == flag:
                continue
            seq = int(r["request_id"]) if str(r.get("request_id")).isdigit() else 0
            if 1e15 < seq < 1e17 and seq / 1e6 < _now() - PENDING_TTL:  # seq 是微秒時間；太舊的不撈
                continue
            # 拉〈我〉的人：NapCat 給〈我〉的邀請 invitor 是〈我〉自己、actor 才是拉的人
            qq = next((str(x) for x in (r.get("actor"), r.get("invitor_uin")) if x and str(x) != me), "")
            name = await self._nickname(bot, qq) if qq else "有人"
            await self._on_invite(bot, gid, qq, name, flag, gname=str(r.get("group_name") or ""), late=True)
            n += 1
        return n

    async def _approve(self, bot, kind: str, flag: str, ok: bool) -> bool:
        try:
            if kind == "friend":
                await bot.set_friend_add_request(flag=flag, approve=ok)
            else:
                await bot.set_group_add_request(flag=flag, sub_type="invite", approve=ok)
            return True
        except Exception as e:
            logger.error(f"[lively_social] 审批失败: {e}")
            return False

    def _friend_added(self, qq: str, name: str, how: str):
        """加上了好友：以前程式隨機挑一句固定的招呼語用〈我〉的口吻發過去（10-26 用戶定插件不替她說話）。
        現在只讓〈我〉知道：TA 的私聊裡記一筆（TA 先開口時看得到），心跳看手機時也看得到「新加的好友」，打不打招呼、怎麼說她定"""
        now = int(_now())
        rows = [r for r in self.state.setdefault("new_friends", []) if now - r.get("ts", 0) < NEW_FRIEND_KEEP and r.get("qq") != qq]
        rows.append({"qq": qq, "name": name or qq, "ts": now, "how": how})
        self.state["new_friends"] = rows[-20:]
        self._save()
        note_outbox(self.s.private_umo(qq), f"TA 刚加了〈我〉QQ 好友（{how}），〈我〉还没跟 TA 说过话", "加好友")

    def new_friends(self, since: float = 0) -> list[dict]:
        """since 之後新加的好友（新的在後）：[{qq, name, ts, how}]，自主插件的心跳讀"""
        cut = max(since, _now() - NEW_FRIEND_KEEP)
        return [dict(r) for r in self.state.get("new_friends", []) if r.get("ts", 0) > cut]

    async def decide(self, key: str, action: str, bot=None, via: str = "panel", by: str = "", umo: str = "") -> tuple[bool, str]:
        """處理一個在等的申請（面板按鈕、〈我〉的工具都走這裡）：同意、拒绝、拉黑（拉黑＝拒絕＋以後 TA 再申請直接拒掉）。
        回 (成沒成, 事實一句)"""
        req = self.state["pending"].get(key)
        if not req:
            return False, "这个申请不在了，可能已经处理过或者过期了"
        bot = bot or self.s.client()
        ok = action == "同意"
        done = await self._approve(bot, req["type"], req["flag"], ok) if bot is not None else False
        if done or action == "拉黑":  # 沒成功就留在待辦裡，還能再處理
            self.state["pending"].pop(key, None)
        if action == "拉黑" and req["type"] == "friend" and req["id"] not in self.state["blacklist"]:
            self.state["blacklist"].append(req["id"])
        self._save()
        self._log(f"{req['type']}_decided", id=req["id"], name=req["name"], action=action, done=done, via=via,
                  **({"by": by} if by else {}), **({"umo": umo} if umo else {}))
        what = f"{req['name']}（{req['id']}）的" + ("好友申请" if req["type"] == "friend" else "群邀请")
        if via == "panel" and self.s.owner():  # 〈主人〉在面板按的：讓〈我〉知道（主人接著問起時不會一臉茫然）
            note_outbox(self.s.private_umo(self.s.owner()),
                        self.s.fill(f"〈主人〉在面板{action}了{what}" + ("" if done else "（QQ 那边没处理成）")),
                        f"{BACKSTAGE_KIND}:{'好友申请' if req['type'] == 'friend' else '群邀请'}")
        if ok and done and req["type"] == "friend":
            how = {"panel": "〈主人〉在面板同意的", "chat": "〈主人〉在聊天里同意的" if self.s.is_owner(by) else "〈我〉在聊天里同意的"}
            self._friend_added(req["id"], req["name"], how.get(via, "〈主人〉同意的"))
        if not done:
            return (True, f"拉黑了{what}：以后 TA 再申请会直接拒掉（这次 QQ 那边没处理成，申请可能已经过期）") if action == "拉黑" \
                else (False, f"没{action}成：QQ 那边处理失败了，{what}可能已经过期或者处理过了")
        if action == "拉黑":
            return True, f"拉黑了{what}：拒绝了这次申请，以后 TA 再申请会直接拒掉"
        return True, f"{action}了{what}"

    # ---------- 〈我〉自己看、處理申請 ----------
    @filter.llm_tool("lively_requests")
    async def tool_requests(self, event: AstrMessageEvent, action: str = "看", who: str = ""):
        """看、处理别人加你好友、拉你进群的申请。
        「看」列出还在等的（主人看得到全部，别人只看得到 TA 自己的那个）；「同意」「拒绝」「拉黑」处理其中一个（拉黑＝拒绝这次，以后 TA 再申请会直接拒掉）。
        主人拉你进的群，进不进你自己定；别人的申请要主人说了同意（或拉黑）才做得成；拒绝你自己就能做。
        主人回申请没有固定说法，主人怎么说的你自己理解。
        进了群不等于会在那边说话：那个群还要加进你服务的群里（lively_serve_group），你才看得到那边的消息。

        Args:
            action(string): 看、同意、拒绝、拉黑
            who(string): 哪一个：QQ 号、群号，或名字、群名里的字；只有一个在等时可以不写
        """
        bot = getattr(event, "bot", None) or self.s.client()
        if bot is not None:
            try:  # 先撈一遍：剛來的邀請可能正好碰上重啟沒收到
                await self._sync_invites(bot)
            except Exception as e:
                logger.warning(f"[lively_social] 查漏掉的群邀请失败: {e}")
        self._prune()
        caller = str(event.get_sender_id() or "")
        boss = self.s.is_owner(caller)
        items = {k: v for k, v in self.state["pending"].items()
                 if boss or caller in (str(v.get("id")), str(v.get("inviter") or ""))}
        a = str(action or "").translate(T2S)
        act = ("拉黑" if ("黑" in a or "屏蔽" in a) else "拒绝" if ("拒" in a or "不" in a)
               else "同意" if any(x in a for x in ("同意", "通过", "接受", "进", "加")) else "看")
        none = "没有在等的申请" if boss else "没有 TA 的申请在等"
        done_note = ("。最近一天处理过的：" + "；".join(d)) if boss and (d := self._recent_done()) else ""
        if act == "看":
            text = ("还在等的：" + "；".join(self._req_line(v) for v in items.values())) if items else none
            return self.s.fill(text + done_note)
        keys = self._match(items, who)
        if not keys:
            return self.s.fill((f"没找到「{who}」的申请" if who and items else none) + done_note)
        if len(keys) > 1:
            return self.s.fill("好几个在等，要说是哪一个：" + "；".join(self._req_line(items[k]) for k in keys))
        key = keys[0]
        req = items[key]
        what = f"{req['name']}（{req['id']}）的" + ("好友申请" if req["type"] == "friend" else "群邀请")
        ok = act == "同意"
        if act in ("同意", "拉黑") and not req.get("her") and not boss:
            return self.s.fill(f"没{act}：{what}要〈主人〉说了才做得成，现在在〈主人〉的信箱里等着")
        if act == "拉黑" and req["type"] != "friend":
            act = "拒绝"  # 群邀請沒有黑名單，照拒絕處理
        done, fact = await self.decide(key, act, bot, via="chat", by=caller, umo=event.unified_msg_origin)
        if not done or not ok:
            return self.s.fill(fact)
        if req["type"] == "group":
            return self.s.fill(f"同意了{what}。这个群还不在〈我〉服务的群里，进去以后那边的消息〈我〉看不到、也不会在那边说话；"
                               "加进服务的群要〈主人〉说了才行（lively_serve_group）")
        return self.s.fill(fact)

    def _match(self, items: dict, who: str) -> list[str]:
        who = str(who or "").strip()
        if not who:
            return list(items)
        exact = [k for k, v in items.items() if str(v.get("id")) == who or str(v.get("inviter") or "") == who]
        return exact or [k for k, v in items.items() if who in str(v.get("name") or "")]

    def _req_line(self, v: dict) -> str:
        ago = _ago(v.get("ts", 0))
        if v.get("type") == "friend":
            return f"{v.get('name')}（QQ {v.get('id')}）想加〈我〉好友，验证信息：{v.get('comment') or '无'}，{ago}，在等〈主人〉决定"
        who = f"{v.get('inviter_name') or '有人'}（{v.get('inviter')}）" if v.get("inviter") else "有人"
        return (f"{who}拉〈我〉进群「{v.get('name')}」（{v.get('id')}），{ago}，"
                + ("〈主人〉拉的，进不进〈我〉自己定" if v.get("her") else "在等〈主人〉决定"))

    def _recent_done(self, within: float = 86400) -> list[str]:
        """最近一天處理過的申請、進的群（主人問起時照實說）"""
        out = []
        for line in tail_lines(self.events_file, 200):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("ts", 0) < _now() - within:
                continue
            k = d.get("kind")
            if k in ("friend_decided", "group_decided"):
                what = "好友申请" if k == "friend_decided" else "群邀请"
                out.append(f"{_ago(d['ts'])}{d.get('action')}{d.get('name')}（{d.get('id')}）的{what}" + ("" if d.get("done", True) else "，没成"))
            elif k == "joined":
                out.append(f"{_ago(d['ts'])}进了群 {d.get('group')}")
        return out[-5:]

    # ---------- 通知 ----------
    async def _on_notice(self, event: AstrMessageEvent, raw: dict):
        ntype = raw.get("notice_type")
        sub = raw.get("sub_type")
        self_id = str(raw.get("self_id") or event.get_self_id() or "")
        uid = str(raw.get("user_id") or "")
        gid = str(raw.get("group_id") or "")
        op = str(raw.get("operator_id") or "")
        if ntype == "group_ban" and uid in (self_id, "0"):
            whole = uid == "0"
            if sub == "ban":
                dur = int(raw.get("duration") or 0)
                self.state["muted"][gid] = int(_now()) + (UNKNOWN_BAN if whole or dur <= 0 else dur)
                self._save()
                self._log("muted", group=gid, operator=op, duration=dur, whole=whole)
                bot = getattr(event, "bot", None)
                where, who = await self._where(bot, gid), await self._who(bot, op)
                how = "开了全员禁言" if whole else f"被 {who} 禁言了 {max(1, dur // 60)} 分钟"
                self._notify(f"〈我〉在群{where}{how}；禁言期间那个群的消息不会交给〈我〉（反正发不出去）",
                             "被禁言", kind="被禁言")
            elif sub == "lift_ban":
                self.state["muted"].pop(gid, None)
                self._save()
                self._log("unmuted", group=gid, operator=op, whole=whole)
                where = await self._where(getattr(event, "bot", None), gid)
                self._notify(f"群{where}解除了〈我〉的禁言，又能在那边说话了", "解禁", kind="解禁")
        elif ntype == "group_decrease" and sub == "kick_me":
            self.state["muted"].pop(gid, None)
            self._save()
            self._log("kicked", group=gid, operator=op)
            bot = getattr(event, "bot", None)
            where, who = await self._where(bot, gid), await self._who(bot, op)
            self._notify(f"〈我〉被 {who} 踢出了群{where}", "被踢出群", must=True, kind="被踢",
                         card=f"被踢出群：{where.strip()}，{who} 踢的")
        elif ntype == "group_increase" and uid == self_id:
            self._log("joined", group=gid, operator=op)
            bot = getattr(event, "bot", None)
            gname, opname = await self._group_name(bot, gid), await self._nickname(bot, op)
            # 走過〈我〉這邊的邀請審批才進的，還是 QQ 那邊沒讓審批就直接進了（好友拉群常常不用同意）
            decided = self._decided_group(gid)
            asked = self.state["pending"].pop(f"group:{gid}", None) is not None or decided is not None
            self._save()
            where = f"「{gname}」（{gid}）" if gname and gname != gid else gid
            who = f"{opname}（{op}）" if opname and opname != op else op
            served = gid in self.s.groups()
            stay = "" if served else "；这个群还不在〈我〉服务的群里，那边的消息〈我〉看不到"
            if decided and decided.get("via") == "chat" and decided.get("action") == "同意" and decided.get("umo"):
                # 〈我〉自己在聊天裡同意的，那邊已經說過了：不再替〈我〉發一句，只記一筆讓〈我〉知道進去了
                note_outbox(decided["umo"], self.s.fill(f"〈我〉进了群 {where}{stay}"), "进了新群")
                return
            if asked:
                self._notify(f"〈我〉进了群 {where}，{who} 拉的（邀请审批过）{stay}", "进了新群", kind="进了新群")
            else:
                self._notify(f"〈我〉进了群 {where}，{who} 拉的；这次没收到邀请让〈主人〉审批，QQ 那边直接就进了{stay}",
                             "没经过审批进了群", must=True, kind="进了新群",
                             card=f"进了新群（没经过审批）：{where}，{who} 拉的" + ("" if served else "\n这个群还不在服务的群里，那边的消息她看不到"))
        elif ntype == "group_admin" and uid == self_id:
            self._log("admin_" + str(sub), group=gid)
            where = await self._where(getattr(event, "bot", None), gid)
            self._notify(f"〈我〉在群{where}{'被设成了管理员' if sub == 'set' else '的管理员被取消了'}", "管理员变动", kind="管理员")
        elif ntype == "friend_add":
            self._log("friend_added", qq=uid)
