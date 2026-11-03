"""相處經驗跟著最新的人設和主人定的規矩走（10-26）：每晚總結時帶上人設和規矩、經驗帶依據；
人設或規矩一改就把舊經驗重整一遍。順便測飯錢按模型設定算單價、面板日誌留 Traceback 結尾。
stub 掉 astrbot，模型回答是假的。

/usr/local/bin/python3 tests/test_evolve_notes.py
"""
import ast, asyncio, json, sys, tempfile, types, importlib
from pathlib import Path

def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
class Dummy:
    def __init__(self, *a, **k): pass
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, on_llm_response=deco, llm_tool=deco, command=deco,
      on_decorating_result=deco, after_message_sent=deco, on_agent_done=deco, permission_type=deco, PermissionType=types.SimpleNamespace(ADMIN=0),
      EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1, GROUP_MESSAGE=2))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Plain=Dummy)
class Star:
    def __init__(self, context=None): self.context = context
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=Dummy)
mod("astrbot.core"); mod("astrbot.core.agent"); mod("astrbot.core.agent.message", TextPart=Dummy)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Dummy, ResultContentType=Dummy)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ev_mod = importlib.import_module("astrbot_plugin_lively_evolve.main")


class S:
    def __init__(self): self.persona, self.rules = "人设第一版：被惹到可以骂回去", []
    def get(self, k, d=None): return self.rules if k == "owner_rules" else d
    def fill(self, t): return str(t).replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹").replace("〈名字〉", "小肥鱼")
    def persona_prompt(self): return self.persona


def make(answers):
    e = object.__new__(ev_mod.LivelyEvolve)
    e.s, e.logs, e.asked = S(), [], []
    e.state = {"enabled": True, "notes": [{"text": "有人嘴上不干净就短句挡回，别带刺嘲讽", "ts": 1}]}
    e._busy = asyncio.Lock()
    e._save = lambda: None
    e.toolbox = types.SimpleNamespace(names_line=lambda: "")
    e._log = lambda kind, **d: e.logs.append((kind, d))

    async def llm(prompt, system, timeout=90):
        e.asked.append((e.s.fill(prompt), e.s.fill(system)))
        return json.dumps(answers.pop(0), ensure_ascii=False)
    e._llm = llm
    return e


def run(c): return asyncio.run(c)


# 規則本身：不再叫它「不能讓〈我〉罵人」「主人的糾正最重要」，要它寫依據、尺度不歸經驗管
R = ev_mod.REFLECT_RULE
assert "不能让〈我〉骂人" not in R and "纠正最重要" not in R, "舊規則還在"
assert "尺度不归经验管" in R and "依据" in R and "试功能" in R

# 每晚總結：帶上人設、規矩、舊經驗（標可能過時），經驗帶依據，記下對齊的指紋
e = make([{"notes": [{"text": "X 被怼了还接着玩，不像真生气", "from": "群里 X 回了哈哈哈"}, "旧格式的字符串也认"], "changed": "换成看到的事"}])
e._exchanges = lambda t0, t1: ["[群聊]\n〈我〉：…"] * 6
e.s.rules = ["有人要印象卡时，发不发由〈我〉自己决定"]
out = run(e.update_notes(ev_mod.datetime.now(ev_mod.TZ)))
prompt, system = e.asked[0]
assert "人设第一版" in prompt and "发不发由本鱼自己决定" in prompt and "可能已经过时" in prompt, prompt[:300]
assert e.state["notes"][0]["from"] == "群里 X 回了哈哈哈" and e.state["notes"][1]["text"] == "旧格式的字符串也认"
assert e.state["notes_basis"] == e._basis()[1] and out == "换成看到的事"
print("每晚总结带人设和规矩 ok")

# 模型沒給出能用的：舊的留著，不清空
before = list(e.state["notes"])
e2 = make([{"notes": []}]); e2._exchanges = e._exchanges; e2.state["notes"] = before
assert run(e2.update_notes(ev_mod.datetime.now(ev_mod.TZ))) == "" and e2.state["notes"] == before
print("模型没给结果时不清空 ok")

# 人設沒改：不重整；改了：按新的重整，記下刪了哪條
e3 = make([{"notes": [{"text": "Y 深夜来私聊多半想有人陪", "from": "10-25 私聊"}],
            "dropped": [{"text": "有人嘴上不干净就短句挡回，别带刺嘲讽", "why": "人设说被惹到可以骂回去"}], "changed": "删了一条和人设冲突的"}])
e3.state["notes_basis"] = e3._basis()[1]
assert run(e3.align_notes()) == "" and not e3.asked, "人設沒改不該問模型"
e3.s.persona = "人设第二版：放开了就别再演害羞"
r = run(e3.align_notes())
assert "人设第二版" in e3.asked[0][0] and r == "删了一条和人设冲突的"
assert [n["text"] for n in e3.state["notes"]] == ["Y 深夜来私聊多半想有人陪"]
assert e3.logs[-1][0] == "notes_align" and e3.logs[-1][1]["dropped"][0]["why"].startswith("人设")
assert e3.state["notes_basis"] == e3._basis()[1]
# 規矩改了也算
e3.s.rules = ["新规矩"]
assert e3.state["notes_basis"] != e3._basis()[1]
print("人设、规矩改了就重整 ok")

# 主人指令
e4 = make([{"notes": [{"text": "有人嘴上不干净就短句挡回，别带刺嘲讽", "from": "b"}], "dropped": [], "changed": ""}])
assert "不冲突" in run(e4._owner_cmd("成长 重整经验")), "模型原樣留著就說不用改"
print("成长 重整经验 ok")


# 飯錢：單獨算價的模型設定
def pick(path, name):
    t = ast.parse(Path(path).read_text("utf-8"))
    ns = {"re": __import__("re"), "LOG_MAX": 600}
    exec(compile(ast.Module([n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == name], []), path, "exec"), ns)
    return ns[name]

pp = pick(ROOT / "astrbot_plugin_lively_billing/main.py", "_pid_prices")
assert pp(["workbuddy-flash=0", "x=1,0.02,4", "bad", "y=abc"]) == {"workbuddy-flash": (0.0, 0.0, 0.0), "x": (1.0, 0.02, 4.0)}
print("饭钱单独算价 ok")

# 面板日誌：Traceback 留結尾（真正的錯誤那行）
clip = pick(ROOT / "astrbot_plugin_lively_panel/main.py", "_clip_log")
tb = "Traceback (most recent call last):\n" + "  File x, line 1\n" * 80 + "ValueError: 真正的错误在这里"
c = clip(tb)
assert len(c) <= 600 and c.endswith("ValueError: 真正的错误在这里") and c.startswith("Traceback"), c[-80:]
assert clip("短的") == "短的"
print("日志留结尾 ok")
# 提案記下〈主人〉定的做法（10-26）：「提案 N 好 怎么做」
e5 = make([])
e5.state.update(proposals=[{"n": 1, "title": "记忆自查", "status": "pending"}, {"n": 2, "title": "群聊回看", "status": "pending"}],
                learned=[], routines=[], history=[])
r5 = run(e5._owner_cmd("提案 1 好 删除要〈主人〉确认才删"))
assert e5.state["proposals"][0] == {"n": 1, "title": "记忆自查", "status": "ok", "note": "删除要〈主人〉确认才删"}, e5.state["proposals"][0]
assert "删除要" in e5.logs[-1][1]["text"]
run(e5._owner_cmd("提案 2 好"))
assert "note" not in e5.state["proposals"][1] and e5.state["proposals"][1]["status"] == "ok"
assert "（删除要〈主人〉确认才删）" in run(e5._owner_cmd("提案 列表"))
# 主人回提案沒有固定說法（10-26 晚）：她用 lively_proposal 記，只有主人說了才記得上
e5.s.is_owner = lambda qq: str(qq) == "10001"
e5._learned = lambda what, n=None: f"记下了学会的本领：{what}"
class PEv:
    def __init__(self, qq): self.qq = qq
    def get_sender_id(self): return self.qq
e5.state["proposals"].append({"n": 3, "title": "表情包偏好", "status": "pending"})
r = run(e5.tool_proposal(PEv("20001"), 3, "好"))
assert r.startswith("没记") and "爹爹" in r and e5.state["proposals"][2]["status"] == "pending", r
r = run(e5.tool_proposal(PEv("10001"), 3, "不要", "先观察几天"))
assert e5.state["proposals"][2]["status"] == "no" and r == "提案【3】表情包偏好记成不要了，以后不再提（为什么：先观察几天）", r
r = run(e5.tool_proposal(PEv("10001"), 1, "做好了"))
assert e5.state["proposals"][0]["status"] == "done" and r.startswith("提案【1】记忆自查记成做好了"), r
assert run(e5.tool_proposal(PEv("10001"), 1, "好")).endswith("已经做好了，不用再定")
assert run(e5.tool_proposal(PEv("10001"), 9, "好")) == "没有提案【9】"
# 主人私信「提案 2 好」不攔成指令（交給她），「提案 列表」照舊是後台指令
class OEv(PEv):
    def __init__(self, text): super().__init__("10001"); self.message_str, self.stopped, self.sent = text, False, []
    def stop_event(self): self.stopped = True
    async def send(self, chain): self.sent.append(chain)
o = OEv("提案 2 好 先在小凛群试")
run(e5.owner(o))
assert not o.stopped and not o.sent
# 相處經驗一天才變一次：放 system 最後（命中得到快取），不掛在這輪消息後面；rules_in_system 關掉照舊
class TP:
    def __init__(self, text): self.text, self.temp = text, False
    def mark_as_temp(self): self.temp = True; return self
ev_mod.TextPart = TP
S.conf = {}
S.shared = lambda self, k, d=None: self.conf.get(k, d)
e = make([]); e.state.update(notes=[{"text": "X 被怼了还接着玩", "ts": 1}], learned=[], history=[], proposals=[])
ask = types.SimpleNamespace(message_str="早")
req = types.SimpleNamespace(system_prompt="人设", extra_user_content_parts=[])
run(e.inject(ask, req)); run(e.inject(ask, req))
assert req.system_prompt.startswith("人设\n\n[系统提示，不要复述] 本鱼从大家的反应里记下的事") and req.system_prompt.count("X 被怼了") == 1, req.system_prompt
assert req.extra_user_content_parts == []
req = types.SimpleNamespace(system_prompt="人设", extra_user_content_parts=[])
run(e.inject(types.SimpleNamespace(message_str="你最近学会什么了"), req))  # 問成長那段照舊掛在這輪消息後面
assert "X 被怼了" in req.system_prompt and [("成长" in p.text, p.temp) for p in req.extra_user_content_parts] == [(True, True)]
S.conf["rules_in_system"] = False
req = types.SimpleNamespace(system_prompt="人设", extra_user_content_parts=[])
run(e.inject(ask, req))
assert req.system_prompt == "人设" and [("X 被怼了" in p.text, p.temp) for p in req.extra_user_content_parts] == [(True, True)]
print("相处经验放 system 最后 ok")
print("all ok")
