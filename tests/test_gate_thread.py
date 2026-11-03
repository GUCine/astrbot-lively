"""gate：TA 在群裡剛跟〈我〉說的，轉到私聊時帶上（10-30 桐群交代畫小凛群的版本，私聊這邊不知道照哪張畫）。

python3 tests/test_gate_thread.py（號碼都是假的）
"""
import asyncio, sys, tempfile, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import test_gate_draft as base  # noqa: E402  stub 好的 astrbot

g = base.g
g.DATA_DIR = Path(tempfile.mkdtemp())
outbox = []
g.read_outbox = lambda umo, since, n=200: [d for d in outbox if d["umo"] == umo and d["ts"] > since]


class GEv(base.Ev):
    def __init__(self, comps, text, wake=True, gid="20001", qq="30001"):
        super().__init__(comps, text, wake)
        self.gid, self.qq = gid, qq
        self.unified_msg_origin = f"aiocqhttp:GroupMessage:{gid}" if gid else f"aiocqhttp:FriendMessage:{qq}"
        self.message_obj.group = types.SimpleNamespace(group_name="桐群") if gid else None
    def get_group_id(self): return self.gid
    def get_sender_id(self): return self.qq


def new():
    gate = base.new_gate({})
    gate._threads = {}
    gate.caption_of = lambda url: "猫捧着奶茶" if url == "cat" else ""
    gate.name = "小肥鱼"
    return gate


gate = new()
quote = base.Dummy(); quote.message_str = "这回是本鱼捧着奶茶蹲雪地里了"; quote.sender_nickname = "小肥鱼"; quote.sender_id = "10002"
ev = GEv([quote, base.Image("cat")], "按照这个做一个小凛那个群的版本，发过去")
gate._thread_note(ev, "TA", gate._thread_text(ev))
row = gate._threads["rows"]["30001"][-1]
assert row["text"] == "（引用〈我〉：「这回是本鱼捧着奶茶蹲雪地里了」） [图片：猫捧着奶茶] 按照这个做一个小凛那个群的版本，发过去", row
assert row["gname"] == "桐群"

# 她在群裡回 TA、調了畫圖工具
sent = GEv([], "", wake=False)
sent._result = types.SimpleNamespace(chain=[base.Plain("先画本鱼和小凛挤一块儿的版本")])
gate._thread_sent(sent)
res = types.SimpleNamespace(content=[types.SimpleNamespace(text="画好了，已经发到这里了（参考图：小凛…）\n图缓存在…")])
asyncio.run(gate.thread_tool(GEv([], "", wake=False), types.SimpleNamespace(name="lively_draw"),
                             {"prompt": "Two-panel meme, whale girl holding milk tea", "text": ""}, res))
outbox.append({"ts": time.time(), "umo": "aiocqhttp:GroupMessage:20001", "kind": "群漫画", "text": "〈我〉把图发到群里了"})
outbox.append({"ts": time.time(), "umo": "aiocqhttp:GroupMessage:20001", "kind": "后台:公告", "text": "不该带"})
assert [r["who"] for r in gate._threads["rows"]["30001"]] == ["TA", "我", "工具"]

# 別人在群裡、別的群：不記到 TA 那段
other = GEv([], "", wake=False, qq="30002"); other._result = types.SimpleNamespace(chain=[base.Plain("hi")])
gate._thread_sent(other)
assert "30002" not in gate._threads["rows"]

# TA 轉到私聊：帶上，只帶一次
dm = GEv([], "小凛那个群的版本图，你自己挑几个", gid="")
part = gate._thread_part(dm)
text = part.text
assert not part.temp  # 存進歷史
assert "群「桐群」（20001）" in text and "TA：（引用〈我〉" in text and "〈我〉：先画本鱼" in text, text
assert "调了 lively_draw（prompt=Two-panel meme" in text and "参考图" not in text and "图缓存" not in text, text
assert "［群漫画］" in text and "不该带" not in text, text
assert gate._thread_part(dm) is None
# 存了檔，重啟讀得回來
assert (g.DATA_DIR / g.THREAD_FILE).exists()

# 又在群裡說了一句：私聊只帶新的
time.sleep(0.01)
gate._thread_note(GEv([], "再加个人"), "TA", "再加个人")
assert gate._thread_part(dm).text.count("TA：") == 1

# 太久以前的不帶；別人私聊不帶
gate2 = new()
gate2._thread_note(GEv([], "x"), "TA", "很早说的")
gate2._threads["rows"]["30001"][-1]["ts"] -= g.THREAD_HOURS * 3600 + 5
assert gate2._thread_part(GEv([], "", gid="")) is None
gate2._thread_note(GEv([], "x"), "TA", "刚说的")
assert gate2._thread_part(GEv([], "", gid="", qq="30009")) is None
assert "很早说的" not in gate2._thread_part(GEv([], "", gid="")).text
print("group thread ok")
