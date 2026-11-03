"""gate 的傾聽（按人學節奏）、停頓提醒、沉默時再說一句，以及聊天外發出去的通知帶回對話：stub 掉 astrbot 直接跑。

python3 tests/test_rhythm.py（號碼都是假的：10001 主人、20001 群、30001 群友）
"""
import asyncio, importlib, json, sys, tempfile, time, types
from pathlib import Path

TMP = tempfile.mkdtemp()


# ---- stub astrbot ----
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
class Dummy:
    def __init__(self, *a, **k): pass
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, on_agent_done=deco,
      on_decorating_result=deco, llm_tool=deco, command=deco, after_message_sent=deco,
      EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
class Plain:
    def __init__(self, text): self.text = text
class At:
    def __init__(self, qq): self.qq = qq
class Image:
    def __init__(self, url="u"): self.url = url
mod("astrbot.api.message_components", At=At, Image=Image, Plain=Plain, Reply=Dummy)
class MessageChain:
    def __init__(self): self.chain = []
    def message(self, t): self.chain.append(Plain(t)); return self
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=MessageChain, ResultContentType=Dummy)
class Star:
    def __init__(self, context=None): self.context = context
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=types.SimpleNamespace(get_data_dir=lambda n: Path(TMP) / n))
mod("astrbot.core"); mod("astrbot.core.agent")
class TextPart:
    def __init__(self, text): self.text = text; self.temp = False
    def mark_as_temp(self): self.temp = True; return self
mod("astrbot.core.agent.message", TextPart=TextPart)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: TMP)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

g = importlib.import_module("astrbot_plugin_lively_gate.main")
rh = importlib.import_module("astrbot_plugin_lively_gate.rhythm")
lc = importlib.import_module("astrbot_plugin_lively_gate.lively_common")
assert lc.OUTBOX == Path(TMP) / "plugin_data" / "astrbot_plugin_lively_gate" / "outbox.jsonl"

DM = "aiocqhttp:FriendMessage:10001"


class Ev:
    def __init__(self, text, umo=DM, sender="10001", group="", wake=True, comps=None):
        self.message_obj = types.SimpleNamespace(message=list(comps or [Plain(text)]), raw_message=None)
        self.message_str = text
        self.is_at_or_wake_command = wake
        self.unified_msg_origin = umo
        self.sender, self.group = sender, group
        self.stopped = False
        self.extra = {}
    def get_sender_id(self): return self.sender
    def get_self_id(self): return "10002"
    def get_group_id(self): return self.group
    def get_sender_name(self): return "陈"
    def get_messages(self): return self.message_obj.message
    def stop_event(self): self.stopped = True
    def is_stopped(self): return self.stopped
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, default=None): return self.extra.get(k, default)


# ---- 節奏 ----
r = rh.Rhythm(Path(TMP) / "r1.json")
assert r.gap("x") == (rh.DEFAULT_GAP, False)
w_stranger = r.wait_for("x", "我跟你说个事")
assert rh.WAIT_MIN <= w_stranger <= rh.WAIT_MAX
assert r.wait_for("x", "你在吗？") < w_stranger < r.wait_for("x", "我妈妈她。。。")
assert r.wait_for("x", "心里难受") > w_stranger  # 很短，多半還有下文
t0 = 1000.0
for i in range(10):  # 這個人打字慢，連發隔 5 秒
    r.on_message(DM, "slow", t0 + i * 5)
assert r.gap("slow") == (5.0, True)
assert r.wait_for("slow", "我跟你说个事") > w_stranger
r.on_message(DM, "slow", t0 + 200)  # 隔太久不算連發
assert r.gap("slow")[0] == 5.0
# 私聊回〈我〉的時間
for i in range(5):
    r.on_bot_sent(DM, t0 + 1000 + i * 100)
    r.on_message(DM, "slow", t0 + 1000 + i * 100 + 30, dm=True)
assert r.lag("slow") == (30.0, True)
assert r.silence_after("slow", 4, 90, 900) == 120
assert r.silence_after("nobody", 4, 90, 900) == rh.DEFAULT_LAG * 4
r.maybe_save(force=True)
assert json.loads((Path(TMP) / "r1.json").read_text())["slow"]["l"][-1] == 30.0
assert rh.Rhythm(Path(TMP) / "r1.json").gap("slow") == (5.0, True)
assert rh.looks_unfinished("我妈妈她。。。") and rh.looks_unfinished("然后") and not rh.looks_unfinished("谢谢你")
assert rh.looks_heavy("她离开了我") and not rh.looks_heavy("今天吃了白饭")

# 停頓提醒
h = rh.pause_hints(r, "slow", [(0, "我遇到了点事情"), (30, "我妈妈她。。。")], 40)
assert any("2 条" in x for x in h) and any("停了 30 秒" in x for x in h) and any("没说完" in x for x in h), h
h = rh.pause_hints(r, "slow", [(0, "我遇到了点事情"), (6, "怎么说呢")], 10)
assert not any("停了" in x for x in h), h  # 6 秒對這個人（平時 5 秒）不算慢
assert rh.pause_hints(r, "x", [(0, "小肥鱼")], 5, "小肥鱼")[0].startswith("（TA 只喊了你一声")
assert rh.pause_hints(r, "x", [(0, "今天好热")], 3) == []
print("rhythm ok")


# ---- 傾聽：心里难受 / 才提的车 合成一條 ----
class Ctx:
    def __init__(self):
        self.sent = []; self.prov = None
        self.conversation_manager = CM()
    def get_config(self, umo=None): return {"wake_prefix": []}
    def get_using_provider(self, umo=None): return self.prov
    async def send_message(self, umo, chain): self.sent.append((umo, chain.chain[0].text)); return True
class CM:
    def __init__(self):
        self.pairs = []
        self.history = [{"role": "user", "content": [{"type": "text", "text": "心里难受\n才提的车"}]},
                        {"role": "assistant", "content": "才提的车呀……那心里肯定堵得慌"},
                        {"role": "user", "content": "<system_reminder>别管这句</system_reminder>"}]
    async def get_curr_conversation_id(self, umo): return "cid"
    async def get_conversation(self, umo, cid): return types.SimpleNamespace(history=json.dumps(self.history))
    async def add_message_pair(self, cid, u, a): self.pairs.append((u, a))


def new_gate(cfg=None):
    gate = g.LivelyGate.__new__(g.LivelyGate)
    gate.context = Ctx(); gate.cfg = cfg or {}
    gate.s = types.SimpleNamespace(fill=lambda t: t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹"), groups=lambda: ["20001"],
                                   persona_prompt=lambda: "你是小肥鱼。", bot_name=lambda: "小肥鱼")
    gate.name = "小肥鱼"
    gate.ignored = set(); gate._calls = {}; gate._late = {}; gate._caption_orig = None
    gate._listening = {}
    gate.rhythm = rh.Rhythm(Path(tempfile.mkdtemp()) / "rhythm.json")
    gate._outbox_seen = {}; gate._outbox_file = Path(tempfile.mkdtemp()) / "seen.json"
    gate._arm = {}; gate._watch = {}; gate._silence_count = {}
    return gate


class Fast(rh.Rhythm):
    """等待縮成十分之一，測試跑得快"""
    def wait_for(self, qq, text): return super().wait_for(qq, text) / 10


g.MAX_LISTEN = 1.5


async def dm_merge():
    gate = new_gate()
    gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    a = Ev("心里难受")
    gate._on_any_message(a, (DM, "10001"))
    task = asyncio.create_task(gate._listen(a, "10001", True))
    await asyncio.sleep(0.4)  # 線上 4 秒：「心里难受」很短，會等到
    b = Ev("才提的车")
    gate._on_any_message(b, (DM, "10001"))
    await gate._listen(b, "10001", True)
    await task
    return a, b

a, b = asyncio.run(dm_merge())
assert b.stopped and not a.stopped and a.message_str == "心里难受\n才提的车", a.message_str
assert any("连着发了 2 条" in x for x in a.extra["lively_rhythm_hints"])


async def dm_alone():
    """說完了的話不會被拖太久"""
    gate = new_gate(); gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    e = Ev("今天吃什么好呢？")
    t = time.monotonic(); await gate._listen(e, "10001", True)
    return e, time.monotonic() - t

e, took = asyncio.run(dm_alone())
assert e.message_str == "今天吃什么好呢？" and took < 0.3 and "lively_rhythm_hints" not in e.extra, took


async def dm_unfinished():
    gate = new_gate(); gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    e = Ev("我妈妈她。。。")
    await gate._listen(e, "10001", True)
    req = types.SimpleNamespace(prompt=e.message_str, extra_user_content_parts=[], contexts=[])
    await gate.sticker_hint(e, req)
    return req

req = asyncio.run(dm_unfinished())
assert any("没说完" in p.text and p.temp for p in req.extra_user_content_parts)


# 群裡：只有叫了她的那個人接著說才合併；空 @ 等過的不再等
async def group_case():
    gate = new_gate(); gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    G = "aiocqhttp:GroupMessage:20001"
    a = Ev("小肥鱼你看", umo=G, sender="30001", group="20001")
    task = asyncio.create_task(gate._listen(a, "30001", False))
    await asyncio.sleep(0.05)
    other = Ev("哈哈", umo=G, sender="30009", group="20001", wake=False)
    await gate._listen(other, "30009", False)
    more = Ev("这个好不好笑", umo=G, sender="30001", group="20001", wake=False)
    await gate._listen(more, "30001", False)
    await task
    waited = Ev("在吗", umo=G, sender="30002", group="20001"); waited.set_extra("lively_call_waited", True)
    t = time.monotonic(); await gate._listen(waited, "30002", False)
    return a, other, more, time.monotonic() - t

a, other, more, took = asyncio.run(group_case())
assert not other.stopped and more.stopped and a.message_str == "小肥鱼你看\n这个好不好笑" and took < 0.05
print("listen ok")


# ---- 聊天外發出去的通知 ----
gate = new_gate()
lc.note_outbox(DM, "有人想加本鱼好友～\n花生（QQ 30005）\n验证信息：我是花生", "好友申请")
lc.note_outbox(DM, "本鱼进了新群「花生的群」（20009），花生（30005）拉的（这次没收到邀请让本鱼审批，QQ 那边直接就进了）", "进了新群")
lc.note_outbox("aiocqhttp:FriendMessage:30005", "别人的", "打招呼")
e = Ev("这个群聊怎么直接就进了？")
req = types.SimpleNamespace(prompt=e.message_str, extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(e, req))
parts = [p for p in req.extra_user_content_parts if "自动发出过" in p.text]
assert len(parts) == 1 and not parts[0].temp, [p.text for p in req.extra_user_content_parts]
assert "［好友申请］有人想加本鱼好友～ / 花生" in parts[0].text and "［进了新群］" in parts[0].text and "别人的" not in parts[0].text
req = types.SimpleNamespace(prompt="嗯", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯"), req))
assert not any("自动发出过" in p.text for p in req.extra_user_content_parts)  # 看過的不再帶
assert json.loads(gate._outbox_file.read_text())[DM] > 0
# 後台的事（kind「后台:…」）：另起一段，標明沒發給誰；佔位符到這裡才換（有的插件記的是沒換過的）
lc.note_outbox(DM, "〈主人〉在面板同意了花生（30005）的好友申请", "后台:好友申请")
lc.note_outbox(DM, "本鱼自己通过了一个好友申请：瓜子（本鱼没私信爹爹）", "后台:好友申请")
lc.note_outbox(DM, "TA 刚加了〈我〉QQ 好友", "加好友")
req = types.SimpleNamespace(prompt="嗯？", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯？"), req))
text = "\n\n".join(p.text for p in req.extra_user_content_parts if "后台发生的事" in p.text)
sent_part, back_part = text.split("\n\n")
assert "自动发出过" in sent_part and "TA 刚加了本鱼QQ 好友" in sent_part and "后台" not in sent_part, sent_part
assert back_part.startswith("（这段时间本鱼这边后台发生的事，没发给谁，本鱼知道就行）"), back_part
assert "爹爹在面板同意了花生（30005）的好友申请" in back_part and "瓜子（本鱼没私信爹爹）" in back_part, back_part
assert "〈" not in text and "后台:" not in text, text  # 佔位符換掉了、鍵不給她看
print("outbox ok")

# ---- 心跳看手機時想說、沒發出去的（自主插件記的「没说出口」）：另起一段，同一件事只帶最新的、最多 3 條、6 小時以前的不帶 ----
def put(text, kind, ago=0):
    lc.note_outbox(DM, text, kind)
    rows = lc.tail_lines(lc.OUTBOX, 400)
    d = json.loads(rows[-1]); d["ts"] = round(time.time() + 1 - ago, 1); rows[-1] = json.dumps(d, ensure_ascii=False)
    lc.OUTBOX.write_text("\n".join(rows) + "\n", "utf-8")
put("本鱼看 QQ 时想回阿A的「旧的」：「很久以前」，没发出去（离上次太近）", "没说出口:r1", ago=7 * 3600)
put("本鱼看 QQ 时想回京城的「卡片呢」：「第一次想的」，没发出去（这一小时本鱼在这个群说得够多了）", "没说出口:r2")
put("本鱼看 QQ 时想回阿B的「在吗」：「在的」，没发出去（发送时出错了）", "没说出口:r3")
put("本鱼看 QQ 时想在这里说：「有人吗」，没发出去（这一小时做的事太多了）", "没说出口:g")
put("本鱼看 QQ 时想回京城的「卡片呢」：「第二次想的」，没发出去（这一小时本鱼在这个群说得够多了）", "没说出口:r2")
put("本鱼这边的日报发出去了", "日报")
req = types.SimpleNamespace(prompt="卡片呢", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("卡片呢"), req))
parts = [p for p in req.extra_user_content_parts if "没说出口" in p.text]
assert len(parts) == 1 and not parts[0].temp, [p.text for p in req.extra_user_content_parts]
t = parts[0].text
sent, missed = t.split("\n\n")
assert "自动发出过" in sent and "日报" in sent and "看 QQ" not in sent, t
assert missed.startswith("（本鱼看 QQ 时在这里想过、没说出口的，只有本鱼自己知道）"), missed
assert "第二次想的" in missed and "第一次想的" not in missed and "很久以前" not in missed, missed  # 同一件事只留最新；放久了不帶
assert missed.count("\n· ") == 3 and missed.index("在的") < missed.index("有人吗") < missed.index("第二次想的"), missed
assert "没说出口:" not in t  # 鍵不給她看
req = types.SimpleNamespace(prompt="嗯", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯"), req))
assert not any("没说出口" in p.text or "自动发出过" in p.text for p in req.extra_user_content_parts)  # 看過的不再帶
put("本鱼看 QQ 时想跟 TA 说：「晚安」，没发出去（TA 嫌本鱼烦）", "没说出口:p", ago=-1)
req = types.SimpleNamespace(prompt="嗯", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯"), req))
only = [p.text for p in req.extra_user_content_parts if "没说出口" in p.text]
assert len(only) == 1 and "自动发出过" not in only[0] and "「晚安」" in only[0], only  # 只有沒說出口的也帶
# 後來說出去了（自主插件補的「:done」）：之前那條不帶；之後又沒說成的照帶
put("本鱼看 QQ 时想回阿C的「吃了吗」：「吃了」，没发出去（离上次太近）", "没说出口:r9", ago=-2)
put("（后来说出去了）", "没说出口:r9:done", ago=-3)
put("本鱼看 QQ 时想回阿D的「睡了吗」：「没呢」，没发出去（离上次太近）", "没说出口:r10", ago=-4)
req = types.SimpleNamespace(prompt="嗯", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯"), req))
only = [p.text for p in req.extra_user_content_parts if "没说出口" in p.text]
assert len(only) == 1 and "「没呢」" in only[0] and "「吃了」" not in only[0] and "后来说出去了" not in only[0], only
# 心跳的心裡話寫了 about（自主插件記的「心里话」）：放在同一塊，只帶最新那句、一小時內的
put("本鱼看 QQ 时心里想：「很久以前想的」", "心里话", ago=2 * 3600)
put("本鱼看 QQ 时心里想：「京城那张卡片还没给」", "心里话", ago=-5)
put("本鱼看 QQ 时心里想：「算了先不管卡片」", "心里话", ago=-6)
req = types.SimpleNamespace(prompt="嗯", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(Ev("嗯"), req))
only = [p.text for p in req.extra_user_content_parts if "心里想" in p.text]
assert len(only) == 1 and only[0].startswith("（本鱼看 QQ 时在这里想过、没说出口的") and "算了先不管卡片" in only[0], only
assert "还没给" not in only[0] and "很久以前" not in only[0] and "自动发出过" not in only[0], only
print("missed outbox ok")


# ---- social：進了新群交給她告訴主人，帶群名、說清楚有沒有審批過；主人在面板審批的記一筆後台的事 ----
soc = importlib.import_module("astrbot_plugin_lively_social.main")
class Bot:
    async def get_group_info(self, group_id): return {"group_name": "花生的群"}
    async def get_stranger_info(self, user_id): return {"nickname": "花生"}
    async def set_friend_add_request(self, flag, approve): pass
class SS:
    def owner(self): return "10001"
    def private_umo(self, qq): return f"aiocqhttp:FriendMessage:{qq}"
    def owner_text(self, t): return t.replace("〈我〉", "本魚")
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def is_owner(self, qq): return str(qq) == "10001"
    def groups(self): return []
    def client(self): return None
told = []
async def fake_tell(s, facts, what, *, must=False, card="", image=None, kind=""):
    told.append((facts, what, must, card, kind)); return ""
soc.tell_owner = fake_tell
so = soc.LivelySocial.__new__(soc.LivelySocial)
so.s = SS(); so.context = Ctx(); so.dir = Path(tempfile.mkdtemp()); so.events_file = so.dir / "events.jsonl"
so.state_file = so.dir / "state.json"; so.state = {"pending": {}, "blacklist": [], "muted": {}, "new_friends": []}
so._tasks = set()
ev = types.SimpleNamespace(bot=Bot(), get_self_id=lambda: "10002")
async def notice():
    await so._on_notice(ev, {"notice_type": "group_increase", "user_id": 10002, "self_id": 10002,
                             "group_id": 20009, "operator_id": 30005})
    await asyncio.gather(*list(so._tasks))
asyncio.run(notice())
facts, what, must, card, kind = told[-1]
assert must and kind == "进了新群" and "「花生的群」（20009）" in facts and "花生（30005）" in facts and "没收到邀请" in facts, told
assert card.startswith("进了新群（没经过审批）：「花生的群」（20009）"), card
assert not so.context.sent  # 插件自己不發固定句
# 主人在面板審批：記一筆後台的事
so.state["pending"]["friend:30005"] = {"type": "friend", "id": "30005", "name": "花生", "flag": "f"}
done, fact = asyncio.run(so.decide("friend:30005", "同意", Bot(), via="panel"))
rows = [json.loads(x) for x in lc.tail_lines(lc.OUTBOX, 3)]
assert done and fact == "同意了花生（30005）的好友申请", fact
assert any(r["kind"] == "后台:好友申请" and "爹爹在面板同意了花生（30005）的好友申请" in r["text"] for r in rows), rows
assert rows[-1]["kind"] == "加好友" and rows[-1]["umo"].endswith(":30005"), rows  # TA 的私聊裡也記一筆
print("social ok")


# ---- 沉默時再說一句 ----
class Prov:
    def __init__(self, out): self.out = out; self.kw = None
    async def text_chat(self, **kw):
        self.kw = kw
        return types.SimpleNamespace(completion_text=self.out)

async def silence(mode, out, reply_in=None):
    gate = new_gate({"silence_followup": mode, "silence_min": 0.2, "silence_max": 0.2, "silence_quiet_hours": ""})
    gate.context.prov = Prov(out)
    e = Ev("她离开了我")
    gate._on_any_message(e, (DM, "10001"))
    gate._arm[DM] = {"qq": "10001", "ts": time.time()}
    await gate.on_sent(e)
    task = gate._watch.get(DM)
    if reply_in is not None:
        await asyncio.sleep(reply_in)
        gate._on_any_message(Ev("嗯"), (DM, "10001"))
    if task:
        try:
            await task
        except asyncio.CancelledError:
            pass
    return gate

gate = asyncio.run(silence("on", "……本鱼在呢，不想说也没关系，本鱼陪着你"))
assert gate.context.sent == [(DM, "……本鱼在呢，不想说也没关系，本鱼陪着你")]
kw = gate.context.prov.kw
assert kw["contexts"][0]["content"] == "心里难受\n才提的车" and len(kw["contexts"]) == 2  # 系統提醒去掉了
assert "你是小肥鱼。" in kw["system_prompt"] and "不说" in kw["system_prompt"]
assert gate.context.conversation_manager.pairs[0][1]["content"].startswith("……本鱼在呢")
gate = asyncio.run(silence("log", "你还好吗"))
assert gate.context.sent == []  # 只記錄
assert json.loads(lc.tail_lines(g.DATA_DIR / "silence.jsonl", 1)[0])["text"] == "你还好吗"
gate = asyncio.run(silence("on", "不说"))
assert gate.context.sent == []
gate = asyncio.run(silence("on", "你还好吗", reply_in=0.05))  # TA 回了：不用再說
assert gate.context.sent == [] and gate.context.prov.kw is None
gate = asyncio.run(silence("off", "你还好吗"))
assert gate.context.prov.kw is None
# 群裡、沒聊到難受的事都不等
gate = new_gate({"silence_followup": "on"})
asyncio.run(gate.on_sent(Ev("今天好热")))
assert not gate._watch
print("silence ok")
# ---- 10-29 00:25：先問一句，2 毫秒後到的轉發併進那句時整段丟了 ----
FWD = "[转发的聊天记录，2 条（旧→新）：陈：小肥鱼，偷拍一张你爹｜小肥鱼：拿什么拍呀]"

async def dm_forward_after():
    gate = new_gate()
    gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    a = Ev("以前不是能拍吗？现在怎么拍不了了")
    task = asyncio.create_task(gate._listen(a, "10001", True))
    await asyncio.sleep(0.05)
    b = Ev("", comps=[])  # 轉發本身沒有字，展開的在 extra 裡
    b.set_extra("lively_forward", [FWD])
    gate._forward_into_text(b)
    await gate._listen(b, "10001", True)
    await task
    return a, b

a, b = asyncio.run(dm_forward_after())
assert b.stopped and FWD in a.message_str and a.message_str.startswith("以前不是能拍吗"), a.message_str

async def dm_forward_first():
    gate = new_gate()
    gate.rhythm = Fast(Path(tempfile.mkdtemp()) / "r.json")
    a = Ev("", comps=[]); a.set_extra("lively_forward", [FWD]); gate._forward_into_text(a)
    task = asyncio.create_task(gate._listen(a, "10001", True))
    await asyncio.sleep(0.05)
    b = Ev("以前不是能拍吗")
    await gate._listen(b, "10001", True)
    await task
    return a

a = asyncio.run(dm_forward_first())
assert a.message_str == FWD + "\n以前不是能拍吗", a.message_str
# 沒轉發不動
e = Ev("hi"); new_gate()._forward_into_text(e); assert e.message_str == "hi"
print("forward listen ok")
print("all ok")
