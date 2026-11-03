"""〈主人〉交代的事（bond asks.py、工具 lively_owner_rule，10-28）。

/usr/local/bin/python3 tests/test_owner_asks.py（號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import asyncio, importlib, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和暫存的 bond.db

core, bm, store, hs = tr.core, tr.bm, tr.store, tr.hs
asks_mod = importlib.import_module("astrbot_plugin_lively_bond.asks")
OwnerAsks, asks_block = asks_mod.OwnerAsks, asks_mod.asks_block
now = time.time()
X, Y, NEW = "20201", "20202", "1785079999"
store.on_talk(X, "多肉", now)
store.on_talk(Y, "小眠", now)
store.db.commit()
core.OWNERS.clear()
core.OWNERS.add(tr.OWNER)

# ---- 本子本身 ----
A = OwnerAsks(store.db)
assert asks_mod.norm_targets([]) == ["all"] and asks_mod.norm_targets(["qq:1", "all"]) == ["all"]
assert asks_mod.norm_targets(["qq:12345", "qq:12345", "group:x", "group:30001"]) == ["qq:12345", "group:30001"]
a1 = A.add("爹爹的仇人，遇见就阴阳怪气", ["qq:" + X, "qq:" + NEW], src="dm")
assert [a["id"] for a in A.for_person(X)] == [a1["id"]] and A.for_person(NEW) and not A.for_person(Y)
a2 = A.add("有人老说没人陪，别劝他去现实里找人，就陪着", [], src="dm")
assert A.everywhere() == [A.get(a2["id"])]
a3 = A.add("这个群别发擦边表情包", ["group:30001"], src="group:30001")
assert A.for_group("30001")[0]["id"] == a3["id"] and not A.for_group("30002")
assert A.get(f"交代{a1['id']}")["id"] == a1["id"] and A.get("x") is None
assert "最多 120" in A.check("x" * 121, ["all"])
t1, t2 = A.add("y" * 120, []), A.add("u" * 100, [])
assert "最多 300" in A.check("t" * 80, ["all"])  # 到哪都算的加起來超了
assert A.check("t" * 80, ["qq:" + X]) == ""  # 掛在人身上不算進那 300
assert A.check("t" * 80, ["all"], skip=t2["id"]) == ""
A.drop(t1["id"]), A.drop(t2["id"])

blk = asks_block(A.for_person(X), "多肉", A.for_group("30001"), A.everywhere())
assert "关于正在说话的「多肉」：「爹爹的仇人" in blk and "在这个群：「这个群别发擦边" in blk and "到哪都算：「有人老说" in blk, blk
assert "私聊里）" in blk and "群里）" in blk
assert asks_block([], "", [], []) == ""

# ---- 關係讀口：掛在人身上的跟著 TA 走（話裡提到、還不認識的號也帶） ----
R = tr.rel.Relations(store, hs)
R.asks = A
r = R.of(X)
assert r["asks"] == ["爹爹的仇人，遇见就阴阳怪气"], r["asks"]
assert "〈主人〉交代过：「爹爹的仇人" in R.say_about(r)
s_new = R.say_about(R.of(NEW))
assert "不知道是谁" in s_new and "〈主人〉交代过：「爹爹的仇人" in s_new, s_new
assert "交代过" not in R.say_about(R.of(Y))
assert R.of(Y)["asks"] == []
# 交代裡寫了「仇人」的：〈主人〉交代的仇人（10-30），冷處理也不攔她主動去對線
assert R.of(X)["enemy"] is True and R.of(Y)["enemy"] is False

# ---- 工具：只有主人說話時能動；記、看、改、刪 ----
class Cfg:
    def get(self, k, d=None): return d
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owners(self): return [tr.OWNER]
    def owner(self): return tr.OWNER
    def is_owner(self, q): return str(q) == tr.OWNER
    def groups(self): return ["30001"]
class Ev:
    def __init__(self, sender, gid=""):
        self.sender, self.gid, self.message_str = sender, gid, ""
        self.message_obj = types.SimpleNamespace(message=[])
    def get_sender_id(self): return self.sender
    def get_sender_name(self): return "n" + self.sender
    def get_self_id(self): return "99"
    def get_group_id(self): return self.gid
plug = bm.LivelyBond.__new__(bm.LivelyBond)
plug.store, plug.heart, plug.s, plug.asks, plug.rel = store, hs, Cfg(), A, R
tool = lambda ev, **kw: asyncio.run(plug.owner_rule(ev, **kw))
OWN = Ev(tr.OWNER)

assert tool(Ev(X), action="记", text="随便").startswith("没做：这个本子只有爹爹")
r = tool(OWN, action="记", text="仇人，见了就损他", who=f"{Y} 多肉")
assert r.startswith("记下了（交代") and f"QQ {Y}（小眠）" in r and f"QQ {X}（多肉）" in r and "被 @" in r, r
nid = int(r.split("交代")[1].split("）")[0])
assert A.get(nid)["targets"] == [f"qq:{Y}", f"qq:{X}"]
assert "认不出「没这人」" in tool(OWN, action="记", text="x", who="没这人")
r = tool(OWN, action="记", text="陌生号", who="1785079000")
assert "本鱼还不认识这个号" in r, r
r = tool(OWN, action="记", text="每轮都要记得吃饭")
assert "到哪都算：以后每一轮" in r, r
tool(OWN, action="记", text="z" * 120)
tool(OWN, action="记", text="w" * 120)
assert "超了" in tool(OWN, action="记", text="v" * 120)
r = tool(Ev(tr.OWNER, "30001"), action="记", text="群里少刷屏", group="这个群")
assert "群 30001" in r and A.for_group("30001")[-1]["src"] == "group:30001", r
assert "认不出群" in tool(OWN, action="记", text="x", group="这个群")  # 私聊裡沒有「這個群」
lst = tool(OWN, action="看")
assert lst.startswith("爹爹交代过的") and "仇人，见了就损他" in lst, lst
r = tool(OWN, action="改", id=str(nid), text="仇人，见了就阴阳他")
assert r.startswith("改好了") and A.get(nid)["targets"] == [f"qq:{Y}", f"qq:{X}"] and A.get(nid)["text"] == "仇人，见了就阴阳他"
r = tool(OWN, action="改", id=f"交代{nid}", who=Y)
assert A.get(nid)["targets"] == [f"qq:{Y}"], r
assert tool(OWN, action="删", id=str(nid)).startswith(f"删了交代{nid}") and A.get(nid) is None
assert "没找到" in tool(OWN, action="删", id="999")
assert "action 写" in tool(OWN, action="飞")
n_ev = store.db.execute("SELECT count(*) FROM events WHERE kind='owner_ask'").fetchone()[0]
assert n_ev >= 5, n_ev

# ---- 說話時帶給她 ----
blk = plug._asks_text(Ev(X, "30001"), X, "多肉")
assert "关于正在说话的「多肉」" in blk and "在这个群" in blk and "到哪都算" in blk and "lively_owner_rule 看得到全部" not in blk
blk = plug._asks_text(OWN, tr.OWNER, "陈")
assert "lively_owner_rule 看得到全部" in blk and "关于正在说话" not in blk, blk

# ---- 工具只在主人說話時看得到 ----
class Tools:
    def __init__(self): self.gone = []
    def remove_tool(self, n): self.gone.append(n)
req = types.SimpleNamespace(func_tool=Tools())
asyncio.run(plug.hide_owner_rule(Ev(X, "30001"), req))
assert req.func_tool.gone == ["lively_owner_rule"]
req = types.SimpleNamespace(func_tool=Tools())
asyncio.run(plug.hide_owner_rule(Ev(tr.OWNER, "30001"), req))
assert req.func_tool.gone == []
# 10-29：她順手寫了 why，以前直接報錯（unexpected keyword argument 'why'）
r = tool(Ev(tr.OWNER), action="记", text="提人一律写名字和号", why="爹爹说光报号码认不得")
assert r.startswith("记下了"), r
note = store.db.execute("SELECT note FROM events WHERE kind='owner_ask' ORDER BY id DESC").fetchone()[0]
assert note.endswith("｜爹爹说光报号码认不得"), note
print("test_owner_asks ok")

# ---- 11-02：說的是哪一天的交代，那天過完就不帶 ----
import sqlite3
from datetime import datetime as _dt
def _ts(s): return _dt.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=asks_mod.TZ).timestamp()
U = asks_mod.until_of
T7 = "今天几个群的群漫画都要重新走流程做一遍发出去，纯良那个只发下午画的那张"
assert U(T7, _ts("2026-10-31 22:16")) == _ts("2026-11-01 06:00")  # 10-31 那條：11-01 早上 6 點就不帶了
assert U("今晚先别发", _ts("2026-11-02 01:30")) == _ts("2026-11-02 06:00")  # 半夜一點半說的「今晚」還是前一晚
assert U("明天早上八点叫我", _ts("2026-11-02 10:00")) == _ts("2026-11-04 06:00")
assert U("后天去看", _ts("2026-11-02 10:00")) == _ts("2026-11-05 06:00")
for t in ("从今天起提人写名字", "今天开始不许发擦边图", "今天以后别劝他去现实里找人", "每天都要陪他", "有人老说没人陪", "提人一律写名字和号"):
    assert U(t, now) is None, t
B = OwnerAsks(sqlite3.connect(":memory:"))
old = B.add(T7, [], src="dm", now=_ts("2026-10-31 22:16"))
keep = B.add("提人一律写名字和号", [], src="dm", now=_ts("2026-10-31 22:16"))
mine = B.add("今天纯良群的先给我看", ["group:30001"], src="dm")
assert old["until"] == _ts("2026-11-01 06:00") and keep["until"] is None and mine["until"] > now
assert [a["id"] for a in B.everywhere()] == [keep["id"]]  # 過期的不帶
assert [a["id"] for a in B.for_group("30001")] == [mine["id"]]
assert len(B.all()) == 3 and B.get(old["id"])  # 本子上還在
blk = asks_block([], "", B.for_group("30001"), B.everywhere())
assert "起不再带" in blk and T7 not in blk, blk
assert "过了，不再带" in asks_mod.until_note(B.get(old["id"]))
e = B.edit(old["id"], "提人只说名字")  # 改成不帶日子的說法：又算數了
assert e["until"] is None and e["id"] in [a["id"] for a in B.everywhere()]
# 舊庫沒有 until 欄：載入時補上，按最後一次記、改的時間算
C = sqlite3.connect(":memory:")
C.execute("CREATE TABLE owner_asks(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, targets TEXT NOT NULL, ts REAL NOT NULL, updated REAL NOT NULL, src TEXT DEFAULT '')")
C.execute("INSERT INTO owner_asks(text,targets,ts,updated,src) VALUES(?,?,?,?,?)", (T7, '["all"]', _ts("2026-10-31 22:16"), _ts("2026-10-31 22:16"), "dm"))
C.execute("INSERT INTO owner_asks(text,targets,ts,updated,src) VALUES(?,?,?,?,?)", ("别劝他去现实里找人", '["all"]', 1, 1, "dm"))
C.commit()
D = OwnerAsks(C)
assert [a["text"] for a in D.everywhere()] == ["别劝他去现实里找人"] and len(D.all()) == 2
OwnerAsks(C)  # 再載入一次不出錯
# 工具：記一條帶「今天」的，回傳照實說那天過完就不帶；看的時候標出來
r = tool(Ev(tr.OWNER), action="记", text="今天几个群的群漫画先给我看")
assert r.startswith("记下了") and "起不再带" in r and "改成不带这种词" in r, r
assert "今天几个群的群漫画先给我看" in tool(Ev(tr.OWNER), action="看")
print("test_owner_asks until ok")
