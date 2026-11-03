"""群漫畫一件事一張四格（10-30 用戶給了一張四格漫畫當參考）：她挑幾件事、一張一張看、每張各能改，到點照順序發；
群漫畫不算進每天的張數上限（10-31 起，只記數）。
/usr/local/bin/python3 tests/test_comic_strips.py（號碼都是假的）"""
import asyncio, sys, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_look as tl  # noqa: E402  借它的假 astrbot
from PIL import Image  # noqa: E402
cm, G = tl.cm, tl.G
CAST = [{"call": "小凛", "name": "小凛🍥", "qq": "2"}]
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        fails.append(name)


imgs = []
for i in range(3):
    p = tl.TMP / f"strip_{i}.png"
    Image.new("RGB", (100, 150), (200, 200 + i * 20, 255)).save(p)
    imgs.append(str(p))
SBS = [{"cast": [{"称呼": "小凛", "look": "pink"}], "title": t, "topic": t,
        "panels": [{"scene": "x", "who": ["小凛"], "me": False, "lines": [], "caption": ""}] * 3} for t in ("抢饭", "死机", "唱歌")]


def sent_g():
    return [s[1] for s in tl.SENT if s[0].endswith(G)]


# ---- 三張：一張一張看，看的時候說是第幾張、畫的是什麼；拼成一張大圖發，圖發完之後另外說話（10-31 _wrap_say，11-02 起拼不了也不一張一張發）----
tl.SENT.clear(); c = tl.new(); tl.S.conf = {}
tl.Prov.replies = ['{"看到的": "抢饭", "text": "第一件", "why": "好"}', '{"看到的": "死机", "text": "", "why": "好"}',
                   '{"看到的": "唱歌", "text": "第三件", "why": "好"}']
r = asyncio.run(c._publish(G, "今天", imgs, tl.TOPICS, SBS, CAST))
gs = sent_g()
check("三张拼成一张发、话在图后面", r == "已自动发群" and len(gs) == 2 and gs[0][0][0] == "img" and gs[0][0][1].endswith("_all.jpg")
      and gs[1] == [("text", "第一件")], gs)
sy = [x["system"] for x in tl.Prov.seen[-4:-1]]  # 最後一個是图发完后写话那次
check("看的时候说是第几张、画的是什么", "的第 2 张（一共 3 张，一件事一张），这张画的是「死机」" in sy[1], sy[1])
check("只核对这一张", "这次只看第 3 张" in tl.Prov.seen[-2]["prompt"])
check("每张缩图各一张", tl.Prov.seen[-2]["images"][0].endswith(f"comic_look_{G}_3.jpg"))
sent = [e for e in tl.events(c) if e["kind"] == "sent"]
check("sent 每张一行，带第几张和标题", [(e["k"], e["title"]) for e in sent[-3:]] == [(1, "抢饭"), (2, "死机"), (3, "唱歌")], sent)
ob = [d for d in tl.outbox() if d["umo"].endswith(G)][-1]["text"]
check("记一笔：几张拼成一张、配的话", "3 张拼成的一张大图" in ob and "「第一件」" in ob, ob)

# ---- 拼成一張大圖發（10-30）：原尺寸不縮；看的時候照實說會拼 ----
tl.SENT.clear(); c = tl.new(); tl.S.conf = {}
tl.Prov.replies = ['{"看到的": "抢饭", "text": "第一件", "why": "好"}', '{"看到的": "死机", "text": "", "why": "好"}',
                   '{"看到的": "唱歌", "text": "第三件", "why": "好"}']
r = asyncio.run(c._publish(G, "今天", imgs, tl.TOPICS, SBS, CAST))
gs = sent_g()
check("拼成一张发", r == "已自动发群" and gs[0][-1][1].endswith("_all.jpg"), gs)
with Image.open(gs[0][-1][1]) as im:
    check("原尺寸三张一行", im.width >= 300 and im.height >= 150 and im.width < 400, im.size)
check("看的时候说会拼成一张", "今天这 3 张会照顺序拼成一张大图" in tl.Prov.seen[-2]["system"])
sent = [e for e in tl.events(c) if e["kind"] == "sent"][-3:]
check("sent 每张一行、记原图", [e.get("strip") for e in sent] == imgs and len({e["path"] for e in sent}) == 1, sent)
ob = [d for d in tl.outbox() if d["umo"].endswith(G)][-1]["text"]
check("记一笔：拼成的大图", "3 张拼成的一张大图" in ob, ob)
# 拼不起来：不一张一张发，整组留着（11-02）
tl.SENT.clear(); c3 = tl.new(); tl.S.conf = {"comic_look": False}
for i, pth in enumerate(imgs, 1):   # 真实流程里 _generate 已经登记了各张
    c3.gallery.add(pth, "群漫画单张", group=G, day="2026-11-02", k=i, n=3, title=f"t{i}")
c3._combine = lambda gid, refs: ""
c3._served = lambda: [G]; c3._groups = lambda: [G]
c3._combine_why = "cannot identify image"
delivered = []
async def spy(gid, ref, text=""): delivered.append(ref); return "sent"
c3._deliver = spy
r = asyncio.run(c3._publish(G, "今天", imgs, tl.TOPICS, SBS, CAST))
pend = c3.state["pending"][G]
check("拼不起来一张都不发", delivered == [] and not sent_g() and "这 3 张" in r and "拼不成一张大图" in r, (r, delivered))
check("整组留着、记着各张", pend["strips"] == imgs and pend["path"] == imgs[0] and "拼不成" in pend["failed"], pend)
check("记 send_fail", any(e["kind"] == "send_fail" and e.get("ks") == [1, 2, 3] for e in tl.events(c3)))
page_id3 = c3.gallery.find_path(imgs[0], "群漫画整页")["id"]
pg = c3.gallery.get(page_id3)
check("图册里整页记着没拼成", pg["need_combine"] is True and pg["status"] == "没发成" and len(pg["parent"]) == 3 and "拼不成" in pg["failed"], pg)
got = []
async def send_to(gid, path, what, text="", day="", pic=0): got.append(path); return "发到了"
c3._send_to = send_to
async def nothing(): pass
c3._refresh_names = nothing
WHOLE = tl.TMP / "whole_all.jpg"; WHOLE.write_bytes(Path(imgs[0]).read_bytes())
c3._combine = lambda gid, refs: str(WHOLE)   # lively_comic_post 再拼一次，拼得起来才发
asyncio.run(c3.post(image=str(page_id3)))
check("post 重拼成功发整页", got == [str(WHOLE)] and G not in c3.state["pending"], got)
c3.state["pending"][G] = pend
c3.gallery.update(page_id3, need_combine=True, status="没发成", path=imgs[0])
c3._combine = lambda gid, refs: ""
got.clear(); r = asyncio.run(c3.post(image=f"#{page_id3}"))
check("post 重拼还是不行：不发、留着", got == [] and "拼不成一张大图" in r and c3.gallery.get(page_id3)["status"] == "没发成"
      and G in c3.state["pending"] and c3.state["pending"][G]["strips"] == imgs, (r, got))
check("四张两行两列", Image.open(c._combine(G, imgs + imgs[:1])).size == (2 * 100 + 3 * 16, 2 * 150 + 3 * 16))
c2 = tl.new(); tl.S.conf = {"comic_look": False}
async def fail_all(gid, ref, text=""): raise RuntimeError("boom")
c2._deliver = fail_all
r = asyncio.run(c2._publish(G, "今天", imgs, tl.TOPICS, SBS, CAST))
pend = c2.state["pending"][G]
check("大图没发成留着", "拼好的大图发到群里没发成" in r and pend["path"].endswith("_all.jpg") and "more" not in pend, (r, pend))

# ---- 每張各改各的：第二張改過一次，下一張還能改兩次 ----
c = tl.new(); tl.S.conf = {"comic_fix_max": 2}
c._post_ts = lambda *a: time.time() + 3600
async def no_wait(*a): pass
c._wait_post = no_wait
DRAWN = []
async def draw_any(gid, prompt, ref, size, measure=True):
    DRAWN.append(ref); return Path(imgs[0]).read_bytes()
c._draw_any = draw_any
c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "auto": True, "paths": list(imgs[:2]), "sbs": SBS[:2], "cast": CAST}
tl.Prov.replies = ['{"看到的": "a", "text": "一", "why": "好"}',
                   '{"看到的": "b", "怎么改": "修图", "改什么": "第二格名字牌", "text": "", "why": "错"}',
                   '{"看到的": "b2", "用哪张": "改过的", "text": "二", "why": "好"}']
asyncio.run(c._publish(G, "今天", imgs[:2], tl.TOPICS, SBS[:2], CAST))
sy = [x["system"] for x in tl.Prov.seen[-4:-1]]  # 最後一個是图发完后写话那次
check("第一张、第二张都说还能改 2 次", "还能改 2 次" in sy[0] and "还能改 2 次" in sy[1], sy[:2])
job = c.state["inflight"][G]
check("改的记在第二张", job["fixes"] == {"1": 1} and job["paths"][1].endswith("_2_fix1.png") and job["paths"][0] == imgs[0], job)
check("改过的那张拼进去发出去", sent_g()[0][-1][1].endswith("_all.jpg") and [e.get("strip") for e in tl.events(c) if e["kind"] == "sent"][-2:] == job["paths"], (sent_g(), job["paths"]))
check("改一次算一张", c.state["img_n"] == 1, c.state)

# ---- 群漫畫不算進每天的張數上限（10-31 用戶定）：記了很多張照樣改、照樣畫 ----
c = tl.new(); tl.S.conf = {"comic_daily_images": 3}
c.state["img_day"], c.state["img_n"] = cm.datetime.now(cm.TZ).strftime("%Y-%m-%d"), 50
c._post_ts = lambda *a: time.time() + 3600
c._wait_post = no_wait
c._draw_any = draw_any
tl.Prov.replies = ['{"看到的": "a", "怎么改": "修图", "改什么": "第一格", "text": "", "why": "x"}',
                   '{"看到的": "a", "用哪张": "改过的", "text": "照发", "why": "好"}']
asyncio.run(c._publish(G, "今天", imgs[:1], tl.TOPICS, SBS[:1], CAST))
fx = [e for e in tl.events(c) if e["kind"] == "fix"][-1]
check("记了 50 张照样改", fx["ok"] is not False and c.state["img_n"] == 51, (fx, c.state["img_n"]))

# ---- 最多畫幾件：comic_strips_max，不看剩幾張 ----
c = tl.new(); tl.S.conf = {"comic_strips_max": 6}
c.state["img_day"], c.state["img_n"] = cm.datetime.now(cm.TZ).strftime("%Y-%m-%d"), 99
most, why = c._strips_most(G)
check("一个群最多 6 件，不看今天画了几张", most == 6 and "最多画 6 件" in why and "还能画" not in why, (most, why))

# ---- 被張數擋住的照實說是額度 ----
r, again = cm.comic_fail_reason("今天群漫画的 50 张已经画完了")
check("张数挡住说是额度、不再试", "额度" in r and "中转站" not in r.replace("不是画图那边坏了", "") and again is False, r)

# ---- 畫：有一張沒畫成就跳過、不算張數 ----
c = tl.new(); tl.S.conf = {}
async def sb_fake(t, cast, **k):
    return [dict(x) for x in SBS]
c._storyboard = sb_fake
c._cast = lambda t, talk: CAST
async def refs(sb, cast, w): return [], {}
c._comic_refs = refs
n = {"i": 0}
async def draw2(gid, prompt, ref, size, measure=True):
    n["i"] += 1
    if n["i"] == 2:
        raise RuntimeError("gpt-image-2.5: rejected by the safety system")
    return Path(imgs[0]).read_bytes()
c._draw_any = draw2
items, cast = asyncio.run(c._my_comic(G, [], {}))
check("三张里一张没画成：留两张", [sb["title"] for _, sb in items] == ["抢饭", "唱歌"], items)
check("没画成的不算张数", c.state["img_n"] == 2, c.state)
check("记 strip_fail", any(e["kind"] == "strip_fail" and e["k"] == 2 for e in tl.events(c)))

# ---- 存檔：一張一個檔，inflight 帶 paths、sbs ----
async def topics_ok(h, gid, off): return {"success": True, "topics": tl.TOPICS, "talk": {}}
c = tl.new(); tl.S.conf = {}
c._topics = topics_ok
async def mc(gid, topics, talk, until=None): return [(Path(imgs[0]).read_bytes(), SBS[0]), (Path(imgs[1]).read_bytes(), SBS[1])], CAST
c._my_comic = mc
c.state["inflight"][G] = {"gid": G, "ts": 1}
out = asyncio.run(c._generate(None, G, 0, True, False, "今天", "u"))
job = c.state["inflight"][G]
check("两张两个档", len(out[0]) == 2 and out[0][0].endswith("_1.png") and out[0][1].endswith("_2.png") and job["paths"] == out[0]
      and job["sbs"] == SBS[:2] and job["cast"] == CAST, (out, job))
r = asyncio.run(c._generate(None, G, 0, False, True, "今天", "u"))
check("试画回所有档", r.startswith("试画好了：") and r.count("comic_test_") == 2, r)

# ---- 只有一張時沒發成：留著，lively_comic_post 發（不拼）----
c = tl.new(); tl.S.conf = {"comic_look": False}
c._served = lambda: [G]; c._groups = lambda: [G]
async def bad_deliver(gid, ref, text=""): raise RuntimeError("boom")
c._deliver = bad_deliver
r = asyncio.run(c._publish(G, "今天", imgs[:1], tl.TOPICS, SBS[:1], CAST))
pend = c.state["pending"][G]
check("一张没发成留着", "发到群里没发成" in r and pend["path"] == imgs[0] and "strips" not in pend, (r, pend))
got = []
async def send_to2(gid, path, what, text="", day="", pic=0): got.append(path); return "发到了"
c._send_to = send_to2
c._refresh_names = nothing
asyncio.run(c.post(image=str(c.gallery.find_path(imgs[0], "群漫画整页")["id"])))
check("post 发留着的那张", got == [imgs[0]] and G not in c.state["pending"], got)

print(f"\n{'all ok' if not fails else f'{len(fails)} FAIL: {fails}'}")
