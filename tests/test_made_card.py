"""印象卡放定做的虛擬形象（10-27）：bond card_img 讀 comic 的 avatars/（made_avatars），卡面圖 → 大圖＋裁出的臉；
只有三視圖時從正面那個人裁；讀不出來回 (None, None) 讓 bond 退回 QQ 頭像。投喂卡的圓圈用臉。
面板人物表、檔案帶 made_av，/api/madeav/<QQ> 縮圖（face=1 是臉）。stub 掉 astrbot，號碼都是假的。

/usr/local/bin/python3 tests/test_made_card.py（要 PIL）
"""
import asyncio, importlib, json, sys, tempfile, types
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

TMP = Path(tempfile.mkdtemp(prefix="madecard_test_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ci = importlib.import_module("astrbot_plugin_lively_bond.card_img")
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, extra)
    if not ok:
        fails.append(name)


AV = TMP / "avatars"
AV.mkdir()
# 卡面圖：上方中間一塊紅（臉）；三視圖：白底三個分開的人，最左邊（正面）是藍的
card = Image.new("RGB", (1536, 1024), "#f4e8ee")
ImageDraw.Draw(card).rectangle((600, 150, 936, 600), fill="#d04050")
card.save(AV / "20001_card.png")
sheet = Image.new("RGB", (1536, 1024), "white")
for x, c in ((180, "#3050c0"), (680, "#30a050"), (1180, "#c09030")):
    ImageDraw.Draw(sheet).rectangle((x, 60, x + 180, 980), fill=c)
for q in ("20001", "20002"):
    sheet.save(AV / f"{q}.png")
(AV / "broken.png").write_bytes(b"not a png")
(AV / "avatars.json").write_text(json.dumps({"made": {
    "20001": {"file": "20001.png", "card": "20001_card.png", "ts": 1},
    "20002": {"file": "20002.png", "ts": 1},
    "20003": {"file": "20003.png", "ts": 1},                      # 圖不在
    "20004": {"file": "broken.png", "card": "nope.png", "ts": 1},  # 卡面沒了、三視圖壞的
}}), "utf-8")

m = ci.made_avatars(AV)
check("读到两个有图的、图不在的跳过", set(m) == {"20001", "20002", "20004"} and m["20001"]["card"].name == "20001_card.png"
      and m["20002"]["card"] is None and m["20004"]["card"] is None, m)
check("没有 avatars.json 是空的", ci.made_avatars(TMP / "nope") == {})

art, face = ci.made_faces(m["20001"])
a, f = Image.open(BytesIO(art)), Image.open(BytesIO(face))
check("有卡面图：大图是整张", a.size == (1536, 1024), a.size)
check("有卡面图：脸是上方中间的正方形、是红的", f.size[0] == f.size[1] and f.getpixel((f.width // 2, f.height // 2))[0] > 180, f.getpixel((f.width // 2, f.height // 2)))

art, face = ci.made_faces(m["20002"])
a, f = Image.open(BytesIO(art)), Image.open(BytesIO(face))
mid = a.getpixel((a.width // 2, a.height // 2))
check("只有三视图：大图取正面（蓝的那个）、横的", a.width > a.height and mid[2] > 150 and mid[0] < 100, (a.size, mid))
check("只有三视图：旁边补的是三视图的白底", a.getpixel((2, a.height // 2)) == (255, 255, 255) or sum(a.getpixel((2, a.height // 2))) > 740)
check("只有三视图：脸是正方形、蓝的", f.size[0] == f.size[1] and f.getpixel((f.width // 2, f.height // 2))[2] > 150)
check("读不出来是 (None, None)", ci.made_faces(m["20004"]) == (None, None))

# 投喂卡的圓圈用 face、普通卡的大圖用 avatar
seen = {}
real = ci._render_feed
ci._render_feed = lambda path, tier, tname, **k: seen.setdefault("feed", k["avatar"]) and Path(path)
base = dict(qq="20001", name="阿月", favor=10, favor_desc="感觉亲近", stage="熟人", mood="开心", known_days=1, talks=1,
            moments=1, impression="x", met="10-27 10:00", last="刚刚聊过")
ci.render(TMP / "c1", avatar=b"ART", face=b"FACE", feed={"tier": 2, "name": "一碗饭"}, **base)
check("投喂卡的圆圈用脸", seen.get("feed") == b"FACE", seen)
seen.clear()
ci.render(TMP / "c2", avatar=b"ART", feed={"tier": 2, "name": "一碗饭"}, **base)
check("没给脸就用原来的头像", seen.get("feed") == b"ART", seen)
ci._render_feed = real


# ---------- 面板 ----------
def mod(name, **kw):
    x = types.ModuleType(name); x.__dict__.update(kw); sys.modules[name] = x; return x
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
class Star:
    def __init__(self, context=None): self.context = context
class FileResponse:
    def __init__(self, path, headers=None): self.path, self.headers = Path(path), headers or {}
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.star", Context=object, Star=Star, register=deco,
    StarTools=types.SimpleNamespace(get_data_dir=lambda name: str(TMP / name)))
mod("astrbot.core"); mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=object)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
web = mod("aiohttp.web", middleware=lambda f: f, Request=object, FileResponse=FileResponse,
          json_response=lambda d, status=200: dict(d, _status=status))
mod("aiohttp", ClientSession=object, ClientTimeout=object, web=web)
pm = importlib.import_module("astrbot_plugin_lively_panel.main")


class S:
    def get(self, k, d=None): return d
    def fill(self, t): return t


BondStar = type("LivelyBond", (), {"__module__": "astrbot_plugin_lively_bond.main",
                                   "made_avatars": lambda self: {q: r for q, r in m.items() if q != "20004"}})
P = object.__new__(pm.LivelyPanel)
P.s, P.dir = S(), TMP / "panel"
P._star = lambda name: BondStar() if name == "lively_bond" else None
avs = P._made_avs()
row = P._with_av({"qq": "20001"}, avs)
check("人物表带上 made_av（修改时间）", row.get("made_av") == {"v": m["20001"]["v"]}, row)
check("没有的不带", "made_av" not in P._with_av({"qq": "20009"}, avs))


class QReq:
    def __init__(self, qq, **q): self.match_info, self.query = {"qq": str(qq)}, {k: str(v) for k, v in q.items()}


r = asyncio.run(P.made_av(QReq(20001, w=320)))
check("大图缩到要的宽", Image.open(r.path).size[0] == 320 and r.path.name == "made-20001-320.jpg", getattr(r, "path", r))
r = asyncio.run(P.made_av(QReq(20001, w=160, face=1)))
im = Image.open(r.path)
check("face=1 是脸、正方形", im.size == (160, 160) and r.path.name.endswith("-face.jpg"), im.size)
check("没定做的 404", asyncio.run(P.made_av(QReq(20009)))["_status"] == 404)
check("号码不对", asyncio.run(P.made_av(QReq("../x")))["_status"] == 400)
P._star = lambda name: None
check("bond 没载入就当没有", P._made_avs() == {} and asyncio.run(P.made_av(QReq(20001)))["_status"] == 404)

print("all ok" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
