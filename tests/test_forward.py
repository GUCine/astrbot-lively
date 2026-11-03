"""轉發的聊天記錄展開給她看（gate，10-27）：收到時向 NapCat 要內容，接在這條消息後面（群聊背景、長期記憶看得到），
叫到她的那條另外帶一段；拿不到就照實寫拿不到。格式在 lively_common.forward_text。

python3 tests/test_forward.py
"""
import asyncio, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gate_draft as base  # noqa: E402

g, lc = base.g, base.dg

# ---- 格式 ----
NODES = [  # NapCat get_forward_msg 給的樣子（名字常常是「QQ用户」）
    {"sender": {"nickname": "泠·月"}, "message": [{"type": "text", "data": {"text": "真乖~\n摸摸头"}}]},
    {"sender": {"nickname": "QQ用户"}, "message": [{"type": "text", "data": {"text": "你呀……行吧，就你一个能摸，别人不许"}}]},
    {"sender": {"nickname": "小肥鱼"}, "message": [{"type": "image", "data": {"summary": "[动画表情]", "sub_type": 1}}]},
    {"sender": {"nickname": "x"}, "message": [{"type": "image", "data": {"summary": "[图片]"}}]},
    {"sender": {"nickname": "y"}, "message": [{"type": "forward", "data": {"content": [{}, {}]}}]},
    {"sender": {"nickname": "z"}, "message": [{"type": "text", "data": {"text": "   "}}]},  # 空的不寫
]
t = lc.forward_text(NODES)
assert t.startswith("[转发的聊天记录，5 条（旧→新，名字写「？」的是 QQ 没给出是谁）："), t
assert "泠·月：真乖~ 摸摸头｜？：你呀……行吧，就你一个能摸，别人不许｜小肥鱼：[动画表情]｜x：[图片]｜y：[又转了一段聊天记录，2 条]" in t, t  # 空節點讀不出字：只報條數
assert lc.forward_text([]) == "[转发的聊天记录：里面的内容 QQ 没给出来，〈我〉看不到]"
long = [{"sender": {"nickname": f"p{i}"}, "message": [{"type": "text", "data": {"text": "字" * 200}}]} for i in range(20)]
t = lc.forward_text(long)
assert "…后面还有 5 条" in t and len(t) < lc.FORWARD_MAX + 80 and "字" * 81 not in t, t
assert lc.forward_lines([{"type": "node", "data": {"nickname": "a", "content": [{"type": "text", "data": {"text": "hi"}}]}}]) == ["a：hi"]

# 轉發裡再轉發：往裡展開，每段只帶前幾條，其餘寫還有幾條；套得太深的只報條數
def inner(n, deep=None):
    msgs = [{"sender": {"nickname": f"u{i}"}, "message": [{"type": "text", "data": {"text": f"第{i}句"}}]} for i in range(n)]
    if deep:
        msgs.append({"sender": {"nickname": "d"}, "message": [{"type": "forward", "data": {"content": deep}}]})
    return msgs
nest = [{"sender": {"nickname": "QQ用户"}, "message": [{"type": "forward", "data": {"content": inner(20)}}]},
        {"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"content": inner(2)}}]}]
t = lc.forward_text(nest)
assert "？：[又转的聊天记录 20 条：u0：第0句／u1：第1句／u2：第2句／u3：第3句／u4：第4句／u5：第5句／…还有 14 条]" in t, t
assert "a：[又转的聊天记录 2 条：u0：第0句／u1：第1句]" in t and "又转了一段" not in t, t
t = lc.forward_text([{"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"content": inner(1, inner(1, inner(1, inner(3))))}}]}])
assert "u0：第0句／d：[又转的聊天记录 2 条：u0：第0句／d：[又转了一段聊天记录，2 条]" in t, t  # 第三層往下只報條數
assert lc.forward_text([{"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"id": "9"}}]}]).count("QQ 没给出来") == 1
assert "又转了一段聊天记录，0 条，里面的内容 QQ 没给出来" in lc.forward_text([{"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"id": "9"}}]}] + inner(1))
many = [{"sender": {"nickname": f"p{i}"}, "message": [{"type": "forward", "data": {"content": inner(20)}}]} for i in range(8)]
t = lc.forward_text(many)
assert len(t) < lc.FORWARD_NEST_MAX + 80 and t.count("又转的聊天记录") >= 4, (len(t), t)

# ---- gate：收到時展開 ----
class Api:
    def __init__(self, ret, fail=False): self.ret, self.fail, self.calls = ret, fail, []
    async def call_action(self, action, **kw):
        self.calls.append((action, kw))
        if self.fail:
            raise RuntimeError("napcat down")
        return self.ret
def gate_with(api):
    gate = base.new_gate({})
    gate.s = types.SimpleNamespace(fill=lambda x: x.replace("〈我〉", "本鱼"), groups=lambda: ["20001"],
                                   client=lambda: types.SimpleNamespace(api=api) if api else None)
    return gate
class Ev:
    def __init__(self, segs, mid="111"):
        self.message_obj = types.SimpleNamespace(raw_message={"message": segs}, message=[], message_id=mid)
        self.extra = {}
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, d=None): return self.extra.get(k, d)

api = Api({"messages": NODES[:2]})
ev = Ev([{"type": "forward", "data": {"id": "770", "content": []}}])
asyncio.run(gate_with(api)._expand_forward(ev))
assert api.calls == [("get_forward_msg", {"message_id": "111"})], api.calls
assert len(ev.message_obj.message) == 1 and "就你一个能摸" in ev.message_obj.message[0].text, ev.message_obj.message
assert ev.extra["lively_forward"][0].startswith("[转发的聊天记录，2 条")
# 帶了內容就不再去要
api = Api({"messages": []})
ev = Ev([{"type": "forward", "data": {"id": "770", "content": NODES[:1]}}])
asyncio.run(gate_with(api)._expand_forward(ev))
assert api.calls == [] and "摸摸头" in ev.message_obj.message[0].text
# 用 message_id 要不到，再用 id 要；都要不到照實寫，〈我〉換成名字
api = Api({"messages": []})
ev = Ev([{"type": "forward", "data": {"id": "770"}}])
asyncio.run(gate_with(api)._expand_forward(ev))
assert [c[1] for c in api.calls] == [{"message_id": "111"}, {"id": "770"}], api.calls
assert "QQ 没给出来，本鱼看不到" in ev.message_obj.message[0].text
api = Api(None, fail=True)
ev = Ev([{"type": "forward", "data": {"id": "770"}}])
asyncio.run(gate_with(api)._expand_forward(ev))
assert "看不到" in ev.message_obj.message[0].text
# 裡面再轉發沒帶內容：拿那段的 id 再要一次
class Api2(Api):
    async def call_action(self, action, **kw):
        self.calls.append((action, kw))
        if kw.get("id") == "inner1":
            return {"messages": inner(2)}
        return {"messages": [{"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"id": "inner1"}}]}]}
api = Api2(None)
ev = Ev([{"type": "forward", "data": {"id": "770"}}])
asyncio.run(gate_with(api)._expand_forward(ev))
assert [c[1] for c in api.calls] == [{"message_id": "111"}, {"id": "inner1"}], api.calls
assert "a：[又转的聊天记录 2 条：u0：第0句／u1：第1句]" in ev.message_obj.message[0].text, ev.message_obj.message[0].text
# 轉發裡的圖：展開後看得到的編號寫成「[图片#n]」（貼圖、第 7 條以後的套著的不編），她自己調 lively_look_forward_image 看
async def fake_cap(orig, this, url, *a, **kw):
    if url == "bad":
        return "没看到这张图：下载不了"
    return f"画面是{url}"
def img(u, sub=0): return {"type": "image", "data": {"url": u, "summary": "[图片]", "sub_type": sub}}
def mk_inn():
    inn = [{"sender": {"nickname": "x"}, "message": [img(f"p{i}")]} for i in range(8)]
    inn[1] = {"sender": {"nickname": "x"}, "message": [img("sticker", 1)]}
    inn[2] = {"sender": {"nickname": "x"}, "message": [img("bad")]}
    return inn
ev = Ev([{"type": "forward", "data": {"id": "1", "content": [{"sender": {"nickname": "a"}, "message": [{"type": "forward", "data": {"content": mk_inn()}}]}]}}])
ev.unified_msg_origin = "umo1"
gate = gate_with(Api({}))
gate._caption_orig = (None, object())
gate.cfg = {}
gate.context = types.SimpleNamespace(get_config=lambda: {"provider_ltm_settings": {"image_caption_provider_id": "v", "image_caption_prompt": "p"}})
gate._icl_caption = fake_cap
asyncio.run(gate._expand_forward(ev))
t = ev.message_obj.message[0].text
assert "x：[图片#1]" in t and "x：[动画表情]" in t and "x：[图片#2]" in t and "x：[图片#5]" in t and "#6" not in t, t  # 6 條：p0、貼圖、bad、p3、p4、p5
assert "画面是" not in t  # 展開時不替她看
ev2 = types.SimpleNamespace(unified_msg_origin="umo1")
out = asyncio.run(gate.tool_look_forward_image(ev2, "1-2,9"))
assert "#1：画面是p0" in out and "#2：没看到这张图：下载不了" in out and "没有这几个编号：#9" in out, out
out = asyncio.run(gate.tool_look_forward_image(ev2, "一张"))
assert out.startswith("没看：编号没看懂"), out
out = asyncio.run(gate.tool_look_forward_image(types.SimpleNamespace(unified_msg_origin="other"), "1"))
assert out.startswith("没看：这个聊天里还没有"), out
# 編號不重複：同一個聊天再來一段接著編
ev = Ev([{"type": "forward", "data": {"id": "1", "content": [{"sender": {"nickname": "a"}, "message": [img("n0")]}]}}])
ev.unified_msg_origin = "umo1"
asyncio.run(gate._expand_forward(ev))
assert "a：[图片#6]" in ev.message_obj.message[0].text, ev.message_obj.message[0].text
# 沒有轉發：什麼都不動
ev = Ev([{"type": "text", "data": {"text": "hi"}}])
asyncio.run(gate_with(Api({}))._expand_forward(ev))
assert ev.message_obj.message == [] and "lively_forward" not in ev.extra

# ---- 叫到她的那條：sticker_hint 另外帶一段 ----
class Ev2(base.Ev):
    pass
e = Ev2([base.Plain("[转发消息]")], "[转发消息]")
e.set_extra("lively_forward", ["[转发的聊天记录，1 条（旧→新）：泠·月：摸摸头]"])
req = types.SimpleNamespace(prompt="", extra_user_content_parts=[], contexts=[])
gate = base.new_gate({})
gate._mark_stickers = lambda e: None
asyncio.run(gate.sticker_hint(e, req))
texts = [p.text for p in req.extra_user_content_parts]
assert any(x == "（这条消息里[转发的聊天记录，1 条（旧→新）：泠·月：摸摸头]）" for x in texts), texts
assert all(p.temp for p in req.extra_user_content_parts if "转发" in p.text)
# 已經寫進這條的字（message_str → prompt）就不再帶一遍
e = Ev2([base.Plain("[转发消息]")], "x")
e.set_extra("lively_forward", ["[转发的聊天记录，1 条（旧→新）：泠·月：摸摸头]"])
req = types.SimpleNamespace(prompt="x [转发的聊天记录，1 条（旧→新）：泠·月：摸摸头]", extra_user_content_parts=[], contexts=[])
asyncio.run(gate.sticker_hint(e, req))
assert not any("转发" in p.text for p in req.extra_user_content_parts), [p.text for p in req.extra_user_content_parts]
print("forward ok")
