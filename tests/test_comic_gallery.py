"""圖冊（11-02）：每張畫好的圖有編號，發圖一定寫編號（lively_comic_post），lively_pic 看圖冊、把圖拿給當前聊天的人看。
起因：11-02 00:17 她要補發「纯良群下午画的群漫画」，lively_comic_post 沒法指定是哪一張，默認發了「最近畫的」——一張說說配圖的自拍。

/usr/local/bin/python3 tests/test_comic_gallery.py（號碼都是假的：10001 主人、20001 群）
"""
import asyncio, json, os, sys, tempfile, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_look as tl  # noqa: E402  借它的假 astrbot
from PIL import Image  # noqa: E402

cm, G, OWNER = tl.cm, tl.G, tl.OWNER
Gallery = cm.Gallery
OWN = f"x:FriendMessage:{OWNER}"
OTHER = "x:FriendMessage:20009"
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        fails.append(name)


def png(name):
    p = tl.TMP / name
    Image.new("RGB", (60, 90), (200, 220, 255)).save(p)
    return str(p)


class Ev(tl.Ev if hasattr(tl, "Ev") else object):
    pass


class E:
    def __init__(self, qq, gid="", umo=None):
        self.qq, self.gid, self.message_str = qq, gid, ""
        self.unified_msg_origin = umo or (f"x:GroupMessage:{gid}" if gid else f"x:FriendMessage:{qq}")
    def get_sender_id(self): return self.qq
    def get_group_id(self): return self.gid


def fresh(root=None):
    c = tl.new()
    c._gallery = Gallery(Path(tempfile.mkdtemp()), root, lambda g: c._names.get(g, g))
    c._refresh_names = lambda: asyncio.sleep(0)
    c._note = lambda t: asyncio.sleep(0)
    c._served = lambda: [G, "20002"]
    c._groups = lambda: [G, "20002"]
    return c


# ---- 一、圖冊本身 ----
P = Gallery.parse_id
check("编号三种写法都认", P("#123") == 123 and P("图123") == 123 and P("123") == 123 and P(" ＃7 ") == 7 and P("图册 123") is None and P("") is None and P("abc") is None)
root = Path(tempfile.mkdtemp())
(root / "画的图").mkdir()
pf = root / "画的图" / "draw_1.png"
Image.new("RGB", (10, 10)).save(pf)
c = fresh(root)
g = c.gallery
a = g.add(str(pf), "拍照", where=OWN, chat="〈主人〉私聊", purpose="说说配图", prompt="selfie", shot="自拍")
b = g.add(png("b.png"), "群漫画单张", group=G, day="2026-11-01", k=1, n=3, title="抢饭")
check("编号递增、不重用", (a, b) == (1, 2) and g.data["seq"] == 2)
check("记相对路径（反斜线）", g.get(a)["file"] == "画的图\\draw_1.png", g.get(a))
txt = (root / "图册.txt").read_text("utf-8")
check("render 写出 图册.txt（新的在上）", txt.index("#2 ") < txt.index("#1 ") and "文件：画的图\\draw_1.png" in txt and "用途：说说配图" in txt, txt)
g.mark_sent(a, "「测试群」", ts=1793580000)
check("mark_sent 记发到哪、状态变已发", g.get(a)["status"] == "已发" and g.get(a)["sent"][0]["to"] == "「测试群」")
g.mark_sent(a, "〈主人〉私聊", show=True)
check("show 不改状态也不算发群", [x for x in g.get(a)["sent"] if not x.get("show")] and g.get(a)["status"] == "已发")
# 超過 30 天的搬走，編號照樣查得到
old = g.add(png("old.png"), "拍照", ts=time.time() - 40 * 86400, where=OWN)
g.add(png("new.png"), "拍照", where=OWN)                  # 這一筆登記時順便搬舊的
check("超过 30 天搬到 gallery-old.jsonl，编号照样查得到", str(old) not in g.data["items"] and g.get(old) and g.get(old)["id"] == old and g.old.exists())
check("recent 按种类、群、地点、天找", [x["id"] for x in g.recent(kind="群漫画单张")] == [b] and g.recent(group=G)[0]["id"] == b
      and all(x["where"] == OWN for x in g.recent(where=OWN)) and g.recent(day="2026-11-01")[0]["id"] == b)
check("page_of：单张找到所在整页", g.page_of(b) is None)
pg = g.add(png("pg.png"), "群漫画整页", group=G, day="2026-11-01", n=3, parent=[b])
check("page_of：单张找到所在整页（有了以后）", g.page_of(b)["id"] == pg and g.page_of(pg)["id"] == pg)
ln = g.line(pg)
check("line 一行说明：编号、种类、群、几张、还没发过", ln.startswith(f"#{pg} 群漫画整页｜") and "3 张" in ln and "还没发过" in ln, ln)

# ---- 二、登記點 ----
# lively_draw：回傳帶編號；主人私聊拍的記 where／chat／purpose
c = fresh()
async def fake_call(p, prompt, refs, size=None): return Path(png("fake.png")).read_bytes()
c._call_images = fake_call
c._drawing_providers = lambda: [{"model": "m"}]
async def build(*a, **k): return {"prompt": "p", "refs": [], "size": "1024x1024", "shot": "自拍", "look": "二次元", "used": [], "missing": [], "people": []}
c.phone = type("Ph", (), {"build": staticmethod(build)})()
c._qq_by_name = lambda n: None
c._call_of = lambda q, d="": ""
c._send_checked = lambda umo, path, text="": asyncio.sleep(0, result="sent")
c.drawn_dir.mkdir(parents=True, exist_ok=True)
c.draw_max = 20; c._waiting, c._seen = set(), {}; c._log = lambda *a, **k: None; c.state.update(draw_day="", draw_count=0)
shoot = {"purpose": "说说配图"}
ok, why = asyncio.run(c._draw_for_inner(OWN, "a selfie", True, "", shoot))
it = c.gallery.get(shoot["_id"])
check("拍照登记：地点、用途、提示词、发到哪", ok and it["kind"] == "拍照" and it["where"] == OWN and it["purpose"] == "说说配图" and it["prompt"] == "a selfie"
      and it["shot"] == "自拍" and it["chat"] == "〈主人〉私聊" and it["status"] == "已发", it)
res = asyncio.run(c._draw_for(OWN, "a selfie", True, None, "", "", "", {}))
check("lively_draw 回传带图册编号", "图册 #" in res, res)
# draw_bytes（说说配图）：落地到画的图、进图册，回的还是 bytes
n0 = len(c.gallery.data["items"])
data = asyncio.run(c.draw_bytes("a cat", False))
d = c.gallery.recent(kind="说说配图")
check("draw_bytes 登记说说配图、回 bytes", isinstance(data, bytes) and d and Path(d[0]["path"]).exists() and d[0]["purpose"] == "说说配图" and len(c.gallery.data["items"]) == n0 + 1, d)
# recent_drawn（说说插件用）改查图冊
got = c.recent_drawn(OWN)
check("recent_drawn 从图册查：两小时内最后一张拍照", got and got["id"] >= shoot["_id"], got)
check("别的聊天没有", c.recent_drawn("x:GroupMessage:39999") is None)

# 群漫畫：_generate 每張登記、_publish 登記整頁；_fix_draw 登記修圖
imgs = [png(f"s{i}.png") for i in range(3)]
c = fresh()
tl.S.conf = {"comic_look": False}
async def topics_ok(h, gid, off): return {"success": True, "topics": tl.TOPICS, "talk": {}}
c._topics = topics_ok
async def mc(gid, topics, talk, until=None):
    return [(Path(imgs[i]).read_bytes(), {"title": f"t{i}"}) for i in range(3)], []
c._my_comic = mc
c.state["inflight"][G] = {"gid": G, "ts": int(time.time())}
c.comics_dir  # 屬性存在
refs, topics, sbs, cast = asyncio.run(c._generate(None, G, 0, True, False, "今天", "u"))
ids = [c.gallery.find_path(r)["id"] for r in refs]
check("_generate：每张一笔「群漫画单张」，带群、天、第几张、标题", [c.gallery.get(i)["kind"] for i in ids] == ["群漫画单张"] * 3
      and [c.gallery.get(i)["k"] for i in ids] == [1, 2, 3] and c.gallery.get(ids[1])["title"] == "t1" and c.gallery.get(ids[0])["group"] == G)
delivered = []
async def deliver(gid, ref, text=""): delivered.append(ref); return "sent"
c._deliver = deliver
c._wait_post = lambda gid="": asyncio.sleep(0)
asyncio.run(c._publish(G, "今天", refs, topics, sbs, cast))
page = c.gallery.recent(kind="群漫画整页")[0]
check("_publish：整页一笔，parent 是各张，记发到哪", page["parent"] == ids and page["n"] == 3 and page["path"].endswith("_all.jpg")
      and page["status"] == "已发" and page["sent"][0]["to"] == "「测试群」" and all(c.gallery.get(i)["status"] == "已发" for i in ids), page)
check("events sent 带 pic", [e for e in tl.events(c) if e["kind"] == "sent"][-1].get("pic") == page["id"])
# 一件事只有一張：那張本身就是整頁
c = fresh()
one = png("one.png")
c.gallery.add(one, "群漫画单张", group=G, day="2026-11-02", k=1, n=1, title="x")
c._deliver = deliver; c._wait_post = lambda gid="": asyncio.sleep(0)
asyncio.run(c._publish(G, "今天", [one], tl.TOPICS))
pg1 = c.gallery.find_path(one, "群漫画整页")
check("只有一张：单张本身记成整页", pg1 and pg1["n"] == 1 and pg1["path"] == one and pg1["status"] == "已发", pg1)

# ---- 三、lively_comic_post：一定寫編號，各種擋住 ----
c = fresh()
selfie_owner = c.gallery.add(png("self.png"), "拍照", where=OWN, chat="〈主人〉私聊", purpose="说说配图", prompt="a candid selfie", shot="自拍")
selfie_other = c.gallery.add(png("self2.png"), "拍照", where=OTHER, chat="别人的私聊里画的")
strip = c.gallery.add(png("st.png"), "群漫画单张", group=G, day="2026-11-01", k=1, n=1, title="抢饭")
page = c.gallery.add(png("pg2.png"), "群漫画整页", group=G, day="2026-11-01", n=1, parent=[strip], status="没发成", failed="QQ 超时")
page_other = c.gallery.add(png("pg3.png"), "群漫画整页", group="20002", day="2026-11-01", n=1, status="没发成")
avatar = c.gallery.add(png("av.png"), "形象", qq="2")
sent = []
async def send_to(gid, path, what, text="", day="", pic=0):
    sent.append((gid, path, pic)); c.gallery.mark_sent(pic, f"「{c._gname(gid)}」") if pic else None; return f"把{what}发到「{c._gname(gid)}」啦～"
c._send_to = send_to
run = lambda **kw: asyncio.run(c.post_tool(E(OWNER), **kw))
r = run(group=G)
check("没写 image 不发、列最近的图（不列形象）", r.startswith("没发：没写发哪张") and f"#{selfie_owner}" in r and f"#{page}" in r and f"#{avatar}" not in r and not sent, r)
r = run(image="9999", group=G)
check("编号不存在", r.startswith("没发：图册里没有 #9999") and not sent, r)
r = run(image="随便", group=G)
check("不是编号", "不是图册编号" in r and not sent, r)
os.remove(c.gallery.get(selfie_other)["path"])
r = run(image=str(selfie_other), group=G)
check("别人私聊里拍的不转群（即使文件还在也一样）", "不是爹爹私聊里画的" in r and not sent, r)
gone = c.gallery.add(str(tl.TMP / "gone.png"), "拍照", where=OWN)
r = run(image=str(gone), group=G)
check("文件被删了：不发、照实说", r.startswith(f"没发：#{gone} 图文件不在了") and not sent, r)
r = run(image=str(strip), group=G)
check("群漫画单张：指去整页", f"这一组的整页是 #{page}" in r and not sent, r)
r = run(image=str(page_other), group=G)
check("别的群的整页：不发", "只能发回它自己的群" in r and not sent, r)
r = run(image=str(page), group="20002")
check("整页给别的群：不发", "只能发回它自己的群" in r and not sent, r)
r = run(image=str(avatar), group=G)
check("形象图不发", "定做形象" in r and not sent, r)
r = run(image=str(selfie_owner))
check("开着两个群没写 group：问发哪个", r.startswith(f"#{selfie_owner} 要发到哪个群") and not sent, r)
r = run(image=f"#{selfie_owner}", group=G, text="补一张")
check("主人私聊拍的照片发到群：回传有编号、种类、用途、之前没发过、拍的是什么", sent[-1] == (G, c.gallery.get(selfie_owner)["path"], selfie_owner)
      and f"发了 #{selfie_owner} 到「测试群」：拍照·自拍" in r and "用途「说说配图」" in r and "之前没发过" in r and "拍的是：a candid selfie" in r, r)
r = run(image=str(page))
check("整页不写群也行（发回它自己的群）；status 变已发", sent[-1][0] == G and sent[-1][2] == page and f"发了 #{page} 到「测试群」：群漫画整页" in r and c.gallery.get(page)["status"] == "已发", r)

# ---- 重放 11-02 00:17：state 有 22:43 的自拍（主人私聊）、纯良那张 pending，调 post_tool(group=纯良) ----
c = fresh()
c._names = {G: "我们是纯良啊啊啊啊啊啊喵", "20002": "桐群"}
selfie = c.gallery.add(png("self3.png"), "拍照", ts=time.time() - 5580, where=OWN, chat="〈主人〉私聊", purpose="说说配图", shot="自拍")
afternoon = c.gallery.add(png("pg4.png"), "群漫画整页", ts=time.time() - 3 * 86400, group=G, day="2026-10-31", n=5, status="没发成", failed="QQ 一直超时")
sent = []
c._send_to = send_to
r = asyncio.run(c.post_tool(E(OWNER), group=G))                    # 当时她没写编号、只写了群
check("重放 00:17：不发，候选里有那张自拍和 10-31 那张群漫画", not sent and f"#{selfie} 拍照" in r and f"#{afternoon} 群漫画整页" in r and "没写发哪张" in r, r)
r = asyncio.run(c.post_tool(E(OWNER), image=str(afternoon), group=G))
check("她写对编号才发：发的是 10-31 那张群漫画", sent and sent[-1][2] == afternoon and "群漫画整页" in r and "10-31" in r, r)

# ---- 四、lively_pic ----
c = fresh()
mine = c.gallery.add(png("m.png"), "拍照", where=OWN, chat="〈主人〉私聊", shot="自拍")
theirs = c.gallery.add(png("t.png"), "拍照", where=OTHER, chat="别人的私聊里画的")
held = c.gallery.add(png("h.png"), "群漫画整页", group=G, day="2026-11-01", n=2, status="画好")
shown = []
async def send_checked(umo, path, text=""): shown.append((umo, path)); return "sent"
c._send_checked = send_checked
r = asyncio.run(c.pic_tool(E(OWNER), action="给这里", image=str(held)))
check("主人那边给这里：发到主人私聊、不算发群、状态不变", shown == [(OWN, c.gallery.get(held)["path"])] and c.gallery.get(held)["status"] == "画好"
      and c.gallery.get(held)["sent"][-1].get("show") and "给这里发了" in r and "不算发群" in r, (r, shown))
r = asyncio.run(c.pic_tool(E(OWNER), action="看"))
check("主人那边看：什么都列", f"#{held}" in r and f"#{theirs}" in r and f"#{mine}" in r, r)
r = asyncio.run(c.pic_tool(E(OWNER), action="看", group=G, kind="群漫画整页"))
check("按群、种类找", f"#{held}" in r and f"#{mine}" not in r, r)
shown.clear()
r = asyncio.run(c.pic_tool(E("20009", umo=OTHER), action="给这里", image=str(mine)))
check("别人那边拿别的聊天的图：不给", r.startswith(f"没给：#{mine}") and not shown, r)
r = asyncio.run(c.pic_tool(E("20009", umo=OTHER), action="给这里", image=str(theirs)))
check("别人那边拿这个聊天画的：给", shown == [(OTHER, c.gallery.get(theirs)["path"])] and "给这里发了" in r, (r, shown))
r = asyncio.run(c.pic_tool(E("20009", umo=OTHER), action="看"))
check("别人那边看：只列能拿的", f"#{theirs}" in r and f"#{mine}" not in r and f"#{held}" not in r, r)
shown.clear()
GU = f"x:GroupMessage:{G}"
r = asyncio.run(c.pic_tool(E("30001", gid=G, umo=GU), action="给这里", image=str(held)))
check("群里拿还没发到这个群的群漫画：不给", r.startswith(f"没给：#{held}") and not shown, r)
c.gallery.mark_sent(held, "「测试群」", umo=GU)
r = asyncio.run(c.pic_tool(E("30001", gid=G, umo=GU), action="给这里", image=str(held)))
check("已经发到这个群的：群里的人也能拿", shown == [(GU, c.gallery.get(held)["path"])], r)
# 主人在群里叫她：「主人那边全拿」指主人的私聊，群里跟别人一样
shown.clear()
unsent = c.gallery.add(png("u.png"), "群漫画整页", group="20002", day="2026-11-02", n=1, status="等主人看")
for pid_, why_ in ((theirs, "别人私聊拍的"), (unsent, "还没发的整页"), (mine, "主人私聊拍的")):
    r = asyncio.run(c.pic_tool(E(OWNER, gid=G, umo=GU), action="给这里", image=str(pid_)))
    check(f"主人在群里给这里{why_}：不给", r.startswith(f"没给：#{pid_}") and not shown, r)
r = asyncio.run(c.pic_tool(E(OWNER, gid=G, umo=GU), action="看"))
check("主人在群里看：只列这个群能拿的（已发到这个群的整页），不列别的聊天的", f"#{held}" in r and f"#{theirs}" not in r and f"#{mine}" not in r and f"#{unsent}" not in r, r)
# 拼不起来的整页，给这里时重拼一次
c2 = fresh()
s1, s2 = png("n1.png"), png("n2.png")
i1 = c2.gallery.add(s1, "群漫画单张", group=G, day="2026-11-02", k=1, n=2); i2 = c2.gallery.add(s2, "群漫画单张", group=G, day="2026-11-02", k=2, n=2)
pgx = c2.gallery.add(s1, "群漫画整页", group=G, day="2026-11-02", n=2, parent=[i1, i2], need_combine=True, status="没发成", failed="拼不成")
c2._send_checked = send_checked; shown.clear()
asyncio.run(c2.pic_tool(E(OWNER), action="给这里", image=str(pgx)))
check("没拼成的整页给这里时重拼", c2.gallery.get(pgx)["need_combine"] is False and shown and shown[0][1].endswith("_all.jpg"), (shown, c2.gallery.get(pgx)))

# ---- 五、補登近 7 天的舊圖 ----
c = fresh()
dd = c.drawn_dir; dd.mkdir(parents=True, exist_ok=True)
cd = c.comics_dir / G; cd.mkdir(parents=True, exist_ok=True)
now = time.time()
def mk(path, age_days=0.5):
    Image.new("RGB", (8, 8)).save(path)
    os.utime(path, (now - age_days * 86400,) * 2)
    return str(path)
d1 = mk(dd / "draw_20261101_224348.png", 0.5)
mk(dd / "draw_20261020_000000.png", 12)
sa = mk(cd / f"comic_{G}_20261031_1401_1.png", 1); sb2 = mk(cd / f"comic_{G}_20261031_1401_2.png", 1)
whole = mk(cd / f"comic_{G}_20261031_1401_all.jpg".replace(".jpg", ".png"), 1)
Path(whole).rename(cd / f"comic_{G}_20261031_1401_all.jpg"); whole = str(cd / f"comic_{G}_20261031_1401_all.jpg")
mk(cd / f"comic_{G}_20261030_1401_1.png", 12)
c.events_file.write_text(json.dumps({"kind": "draw", "ts": int(now - 0.5 * 86400 + 20), "umo": OWN, "prompt": "A candid phone selfie", "shot": "自拍"}) + "\n"
                         + json.dumps({"kind": "sent", "ts": int(now - 86000), "path": whole, "group": G}) + "\n", "utf-8")
c.state = {"pending": {}, "inflight": {}}
c._save = lambda: None
c._backfill_gallery()
items = c.gallery.data["items"].values()
selfie_b = next(x for x in items if x["path"] == d1)
check("补登：近 7 天的拍照，提示词和地点从 events 对时间配上", selfie_b["kind"] == "拍照" and selfie_b["where"] == OWN and selfie_b["prompt"] == "A candid phone selfie", selfie_b)
check("补登：超过 7 天的不补", not any("20261020" in x["path"] or "20261030" in x["path"] for x in items))
pgb = next(x for x in items if x["kind"] == "群漫画整页")
check("补登：_all 是整页，parent 是两张，从 sent 记录标已发", pgb["path"] == whole and len(pgb["parent"]) == 2 and pgb["n"] == 2 and pgb["group"] == G
      and pgb["day"] == "2026-10-31" and pgb["status"] == "已发", pgb)
check("补登：对上 draw 记录的拍照记成发过", selfie_b["status"] == "已发" and selfie_b["sent"][0]["to"] == "〈主人〉私聊", selfie_b)
n1 = len(c.gallery.data["items"]); c._backfill_gallery()
check("补登只做一次", len(c.gallery.data["items"]) == n1)


# 线上真实例子（纯良 20000002，10-30）：原图 2143_1..4，修图 2145_1／2146_2／2148_3／2152_4，整页名字取自 2145 那张修过的
c = fresh()
Z = "20000002"
c._names = {Z: "我们是纯良"}
zd = c.comics_dir / Z; zd.mkdir(parents=True, exist_ok=True)
now = time.time()
def mk2(name, age=2.0):
    f = zd / name
    Image.new("RGB", (8, 8)).save(f, "JPEG" if name.endswith(".jpg") else "PNG")
    os.utime(f, (now - age * 86400,) * 2)
    return str(f)
for k in range(1, 5):
    mk2(f"comic_{Z}_20261030_2143_{k}.png")
fx = [mk2(f"comic_{Z}_20261030_{t}_{k}_fix1.png") for t, k in (("2145", 1), ("2146", 2), ("2148", 3), ("2152", 4))]
allp = mk2(f"comic_{Z}_20261030_2145_all.jpg")
mk2(f"comic_{Z}_20261030_2147_2_fix2.png")              # 第 2 张又修了一次：取最后一次当 final
c.events_file.write_text(json.dumps({"kind": "sent", "ts": int(now - 2 * 86400 + 900), "path": allp, "group": Z}) + "\n", "utf-8")
c.state = {"pending": {}, "inflight": {}}; c._save = lambda: None
c._backfill_gallery()
its = [x for x in c.gallery.data["items"].values() if x.get("group") == Z]   # 同一个临时目录里别的段落也留了文件，只看纯良
strips_ = [x for x in its if x["kind"] == "群漫画单张"]; fixes_ = [x for x in its if x["kind"] == "修图"]; pages_ = [x for x in its if x["kind"] == "群漫画整页"]
check("10-30 纯良：4 张单张、1 个整页 n=4、parent 是 4 张单张", len(strips_) == 4 and len(pages_) == 1 and pages_[0]["n"] == 4
      and pages_[0]["parent"] == [x["id"] for x in sorted(strips_, key=lambda x: x["k"])] and all(x["day"] == "2026-10-30" for x in its), (len(strips_), len(fixes_), pages_))
check("每张的修图挂在它的原图上", len(fixes_) == 4 and sorted(x["k"] for x in fixes_) == [1, 2, 3, 4]
      and all(x["parent"] == next(s0["id"] for s0 in strips_ if s0["k"] == x["k"]) for x in fixes_), fixes_)
check("第 2 张修了两次：登记的是最后一次（fix2）", next(x for x in fixes_ if x["k"] == 2)["path"].endswith("_2147_2_fix2.png"), fixes_)
check("events 发过的那页是已发、各张单张也已发", pages_[0]["status"] == "已发" and all(x["status"] == "已发" for x in strips_), pages_)

print(f"\n{'all ok' if not fails else f'{len(fails)} FAIL: {fails}'}")
sys.exit(1 if fails else 0)
