"""感情收成六種、說話時那句「〈我〉跟 TA」、心裡的 TA 按欄位挑、印象卡短字的測試（10-27）：stub 掉 astrbot，用暫存的 bond.db。

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
OWNER, A, B, C, J = "10001", "20001", "20002", "20003", "20004"
core.OWNERS.clear(); core.OWNERS.add(OWNER)
tmp = tempfile.mkdtemp()
store = core.BondStore(str(Path(tmp) / "bond.db"))
hs = heart.HeartStore(store.db)
R = rel.Relations(store, hs)
now = time.time()
for q in (OWNER, A, B, C, J):
    store.on_talk(q, f"n{q}", now - 9 * DAY)

# ---- 六種：舊的信任、依賴讀成亲近；同一件事落到同一維度加起來再限幅 ----
assert heart.DIMS == ("亲近", "逗趣", "牵挂", "欣赏", "芥蒂", "反感")
assert heart._clamp_impacts({"信任": 1, "依赖": 1, "亲近": 1, "瞎写": 3}) == {"亲近": 2}
assert heart._clamp_impacts({"信任": -1, "亲近": 1}) == {}
hs.db.execute("INSERT INTO moments(qq,ts,scope,text,kind,weight,impacts,ref,created) VALUES(?,?,?,?,?,?,?,?,?)",
              (A, now - DAY, "dm", "旧片段", "关心", 0.6, json.dumps({"信任": 2}), "old", now))
assert hs.moments(A, 5)[0]["impacts"] == {"亲近": 2}
assert set(hs.feelings(A)) == set(heart.DIMS) and hs.feelings(A)["亲近"] > 0

# ---- 給她看的那句：A 很亲、爱互损 ----
for i in range(10):
    hs.add_moment(A, now - (i + 2) * DAY, f"A 好事{i}", kind="玩笑", weight=0.6, impacts={"亲近": 2, "逗趣": 2}, ref=f"a{i}")
fa = hs.feel(A)
assert fa["line"].startswith("〈我〉跟 TA：很亲") and "天天互相逗" in fa["line"], fa
assert fa["words"] == ["很亲", "爱互损"] and fa["public"] == fa["words"], fa
assert "疙瘩" not in fa["line"]

# ---- 玩笑那種的芥蒂：給她看的不算，好感度照算 ----
for i in range(6):
    hs.add_moment(J, now - (i + 1) * DAY, f"J 逗我{i}", kind="玩笑", weight=0.4, impacts={"逗趣": 2, "芥蒂": 2}, ref=f"j{i}")
assert hs.feelings(J)["芥蒂"] > 30 and hs.feelings(J, shown=True)["芥蒂"] == 0
lj = hs.feel(J)["line"]
assert "疙瘩" not in lj and ("常开玩笑" in lj or "互相逗" in lj), lj
assert hs.balance(J)["bad"] > 0  # 好感度那邊沒動
assert hs.heaviest(J, "芥蒂") is None

# ---- 真的冲突：帶上為的是哪件事（分量最重的那段），話裡提到 TA 時不帶原因、群友看的卡不放 ----
hs.add_moment(B, now - 5 * DAY, "B 很久以前骂了一句", kind="冲突", weight=0.6, impacts={"芥蒂": 1}, ref="b0")
hs.add_moment(B, now - DAY, "B 当众说本鱼坏话", kind="冲突", weight=0.6, impacts={"芥蒂": 3}, ref="b1")
hs.add_moment(B, now - 2 * DAY, "B 拿本鱼开涮", kind="玩笑", weight=0.4, impacts={"芥蒂": 2, "逗趣": 1}, ref="b2")
fb = hs.feel(B)
assert "小疙瘩" in fb["line"] or "有疙瘩" in fb["line"], fb
assert "为的是：" in fb["line"] and "B 当众说本鱼坏话" in fb["line"] and "开涮" not in fb["line"], fb
assert "为的是" not in fb["about"] and "疙瘩" in fb["about"], fb
assert not any("疙瘩" in w for w in fb["public"]) and any("疙瘩" in w for w in fb["words"]), fb

# ---- 聽 TA 倾诉、关心 TA 時心裡不好受：不算疙瘩，也不拿來當為的是 ----
K = "70005"
for i in range(5):
    hs.add_moment(K, now - (i + 1) * DAY, f"K 半夜说难过{i}，本鱼哄两句", kind="心事", feeling="无奈", weight=0.6, impacts={"芥蒂": 2, "牵挂": 1}, ref=f"k{i}")
hs.add_moment(K, now - DAY, "K 一直缠着本鱼", kind="日常", feeling="心疼", weight=0.6, impacts={"芥蒂": 3}, ref="k9")
assert hs.feelings(K)["芥蒂"] > 40 and hs.feelings(K, shown=True)["芥蒂"] == 0, (hs.feelings(K), hs.feelings(K, shown=True))
assert "疙瘩" not in hs.feel(K)["line"] and hs.heaviest(K, "芥蒂") is None
hs.add_moment(K, now - 3 * DAY, "K 说本鱼是 AI 滚", kind="冲突", feeling="小生气", weight=0.6, impacts={"芥蒂": 2}, ref="k10")
assert hs.heaviest(K, "芥蒂")["text"] == "K 说本鱼是 AI 滚" and 0 < hs.feelings(K, shown=True)["芥蒂"] < 30

# ---- 主人也帶 ----
for i in range(8):
    hs.add_moment(OWNER, now - (i + 1) * DAY, f"爹爹陪我{i}", kind="关心", weight=0.8, impacts={"亲近": 2, "信任": 2}, ref=f"o{i}")
assert "很亲" in hs.feel(OWNER)["line"]

# ---- 說話時：關係那句後面接著；沒到門檻的人不寫 ----
ra, rc = R.of(A), R.of(C)
assert "〈我〉跟 TA：很亲" in R.say(ra), R.say(ra)
assert "跟 TA：" not in R.say(rc) and rc["feel"]["line"] == "", R.say(rc)
assert "为的是" not in R.say_about(R.of(B)) and "疙瘩" in R.say_about(R.of(B)), R.say_about(R.of(B))
assert ra["known_days"] >= 10, ra["known_days"]

# ---- 心裡的 TA：不截半句，按欄位挑 ----
big = {"称呼": "小凛", "印象": "爱较真的HiFi党" * 2, "喜好": ["调EQ", "吹HiFi", "安利小塞子"], "雷区": ["聚会被掐的事"],
       "梗": [{"梗": f"梗{i}", "来历": "很长的来历" * 4} for i in range(6)], "最近": "带头刷烧鸡，一直喊饿",
       "语气": "嘴硬哼唧插嘴吐槽", "牵挂": ["考试", "感冒"], "私下": {"心事": ["分手了"], "牵挂": []}}
full = heart.heart_text(big)
assert "梗5" in full and "梗0" in full  # 不給 budget 全放（整理材料、主人看的）
t, dropped = heart.heart_fit(big, private=False, memories=False, budget=core.HEART_MAX)
assert len(t) <= core.HEART_MAX, (len(t), t)
assert "梗0" not in t and "梗5" in t  # 梗只帶最近 3 條
for k in ("叫 TA「小凛」", "印象：", "雷区：", "语气：", "最近：", "牵挂："):
    assert k in t, (k, t)
assert "私下" not in t
assert all(seg.count("：") <= 1 or seg.startswith("梗") for seg in t.split("；")), t
t2, d2 = heart.heart_fit(big, private=True, memories=False, budget=120)
assert len(t2) <= 120 and d2 and "叫 TA「小凛」" in t2 and "私下：分手了" in t2, (t2, d2)
assert not t2.endswith("、") and "…" not in t2

# ---- 注入：state_line 不再截 200 ----
p = store.get(A)
note = core.build_prompt(p, True, heart=t, rel=R.say(ra))
assert t in note and "〈我〉跟 TA：很亲" in note

# ---- 印象卡：認識幾天／聊過幾次／回憶幾段、好的短字 ----
img = importlib.import_module("astrbot_plugin_lively_bond.card_img")
out = img.render(Path(tmp) / "c", qq=A, name="阿月", favor=30, favor_desc="挺喜欢 TA", stage="熟人", mood="开心",
                 known_days=ra["known_days"], talks=5, moments=11, impression="会挑好ED", met="10-20", last="刚刚聊过",
                 avatar=None, me="本鱼", words=ra["feel"]["public"])
assert out.exists()
out2 = img.render(Path(tmp) / "f", qq=A, name="阿月", favor=30, favor_desc="挺喜欢 TA", stage="熟人", mood="开心",
                  known_days=3, talks=5, moments=11, impression="会挑好ED", met="10-20", last="刚刚聊过",
                  avatar=None, me="本鱼", words=["很亲", "爱互损", "挂心", "欣赏"], feed={"tier": 2, "name": "一碗饭"})
assert out2.exists()
print("feel words ok")
