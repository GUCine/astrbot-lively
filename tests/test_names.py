"""名字固定用 QQ 暱稱、群名片按群記（bond，10-27）。

起因：bond 每條消息都拿 AstrBot 給的名字（群名片優先）蓋 people.name，主人在哪個群說話，後台就變成那個群的群名片
（「陈／5090-vision pro／小兔崽崽」）。現在名字讀原始消息的 sender.nickname，群名片記進 group_cards，
群裡說話時名片和暱稱不一樣才多給她一句。

/usr/local/bin/python3 tests/test_names.py（要有 PIL；號碼都是假的：10001 主人、2000x 群友、3000x 群）
"""
import sys, types, asyncio, time, importlib, tempfile
from pathlib import Path
# ---- stub astrbot（同 test_card_ask）----
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __init__(self): self.lines = []
    def info(self, m, *a, **k): self.lines.append(m)
    def __getattr__(self, k): return lambda *a, **k2: None
LOG = L()
class Dummy:
    def __init__(self, *a, **k): pass
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, on_agent_done=deco,
      on_decorating_result=deco, llm_tool=deco, command=deco, after_message_sent=deco, permission_type=deco,
      PermissionType=types.SimpleNamespace(ADMIN=0), EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=LOG, AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", At=Dummy, Image=Dummy, Plain=Dummy, Reply=Dummy)
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
OWNER, A, B, BOT = "10001", "20001", "20002", "99999"
G1, G2, G3 = "30001", "30002", "30003"
core.OWNERS.clear(); core.OWNERS.add(OWNER)
store = core.BondStore(str(Path(tempfile.mkdtemp()) / "bond.db"))
hs = heart.HeartStore(store.db)
store.set_meta(bm.MODE_KEY, "active")

bond = bm.LivelyBond.__new__(bm.LivelyBond)
bond.store, bond.heart, bond.rel = store, hs, rel.Relations(store, hs)
bond._sync_owners = lambda: None
bond._shared_umo = {}
bond._card_busy = set()
class BS:
    conf = {"mention_people": False, "card_auto": False}
    def groups(self): return [G1, G2, G3]
    def get(self, k, d=None): return self.conf.get(k, d)
    def fill(self, t): return t.replace("〈主人〉", "爹爹").replace("〈我〉", "本鱼")
    def remember_self(self, e): pass
bond.s = BS()

class Ev:
    def __init__(self, sender, text="在吗", group=G1, nick=None, card=None, shown="", raw=True):
        self.sender, self.message_str, self.group, self.shown = sender, text, group, shown
        s = {"user_id": int(sender)}
        if nick is not None:
            s["nickname"] = nick
        if card is not None:
            s["card"] = card
        self.message_obj = types.SimpleNamespace(message=[], message_id=1, raw_message={"sender": s} if raw else {})
        self.unified_msg_origin = f"x:GroupMessage:{group}" if group else f"x:FriendMessage:{sender}"
        self.extra = {}
    def get_sender_id(self): return self.sender
    def get_sender_name(self): return self.shown  # AstrBot 給的：群名片優先
    def get_self_id(self): return BOT
    def get_group_id(self): return self.group
    def get_messages(self): return []
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, d=None): return self.extra.get(k, d)
class Req:
    def __init__(self): self.extra_user_content_parts = []
def run(c): return asyncio.run(c)
def note(e):
    req = Req(); run(bond.inject(e, req))
    return "\n".join(p.text for p in req.extra_user_content_parts if "<bond_note>" in p.text)

# ---- 主人在三個群用三個群名片：名字一直是暱稱，群名片按群記 ----
run(bond.seen(Ev(OWNER, group=G1, nick="陈", card="小兔崽崽", shown="小兔崽崽")))
assert store.get(OWNER)["name"] == "陈", store.get(OWNER)
run(bond.seen(Ev(OWNER, group=G2, nick="陈", card="5090-vision pro", shown="5090-vision pro")))
run(bond.seen(Ev(OWNER, group=G3, nick="陈", card="", shown="陈")))
assert store.get(OWNER)["name"] == "陈"
assert store.cards_of(OWNER) == {G2: "5090-vision pro", G1: "小兔崽崽"}, store.cards_of(OWNER)
assert store.card_in(OWNER, G1) == "小兔崽崽" and store.card_in(OWNER, G3) == ""
assert bond.rel.card_in(OWNER, G2) == "5090-vision pro" and bond.rel.cards(OWNER) == store.cards_of(OWNER)
# 私聊沒有群名片：名字照舊、群名片不動
run(bond.seen(Ev(OWNER, group=None, nick="陈", shown="陈")))
assert store.get(OWNER)["name"] == "陈" and len(store.cards_of(OWNER)) == 2
# 群名片改了就換；改回不設就刪掉那行
run(bond.seen(Ev(OWNER, group=G1, nick="陈", card="大兔子", shown="大兔子")))
assert store.card_in(OWNER, G1) == "大兔子"
run(bond.seen(Ev(OWNER, group=G1, nick="陈", card="", shown="陈")))
assert store.card_in(OWNER, G1) == "" and G1 not in store.cards_of(OWNER)
run(bond.seen(Ev(OWNER, group=G1, nick="陈", card="小兔崽崽", shown="小兔崽崽")))

# ---- 原始消息裡沒有暱稱：退回 AstrBot 給的名字；QQ 號不蓋掉已知的名字；沒有 card 欄不動群名片 ----
run(bond.seen(Ev(A, group=G1, shown="小凛", raw=False)))
assert store.get(A)["name"] == "小凛" and store.cards_of(A) == {}
run(bond.seen(Ev(A, group=G1, nick="", shown=A)))
assert store.get(A)["name"] == "小凛"
run(bond.seen(Ev(A, group=G1, nick="凛凛子", card="小凛", shown="小凛")))
assert store.get(A)["name"] == "凛凛子" and store.card_in(A, G1) == "小凛"
# 群名片寫成 QQ 號的不記
run(bond.seen(Ev(B, group=G2, nick="月", card=B, shown=B)))
assert store.card_in(B, G2) == "" and store.get(B)["name"] == "月"

# ---- 說話時給她的那句：群名片和暱稱不一樣才多一句 ----
n = note(Ev(OWNER, "在吗", group=G1, nick="陈", card="小兔崽崽", shown="小兔崽崽"))
assert "群名片是「小兔崽崽」" in n, n
n = note(Ev(OWNER, "在吗", group=G3, nick="陈", card="", shown="陈"))
assert "群名片" not in n, n
n = note(Ev(OWNER, "在吗", group=None, nick="陈", shown="陈"))
assert "群名片" not in n, n
# 原始消息沒帶 card：用記下的
n = note(Ev(OWNER, "在吗", group=G2, nick="陈", shown="5090-vision pro"))
assert "群名片是「5090-vision pro」" in n, n
# 說話過後名字照舊是暱稱（印象卡、面板讀的都是它）
assert store.get(OWNER)["name"] == "陈"

print("ok: 名字用 QQ 昵称、群名片按群记")
