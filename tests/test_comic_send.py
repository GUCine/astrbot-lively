"""群漫畫發送（10-28）：10-27 22:00 四個群同一秒發 2.6MB PNG，NapCat 報 1200 超時，三張其實發到了卻被當成沒發。
現在：大圖轉 JPEG、排隊發、報超時翻群裡的消息看到了算發成；真的沒發成圖留著，lively_comic_post 能發。
/usr/local/bin/python3 tests/test_comic_send.py（號碼都是假的）"""
import asyncio, os, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_look as tl  # noqa: E402  借它的假 astrbot
cm, G, BOT = tl.cm, tl.G, "99999"
cm.SEND_CHECK = (0, 0, 0)
tl.S.bot_qq = lambda self: BOT
tl.S.groups = lambda self: [G]
hist: list = []
calls: list = []


class Client:
    async def _call(self, action, **kw):
        assert action in ("get_group_msg_history", "get_friend_msg_history")
        calls.append((action, kw))
        return {"messages": list(hist)}
    def __init__(self): self.api = types.SimpleNamespace(call_action=self._call)
tl.S.client = lambda self: Client()
TIMEOUT = RuntimeError("ActionFailed retcode=1200 Timeout: NTEvent serviceAndMethod:NodeIKernelMsgService/sendMsg")
plan: list = []
sent: list = []


async def send(umo, chain):
    sent.append((umo, chain.chain))
    r = plan.pop(0) if plan else None
    if isinstance(r, tuple):  # (異常, 之後群裡看得到)
        if r[1]:
            hist.append({"time": time.time(), "sender": {"user_id": int(BOT)}, "message": [{"type": "image"}]})
        raise r[0]


def new():
    c = tl.new()
    c.context.send_message = send
    if c.events_file.exists():
        c.events_file.unlink()
    hist.clear(); sent.clear(); plan.clear()
    return c


# 大 PNG 轉 JPEG，小的照原樣
big = tl.TMP / "comic_big.png"
from PIL import Image  # noqa: E402
Image.frombytes("RGB", (900, 900), os.urandom(900 * 900 * 3)).save(big)
c = new()
assert big.stat().st_size > cm.JPEG_OVER
light = c._light(str(big))
assert light.endswith("_send.jpg") and Path(light).exists() and big.exists()
assert c._light(str(tl.IMG)) == str(tl.IMG)
assert c._light("http://x/y.png") == "http://x/y.png"
assert c._light(str(big)) == light  # 同一張圖不重轉
# 同一個檔名被重畫覆蓋：發的要是新的（10-29 定做形象發出了上一版），舊版本清掉，名字相近的別張不動
sib = Path(light).parent / "comic_big_card_0123456789_send.jpg"
sib.write_bytes(b"x")
legacy = Path(light).parent / "comic_big_send.jpg"
legacy.write_bytes(b"old")
Image.frombytes("RGB", (900, 900), os.urandom(900 * 900 * 3)).save(big)
light2 = c._light(str(big))
assert light2 != light and not Path(light).exists() and not legacy.exists() and sib.exists()
assert not list(Path(light2).parent.glob("*.tmp"))
print("转 JPEG ok")

# 報超時、群裡其實有：算發成，不再發
c = new()
plan.append((TIMEOUT, True))
assert asyncio.run(c._deliver(G, str(tl.IMG), "配的话")) == "late" and len(sent) == 1
# 報超時、群裡沒有：再發一次
c = new()
plan.extend([(TIMEOUT, False), None])
assert asyncio.run(c._deliver(G, str(tl.IMG))) == "sent" and len(sent) == 2
# 兩次都沒發成：拋錯；不是超時的錯不重發
c = new()
plan.extend([(TIMEOUT, False), (TIMEOUT, False)])
try:
    asyncio.run(c._deliver(G, str(tl.IMG))); raise AssertionError
except RuntimeError:
    pass
c = new()
plan.append((ValueError("bad"), False))
try:
    asyncio.run(c._deliver(G, str(tl.IMG))); raise AssertionError
except ValueError:
    assert len(sent) == 1
# 私聊也一樣（10-28 10:31 主人私聊那張長圖報超時、其實發到了）：翻的是和 TA 的私聊
c = new()
calls.clear()
plan.append((TIMEOUT, True))
assert asyncio.run(c._send_checked("x:FriendMessage:10001", str(tl.IMG))) == "late" and len(sent) == 1
assert calls and calls[-1] == ("get_friend_msg_history", {"user_id": 10001, "count": 20}), calls
print("超时翻群消息 ok")

# 每天那張：真的沒發成 → 留著（pending），返回事實；lively_comic_post 能發
c = new()
tl.S.conf = {"comic_look": False}
c.state["inflight"][G] = {"offset": 0}
plan.extend([(TIMEOUT, False), (TIMEOUT, False)])
r = asyncio.run(c._publish(G, "今天", str(tl.IMG), tl.TOPICS))
assert "没发成" in r and "lively_comic_post" in r, r
p = c.state["pending"][G]
assert p["path"] == str(tl.IMG) and p["day"] == c._day_of(0) and p["failed"]
assert any(e["kind"] == "send_fail" for e in tl.events(c))
assert "今天的没发：画好了，发到群里没发成" in c._status(G), c._status(G)
pid = c.gallery.find_path(str(tl.IMG), "群漫画整页")["id"]
assert c.gallery.get(pid)["status"] == "没发成" and c.gallery.get(pid).get("failed"), c.gallery.get(pid)
assert f"图册 #{pid}" in r, r                                    # 回给她的话带整页编号
out = asyncio.run(c.post(image=f"#{pid}", target=G))
assert f"发了 #{pid} 到「测试群」" in out and G not in c.state["pending"] and c.gallery.get(pid)["status"] == "已发", out
assert "今天的 " in c._status(G) and "发到群里了" in c._status(G), c._status(G)
# 報超時其實到了：記 late
c = new()
c.state["inflight"][G] = {"offset": 0}
plan.append((TIMEOUT, True))
assert asyncio.run(c._publish(G, "今天", str(tl.IMG), tl.TOPICS)) == "已自动发群"
ev = [e for e in tl.events(c) if e["kind"] == "sent"][-1]
assert ev.get("late") and ev["day"] == c._day_of(0)
# 沒有要發的圖：照實說那個群最近兩天怎麼樣
c = new()
out = asyncio.run(c.post(target=G))
assert out.startswith("没发：没写发哪张"), out
tl.S.conf = {}
print("没发成留着 ok")

# 畫圖那步沒成的原因說清楚（10-28 另一個 session 轉來：小凛群只交給她「画图那步失败了」，主人問為啥她答不出）
R = cm.comic_fail_reason
assert R("gpt-image-2.5: 流式返回错误: {'type': 'timeout'}；gpt-image-2.5-flare: timed out") == ("画图中转站两个模型都超时了", True)
assert R("gpt-image-2.5: Your request was rejected by the safety system")[1] is False and "审核" in R("x: 请求被OpenAi审核拒绝")[0]
assert R("gpt-image-2.5: 参考图损坏或无效") == ("有张参考图中转站读不了", False)
assert R("TimeoutError") == ("画图中转站超时了", True)
assert R("gpt-image-2.5: 502 bad gateway")[1] is True
c = new()
c._topics = lambda h, gid, off: asyncio.sleep(0, result={"success": True, "topics": tl.TOPICS, "talk": {}})
async def mc(gid, topics, talk, until=None):
    raise RuntimeError("gpt-image-2.5: timed out；gpt-image-2.5-flare: timed out")
c._my_comic = mc
gen_calls = []
async def gen(*a, **k): gen_calls.append(1); return None, None
h = types.SimpleNamespace(comic_service=types.SimpleNamespace(generate_comic=gen))
tl.S.conf = {}
r = asyncio.run(c._generate(h, G, 0, True, False, "今天", "u"))
assert "两个模型都超时了" in r and not gen_calls, (r, gen_calls)  # 11-02 起没有退回群分析插件那条路
assert "两个模型都超时了" in c._status(G), c._status(G)
tl.S.conf = {}
# 分鏡兩次都寫壞（11-02 桐群）：不退回群分析插件、記 fail、補畫退張數、說清楚這個群這次沒有群漫畫
c = new()
c._topics = lambda h, gid, off: asyncio.sleep(0, result={"success": True, "topics": tl.TOPICS, "talk": {}})
tries = []
async def bad_sb(gid, topics, talk, until=None):
    tries.append(1); raise cm.StoryboardBad(cm.STORYBOARD_BAD + "Expecting ',' delimiter: line 1 column 3135")
c._my_comic = bad_sb
c._redo = {G: {"counted": True}}
refunded = []
c._redo_refund = lambda gid="": refunded.append(gid)
c._draw_by_ts = lambda: None            # 離該畫第一張沒有餘裕：不整個再試
gen_calls.clear()
r = asyncio.run(c._generate(h, G, 0, False, False, "今天", "u"))
assert "分镜写坏了" in r and "没有群漫画" in r and not gen_calls and len(tries) == 1 and refunded == [G], (r, gen_calls, tries, refunded)
assert [e for e in c.events_file.read_text("utf-8").splitlines() if '"kind": "fail"' in e], c.events_file.read_text("utf-8")
# 定時那張離該畫第一張還早：整個再寫一次，第二次好就照常出圖
c = new()
c._topics = lambda h, gid, off: asyncio.sleep(0, result={"success": True, "topics": tl.TOPICS, "talk": {}})
tries.clear(); cm.TOPIC_RETRY_GAP = 0
async def sb_then_ok(gid, topics, talk, until=None):
    tries.append(1)
    if len(tries) == 1:
        raise cm.StoryboardBad(cm.STORYBOARD_BAD + "x")
    return [(IMG_BYTES, {"title": "a"})], []
IMG_BYTES = Path(tl.IMG).read_bytes()
c._my_comic = sb_then_ok
c._draw_by_ts = lambda: time.time() + 3600
c.state["inflight"][G] = {"gid": G, "ts": 1}
out = asyncio.run(c._generate(h, G, 0, True, False, "今天", "u"))
assert isinstance(out, tuple) and len(tries) == 2 and len(out[0]) == 1 and not gen_calls, (out, tries)
# 畫圖那步失敗（不是分鏡壞）：不整個再寫一次，免得重複花錢
c = new()
c._topics = lambda h, gid, off: asyncio.sleep(0, result={"success": True, "topics": tl.TOPICS, "talk": {}})
tries.clear()
async def draw_bad(gid, topics, talk, until=None):
    tries.append(1); raise RuntimeError("gpt-image-2.5: timed out")
c._my_comic = draw_bad
c._draw_by_ts = lambda: time.time() + 3600
r = asyncio.run(c._generate(h, G, 0, True, False, "今天", "u"))
assert len(tries) == 1 and "没画成" in r and "超时" in r, (r, tries)
# 靜態檢查：不再碰群分析插件的 generate_comic、拿掉的兩個設定
src = (Path(cm.__file__)).read_text("utf-8")
assert "generate_comic" not in src and "comic_combine" not in src and 'get("own_storyboard"' not in src
print("分镜写坏 ok")

# 審核拒了不再等著重畫
c = new()
calls = []
async def bad(gid, prompt, ref, size, measure=True):
    calls.append(1); raise RuntimeError("gpt-image-2.5: rejected by the safety system")
c._draw_any = bad
c._cast = lambda t, talk: []
c._storyboard = lambda t, cast, **k: asyncio.sleep(0, result=[{"panels": []}])
c._comic_prompt = lambda sb, cast, idx=None: ("p", False)
c._comic_refs = lambda sb, cast, w: asyncio.sleep(0, result=([], []))
try:
    asyncio.run(c._my_comic(G, [], {}, until=time.time() + 3600)); raise AssertionError
except RuntimeError:
    assert len(calls) == 1
print("画图失败原因 ok")
