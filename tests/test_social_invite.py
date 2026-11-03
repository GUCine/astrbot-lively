"""群邀請、好友申請（10-26）：主人拉的群進不進〈我〉自己定（不找主人審批），別人拉的、加好友的告訴主人等主人定；
重啟、斷線那會兒沒收到的邀請從 NapCat 的 get_group_system_msg 撈回來；工具 lively_requests 看、同意、拒絕、拉黑。
10-26 晚起告訴主人的話是她寫的（lively_common.tell_owner，這裡換成記下來的假的），要主人拍板的另附【后台】卡片；
沒有「同意 / 拒绝 / 拉黑」固定指令了，主人怎麼回都交給她。
stub 掉 astrbot，號碼都是假的：10001 主人、10002〈我〉、2000x 群友、3000x 群。

/usr/local/bin/python3 tests/test_social_invite.py
"""
import asyncio, importlib, json, sys, tempfile, time, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
class Dummy:
    def __init__(self, *a, **k): pass
def deco(*a, **k): return lambda f: f
class Chain:
    def __init__(self): self.chain = []
    def message(self, t): self.chain.append(t); return self
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco, command=deco, on_agent_done=deco,
      EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.star", Context=object, Star=Dummy, register=deco, StarTools=Dummy)
mod("astrbot.core"); mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Chain)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sm = importlib.import_module("astrbot_plugin_lively_social.main")
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, "" if ok else extra)
    if not ok:
        fails.append(name)


OWNER, ME, P1, P2 = "10001", "10002", "20001", "20002"
NOW = time.time()
SEQ = lambda t: int(t * 1e6)  # NapCat 的 request_id 是微秒時間


class Bot:
    def __init__(self, rows=(), fail=False):
        self.rows, self.fail, self.done = list(rows), fail, []
        self.api = types.SimpleNamespace(call_action=self.call_action)
    async def call_action(self, action, **kw):
        assert action == "get_group_system_msg", action
        return {"invited_requests": self.rows, "join_requests": []}
    async def get_group_info(self, group_id): return {"group_name": {30001: "浅梦", 30002: "花生的群"}.get(group_id, "")}
    async def get_stranger_info(self, user_id): return {"nickname": {10001: "陈", 20001: "花生", 20002: "瓜子"}.get(user_id, "")}
    async def set_group_add_request(self, flag, sub_type, approve):
        if self.fail:
            raise RuntimeError("No such request")
        self.done.append((flag, sub_type, approve))
    async def set_friend_add_request(self, flag, approve):
        self.done.append((flag, "friend", approve))


class SS:
    def __init__(self): self.bot = None
    def owner(self): return OWNER
    def is_owner(self, qq): return str(qq) == OWNER
    def private_umo(self, qq): return f"x:FriendMessage:{qq}"
    def owner_text(self, t): return self.fill(t)
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def bot_qq(self): return ME
    def client(self): return self.bot
    def groups(self): return ["30009"]


class Ctx:
    def __init__(self): self.sent = []
    def get_registered_star(self, name): return None
    async def send_message(self, umo, chain): self.sent.append((umo, chain.chain[0])); return True


notes = []
sm.note_outbox = lambda umo, text, kind="": notes.append((umo, text, kind))
told = []  # 交給她告訴主人的事：{facts, what, must, card, kind}


async def fake_tell(s, facts, what, *, must=False, card="", image=None, kind=""):
    told.append({"facts": facts, "what": what, "must": must, "card": card, "kind": kind})
    return "她的话"
sm.tell_owner = fake_tell


def run(so, coro):
    """跑完再等背景裡告訴主人的那些（asyncio.run 結束會把沒做完的取消掉）"""
    async def go():
        r = await coro
        await asyncio.gather(*list(so._tasks))
        return r
    return asyncio.run(go())


def fresh():
    so = sm.LivelySocial.__new__(sm.LivelySocial)
    so.s, so.context = SS(), Ctx()
    so.dir = Path(tempfile.mkdtemp())
    so.state_file, so.events_file = so.dir / "state.json", so.dir / "events.jsonl"
    so.state = so._load()
    so._tasks = set()
    notes.clear()
    told.clear()
    return so


def events(so):
    return [json.loads(x) for x in so.events_file.read_text("utf-8").splitlines()] if so.events_file.exists() else []


class Ev:
    def __init__(self, sender, text="", bot=None, group="", raw=None):
        self.sender, self.message_str, self.bot, self.group = sender, text, bot, group
        self.message_obj = types.SimpleNamespace(raw_message=raw or {})
        self.unified_msg_origin = f"x:FriendMessage:{sender}"
        self.stopped, self.sent = False, []
    def get_sender_id(self): return self.sender
    def get_group_id(self): return self.group
    def stop_event(self): self.stopped = True
    async def send(self, chain): self.sent.append(chain.chain[0])


# ---- 現場來的：主人拉的不找主人，記在主人私聊裡等〈我〉自己定；別人拉的照舊私信主人 ----
so, bot = fresh(), Bot()
run(so, so.on_event(Ev(OWNER, bot=bot, raw={"post_type": "request", "request_type": "group", "sub_type": "invite",
                                                  "group_id": 30001, "user_id": 10001, "flag": "111"})))
p = so.state["pending"].get("group:30001") or {}
check("主人拉的记下来、标成她自己定", p.get("her") and p.get("flag") == "111" and p.get("name") == "浅梦", p)
check("主人拉的不私信主人审批", so.context.sent == [] and told == [], (so.context.sent, told))
check("主人私聊里记一笔让她知道", notes and notes[-1][0] == f"x:FriendMessage:{OWNER}" and "进不进由本鱼自己定" in notes[-1][1]
      and "浅梦" in notes[-1][1] and "刚刚才看到" not in notes[-1][1], notes)
check("记录里写等她决定", events(so)[-1]["result"] == "等〈我〉决定", events(so))
check("没同意", bot.done == [], bot.done)
run(so, so.on_event(Ev(OWNER, bot=bot, raw={"post_type": "request", "request_type": "group", "sub_type": "invite",
                                                  "group_id": 30002, "user_id": 20001, "flag": "222"})))
t = told[-1] if told else {}
check("别人拉的交给她告诉主人（一定发）", t.get("must") and t.get("kind") == "群邀请"
      and "花生 拉〈我〉进群「花生的群」（30002）" in t.get("facts", ""), told)
check("附一张后台卡：谁、哪个群、等你定", t.get("card", "").startswith("群邀请 · 等你定\n花生（QQ 20001）拉她进群「花生的群」（30002）")
      and "〈我〉" not in t.get("card", ""), t.get("card"))
check("没有固定指令的说明", not any("同意 30002" in x["facts"] + x["card"] or "回「" in x["facts"] + x["card"] for x in told), told)
check("别人拉的等主人", not so.state["pending"]["group:30002"].get("her"))

# ---- 主人說「同意」不再攔成指令：那句照常交給她，她用工具去辦 ----
so2 = fresh()
so2.state["pending"]["group:30001"] = {"type": "group", "id": "30001", "name": "浅梦", "flag": "111", "inviter": OWNER, "ts": NOW, "her": True}
so2.state["pending"]["friend:20002"] = {"type": "friend", "id": "20002", "name": "瓜子", "flag": "f2", "ts": NOW}
b2 = Bot()
for word in ("同意", "同意 30001", "同意 20002", "拉黑"):
    e = Ev(OWNER, word, bot=b2)
    run(so2, so2.on_event(e))
    check(f"主人说「{word}」交给她", not e.stopped and b2.done == [] and len(so2.state["pending"]) == 2, (e.stopped, b2.done))

# ---- 好友申請：熟人自動通過（說不說她定）、別人的告訴主人（她的話＋卡片） ----
so6 = fresh()
so6._talks = lambda qq: {"20001": 3}.get(qq, 0)
b6 = Bot()
run(so6, so6.on_event(Ev(P1, bot=b6, raw={"post_type": "request", "request_type": "friend", "user_id": 20001, "flag": "ff1", "comment": "我是花生"})))
check("聊过的自动通过", b6.done == [("ff1", "friend", True)] and so6.state["new_friends"][-1]["qq"] == P1, b6.done)
check("自动通过的说不说她定", told and not told[-1]["must"] and "自己通过了一个好友申请：花生" in told[-1]["facts"], told)
run(so6, so6.on_event(Ev(P2, bot=b6, raw={"post_type": "request", "request_type": "friend", "user_id": 20002, "flag": "ff2", "comment": "交个朋友"})))
t = told[-1]
check("没聊过的等主人：一定发", t["must"] and t["kind"] == "好友申请" and "瓜子" in t["facts"] and "交个朋友" in t["facts"]
      and "friend:20002" in so6.state["pending"], t)
check("卡片有名字、号码、验证信息、聊过几次", t["card"] == "好友申请 · 等你定\n瓜子（QQ 20002）\n验证信息：交个朋友\n不在她服务的群里；和她聊过 0 次", t["card"])
r = run(so6, so6.tool_requests(Ev(P2, bot=b6), "拉黑"))
check("别人叫的拉黑不做", r.startswith("没拉黑") and "friend:20002" in so6.state["pending"], r)
r = run(so6, so6.tool_requests(Ev(OWNER, bot=b6), "拉黑", "瓜子"))
check("主人说了拉黑", "20002" in so6.state["blacklist"] and "friend:20002" not in so6.state["pending"]
      and b6.done[-1] == ("ff2", "friend", False) and r.startswith("拉黑了瓜子（20002）的好友申请"), (r, b6.done))
run(so6, so6.on_event(Ev(P2, bot=b6, raw={"post_type": "request", "request_type": "friend", "user_id": 20002, "flag": "ff3"})))
check("拉黑的再申请直接拒掉、不打扰主人", b6.done[-1] == ("ff3", "friend", False) and len(told) == 2, told)
# 面板按的：讓她知道（記成後台的事）
so6.state["pending"]["friend:20003"] = {"type": "friend", "id": "20003", "name": "瓜子二号", "flag": "ff4", "ts": NOW}
done, fact = run(so6, so6.decide("friend:20003", "同意", b6, via="panel"))
check("面板同意了", done and fact == "同意了瓜子二号（20003）的好友申请" and b6.done[-1] == ("ff4", "friend", True), fact)
check("面板按的记一笔后台的事给她", any(k == "后台:好友申请" and "爹爹在面板同意了瓜子二号（20003）的好友申请" in t2 for _, t2, k in notes), notes)

# ---- 漏掉的：從 NapCat 撈回來；〈我〉的邀請 invitor 是〈我〉自己、actor 才是拉的人 ----
so3 = fresh()
rows = [
    {"request_id": SEQ(NOW - 120), "invitor_uin": int(ME), "group_id": 30001, "group_name": "浅梦", "checked": False, "actor": int(OWNER)},
    {"request_id": SEQ(NOW - 300), "invitor_uin": int(ME), "group_id": 30003, "group_name": "老群", "checked": True, "actor": int(OWNER)},
    {"request_id": SEQ(NOW - 9 * 86400), "invitor_uin": int(ME), "group_id": 30004, "group_name": "太旧", "checked": False, "actor": int(P1)},
    {"request_id": SEQ(NOW - 60), "invitor_uin": int(ME), "group_id": 30002, "group_name": "花生的群", "checked": False, "actor": int(P1)},
]
b3 = Bot(rows)
n = run(so3, so3._sync_invites(b3))
pend = so3.state["pending"]
check("补上两个", n == 2 and set(pend) == {"group:30001", "group:30002"}, (n, pend))
check("拉的人是 actor", pend["group:30001"]["inviter"] == OWNER and pend["group:30001"].get("her")
      and pend["group:30002"]["inviter"] == P1 and pend["group:30002"]["inviter_name"] == "花生", pend)
check("flag 是 request_id", pend["group:30001"]["flag"] == str(SEQ(NOW - 120)))
check("主人那个说是刚刚才看到", any("刚刚才看到" in t and "浅梦" in t for _, t, _ in notes), notes)
check("别人那个告诉主人时也说", told and "刚刚才看到" in told[-1]["facts"] and "刚刚才看到" in told[-1]["card"], told)
check("记录里标补上的", all(x.get("late") for x in events(so3) if x["kind"] == "group_invite"), events(so3))
check("再撈不重复", run(so3, so3._sync_invites(b3)) == 0 and len(told) == 1)
so3.state["pending"].clear()  # 過期丟掉的也不再撈回來
check("处理过的不再撈", run(so3, so3._sync_invites(b3)) == 0 and not so3.state["pending"])
so3.s.bot = None
check("QQ 没连上就不撈", run(so3, so3._sync_invites()) == 0)

# ---- 工具：別人只看得到自己的；同意別人的要主人說；主人拉的她自己定；拒絕她自己能做 ----
so4 = fresh()
b4 = Bot([rows[0], rows[3]])
so4.s.bot = b4
r = run(so4, so4.tool_requests(Ev(P2, bot=b4), "看"))
check("工具先撈一遍", "group:30001" in so4.state["pending"])
check("群友看不到别人的", r == "没有 TA 的申请在等", r)
r = run(so4, so4.tool_requests(Ev(P1, bot=b4), "看"))
check("群友看得到自己的", "花生的群" in r and "浅梦" not in r and "等爹爹决定" in r, r)
r = run(so4, so4.tool_requests(Ev(P1, bot=b4), "同意"))
check("别人叫的同意不做", r.startswith("没同意") and "爹爹" in r and b4.done == [], r)
r = run(so4, so4.tool_requests(Ev(OWNER, bot=b4), "看"))
check("主人看得到全部", "浅梦" in r and "进不进本鱼自己定" in r and "花生的群" in r, r)
r = run(so4, so4.tool_requests(Ev(OWNER, bot=b4), "同意"))
check("好几个在等要说哪个", r.startswith("好几个在等") and b4.done == [], r)
r = run(so4, so4.tool_requests(Ev(OWNER, bot=b4), "同意", "浅梦"))
check("主人拉的她同意了", b4.done == [(str(SEQ(NOW - 120)), "invite", True)] and "group:30001" not in so4.state["pending"]
      and r.startswith("同意了浅梦（30001）的群邀请") and "lively_serve_group" in r and "爹爹说了" in r, (b4.done, r))
d = events(so4)[-1]
check("记一笔她在聊天里同意的", d["kind"] == "group_decided" and d["action"] == "同意" and d["via"] == "chat" and d["by"] == OWNER
      and d["umo"] == f"x:FriendMessage:{OWNER}", d)
check("进群通知认得审批过", so4._decided_group("30001"))
told_before, notes_before = len(told), len(notes)
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_increase", "user_id": 10002, "self_id": 10002,
                                               "group_id": 30001, "operator_id": 10001}))
check("她在聊天里同意的，进群时不再告诉主人", len(told) == told_before, told[told_before:])
check("只在同意的那个聊天记一笔", len(notes) == notes_before + 1 and notes[-1][0] == f"x:FriendMessage:{OWNER}"
      and notes[-1][1] == "本鱼进了群 「浅梦」（30001）；这个群还不在本鱼服务的群里，那边的消息本鱼看不到", notes[-1:])
check("进群记录照记", events(so4)[-1]["kind"] == "joined")
r = run(so4, so4.tool_requests(Ev(P1, bot=b4), "不想去", "30002"))
check("拒绝她自己能做", b4.done[-1] == (str(SEQ(NOW - 60)), "invite", False) and r == "拒绝了花生的群（30002）的群邀请", (b4.done, r))
# 審批過的（她拒了 30002，QQ 那邊還是進了）：說不說她定
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_increase", "user_id": 10002, "self_id": 10002,
                                               "group_id": 30002, "operator_id": 20001}))
t = told[-1]
check("审批过的进群：说不说她定", not t["must"] and "进了群 「花生的群」（30002），花生（20001） 拉的（邀请审批过）" in t["facts"], t)
# 沒經過審批就進了：一定告訴主人（她的話＋一行後台）；已經在服務的群裡就不提
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_increase", "user_id": 10002, "self_id": 10002,
                                               "group_id": 30005, "operator_id": 20001}))
t = told[-1]
check("没经过审批的一定告诉主人", t["must"] and "没收到邀请让〈主人〉审批" in t["facts"]
      and t["card"].startswith("进了新群（没经过审批）：30005，花生（20001） 拉的") and "不在服务的群里" in t["card"], t)
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_increase", "user_id": 10002, "self_id": 10002,
                                               "group_id": 30009, "operator_id": 20001}))
check("已经服务的群不提服务", "服务的群" not in told[-1]["facts"] and "服务的群" not in told[-1]["card"], told[-1])
# 被踢：一定告訴主人；禁言：說不說她定
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_decrease", "sub_type": "kick_me", "user_id": 10002,
                                               "self_id": 10002, "group_id": 30001, "operator_id": 20001}))
check("被踢一定告诉主人", told[-1]["must"] and told[-1]["card"] == "被踢出群：「浅梦」（30001），花生（QQ 20001） 踢的", told[-1])
run(so4, so4._on_notice(Ev(OWNER, bot=b4), {"notice_type": "group_ban", "sub_type": "ban", "user_id": 10002,
                                               "self_id": 10002, "group_id": 30009, "operator_id": 20001, "duration": 600}))
check("禁言说不说她定", not told[-1]["must"] and "禁言了 10 分钟" in told[-1]["facts"] and "30009" in so4.state["muted"], told[-1])
r = run(so4, so4.tool_requests(Ev(OWNER, bot=b4), "看"))
check("主人问起时说最近处理过的（最近 5 件）", r.startswith("没有在等的申请。最近一天处理过的") and "拒绝花生的群（30002）的群邀请" in r
      and "进了群 30001" in r, r)
r = run(so4, so4.tool_requests(Ev(OWNER, bot=b4), "同意", "不存在"))
check("找不到", r.startswith("没有在等的申请"), r)

# QQ 那邊沒做成：留著，照實說
so5 = fresh()
so5.state["pending"]["group:30001"] = {"type": "group", "id": "30001", "name": "浅梦", "flag": "111", "inviter": OWNER, "ts": NOW, "her": True}
b5 = Bot(fail=True)
r = run(so5, so5.tool_requests(Ev(OWNER, bot=b5), "同意"))
check("没成留着", r.startswith("没同意成") and "group:30001" in so5.state["pending"] and events(so5)[-1]["done"] is False, r)

check("几分钟前", sm._ago(NOW - 30) == "刚刚" and sm._ago(NOW - 300) == "5 分钟前" and sm._ago(NOW - 7300) == "2 小时前")

print("all ok" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
