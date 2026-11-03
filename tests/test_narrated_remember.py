"""回覆最後一行像她寫給自己的「记住」（連標記都沒寫）：不發出去、不進聊天記錄，這一輪還沒记住別的就當成记住記下（bond，10-29）。
起因 10-29 20:54～20:56 小凛群連著四條「爹爹纠正本鱼，摸头是人家摸本鱼，本鱼别伸手」這種。

/usr/local/bin/python3 tests/test_narrated_remember.py（號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import asyncio, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_heart_edit as te  # noqa: E402  借它 stub 好的 astrbot、bond.db

core, bm, store, hs, plug = te.core, te.bm, te.store, te.hs, te.plug
N = core.narrated_tail
S = ["爹爹", "他", "她", "TA", "布丁"]

# ---- 純函數：線上那幾條認得出、正常的話不動 ----
for t, last in [
    ("嗯\n（手放上去，按了按，没挪开）\n爹爹考本鱼摸头该怎么应，本鱼照教的哼了一声", "爹爹考本鱼摸头该怎么应，本鱼照教的哼了一声"),
    ("嗯\n（脑袋往那只手上靠了靠）\n爹爹纠正本鱼，摸头是人家摸本鱼，本鱼别伸手", "爹爹纠正本鱼，摸头是人家摸本鱼，本鱼别伸手"),
    ("嗯……\n喜欢爹爹\n爹爹让本鱼摸头时把心里话说出来，别憋着", "爹爹让本鱼摸头时把心里话说出来，别憋着"),
    ("哼\n嘴上嫌弃\n布丁又摸本鱼头，本鱼嘴上嫌手没躲", "布丁又摸本鱼头，本鱼嘴上嫌手没躲"),
    ("好\n他让本鱼别喊三毛哥了，本鱼还没想好改叫啥", "他让本鱼别喊三毛哥了，本鱼还没想好改叫啥"),
]:
    rest, got = N(t, S, "本鱼")
    assert got == last and last not in rest and rest.strip(), (t, rest, got)
for t in ["爹爹纠正本鱼，摸头是人家摸本鱼",  # 只有一行：不動
          "收到\n他要是回得慢，本鱼就先按现在这版整理描述准备着",
          "好\n爹爹别嫌本鱼黏", "嗯\n爹爹你让本鱼咋办", "哈\n爹爹让本鱼摸摸头嘛？",
          "嗯\n爹爹刚还说西瓜霜是西瓜的粑粑，那本鱼这名起得还挺准",
          "嗯\n祈投喂本鱼十五块，本鱼记账上",  # 名字不在名單裡
          "嗯\n爹爹让本鱼" + "去" * 40]:
    assert N(t, S, "本鱼")[1] is None, t
assert N("嗯\n爹爹让本鱼去睡", S, "")[1] is None  # 沒有自稱不認


# ---- 外掛：發出去之前拿掉、記成记住；有標記记住過的不另記；聊天記錄也拿掉 ----
class Cfg(te.Cfg):
    def me(self): return "本鱼"
plug.s = Cfg()
plug._sync_owners = lambda: None
Q = "20401"
store.on_talk(Q, "布丁", time.time())


class Ev(te.Ev):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.extra = {"lively_bond_qq": Q}
        self.unified_msg_origin = "g"
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, d=None): return self.extra.get(k, d)


ev = Ev(Q, "30001")
subj = plug._narrate_subjects(ev, Q, store.get(Q))
assert "爹爹" in subj and "布丁" in subj and "他" in subj, subj
ev.extra["lively_bond_subj"] = subj


class Resp:
    completion_text = "嗯\n（脑袋往那只手上靠了靠）\n爹爹纠正本鱼，摸头是人家摸本鱼，本鱼别伸手"
r = Resp()
asyncio.run(plug.take_tag(ev, r))
assert r.completion_text == "嗯\n（脑袋往那只手上靠了靠）", r.completion_text
live = [x[0] for x in hs.db.execute("SELECT text FROM moments WHERE qq=? AND source='live'", (Q,))]
assert any("摸头是人家摸本鱼" in x for x in live), live

# 有好感標記、标记裡沒记住：那一行當成记住
ev2 = Ev(Q, "30001"); ev2.extra["lively_bond_subj"] = subj
class Resp2:
    completion_text = "好呀\n布丁又摸本鱼头，本鱼嘴上嫌手没躲\n<<好感+1|害羞>>"
r2 = Resp2()
asyncio.run(plug.take_tag(ev2, r2))
assert r2.completion_text == "好呀", r2.completion_text
assert ev2.extra.get("lively_bond_remember") == "布丁又摸本鱼头，本鱼嘴上嫌手没躲", ev2.extra

# 聊天記錄：這一輪每一步的那行都拿掉
msgs = [types.SimpleNamespace(role="user", content="摸摸"),
        types.SimpleNamespace(role="assistant", content="嗯\n（脑袋往那只手上靠了靠）\n爹爹纠正本鱼，摸头是人家摸本鱼，本鱼别伸手")]
asyncio.run(plug.clean_history(ev, types.SimpleNamespace(messages=msgs), None))
assert msgs[1].content == "嗯\n（脑袋往那只手上靠了靠）", msgs[1].content


# 調工具前那步的字（不經過 on_llm_response）：發送前拿掉；最後那步 take_tag 看過的不再看第二遍
class P:
    def __init__(self, text): self.text = text
_plain, bm.Plain = bm.Plain, P
ev3 = Ev(Q, "30001"); ev3.extra["lively_bond_subj"] = subj
ev3._result = types.SimpleNamespace(chain=[P("行\n爹爹让本鱼开护士模式去治愈喊累的人")])
ev3.get_result = lambda: ev3._result; ev3.stop_event = lambda: None
asyncio.run(plug.last_check(ev3))
assert [c.text for c in ev3._result.chain] == ["行"], [c.text for c in ev3._result.chain]
ev4 = Ev(Q, "30001"); ev4.extra["lively_bond_subj"] = subj
class Resp4:
    completion_text = "嗯\n爹爹让本鱼去睡\n爹爹纠正本鱼，摸头该谢人家"
asyncio.run(plug.take_tag(ev4, Resp4()))
ev4._result = types.SimpleNamespace(chain=[P("嗯\n爹爹让本鱼去睡")])
ev4.get_result = lambda: ev4._result; ev4.stop_event = lambda: None
asyncio.run(plug.last_check(ev4))
assert [c.text for c in ev4._result.chain] == ["嗯\n爹爹让本鱼去睡"], [c.text for c in ev4._result.chain]
bm.Plain = _plain

# 沒注入過（不知道是誰）不動
ev5 = Ev(Q, "30001")
class Resp5:
    completion_text = "嗯\n爹爹纠正本鱼，摸头是人家摸本鱼"
r5 = Resp5(); asyncio.run(plug.take_tag(ev5, r5))
assert "纠正" in r5.completion_text
print("test_narrated_remember ok")
