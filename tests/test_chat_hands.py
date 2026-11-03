"""看手機時才有的動作做成聊天時的工具（mind，10-28 用戶定「放开」）：空間（看／贊／評論／回）、記事本記一筆、
嫌煩名單、改線上狀態和簽名。借 test_send_to 搭好的假 mind。

/usr/local/bin/python3 tests/test_chat_hands.py（號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import asyncio, sys, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_send_to as b  # noqa: E402

mind, Ev, hands_mod = b.mind, b.Ev, b.hands_mod
OWNER, MOON, LOW, GROUP = b.OWNER, b.MOON, b.LOW, b.GROUP
mind.state["modes"].update({"qzone_read": "on", "qzone_like": "on", "qzone_comment": "on", "qzone_reply": "on",
                            "quiet": "on", "status": "shadow", "longnick": "on"})
mind.state["enabled"] = True
quiet = {}
mind.quiet_people = lambda: quiet
mind.set_quiet = lambda qq, off=False, name="", why="": quiet.pop(qq, None) if off else quiet.update({qq: {"name": name}})


async def run(coro):
    r = await coro
    await asyncio.gather(*list(mind.hands._tasks))
    return r

# ---- 空間：先看拿編號，再贊、評論、回 ----
now = time.time()
FEEDS = [{"qq": MOON, "name": "泠·月", "tid": "t1", "ts": now - 600, "text": "今天做了拌饭", "pics": True, "liked": False},
         {"qq": LOW, "name": "路人", "tid": "t2", "ts": now - 3600, "text": "上班好累", "pics": False, "liked": True}]
COMMENTS = [{"qq": MOON, "name": "泠·月", "tid": "m1", "cid": "7", "ts": now - 300, "text": "本鱼好可爱", "post": "睡醒了"}]
got_fresh = []
async def fake_qzone(fresh=0):
    got_fresh.append(fresh)
    mind.senses._feeds = (time.time(), FEEDS, COMMENTS)
    return FEEDS, COMMENTS
mind.senses = type("S", (), {})()
mind.senses._qzone, mind.senses._feeds = fake_qzone, None
done = []
async def fake_exec(action, args, ctx):
    done.append((action, args, ctx))
mind.hands._qzone = fake_exec

ev = Ev(LOW, "去空间看看", group=GROUP)
r = asyncio.run(run(mind.tool_qzone(ev)))
assert "Q1" in r and "泠·月（20001）：今天做了拌饭［有图］" in r and "［本鱼赞过了］" in r and "C1" in r and "在「睡醒了」下" in r, r
assert got_fresh[-1] == b.mm.QZ_FRESH, got_fresh
r = asyncio.run(run(mind.tool_qzone(ev, action="赞", which="q1")))
assert r == "好，一会儿就做" and done[-1][0] == "qzone_like" and done[-1][2]["tid"] == "t1", (r, done)
r = asyncio.run(run(mind.tool_qzone(ev, action="赞", which="Q1")))
assert "已经赞过了" in r, r
r = asyncio.run(run(mind.tool_qzone(ev, action="赞", which="Q9")))
assert "Q 编号对不上" in r, r
r = asyncio.run(run(mind.tool_qzone(ev, action="评论", which="Q2", text="")))
assert "评论的话是空的" in r
r = asyncio.run(run(mind.tool_qzone(ev, action="评论", which="Q1", text="看着好香")))
assert r == "好，一会儿就做" and done[-1] == ("qzone_comment", {"text": "看着好香"}, done[-1][2]), done[-1]
r = asyncio.run(run(mind.tool_qzone(ev, action="评论", which="Q1", text="再来一句")))
assert "今天已经对 TA 做过了" in r, r  # 同一條說說一天評論一次
r = asyncio.run(run(mind.tool_qzone(ev, action="回", which="C1", text="你更可爱")))
assert r == "好，一会儿就做" and done[-1][2]["cid"] == "7", done[-1]
assert "C 编号对不上" in asyncio.run(run(mind.tool_qzone(ev, action="回", which="Q1", text="x")))
mind.state["modes"]["qzone_read"] = "off"
assert "关着" in asyncio.run(run(mind.tool_qzone(ev)))
mind.state["modes"]["qzone_read"] = "on"
assert "action 写" in asyncio.run(run(mind.tool_qzone(ev, action="飞")))

# ---- 記事本記一筆：跟這個群、跟某人有關的 ----
r = asyncio.run(run(mind.tool_note(ev, text="晚上问泠·月拌饭怎么做", when="今晚", who=MOON, where="这个群")))
n = mind.state["notes"][-1]
assert r.startswith("记下了（#") and n["who"] == MOON and n["where"] == GROUP and n["when"] == "今晚", (r, n)
r = asyncio.run(run(mind.tool_note(ev, text="别的群的事", where="88888")))
assert "where" not in mind.state["notes"][-1], mind.state["notes"][-1]  # 不是服務的群不記群
assert "是空的" in asyncio.run(run(mind.tool_note(ev, text=" ")))

# ---- 嫌煩名單：不寫就是說話的人；主人、自己不記；劃掉 ----
r = asyncio.run(run(mind.tool_quiet(ev, why="TA 说别插嘴")))
assert r.startswith("记下了") and LOW in quiet, r
assert "已经在名单里" in asyncio.run(run(mind.tool_quiet(ev)))
assert "QQ 号不对" in asyncio.run(run(mind.tool_quiet(ev, qq=OWNER)))
r = asyncio.run(run(mind.tool_quiet(ev, qq=LOW, off=True)))
assert r.startswith("划掉了") and LOW not in quiet, r
assert "本来就不在" in asyncio.run(run(mind.tool_quiet(ev, qq=LOW, off=True)))

# ---- 線上狀態、簽名 ----
called = []
async def call_action(a, **kw):
    called.append((a, kw))
    return {}
mind.s.client = lambda: type("C", (), {"api": type("A", (), {"call_action": staticmethod(call_action)})()})()
r = asyncio.run(run(mind.tool_qq_profile(ev, status="忙碌", signature="今天也在吃白饭")))
assert "在线状态：这个动作现在只记录" in r and "个性签名：好，一会儿就做" in r, r
assert called == [("set_self_longnick", {"longNick": "今天也在吃白饭"})], called
assert "都没写" in asyncio.run(run(mind.tool_qq_profile(ev)))
print("test_chat_hands ok")
