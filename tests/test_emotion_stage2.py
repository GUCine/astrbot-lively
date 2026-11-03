"""情感第二階段（bond，10-28）：「记住」當場記片段、道歉當場告訴她（原不原諒她定）、封閉時她寫一句告訴主人、
群梗和群友之間只記後台。

/usr/local/bin/python3 tests/test_emotion_stage2.py（號碼都是假的：10001 主人、2000x 群友、30001 群）
"""
import asyncio, json, sys, time, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_heart_edit as te  # noqa: E402  借它 stub 好的 astrbot、bond.db

heart, core, dg, bm, tr = te.heart, te.core, te.dg, te.bm, te.tr
store, hs, plug = te.store, te.hs, te.plug
gm = __import__("importlib").import_module("astrbot_plugin_lively_bond.group")
now = time.time()
P, Q, Z = "20301", "20302", "20303"
for q in (P, Q, Z):
    store.on_talk(q, "n" + q, now - 3600)


class Ev(te.Ev):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.extra = {}
        self.unified_msg_origin = "x"
    def set_extra(self, k, v): self.extra[k] = v
    def get_extra(self, k, d=None): return self.extra.get(k, d)


class S(te.Cfg):
    over = {}
    def get(self, k, d=None): return self.over.get(k, d)
    def me(self): return "本鱼"
plug.s = S()
plug.rel = tr.R
plug.group = gm.GroupNotes(store.db)

# ---- 標記：「记住」「原谅」；舊的「印象」照認；漏到外面的「记住:」行也剝掉 ----
clean, tag = core.parse_tag("好呀\n<<好感+1|开心|记住:答应周末陪 TA 打游戏>>")
assert clean == "好呀" and tag["remember"] == "答应周末陪 TA 打游戏" and tag["mood_word"] == "开心" and not tag["forgive"], tag
clean, tag = core.parse_tag("行吧\n<<好感+1|原谅|心软>>")
assert tag["forgive"] and tag["mood_word"] == "心软", tag  # 「原谅」不被當成心情
clean, tag = core.parse_tag("行吧\n<<好感0|平常>>\n记住: 说下次带奶茶")
assert clean == "行吧" and tag["remember"] == "说下次带奶茶", (clean, tag)
assert core.parse_tag("好呀\n<<好感0|平常|印象:爱撒娇>>")[1]["impression"] == "爱撒娇"
assert core.parse_tag("x\n<<好感0|平常|记住:" + "字" * 50 + ">>")[1]["remember"] == "字" * core.REMEMBER_MAX
assert core.parse_tag("我记住: 这句是正文")[1] is None  # 沒有標記的正文不動
rule_on, rule_off = core.tag_rule(True), core.tag_rule(False)
assert "|记住:" in rule_on and "|印象:" not in rule_on and "|印象:" in rule_off and "{remember}" not in rule_on
note = core.build_prompt(store.get(P), True, fresh=["10-28 群里：答应陪 TA 打游戏"], sorry="TA 这条像是在道歉。")
assert "当场记下的" in note and "像是在道歉" in note and "|记住:" in note, note
assert "|印象:" in core.build_prompt(store.get(P), True, remember=False)

# ---- 「记住」：當場記成 live 片段、不帶分數；一天最多 5 條；說話帶最近的最多 3 條，私聊的在群裡標出來 ----
def say(ev, text):
    _, t = core.parse_tag(text)
    plug._remember(ev, ev.get_sender_id(), t)
say(Ev(P), "x\n<<好感0|平常|记住:私聊里说最近失眠>>")
say(Ev(P, "30001"), "x\n<<好感0|平常|记住:群里教本鱼打牌>>")
m = hs.fresh(P)
assert [x["text"] for x in m] == ["群里教本鱼打牌", "私聊里说最近失眠"] and m[1]["private"] == 1 and m[0]["impacts"] == "{}", m
for i in range(5):
    say(Ev(P), f"x\n<<好感0|平常|记住:第{i}件>>")
assert hs.live_today(P) == 5, hs.live_today(P)  # 第 6、7 條不記
lines_g = plug._fresh_lines(Ev(P, "30001"), P)
assert len(lines_g) == 3 and all("第" in x for x in lines_g), lines_g
S.over = {"remember_daily": 0}; say(Ev(P), "x\n<<好感0|平常|记住:不限的时候照记>>"); S.over = {}
assert hs.live_today(P) == 6
S.over = {"remember": False}
assert plug._fresh_lines(Ev(P), P) == []
say(Ev(P), "x\n<<好感0|平常|记住:关了不记>>"); assert hs.live_today(P) == 6
S.over = {}
# 群裡帶私聊那條標出來
store.db.execute("DELETE FROM moments WHERE qq=? AND text LIKE '第%'", (P,)); store.db.commit()
assert any("私聊里，群里别人不知道" in x for x in plug._fresh_lines(Ev(P, "30001"), P))
assert not any("群里别人不知道" in x for x in plug._fresh_lines(Ev(P), P))
assert sum(1 for _ in hs.fresh(P, now=now + 2 * 86400)) == 0  # 過了一天不帶
# 晚上整理心裡的 TA 看得到；回味時告訴模型那天當場記過的
assert "私聊里说最近失眠" in dg.Digest._heart_material(types.SimpleNamespace(bond=store, heart=hs), P)
d = dg.Digest.__new__(dg.Digest); d.s, d.bond, d.heart, d.closed, d.group = S(), store, hs, [], plug.group
bp = d._batch_prompt([{"doc_id": "m1", "ts": now, "gid": "30001", "people": {P: "小p"}, "text": "聊了打牌"}])
assert "当场记下的" in bp and "群里教本鱼打牌" in bp, bp

# ---- 道歉：只對不是正常態度的人看；像就照實告訴她；她寫 |原谅 才降，沒寫記成沒原諒 ----
class FakeSorry:
    hit = True
    async def check(self, text): return self.hit, 0.8, 0.5
plug.sorry = FakeSorry()
hs.apply_stance(Q, "恶意", now - 7200, suggest=3, note="骂本鱼", weight=0.8)
assert hs.get_stance(Q)["attitude"] == 3
ev = Ev(Q, "30001", text="对不起，刚才是我说话太冲了")
line = asyncio.run(plug._sorry_line(ev, Q))
assert "像是在道歉" in line and "冷处理" in line and "|原谅" in line and "变成戒备" in line, line
assert ev.get_extra("lively_bond_sorry")["att"] == 3
assert asyncio.run(plug._sorry_line(Ev(P, text="对不起"), P)) == ""  # 正常態度的人不看
assert asyncio.run(plug._sorry_line(Ev(tr.OWNER, text="对不起"), tr.OWNER)) == ""
S.over = {"sorry_live": False}; assert asyncio.run(plug._sorry_line(Ev(Q, text="对不起"), Q)) == ""; S.over = {}
FakeSorry.hit = False; assert asyncio.run(plug._sorry_line(Ev(Q, text="随便聊聊"), Q)) == ""; FakeSorry.hit = True
# 沒原諒：態度不變，記一筆
_, t = core.parse_tag("哼\n<<好感0|不屑>>")
plug._decide_sorry(ev, Q, t)
assert hs.get_stance(Q)["attitude"] == 3
assert "没原谅" in store.db.execute("SELECT note FROM events WHERE qq=? AND kind='sorry'", (Q,)).fetchone()[0]
# 晚上回味拆出同一次道歉：照她當時的，不再自己降
assert hs.decided_sorry_near(Q, time.time())
d._save([{"doc_id": "s1", "ts": time.time(), "gid": "30001", "people": {Q: "小q"}, "text": "道歉"}],
        [{"记忆": 1, "qq": Q, "事": "小q 跟本鱼道歉说话太冲", "类型": "道歉", "重要": 3}])
assert hs.get_stance(Q)["attitude"] == 3
# 原諒：降一級，記一段道歉片段
store.db.execute("DELETE FROM events WHERE qq=? AND kind='sorry'", (Q,)); store.db.commit()
st = hs.get_stance(Q); st["last_apology"] = 0; store.db.execute("UPDATE stance SET last_apology=0, apologies=0 WHERE qq=?", (Q,)); store.db.commit()
ev2 = Ev(Q, "30001", text="真的对不起")
asyncio.run(plug._sorry_line(ev2, Q))
_, t = core.parse_tag("算了\n<<好感+1|原谅|心软>>")
plug._decide_sorry(ev2, Q, t)
assert hs.get_stance(Q)["attitude"] == 2, hs.get_stance(Q)
assert any(m["kind"] == "道歉" and m["source"] == "live" for m in hs.moments(Q, 5))
# 6 小時內再道歉：告訴她這次原諒了態度也不變
line = asyncio.run(plug._sorry_line(Ev(Q, text="再说一次对不起"), Q))
assert "不会再变" in line, line
# 沒有提醒過的那一輪寫了 |原谅：不算
_, t = core.parse_tag("x\n<<好感0|原谅>>"); plug._decide_sorry(Ev(Q), Q, t); assert hs.get_stance(Q)["attitude"] == 2
# 惹滿三次、已經在冷淡：原諒了態度也不變，照實說
store.db.execute("UPDATE stance SET attitude=1, offenses=3, last_apology=0 WHERE qq=?", (Q,)); store.db.commit()
line = asyncio.run(plug._sorry_line(Ev(Q, text="对不起"), Q))
assert "要〈主人〉" in line or "要爹爹" in line or "再往下要" in line, line

# ---- 封閉：回味升到 4 的人記下來，交給她寫一句告訴主人（must） ----
d.closed = []
d._save([{"doc_id": "c1", "ts": time.time(), "gid": "30001", "people": {Z: "小z"}, "text": "骚扰"}],
        [{"记忆": 1, "qq": Z, "事": "小z 下流地骚扰本鱼", "类型": "恶意", "重要": 5, "态度": 4}])
assert hs.get_stance(Z)["attitude"] == 4 and d.closed and d.closed[0]["qq"] == Z, d.closed
told = []
async def fake_tell(s, facts, what, **kw): told.append((facts, what, kw))
bm.tell_owner = fake_tell
plug.digest = d
asyncio.run(plug._tell_closed())
assert told and told[0][2]["must"] and "封闭" in told[0][0] and f"/好感 态度 {Z} 0" in told[0][2]["card"], told
assert d.closed == []
# 主人不會被記成封閉
d._save([{"doc_id": "c2", "ts": time.time(), "gid": "30001", "people": {tr.OWNER: "爹"}, "text": "测试"}],
        [{"记忆": 1, "qq": tr.OWNER, "事": "爹爹测试", "类型": "恶意", "重要": 5, "态度": 4}])
assert d.closed == []

# ---- 群梗、群友之間：只收群聊記憶、在場的人 ----
batch = [{"doc_id": "g1", "ts": now, "gid": "30001", "people": {P: "小p", Q: "小q"}, "text": "..."},
         {"doc_id": "g2", "ts": now, "gid": "", "people": {P: "小p"}, "text": "私聊"}]
out = {"群梗": [{"记忆": 1, "梗": "token换白饭", "来历": "小p 先说的", "谁": [P, "99999"]},
                {"记忆": 2, "梗": "私聊的不算"}],
       "关系": [{"记忆": 1, "a": Q, "b": P, "怎么样": "常互损"}, {"记忆": 1, "a": P, "b": "88888", "怎么样": "不在场"},
                {"记忆": 2, "a": P, "b": Q, "怎么样": "私聊不算"}]}
assert d._save_group(batch, out) == (1, 1)
g = plug.group.gags("30001")
assert len(g) == 1 and g[0]["gag"] == "token换白饭" and g[0]["who"] == [P], g
d._save_group(batch, {"群梗": [{"记忆": 1, "梗": "token换白饭", "谁": [Q]}]})
assert plug.group.gags("30001")[0]["n"] == 2 and set(plug.group.gags("30001")[0]["who"]) == {P, Q}
pr = plug.group.pairs_of(P)
assert len(pr) == 1 and pr[0]["how"] == "常互损" and (pr[0]["a"], pr[0]["b"]) == tuple(sorted((P, Q))), pr
S.over = {"group_notes": False}; assert d._save_group(batch, out) == (0, 0); S.over = {}
assert "群梗" in plug._handle_admin(["群梗"]) and "token换白饭" in plug._handle_admin(["群梗", "30001"])
assert "常互损" in plug._handle_admin(["关系", P])
assert "群梗" in dg.GROUP_RULE.format() and "{{" not in dg.GROUP_RULE.format()

print("ok test_emotion_stage2")
