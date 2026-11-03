"""群漫畫取話題前看圖、分鏡給原話（10-31）：照桐群那天的樣子（人均收入的圖 13:47、基金全綠 14:14 被併成一個話題）。

/usr/local/bin/python3 tests/test_comic_see.py（號碼都是假的：30001 小兔崽崽、30002 day3、30003 阳光、30004 黄金、99999 她）
"""
import asyncio, importlib, sys, tempfile, time, types
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
see = importlib.import_module("astrbot_plugin_lively_comic.see")

T0 = time.mktime(time.strptime("2026-10-31 13:46", "%Y-%m-%d %H:%M"))
C = lambda kind, url="": types.SimpleNamespace(type=types.SimpleNamespace(value=kind), url=url)
def M(mid, sec, qq, name, text="", img="", reply=None, at=""):
    at_c = (types.SimpleNamespace(type=types.SimpleNamespace(value="at"), url="", at_user_id=at),) if at else ()
    return types.SimpleNamespace(message_id=mid, timestamp=int(T0 + sec), sender_id=qq, sender_name=name, sender_card=None,
                                 text_content=text, contents=at_c + ((C("image", img),) if img else ()) + ((C("text"),) if text else ()),
                                 reply_to_id=reply)
raw = [M("1", 0, "30001", "小兔崽崽", "24w？？？"), M("2", 8, "30001", "小兔崽崽", img="http://img/income"),
       M("3", 20, "30001", "小兔崽崽", "人均2w收入吗..."), M("4", 35, "30001", "小兔崽崽", "上限拉这么高"),
       M("5", 500, "30002", "day3", "是互联网行业", reply="2"), M("6", 600, "30002", "day3", "软件开发没那么低"),
       M("7", 610, "30004", "黄金", img="http://img/meme"),
       *[M(f"f{i}", 700 + i * 90, "30005", "张顺平", t) for i, t in enumerate(
           ["叶问2没虚化之后好打太多了", "技能树卡得真死", "完全没有选择空间", "其实是游戏流程", "红房子啥时候开",
            "主板保护了", "这玩意是干啥的", "下一个图的支线吧", "湖心那里", "地下500米"])],
       M("8", 1680, "30003", "阳光", "今天我的基金全绿的"), M("9", 1690, "30004", "黄金", "你别玩了", at="30005"),
       M("10", 1695, "30004", "黄金", "你玩不明白的"), M("11", 1740, "30003", "阳光", "还是老实放余额宝得了")]
items = see.pick(raw, set())
assert items[0][0] == "2", items                                          # 被引用、接話多的那張排最前
assert "1" not in [i[0] for i in items]                                   # 沒圖的不算
descs = {"2": "互联网行业收入统计表，人均月收入2万，上限24万"}
lines = see.chat_lines(raw, descs, set())
assert any("[图片：互联网行业收入统计表" in x["text"] for x in lines) and any(x["text"] == "[图片]" for x in lines)
leg = see.legacy_images(items, descs)
assert leg[0]["message"][0]["data"]["text"].startswith("[图片：") and leg[0]["sender"]["user_id"] == "30001"
said = see.topic_chat(lines, "基金亏损与互联网薪资 小兔崽崽看到人均2w收入，阳光基金全绿", {"30001", "30003"}, lambda q, n: n)
print(said)
assert "人均2w" in said and "基金全绿" in said and "……" in said           # 兩段分開、中間隔開
assert said.index("13:4") < said.index("……") < said.index("14:14")
assert "黄金：@张顺平 你别玩了" in said and "day3：（回 小兔崽崽）是互联网行业" in said   # @ 誰、回誰都留著

# 分鏡的話題下面帶原話
class Prov:
    async def text_chat(self, prompt, system_prompt):
        Prov.prompt, Prov.system = prompt, system_prompt
        return types.SimpleNamespace(completion_text='{"cast": [], "strips": [{"title": "t", "panels": [{"scene": "x", "who": []}]}]}')
class S:
    def get(self, k, d=None): return d
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹").replace("〈名字〉", "小肥鱼")
    def is_owner(self, qq): return False
    def bot_qq(self): return "99999"
    def persona_prompt(self): return ""
    def provider(self, key="provider_id"): return Prov()
c = cm.LivelyComic.__new__(cm.LivelyComic)
c.s, c.phone = S(), None
c._made_zh = lambda qq: (False, "")
topics = [{"topic": "基金亏损与互联网薪资", "detail": "小兔崽崽看到人均2w收入，阳光基金全绿", "contributors": ["小兔崽崽", "阳光"],
           "contributor_ids": ["30001", "30003"]}]
cast = [{"qq": "30001", "call": "小兔崽崽", "name": "小兔崽崽", "n": 9}, {"qq": "30003", "call": "阳光", "name": "阳光", "n": 3}]
asyncio.run(c._storyboard(topics, cast, chat=lines))
assert "相关的原话" in Prov.prompt and "[图片：互联网行业收入统计表" in Prov.prompt and "14:14 阳光：今天我的基金全绿的" in Prov.prompt
assert "不相干的别硬接成一件事" in Prov.system
print("comic see ok")

# 白天邊收邊看（10-31 晚）：收到的圖排隊、背景看完記下；晚上全部用上，只補看沒看過的
ev = lambda segs, mid="m1": types.SimpleNamespace(message_obj=types.SimpleNamespace(raw_message={"message": segs}, message_id=mid))
assert see.live_images(ev([{"type": "image", "data": {"url": "http://q/a", "sub_type": 0}}])) == [("m1", "http://q/a")]
assert see.live_images(ev([{"type": "image", "data": {"url": "http://q/a", "sub_type": 1}}])) == []          # 表情包
assert see.live_images(ev([{"type": "image", "data": {"url": "https://gxh.vip.qq.com/x"}}])) == []           # 商城表情
assert see.live_images(ev([{"type": "text", "data": {"text": "hi"}}])) == []
plug = types.SimpleNamespace(dir=TMP, s=S())
w = see.Watcher(plug)
async def fake_one(prov, mid, url): return f"看了{url}"
w.seer._one = fake_one
async def day():
    w.offer("m1", "http://q/a"); w.offer("m2", "http://q/b")
    t = asyncio.ensure_future(w.run())
    await asyncio.sleep(0.1)
    t.cancel()
see.WATCH_GAP = 0
asyncio.run(day())
assert w.seer.known(["m1", "m2", "m3"]) == {"m1": "看了http://q/a", "m2": "看了http://q/b"} and w.n == 2
assert see.Seer(plug).known(["m1"]) and (TMP / "seen_imgs.json").exists()
w.offer("m1", "http://q/a"); assert w.q.empty()                                  # 看過的不再排
print("comic watch ok")
