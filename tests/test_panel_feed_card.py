"""面板的投喂檔位〈卡〉（10-26）：人物表、檔案帶上 bond 讀口給的投喂檔位；/api/feedbg/<檔> 從 bond 帶的
card_assets/feed 縮出背景（blur=1 是霧面玻璃底下那張），沒有這張圖就 404。
stub 掉 astrbot，號碼都是假的。

/usr/local/bin/python3 tests/test_panel_feed_card.py（要 PIL）
"""
import asyncio, importlib, sys, tempfile, types
from pathlib import Path

from PIL import Image

TMP = Path(tempfile.mkdtemp(prefix="feedcard_test_"))


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pm = importlib.import_module("astrbot_plugin_lively_panel.main")
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, extra)
    if not ok:
        fails.append(name)


class S:
    def get(self, k, d=None): return d
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")


P = object.__new__(pm.LivelyPanel)
P.s, P.dir = S(), TMP / "panel"
P._star = lambda name: None

# 人物表、檔案帶上投喂檔位；沒投喂過的不帶
fed = {"n": 2, "total": 30.0, "tier": 3, "tier_name": "一锅饭", "tier_count": 5, "next_amount": 100.0, "next_name": "长期饭票"}
rel = {"score": 47.4, "base": 40, "live": 1, "adjust": 0, "tier": "亲近", "stage": "熟人", "desc": "挺喜欢 TA", "attitude": 0, "fed": fed}
row = P._with_rel({"qq": "20001", "favor": 3}, rel)
check("带上投喂档位", row.get("fed") == fed and row["favor"] == 47.4, row)
row = P._with_rel({"qq": "20002"}, {**rel, "fed": None})
check("没投喂过的不带", "fed" not in row, row)

# 背景：bond 带的 card_assets/feed/bg<N>
src = P._feed_bg_src(3)
check("找得到 bond 带的背景", src is not None and src.name.startswith("bg3.") and src.exists(), src)


class Req:
    def __init__(self, tier, **q): self.match_info, self.query = {"tier": str(tier)}, {k: str(v) for k, v in q.items()}


r = asyncio.run(P.feed_bg(Req(3, w=300)))
im = Image.open(r.path)
check("缩到要的宽", r.path.exists() and im.size[0] == 300 and im.format == "JPEG", (r.path, im.size))
rb = asyncio.run(P.feed_bg(Req(3, w=300, blur=1)))
check("糊过的另存一张", rb.path != r.path and rb.path.name.endswith("-blur.jpg") and Image.open(rb.path).size == im.size, rb.path)
check("宽度有上下限", Image.open(asyncio.run(P.feed_bg(Req(1, w=99999))).path).size[0] == 900)
check("档位不对", asyncio.run(P.feed_bg(Req(9)))["_status"] == 400)
check("档位不是数字", asyncio.run(P.feed_bg(Req("../x")))["_status"] == 400)
P._feed_bg_src = lambda t: None
check("没有这张背景", asyncio.run(P.feed_bg(Req(2)))["_status"] == 404)


# 專屬背景：bond 的 card_bgs() 給 qq -> {path, v, dark, deep}；人物表、檔案帶上，/api/cardbg/<QQ> 縮、糊
bgp = TMP / "card_bg" / "20003.webp"
bgp.parent.mkdir(parents=True, exist_ok=True)
Image.new("RGB", (450, 675), "#ddd0cd").save(bgp)
BGS = {"20003": {"path": bgp, "v": 123, "dark": False, "deep": "#ddd0cd", "look": "〈主人〉喂〈我〉"}}
P._card_bgs = lambda: BGS
row = P._with_bg({"qq": "20003"}, BGS)
check("带上专属背景", row.get("card_bg") == {"v": 123, "dark": False, "deep": "#ddd0cd"}, row)
check("没有的不带", "card_bg" not in P._with_bg({"qq": "20004"}, BGS))


class QReq:
    def __init__(self, qq, **q): self.match_info, self.query = {"qq": str(qq)}, {k: str(v) for k, v in q.items()}


r = asyncio.run(P.card_bg(QReq(20003, w=300)))
check("专属背景缩到要的宽", Image.open(r.path).size[0] == 300 and r.path.name == "card-bg20003-300.jpg", r.path)
rb = asyncio.run(P.card_bg(QReq(20003, w=300, blur=1)))
check("专属背景糊过的另存", rb.path.name.endswith("-blur.jpg"), rb.path)
check("没有专属背景 404", asyncio.run(P.card_bg(QReq(20004)))["_status"] == 404)
check("号码不对", asyncio.run(P.card_bg(QReq("../x")))["_status"] == 400)
P._star = lambda name: None
del P._card_bgs
check("bond 没载入就当没有", P._card_bgs() == {})

print("all ok" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
