"""她自己改心裡的 TA（bond 工具 lively_heart_edit、heart.edit_heart，10-26）＋每晚回味對不上的改掉、記成 heart_fix。

/usr/local/bin/python3 tests/test_heart_edit.py（號碼都是假的：10001 主人、2000x 群友）
"""
import asyncio, json, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和暫存的 bond.db

heart, core, dg, bm = tr.heart, tr.core, tr.dg, tr.bm
store, hs, now = tr.store, tr.hs, time.time()
X, Y, Z = "20101", "20102", "20103"
for q in (X, Y, Z):
    store.on_talk(q, f"n{q}", now)
hs.set_heart(X, {"称呼": "小X", "印象": "爱吃火锅", "喜好": ["火锅", "猫"], "雷区": ["香菜"],
                 "梗": [{"梗": "锅王", "来历": "火锅吃了三锅"}], "私下": {"心事": ["失恋了"], "牵挂": []}}, now=now - 86400)
upd = store.db.execute("SELECT updated FROM hearts WHERE qq=?", (X,)).fetchone()[0]

# ---- 純函數：各種改法 ----
E = heart.edit_heart
h0 = hs.get_heart(X)
h, m = E(h0, "喜好", "删", "猫"); assert h["喜好"] == ["火锅"] and "删掉了「猫」" in m, m
assert h0["喜好"] == ["火锅", "猫"]  # 不改傳進來的
h, m = E(h0, "喜好", "加", "打游戏"); assert h["喜好"] == ["火锅", "猫", "打游戏"], h
h, m = E(h0, "喜好", "加", "猫"); assert h is None and "已经有" in m
h, m = E(h0, "喜好", "改成", "唱歌、跳舞，画画"); assert h["喜好"] == ["唱歌", "跳舞", "画画"], h
h, m = E(h0, "雷区", "改成", ""); assert h["雷区"] == [] and "（空的）" in m
h, m = E(h0, "称呼", "改成", "X 哥"); assert h["称呼"] == "X 哥" and "从「小X」改成了「X 哥」" in m, m
h, m = E(h0, "称呼", "加", "X 哥"); assert h is None and "只能「改成」" in m
h, m = E(h0, "梗", "加", "三锅（那天吃了三锅）"); assert h["梗"][-1] == {"梗": "三锅", "来历": "那天吃了三锅"}, h
h, m = E(h0, "梗", "删", "锅王"); assert h["梗"] == []
h, m = E(h0, "私下心事", "删", "失恋"); assert h["私下"]["心事"] == [] and h["私下"]["牵挂"] == []
h, m = E(h0, "私下的牵挂", "加", "睡不好"); assert h["私下"]["牵挂"] == ["睡不好"]
h, m = E(h0, "印象", "改成", "x" * 50); assert len(h["印象"]) == heart.HEART_IMPRESSION_MAX
h, m = E(h0, "爱好", "加", "猫"); assert h is None and "没有「爱好」" in m
h, m = E(h0, "喜好", "换", "猫"); assert h is None and "action" in m
h, m = E({"喜好": ["火锅", "火锅底料"]}, "喜好", "删", "火"); assert h is None and "几条都含" in m
h, m = E({"喜好": ["火锅", "火锅底料"]}, "喜好", "删", "火锅"); assert h["喜好"] == ["火锅底料"]  # 一字不差的優先
h, m = E({"喜好": list("abcd")}, "喜好", "加", "e"); assert h["喜好"] == list("bcde") and "挤掉" in m, m

# ---- 存：不動 updated，印象改了舊的進印象史 ----
ok, m = hs.edit(X, "印象", "改成", "其实不爱火锅，爱吃烤肉")
assert ok and hs.get_heart(X)["印象"] == "其实不爱火锅，爱吃烤肉" and hs.get_heart(X)["印象史"][0]["印象"] == "爱吃火锅"
assert store.db.execute("SELECT updated FROM hearts WHERE qq=?", (X,)).fetchone()[0] == upd
ok, m = hs.edit(Y, "喜好", "加", "猫")  # 還沒有心裡的 TA：建一份，當成還沒整理過
assert ok and hs.get_heart(Y)["喜好"] == ["猫"] and store.db.execute("SELECT updated FROM hearts WHERE qq=?", (Y,)).fetchone()[0] == 0

# ---- 工具：誰能改、在哪改 ----
class Cfg:
    def get(self, k, d=None): return d
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owners(self): return [tr.OWNER]
    def is_owner(self, q): return str(q) == tr.OWNER
    def groups(self): return ["30001"]
class Ev:
    def __init__(self, sender, gid="", text="", ats=()):
        self.sender, self.gid, self.message_str = sender, gid, text
        self.message_obj = types.SimpleNamespace(message=[bm.At(qq=a) for a in ats])
    def get_sender_id(self): return self.sender
    def get_sender_name(self): return "n" + self.sender
    def get_self_id(self): return "99"
    def get_group_id(self): return self.gid
class At:
    def __init__(self, qq): self.qq = qq
bm.At = At
plug = bm.LivelyBond.__new__(bm.LivelyBond)
plug.store, plug.heart, plug.s = store, hs, Cfg()
tool = lambda ev, **kw: asyncio.run(plug.heart_edit(ev, **kw))

r = tool(Ev(X, "30001"), field="喜好", action="加", value="烤肉", why="TA 刚说的")
assert r == "改好了：往「喜好」加了「烤肉」", r
ev = store.db.execute("SELECT note, source FROM events WHERE qq=? AND kind='heart_edit' ORDER BY id DESC", (X,)).fetchone()
assert ev[0] == "往「喜好」加了「烤肉」｜TA 刚说的" and ev[1] == "group", tuple(ev)
# 群裡：10-28 放开，改別人不用那個人在這句話裡被提到；私下那兩欄照舊改不了
assert tool(Ev(X, "30001"), field="喜好", action="加", value="猫", qq=Z) == "改好了：往「喜好」加了「猫」"
assert tool(Ev(X, "30001", text=f"{Z} 喜欢狗"), field="喜好", action="加", value="狗", qq=Z) == "改好了：往「喜好」加了「狗」"
assert "私下的那两栏" in tool(Ev(X, "30001"), field="私下心事", action="加", value="压力大")
# 私聊：自己的私下欄能改，別人的不行；主人私聊誰都能改
assert tool(Ev(X), field="私下心事", action="加", value="压力大") == "改好了：往「私下心事」加了「压力大」"
assert "私下的那两栏" in tool(Ev(X, text=f"{Z}"), field="私下心事", action="加", value="x", qq=Z)
assert tool(Ev(tr.OWNER), field="私下牵挂", action="加", value="考试", qq=Z) == "改好了：往「私下牵挂」加了「考试」"
# 還沒聊過的號（10-29）：向 QQ 查得到就先建一頁再記，查不到、欄位不對都不建
class Api:
    def __init__(self): self.calls = []
    async def call_action(self, action, **kw):
        self.calls.append((action, kw))
        if kw.get("user_id") == 29998:
            return {"user_id": 29998, "nickname": "某bot"}
        raise RuntimeError("查无此人")
api = Api()
plug.s.client = lambda: types.SimpleNamespace(api=api)
assert tool(Ev(tr.OWNER), field="喜好", action="加", value="x", qq="29999").startswith("没改：小本本上还没有这个号，向 QQ 也没查到")
assert store.get("29999") is None
assert tool(Ev(tr.OWNER), field="爱好", action="加", value="x", qq="29998").startswith("没改：没有「爱好」")
assert store.get("29998") is None and api.calls == [("get_stranger_info", {"user_id": 29999})], api.calls
r = tool(Ev(tr.OWNER), field="印象", action="改成", value="主人说是 bot", qq="29998")
assert r.startswith("改好了：") and "先建了一页：QQ 昵称「某bot」" in r, r
p98 = store.get("29998")
assert p98["name"] == "某bot" and p98["talks"] == 0 and hs.get_heart("29998")["印象"] == "主人说是 bot", p98
assert "建了一页" not in tool(Ev(tr.OWNER), field="喜好", action="加", value="刷屏", qq="29998")
plug.s.client = lambda: None
assert "QQ 这会儿连不上" in tool(Ev(tr.OWNER), field="喜好", action="加", value="x", qq="29997")
assert tool(Ev(X), field="雷区", action="删", value="猫") .startswith("没改：「雷区」里没有含「猫」的")
assert hs.get_heart(X)["私下"]["心事"] == ["失恋了", "压力大"]

# ---- 每晚回味：材料帶上她自己改過的；「改了」記成 heart_fix ----
class S2(Cfg):
    def get(self, k, d=None): return False if k == "digest_persona" else d
    def provider(self):
        class P:
            async def text_chat(self, prompt, system_prompt):
                P.prompt = prompt
                return types.SimpleNamespace(completion_text=json.dumps({
                    "称呼": "小X", "印象": "爱吃烤肉", "喜好": ["烤肉"], "雷区": [], "梗": [], "最近": "", "语气": "", "牵挂": [],
                    "私下": {"牵挂": [], "心事": []}, "偏心": {"分": 0}, "改了": ["喜好：火锅改成烤肉，TA 说自己不爱火锅", "  "]}, ensure_ascii=False))
        plug_p = P(); S2.p = P
        return plug_p
d = dg.Digest.__new__(dg.Digest)
d.s, d.bond, d.heart = S2(), store, hs
mat = d._heart_material(X)
assert "〈我〉自己改过（新的在前，lively_heart_edit）：" in mat and "往「喜好」加了「烤肉」｜TA 刚说的" in mat, mat
assert "改了" in dg.HEART_RULE and "对不上" in dg.HEART_RULE
asyncio.run(d.update_heart(X))
fix = store.db.execute("SELECT note FROM events WHERE qq=? AND kind='heart_fix'", (X,)).fetchall()
assert [r[0] for r in fix] == ["喜好：火锅改成烤肉，TA 说自己不爱火锅"], fix
assert hs.get_heart(X)["喜好"] == ["烤肉"]
print("heart edit ok")
