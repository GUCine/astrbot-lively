"""群漫畫：QQ 頭像裡沒有能照著畫的人就不帶（10-31 爱丽丝的頭像是黑白風景，畫出來套了张顺平的樣子）。
每張頭像問一次看圖模型，記下來；定做過形象的不問；分鏡名單標「头像不是人」，樣子她定。

/usr/local/bin/python3 tests/test_comic_face.py（號碼都是假的：30001 爱丽丝、30002 张顺平、30003 有形象的）
"""
import asyncio, importlib, json, sys, tempfile, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco, command=deco, on_agent_done=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
TMP = Path(tempfile.mkdtemp())
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Plain=object)
class Star:
    def __init__(self, context=None): self.context = context
class StarTools:
    @staticmethod
    def get_data_dir(name): p = TMP / name; p.mkdir(parents=True, exist_ok=True); return p
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=StarTools)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("astrbot.core.agent"); mod("astrbot.core.agent.message", TextPart=object)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=object)
mod("aiohttp")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
cm = importlib.import_module("astrbot_plugin_lively_comic.main")
ph_mod = importlib.import_module("astrbot_plugin_lively_comic.phone")

ANS = {"30001": False, "30002": True}
asked = []
class Prov:
    async def text_chat(self, prompt, image_urls=None, system_prompt=None):
        qq = Path(image_urls[0]).stem
        asked.append(qq)
        return types.SimpleNamespace(completion_text='{"人物": %s}' % ("true" if ANS[qq] else "false"))
class S:
    def get(self, k, d=None): return {"look_provider_id": "look"}.get(k, d)
    def provider(self, key="provider_id"): return Prov()
    def is_owner(self, qq): return False
    def fill(self, t): return t.replace("〈我〉", "本鱼")
    def bot_qq(self): return "99999"

D = TMP / "comic"
(D / "avatars_meta" / "qq").mkdir(parents=True)
for q in ("30001", "30002", "30003"):
    (D / "avatars_meta" / "qq" / f"{q}.jpg").write_bytes(b"\xff\xd8" + q.encode() * 300)
plugin = types.SimpleNamespace(s=S(), dir=D)
ph = ph_mod.Phone(plugin)
ph.made = lambda qq: {"file": "x.png"} if str(qq) == "30003" else None

assert asyncio.run(ph.has_face("30001")) is False and asyncio.run(ph.has_face("30002")) is True
assert asyncio.run(ph.has_face("30003")) is None                        # 定做過形象的不問
assert asyncio.run(ph.has_face("30001")) is False and asked == ["30001", "30002"], asked   # 記下來了，不再問
(D / "avatars_meta" / "qq" / "30001.jpg").write_bytes(b"\xff\xd8" + b"new" * 400)       # 換了頭像就再問
ANS["30001"] = True
assert asyncio.run(ph.has_face("30001")) is True and asked[-1] == "30001"
ANS["30001"] = False
(D / "avatars_meta" / "qq" / "30001.jpg").write_bytes(b"\xff\xd8" + b"30001" * 300)

c = cm.LivelyComic.__new__(cm.LivelyComic)
c.s, c.phone, c.self_look, c.self_ref = S(), ph, "", None
c.me_ref = lambda: None
cast = [{"qq": "30001", "call": "爱丽丝", "name": "爱丽丝在树上", "n": 5},
        {"qq": "30002", "call": "张顺平", "name": "张顺平", "n": 9},
        {"qq": "30003", "call": "小明", "name": "小明", "n": 2}]
asyncio.run(c._judge_faces(cast))
assert cast[0].get("no_face") and not cast[1].get("no_face") and not cast[2].get("no_face"), cast
sb = {"cast": [{"称呼": "爱丽丝", "look": "long blonde twin tails"}, {"称呼": "张顺平", "look": ""}, {"称呼": "小明", "look": ""}],
      "panels": [{"scene": "x", "who": ["爱丽丝", "张顺平", "小明"]}]}
async def person(qq, call=""):
    return D / "avatars_meta" / "qq" / f"{qq}.jpg", f"avatar {call}"
ph.person = person
refs, idx = asyncio.run(c._comic_refs(sb, cast, False))
assert set(idx) == {"张顺平", "小明"} and len(refs) == 2, idx             # 爱丽丝不帶頭像
p, _ = c._comic_prompt(sb, cast, idx)
assert "- 爱丽丝: young chibi person, long blonde twin tails" in p        # 照分鏡寫的樣子畫
assert "头像不是人" in cm.STORYBOARD_RULE
print("comic face ok")

# 多把生圖 key 分通道（10-31）：每條通道同時最多 comic_lane_max 張，挑最空的；幾張一起畫，回的順序照分鏡
import time as _t
(D / "draw_keys.json").write_text(json.dumps([{"name": "通道2", "api_url": "https://x/v1", "api_key": "k2"}]), encoding="utf-8")
c.dir = D
c.s = types.SimpleNamespace(get=lambda k, d=None: {"comic_lane_max": 1}.get(k, d))
c._drawing_providers = lambda: [{"model": "gpt-image-2.5", "api_url": "https://x/v1", "api_key": "k1", "timeout": 600},
                                {"model": "gpt-image-2.5-flare", "api_url": "https://x/v1", "api_key": "k1"}]
lanes = c._draw_lanes()
assert [[(p["api_key"], p["model"]) for p in l] for l in lanes] == [
    [("k1", "gpt-image-2.5"), ("k1", "gpt-image-2.5-flare")], [("k2", "gpt-image-2.5"), ("k2", "gpt-image-2.5-flare")]]
used, live, peak = [], [0], [0]
async def call(p, prompt, ref, size):
    live[0] += 1; peak[0] = max(peak[0], live[0]); used.append((prompt, p["api_key"]))
    await asyncio.sleep(0.2)
    live[0] -= 1
    if p["api_key"] == "k2" and p["model"] == "gpt-image-2.5" and prompt == "b":
        raise RuntimeError("timed out")
    return prompt.encode()
c._call_images = call
c._draw_secs = {}
async def three():
    return await asyncio.gather(*(c._draw_any("g", x, None, "s") for x in "abc"))
assert asyncio.run(three()) == [b"a", b"b", b"c"] and peak[0] == 2, (peak, used)   # 兩條通道各一張，第三張等
assert ("b", "k2") in used and used.count(("b", "k2")) == 2                        # 通道2 的 2.5 不行換同一把的 flare
assert not any(c._lane_busy.values())
print("comic lanes ok")
