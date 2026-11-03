"""專屬回憶時刻（bond，10-27）：心裡的 TA 多一欄「回忆」，哪些算由〈我〉定（每晚整理時挑、以前的人挑一次、聊天時自己加刪），
TA 說話時單獨帶一行：私聊全部、群裡也全部（私聊的標出來）、話裡提到 TA 只帶不是私聊的。

/usr/local/bin/python3 tests/test_heart_memories.py（號碼都是假的：10001 主人、2000x 群友）
"""
import asyncio, json, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_heart_edit as te  # noqa: E402  借它 stub 好的 astrbot、bond.db、工具外殼

heart, core, dg, bm, tr = te.heart, te.core, te.dg, te.bm, te.tr
store, hs, plug, Ev, tool = te.store, te.hs, te.plug, te.Ev, te.tool
now = time.time()
M = "20201"
store.on_talk(M, "泠月", now)
hs.set_heart(M, {"称呼": "月月", "印象": "爱逗本鱼", "喜好": [], "雷区": [], "梗": []}, now=now - 86400)
upd = store.db.execute("SELECT updated FROM hearts WHERE qq=?", (M,)).fetchone()[0]

# ---- 整理：日期寫在開頭也認、去重、最多 6 條、私聊標記各種寫法 ----
C = heart.clean_memories
got = C([{"事": "10-26 只让 TA 一个人摸头", "私聊": "true"}, "一起熬夜看比赛", {"事": "一起熬夜看比赛"}, {"事": ""}, 3], now)
assert got[0] == {"事": "只让 TA 一个人摸头", "哪天": "10-26", "私聊": True}, got
assert len(got) == 2 and got[1]["私聊"] is False and got[1]["哪天"] == time.strftime("%m-%d", time.localtime(now)), got
assert len(C([{"事": f"事{i}"} for i in range(9)])) == heart.MEMORY_MAX
assert C([{"事": "10月3号 给本鱼画了张图"}])[0]["哪天"] == "10-03"
assert C(None) == [] and C("x") == []

# ---- 給她看的那一行 ----
h = {"回忆": [{"事": "只让 TA 一个人摸头", "哪天": "10-26", "私聊": True}, {"事": "教本鱼打解放战", "哪天": "10-20", "私聊": False}]}
dm, grp, about = (heart.memories_text(h, w) for w in ("dm", "group", "about"))
assert "「只让 TA 一个人摸头」（10-26 私聊里）" in dm and "群里别人不知道" not in dm, dm
assert "「只让 TA 一个人摸头」（10-26 私聊里，群里别人不知道）" in grp and "「教本鱼打解放战」（10-20 群里）" in grp, grp
assert "摸头" not in about and "解放战" in about, about
assert heart.memories_text({}, "dm") == "" and heart.memories_text({"回忆": [h["回忆"][0]]}, "about") == ""
# 心裡的 TA 那一段：說話注入的不帶（另外一行、不被截斷）；整理材料、主人看的帶，私聊的不給群裡
assert "专属回忆" not in heart.heart_text(h, private=False, memories=False)
assert "只让 TA 一个人摸头" in heart.heart_text(h) and "摸头" not in heart.heart_text(h, private=False)
# build_prompt 單獨一行、在心裡的 TA 後面
note = core.build_prompt(store.get(M), True, heart="印象：爱逗本鱼", memories=grp)
assert grp in note and note.index("心里的 TA") < note.index("专属回忆"), note

# ---- 她自己加、刪：私聊裡加的算私聊的，群裡加的不算，開頭寫「私聊」就算；不動 updated ----
r = tool(Ev(M), field="回忆", action="加", value="10-26 松口说只让 TA 一个人摸头", why="TA 说了好开心")
assert r == "改好了：往「回忆」加了「松口说只让 TA 一个人摸头」（10-26 私聊里）", r
r = tool(Ev(M, "30001"), field="回忆", action="加", value="在群里教本鱼打解放战")
assert "「在群里教本鱼打解放战」（" in r and "群里）" in r, r
r = tool(Ev(M, "30001"), field="回忆", action="加", value="私聊里的：答应给本鱼买薯片")
assert "「答应给本鱼买薯片」（" in r and "私聊里）" in r, r
assert "已经有" in tool(Ev(M), field="回忆", action="加", value="答应给本鱼买薯片")
assert "几条都含" not in tool(Ev(M), field="回忆", action="删", value="薯片")
mems = hs.get_heart(M)["回忆"]
assert [m["事"] for m in mems] == ["松口说只让 TA 一个人摸头", "在群里教本鱼打解放战"], mems
assert store.db.execute("SELECT updated FROM hearts WHERE qq=?", (M,)).fetchone()[0] == upd
assert "没有「回忆」这栏" not in tool(Ev(M), field="回忆", action="改成", value="")  # 清空
assert hs.get_heart(M)["回忆"] == []
for v in ("10-26 松口说只让 TA 一个人摸头", "教本鱼打解放战"):
    tool(Ev(M, "" if "摸头" in v else "30001"), field="回忆", action="加", value=v)

# ---- 說話時帶上：群裡、私聊各一行 ----
class S(te.Cfg):
    def get(self, k, d=None): return d
plug.s = S()
line_g = plug._memories_line(Ev(M, "30001"), M)
line_d = plug._memories_line(Ev(M), M)
assert "只让 TA 一个人摸头」（10-26 私聊里，群里别人不知道）" in line_g and "群里别人不知道" not in line_d, (line_g, line_d)
class Off(te.Cfg):
    def get(self, k, d=None): return False if k == "heart_memories" else d
plug.s = Off(); assert plug._memories_line(Ev(M, "30001"), M) == ""; plug.s = S()
# 話裡提到 TA：只帶群裡的
R = tr.R
about = R.say_about(R.of(M))
assert "解放战" in about and "摸头" not in about, about

# ---- 每晚整理：規則說了這一欄；模型沒寫回忆就照舊留著，寫了就照寫的，加減記 events ----
assert "专属回忆时刻" in dg.HEART_RULE and "MEMORY_" not in dg.HEART_RULE and "\"回忆\"" in dg.HEART_RULE
assert "和「回忆」" in dg.HEART_RULE
def prov(payload):
    class P:
        async def text_chat(self, prompt, system_prompt):
            P.prompt = prompt
            return types.SimpleNamespace(completion_text=json.dumps(payload, ensure_ascii=False))
    return P
base = {"称呼": "月月", "印象": "爱逗本鱼", "喜好": [], "雷区": [], "梗": [], "最近": "", "语气": "", "牵挂": [],
        "私下": {"牵挂": [], "心事": []}, "偏心": {"分": 0}, "改了": []}
class S2(te.Cfg):
    P = None
    def get(self, k, d=None): return False if k == "digest_persona" else d
    def provider(self): return S2.P()
d = dg.Digest.__new__(dg.Digest)
d.s, d.bond, d.heart = S2(), store, hs
S2.P = prov(base)
mat = d._heart_material(M)
assert "专属回忆：「松口说只让 TA 一个人摸头」（10-26 私聊里）" in mat, mat
asyncio.run(d.update_heart(M))
assert [m["事"] for m in hs.get_heart(M)["回忆"]] == ["松口说只让 TA 一个人摸头", "教本鱼打解放战"], hs.get_heart(M)
S2.P = prov(dict(base, 回忆=[{"事": "松口说只让 TA 一个人摸头", "哪天": "10-26", "私聊": True},
                            {"事": "半夜陪本鱼聊到两点", "哪天": "10-27", "私聊": True}]))
asyncio.run(d.update_heart(M))
evs = [r[0] for r in store.db.execute("SELECT note FROM events WHERE qq=? AND kind='heart_memory' ORDER BY id", (M,))]
assert evs == ["+半夜陪本鱼聊到两点", "-教本鱼打解放战"], evs

# ---- 以前的人挑一次：只動這一欄、不動 updated；挑過的（有這一欄，空的也算）不再挑 ----
N = "20202"
store.on_talk(N, "老王", now)
hs.set_heart(N, {"称呼": "老王", "印象": "爱下棋"}, now=now - 3600)
for i in range(3):
    hs.add_moment(N, now - 86400 * (i + 1), f"一起下棋第{i}回", feeling="开心", weight=0.4 + 0.2 * i,
                  scope="dm" if i else "group:30001", private=bool(i), source="test", ref=f"docN{i}")
due = d.memories_due()
if True:
    assert N in due and M not in due, due
    upd_n = store.db.execute("SELECT updated FROM hearts WHERE qq=?", (N,)).fetchone()[0]
    S2.P = prov({"回忆": [{"事": "一起下棋第2回", "哪天": "10-24", "私聊": True}]})
    d.memories_due = lambda: [N]  # 借來的 bond.db 裡還有別人也沒挑過，這裡只看 N
    ok, fail = asyncio.run(d.pick_memories())
    del d.memories_due
    assert ok == 1 and fail == 0 and hs.get_heart(N)["回忆"][0]["事"] == "一起下棋第2回"
    assert "一起下棋第0回" in S2.P.prompt and "私聊" in S2.P.prompt
    assert store.db.execute("SELECT updated FROM hearts WHERE qq=?", (N,)).fetchone()[0] == upd_n
    assert hs.get_heart(N)["印象"] == "爱下棋" and N not in d.memories_due()
assert "{" not in dg.MEMORY_PICK_RULE.split("JSON")[0]
print("heart memories ok")
