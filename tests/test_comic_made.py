"""群漫畫看圖、分鏡、修圖認得定做形象（10-28）：分鏡給祈瞎編了黑長髮，畫的時候照他的定做形象畫成綠髮（對的），
看圖時她只看到分鏡那句，把對的改成了錯的，被問又說「手里没他的样子」。現在：
分鏡名單帶上定做形象；看圖照實說誰照形象、誰照 QQ 頭像畫的；修圖時寫到的人帶上 TA 的形象圖。

/usr/local/bin/python3 tests/test_comic_made.py（號碼都是假的：10001 主人、20001 群、30001 祈、30002 西瓜头）
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
lc.OUTBOX = TMP / "outbox.jsonl"
G, OWNER = "20001", "10001"


class Prov:
    replies: list = []
    seen: list = []
    async def text_chat(self, prompt, system_prompt, image_urls=None):
        Prov.seen.append({"prompt": prompt, "system": system_prompt, "images": image_urls})
        r = Prov.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(completion_text=r)


class S:
    conf: dict = {}
    def get(self, k, d=None): return S.conf.get(k, d)
    def fill(self, t): return str(t).replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owner_text(self, t): return self.fill(t)
    def is_owner(self, qq): return str(qq) == OWNER
    def owner(self): return OWNER
    def private_umo(self, qq): return f"x:FriendMessage:{qq}"
    def group_umo(self, gid): return f"x:GroupMessage:{gid}"
    def persona_prompt(self): return "（人设）"
    def provider(self, key="provider_id"): S.used = key; return Prov()
    def platform_id(self): return "x"


SENT = []
async def send_message(umo, chain): SENT.append((umo, chain.chain))
def new():
    c = cm.LivelyComic.__new__(cm.LivelyComic)
    c.s, c.comic_at, c._names, c._sb = S(), "00:00", {G: "测试群", "20002": "第二群"}, {}
    c.dir = TMP / "comic"; c.dir.mkdir(exist_ok=True)
    c.state_file, c.events_file = c.dir / "state.json", c.dir / "events.jsonl"
    c.state = {"pending": {}, "inflight": {}, "enabled": True}
    c._locks, c._gen_sem, c._draw_secs = {}, None, {}
    c._redo, c._bg = {}, set()
    c._busy = cm._AnyLocked(c._locks)
    gda = types.SimpleNamespace(comic_command_handler=types.SimpleNamespace(
        config_manager=types.SimpleNamespace(get_enable_daily_comic=lambda: True)))
    c.context = types.SimpleNamespace(send_message=send_message, conversation_manager=None,
                                      get_registered_star=lambda n: types.SimpleNamespace(star_cls=gda))
    return c

QI, XG = "30001", "30002"
DESC = ("hair: 亮草绿的长碎发 / eyes: 紫红色 / face: 脸偏瘦 / body: 成年男性 / outfit: 深色带银纹的长衫 / "
        "accessories: 右耳银耳钉 / features: 背后白色羽翼 / vibe: 爱起哄")
AV = TMP / "qi.png"; AV.write_bytes(b"x"); QQAV = TMP / "xg.jpg"; QQAV.write_bytes(b"y")
class Phone:
    def made(self, qq): return {"file": str(AV), "desc": DESC} if qq == QI else None
    async def person(self, qq, call=""):
        return (AV, f"the character sheet of {call}") if qq == QI else (QQAV, f"the QQ avatar of {call}")
CAST = [{"call": "祈", "name": "祈", "qq": QI, "n": 5}, {"call": "西瓜头", "name": "西瓜头penguin", "qq": XG, "n": 3},
        {"call": "小凛", "name": "小凛🍥", "qq": "30003", "n": 2}]
SB = {"cast": [{"称呼": "祈", "look": "long black hair, white hairband"}, {"称呼": "西瓜头", "look": "short green hair"},
               {"称呼": "小凛", "look": "pink twin tails"}],
      "panels": [{"scene": "x", "who": ["祈", "西瓜头", "小凛"], "me": False, "lines": [{"who": "祈", "say": "在呢"}], "caption": "深夜"}]}

# 描述縮成一句
assert cm.made_brief(DESC) == "亮草绿的长碎发，紫红色，深色带银纹的长衫，右耳银耳钉，背后白色羽翼", cm.made_brief(DESC)
assert cm.made_brief("就是一只猫") == "就是一只猫" and len(cm.made_brief("字" * 200)) == 90

c = new(); c.phone = Phone()
# _comic_refs 記下誰照什麼畫的
sb = json.loads(json.dumps(SB))
refs, idx = asyncio.run(c._comic_refs(sb, CAST, False))
assert refs == [AV, QQAV, QQAV] and sb["_refs"] == {"祈": "made", "西瓜头": "qq", "小凛": "qq"}, sb["_refs"]

# 看圖：照形象畫的、照 QQ 頭像畫的照實說，分鏡瞎編的那句不給
sb["_refs"].pop("小凛")  # 沒帶參考圖的（超過張數）照分鏡寫的
c._sb[G] = (sb, CAST)
S.conf = {"storyboard_provider_id": "bg"}
IMG = TMP / "comic_20001.png"
from PIL import Image  # noqa: E402
Image.new("RGB", (100, 150)).save(IMG)
Prov.replies = ['{"看到的": "一格", "text": "", "私信爹爹": "", "why": "好"}']
asyncio.run(c._look(G, "今天", str(IMG), []))
pr = Prov.seen[-1]["prompt"]
assert f"名字牌「祈」（QQ {QI}）：照 TA 定做的形象画的（亮草绿的长碎发，" in pr and "long black hair" not in pr, pr
assert f"名字牌「西瓜头」（QQ {XG}）：照 TA 的 QQ 头像画的（头像本鱼这里看不到）" in pr and "short green hair" not in pr
assert "名字牌「小凛」（QQ 30003）：pink twin tails（分镜里写的，英文）" in pr
assert "以形象、头像为准" in pr and "不算画错" in pr
# 以前存下的分鏡沒有 _refs：有定做形象的照樣說是照形象畫的
c._sb[G] = (json.loads(json.dumps(SB)), CAST)
assert c._look_people(c._sb[G][0], CAST)[0].startswith(f"名字牌「祈」（QQ {QI}）：照 TA 定做的形象画的")
assert c._look_people(c._sb[G][0], CAST)[1] == f"名字牌「西瓜头」（QQ {XG}）：short green hair（分镜里写的，英文）"
# 沒有 phone（舊物件）也不出錯
c2 = new(); assert c2._look_people(SB, CAST)[0] == f"名字牌「祈」（QQ {QI}）：long black hair, white hairband（分镜里写的，英文）"

# 分鏡：名單帶定做形象，規矩寫明照形象寫 look
class SBProv:
    seen = None
    async def text_chat(self, prompt, system_prompt):
        SBProv.seen = (prompt, system_prompt)
        return types.SimpleNamespace(completion_text=json.dumps(SB, ensure_ascii=False))
S.provider = lambda self, key="provider_id": SBProv()
sb_new = asyncio.run(c._storyboard([], CAST))[0]
assert [x["look"] for x in sb_new["cast"]] == ["", "short green hair", "pink twin tails"], sb_new  # 有定做形象的 look 清空
p, sysp = SBProv.seen
assert "- 祈｜祈｜5｜有定做的形象" in p and "亮草绿" not in p and "- 西瓜头｜西瓜头penguin｜3\n" in p + "\n", p
assert "look 写空字符串" in sysp and "scene 里提到人一律用称呼" in sysp
S.provider = lambda self, key="provider_id": (setattr(S, "used", key), Prov())[1]

# 修圖：寫到的人帶上 TA 的形象（沒有就 QQ 頭像），沒寫到的不帶
got = {}
async def draw_any(gid, prompt, ref, size, measure=True):
    got.update(prompt=prompt, ref=ref); return b"\x89PNG...."
c._draw_any = draw_any
c._sb[G] = (sb, CAST)
asyncio.run(c._fix_draw(G, str(IMG), [], "修图", f"第3格搭手的人改成 QQ {QI} 的样子，名字牌还是祈", 1))
assert got["ref"] == [IMG, AV], got["ref"]
assert "Image 1 is the comic page to edit" in got["prompt"] and "Image 2: the character sheet of 祈." in got["prompt"]
asyncio.run(c._fix_draw(G, str(IMG), [], "修图", f"{QI}和{XG}的台词对调", 2))
assert got["ref"] == [IMG, AV, QQAV] and "Image 3: the QQ avatar of 西瓜头." in got["prompt"]
asyncio.run(c._fix_draw(G, str(IMG), [], "修图", "第一格的字歪了", 3))
assert got["ref"] == [IMG]
asyncio.run(c._fix_draw(G, str(IMG), [], "修图", "第一格祈的头发改短", 4))  # 只写名字牌上的字：不认（名字会变）
assert got["ref"] == [IMG] and "Image 1 is" not in got["prompt"]
# 舊分鏡（重畫時的 prev）：有定做形象的 look 也清空
S.provider = lambda self, key="provider_id": SBProv()
old = json.loads(json.dumps(SB)); asyncio.run(c._storyboard([], CAST, prev=old, change="x"))
assert old["cast"][0]["look"] == "" and old["cast"][1]["look"] == "short green hair" and "long black hair" not in SBProv.seen[0]
# 「写到的人会一起带给画图的」照實寫在能改的說明裡
assert "定做的形象（没有就 QQ 头像）会一起带给画图的" in cm.FIX_NOTE and "QQ 号或 QQ 昵称" in cm.FIX_NOTE and "不会用" in cm.FIX_NOTE
print("ok")
