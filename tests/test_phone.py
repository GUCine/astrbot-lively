"""手機拍照（10-27）：拍法、畫風、形狀、參考素材怎麼翻成提示詞和參考圖；群友頭像、定做虛擬形象（lively_avatar）；群漫畫帶頭像。

/usr/local/bin/python3 tests/test_phone.py（號碼是假的：10001 主人）
"""
import asyncio, json, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_draw_wait as base  # noqa: E402  先跑一遍舊的，順便拿 stub 好的 astrbot

cm, TMP, S, Ev = base.cm, base.TMP, base.S, base.Ev
ph = sys.modules["astrbot_plugin_lively_comic.phone"]
ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))


D = TMP / "phone"
(D / "refs").mkdir(parents=True, exist_ok=True)
for f in ("me.jpg", "cos.jpg", "outfit_home.jpg", "owner.jpg", "room.jpg", "room_desk.jpg", "room_real.jpg", "home.jpg"):
    (D / "refs" / f).write_bytes(b"jpg")
(D / "refs" / "refs.json").write_text(json.dumps({"items": [
    {"name": "我", "file": "me.jpg", "desc": "〈我〉本人", "en": "ME", "real": "cos.jpg", "real_en": "COS"},
    {"name": "家居服", "file": "outfit_home.jpg", "desc": "家居服", "en": "HOME_OUTFIT", "real": "cos.jpg", "real_en": "COS_FACE", "real_keep": True},
    {"name": "〈主人〉", "file": "owner.jpg", "desc": "〈主人〉的样子", "en": "OWNER"},
    {"name": "房间", "file": "room.jpg", "desc": "房间", "en": "ROOM", "real": "room_real.jpg", "real_en": "ROOM_REAL"},
    {"name": "书桌", "file": "room_desk.jpg", "desc": "书桌", "en": "DESK", "real": "room_real.jpg", "real_en": "ROOM_REAL2", "real_keep": True},
    {"name": "主屏", "file": "home.jpg", "desc": "主屏", "en": "HOMESCREEN"},
    {"name": "没图的", "file": "nope.jpg", "desc": "x", "en": "x"}]}, ensure_ascii=False), encoding="utf-8")
plug = types.SimpleNamespace(dir=D, s=S())
phone = ph.Phone(plug)


async def fake_person(qq, call=""):
    f = D / f"av_{qq}.jpg"; f.write_bytes(b"j")
    return (f, f"AVATAR {call}") if qq != "99999" else None
names = lambda b: [p.name for p in b["refs"]]


async def run():
    b = await phone.build("a bowl of rice on the desk", "随手拍", "", "", "书桌")
    check("随手拍：带书桌、不自动带她自己", names(b) == ["room_desk.jpg"] and "first person" in b["prompt"] and "ME" not in b["prompt"], b)
    check("没写形状是方的、没写画风是二次元", b["size"] == "1024x1024" and b["look"] == "二次元" and "anime illustration" in b["prompt"])
    b = await phone.build("me on the bed", "自拍", "", "直", "房间")
    check("自拍自动带上她自己、排在前面", names(b) == ["me.jpg", "room.jpg"] and "Image 1: ME." in b["prompt"] and "Image 2: ROOM." in b["prompt"], b)
    check("直的是 1024x1536、自拍说明不用看镜头", b["size"] == "1024x1536" and "does not have to look at the camera" in b["prompt"])
    b = await phone.build("me", "自拍", "真人cos", "竖", "家居服")
    check("真人：家居服原图和 cos 照片都带，不另外带「我」", names(b) == ["outfit_home.jpg", "cos.jpg"] and "COS_FACE" in b["prompt"]
          and "Photorealistic" in b["prompt"], b)
    b = await phone.build("me", "自拍", "真人", "", "房间")
    check("真人：我换成 cos、房间换成真房间", names(b) == ["cos.jpg", "room_real.jpg"] and "ROOM_REAL" in b["prompt"], b)
    b = await phone.build("me at the desk", "其他", "真人", "横", "书桌")
    check("真人：书桌角度留着、再带真房间", names(b) == ["room_desk.jpg", "room_real.jpg"] and b["size"] == "1536x1024", b)
    b = await phone.build("playing a water park game", "截屏", "", "直", "")
    check("截图：iOS、带现在的时间、不加画风", b["shot"] == "截图" and "iOS" in b["prompt"] and "anime illustration" not in b["prompt"]
          and "time " in b["prompt"], b["prompt"])
    b = await phone.build("home screen", "截图", "", "直", "主屏、不存在、没图的")
    check("找不到的素材记下来", names(b) == ["home.jpg"] and b["missing"] == ["不存在", "没图的"], b)
    b = await phone.build("with daddy", "自拍", "", "", "爹爹")
    check("〈主人〉写成「爹爹」也认得", names(b) == ["me.jpg", "owner.jpg"] and b["used"] == ["我", "爹爹"], b)
    b = await phone.build("cat", "", "", "", "")
    check("其他：不带构图说明、不带参考图", b["shot"] == "其他" and not b["refs"] and "first person" not in b["prompt"] and "selfie" not in b["prompt"], b)
    b = await phone.build("x", "", "", "", "", with_self=True)
    check("with_self 照旧带她自己", names(b) == ["me.jpg"])
    phone.person = fake_person
    b = await phone.build("two of us", "自拍", "", "", "20001, 99999", call_of=lambda q: "阿月")
    check("群友写 QQ 号：带 TA 的头像，说明里是称呼", len(b["refs"]) == 2 and "AVATAR 阿月" in b["prompt"] and b["missing"] == ["99999"], b)
    b = await phone.build("crowd", "", "", "", ",".join(str(20000 + i) for i in range(15)))
    check("最多带 10 张", len(b["refs"]) <= ph.MAX_REFS, len(b["refs"]))
    check("Everyone adult", "adult" in b["prompt"])
    del phone.person
    check("清单列出有图的、换成名字", "- 本鱼本人" not in phone.listing() and "- 爹爹：爹爹的样子" in phone.listing()
          and "没图的" not in phone.listing(), phone.listing())
    rec = phone.made("10001")
    check("主人用素材里〈主人〉那张当定做好的", rec and rec.get("preset") and rec["file"].endswith("owner.jpg"), rec)
    check("别人没有定做的", phone.made("20001") is None)

    # ---- draw_tool 把她选的传下去 ----
    seen = []
    async def draw(p, prompt, refs, size=""):
        seen.append((prompt, [Path(r).name for r in refs or []], size)); return b"png"
    p = base_plug(draw)
    r = await p.draw_tool(Ev(), "my legs on the bed", shot="随手拍", shape="直", refs="我,房间")
    check("工具：拍法、形状、参考图都传到画图", seen and seen[-1][1] == ["me.jpg", "room.jpg"] and seen[-1][2] == "1024x1536"
          and "first person" in seen[-1][0], seen[-1:])
    r = await p.draw_tool(Ev(), "x", refs="不存在")
    check("工具：没找到的素材告诉她", "参考素材里没有：不存在" in r, r)
    check("job 记下了拍法（重启后接着画）", True)
    # 说明后面接素材清单
    tool = types.SimpleNamespace(description="BASE")
    tools = types.SimpleNamespace(get_tool=lambda n: tool if n == "lively_draw" else None)
    p._with_listing(tools); p._with_listing(tools)
    check("说明后面接一次清单", tool.description.startswith("BASE\n参考素材") and tool.description.count("参考素材（") == 1, tool.description)


def base_plug(draw):
    cls = next(v for v in vars(cm).values() if isinstance(v, type) and hasattr(v, "draw_tool"))
    p = object.__new__(cls)
    p.s, p.draw_max, p.dir = S(), 20, D
    p.self_look, p.self_ref = "", None
    p.state = {"draw_day": "", "draw_count": 0, "draw_jobs": []}
    p._waiting, p._bg, p._seen = set(), set(), {}
    async def send(umo, chain): SENT.append((umo, chain.parts))
    p.context = types.SimpleNamespace(send_message=send, get_registered_star=base.get_star)
    p._save = lambda: None
    p._log = lambda *a, **k: LOG.append((a, k))
    p._owner_umo = lambda: "x:FriendMessage:10001"
    p._drawing_providers = lambda: [{"model": "m1"}]
    p._call_images = draw
    p.phone = cm.Phone(p)
    p.avatars = cm.Avatars(p)
    return p


SENT, LOG = [], []


class AEv(Ev):
    def __init__(self, qq, mid, gid="30001"):
        super().__init__(qq, gid)
        self.message_obj = types.SimpleNamespace(message_id=mid, raw_message={"message": []})


async def avatars():
    av = ph.Phone  # noqa
    drawn = []
    async def draw(p, prompt, refs, size=""):
        drawn.append((prompt, [Path(r).name for r in refs or []], size)); return b"png"
    p = base_plug(draw)
    async def collect(event, qq): return [("http://x/1", "这条里的图"), ("http://x/2", "10:01 发的那张")]
    async def save_pic(url, path):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"j"); return True
    p.avatars.collect, p.avatars._save_pic = collect, save_pic
    run = p.avatars.run
    r = await run(AEv("20002", 1), "准备", "hair: short pink / outfit: hoodie")
    check("准备：摘要里有图和描述、说要等 TA 确认", "参考图 2 张" in r and "hoodie" in r and "确认" in r and not drawn, r)
    r = await run(AEv("20002", 1), "确认")
    check("同一条消息里确认不算", r.startswith("没画") and "同一条" in r and not drawn, r)
    r = await run(AEv("20003", 2), "确认")
    check("别人确认不了（没有 TA 自己准备的）", r.startswith("没画") and not drawn, r)
    r = await run(AEv("20002", 3), "确认", text="喏")
    check("TA 之后确认了才画：先画一格漫画（带 TA 给的图、方的、描述、名字牌、粗线条）", r.startswith("画好了") and len(drawn) == 2
          and drawn[-2][1] == ["20002_0.jpg", "20002_1.jpg"] and drawn[-2][2] == "1024x1024" and "hoodie" in drawn[-2][0]
          and "one single comic panel" in drawn[-2][0] and "name tag" in drawn[-2][0] and "thick, solid black outlines" in drawn[-2][0],
          (r, drawn[-2:]))
    check("再照那一格画三视图（横的、只带那一格）", drawn[-1][1] == ["20002_panel.png"] and drawn[-1][2] == "1536x1024"
          and "front, side and back" in drawn[-1][0] and "very thick and black" in drawn[-1][0], drawn[-1:])
    check("那一格存下、记进 made", (p.phone.av_dir / "20002_panel.png").exists() and p.phone.avatars()["made"]["20002"]["panel"] == "20002_panel.png")
    check("画好发到这个聊天、带那句话", SENT and SENT[-1][0] == "x:GroupMessage:30001" and SENT[-1][1][0] == ("text", "喏"), SENT[-1:])
    check("存下了、算一次", p.phone.made("20002") and p.phone.avatars()["made"]["20002"]["count"] == 1 and p.state["draw_count"] == 2)
    check("回传说印象卡也会换、卡面正在画", "印象卡上也会换成" in r and "正在画" in r, r)
    for _ in range(5):
        await asyncio.sleep(0)
    check("背景照三视图画卡面：参考图是三视图、横的、半身", drawn[-1][1] == ["20002.png"] and drawn[-1][2] == "1536x1024"
          and "portrait for a profile card" in drawn[-1][0], drawn[-1:])
    check("卡面记进 made、也算一张", p.phone.avatars()["made"]["20002"].get("card") == "20002_card.png"
          and (p.phone.av_dir / "20002_card.png").exists() and p.state["draw_count"] == 3)
    r = await run(AEv("20002", 4), "准备", "hair: blue")
    check("做过一次再准备：要主人同意", r.startswith("没准备") and "做过一次" in r and "爹爹" in r, r)
    r = await run(AEv("20002", 5), "放行", qq="20002")
    check("群友自己放行不了", r.startswith("没放行"), r)
    r = await run(AEv("10001", 6), "放行", qq="20002")
    check("主人放行", r.startswith("放行了"), r)
    r = await run(AEv("20002", 7), "准备", "hair: blue", images="不用")
    check("放行后能再准备、不用图", r.startswith("记下了") and "没有图" in r, r)
    r = await run(AEv("20002", 8), "确认")
    check("第二次画好、计数 2、放行用掉", r.startswith("画好了") and p.phone.avatars()["made"]["20002"]["count"] == 2
          and "20002" not in (p.phone.avatars().get("allow") or {}) and drawn[-2][1] == [] and "Image" not in drawn[-2][0].split("Draw")[0], r)
    check("重做的形象先不带旧卡面（新卡面画好才记上）", "card" not in p.phone.avatars()["made"]["20002"])
    # 卡面画的时候形象又重做了：画好的这张不算
    d = p.phone.avatars(); old_ts = d["made"]["20002"]["ts"]; d["made"]["20002"]["ts"] = old_ts + 1; p.phone.save_avatars(d)
    for _ in range(5):
        await asyncio.sleep(0)
    check("画卡面期间重做了：不记这张", "card" not in p.phone.avatars()["made"]["20002"])
    r = await run(AEv("20004", 9), "看", qq="20002")
    check("看：别人能看 TA 有没有、描述", "有定做的形象" in r and "hair: blue" in r, r)
    r = await run(AEv("20004", 9), "看")
    check("看：自己没有就说照头像画", "QQ 头像" in r, r)
    r = await run(AEv("20005", 10), "准备", "body: loli, small")
    check("描述里有未成年的词不做", r.startswith("没准备") and "成年" in r, r)
    r = await run(AEv("20006", 11), "准备", "")
    check("描述空的不做", r.startswith("没准备"), r)
    # 没画成：不算次数、准备的还在、张数退回
    async def bad(p_, prompt, refs, size=""): raise RuntimeError("safety system rejected")
    p._call_images = bad
    await run(AEv("20007", 12), "准备", "hair: green")
    n = p.state["draw_count"]
    r = await run(AEv("20007", 13), "确认")
    check("没画成：原因、不算次数、准备的还在", r.startswith("没画成") and "审核" in r and p.phone.made("20007") is None
          and "20007" in p.phone.avatars()["pending"] and p.state["draw_count"] == n, r)
    p.phone.avatars_ = None
    d = p.phone.avatars(); d["pending"]["20007"]["ts"] -= 3600; p.phone.save_avatars(d)
    r = await run(AEv("20007", 14), "确认")
    check("准备超过 30 分钟作废", r.startswith("没画") and "作废" in r, r)
    # 卡面没画成：不影响形象、张数退回、记一笔
    calls = []
    async def sheet_ok_card_bad(p_, prompt, refs, size=""):
        calls.append(prompt)
        if "profile card" in prompt:
            raise RuntimeError("HTTP 502")
        return b"png"
    p._call_images = sheet_ok_card_bad
    await run(AEv("20011", 20), "准备", "hair: red")
    n = p.state["draw_count"]
    r = await run(AEv("20011", 21), "确认")
    for _ in range(5):
        await asyncio.sleep(0)
    check("卡面没画成：形象照存、不记卡面、卡面那张退回", r.startswith("画好了") and p.phone.made("20011")
          and "card" not in p.phone.avatars()["made"]["20011"] and p.state["draw_count"] == n + 2
          and any(a[0] == ("avatar_card_fail",) for a in LOG), (r, p.state["draw_count"], n))
    # 沒給圖：外觀照 TA 的 QQ 頭像
    p._call_images = draw
    async def none(event, qq): return []
    p.avatars.collect = none
    r = await run(AEv("20012", 22), "准备", "face: 总是半眯着眼")
    check("没给图：参考图是 QQ 头像、摘要照实说", "QQ 头像" in r and p.phone.avatars()["pending"]["20012"]["qq_ref"]
          and p.phone.avatars()["pending"]["20012"]["imgs"] == ["20012_qq.jpg"], r)
    r = await run(AEv("20012", 23), "确认")
    check("没给图：那一格的提示词说图 1 是 QQ 头像", r.startswith("画好了") and drawn[-2][0].startswith("Image 1 is the QQ avatar")
          and drawn[-2][1] == ["20012_qq.jpg"], drawn[-2:])
    check("画风：Q 版、粗黑线、平涂", "chibi" in drawn[-2][0] and "flat, highly saturated" in drawn[-2][0])
    # 沒放畫風參考時用〈我〉的 Q 版三視圖（self_ref）：排在 TA 的圖後面、只學畫風
    p.self_ref = D / "refs" / "me.jpg"
    await run(AEv("20014", 26), "准备", "hair: z")
    r = await run(AEv("20014", 27), "确认")
    check("没有 avatars/style/ 就用 self_ref 当画风参考（排在 TA 的图后面）", r.startswith("画好了") and drawn[-2][1] == ["20014_qq.jpg", "me.jpg"]
          and "Image 2 is only the art style reference" in drawn[-2][0] and "do not copy" in drawn[-2][0], drawn[-2:])
    # avatars/style/ 有圖就照檔名順序用它們，不用 self_ref
    sd = p.phone.av_dir / "style"; sd.mkdir(exist_ok=True)
    (sd / "2_sheet.png").write_bytes(b"j"); (sd / "1_comic.jpg").write_bytes(b"j"); (sd / "note.txt").write_text("x")
    await run(AEv("20015", 28), "准备", "hair: w")
    await run(AEv("20015", 29), "确认")
    check("有 avatars/style/ 就照顺序用里面的图", drawn[-2][1] == ["20015_qq.jpg", "1_comic.jpg", "2_sheet.png"]
          and "Images 2 to 3 are only the art style reference" in drawn[-2][0], drawn[-2][1])
    for f in sd.iterdir():
        f.unlink()
    sd.rmdir()
    p.self_ref = None
    # 那一格画好了、三视图没画成：不算次数、那一张算进张数、另一张退回
    async def panel_ok_sheet_bad(p_, prompt, refs, size=""):
        if "reference sheet" in prompt:
            raise RuntimeError("HTTP 502")
        return b"png"
    p._call_images = panel_ok_sheet_bad
    await run(AEv("20016", 30), "准备", "hair: v")
    n = p.state["draw_count"]
    r = await run(AEv("20016", 31), "确认")
    check("三视图没画成：照实说那一格画好了、不算次数、只算一张", r.startswith("没画成") and "那一格画好了" in r
          and p.phone.made("20016") is None and "20016" in p.phone.avatars()["pending"] and p.state["draw_count"] == n + 1, (r, p.state["draw_count"], n))
    # 張數只剩一張：不畫，張數不動
    p._call_images = draw
    p.state["draw_count"] = p.draw_max - 1
    k = len(drawn)
    r = await run(AEv("20016", 32), "确认")
    check("今天只剩一张：不画、张数不动", r.startswith("没画") and "两张" in r and len(drawn) == k and p.state["draw_count"] == p.draw_max - 1, r)
    p.state["draw_count"] = 0
    p.avatars.collect = collect
    # 首批照 QQ 頭像先做的：看得到是先做的、TA 自己還能定做一次
    d = p.phone.avatars()
    d["made"]["20013"] = {"file": "20002.png", "desc": "hair: x", "ts": 1, "count": 0, "source": "qq"}
    p.phone.save_avatars(d)
    r = await run(AEv("20004", 24), "看", qq="20013")
    check("看：照 QQ 头像先做的照实说", "QQ 头像先做的" in r and "还没定做过" in r, r)
    r = await run(AEv("20013", 25), "准备", "hair: y")
    check("先做的不算 TA 的那一次：还能准备", r.startswith("记下了"), r)
    r = await run(AEv("20008", 15), "取消")
    check("没准备的取消照实说", "没有在准备" in r, r)
    # 主人不限次数
    p._call_images = draw
    await run(AEv("10001", 16), "准备", "hair: grey-green")
    r1 = await run(AEv("10001", 17), "确认")
    await run(AEv("10001", 18), "准备", "hair: grey-green 2")
    r2 = await run(AEv("10001", 19), "确认")
    check("主人自己不限次数", r1.startswith("画好了") and r2.startswith("画好了"), (r1, r2))
    # 定做过的人：画到 TA 时用定做的
    got = await p.phone.person("20002", "阿蓝")
    check("画到定做过的人用定做的三视图", got and got[0].name == "20002.png" and "character sheet" in got[1], got)


async def comic():
    p = base_plug(None)
    p.self_ref = D / "refs" / "me.jpg"
    async def person(qq, call=""):
        return (D / "refs" / "owner.jpg", f"AV {call}") if qq != "20009" else None
    p.phone.person = person
    sb = {"cast": [{"称呼": "阿月", "look": "red hair"}, {"称呼": "陈", "look": "x"}, {"称呼": "路人", "look": "y"}],
          "panels": [{"scene": "a", "who": ["阿月", "陈"], "me": True, "lines": [], "caption": ""}]}
    cast = [{"qq": "20001", "call": "阿月", "name": "阿月", "n": 3}, {"qq": "10001", "call": "陈", "name": "陈", "n": 2},
            {"qq": "20009", "call": "路人", "name": "路人", "n": 1}, {"qq": "20010", "call": "没出场", "name": "x", "n": 1}]
    refs, idx = await p._comic_refs(sb, cast, True)
    check("群漫画：她自己第一张、出场的人带头像、不在分镜里的不带、拿不到的跳过",
          len(refs) == 3 and idx[""][0] == 1 and idx["阿月"][0] == 2 and idx["陈"][0] == 3 and "路人" not in idx and "没出场" not in idx, idx)
    prompt, me = p._comic_prompt(sb, cast, idx)
    check("提示词：先列参考图、人照那张画", prompt.startswith("Reference images") and "Image 2: AV 阿月." in prompt
          and "阿月: young chibi person, looks like image 2" in prompt and "路人: young chibi person, y" in prompt, prompt[:600])
    plain, _ = p._comic_prompt(sb, cast)
    check("不带参考图时照旧", not plain.startswith("Reference") and "red hair" in plain)


async def looks():
    """10-29：畫到人先照定做形象、沒有才頭像；帶了參考圖的人長相只照圖；refs 能寫名字"""
    import sqlite3
    phone.person = fake_person
    b = await phone.build("two of us", "自拍", "", "", "阿月", qq_of=lambda n: "20001" if n == "阿月" else "")
    check("refs 写名字认成 QQ", any(x.name == "av_20001.jpg" for x in b["refs"]) and ph.LOOK_FROM_REF in b["prompt"], b)
    b = await phone.build("cat", "", "", "", "", qq_of=lambda n: "")
    check("没带人不加那句", ph.LOOK_FROM_REF not in b["prompt"])
    p = base_plug(None)
    p.s.owner = lambda: "10001"
    p.phone = phone
    db = sqlite3.connect(":memory:")
    db.executescript("CREATE TABLE people(qq,name);CREATE TABLE group_cards(qq,gid,card,ts);CREATE TABLE hearts(qq,data);"
                     "INSERT INTO people VALUES('20001','月');INSERT INTO people VALUES('20002','撞名');INSERT INTO people VALUES('20003','撞名');"
                     "INSERT INTO group_cards VALUES('10001','30001','5090-vision pro',0);"
                     "INSERT INTO hearts VALUES('20004','{\"称呼\": \"三毛哥\"}');")
    bond = types.SimpleNamespace(star_cls=types.SimpleNamespace(store=types.SimpleNamespace(db=db, get=lambda q: {"name": "陈"})))
    p.context.get_registered_star = lambda n: bond if n == "astrbot_plugin_lively_bond" else None
    check("名字：只认 QQ 暱称和〈主人〉，群名片、她叫的不认", p._qq_by_name("月") == "20001" and p._qq_by_name("5090-vision pro") == ""
          and p._qq_by_name("三毛哥") == "" and p._qq_by_name("主人") == str(p.s.owner()))
    check("对上好几个、没有的都不认", p._qq_by_name("撞名") == "" and p._qq_by_name("谁") == "")
    al = p._aliases({"qq": "10001", "call": "5090visi", "name": "5090-vision pro"})
    check("修图认人：先 QQ 号、再那个号的暱称，不认名字牌、群名片", al == ["10001", "陈"], al)
    check("她的参考图先用形象「我」那张", p.me_ref() and p.me_ref().name == "me.jpg", p.me_ref())


asyncio.run(run())
asyncio.run(avatars())
asyncio.run(comic())
asyncio.run(looks())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
