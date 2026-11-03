"""印象卡先問她（bond card_ask）：語義認出在要卡，card_ask 開著只提醒、她自己調工具才發；關掉照舊直接發。

起因：10-25 她跟主人說印象卡「不经本鱼点头就出去了」。10-26 重放：提醒裡不寫明「光說喏卡不會出去」，
她偶爾只回「喏，自己看」不調工具。

/usr/local/bin/python3 tests/test_card_ask.py（要有 PIL；號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import sys, types, asyncio, time, importlib, tempfile
from pathlib import Path
# ---- stub astrbot ----
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __init__(self): self.lines = []
    def info(self, m, *a, **k): self.lines.append(m)
    def __getattr__(self, k): return lambda *a, **k2: None
LOG = L()
class Dummy:
    def __init__(self, *a, **k): pass
class At:
    def __init__(self, qq="", name=""): self.qq, self.name = qq, name
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, on_agent_done=deco,
      on_decorating_result=deco, llm_tool=deco, command=deco, after_message_sent=deco, permission_type=deco,
      PermissionType=types.SimpleNamespace(ADMIN=0), EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=LOG, AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", At=At, Image=Dummy, Plain=Dummy, Reply=Dummy)
mod("astrbot.api.star", Context=object, Star=Dummy, register=deco, StarTools=Dummy)
mod("astrbot.core"); mod("astrbot.core.agent")
class TextPart:
    def __init__(self, text): self.text = text; self.temp = False
    def mark_as_temp(self): self.temp = True; return self
mod("astrbot.core.agent.message", TextPart=TextPart)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Dummy, ResultContentType=Dummy)
mod("astrbot.core.star"); mod("astrbot.core.star.filter"); mod("astrbot.core.star.filter.command", GreedyStr=str)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
mod("aiohttp", ClientSession=Dummy, ClientTimeout=Dummy)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

core = importlib.import_module("astrbot_plugin_lively_bond.core")
heart = importlib.import_module("astrbot_plugin_lively_bond.heart")
rel = importlib.import_module("astrbot_plugin_lively_bond.relation")
bm = importlib.import_module("astrbot_plugin_lively_bond.main")
OWNER, A, BOT, GROUP = "10001", "20001", "99999", "30001"
core.OWNERS.clear(); core.OWNERS.add(OWNER)
store = core.BondStore(str(Path(tempfile.mkdtemp()) / "bond.db"))
hs = heart.HeartStore(store.db)
store.on_talk(A, "小凛", time.time() - 86400); store.db.commit()

bond = bm.LivelyBond.__new__(bm.LivelyBond)
bond.store, bond.heart, bond.rel = store, hs, rel.Relations(store, hs)
bond._sync_owners = lambda: None
bond._shared_umo = {}
bond._card_busy = set()
class BS:
    conf = {"mention_people": False}
    def groups(self): return [GROUP]
    def get(self, k, d=None): return self.conf.get(k, d)
    def fill(self, t): return t.replace("〈主人〉", "爹爹").replace("〈我〉", "本鱼")
bond.s = BS()
class Intent:
    hit, learned = True, []
    async def check(self, t): return (self.hit, 0.9)
    def add(self, t, yes=True, auto=False): self.learned.append(t); return t
bond.intent = Intent()
SENT = []
async def fake_send(event):
    SENT.append(event.message_str); return True, "印象卡发出去了"
bond._send_card = fake_send

class Ev:
    def __init__(self, sender, text, group=GROUP, segs=()):
        self.sender, self.message_str, self.group = sender, text, group
        self.message_obj = types.SimpleNamespace(message=list(segs), message_id=1, raw_message={})
        self.unified_msg_origin = f"x:GroupMessage:{group}" if group else f"x:FriendMessage:{sender}"
        self.extra = {}
    def get_sender_id(self): return self.sender
    def get_sender_name(self): return "小凛"
    def get_self_id(self): return BOT
    def get_group_id(self): return self.group
    def get_messages(self): return self.message_obj.message
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, d=None): return self.extra.get(k, d)
class Req:
    def __init__(self): self.extra_user_content_parts = []
def run(c): return asyncio.run(c)
def texts(req): return [p.text for p in req.extra_user_content_parts]

# ---- 預設（card_ask 開）：認出來只提醒，不發；提醒是臨時的、寫明光說喏不會出去 ----
e, req = Ev(A, "查看好感度"), Req()
run(bond.inject(e, req))
hint = [t for t in texts(req) if "印象卡" in t]
assert SENT == [] and len(hint) == 1, texts(req)
assert "lively_impression_card" in hint[0] and "喏" in hint[0] and "不想给" in hint[0] and "本鱼" in hint[0], hint
assert all(p.temp for p in req.extra_user_content_parts)
assert e.get_extra("lively_card_hinted") is True and e.get_extra("lively_card_done") is None
assert any("像在要印象卡" in l for l in LOG.lines)
# 她決定發：調工具才發；提醒過的不學成新例句
out = run(bond.share_card(e))
assert SENT == ["查看好感度"] and "发出去" in out and Intent.learned == [], (SENT, Intent.learned)
assert any("她决定发" in l for l in LOG.lines)

# ---- 沒認出來、她自己判斷出在要卡：照舊學 ----
SENT.clear(); Intent.hit = False
e, req = Ev(A, "给我也来一张"), Req()
run(bond.inject(e, req))
assert not any("印象卡" in t for t in texts(req)) and e.get_extra("lively_card_hinted") is None
run(bond.share_card(e))
assert SENT == ["给我也来一张"] and Intent.learned == ["给我也来一张"], Intent.learned

# ---- @ 了別人：不提醒 ----
SENT.clear(); Intent.hit = True; Intent.learned.clear()
e, req = Ev(A, "看看他的印象卡", segs=[At("20002")]), Req()
run(bond.inject(e, req))
assert not any("印象卡" in t for t in texts(req)) and SENT == []

# ---- card_ask 關：舊做法，認出來直接發，告訴她已經發了 ----
BS.conf["card_ask"] = False
e, req = Ev(A, "我的印象卡"), Req()
run(bond.inject(e, req))
assert SENT == ["我的印象卡"] and e.get_extra("lively_card_done") == "印象卡发出去了"
assert any("程序已经直接发出去了：印象卡发出去了" in t for t in texts(req)) and e.get_extra("lively_card_hinted") is None
assert not any(w in t for t in texts(req) for w in ("简短", "不要复述卡片", "说一句"))  # 只講事實，說什麼她定
out = run(bond.share_card(e))
assert "已经处理过" in out and "简短" not in out and SENT == ["我的印象卡"]  # 不會發第二張

# ---- card_auto 關：什麼都不做 ----
BS.conf.update(card_ask=True, card_auto=False); SENT.clear()
e, req = Ev(A, "查看好感度"), Req()
run(bond.inject(e, req))
assert not any("印象卡" in t for t in texts(req)) and SENT == []

print("ok: 印象卡先问她")
