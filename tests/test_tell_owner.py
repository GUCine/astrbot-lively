"""後台的事交給她說（10-26 晚）：lively_common.her_words／tell_owner，指令回覆的 admin_text，日報寫不出來時的【后台】數字。
stub 掉 astrbot，號碼都是假的：10001 主人。

/usr/local/bin/python3 tests/test_tell_owner.py
"""
import asyncio, importlib.util, json, sys, tempfile, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __init__(self): self.lines = []
    def __getattr__(self, k): return lambda *a, **k2: self.lines.append((k, a[0] if a else ""))
LOG = L()
TMP = Path(tempfile.mkdtemp())
mod("astrbot"); mod("astrbot.api", logger=LOG)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
class MessageChain:
    def __init__(self): self.parts = []
    def message(self, t): self.parts.append(("text", t)); return self
    def file_image(self, p): self.parts.append(("image", p)); return self
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=MessageChain)
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("lively_common", ROOT / "common" / "lively_common.py")
lc = importlib.util.module_from_spec(spec); sys.modules["lively_common"] = lc; spec.loader.exec_module(lc)
fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, "" if ok else extra)
    if not ok:
        fails.append(name)


class Prov:
    def __init__(self, out=None, err=None): self.out, self.err, self.calls = out, err, []
    async def text_chat(self, prompt, system_prompt):
        self.calls.append((prompt, system_prompt))
        if self.err:
            raise self.err
        return types.SimpleNamespace(completion_text=self.out)


class Ctx:
    def __init__(self): self.sent, self.provs, self.fail = [], {}, False
    def get_provider_by_id(self, pid): return self.provs.get(pid)
    def get_using_provider(self): return None
    async def send_message(self, umo, chain):
        if self.fail:
            raise RuntimeError("napcat 超时")
        self.sent.append((umo, chain.parts))


def settings(prov, words_pid=""):
    s = lc.Settings(Ctx(), {"owner_qq": "10001", "words_provider_id": words_pid, "platform_id": "x",
                            "self_call": "本鱼", "owner_call": "爹爹"})
    s.provider = lambda key="provider_id": prov
    s.persona_prompt = lambda: "你是小肥鱼，自称本鱼，叫主人爹爹。"
    return s


def outbox():
    try:
        return [json.loads(x) for x in lc.OUTBOX.read_text("utf-8").splitlines()]
    except FileNotFoundError:
        return []


OWNER_DM = "x:FriendMessage:10001"

# ---- 一定要說的（must）：她的話＋【后台】卡片 ----
p = Prov('{"say": "爹爹，有人想加本鱼好友，名字叫花生，你看看要不要"}')
s = settings(p)
said = asyncio.run(lc.tell_owner(s, "有人想加〈我〉好友\n名字：花生", "有人想加好友", must=True,
                                 card="好友申请 · 等你定\n花生（QQ 20001）", kind="好友申请"))
sent = s.context.sent
check("回她说的话", said == "爹爹，有人想加本鱼好友，名字叫花生，你看看要不要", said)
check("先发她的话、再发卡片", [x[0] for x in sent] == [OWNER_DM, OWNER_DM] and sent[0][1] == [("text", said)]
      and sent[1][1] == [("text", "【后台】好友申请 · 等你定\n花生（QQ 20001）")], sent)
prompt, system = p.calls[0]
check("事实交给她（换了占位符）", prompt == "有人想加本鱼好友\n名字：花生", prompt)
check("系统提示词是人设＋规则", system.startswith("你是小肥鱼") and "[后台的事：有人想加好友]" in system
      and "【后台】卡片" in system and "不说就空字符串" not in system, system)
ob = outbox()
check("两条都记进主人私聊", [(d["umo"], d["kind"]) for d in ob[-2:]] == [(OWNER_DM, "好友申请")] * 2 and ob[-1]["text"].startswith("【后台】"), ob[-2:])

# 她沒寫出來（模型出錯、看不懂、帶了號碼）：只發卡片
for name, prov in (("模型出错", Prov(err=RuntimeError("超时"))), ("看不懂", Prov("我想想……")),
                   ("带了号码", Prov('{"say": "爹爹，QQ 20001 想加本鱼"}'))):
    s = settings(prov)
    said = asyncio.run(lc.tell_owner(s, "有人想加〈我〉好友", "有人想加好友", must=True, card="好友申请 · 等你定"))
    check(f"{name}：只发卡片", said == "" and s.context.sent == [(OWNER_DM, [("text", "【后台】好友申请 · 等你定")])], s.context.sent)
# 沒給卡片：事實當卡片
s = settings(Prov(err=RuntimeError("超时")))
asyncio.run(lc.tell_owner(s, "被〈主人〉的群踢了", "被踢", must=True))
check("没给卡片就把事实当卡片", s.context.sent == [(OWNER_DM, [("text", "【后台】被爹爹的群踢了")])], s.context.sent)
# 圖跟第一張卡片；好幾張卡片
s = settings(Prov('{"say": "爹爹看看这条说说"}'))
asyncio.run(lc.tell_owner(s, "说说草稿", "说说草稿", must=True, card=["说说草稿 · 等你定", "第二张"], image="/tmp/a.png"))
check("图跟第一张卡片、好几张依次发", [x[1] for x in s.context.sent] == [
    [("text", "爹爹看看这条说说")], [("text", "【后台】说说草稿 · 等你定"), ("image", "/tmp/a.png")], [("text", "【后台】第二张")]],
    s.context.sent)
# 發送出錯不拋
s = settings(Prov('{"say": "爹爹"}')); s.context.fail = True
check("发不出去不抛", asyncio.run(lc.tell_owner(s, "x", "x", must=True, card="c")) == "爹爹")

# ---- 說不說她定（不是 must） ----
p = Prov('{"say": ""}')
s = settings(p)
said = asyncio.run(lc.tell_owner(s, "〈我〉在群「浅梦」被禁言了 10 分钟", "被禁言", kind="被禁言"))
check("她不说就什么都不发", said == "" and s.context.sent == [], s.context.sent)
d = outbox()[-1]
check("只记一笔后台的事让她知道", d["umo"] == OWNER_DM and d["kind"] == "后台:被禁言"
      and d["text"] == "本鱼在群「浅梦」被禁言了 10 分钟（本鱼没私信爹爹）", d)
check("规则写明可以不说", "不说就空字符串" in p.calls[0][1] and "不想说就空着" in p.calls[0][1], p.calls[0][1])
s = settings(Prov('{"say": "爹爹，本鱼在浅梦被禁言了，闷"'))  # 少了最後的 }
said = asyncio.run(lc.tell_owner(s, "被禁言了", "被禁言"))
check("她说了就只发她的话（少了 } 也认）", said == "爹爹，本鱼在浅梦被禁言了，闷" and s.context.sent == [(OWNER_DM, [("text", said)])], s.context.sent)

# ---- 她的話洗一遍：表情包標籤、好感標記拿掉；起草稿挑終稿 ----
check("去掉表情包标签和好感标记", lc._words_out('{"say": "爹爹～&&happy&&\\n<<好感+1|开心>>"}') == "爹爹～")
check("起草稿挑终稿", lc._words_out('{"say": "情景：被禁言了\\n语气：委屈\\n写：爹爹本鱼被关小黑屋了"}') == "爹爹本鱼被关小黑屋了")

# ---- 用哪個模型：門禁插件的 words_provider_id，找不到用插件自己的 ----
own, words = Prov('{"say": "a"}'), Prov('{"say": "b"}')
s = settings(own, words_pid="deepseek-flash-bg"); s.context.provs["deepseek-flash-bg"] = words
check("用 words_provider_id", asyncio.run(lc.her_words(s, "x", "x")) == "b" and not own.calls)
s = settings(own, words_pid="不存在")
check("找不到就用插件自己的", asyncio.run(lc.her_words(s, "x", "x")) == "a")

# ---- 指令回覆：【后台】白話，〈我〉寫成她、〈主人〉寫成你 ----
s = settings(Prov())
check("admin_text", s.admin_text("〈我〉的记忆分层开了，好了告诉〈主人〉") == "【后台】她的记忆分层开了，好了告诉你",
      s.admin_text("〈我〉的记忆分层开了，好了告诉〈主人〉"))
check("已经带了【后台】不重复加", s.admin_text("【后台】x") == "【后台】x")
check("backstage", lc.backstage(" 饭钱快没了") == "【后台】饭钱快没了")

# ---- 日報：她寫不出來時的數字是【后台】白話，自稱檢查那行也是 ----
sys.path.insert(0, str(ROOT))
mod("astrbot.api", logger=LOG, AstrBotConfig=dict)
def deco(*a, **k): return lambda f: f
mod("astrbot.api.event", AstrMessageEvent=object,
    filter=types.SimpleNamespace(event_message_type=deco, EventMessageType=types.SimpleNamespace(PRIVATE_MESSAGE=1)))
mod("astrbot.api.star", Context=object, Star=object, register=deco, StarTools=object)
rep = importlib.import_module("astrbot_plugin_lively_report.main")
plain = rep.LivelyReport.plain({"日期": "2026-10-26", "各群": {"小凛群": {"群消息": 300, "〈我〉回复": 12}}})
check("日报数字版是后台白话", plain.startswith("【后台】今天（2026-10-26）的日报，她这会儿没写出来") and "她回了 12 次" in plain
      and "〈我〉" not in plain and "～" not in plain, plain)
check("自称检查那行标后台", rep.LivelyReport.drift_line(["开摆（5/6 句）"]).startswith("\n【后台】自称检查：")
      and "她提到自己" in rep.LivelyReport.drift_line(["开摆（5/6 句）"]))

print("all ok" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
