"""防打擾的上限第二批（10-29 用戶定）：個性簽名一週一次（被擋時寫上次幾號、幾號以後能改）；嫌煩名單、冷處理／戒備
〈主人〉叫的不擋（回傳照實說 TA 現在是什麼態度），別人叫的、心跳自己想做的、到點提醒／投喂好感照擋；屏蔽照擋；
說說她自己送審一天 3 條〈主人〉叫的不看。借 test_send_to 搭好的假 mind。

/usr/local/bin/python3 tests/test_owner_caps2.py（號碼都是假的：10001 主人、2000x 群友）
"""
import asyncio, sys, time, types
from datetime import datetime
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_send_to as b  # noqa: E402

mind, Ev, hands_mod, mm = b.mind, b.Ev, b.hands_mod, b.mm
OWNER, MOON, LOW, COLD, GROUP = b.OWNER, b.MOON, b.LOW, b.COLD, b.GROUP
H = mind.hands
TZ = hands_mod.TZ
mind.state["modes"].update({"longnick": "on", "status": "shadow"})
mind.state["enabled"] = True
quiet = {}
mind.quiet_people = lambda: quiet
ignored = []
orig_shared = mind.s.shared if hasattr(mind.s, "shared") else None
mind.s.shared = lambda k: ignored if k == "ignored_senders" else None
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, "" if ok else extra)
    if not ok:
        fails.append(name)


async def call(ev, **kw):
    r = await mind.tool_send_to(ev, **kw)
    await asyncio.gather(*list(H._tasks))
    return r

own, mate = Ev(OWNER, "你私聊他一下"), Ev(MOON, "你私聊他一下", group=GROUP)

# ---- 嫌煩名單 ----
quiet[LOW] = {"name": "路人", "why": "说本鱼吵", "ts": time.time() - 86400}
r = asyncio.run(call(own, text="在吗", qq=LOW))
mmdd = f"{datetime.fromtimestamp(quiet[LOW]['ts'], TZ):%m-%d}"
check("主人叫的不被嫌煩名單擋，回傳照實說", r.startswith("好，过几秒就用你自己的号发给路人") and "TA 在本鱼的嫌烦名单上" in r
      and f"{mmdd}记的：说本鱼吵" in r, r)
check("真的發出去了", b.ctx.sent[-1][0] == f"x:FriendMessage:{LOW}" and b.ctx.sent[-1][1] == ["在吗"])
r = asyncio.run(call(mate, text="在吗", qq=LOW))
# 10-30 用戶定：嫌煩名單只記著、不攔，誰叫的都一樣（照實帶一句）
check("群友叫的也不被嫌煩名單擋", "嫌本鱼烦" not in r, r)
for by, ctx in (("heartbeat", {}), ("reminder", {"owner_asked": True}), ("perk", {"owner_asked": True})):
    rec = asyncio.run(H.do("say_private", by=by, umo=f"x:FriendMessage:{LOW}", qq=LOW, args={"text": "嗨"}, ctx=ctx))
    check(f"{by} 不被嫌煩名單擋", "嫌" not in (rec.get("blocked_by") or ""), rec.get("blocked_by"))
rec = asyncio.run(H.do("poke", by="heartbeat", umo=b.ctx and f"x:GroupMessage:{GROUP}", qq=LOW))
check("心跳戳嫌煩的人不擋", "嫌" not in (rec.get("blocked_by") or ""), rec.get("blocked_by"))
quiet.pop(LOW)

# ---- 冷處理／戒備 ----
r = asyncio.run(call(own, text="嗨", qq=COLD))
check("主人叫的不被冷處理擋，回傳帶態度和原因", r.startswith("好，过几秒就用你自己的号发给坏人") and "冷处理" in r and "主人修改" in r
      and "这次是爹爹叫的" in r, r)
r = asyncio.run(call(mate, text="嗨", qq=COLD))
check("群友叫的照擋", r.startswith("没做成：对 TA 冷处理中") and "不看这一道" in r, r)
rec = asyncio.run(H.do("say_private", by="reminder", umo=f"x:FriendMessage:{COLD}", qq=COLD, args={"text": "嗨"},
                       ctx={"owner_asked": True}))
check("到點提醒不算主人叫的，照擋冷處理", (rec.get("blocked_by") or "").startswith("对 TA 冷处理中"), rec.get("blocked_by"))
# 戒備（level 2）：示好的動作主人叫的放行，別人叫的擋
real_att = mind.bond.attitude
mind.bond.attitude = lambda q: 2 if q == COLD else real_att(q)
rec = asyncio.run(H.do("poke", by="chat", umo=f"x:GroupMessage:{GROUP}", qq=COLD, ctx={"owner_asked": True, "by_owner": True}))
check("戒備：主人叫的戳一戳放行並記態度", rec.get("result") in ("queued", "done", "shadow") and rec.get("passed")
      and "这次是〈主人〉叫的" in rec["passed"][0], rec)
rec = asyncio.run(H.do("poke", by="chat", umo=f"x:GroupMessage:{GROUP}", qq=COLD, ctx={"owner_asked": False}))
check("戒備：別人叫的戳一戳擋", (rec.get("blocked_by") or "").startswith("对 TA 有戒备"), rec.get("blocked_by"))
mind.bond.attitude = real_att

# ---- 屏蔽照擋（她自己用 lively_block 放得出來） ----
ignored.append(LOW)
r = asyncio.run(call(own, text="在吗", qq=LOW))
check("被屏蔽的主人叫的也擋，說放出來用 lively_block", r.startswith("没做成：TA 被屏蔽了") and "lively_block" in r, r)
ignored.clear()

# ---- 個性簽名一週一次 ----
check("簽名間隔 7 天", hands_mod.ACTIONS["longnick"]["every"] == 7 * 86400)
spec = hands_mod.ACTIONS["longnick"]
now = time.time()
H.state["acted"] = [[now - 2 * 86400, "longnick", "", "x", "chat"]]
w = H._rate("longnick", spec, "", "x", True)
last = datetime.fromtimestamp(now - 2 * 86400, TZ)
nxt = datetime.fromtimestamp(now + 5 * 86400, TZ)
check("兩天前改過：擋，寫上次是哪天、幾號以後能改", w.startswith("离上次太近") and f"{last:%m-%d %H:%M}" in w and "2 天前" in w
      and "至少隔 7 天" in w and f"{nxt:%m-%d %H:%M} 以后能再个性签名" in w and "〈主人〉叫的也算" in w, w)
H.state["acted"] = [[now - 6.9 * 86400, "longnick", "", "x", "chat"]]
check("六天多還擋", bool(H._rate("longnick", spec, "", "x")))
H.state["acted"] = [[now - 7.1 * 86400, "longnick", "", "x", "chat"]]
check("滿七天放行", H._rate("longnick", spec, "", "x") is None)
check("記錄留得夠久（>7 天）", hands_mod.KEEP_DAYS > 7)
# 名片讚、在線狀態不動
check("名片讚一天一次、在線狀態隔 10 分鐘沒動", hands_mod.ACTIONS["profile_like"]["target_day"] == 1
      and hands_mod.ACTIONS["status"]["every"] == 600)
# 一小時 30 件照舊寫明主人叫的也算
H.state["acted"] = [[now - 60, "say_group", "u", "", "heartbeat"]] * 30
w = H._rate("poke", hands_mod.ACTIONS["poke"], "u", "k", True)
check("防失控那道照舊", w.startswith("这一小时做的事太多了") and "〈主人〉叫的也算在里面" in w, w)

# 說說她自己送審一天 3 條主人叫的不看：見 test_qzone_her.py

print("\n全部通過" if not fails else f"\n{len(fails)} 項失敗：{fails}")
sys.exit(1 if fails else 0)
