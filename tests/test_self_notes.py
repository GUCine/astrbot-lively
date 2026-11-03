"""〈我〉自己的事（bond self_notes.py、工具 lively_self_note，10-30）。

/usr/local/bin/python3 tests/test_self_notes.py（號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import asyncio, importlib, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和暫存的 bond.db

core, bm, store, hs = tr.core, tr.bm, tr.store, tr.hs
sn = importlib.import_module("astrbot_plugin_lively_bond.self_notes")
X = "20301"
store.on_talk(X, "多肉", time.time())
store.db.commit()
core.OWNERS.clear()
core.OWNERS.add(tr.OWNER)
is_owner = lambda q: str(q) == tr.OWNER

# ---- 本子本身 ----
N = sn.SelfNotes(store.db)
assert N.all() == [] and sn.notes_block([], is_owner) == ""
a = N.add("住在爹爹的台式机上", "dm:" + tr.OWNER, tr.OWNER, "陈")
assert N.get(f"S{a['id']}")["id"] == a["id"] and N.get("x") is None
assert "最多 150" in N.check("x" * 151)
assert "没写" in N.check("")
fill = [N.add("y" * 120, "", sn.SELF) for _ in range(6)]
assert "最多 800" in N.check("t" * 100), N.check("t" * 100)  # 9+720+100 > 800
assert N.check("t" * 100, skip=fill[0]["id"]) == ""
for f in fill:
    N.drop(f["id"])
blk = sn.notes_block(N.all(), is_owner)
assert blk.startswith(sn.BLOCK_HEAD) and f"S{a['id']} 住在爹爹的台式机上（" in blk and "〈主人〉说的" in blk, blk
assert tr.OWNER not in blk  # 不帶號碼
b = N.add("有自己的电脑", "", sn.SELF)
c = N.add("会唱歌", "group:30001", X, "多肉")
blk = sn.notes_block(N.all(), is_owner)
assert "〈我〉自己知道的" in blk and "多肉说的" in blk and X not in blk, blk
N.edit(c["id"], "会唱歌，是多肉说的", now=time.time() + 3600 * 30)
assert "改过" in sn.note_line(N.get(c["id"]), is_owner)
for n in N.all():
    N.drop(n["id"])

# ---- 工具：誰說的都能記；不是主人說的記一筆給主人私聊 ----
class Cfg:
    def get(self, k, d=None): return d
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owners(self): return [tr.OWNER]
    def owner(self): return tr.OWNER
    def is_owner(self, q): return str(q) == tr.OWNER
    def private_umo(self, q): return f"p:{q}"
class Ev:
    def __init__(self, sender, gid="", nick=""):
        self.sender, self.gid, self.message_str = sender, gid, ""
        self.message_obj = types.SimpleNamespace(message=[], raw_message={"sender": {"nickname": nick}})
    def get_sender_id(self): return self.sender
    def get_sender_name(self): return "n" + self.sender
    def get_self_id(self): return "99"
    def get_group_id(self): return self.gid
told = []
bm.note_outbox = lambda umo, text, kind="": told.append((umo, text, kind))
plug = bm.LivelyBond.__new__(bm.LivelyBond)
plug.store, plug.heart, plug.s, plug.self_notes = store, hs, Cfg(), N
tool = lambda ev, **kw: asyncio.run(plug.self_note(ev, **kw))
OWN = Ev(tr.OWNER, nick="陈")

assert tool(OWN, action="看") == "本子上还没有记自己的事"
r = tool(OWN, action="记", text="住在爹爹的台式机上，10-28 搬过来的")
assert r.startswith("记下了：S") and "爹爹说的" in r and "1 条" in r, r
assert told == []  # 主人說的不用告訴主人
r = tool(Ev(X, "30001", "多肉"), action="记", text="会唱歌")
assert "多肉说的" in r, r
assert len(told) == 1 and told[0][0] == f"p:{tr.OWNER}" and "群里记了一条自己的事" in told[0][1] and "多肉说的" in told[0][1], told
assert told[0][2] == "后台:自己的事"
r = tool(Ev(X, nick="多肉"), action="记", text="有手机了", who="自己")
assert "本鱼自己知道的" in r and "和多肉的私聊里" in told[-1][1], (r, told[-1])
assert tool(OWN, action="记", text="x" * 151).startswith("没记：一条最多 150")
lst = tool(OWN, action="看")
assert lst.startswith("本子上 3 条") and "最多 800" in lst and "S" in lst, lst
first = N.all()[0]["id"]
r = tool(OWN, action="改", id=f"S{first}", text="住在爹爹的台式机上")
assert r.startswith("改好了") and "原来是" in r, r
assert "没找到" in tool(OWN, action="删", id="999")
r = tool(OWN, action="删", id=str(first))
assert r.startswith(f"删了 S{first}") and N.get(first) is None
assert "action 写" in tool(OWN, action="飞")
assert store.db.execute("SELECT count(*) FROM events WHERE kind='self_note'").fetchone()[0] >= 4

# ---- 說話時接在 system 最後，已經有了不重複加 ----
req = types.SimpleNamespace(system_prompt="人设")
txt = plug.s.fill(plug.self_notes_text())
bm.system_tail(req, txt)
bm.system_tail(req, txt)
assert req.system_prompt.startswith("人设\n\n本鱼自己记着的自己的事") and req.system_prompt.count("自己记着的") == 1, req.system_prompt
print("ok")
