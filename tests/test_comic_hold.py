"""先看再發（11-02）：〈主人〉說某個群的群漫畫先給他看，她在主人私聊調 lively_comic_hold，下一組畫好存著不發，點頭了才發。
起因：11-01 22:49 主人說「纯良的先发给我 我确认后再发群」，她答應了，補畫路上卻沒有任何能停住的地方，22:54 照發。

/usr/local/bin/python3 tests/test_comic_hold.py（號碼都是假的：10001 主人、20001 群）
"""
import asyncio, json, sys, tempfile, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_look as tl  # noqa: E402  借它的假 astrbot
from PIL import Image  # noqa: E402

cm, G, OWNER = tl.cm, tl.G, tl.OWNER
OWN = f"x:FriendMessage:{OWNER}"
GU = f"x:GroupMessage:{G}"
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        fails.append(name)


def png(name):
    p = tl.TMP / name
    Image.new("RGB", (60, 90), (200, 220, 255)).save(p)
    return str(p)


class E:
    def __init__(self, qq, umo):
        self.qq, self.unified_msg_origin, self.message_str = qq, umo, ""
    def get_sender_id(self): return self.qq
    def get_group_id(self): return ""


imgs = [png(f"h{i}.png") for i in range(3)]
SBS = [{"title": f"t{i}", "cast": [], "panels": []} for i in range(3)]


def fresh():
    c = tl.new()
    c.events_file = Path(tempfile.mkdtemp()) / "events.jsonl"     # 每个测试各一份记录，免得别的测试发过的算进「今天已经发了」
    c._gallery = cm.Gallery(Path(tempfile.mkdtemp()), None, lambda g: c._names.get(g, g))
    c._refresh_names = lambda: asyncio.sleep(0)
    c._note = lambda t: asyncio.sleep(0)
    c._served = lambda: [G, "20002"]
    c._groups = lambda: [G, "20002"]
    c._wait_post = lambda gid="": asyncio.sleep(0)
    c.state.update(hold={}, held={}, last_day={}, makeup={}, off_groups=[])
    c.delivered, c.woken, c.wrapped = [], [], []
    async def deliver(gid, ref, text=""): c.delivered.append((gid, ref)); return "sent"
    c._deliver = deliver
    async def wake(facts): c.woken.append(facts); return True
    c._wake_owner = wake
    async def wrap(gid, label, seen): c.wrapped.append((label, seen)); return ["今天就这些"]
    c._wrap_say = wrap
    for i, p in enumerate(imgs, 1):
        c.gallery.add(p, "群漫画单张", group=G, day=c._day_of(0), k=i, n=3, title=f"t{i - 1}")
    tl.S.conf = {"comic_look": False}
    return c


def publish(c, redo=False):
    c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "offset": 0}
    return asyncio.run(c._publish(G, "今天", imgs, tl.TOPICS, SBS, []))


tool = lambda c, action, umo=OWN, group=G: asyncio.run(c.hold_tool(E(OWNER, umo), group, action))

# ---- 一、先看：定時那組畫好存著不發 ----
c = fresh()
r = tool(c, "先看")
check("先看：设好、说今天的还没画好", r.startswith("设好了：") and G in c.state["hold"] and "还没画好" in r, r)
r = publish(c)
page = c.gallery.recent(kind="群漫画整页")[0]
h = c.state["held"][G]
check("检查点：没发、整页进图册状态等主人看、held 存着各张看图写的", r == cm.HELD_MSG and not c.delivered and page["status"] == "等主人看"
      and page["n"] == 3 and h["page"] == page["id"] and [x["title"] for x in h["looks"]] == ["t0", "t1", "t2"], (r, h, page))
check("一次：存住后 hold 自己没了", G not in c.state["hold"])
check("叫她一轮：事实带整页编号和 lively_pic", c.woken and f"图册 #{page['id']}" in c.woken[0] and "lively_pic" in c.woken[0], c.woken)
check("events 记 held", [e for e in tl.events(c) if e["kind"] == "held"], tl.events(c)[-3:])
check("_daily 不再另外报", cm.HELD_MSG in cm.DONE_MSGS)
r = tool(c, "先看")
check("已经存着：照实说，不重设", "已经画好存着了" in r and G not in c.state["hold"], r)
# 一次：存住之后下一組直接發
c.state["held"].pop(G); c.gallery.set_status(page["id"], "画好")
r = publish(c)
check("一次：第二组直接发", r == "已自动发群" and c.delivered, (r, c.delivered))

# ---- 二、畫到一半才設 hold，照樣存住（11-01 22:49 那種）----
c = fresh()
async def look_sets_hold(gid, label, ref, topics, used):
    c.state["hold"][G] = {"since": int(time.time())}      # 主人在她看圖的時候才說
    return (ref, None, [], "")
c._look_fix = look_sets_hold
r = publish(c)
check("画到一半才设 hold 也存住", r == cm.HELD_MSG and not c.delivered, (r, c.delivered))

# ---- 三、lively_comic_post 碰存著的：不發 ----
c = fresh()
tool(c, "先看"); publish(c)
pid = c.state["held"][G]["page"]
sent = []
async def send_to(gid, path, what, text="", day="", pic=0): sent.append(gid); return "发到了"
c._send_to = send_to
r = asyncio.run(c.post_tool(E(OWNER, OWN), image=str(pid), group=G))
check("post 碰存着的：不发，说放行在主人私聊用 lively_comic_hold", not sent and "先看" in r and "lively_comic_hold" in r, r)

# ---- 四、lively_pic 給這裡：存著的拿給主人看，hold／held 不變 ----
shown = []
async def send_checked(umo, path, text=""): shown.append((umo, path)); return "sent"
c._send_checked = send_checked
before = json.dumps(c.state["held"], sort_keys=True)
r = asyncio.run(c.pic_tool(E(OWNER, OWN), action="给这里", image=str(pid)))
check("存着的 lively_pic 给这里：发到主人私聊，held 不变，说不算发群", shown and shown[0][0] == OWN and json.dumps(c.state["held"], sort_keys=True) == before
      and "不算发群" in r and c.gallery.get(pid)["status"] == "等主人看", (r, shown))

# ---- 五、放行 ----
r = tool(c, "放行")
pg = c.gallery.get(pid)
check("放行：发整页、每张记 sent（带 pic、released）、跑 _wrap_say、held 清掉", len(c.delivered) == 1 and c.delivered[0][0] == G and pg["status"] == "已发"
      and G not in c.state["held"] and c.wrapped and [x[0]["title"] for x in c.wrapped[0][1]] == ["t0", "t1", "t2"]
      and len([e for e in tl.events(c) if e["kind"] == "sent" and e.get("released")]) == 3, (r, c.delivered, pg))
check("放行的回传：发了 #编号、配的话", r.startswith(f"发了 #{pid} 到「测试群」") and "今天就这些" in r, r)
check("放行后各张单张也是已发", all(c.gallery.get(i)["status"] == "已发" for i in pg["parent"]))
r = tool(c, "放行")
check("没存着再放行：只撤掉先看", "没有存着的" in r and len(c.delivered) == 1, r)

# ---- 六、不發了 ----
c = fresh()
tool(c, "先看"); publish(c)
pid = c.state["held"][G]["page"]
r = tool(c, "不发了")
check("不发了：不发、图册留着（画好）、held 清掉", not c.delivered and c.gallery.get(pid)["status"] == "画好" and G not in c.state["held"] and f"#{pid}" in r, (r, c.gallery.get(pid)))
c._send_to = send_to; sent.clear()
r = asyncio.run(c.post_tool(E(OWNER, OWN), image=str(pid), group=G))
check("之后 lively_comic_post 写编号发得出去", sent == [G] and r.startswith(f"发了 #{pid}"), r)
tool(c, "先看")
r = tool(c, "不发了")
check("没存着、只撤先看", G not in c.state["hold"] and "先看的设置撤掉了" in r, r)

# ---- 七、只認主人私聊 ----
c = fresh()
r = tool(c, "先看", umo=GU)
check("主人在群里说的不算（她在群里调也不认）", r.startswith("没动：这件事只认在和") and G not in c.state["hold"], r)
r = tool(c, "先看", umo="x:FriendMessage:20009")
check("别人私聊里不认", r.startswith("没动") and G not in c.state["hold"], r)
class Tools:
    def __init__(self): self.t = {"lively_comic_hold", "lively_comic_post"}
    def get_tool(self, k): return k in self.t
    def remove_tool(self, k): self.t.discard(k)
class Ev2(E):
    def get_group_id(self): return ""
for umo, want in ((OWN, True), (GU, False), ("x:FriendMessage:20009", False)):
    req = type("R", (), {})(); req.func_tool = Tools(); req.extra_user_content_parts = []
    c._draw_denied = lambda qq: ""
    asyncio.run(c.hide_tools(Ev2(OWNER if umo == OWN else "20009", umo), req))
    check(f"lively_comic_hold 只在主人私聊里看得到：{umo[-12:]}", ("lively_comic_hold" in req.func_tool.t) == want, req.func_tool.t)

# ---- 八、補畫：redo_tool 的說法、同一天已有存著的、again ----
c = fresh()
c.state["enabled"] = True
started = []
async def redo_run(gid, offset, redo, done_path=""): started.append(gid)
c._redo_run = redo_run
c.state["last_day"][G] = c._day_of(0)
class Ev3(E):
    def get_group_id(self): return ""
r = asyncio.run(c.redo_tool(Ev3(OWNER, OWN), G, "今天"))
check("补画开画时没 hold：照旧说看完就发到群", "看完就连同你配的话发到" in r, r)
tool(c, "先看")
c.state["makeup"].clear(); c.state["last_day"][G] = c._day_of(0)
r = asyncio.run(c.redo_tool(Ev3(OWNER, OWN), G, "今天"))
check("补画开画时 hold 着：说画好先存着等主人放行", "画好先存着，等〈主人〉放行" in r and "看完就连同" not in r, r)
publish(c)
r = asyncio.run(c.redo_tool(Ev3(OWNER, OWN), G, "今天"))
check("同一天已有存着的：没画，指去 lively_comic_hold，要重画写 again", r.startswith("没画：") and "lively_comic_hold" in r and "again" in r and "存着" in r, r)
c.state["makeup"].clear()
r = asyncio.run(c.redo_tool(Ev3(OWNER, OWN), G, "今天", True))
check("again：重画的这组也先存着（hold 重设）", G in c.state["hold"] and not r.startswith("没画：画好了存着"), (r, c.state["hold"]))
old_page = c.state["held"][G]["page"]
c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "offset": 0}
imgs2 = [png(f"again{i}.png") for i in range(3)]       # 重画是新的文件
for i, p in enumerate(imgs2, 1):
    c.gallery.add(p, "群漫画单张", group=G, day=c._day_of(0), k=i, n=3, title=f"t{i - 1}")
r = asyncio.run(c._publish(G, "今天", imgs2, tl.TOPICS, SBS, []))
check("again 画好存住后，上一组作废", r == cm.HELD_MSG and c.gallery.get(old_page)["status"] == "被重画取代" and c.state["held"][G]["page"] != old_page)
# _redo_run 的事實
c = fresh()
tool(c, "先看")
async def draw_held(gid, offset, done_path="", redo=None):
    c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "offset": 0}
    return await c._publish(G, "今天", imgs, tl.TOPICS, SBS, [])
c.draw = draw_held
woke = []
async def wake_origin(umo, asker, facts): woke.append(facts); return True
c._wake_origin = wake_origin
asyncio.run(c._redo_run(G, 0, {"origin": OWN, "asker": "〈主人〉", "asker_qq": OWNER, "due": time.time() + 600}))
check("_redo_run：存住的事实交给叫她补画的聊天，不说「已经发到」", woke and "存着没发" in woke[0] and "已经发到" not in woke[0] and "lively_comic_hold" in woke[0], woke)

# ---- 九、重啟：hold 在 state、畫好的 paths 接著發 → 還是存住 ----
c = fresh()
tool(c, "先看")
c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "offset": 0, "auto": False, "paths": list(imgs), "sbs": SBS, "cast": []}
reported = []
c._report = lambda facts: asyncio.sleep(0, result=reported.append(facts))
asyncio.run(c._draw_and_report(G, 0, True, list(imgs)))
check("重启后接着：画好的接着走检查点，存住、不报错", c.state["held"].get(G) and not c.delivered and not reported, (c.state["held"], reported))

# ---- 十、過期 ----
c = fresh()
tool(c, "先看"); publish(c)
pid = c.state["held"][G]["page"]
check("没到期：不动", c._expire_held() == [] and G in c.state["held"])
c.state["held"][G]["ts"] -= cm.HOLD_TTL + 10
c.state["hold"]["20002"] = {"since": time.time() - cm.HOLD_TTL - 10}
out = c._expire_held()
check("到期：不发、状态记下、给她的话说是哪个群哪张、到期不发了", len(out) == 1 and f"#{pid}" in out[0] and "到期不发" in out[0] and c.gallery.get(pid)["status"] == "存放到期没发"
      and G not in c.state["held"] and "20002" not in c.state["hold"] and not c.delivered, out)
c.state["hold"][G] = {"since": time.time() - cm.HOLD_TTL - 10}
check("设了先看一直没用上的，到期也自动没了", not c._hold_active(G))

# ---- 沒用上的「先看」到次日 06:00 自己失效（審查：不能拖到隔天把 22:00 該發的那組攔下來）----
from datetime import datetime, timedelta, timezone
TZ8 = timezone(timedelta(hours=8))
at = lambda d, h, m: datetime(2026, 11, d, h, m, tzinfo=TZ8).timestamp()
c = fresh()
real_time = time.time
try:
    c.state["hold"][G] = {"since": at(2, 23, 0)}                      # 11-02 23:00 主人說先看（今天的已發、之後沒人 again）
    time.time = lambda: at(3, 5, 59)
    check("次日 06:00 前還管", c._hold_active(G))
    time.time = lambda: at(3, 21, 20)                                # 隔天 21:20 定時那組畫完
    r = publish(c)
    check("23:00 設的先看，隔天 21:20 那組照常發", r == "已自动发群" and c.delivered and not c.state["held"] and G not in c.state["hold"], (r, c.delivered))
    c = fresh()
    c.state["hold"][G] = {"since": at(2, 20, 0)}                      # 20:00 設，當晚 22:00 那組
    time.time = lambda: at(2, 21, 40)
    r = publish(c)
    check("20:00 設的先看，當晚那組存住", r == cm.HELD_MSG and not c.delivered, (r, c.delivered))
    c.state["hold"][G] = {"since": at(3, 1, 0)}                       # 凌晨 01:00 設（補昨天的）：當天 06:00 失效
    time.time = lambda: at(3, 5, 0)
    check("凌晨設的當天 06:00 失效（5:00 還管）", c._hold_active(G))
    time.time = lambda: at(3, 6, 1)
    check("凌晨設的當天 06:00 失效（6:01 沒了）", not c._hold_active(G))
    c = fresh()
    c.state["hold"][G] = {"since": at(2, 23, 0)}
    time.time = lambda: at(3, 6, 1)
    check("_expire_held 也清掉沒用上的", c._expire_held() == [] and G not in c.state["hold"])
    c = fresh()
    c.state["enabled"] = True
    c.state["last_day"][G] = c._day_of(0)
    c._day_record = lambda gid, day: {"sent": at(2, 22, 0), "late": False, "redo_sent": 0, "failed": ""}
    time.time = lambda: at(2, 23, 0)
    r = tool(c, "先看")
    check("今天已經發了：回傳照實說只管到明早 6 點、補畫存著、明晚照常發", "已经发到群里了" in r and "先看只管到明早 6 点" in r and "明晚定时的照常发" in r, r)
finally:
    time.time = real_time
# 登記不上圖冊：不 raise、不悄悄丟，回一句當沒畫成報給她
c = fresh()
tool(c, "先看")
c._register_page = lambda *a, **k: 0
r = publish(c)
check("整页进不了图册：不发、不存、hold 清掉、回一句出错（不在 DONE_MSGS，会报给她）", "存的时候出错了" in r and r not in cm.DONE_MSGS and not c.delivered
      and G not in c.state["held"] and G not in c.state["hold"], r)

# ---- 重放 11-01：22:39 開補畫、22:49 設 hold、22:52 畫好 → 22:54 不發群 ----
c = fresh()
c.state["inflight"][G] = {"gid": G, "ts": int(time.time()), "offset": 0, "redo": {"origin": OWN}}     # 22:39 補畫已開
c._redo[G] = {"origin": OWN, "asker": "〈主人〉", "due": time.time() + 600}
r = tool(c, "先看")                                                                                  # 22:49 主人說「先发给我看」
check("重放：画到一半设先看，回传说正在画、画好会存着", "正在画，画好会存着不发" in r and G in c.state["hold"], r)
r = publish(c)                                                                                       # 22:52 畫好、22:54 本來會發
check("重放：22:54 不发群，存住等放行", r == cm.HELD_MSG and not c.delivered and c.state["held"][G]["redo"] is True, (r, c.delivered))

print(f"\n{'all ok' if not fails else f'{len(fails)} FAIL: {fails}'}")
sys.exit(1 if fails else 0)
