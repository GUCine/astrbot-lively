"""形象工具「看」寫 group：列出那個群裡誰有形象（10-30 她挑小凛群有形象的人，只能一個個 QQ 問，漏了布丁）。

/usr/local/bin/python3 tests/test_avatar_group.py（號碼都是假的：10001 主人、20001 群、3000x 群友）
"""
import asyncio, importlib, json, sys, tempfile, time, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco, command=deco, on_agent_done=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
TMP = Path(tempfile.mkdtemp())
class Plain: pass
class Chain:
    def __init__(self): self.chain = []
    def message(self, t): self.chain.append(("text", t)); return self
    def file_image(self, p): self.chain.append(("img", p)); return self
    def url_image(self, u): self.chain.append(("url", u)); return self
class TP:
    def __init__(self, text): self.text = text
    def mark_as_temp(self): return self
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Plain=Plain)
class Star:
    def __init__(self, context=None): self.context = context
class StarTools:
    @staticmethod
    def get_data_dir(name): p = TMP / name; p.mkdir(parents=True, exist_ok=True); return p
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=StarTools)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("astrbot.core.agent"); mod("astrbot.core.agent.message", TextPart=TP)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Chain)
mod("aiohttp")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
cm = importlib.import_module("astrbot_plugin_lively_comic.main")
cm.SEND_GAP = 0  # 各群排隊發的間隔，測試裡不等
lc = importlib.import_module("astrbot_plugin_lively_comic.lively_common")
av = importlib.import_module("astrbot_plugin_lively_comic.avatar")


class Phone:
    made_recs = {"30001": {"file": "a.png", "desc": "x", "ts": 1, "count": 1},
                 "30002": {"file": "b.png", "desc": "y", "ts": 1, "source": "qq"},
                 "10001": {"file": "o.png", "desc": "", "preset": True}}
    def made(self, qq): return self.made_recs.get(qq)
    def avatars(self): return {"made": {k: v for k, v in self.made_recs.items() if k != "10001"}}


members = [{"user_id": 10001, "card": "爹爹"}, {"user_id": 30001, "card": "", "nickname": "祈"},
           {"user_id": 30002, "card": "西瓜头"}, {"user_id": 30003, "nickname": "垂耳兔"}]
calls = []
async def call_action(action, **kw):
    calls.append((action, kw)); return members
client = types.SimpleNamespace(api=types.SimpleNamespace(call_action=call_action))
s = types.SimpleNamespace(client=lambda: client, fill=lambda t: t.replace("〈主人〉", "主人"))
p = types.SimpleNamespace(phone=Phone(), s=s, _gname=lambda g: "小凛群",
                          _find_group=lambda t: ("20001", "") if t in ("20001", "小凛") else ("", "没有这个群"))
a = av.Avatars(p)
ev = types.SimpleNamespace(get_sender_id=lambda: "10001")
out = asyncio.run(a.run(ev, "看", group="小凛"))
assert calls == [("get_group_member_list", {"group_id": 20001})]
assert out.startswith("群「小凛群」（20001）4 个人里有形象的："), out
assert "· 定做的：爹爹（10001，主人，用素材里主人的样子）、祈（30001）" in out, out
assert "· 照 QQ 头像先做的（TA 自己还没定做）：西瓜头（30002）" in out, out
assert "垂耳兔" not in out
assert asyncio.run(a.run(ev, "看", group="别的")) == "没有这个群"
# 不寫 group 照舊查一個人
assert asyncio.run(a.run(ev, "看", qq="30003")).startswith("QQ 30003 没有定做的形象")
members[:] = [{"user_id": 30003}]
assert asyncio.run(a.run(ev, "看", group="20001")).endswith("没有人有形象，画到谁都照 TA 的 QQ 头像画")
print("avatar group ok")
