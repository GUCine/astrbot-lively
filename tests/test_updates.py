"""改動公告（gate updates.py、_deliver_updates、工具 lively_updates，10-28）：公告寫進 updates.jsonl，
門禁插件交給她寫一段私信〈主人〉；寫不出來再問一次，再不行發【后台】卡片；不限次數、睡覺不送；主人私聊記一筆她收到了什麼。
stub 掉 astrbot，號碼都是假的：10001 主人。

/usr/local/bin/python3 tests/test_updates.py
"""
import asyncio, json, sys, tempfile, time, types
from datetime import datetime
from pathlib import Path

sys.argv = [sys.argv[0]]
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import test_gate_draft as base  # noqa: E402  拿 stub 好的 astrbot

g = base.g
U = sys.modules[g.__name__.rsplit(".", 1)[0] + ".updates"]
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, "" if ok else extra)
    if not ok:
        fails.append(name)


def ts(h, m=0, day=28):
    return datetime(2026, 10, day, h, m, tzinfo=U.TZ).timestamp()


d = Path(tempfile.mkdtemp())
ups = U.Updates(d)
check("没文件：没有要送的", ups.pending() == [] and ups.recent() == [])
rows = [{"id": "a", "ts": ts(20), "title": "主人交代的事", "items": [
            {"what": "主人交代的事", "before": "以前主人交代的只记在主人私聊里", "now": "现在有个随身本子",
             "use": "lively_owner_rule 记、看、改、删"}]},
        {"id": "b", "ts": ts(21), "title": "改动公告", "items": [{"what": "改动公告", "now": "每次改了都告诉〈我〉"}]},
        {"id": "later", "ts": ts(23, day=29), "title": "明天的", "items": [{"what": "x"}]},
        {"id": "bad"}]
(d / "updates.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\nnot json\n", "utf-8")
check("读得出、坏行跳过", [a["id"] for a in ups.all()] == ["a", "b", "later"])
check("还没到时候的不送", [a["id"] for a in ups.pending(ts(22))] == ["a", "b"])
check("睡觉时间不送", ups.due(ts(3, day=29)) == [])
check("醒着送", [a["id"] for a in ups.due(ts(22))] == ["a", "b"])
f = U.facts_text(ups.pending(ts(22)))
check("事实：以前、现在、能做什么、结尾那句",
      "1. 主人交代的事：以前主人交代的只记在主人私聊里；现在有个随身本子。lively_owner_rule" in f
      and "1. 改动公告：现在每次改了都告诉〈我〉。" in f and f.endswith(U.TAIL), f)
ups.mark(ups.pending(ts(22)), "收到啦", "said", ts(22))
check("送过的不再送", ups.pending(ts(22)) == [])
check("存下来了", json.loads((d / "updates_state.json").read_text("utf-8"))["sent"]["a"]["say"] == "收到啦")
ups.mark([{"id": "c"}], "", "card", ts(22, 5))
(d / "updates.jsonl").write_text((d / "updates.jsonl").read_text("utf-8")
                                 + json.dumps({"id": "d", "ts": ts(22), "items": [{"what": "y"}]}) + "\n", "utf-8")
check("不限次数：同一天又有新的照送", [a["id"] for a in ups.due(ts(22, 30))] == ["d"])
check("recent 新的在前", [a["id"] for a in U.Updates(d).recent(2)] == ["later", "d"])


# ---- 送：她寫一段私信主人；寫不出來發卡片 ----
class Prov:
    def __init__(self, outs): self.outs, self.calls = list(outs), []
    async def text_chat(self, prompt, system_prompt):
        self.calls.append((prompt, system_prompt))
        o = self.outs.pop(0)
        if isinstance(o, Exception):
            raise o
        return types.SimpleNamespace(completion_text=o)


class Ctx:
    def __init__(self, prov): self.prov, self.sent = prov, []
    def get_provider_by_id(self, pid): return self.prov
    async def send_message(self, umo, chain): self.sent.append((umo, chain))


def gate_with(prov, down=False):
    gate = base.new_gate()
    gate.context = Ctx(prov)
    async def call_action(a, **kw):
        if down:
            raise RuntimeError("offline")
        return {"user_id": 99}
    fill = lambda t: t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    gate.s = types.SimpleNamespace(fill=fill, owner=lambda: "10001", private_umo=lambda q: f"p:{q}",
                                   owner_text=lambda t: t, persona_prompt=lambda: "人设", get=lambda k, d=None: d,
                                   provider=lambda k="provider_id": prov, is_owner=lambda q: str(q) == "10001",
                                   client=lambda: types.SimpleNamespace(api=types.SimpleNamespace(call_action=call_action)))
    gate.updates = U.Updates(Path(tempfile.mkdtemp()))
    return gate


class Chain:
    def __init__(self): self.text = ""
    def message(self, t):
        self.text += t
        return self


g.MessageChain = Chain
notes = []
g.note_outbox = lambda umo, text, kind="": notes.append((umo, text, kind))
ann = [{"id": "x1", "ts": ts(20), "title": "主人交代的事", "items": [{"what": "交代", "now": "有本子", "use": "lively_owner_rule"}]}]

gate = gate_with(Prov(['{"say": "爹爹～收到啦，本鱼有本子了"}']))
asyncio.run(gate._deliver_updates(ann))
sent = gate.context.sent
check("她的话私信了主人", len(sent) == 1 and sent[0][0] == "p:10001", sent)
check("主人私聊记了收到的公告和她说的", [n[2] for n in notes] == ["后台:公告", "公告"]
      and "本鱼收到了爹爹那边的改动公告" in notes[0][1] and notes[1][1] == "爹爹～收到啦，本鱼有本子了", notes)
check("记成送过、她说的话留着", gate.updates.state["sent"]["x1"]["say"] == "爹爹～收到啦，本鱼有本子了")
p_sys = gate.context.prov.calls[0][1]
check("提示词：人设＋公告规矩", p_sys.startswith("人设") and "[改动公告]" in p_sys and "边界太严" in p_sys)

notes.clear()
gate = gate_with(Prov(["看不懂", '{"say": "号码 20000001 是仇人"}']))
asyncio.run(gate._deliver_updates(ann))
check("写不出来（看不懂、带号码）发后台卡片", len(gate.context.sent) == 1
      and gate.updates.state["sent"]["x1"]["how"] == "card" and notes[-1][2] == "后台:公告", notes)
check("问了两次", len(gate.context.prov.calls) == 2)

notes.clear()
gate = gate_with(Prov([RuntimeError("timeout"), '{"say": "收到"}']))
asyncio.run(gate._deliver_updates(ann))
check("第一次出错再问一次", gate.updates.state["sent"]["x1"]["say"] == "收到")

gate = gate_with(Prov(['{"say": "收到"}']), down=True)
asyncio.run(gate._deliver_updates(ann))
check("QQ 连不上：不送、不记成送过", gate.context.sent == [] and "x1" not in gate.updates.state["sent"]
      and gate.updates.last_try > 0)


# ---- 工具：看最近的公告；主人那边看得到她当时说的 ----
class Ev:
    def __init__(self, sender): self.sender = sender
    def get_sender_id(self): return self.sender


gate = gate_with(Prov([]))
check("没有公告", asyncio.run(gate.tool_updates(Ev("20001"))) == "还没有改动公告")
(gate.updates.file).write_text(json.dumps(ann[0], ensure_ascii=False) + "\n"
                               + json.dumps({"id": "x2", "ts": ts(21), "title": "新的", "items": [{"what": "y", "now": "z"}]},
                                            ensure_ascii=False) + "\n", "utf-8")
gate.updates.mark(ann, "收到啦", "said", ts(20, 5))
r = asyncio.run(gate.tool_updates(Ev("10001")))
check("主人那边：新的在前、带她说的、没送到的标出来", r.index("新的") < r.index("主人交代的事")
      and "还没送到本鱼这边" in r and "本鱼跟爹爹说的：收到啦" in r, r)
r = asyncio.run(gate.tool_updates(Ev("20001"), count=1))
check("别人那边：不带她跟主人说的；count 管条数", "跟爹爹说的" not in r and "主人交代的事" not in r, r)

# 隔幾分鐘又一條：她上次說過的帶上（10-29 兩條公告她說了兩遍一樣的）
prov = Prov(['{"say": "放出来也能自己定，好"}'])
gate = gate_with(prov)
now = time.time()
gate.updates.mark([{"id": "a1"}], "收到啦，屏蔽这个本鱼念叨好久了", "said", now - 240)
gate.updates.mark([{"id": "old"}], "很久以前说的", "said", now - 86400)
asyncio.run(gate._deliver_updates([{"id": "a2", "ts": now, "title": "屏蔽谁你自己定", "items": [{"what": "x", "now": "y"}]}]))
pr = prov.calls[0][0]
check("带上几分钟前说过的", "已经私信爹爹说过：「收到啦，屏蔽这个本鱼念叨好久了」" in pr, pr)
check("太久以前的不带", "很久以前说的" not in pr, pr)

print("test_updates", "FAIL" if fails else "ok", fails)
sys.exit(1 if fails else 0)
