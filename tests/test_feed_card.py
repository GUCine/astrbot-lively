"""投喂檔位的印象卡（bond card_img.py＋card_fx.py，10-26）：五檔都畫得出來（背景畫、霧面玻璃、圓頭像）、第四檔起是動圖、檔案不太大。

/usr/local/bin/python3 tests/test_feed_card.py（要有 PIL；號碼都是假的）
"""
import importlib
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
card_img = importlib.import_module("astrbot_plugin_lively_bond.card_img")
fx = card_img.fx

av = Image.new("RGB", (320, 320), "#9cc8f0")
buf = BytesIO()
av.save(buf, "PNG")
AV = buf.getvalue()
tmp = Path(tempfile.mkdtemp())
NAMES = {1: "一口饭", 2: "一碗饭", 3: "一锅饭", 4: "长期饭票", 5: "金饭碗"}


def draw(tier, name="泠·月", **kw):
    return card_img.render(tmp / f"card_2000{tier}", qq=f"2000{tier}", name=name, favor=36.5, favor_desc="亲近",
                           stage="很熟", mood="开心", mood_kind="开心", known_days=12, talks=231, moments=116, words=["很亲", "爱互损", "挂心"],
                           impression="会拿 token 换大白饭", met="10-18 21:04", last="最近聊天 3 分钟前", avatar=AV,
                           me="本鱼", feed={"tier": tier, "name": NAMES[tier]} if tier else None, **kw)


sizes = {}
for t in range(6):
    p = draw(t)
    assert p.exists() and p.suffix == (".gif" if t >= fx.ANIMATED else ".jpg" if t else ".png"), (t, p)
    im = Image.open(p)
    sizes[t] = p.stat().st_size
    if t >= fx.ANIMATED:
        assert im.n_frames >= 10 and im.info.get("loop") == 0, (t, im.n_frames)
        assert sizes[t] < 3 * 1024 * 1024, (t, sizes[t])  # QQ 發得動、不容易超時
    else:
        assert getattr(im, "n_frames", 1) == 1 and sizes[t] < 600 * 1024, (t, sizes[t])
    assert im.width == card_img.W + 40 * card_img.S
print("sizes", {t: f"{v // 1024}KB" for t, v in sizes.items()})

# 五張背景畫都在；拿掉了就用這一檔的漸變代替，照樣畫得出來
for t in range(1, 6):
    assert any((fx.BG_DIR / f"bg{t}.{e}").exists() for e in ("webp", "png", "jpg")), t
real_bg, fx.BG_DIR = fx.BG_DIR, tmp / "没有"
assert draw(3).suffix == ".jpg"
fx.BG_DIR = real_bg
# 寫壞的檔位當沒有；超過五檔畫最高那檔；沒頭像照樣畫
plain = dict(qq="1", name="a", favor=0, favor_desc="普通", stage="还不熟", mood="平常", known_days=0, talks=0,
             moments=0, impression="", met="", last="", avatar=None)
assert card_img.render(tmp / "x", **plain, feed={"tier": "坏的"}).suffix == ".png"
assert card_img.render(tmp / "y", **plain, feed={"tier": 9, "name": "超"}).suffix == ".gif"
# 名字很長也讓開右邊的檔位，很長的印象最多三行
draw(3, name="一个名字特别特别特别长的群友啊啊啊啊")
draw(1, name="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
card_img.render(tmp / "z", **{**plain, "impression": "很长" * 80}, feed={"tier": 2, "name": "一碗饭"})
# 〈我〉對 TA 的稱呼（心裡的 TA 的「称呼」）：普通卡寫在關係緞帶右邊、不改高度；投喂卡在名字底下多一行；和名字一樣、空的不寫
assert card_img._alias("小凛酱", "小凛🍥") == "小凛酱" and card_img._alias("逸凡", "逸凡") == "" and card_img._alias("  ", "a") == ""
assert card_img._alias("一二三四五六七八九十一二三", "a") == "一二三四五六七八九十一二"
h = lambda p: Image.open(p).height
assert h(draw(0, alias="阿月")) == h(draw(0))
assert h(draw(2, alias="阿月")) == h(draw(2)) + 18 * card_img.S
assert h(draw(2, alias="泠·月")) == h(draw(2))  # 和名字一樣
draw(0, name="暴力清理完电脑转头去下载原神之人", alias="笨比笨比笨比笨比笨比笨比")  # 太長截掉，不擠出卡外
draw(3, name="一个名字特别特别特别长的群友啊啊啊啊", alias="大王大王大王大王大王大王")
# 字不出卡外（10-27）：放不下先縮字、再截；稱呼連一個字都放不下就不寫；印象多了最後一行截掉補「…」」
probe = ImageDraw.Draw(Image.new("RGB", (4, 4)))
f20 = ImageFont.load_default()
assert card_img._ellipsize(f20, probe, "短", 999) == "短"
cut = card_img._ellipsize(f20, probe, "abcdefghijklmnopqrstuvwxyz" * 3, 120)
assert cut.endswith("…") and probe.textlength(cut, font=f20) <= 120
assert card_img._fit(f20, probe, "本鱼叫你「", "阿月", "」", 1) == ""
assert card_img._clip_lines(["「一", "二", "三」"], 3, lambda s: True) == ["「一", "二", "三」"]
assert card_img._clip_lines(["「一二", "三四", "五六", "七」"], 2, lambda s: True) == ["「一二", "三四…」"]
assert card_img._shrink(lambda n: ImageFont.load_default(n), probe, "x" * 200, 50, 26, 18).size == 18
# 一行不以收尾的標點開頭（主人那張的印象最後一行原本只剩一個「」」）
assert card_img._no_orphan(["「追着问能不能给", "别人发，只归他", "」"], lambda t: True) == ["「追着问能不能给", "别人发，只归", "他」"]
assert card_img._no_orphan(["「一二", "」"], lambda t: False) == ["「一二", "」"]  # 挪了放不下就不挪
assert card_img._no_orphan(["「一。", "」"], lambda t: True) == ["「一。", "」"]  # 前一個也是標點不挪
# 表情符號（10-27）：有彩色表情字體（card_assets/NotoColorEmoji.ttf）就照樣畫，組合表情算一個字、截字時不會切開；
# 沒有字體就拿掉（不然畫成方框），名字整個是表情時用〈我〉對 TA 的稱呼，沒有稱呼寫「（表情名字）」。
# 名字裡沒有字（整個是表情、只有標點）時旁邊括號加上稱呼，稱呼裡也沒字用群名片墊上
emo = card_img.emo
FAM = "👨\u200d👩\u200d👧"
assert emo.clusters(FAM + "x🇨🇳🇯🇵1\ufe0f\u20e3👍🏽") == [FAM, "x", "🇨🇳", "🇯🇵", "1\ufe0f\u20e3", "👍🏽"]
assert emo.head("🇨🇳🇯🇵ab", 1) == "🇨🇳" and emo.drop_last("ab👍🏽") == "ab"
assert card_img._printable("a\u200db") == "ab"
if emo.font() is not None:
    print("有表情字体")
    assert card_img._printable("小凛🍥") == "小凛🍥" and card_img._printable("👍🏽" + FAM) == "👍🏽" + FAM
    assert card_img._names("🍮", "布丁", "1") == ("🍮（布丁）", "") and card_img._names("🍮", "", "1") == ("🍮", "")
    assert card_img._names("🍮", "🍮", "1", "布丁🍮") == ("🍮（布丁）", "")  # 稱呼也是表情：用群名片裡的字
    assert card_img._names("🍮", "凛凛👍🏽", "1") == ("🍮（凛凛）", "")
    assert card_img._names("🔕", "🌙", "1", "Randy-4070 983 32G-Quest3") == ("🔕（Randy-4070…）", "🌙")
    assert card_img._names("🍮", "🍮", "1") == ("🍮", "")
    f40 = ImageFont.load_default(40)
    assert emo.length(probe, "a🍮", f40) > probe.textlength("a", font=f40) + 30
    cut = card_img._ellipsize(f40, probe, "布丁" + FAM * 20, 300)
    assert cut.endswith("…") and set(emo.clusters(cut[:-1])) <= {"布", "丁", FAM}, cut
    pic = Image.new("RGBA", (120, 80), (255, 255, 255, 255))
    emo.draw(ImageDraw.Draw(pic), (10, 60), "🍮", f40, "#000000")
    assert any(r > 180 and 90 < g < 200 and b < 90 for _, (r, g, b) in pic.convert("RGB").getcolors(1 << 16))  # 畫出來是布丁的橙黃色，不是黑字方框
    m = card_img.Mixed(f40, f40)
    pic = Image.new("RGBA", (300, 80), (255, 255, 255, 255))
    m.draw(ImageDraw.Draw(pic), (10, 60), "a🍮b", "#000000")
    assert any(r > 180 and 90 < g < 200 and b < 90 for _, (r, g, b) in pic.convert("RGB").getcolors(1 << 16))
elif card_img._printable("🍮") == "":  # 有中文字體才判得出來
    assert card_img._printable("小凛🍥") == "小凛"
    assert card_img._names("🍮", "布丁", "1") == ("布丁", "")
    assert card_img._names("🍮", "", "1") == ("（表情名字）", "")
    assert card_img._names("🍮", "", "1", "布丁🍮") == ("布丁", "")
    assert card_img._names("小凛🍥", "小凛", "1") == ("小凛", "")
assert card_img._names("西瓜头", "瓜瓜", "1", "西瓜") == ("西瓜头", "瓜瓜")
assert card_img._names(".", "", "1", "菜菜") == (".（菜菜）", "") and card_img._names(".", "", "1") == (".", "")
assert card_img._names(".", "", "1", "台式5060ti 16 quest2")[0] == ".（台式5060ti…）"
assert card_img._ellipsize(ImageFont.load_default(20), probe, "🍮（" + "布丁" * 40 + "）", 300).endswith("…）")
for t in (0, 2):
    card_img.render(tmp / f"long{t}", **{**plain, "name": "发现前男友是男同出轨绝望去点模子点到小三", "mood": "又好气又好笑还有点心虚",
                                        "favor": 12.6, "avatar": AV}, alias="小三姐姐小三姐姐",
                    feed={"tier": t, "name": NAMES[t]} if t else None)
    card_img.render(tmp / f"emoji{t}", **{**plain, "name": "🍮", "impression": "特别长的印象" * 30},
                    feed={"tier": t, "name": NAMES[t]} if t else None)
    card_img.render(tmp / f"emoji3{t}", **{**plain, "name": "🍮", "impression": "布丁"}, alias="🍮", card="布丁🍮",
                    feed={"tier": t, "name": NAMES[t]} if t else None)
    card_img.render(tmp / f"emoji2{t}", **{**plain, "name": "小凛🍥" + FAM, "mood": "开心😆", "impression": "爱吃🍮" * 40},
                    alias="凛凛👍🏽", feed={"tier": t, "name": NAMES[t]} if t else None)
card_img.render(tmp / "emoji5", **{**plain, "name": "金🍮" * 3}, feed={"tier": 5, "name": "金饭碗"})  # 金字名字裡的表情照原色
# 上一次是動圖、這次掉回靜態：返回的路徑跟著換副檔名
assert draw(2).suffix == ".jpg"
# 發完卡告訴她這張長什麼樣：每一檔都有說法
assert set(fx.LOOK) == {1, 2, 3, 4, 5} and all(fx.LOOK.values())

# ---- 真的走一遍發卡：讀口給的檔位 → 畫成動圖 → 發出去的是 .gif，回給她的話帶檔名和樣子 ----
import asyncio, json, time, types  # noqa: E402


def mod(name, **kw):
    m = types.ModuleType(name)
    m.__dict__.update(kw)
    sys.modules[name] = m
    return m


class L:
    def __getattr__(self, k): return lambda *a, **k2: None


class Dummy:
    def __init__(self, *a, **k): pass


class Chain:
    def __init__(self): self.parts = []
    def file_image(self, p): self.parts.append(p); return self


def deco(*a, **k): return lambda f: f


flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, on_agent_done=deco,
                            on_decorating_result=deco, llm_tool=deco, command=deco, after_message_sent=deco,
                            permission_type=deco, PermissionType=types.SimpleNamespace(ADMIN=0),
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", At=Dummy, Image=Dummy, Plain=Dummy, Reply=Dummy)
mod("astrbot.api.star", Context=object, Star=Dummy, register=deco,
    StarTools=types.SimpleNamespace(get_data_dir=lambda name: tmp))
mod("astrbot.core"); mod("astrbot.core.agent")
mod("astrbot.core.agent.message", TextPart=Dummy)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Chain, ResultContentType=Dummy)
mod("astrbot.core.star"); mod("astrbot.core.star.filter"); mod("astrbot.core.star.filter.command", GreedyStr=str)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(tmp))
mod("aiohttp", ClientSession=Dummy, ClientTimeout=Dummy)
core = importlib.import_module("astrbot_plugin_lively_bond.core")
heart = importlib.import_module("astrbot_plugin_lively_bond.heart")
rel = importlib.import_module("astrbot_plugin_lively_bond.relation")
bm = importlib.import_module("astrbot_plugin_lively_bond.main")
A, B = "20001", "20002"
core.OWNERS.clear(); core.OWNERS.add("10001")
store = core.BondStore(str(tmp / "bond.db"))
hs = heart.HeartStore(store.db)
for q in (A, B):
    store.on_talk(q, "阿" + q[-1], time.time() - 3600)
store.db.commit()
rel.FEEDS.parent.mkdir(parents=True, exist_ok=True)
rel.FEEDS.write_text(json.dumps([{"id": "1", "ts": time.time(), "qq": A, "amount": 88, "added": time.time()},
                                 {"id": "2", "ts": time.time(), "qq": A, "amount": 20, "added": time.time()}]), "utf-8")
conf = {"feed_card": True}


class BS:
    def get(self, k, d=None): return conf.get(k, d)
    def is_owner(self, q): return q == "10001"
    def me(self): return "本鱼"
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")


bond = bm.LivelyBond.__new__(bm.LivelyBond)
bond.s, bond.store, bond.heart = BS(), store, hs
bond.rel = rel.Relations(store, hs, feed_tiers=lambda: (bond.s.get("feed_tiers", rel.FEED_TIERS) if bond.s.get("feed_card", True) else ""))
bond._card_busy, bond._shared_umo = set(), {}
bond.card_bg_dir = tmp / "card_bg"
bond._qq_avatar = lambda q: asyncio.sleep(0, result=AV)
SENT = []


async def send_message(umo, chain): SENT.append((umo, chain.parts[0]))
bond.context = types.SimpleNamespace(send_message=send_message)


class Ev:
    def __init__(self, q, umo=None): self.q, self.unified_msg_origin = q, umo or f"x:FriendMessage:{q}"
    def get_sender_id(self): return self.q
    def get_sender_name(self): return ""
    def get_self_id(self): return "99999"
    def get_group_id(self): return ""


ok, msg = asyncio.run(bond._send_card(Ev(A)))
assert ok and SENT[-1][1].endswith(f"card_{A}.gif"), (ok, msg, SENT)
assert "这张带着 TA 的投喂档位「长期饭票」：" + fx.LOOK[4] in msg, msg
assert Image.open(SENT[-1][1]).n_frames > 1
ok, msg = asyncio.run(bond._send_card(Ev(B)))  # 沒投喂過：照舊的 png，不提檔位
assert ok and SENT[-1][1].endswith(f"card_{B}.png") and "档位" not in msg, (msg, SENT[-1])
conf["feed_card"] = False  # 關掉就不分檔：卡片和以前一樣
ok, msg = asyncio.run(bond._send_card(Ev(A)))
assert ok and SENT[-1][1].endswith(f"card_{A}.png") and "档位" not in msg, (msg, SENT[-1])

# ---- 專屬背景：card_bg/<QQ>.webp（＋.txt 一句說明）；有就用它，香檳金，玻璃亮暗看畫的下半截 ----
bgd = tmp / "card_bg"
bgd.mkdir()
fx.gradient(450, 675, ["#f3ead8", "#e8d8c8", "#f6efe6"]).save(bgd / f"{B}.webp")  # 亮的
fx.gradient(450, 675, ["#f0c890", "#3a2850", "#141830"]).save(bgd / f"{A}.png")  # 下半截暗
(bgd / f"{B}.txt").write_text("\n〈主人〉用筷子喂〈我〉一口白饭\n第二行不要", "utf-8")
(bgd / "readme.webp").write_bytes(b"x")  # 不是 QQ 號的跳過
(bgd / "30003.jpg").write_bytes(b"broken")  # 讀不出來的跳過
bgs = fx.own_bgs(bgd)
assert set(bgs) == {A, B}, bgs
assert bgs[B]["dark"] is False and bgs[A]["dark"] is True, bgs
assert bgs[B]["look"] == "〈主人〉用筷子喂〈我〉一口白饭" and bgs[A]["look"] == "" and bgs[B]["deep"].startswith("#")
assert fx.own_bgs(tmp / "没有这个目录") == {}
p0 = card_img.render(tmp / "own0", **plain, bg=bgs[B]["path"])  # 沒投喂過也換成專屬背景
assert p0.suffix == ".jpg" and Image.open(p0).width == card_img.W + 40 * card_img.S, p0
assert draw(4, bg=bgs[A]["path"]).suffix == ".gif"  # 投喂四檔起照樣是動圖
assert card_img.render(tmp / "own1", **plain, bg=tmp / "没有.webp").suffix == ".png"  # 圖沒了：照舊
bond.card_bg_dir = bgd
conf["feed_card"] = True
ok, msg = asyncio.run(bond._send_card(Ev(B)))
assert ok and SENT[-1][1].endswith(f"card_{B}.jpg") and "专门给 TA 画的背景：爹爹用筷子喂本鱼一口白饭" in msg, (msg, SENT[-1])
assert "投喂档位" not in msg, msg
ok, msg = asyncio.run(bond._send_card(Ev(A)))  # 專屬背景＋投喂四檔：動圖，標檔位
assert ok and SENT[-1][1].endswith(f"card_{A}.gif") and "「长期饭票」" in msg and "动图" in msg and fx.LOOK[4] not in msg, msg

# ---- 「剛發過」按聊天分開算：別的群看不到這邊發的；同一個聊天回給她的只講事實 ----
bond._shared_umo.clear()
G1, G2 = "x:GroupMessage:30001", "x:GroupMessage:30002"
ok1, _ = asyncio.run(bond._send_card(Ev(A, G1)))
ok2, m2 = asyncio.run(bond._send_card(Ev(A, G2)))
assert ok1 and ok2 and SENT[-1][0] == G2, (m2, SENT[-1])
ok3, m3 = asyncio.run(bond._send_card(Ev(A, G1)))  # 同一個聊天馬上又要：發不發她定，程式不擋（10-28 拿掉 10 分鐘那道）
assert ok3 and SENT[-1][0] == G1, m3
bond._card_busy.add((A, G1))  # 那張正在畫、正在發：不畫第二張
ok4, m4 = asyncio.run(bond._send_card(Ev(A, G1)))
assert not ok4 and "正在发" in m4 and "翻" not in m4, m4
bond._card_busy.clear()
for _ in range(10):  # 一個聊天一小時 8 張那道 10-28 拿掉了：發幾張她定
    assert asyncio.run(bond._send_card(Ev(B, G1)))[0]
assert not bond._card_busy, bond._card_busy

# 卡上的關係只放第一段，名字等佔位符發卡前就套好；很長也不會擠出卡外
assert card_img.short_stage("主人，最亲的人，本鱼叫 TA「爹爹」") == "主人" and card_img.short_stage("熟人") == "熟人"
assert card_img.short_stage("") == ""
card_img.render(tmp / "long", **{**plain, "stage": "一个特别特别长的关系说明没有逗号啊啊啊啊啊啊", "favor_desc": "很喜欢 TA",
                                 "mood": "有点小得意又有点害羞"}, bg=bgs[B]["path"])
# 發卡時把心裡的 TA 的稱呼帶上
seen = []
real_render = bm.card_img.render
bm.card_img.render = lambda *a, **k: (seen.append(k.get("alias")), real_render(*a, **k))[1]
hs.set_heart(B, {"称呼": "阿二酱", "印象": "爱吃饭"})
bond._shared_umo.clear()
assert asyncio.run(bond._send_card(Ev(B)))[0] and seen[-1] == "阿二酱", seen
assert asyncio.run(bond._send_card(Ev(A)))[0] and seen[-1] == "", seen  # 沒有心裡的 TA
bm.card_img.render = real_render
# 發卡報超時（napcat retcode 1200）：先翻那邊的消息，看到了就不再發（10-28 19:30 白岩收到兩張）；沒看到才再發一次
bm.CARD_CHECK = (0,)
BOT = "99999"
BS.client = lambda self: types.SimpleNamespace(api=types.SimpleNamespace(call_action=call_action))
BS.bot_qq = lambda self: BOT
HIST = []
CALLS = []


async def call_action(action, **kw):
    CALLS.append((action, kw))
    return {"messages": list(HIST)}


TRIES = []


async def flaky(umo, chain):
    TRIES.append(umo)
    if len(TRIES) == 1:
        HIST.append({"sender": {"user_id": BOT}, "time": time.time(), "message": [{"type": "image", "data": {}}]})
        raise RuntimeError("ActionFailed retcode=1200 Timeout: sendMsg")


bond.context = types.SimpleNamespace(send_message=flaky)
bond._shared_umo.clear()
ok, msg = asyncio.run(bond._send_card(Ev(B, umo="x:GroupMessage:30001")))
assert ok and len(TRIES) == 1 and CALLS[-1] == ("get_group_msg_history", {"count": 20, "group_id": 30001}), (ok, msg, TRIES, CALLS)
TRIES.clear(); HIST.clear()


async def flaky_lost(umo, chain):  # 報超時、那邊也沒看到：再發一次
    TRIES.append(umo)
    if len(TRIES) == 1:
        raise RuntimeError("ActionFailed retcode=1200 Timeout")


bond.context = types.SimpleNamespace(send_message=flaky_lost)
bond._shared_umo.clear()
ok, msg = asyncio.run(bond._send_card(Ev(B)))
assert ok and len(TRIES) == 2 and CALLS[-1][0] == "get_friend_msg_history", (ok, TRIES, CALLS)
HIST.append({"sender": {"user_id": BOT}, "time": time.time() - 3600, "message": [{"type": "image"}]})  # 一小時前的那張不算
assert not asyncio.run(bond._card_landed("x:GroupMessage:30001", time.time()))
rel.FEEDS.unlink()
print("feed card ok")
