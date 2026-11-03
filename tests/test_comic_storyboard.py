"""群漫畫自己的分鏡（10-25）：〈我〉定格數、出場的人標〈我〉起的稱呼、直式尺寸、只畫有〈我〉的格才帶參考圖。

/usr/local/bin/python3 tests/test_comic_storyboard.py（號碼都是假的：10001 主人、2000x 群友、99999 機器人）
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

SB = {"cast": [{"称呼": "小凛", "look": "pink twin tails, star hairclip"}, {"称呼": "冰山", "look": "short silver hair, glasses"},
               {"称呼": "路人甲", "look": "should be dropped"}],
      "panels": [{"scene": "Xiaofeiyu and Xiaolin argue over a rice bowl", "who": ["小凛", "本鱼"], "me": True,
                  "lines": [{"who": "本鱼", "say": "这碗是本鱼的"}, {"who": "小凛", "say": "写你名字了吗"}], "caption": "抢饭大战"},
                 {"scene": "Bingshan stares at a crashed computer", "who": ["冰山"], "me": False,
                  "lines": [{"who": "冰山", "say": "我的存档呢"}], "caption": "又死机了"},
                 {"scene": "everyone laughing", "who": ["小凛", "冰山"], "me": False, "lines": [], "caption": ""}]}


class Prov:
    reply = None
    queue: list = []  # 有東西就依序回（原樣，不加前綴）
    prompts: list = []
    async def text_chat(self, prompt, system_prompt):
        Prov.prompt, Prov.system = prompt, system_prompt
        Prov.prompts.append((prompt, system_prompt))
        if Prov.queue:
            return types.SimpleNamespace(completion_text=Prov.queue.pop(0))
        return types.SimpleNamespace(completion_text="好的\n" + (Prov.reply or json.dumps(SB, ensure_ascii=False)))


class Bond:
    def relation(self, qq):
        return {"heart": {"称呼": {"20001": "小凛"}.get(qq, "")}}


class S:
    look = ""
    def get(self, k, d=None): return {"comic_cast_max": 3, "comic_panels_max": 4, "comic_panels_min": 3, "comic_owner_look": S.look}.get(k, d)
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹").replace("〈名字〉", "小肥鱼")
    def is_owner(self, qq): return str(qq) == "10001"
    def bot_qq(self): return "99999"
    def persona_prompt(self): return "（人设）"
    def provider(self, key="provider_id"): return Prov()


c = cm.LivelyComic.__new__(cm.LivelyComic)
c.s, c.self_look, c.self_ref = S(), "a cute chibi whale girl ", None
c.context = types.SimpleNamespace(get_registered_star=lambda n: types.SimpleNamespace(star_cls=Bond()) if n.endswith("bond") else None)
topics = [{"topic": "抢饭", "contributors": ["小凛🍥"], "detail": "小凛和本鱼抢饭", "contributor_ids": ["20001", "99999"]},
          {"topic": "死机", "contributors": ["B級冰山"], "detail": "电脑死机", "contributor_ids": ["20002"]}]
talk = {"20001": [30, "小凛🍥"], "20002": [12, "B級冰山"], "10001": [40, "陈"], "20003": [3, "路人甲乙丙"], "99999": [50, "小肥鱼"]}

cast = c._cast(topics, talk)
assert [x["qq"] for x in cast] == ["20001", "20002", "10001"], cast            # 話題裡的人在前，再按說話多少；不含機器人；最多 3 個
assert [x["call"] for x in cast] == ["小凛", "B級冰山", "陈"], cast               # 有稱呼用稱呼；沒有用群名片前四個字；主人標群名片

# 撞名：〈我〉叫某個群友「陈」，主人群名片也是「陈」→ 那個群友換回群名片
class Bond2(Bond):
    def relation(self, qq): return {"heart": {"称呼": {"20001": "小凛", "20004": "陈"}.get(qq, "")}}
c.context = types.SimpleNamespace(get_registered_star=lambda n: types.SimpleNamespace(star_cls=Bond2()) if n.endswith("bond") else None)
cc = c._cast(topics, dict(talk, **{"20004": [60, "XChen446"]}))
assert {x["qq"]: x["call"] for x in cc}["20004"] == "XChen446", cc
c.context = types.SimpleNamespace(get_registered_star=lambda n: types.SimpleNamespace(star_cls=Bond()) if n.endswith("bond") else None)

cast[1]["call"] = "冰山"
sbs = asyncio.run(c._storyboard(topics, cast, most=2, why="今天还能画 10 张"))
sb = sbs[0]
assert len(sbs) == 1 and len(sb["panels"]) == 3 and "3～4 格" in Prov.system and "本鱼" in Prov.system and "〈我〉" not in Prov.system
assert "最多画 2 件（今天还能画 10 张）" in Prov.system and sb["cast"] == SB["cast"]   # 舊格式（沒有 strips）當成一張
assert "小凛｜小凛🍥｜30" in Prov.prompt and "20001" not in Prov.prompt and "抢饭（小凛、本鱼）" in Prov.prompt         # 不給模型 QQ 號；〈我〉照 QQ 號認（10-31）

prompt, with_me = c._comic_prompt(sb, cast)
assert with_me and "3 wide panels" in prompt and "4-koma" in prompt and "vertical comic page" in prompt and "written vertically" in prompt
assert 'name tag above the head with exact Chinese text "小凛"' in prompt and '"冰山"' in prompt
assert "路人甲" not in prompt                                                    # 分鏡給了不在出場名單裡的人，不畫
assert 'Xiaofeiyu has a speech bubble with exact Chinese text "这碗是本鱼的"' in prompt
assert '小凛 has a speech bubble with exact Chinese text "写你名字了吗"' in prompt
assert "抢饭大战" in prompt and "no QQ IDs" in prompt and "ONE whale tail" in prompt
assert "陈｜陈｜40（就是爹爹）" in Prov.prompt and "不画成大叔" in Prov.system
# 主人的樣子：設了 comic_owner_look 就蓋掉分鏡給的
S.look = "messy black hair, navy hoodie"
sb3 = {"cast": SB["cast"] + [{"称呼": "陈", "look": "old man with beard"}], "panels": SB["panels"] + [{"scene": "x", "who": ["陈"]}]}
p3, _ = c._comic_prompt(sb3, cast)
assert "- 陈: young chibi person, messy black hair, navy hoodie" in p3 and "beard" not in p3
S.look = ""
assert "- 陈:" not in c._comic_prompt({"cast": sb3["cast"], "panels": SB["panels"]}, cast)[0]  # 這張沒出場的人不列（10-31）
assert c._in_strip({"cast": sb3["cast"], "panels": SB["panels"][1:]}) == {"冰山", "小凛"}
assert "别人跟本鱼说话、提到本鱼时" in Prov.system and "「小肥鱼」" in Prov.system   # 別人嘴裡不叫她「本鱼」（10-31）
# 沒有〈我〉的格就不帶她的樣子和參考圖
sb2 = {"cast": SB["cast"], "panels": [dict(p, me=False, who=[w for w in p["who"] if w != "本鱼"]) for p in SB["panels"]]}
p2, me2 = c._comic_prompt(sb2, cast)
assert not me2 and "Xiaofeiyu (the main girl)" not in p2
# 新格式：一件事一張，最多 most 件；每張帶標題、話題
import json as _j
Prov.reply = _j.dumps({"cast": SB["cast"], "strips": [{"title": "抢饭大战", "topic": "抢饭", "panels": SB["panels"]},
                                                       {"title": "死机", "topic": "死机", "panels": SB["panels"][:2]},
                                                       {"title": "多的", "panels": SB["panels"]}]}, ensure_ascii=False)
sbs = asyncio.run(c._storyboard(topics, cast, most=2))
assert [x["title"] for x in sbs] == ["抢饭大战", "死机"] and len(sbs[1]["panels"]) == 2 and sbs[0]["cast"] == SB["cast"], sbs
pt, _ = c._comic_prompt(sbs[0], cast)
assert 'Title at the top with exact Chinese text "抢饭大战"' in pt
assert 'Xiaofeiyu (the main girl)' in pt and "NO name tag above her head" in pt and '"小肥鱼"' not in pt  # 10-30 她不帶名字牌
# 重畫一張：回的只有一張
one = asyncio.run(c._storyboard(topics, cast, prev=sbs[0], change="第二格换人", most=5))
assert len(one) == 1 and "只重写一件事的那张" in Prov.system and "第二格换人" in Prov.prompt
Prov.reply = None

# 重啟後接著畫：這次開機的試畫正畫著、或試畫被打斷，都不接（10-25 12:37 試畫被當成沒畫完，給主人發了「正在画着呢」）
import time
async def resume_case(job, busy):
    c.state, c._save, called = {"inflight": {"20001": dict(job)}, "draw_jobs": []}, (lambda: None), []
    c._locks = {}
    async def report(*a): called.append(a)
    c._draw_and_report = report
    if busy:
        await c._lock("20001").acquire()
    await c._resume()
    return called, c.state["inflight"]
now = int(time.time())
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "test": False}, True)) == ([], {"20001": {"gid": "20001", "ts": now, "test": False}})
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "test": True}, False)) == ([], {})
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "auto": True}, False))[0] == [("20001", 0, True, [])]
# 畫好了、還沒發（看圖、發送時被打斷）：拿那張接著，不重畫；檔案沒了就重畫
img = Path(tempfile.mkdtemp()) / "c.png"; img.write_bytes(b"x")
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "auto": True, "path": str(img)}, False))[0] == [("20001", 0, True, [str(img)])]
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "auto": True, "path": "/nope.png"}, False))[0] == [("20001", 0, True, [])]
assert asyncio.run(resume_case({"gid": "20001", "ts": now, "auto": False}, False))[0] == [("20001", 0, True, [])]  # 舊記錄 auto=False：11-02 起照定時那張接，不私信主人預覽

# ---- 分鏡 JSON 壞了（11-02）：先本地修；修不好請備用模型照原樣補成合法 JSON，重寫 1 次；還是壞就拋 StoryboardBad，不退回群分析插件 ----
good = _j.dumps({"cast": SB["cast"], "strips": [{"title": "抢饭大战", "topic": "抢饭", "panels": SB["panels"]}, {"title": "死机", "topic": "死机", "panels": SB["panels"][:2]}]}, ensure_ascii=False)
fix = cm.fix_json
c.dir = Path(tempfile.mkdtemp())
# 本地能修的幾種：```、尾逗號、缺逗號、被截斷（字串中間、物件中間）
for name, bad_txt in [
    ("```", "```json\n" + good + "\n```"),
    ("尾逗號", good.replace('"caption": "又死机了"}', '"caption": "又死机了",}', 1)),
    ("缺逗號", good.replace('"scene": "Bingshan stares at a crashed computer", ', '"scene": "Bingshan stares at a crashed computer" ', 1)),
    ("缺逗號(物件之間)", good.replace("}, {", "} {", 1)),
    ("被截斷", good[:len(good) - 40]),
]:
    assert json.loads(fix(bad_txt)), name
    Prov.prompts.clear(); Prov.queue = [bad_txt]
    got = asyncio.run(c._storyboard(topics, cast, most=2))
    assert got and not Prov.prompts[1:], (name, got, Prov.prompts[1:])               # 本地修好就不再叫模型
# 修好了也要過欄位檢查：沒有 panels 的不放過
Prov.queue = ['{"cast": [], "strips": [{"title": "空", "panels": [],}]}']
try:
    asyncio.run(c._storyboard(topics, cast, most=2)); raise AssertionError
except RuntimeError as e:
    assert "一格都没有" in str(e)
# 本地修不好（字串裡有沒轉義的引號）：請備用模型；沒設備用就用同一個
unfixable = good.replace("这碗是本鱼的", '这碗是"本鱼"的的', 1)
for t in (unfixable,):
    try:
        json.loads(t); raise AssertionError
    except ValueError:
        pass
    assert cm.LivelyComic._parse_sb(t, loose=True, quiet=True) is None, "這個本地修不了"
broken = unfixable
class Backup:
    queue: list = []
    prompts: list = []
    async def text_chat(self, prompt, system_prompt):
        Backup.prompts.append(prompt)
        return types.SimpleNamespace(completion_text=Backup.queue.pop(0))
class Pair(Prov):
    _backup = Backup()
_old = S.provider
S.provider = lambda self, key="provider_id": Pair()
Prov.prompts.clear(); Prov.queue = [broken]; Backup.prompts.clear(); Backup.queue = [good]
sbs = asyncio.run(c._storyboard(topics, cast, most=2, gid="20001"))
assert [x["title"] for x in sbs] == ["抢饭大战", "死机"], sbs                       # 主模型壞、備用重寫好：照常多張
assert len(Prov.prompts) == 1 and len(Backup.prompts) == 1                           # 重寫走備用模型，不是同一個再寫一遍
assert "解析时报错" in Backup.prompts[0] and "内容一个字都不改" in Backup.prompts[0]
bad_files = list((c.dir / "storyboard_bad").glob("20001_*_bad.txt"))
assert bad_files and broken in bad_files[0].read_text("utf-8"), bad_files           # 壞掉的原文整段存了一份
Backup.prompts.clear(); Prov.queue = [broken]; Backup.queue = [broken]
try:
    asyncio.run(c._storyboard(topics, cast, most=2)); raise AssertionError("兩次都壞要拋錯")
except cm.StoryboardBad as e:
    assert str(e).startswith(cm.STORYBOARD_BAD), e
assert len(Backup.prompts) == 1                                                       # 只重寫 1 次
assert list((c.dir / "storyboard_bad").glob("*_rewrite.txt"))                         # 重寫後還壞的也存
Prov.queue = ["完全不是 JSON"]; Backup.queue = [good]                                  # 連大括號都沒有也算壞，也重寫
assert len(asyncio.run(c._storyboard(topics, cast, most=2))) == 2
S.provider = _old
Prov.queue = []
# 超過 7 天的原文清掉
import os
old_f = c.dir / "storyboard_bad" / "old.txt"; old_f.write_text("x"); os.utime(old_f, (1, 1))
c.keep_days = 30; c.state = {}
c._cleanup_images()
assert not old_f.exists()
# 重放 11-01 22:41:58 桐群：JSON 在第 3134 字缺逗號（Expecting ',' delimiter）——現在本地就修得好
long_sb = {"cast": SB["cast"], "strips": [{"title": "t", "panels": SB["panels"] * 12}]}
txt = json.dumps(long_sb, ensure_ascii=False, indent=1)
bad = txt[:3133] + txt[3133:].replace(",", "", 1)
try:
    json.loads(bad); raise AssertionError
except ValueError as e:
    assert "Expecting" in str(e) or "Unterminated" in str(e), e
Prov.prompts.clear(); Prov.queue = [bad]
assert asyncio.run(c._storyboard(topics, cast, most=2)) and not Prov.prompts[1:]
print("comic storyboard ok")
