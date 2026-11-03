"""關係讀口（bond relation.py）、主人測試不算惡意、態度每小時緩和的測試：stub 掉 astrbot，用暫存的 bond.db。

/usr/local/bin/python3 tests/test_relation.py（要有 PIL；號碼都是假的：10001 主人、2000x 群友）
"""
import sys, types, asyncio, time, importlib, tempfile, json
from pathlib import Path
# ---- stub astrbot ----
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
class Dummy:
    def __init__(self, *a, **k): pass
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, on_agent_done=deco,
      on_decorating_result=deco, llm_tool=deco, command=deco, after_message_sent=deco,
      EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict, sp=None)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", At=Dummy, Image=Dummy, Plain=Dummy)
mod("astrbot.api.star", Context=object, Star=Dummy, register=deco, StarTools=Dummy)
mod("astrbot.core"); mod("astrbot.core.agent")
class TextPart:
    def __init__(self, text): self.text = text; self.temp = False
    def mark_as_temp(self): self.temp = True; return self
mod("astrbot.core.agent.message", TextPart=TextPart)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Dummy, ResultContentType=Dummy)
mod("astrbot.core.star"); mod("astrbot.core.star.filter"); mod("astrbot.core.star.filter.command", GreedyStr=str)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
mod("aiohttp", ClientSession=Dummy, ClientTimeout=Dummy)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

core = importlib.import_module("astrbot_plugin_lively_bond.core")
heart = importlib.import_module("astrbot_plugin_lively_bond.heart")
rel = importlib.import_module("astrbot_plugin_lively_bond.relation")
dg = importlib.import_module("astrbot_plugin_lively_bond.digest")
DAY = 86400
OWNER, A, B, C = "10001", "20001", "20002", "20003"
core.OWNERS.clear(); core.OWNERS.add(OWNER)
tmp = tempfile.mkdtemp()
store = core.BondStore(str(Path(tmp) / "bond.db"))
hs = heart.HeartStore(store.db)
R = rel.Relations(store, hs)
now = time.time()
assert "adjust" in {r[1] for r in store.db.execute("PRAGMA table_info(people)")}

# ---- 好感度：回憶 + 回味後的即時調整（不算常來聊天的 +0.5）+ 手調 ----
for q in (OWNER, A, B, C):
    store.on_talk(q, f"n{q}", now - 3 * DAY)
for i in range(8):  # A：好事很多
    hs.add_moment(A, now - 2 * DAY - i, f"A 的好事{i}", kind="关心", weight=0.6, impacts={"亲近": 2, "逗趣": 1}, ref=f"a{i}")
for i in range(4):  # B：壞事
    hs.add_moment(B, now - 2 * DAY - i, f"B 骂人{i}", kind="冲突", weight=0.6, impacts={"芥蒂": 2, "反感": 1}, ref=f"b{i}")
store.db.execute("INSERT INTO digested(doc_id, ts, n) VALUES('d1', ?, 3)", (now - DAY,))
store.log(A, "favor", 3, 0, "模型给+3", "group", now - 2 * DAY)  # 回味之前的：已經在片段裡了，不算
store.log(A, "favor", 2, 0, "模型给+2", "group", now - 3600)
store.log(A, "favor", 0.5, 0, "常来聊天", "warm", now - 3600)  # 不算
store.log(C, "favor", -4, 0, "模型给-4", "group", now - 3600)
store.log(C, "favor", -15, 0, "模型给-5", "group", now - 1800)  # 加總 -19，封頂 -16
store.db.commit()
ra, rb, rc, ro = R.of(A), R.of(B), R.of(C), R.of(OWNER)
assert ra["live"] == 2 and ra["score"] == round(min(ra["base"] + 2, (ra["grow_cap"] or {"cap": 99})["cap"]), 1), ra  # 才認識一天，13 以上被封頂
assert ra["base"] == hs.affinity(A) and ra["tier"] in ("亲近", "喜欢"), ra
assert rb["score"] < -13 and rb["tier"] == "讨厌" and rb["desc"] in ("有点不爽 TA", "挺讨厌 TA"), rb
assert rc["live"] == -16 and rc["score"] == -16 and rc["hurt"] == 19, rc
assert ro["score"] == 100 and ro["tier"] == "喜欢" and ro["desc"] == "最喜欢" and "主人" in ro["stage"], ro
assert R.of("99999")["known"] is False and R.of("99999")["score"] == 0
assert len(R.all()) == 4
# 手調：調完剛好是這個數，之後照樣跟著聊天變
r = R.set_score(B, 12)
assert r["score"] == 12 and r["adjust"] != 0, r
store.log(B, "favor", 1, 0, "模型给+1", "group", now - 60); store.db.commit()
assert R.of(B)["score"] == 12.3 and R.of(B)["raw"] == 13  # 同一天裡只往目標追三成：一句話挪不了多少
# 舊的 stage/favor_desc：熟不熟只看熟悉度，喜不喜歡看好感度
p = dict(store.get(A), score=75)
assert core.favor_desc(p) == "很喜欢 TA" and core.stage(p) == "还不太认识的人"
assert core.favor_desc(dict(p, score=30)) == "挺喜欢 TA" and core.favor_desc(dict(p, score=-20)) == "有点不爽 TA"
assert core.tier_of(13) == ("亲近", "t-close") and core.tier_of(69.9) == ("亲近", "t-close") and core.tier_of(70) == ("喜欢", "t-love")
assert core.tier_of(-13.1) == ("讨厌", "t-hate")

# ---- 能不能主動找：主動私聊門檻 ≥13、態度正常 ----
assert ra["can_reach"] == (ra["score"] >= 13)
assert R.of(C)["can_reach"] is False and R.of(C)["reach_why"] == "好感度不够"
hs.apply_stance(A, "恶意", now - 7200, 2, "A 骂了人", 0.4)
ra = R.of(A)
assert ra["attitude"] == 2 and ra["can_reach"] is False and ra["reach_why"] == "态度是戒备", ra
assert ra["attitude_reason"] == "A 骂了人"

# ---- 態度帶進說話：只描述 ----
say = R.say(ra)
assert "有戒备" in say and "因为：A 骂了人" in say and "好感" not in say and str(ra["score"]) not in say, say
assert "冷淡" not in R.say(R.of(C)) and "戒备" not in R.say(R.of(C))
note = core.build_prompt(store.get(A), True, rel=say)
assert "有戒备" in note and "〈我〉和正在说话的" in note, note
assert note.count("〈我〉和正在说话的") == 1 and "你" not in note.split("【必须】")[0], note
# 主人：冷淡（最多到這裡）說成鬧脾氣
hs.apply_stance(OWNER, "冲突", now - 600, 1, "爹爹凶了本鱼", 0.4)
ro = R.of(OWNER)
assert ro["attitude"] == 1 and ro["can_reach"] and "闹脾气" in R.say(ro) and "冷淡" not in R.say(ro), R.say(ro)

# ---- 每天只往目標追一部分（上三成、下四成），最多 +4／-10；換日拿昨天最後的值當起點；主人手調不受限 ----
F, G = "20006", "20007"
store.on_talk(F, "nF", now - 3 * DAY); store.on_talk(G, "nG", now - 3 * DAY)
for i in range(12):
    hs.add_moment(F, now - 2 * DAY - i * DAY, f"F 的好事{i}", kind="关心", weight=0.8, impacts={"亲近": 2, "逗趣": 2, "欣赏": 2}, ref=f"f{i}")
    hs.add_moment(G, now - 2 * DAY - i, f"G 骂人{i}", kind="恶意", weight=0.8, impacts={"芥蒂": 3, "反感": 3}, ref=f"g{i}")
store.db.execute("INSERT INTO score_day VALUES(?, '2000-01-01', 0, 0)", (F,))
store.db.execute("INSERT INTO score_day VALUES(?, '2000-01-01', 0, 0)", (G,))
store.db.commit()
rf, rg = R.of(F), R.of(G)
assert rf["raw"] > 20 and rf["score"] == 4.0, rf
assert rg["raw"] < -25 and rg["score"] == -10.0, rg
assert R.of(F)["score"] == 4.0  # 同一天再算還是 4
store.db.execute("UPDATE score_day SET day='2000-01-02' WHERE qq=?", (F,)); store.db.commit()
assert R.of(F)["score"] == 8.0  # 換日：起點變成昨天的 4
store.db.execute("UPDATE score_day SET day='2000-01-03', shown=28 WHERE qq=?", (F,)); store.db.commit()
assert R.of(F)["score"] == round(28 + 0.3 * (R.of(F)["raw"] - 28), 1)  # 差得不多時只追三成，不一下補齊
assert R.set_score(F, 40)["score"] == 40  # 主人手調一次到位
assert R.of("")["score"] == 0

# ---- 目標分 13 以上按認識了多久封頂：13 以下不動，親近的還是親近 ----
K = "20010"
store.on_talk(K, "nK", now)
for i in range(30):  # 一天裡一大堆好事：回憶算出來很高，但才認識一天
    hs.add_moment(K, now - 3600 - i, f"K 的好事{i}", kind="关心", weight=0.8, impacts={"亲近": 2, "牵挂": 2, "欣赏": 2, "逗趣": 2}, ref=f"k{i}")
store.db.commit()
rk = R.of(K)
assert rk["base"] > 30 and rk["grow_cap"]["known_days"] == 1.0 and 13 < rk["raw"] < 16, rk
assert rk["raw"] == rk["grow_cap"]["cap"] == round(rel.GROW_FROM + rel.GROW_SPAN * (1 - rel.math.exp(-1 / rel.GROW_DAYS)), 1), rk
assert rk["tier"] == "亲近" and rk["can_reach"], rk
for d in range(1, 60):  # 天天都聊、聊了兩個月：上限跟著長
    hs.add_moment(K, now - d * DAY, f"K 那天{d}", kind="日常", weight=0.3, impacts={"亲近": 1}, ref=f"kd{d}")
store.db.commit()
kd = hs.known_days(K)
assert 40 < kd < 45, kd
assert R.of(K)["grow_cap"]["cap"] > 60 or R.of(K)["grow_cap"] is None, R.of(K)
# 13 以下的、壞的：不封頂
assert R.of(B)["grow_cap"] is None and R.of(G)["grow_cap"] is None
# 主人手調照樣一次到位（偏移加在封頂之後）
assert R.set_score(K, 70)["score"] == 70
assert R.of(OWNER)["grow_cap"] is None

# ---- 〈我〉自己的偏心：每次 -3～+3、累積 ±13、21 天淡一半；主人不算 ----
H = "20008"
store.on_talk(H, "nH", now)
assert R.add_lean(H, 2, "说话可爱") == 2 and R.lean_why(H) == "说话可爱"
assert R.add_lean(H, 9, "又可爱") == 5  # 一次最多 3
for _ in range(5):
    R.add_lean(H, 3, "一直可爱")
assert R.lean(H) == 13
assert abs(R.lean(H, time.time() + 21 * DAY) - 6.5) < 0.1
assert R.add_lean(OWNER, 3, "爹爹") == 0 and R.lean(OWNER) == 0
rh = R.of(H)
assert rh["lean"] == 13 and rh["lean_why"] == "一直可爱" and rh["raw"] == round(rh["base"] + 13 + rh["live"], 1), rh
assert any(e["kind"] == "lean" for e in store.events(H, 10))
# 回味整理心裡的 TA 時順手記偏心
dd = dg.Digest.__new__(dg.Digest)
class S2:
    def me(self): return "本鱼"
    def fill(self, t): return t
dd.s, dd.heart, dd.bond, dd.rel = S2(), hs, store, R
async def fake_ask(prompt, system):
    assert "偏心" in system
    assert "偏心：+13" in prompt, prompt
    return {"称呼": "小H", "印象": "很会撒娇", "偏心": {"分": -2, "为什么": "最近有点敷衍"}}
dd._ask = fake_ask
asyncio.run(dd.update_heart(H))
assert R.lean(H) == 11 and R.lean_why(H) == "最近有点敷衍"

# ---- 心情按時間結算（不改 p） ----
p = {"mood": "开心", "mood_word": "好开心", "mood_level": 2, "mood_at": now - 100 * 60}
assert core.settled_mood(p, now) == ("开心", "好开心", 1) and p["mood_level"] == 2
assert core.settled_mood(p, now + 3 * 3600) == ("平常", "", 0)
store.on_talk(B, "nB", now)
store.apply_tag(B, "nB", {"delta": 0, "mood": "委屈", "mood_word": "委屈", "impression": None}, "group", now)
assert R.of(B, now + 60)["mood_shown"] == "委屈" and R.of(B, now + 4 * 3600)["mood_shown"] == "平常"

# ---- 主人測試不算惡意（10-23 16:55 那次） ----
assert dg.owner_moment("恶意", {"信任": -2, "反感": 2, "芥蒂": 3, "亲近": 1}) == ("日常", {"芥蒂": 1, "亲近": 1})
assert dg.owner_moment("冲突", {"反感": 1}) == ("冲突", {"反感": 1})
assert "试边界" in dg.DIGEST_RULE and "不算恶意也不算冲突" in dg.DIGEST_RULE

class S:
    def me(self): return "本鱼"
d = dg.Digest.__new__(dg.Digest); d.s, d.heart = S(), hs
batch = [{"doc_id": "o1", "ts": now - 5 * 3600, "gid": "", "people": {OWNER: "主人"}, "text": "x"},
         {"doc_id": "x1", "ts": now - 5 * 3600, "gid": "", "people": {"20009": "路人"}, "text": "y"}]
hs.admin_attitude(OWNER, 0)
n = d._save(batch, [
    {"记忆": 1, "qq": OWNER, "事": "说测成人向边界", "感受": "委屈", "类型": "恶意", "重要": 5,
     "影响": {"信任": -2, "反感": 2, "芥蒂": 1}, "一起的": [], "态度": 2},
    {"记忆": 2, "qq": "20009", "事": "路人骂本鱼", "感受": "委屈", "类型": "恶意", "重要": 3, "影响": {"反感": 2}, "态度": 2}])
assert n == 2
mo = hs.moments(OWNER, 1)[0]
assert mo["kind"] == "日常" and mo["impacts"] == {"芥蒂": 1}, mo
assert hs.get_stance(OWNER)["attitude"] == 0
assert hs.get_stance("20009")["attitude"] == 2 and hs.moments("20009", 1)[0]["kind"] == "恶意"

# ---- 態度每小時看一次緩和：冷淡一天沒再犯就回正常，不等夜裡 ----
hs.apply_stance(C, "冲突", now - DAY - 3600, 1, "C 闹别扭", 0.4)
assert hs.get_stance(C)["attitude"] == 1
bm = importlib.import_module("astrbot_plugin_lively_bond.main")
plug = bm.LivelyBond.__new__(bm.LivelyBond); plug.heart = hs; plug._eased_at = 0.0
assert plug.ease_all() >= 1 and hs.get_stance(C)["attitude"] == 0
assert plug._eased_at > 0 and bm.EASE_EVERY == 3600
assert hs.get_stance(A)["attitude"] == 2  # 戒備兩小時前才犯，還沒到

# ---- 說話只讀心裡的 TA；聊天時記的印象馬上換進去；每週人物卡停了 ----
D, E = "20004", "20005"
store.on_talk(D, "nD", now); store.on_talk(E, "nE", now)
hs.set_heart(D, {"称呼": "小D", "印象": "爱吃火锅", "雷区": ["香菜"], "私下": {"心事": ["失恋了"], "牵挂": []}}, now=now - DAY)
upd = store.db.execute("SELECT updated FROM hearts WHERE qq=?", (D,)).fetchone()[0]
hs.note_impression(D, "老拿火锅馋本鱼", now)
h = hs.get_heart(D)
assert h["印象"] == "老拿火锅馋本鱼" and h["印象史"][0]["印象"] == "爱吃火锅" and h["雷区"] == ["香菜"], h
assert store.db.execute("SELECT updated FROM hearts WHERE qq=?", (D,)).fetchone()[0] == upd  # 晚上整理照樣看得到這段時間的片段
hs.note_impression(D, "老拿火锅馋本鱼", now); assert len(hs.get_heart(D)["印象史"]) == 1  # 一樣的不重複記
hs.note_impression(E, "新来的", now)  # 還沒有心裡的 TA：先建一份只有印象的，當成還沒整理過
assert hs.get_heart(E)["印象"] == "新来的" and store.db.execute("SELECT updated FROM hearts WHERE qq=?", (E,)).fetchone()[0] == 0
assert any(q == E for q, *_ in hs.stale_hearts()) is False  # 沒片段不用整理
hs.add_moment(E, now, "E 来打招呼", kind="日常", weight=0.3, impacts={"亲近": 1}, ref="e1")
assert any(q == E for q, *_ in hs.stale_hearts())

class Ev:
    def __init__(self, qq, gid=""): self.qq, self.gid, self.extra = qq, gid, {}
    def get_extra(self, k, d=None): return self.extra.get(k, d)
    def set_extra(self, k, v): self.extra[k] = v
    def get_sender_id(self): return self.qq
    def get_self_id(self): return "99"
    def get_sender_name(self): return "n" + self.qq
    def get_group_id(self): return self.gid
    message_str = "火锅"
class Cfg:
    def __init__(self, **kw): self.kw = kw
    def get(self, k, d=None): return self.kw.get(k, d)
plug.store, plug.s = store, Cfg(inject_heart=False, heart_moments=2)
heart_g, moms = plug._heart_bits(Ev(D, "30001"), D, False)
heart_d, _ = plug._heart_bits(Ev(D), D, False)
assert "失恋" not in heart_g and "失恋" in heart_d and moms == [] and "雷区：香菜" in heart_g
store.db.execute("UPDATE people SET impression='旧印象' WHERE qq=?", (D,)); store.db.commit()
note = core.build_prompt(store.get(D), True, heart=heart_g, rel=R.say(R.of(D)))
assert note.split("\n")[1].count("印象") == 1 and "〈我〉心里的 TA：" in note and "老拿火锅馋本鱼" in note and "旧印象" not in note, note
note = core.build_prompt(store.get(E), True, heart="", rel=R.say(R.of(E)))  # 心裡沒有 TA 才帶聊天時記的
store.db.execute("UPDATE people SET impression='新来的' WHERE qq=?", (E,)); store.db.commit()
assert "〈我〉对 TA 的印象：新来的" in core.build_prompt(store.get(E), True, heart="", rel="")
assert R.of(D)["impression"] == "老拿火锅馋本鱼"

# 好感標記裡的印象：寫 people.impression；10-28 起「记住」開著（預設）印象只在凌晨改，不換進心裡的 TA，關掉才照舊換
plug._sync_owners = lambda: None
class Resp: completion_text = "好呀\n<<好感+1|开心|印象:请本鱼吃火锅的好人>>"
def tev():
    e = Ev(D, "30001"); e.extra["lively_bond_qq"] = D; return e
ev = tev()
asyncio.run(plug.take_tag(ev, Resp()))
assert store.get(D)["impression"] == "请本鱼吃火锅的好人" and hs.get_heart(D)["印象"] == "老拿火锅馋本鱼"
_s = plug.s
class _Off:
    def __getattr__(self, k): return getattr(_s, k)
    def get(self, k, d=None): return False if k == "remember" else _s.get(k, d)
plug.s = _Off()
class Resp: completion_text = "好呀\n<<好感+1|开心|印象:请本鱼吃火锅的好人>>"
asyncio.run(plug.take_tag(tev(), Resp()))
assert hs.get_heart(D)["印象"] == "请本鱼吃火锅的好人"
plug.s = _s

# 10-29 15:09：調工具前那步帶的標記不經過 on_llm_response，發送前清掉時照樣記（一輪只記一次）；
# 之後那步把记住的事寫成正文的一行，拿掉
class P:
    def __init__(self, text): self.text = text
_plain, bm.Plain = bm.Plain, P
ev = tev()
ev._result = types.SimpleNamespace(chain=[P("真给本鱼画的？\n标记：<<好感+1|被逗乐|记住:手绘一张一亿token的鲸元券塞给本鱼>>真给本鱼画的？")])
ev.get_result = lambda: ev._result; ev.unified_msg_origin = "g"; ev.stop_event = lambda: None
asyncio.run(plug.last_check(ev))
assert "<<" not in ev._result.chain[0].text and ev.extra.get("lively_bond_tagged")
assert ev.extra["lively_bond_remember"] == "手绘一张一亿token的鲸元券塞给本鱼", ev.extra
assert any("鲸元券" in (r[0] or "") for r in hs.db.execute("SELECT text FROM moments WHERE qq=? AND source='live'", (D,)))
class Resp: completion_text = "好\n<<好感+1|开心|记住:又一件>>"
asyncio.run(plug.take_tag(ev, Resp()))  # 同一輪最後那步又寫一個：不重複記
assert not any("又一件" in (r[0] or "") for r in hs.db.execute("SELECT text FROM moments WHERE qq=?", (D,)))
ev._result = types.SimpleNamespace(chain=[P("真给本鱼画的？\n手绘一张一亿 token 的鲸元券塞给本鱼")])
asyncio.run(plug.last_check(ev))
assert [c.text for c in ev._result.chain] == ["真给本鱼画的？"], [c.text for c in ev._result.chain]
msgs = [types.SimpleNamespace(role="user", content="给你"),
        types.SimpleNamespace(role="assistant", content="标记：<<好感+1|被逗乐|记住:手绘一张一亿token的鲸元券塞给本鱼>>真给本鱼画的？"),
        types.SimpleNamespace(role="tool", content="发了"),
        types.SimpleNamespace(role="assistant", content="真给本鱼画的？\n手绘一张一亿 token 的鲸元券塞给本鱼")]
asyncio.run(plug.clean_history(ev, types.SimpleNamespace(messages=msgs), None))
assert "<<" not in msgs[1].content and msgs[3].content == "真给本鱼画的？", (msgs[1].content, msgs[3].content)
bm.Plain = _plain

# 停卡：只有卡的人搬進心裡的 TA（只做一次），當成還沒整理過；不再做卡
F = "20006"
store.on_talk(F, "nF", now)
store.set_card(F, {"称呼": "阿F", "喜好": ["猫"], "雷区": ["加班"], "梗": [], "最近": "", "相处": "慢慢聊"}); store.set_card(D, {"称呼": "别搬我"})
store.db.commit()
plug._retire_cards()
hf = hs.get_heart(F)
assert hf["称呼"] == "阿F" and hf["雷区"] == ["加班"] and hf["语气"] == "慢慢聊", hf
assert store.db.execute("SELECT updated FROM hearts WHERE qq=?", (F,)).fetchone()[0] == 0
assert hs.get_heart(D)["称呼"] == "小D"  # 本來就有的不動
store.set_card("20007", {"称呼": "第二次"}); plug._retire_cards()
assert hs.get_heart("20007") is None
assert not hasattr(bm.LivelyBond, "update_cards") and not hasattr(bm.LivelyBond, "make_card")

# ---- 嫌煩名單、找人記錄、私聊能不能開口 ----
G = "20008"
store.on_talk(G, "nG", now - 3 * DAY)
for i in range(10):
    hs.add_moment(G, now - 2 * DAY - i, f"G 的好事{i}", kind="关心", weight=0.6, impacts={"亲近": 2, "逗趣": 2}, ref=f"g{i}")
store.db.commit()
assert R.of(G)["can_reach"] and R.of(G)["last_reach"] == 0, R.of(G)
op = R.opening(G, now)
assert op == {"continuing": False, "ok": True, "why": ""}, op
assert R.set_quiet(G, name="nG", why="说本鱼吵") and R.of(G)["quiet"] and R.of(G)["quiet_why"] == "说本鱼吵"
# 10-30 起嫌煩名單只記著，不攔主動找 TA（她自己定）
assert R.of(G)["can_reach"] and R.opening(G, now)["ok"] and G in R.quiet_people()
assert R.set_quiet(G, off=True) and not R.set_quiet(G, off=True) and not R.of(G)["quiet"]
R.note_reach(G, "proactive", now - 3600)
assert R.of(G)["last_reach"] == now - 3600
assert R.opening(G, now) == {"continuing": False, "ok": False, "why": "一天内已经主动找过 TA"}
assert R.opening(G, now + DAY)["ok"]
store.on_talk(G, "nG", now - 600)  # TA 剛跟〈我〉說過話：接話，不擋
assert R.opening(G, now)["continuing"] and R.opening(G, now)["ok"]
assert R.opening(C, now - 3 * DAY + 60)["continuing"]  # C 好感度不夠，但接話照樣不擋
assert R.opening(C, now + DAY) == {"continuing": False, "ok": False, "why": "好感度不够"}
assert R.opening(OWNER, now + 30 * DAY)["ok"]
kinds = {r[0] for r in store.db.execute("SELECT kind FROM events WHERE qq=?", (G,))}
assert {"quiet", "reach"} <= kinds

# ---- 投喂：飯錢插件的 feeds.json 照實帶進讀口和說話的那句 ----
rel.FEEDS.parent.mkdir(parents=True, exist_ok=True)
if rel.FEEDS.exists():
    rel.FEEDS.unlink()
assert rel.fed_by() == {} and R.of(G)["fed"] is None and "投喂" not in R.say(R.of(G))
day0 = time.mktime((2026, 10, 26, 8, 0, 0, 0, 0, -1))
rows = [{"id": "1", "ts": day0, "qq": G, "name": "nG", "amount": 15, "note": "token换大白饭", "added": day0 + 60,
         "via": "chat", "told_by": OWNER, "told_owner": True},
        {"id": "2", "ts": day0 - 3 * DAY, "qq": G, "name": "nG", "amount": 5.5, "note": "", "added": day0 - 3 * DAY},
        {"id": "3", "ts": day0, "qq": "30001", "name": "", "amount": 2, "note": "", "added": day0},
        {"id": "4", "ts": day0, "qq": "坏的", "amount": 9}, "也是坏的"]
rel.FEEDS.write_text(json.dumps(rows, ensure_ascii=False), "utf-8")
fb = rel.fed_by()
assert fb[G] == {"n": 2, "total": 20.5, "last_ts": day0, "last_amount": 15.0, "last_note": "token换大白饭",
                 "last_from": "〈主人〉跟〈我〉说的"}, fb[G]
assert set(fb) == {G, "30001"}
assert R.of(G)["fed"]["total"] == 20.5
say = R.say(R.of(G))
assert "TA 投喂过〈我〉饭钱：2 次共 ¥20.5，最近一次 10月26日（token换大白饭），〈主人〉跟〈我〉说的" in say, say
assert say.endswith("〈主人〉跟〈我〉说的；投喂档位：一碗饭（5 档里的第 2 档，TA 的印象卡换成这一档的背景）"), say
assert "还差" not in say and "30" not in say.split("投喂档位")[1]  # 不帶下一檔要多少錢
about = R.say_about(R.of(G))
assert "〈主人〉跟〈我〉说的；投喂档位：一碗饭" in about and "QQ 20008 就是「nG」" in about, about
assert R.say_about(R.of("30001")) == ("QQ 30001：〈我〉没跟这个号聊过，不知道是谁；TA 10月26日投喂过〈我〉饭钱 ¥2，〈主人〉收到后记在饭钱本上的"
                                      "；投喂档位：一口饭（5 档里的第 1 档，TA 的印象卡换成这一档的背景）")
f = R.of(G)["fed"]
assert (f["tier"], f["tier_name"], f["tier_count"], f["next_amount"], f["next_name"]) == (2, "一碗饭", 5, 30, "一锅饭"), f
assert "tier" not in rel.fed_by()[G]  # 快取裡的匯總不被改
# ---- 投喂檔位：設定怎麼寫、關掉、改了馬上生效 ----
assert rel.parse_feed_tiers(rel.FEED_TIERS) == [(1, "一口饭"), (10, "一碗饭"), (30, "一锅饭"), (100, "长期饭票"), (300, "金饭碗")]
assert rel.parse_feed_tiers("50|大\n坏的\n0|零\n-3|负\n¥5 | 小 \n9|\n1|a\n2|b\n3|c\n4|d") == [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, "小")]
assert rel.parse_feed_tiers("") == [] and rel.parse_feed_tiers(None) == []
assert rel.feed_tier(0.99, rel.parse_feed_tiers(rel.FEED_TIERS))["tier"] == 0
assert rel.feed_tier(300, rel.parse_feed_tiers(rel.FEED_TIERS)) == {"tier": 5, "tier_name": "金饭碗", "tier_count": 5, "next_amount": 0, "next_name": ""}
assert rel.feed_tier(5, [])["tier"] == 0
off = rel.Relations(store, hs, feed_tiers="")
assert off.of(G)["fed"]["tier"] == 0 and "档位" not in off.say(off.of(G)) and off.of(G)["fed"]["total"] == 20.5
conf = {"t": "20|小碗"}
live = rel.Relations(store, hs, feed_tiers=lambda: conf["t"])
assert live.of(G)["fed"]["tier"] == 1 and "投喂档位：小碗（1 档里的第 1 档" in live.say(live.of(G))
conf["t"] = "1|一\n5|五\n20|二十\n21|二十一"
assert live.of(G)["fed"]["tier_name"] == "二十" and live.of(G)["fed"]["next_name"] == "二十一"
for r, want in (({"via": "panel"}, "〈主人〉收到后在后台记在饭钱本上的"), ({"via": "chat", "qq": "1", "told_by": "1"}, "TA 自己跟〈我〉说的"),
                ({"via": "chat", "qq": "1", "told_by": "2", "told_name": "乙"}, "乙跟〈我〉说的")):
    assert rel.feed_from(r) == want, (r, rel.feed_from(r))
rel.FEEDS.write_text("{壞了", "utf-8")
import os; os.utime(rel.FEEDS, (time.time() + 5, time.time() + 5))
assert rel.fed_by() == {} and "投喂" not in R.say(R.of(G))
rel.FEEDS.unlink()
assert rel.fed_by() == {}
print("relation ok")
