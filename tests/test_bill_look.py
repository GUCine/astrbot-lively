"""她查飯錢（billing lively_bill_look，10-27）：只有主人在的聊天裡有；餘額、今天扣了多少、還夠吃幾天，回傳只講事實；上次查餘額超過 10 分鐘才再查。

/usr/local/bin/python3 tests/test_bill_look.py（號碼都是假的：10001 主人、20001 群友、30001 群）
"""
import json, sqlite3, sys, tempfile, threading, time, types, importlib
from datetime import datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="bill_look_test_"))

import json, sqlite3, sys, tempfile, threading, time, types, importlib
from datetime import datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="ledger_test_"))


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
class Star:
    def __init__(self, context=None): self.context = context
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.star", Context=object, Star=Star, register=deco,
    StarTools=types.SimpleNamespace(get_data_dir=lambda name: str(TMP / name)))
mod("astrbot.core"); mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=object)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("aiohttp", ClientSession=object, ClientTimeout=object)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
bm = importlib.import_module("astrbot_plugin_lively_billing.main")
fails = []


import asyncio
fails = []
def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, extra)
    if not ok:
        fails.append(name)

OWNER = "10001"
b = object.__new__(bm.LivelyBilling)
b.s = types.SimpleNamespace(is_owner=lambda q: str(q) == OWNER, get=lambda k, d=None: d,
                            fill=lambda t: t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹"))
b.alert_at = 10.0
b.dir = TMP / "bill"; b.dir.mkdir(parents=True, exist_ok=True)
b.snap_file = b.dir / "balance.jsonl"
now = time.time()
LED = {"bal": 41.236, "updated": now - 120, "per_day": 8.5, "runway": 4.86,
       "list": [{"actual": 7.9, "partial": False}, {"actual": 9.12, "partial": False}, {"actual": 3.4, "partial": True}]}

# ---- 給她看的事實 ----
t = b.bill_text(LED)
check("余额、不是主人自己的钱", "DeepSeek 账户的余额" in t and "不是爹爹自己的钱" in t and "¥41.24" in t, t)
check("今天扣了、昨天一共", "今天到现在实际扣了 ¥3.40" in t and "昨天一共 ¥9.12" in t, t)
end = (datetime.now(bm.TZ) + timedelta(days=4.86)).strftime("%m-%d")
check("还够吃几天、到哪天", "一天 ¥8.50" in t and "还够吃 4.9 天" in t and end in t, t)
check("提醒线、降智版和画图不算", "低于 ¥10 时本鱼会提醒爹爹" in t and "降智版不花这笔钱" in t)
check("没有命令口吻", not any(w in t for w in ("你应该", "要告诉", "回话里", "别说")))
t = b.bill_text(dict(LED, per_day=None, runway=None, list=[{"actual": None, "partial": True}]), "HTTP 500")
check("算不出天数、刚才没查到照实说", "算不出还够吃几天" in t and "没查到：HTTP 500" in t and "今天到现在" not in t, t)
check("从没查到过", b.bill_text({"bal": None}).startswith("饭钱查不到"))

# ---- 只有主人在的聊天里有 ----
class Tools:
    def __init__(self): self.names = {"lively_bill_look", "lively_feed_note"}
    def get_tool(self, n): return n in self.names or None
    def remove_tool(self, n): self.names.discard(n)
class Ev:
    def __init__(self, qq, gid="", extra=None): self.qq, self.gid, self.extra = qq, gid, extra or {}
    def get_sender_id(self): return self.qq
    def get_group_id(self): return self.gid
    def get_extra(self, k): return self.extra.get(k)
for qq, gid, keep in ((OWNER, "", True), (OWNER, "30001", True), ("20001", "30001", False), ("20001", "", False)):
    req = types.SimpleNamespace(func_tool=Tools())
    asyncio.run(b.hide_bill_tool(Ev(qq, gid), req))
    check(f"工具 {'在' if keep else '不在'}：{qq} {gid or '私聊'}", ("lively_bill_look" in req.func_tool.names) == keep)
    check(f"别的工具不动：{qq}", "lively_feed_note" in req.func_tool.names)
check("别人叫到也查不了", asyncio.run(b.tool_bill_look(Ev("20001", "30001"))).startswith("没查"))
check("做她自己记下的事时查得了（mind 任務那一輪）", not asyncio.run(b.tool_bill_look(Ev("10000", extra={"lively_task_own": True}))).startswith("没查"))

# ---- 上次查余额超过 10 分钟才再查 ----
calls = []
async def fetch():
    calls.append(1)
    with b.snap_file.open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), "keys": {"deepseek": 41.2}}) + "\n")
b.fetch = fetch
b.ledger = lambda days: dict(LED, updated=time.time())
b.snap_file.write_text(json.dumps({"ts": int(now - 3600), "keys": {"deepseek": 42}}) + "\n")
r = asyncio.run(b.tool_bill_look(Ev(OWNER, "30001")))
check("一小时前查的：先再查", calls == [1] and "¥41.24" in r, r)
r = asyncio.run(b.tool_bill_look(Ev(OWNER)))
check("刚查过：不再查", calls == [1])
async def bad():
    raise RuntimeError("一个余额都没查到")
b.fetch = bad
b.snap_file.write_text(json.dumps({"ts": int(now - 3600), "keys": {"deepseek": 42}}) + "\n")
r = asyncio.run(b.tool_bill_look(Ev(OWNER)))
check("再查失败：用上次的、照实说", "没查到：一个余额都没查到" in r, r)
print("FAILS:", fails) if fails else print("bill look ok")
sys.exit(1 if fails else 0)
