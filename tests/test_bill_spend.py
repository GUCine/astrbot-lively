"""飯錢插件的「錢花在哪」和投餵記錄（10-26）：按做的事分類（舊記錄沒標做什麼也認得出看圖和壓縮歷史）、
降智版不算錢只記次數、餘額掉得比記到的多單列「沒記到的」；投餵記一筆、刪一筆、擋掉錯的號碼和金額、主人私信指令。
也順手測面板回成長提案時帶上主人定的做法。
stub 掉 astrbot，號碼都是假的（10001 主人、20001、20002 群友、30001 群）。

/usr/local/bin/python3 tests/test_bill_spend.py
"""
import asyncio, json, sqlite3, sys, tempfile, time, types, importlib
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="spend_test_"))


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
class Chain:
    def __init__(self): self.chain = []
    def message(self, t): self.chain.append(t); return self
class Star:
    def __init__(self, context=None): self.context = context
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.star", Context=object, Star=Star, register=deco,
    StarTools=types.SimpleNamespace(get_data_dir=lambda name: str(TMP / name)))
mod("astrbot.core"); mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Chain)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("aiohttp", ClientSession=object, ClientTimeout=object)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
bm = importlib.import_module("astrbot_plugin_lively_billing.main")
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, extra)
    if not ok:
        fails.append(name)


# ---- 分類 ----
cat = bm._spend_cat
check("看图（标了 caption）", cat({"who": "astrbot", "pid": "deepseek-flash", "what": "caption", "miss": 9000}) == "look")
check("压缩历史（标了 compress）", cat({"who": "astrbot", "pid": "deepseek-flash", "what": "compress", "miss": 100}) == "squeeze")
check("旧记录：图片描述的模型设定", cat({"who": "astrbot", "pid": "deepseek-flash-caption", "miss": 5000, "hit": 0}) == "look")
check("旧记录：输入短的是看图", cat({"who": "astrbot", "pid": "deepseek-flash", "miss": 800, "hit": 200}) == "look")
check("旧记录：输入长的是压缩", cat({"who": "astrbot", "pid": "deepseek-flash-dm", "miss": 3000, "hit": 12000}) == "squeeze")
check("门禁包的看图", cat({"who": "lively_gate", "pid": "deepseek-flash-caption"}) == "look")
check("门禁别的（起草稿重写）", cat({"who": "lively_gate", "pid": "deepseek-flash-dm"}) == "other")
check("回味", cat({"who": "lively_bond", "pid": "deepseek-flash-bg"}) == "digest")
check("记忆插件和记忆分层", cat({"who": "livingmemory"}) == "remember" and cat({"who": "lively_memtier"}) == "remember")
check("测试", cat({"who": "lively_bond_test"}) == "test" and cat({"who": "caption_test"}) == "test")
check("认不出", cat({"who": "其他"}) == "other")

# ---- AstrBot 自己的呼叫在做什麼 ----
names = ["prompt", "session_id", "image_urls", "func_tool", "contexts", "system_prompt"]
check("带图、没历史 → 看图", bm._what(names, ("描述这张图",), {"image_urls": ["a.jpg"]}) == "caption")
ctx = [{"role": "user", "content": "你好"}, {"role": "user", "content": bm.COMPRESS_MARK + " please"}]
check("最后一条是压缩的话 → 压缩", bm._what(names, (), {"contexts": ctx}) == "compress")
check("普通的 → 空", bm._what(names, ("你好",), {"contexts": [{"role": "user", "content": "你好"}]}) == "")

# ---- spend ----
b = object.__new__(bm.LivelyBilling)
b.prices, b.peak_double, b.image_price = (1.0, 0.02, 4.0), False, 0.3
b.voice_price = 21.6
b.pid_prices = bm._pid_prices(["workbuddy-flash=0"])
b.s = types.SimpleNamespace(get=lambda k, d=None: d)
b.dir = TMP / "bill"; b.dir.mkdir(parents=True, exist_ok=True)
b.usage_file, b.users_file = b.dir / "usage.jsonl", b.dir / "users.jsonl"
b.feeds_file = b.dir / "feeds.json"
b.voice_file = b.dir / "voice.json"
import threading
b._feeds_lock = threading.Lock()
now = int(time.time()) - 60
rows = [{"ts": now, "pid": "deepseek-flash-bg", "who": "lively_bond", "miss": 1_000_000, "hit": 0, "out": 0},       # ¥1 回味
        {"ts": now, "pid": "deepseek-flash-caption", "who": "lively_gate", "miss": 500_000, "hit": 0, "out": 0},  # ¥0.5 看图
        {"ts": now, "pid": "deepseek-flash", "who": "astrbot", "what": "compress", "miss": 0, "hit": 0, "out": 100_000},  # ¥0.4 压缩
        {"ts": now, "pid": "workbuddy-flash", "who": "astrbot", "what": "compress", "miss": 9_000_000, "hit": 0, "out": 0}]  # 降智版：0 元
b.usage_file.write_text("\n".join(json.dumps(r) for r in rows) + "\nbad line\n", "utf-8")
db = TMP / "data_v4.db"
con = sqlite3.connect(db)
con.execute("create table provider_stats (umo text, provider_id text, start_time real, token_input_other int, token_input_cached int, token_output int)")
con.executemany("insert into provider_stats values (?,?,?,?,?,?)", [
    ("napcat:FriendMessage:20001", "deepseek-flash-dm", now, 2_000_000, 0, 0),   # ¥2 私聊
    ("napcat:GroupMessage:30001", "deepseek-flash", now, 300_000, 0, 0),         # ¥0.3 群里（满血版）
    ("napcat:GroupMessage:30001", "workbuddy-flash", now, 5_000_000, 0, 0),       # 降智版：0 元
    ("napcat:GroupMessage:30001", "workbuddy-flash", now, 5_000_000, 0, 0)])
con.commit(); con.close()
bm.STATS_DB = db
day = bm._day(now)
b.summary = lambda days=7: {"days": [{"day": day, "actual": 6.0, "partial": True, "unattributed": 1.8}]}
sp = b.spend(30)
C = {c["id"]: c for c in sp["cats"]}
check("私聊 ¥2", abs(C["private"]["cost"] - 2.0) < 1e-6, C["private"])
check("群里 ¥0.3、3 次", abs(C["group"]["cost"] - 0.3) < 1e-6 and C["group"]["n"] == 3, C["group"])
check("回味、看图、压缩", abs(C["digest"]["cost"] - 1) < 1e-6 and abs(C["look"]["cost"] - .5) < 1e-6 and abs(C["squeeze"]["cost"] - .4) < 1e-6, sp["cats"])
check("降智版不算钱，只记次数", sp["free"] == {"n": 3, "chat": 2}, sp["free"])
check("记到的合计", abs(sp["recorded"] - 4.2) < 1e-6, sp["recorded"])
check("没记到的从每天的账拿", sp["unrecorded"] == 1.8 and sp["daily"][-1]["unrecorded"] == 1.8, sp["daily"])
check("今天没过完不算进实际扣的", sp["actual"] is None and sp["actual_days"] == 0)
check("每天分群里、私聊、后台", sp["daily"][-1]["private"] == 2.0 and sp["daily"][-1]["bg"] == 1.9, sp["daily"][-1])
check("没用过的类不列", "test" not in C and "phone" not in C)
check("显示顺序跟 SPEND_CATS", [c["id"] for c in sp["cats"]] == [k for k, _, _ in bm.SPEND_CATS if k in C])

# ---- 投餵 ----
r1 = b.add_feed("20001", "15", note="token 换大白饭", name="月")
check("记一笔", r1["amount"] == 15 and r1["note"] == "token 换大白饭" and b.feeds()[0]["id"] == r1["id"])
r2 = b.add_feed("20002", 6.666, ts=now - 3 * 86400)
check("金额留两位、日期照填的", r2["amount"] == 6.67 and r2["ts"] == now - 3 * 86400)
check("新的在前", [f["qq"] for f in b.feeds()] == ["20001", "20002"])
for bad, why in ((("abc", 1), "号码"), (("123", 1), "太短的号"), (("20001", 0), "零元"), (("20001", -5), "负数"), (("20001", 1e9), "太多")):
    try:
        b.add_feed(*bad); check(f"挡掉{why}", False)
    except ValueError:
        check(f"挡掉{why}", True)
try:
    b.add_feed("20001", 1, ts=time.time() + 5 * 86400); check("挡掉以后的日期", False)
except ValueError:
    check("挡掉以后的日期", True)
check("删一笔", b.del_feed(r2["id"])["qq"] == "20002" and len(b.feeds()) == 1)
check("删不存在的", b.del_feed("nope") is None)
check("文件坏了当没有", (b.feeds_file.write_text("{坏的", "utf-8"), b.feeds())[1] == [])
b._save_feeds([r1])


# ---- 〈我〉聊天時自己記投喂（工具），主人私信不再有「飯錢 投喂」死指令 ----
class S:
    def get(self, k, d=None): return d
    def is_owner(self, q): return str(q) == "10001"
    def owners(self): return ["10001"]
    def owner(self): return "10001"
    def private_umo(self, q): return f"aiocqhttp:FriendMessage:{q}"
    def owner_call(self): return "爹爹"
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owner_text(self, t): return self.fill(t)
b.s = S()
PEOPLE = [("20001", "泠·月"), ("20002", "群友乙"), ("20003", "月"), ("10001", "陈")]
b.bond_name = lambda qq: dict(PEOPLE).get(str(qq), "")
b.bond_find = lambda name: [r for r in PEOPLE if r[1] == name] or [r for r in PEOPLE if name in r[1]]


class Ev:
    def __init__(self, text="", who="10001", name="陈"): self.message_str, self.who, self.name, self.sent, self.stopped = text, who, name, [], False
    def get_sender_id(self): return self.who
    def get_sender_name(self): return self.name
    def stop_event(self): self.stopped = True
    async def send(self, chain): self.sent.append("".join(chain.chain))


def note(sender="10001", sname="陈", **kw):
    return asyncio.run(b.tool_feed_note(Ev(who=sender, name=sname), **kw))


def drop(sender="10001", **kw):
    return asyncio.run(b.tool_feed_drop(Ev(who=sender), **kw))


b._save_feeds([])
t = note(amount="15元", who="泠·月", when="昨天", note="token 换大白饭")
f = b.feeds()[0]
check("主人说的，按名字找到人", "记下了：泠·月（QQ 20001）" in t and "投喂 ¥15（token 换大白饭），爹爹跟本鱼说的" in t, t)
check("记下是谁说的", f["via"] == "chat" and f["told_by"] == "10001" and f["told_owner"] is True and f["name"] == "泠·月", f)
check("昨天按昨天记", abs(f["ts"] - (time.time() - 86400)) < 60, f)
t = note(amount="15", who="20001", note="薯片")
check("同样金额再说一次也照记，列出之前那笔", t.startswith("记下了") and len(b.feeds()) == 2
      and "饭钱本上 TA 之前还有：" in t and "¥15（token 换大白饭），爹爹跟本鱼说的" in t and "现在 TA 一共 2 笔 ¥30" in t, t)
b.add_feed("20001", 15, via="panel", name="泠·月")
t = drop(who="20001", amount="15")
check("同样金额好几笔，划掉的是自己记的", t.startswith("划掉了") and [x["via"] for x in b.feeds() if x["qq"] == "20001"] == ["panel", "chat"], t)
b._save_feeds([x for x in b.feeds() if x["via"] == "chat"])
check("划完剩一笔", len(b.feeds()) == 1)
t = note(sender="20002", sname="乙", amount="8.8", note="请喝奶茶")
check("TA 自己说的，不写谁就是说话的人", "群友乙（QQ 20002）" in t and "TA 自己跟本鱼说的" in t and b.feeds()[0]["told_owner"] is False, t)
t = note(sender="20003", sname="月", amount="2", who="群友乙")
check("第三个人说的", "月跟本鱼说的" in t and "一共 2 笔 ¥10.8" in t, t)
PEOPLE.append(("20004", "月"))
t = note(amount="3", who="月")
check("名字对得上好几个", "对得上好几个人：月（QQ 20003）、月（QQ 20004）" in t, t)
PEOPLE.pop()
t = note(amount="3", who="小")
check("认识的人里没有", "没有叫「小」的" in t and "QQ 号" in t, t)
check("金额不是数字", "不是数字" in note(amount="很多", who="20001"))
check("零元挡掉", note(amount="0", who="20001").startswith("没记成"))
t = note(amount="5", who="QQ 30001", when="10-26")
check("写 QQ 号、写日子", "（QQ 30001）10月26日投喂 ¥5" in t, t)
t = note(amount="1", who="30001", when="上回")
check("认不出的日子按今天并说出来", "「上回」没认出是哪天，按今天记了" in t, t)
check("几天前", abs(b.feed_day("3天前") - (time.time() - 3 * 86400)) < 5 and b.feed_day("2026年13月1日") is None)
n = len(b.feeds())
check("划掉自己记的", drop(who="30001", amount="1").startswith("划掉了") and len(b.feeds()) == n - 1)
b.add_feed("20001", 50, via="panel", name="泠·月")
t = drop(who="泠·月", amount="50")
check("后台记的划不掉", "在后台记的" in t and "划不掉" in t and len(b.feeds()) == n, t)
check("没有这笔", "没有" in drop(who="20001", amount="99"))
check("feed_from 认得以前私信记的", b.feed_from({"via": "qq"}) == "〈主人〉记的")
e = Ev("饭钱 投喂 20002 5"); asyncio.run(b.owner(e))
check("私信「饭钱 投喂」不再是指令", not e.stopped and not e.sent, e.sent)
b._save_feeds([r1])


# ---- 面板記投餵：日期、名字、錯的值 ----
web = mod("aiohttp.web", middleware=lambda f: f, Request=object, json_response=lambda d, status=200: dict(d, _status=status))
sys.modules["aiohttp"].web = web
pm = importlib.import_module("astrbot_plugin_lively_panel.main")
P = object.__new__(pm.LivelyPanel)
P.s = S()
P._star = lambda name: b if name == "lively_billing" else None
P._people_names = lambda: {"20002": "群友乙"}
act = lambda body: asyncio.run(P.feeds_act({"body": body}))
r = act({"action": "add", "qq": "20002", "amount": "12.5", "date": "", "note": "奶茶"})
check("面板记一笔，名字从情感插件拿", r["ok"] and r["data"]["name"] == "群友乙" and "群友乙 投喂 ¥12.5" in r["msg"], r)
r2 = act({"action": "add", "qq": "20001", "amount": 3, "date": "2026-10-01"})
check("填了以前的日期按那天中午记", r2["ok"] and bm._day(r2["data"]["ts"]) == "2026-10-01", r2)
check("日期写错", act({"action": "add", "qq": "20001", "amount": 3, "date": "10/01"})["ok"] is False)
check("金额写错", act({"action": "add", "qq": "20001", "amount": "abc"})["ok"] is False)
check("号码写错", "QQ 号不对" in act({"action": "add", "qq": "x", "amount": 3})["error"])
d = act({"action": "del", "id": r["data"]["id"]})
check("面板删一笔", d["ok"] and "群友乙" in d["msg"] and all(f["id"] != r["data"]["id"] for f in b.feeds()), d)
check("删没有的", act({"action": "del", "id": "nope"})["ok"] is False)
check("不认得的动作", act({"action": "x"})["ok"] is False)
P._star = lambda name: None
check("饭钱插件没加载", act({"action": "add"})["_status"] == 503)

# ---- 面板飯錢的投喂榜：按累計排，帶筆數、最近一次、檔位（檔位問 bond 的關係讀口） ----
b._save_feeds([])
f1 = b.add_feed("20001", 15, ts=now - 2 * 86400, name="泠·月")
f2 = b.add_feed("20002", 20, ts=now - 86400, name="群友乙")
f3 = b.add_feed("20001", 15, ts=now - 3600, name="泠·月")
user = lambda q: {"qq": q, "name": "", "cost": 0.1, "turns": 3, "called": 1, "private": 1, "hours": [1] * 24, "wdays": [1] * 7,
                  "active_days": 2, "first": now - 5 * 86400, "last": now - 600}
B = types.SimpleNamespace(users=lambda days: {"users": [user("20001"), user("10001")]}, feeds=b.feeds, feed_from=b.feed_from)
P._star = lambda name: B if name == "lively_billing" else None
P._bond_rows = lambda: [{"qq": "20002", "name": "群友乙"}]
P._rel_map = lambda: {"20001": {"fed": {"tier": 3, "tier_name": "一锅饭"}}, "20002": {"fed": {"tier": 2, "tier_name": "一碗饭"}}}
P._with_rel = lambda r, rel: r
async def _gn(): return {}
P._group_names = _gn
u = asyncio.run(P.usage(types.SimpleNamespace(query={"days": "30"})))["data"]
fd = u["feeders"]
check("投喂榜按累计排", [x["qq"] for x in fd] == ["20001", "20002"] and fd[0]["total"] == 30 and fd[0]["n"] == 2, fd)
check("最近一次是最新那笔", fd[0]["last"] == f3["ts"] and fd[1]["last"] == f2["ts"], fd)
check("带档位", (fd[0]["tier"], fd[0]["tier_name"], fd[1]["tier"]) == (3, "一锅饭", 2), fd)
check("名字从情感插件拿", fd[1]["name"] == "群友乙", fd)
check("画像不再有打分", all("score" not in x for x in u["users"]), u["users"])
P._rel_map = lambda: {}
check("问不到 bond 就不带档位", "tier" not in asyncio.run(P.usage(types.SimpleNamespace(query={})))["data"]["feeders"][0])
b._save_feeds([r1])
P._star = lambda name: None

# ---- 面板回成長提案：順手寫的做法跟在指令後面；學會了的不能再改 ----
class Evolve:
    def __init__(self):
        self.cmds = []
        self.state = {"proposals": [{"n": 1, "title": "记忆自查", "status": "pending"}, {"n": 2, "title": "群聊回看", "status": "ok"},
                                    {"n": 3, "title": "学会了的", "status": "done"}]}
    async def _owner_cmd(self, cmd):
        self.cmds.append(cmd)
        return "耶！【1】记忆自查，需求书在上面那条\n第二行"
ev = Evolve()
P._star = lambda name: ev if name == "lively_evolve" else None
eact = lambda body: asyncio.run(P.evolve_act({"body": body}))
r = eact({"action": "proposal", "n": "1", "ok": True, "note": "  只在〈主人〉私聊里翻\n按人按群列  "})
check("说好时带做法", r["ok"] and ev.cmds[-1] == "提案 1 好 只在〈主人〉私聊里翻 按人按群列" and r["msg"] == "记下了：【1】爹爹定的做法", (r, ev.cmds))
r = eact({"action": "proposal", "n": "1", "ok": False, "note": "太费钱"})
check("说不要时带为什么", r["ok"] and ev.cmds[-1] == "提案 1 不要 太费钱" and "为什么不要" in r["msg"], (r, ev.cmds))
r = eact({"action": "proposal", "n": 2, "ok": True})
check("不写做法照旧", r["ok"] and ev.cmds[-1] == "提案 2 好" and r["msg"].startswith("耶！") and "第二行" not in r["msg"], r)
check("做法最多 300 字", eact({"action": "proposal", "n": "2", "ok": True, "note": "做" * 400})["ok"] and len(ev.cmds[-1]) == len("提案 2 好 ") + 300)
n = len(ev.cmds)
check("学会了的不能再改", eact({"action": "proposal", "n": "3", "ok": True, "note": "改"})["ok"] is False and len(ev.cmds) == n)
check("没有这个提案", "没有这个提案" in eact({"action": "proposal", "n": "9", "ok": True})["error"])
check("n 不是数字", eact({"action": "proposal", "n": "x", "ok": True})["ok"] is False and len(ev.cmds) == n)

print("all ok" if not fails else f"{len(fails)} 项没过：{fails}")
sys.exit(1 if fails else 0)
