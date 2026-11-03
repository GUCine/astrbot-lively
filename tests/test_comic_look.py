"""群漫畫她看過再發（10-26）：每天那張畫好先給〈我〉看，配什麼話她定；沒看成就照以前直接發；重啟前畫好沒發的不重畫。
10-26 晚：私信主人的話都是她寫的（不再有插件的固定句）；各群同時畫、提前開始、到點發；取不到話題再試；
到點一定發（不再有「看過不發」），她看了想改的見 test_comic_fix.py。

/usr/local/bin/python3 tests/test_comic_look.py（號碼都是假的：10001 主人、20001 群、99999 機器人）
"""
import asyncio, importlib, json, sys, tempfile, time, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco, command=deco, on_agent_done=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
TMP = Path(tempfile.mkdtemp())
class Plain: pass
class Chain:
    def __init__(self): self.chain = []
    def message(self, t): self.chain.append(("text", t)); return self
    def file_image(self, p): self.chain.append(("img", p)); return self
    def url_image(self, u): self.chain.append(("url", u)); return self
class TP:
    def __init__(self, text): self.text = text
    def mark_as_temp(self): return self
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Plain=Plain)
class Star:
    def __init__(self, context=None): self.context = context
class StarTools:
    @staticmethod
    def get_data_dir(name): p = TMP / name; p.mkdir(parents=True, exist_ok=True); return p
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=StarTools)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("astrbot.core.agent"); mod("astrbot.core.agent.message", TextPart=TP)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=Chain)
mod("aiohttp")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
cm = importlib.import_module("astrbot_plugin_lively_comic.main")
cm.SEND_GAP = 0  # 各群排隊發的間隔，測試裡不等
lc = importlib.import_module("astrbot_plugin_lively_comic.lively_common")
lc.OUTBOX = TMP / "outbox.jsonl"
G, OWNER = "20001", "10001"


class Prov:
    replies: list = []
    seen: list = []
    async def text_chat(self, prompt, system_prompt, image_urls=None):
        Prov.seen.append({"prompt": prompt, "system": system_prompt, "images": image_urls})
        r = Prov.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(completion_text=r)


class S:
    conf: dict = {}
    def get(self, k, d=None): return S.conf.get(k, d)
    def fill(self, t): return str(t).replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def owner_text(self, t): return self.fill(t)
    def is_owner(self, qq): return str(qq) == OWNER
    def owner(self): return OWNER
    def private_umo(self, qq): return f"x:FriendMessage:{qq}"
    def group_umo(self, gid): return f"x:GroupMessage:{gid}"
    def persona_prompt(self): return "（人设）"
    def provider(self, key="provider_id"): S.used = key; return Prov()
    def platform_id(self): return "x"


SENT = []
async def send_message(umo, chain): SENT.append((umo, chain.chain))
def new():
    c = cm.LivelyComic.__new__(cm.LivelyComic)
    c.s, c.comic_at, c._names, c._sb = S(), "00:00", {G: "测试群", "20002": "第二群"}, {}
    c.dir = TMP / "comic"; c.dir.mkdir(exist_ok=True)
    c.state_file, c.events_file = c.dir / "state.json", c.dir / "events.jsonl"
    c.state = {"pending": {}, "inflight": {}, "enabled": True}
    c._gallery = cm.Gallery(Path(tempfile.mkdtemp()), None, lambda g: c._names.get(g, g))  # 每个测试各一本图册
    c._locks, c._gen_sem, c._draw_secs = {}, None, {}
    c._redo, c._bg = {}, set()
    c._busy = cm._AnyLocked(c._locks)
    gda = types.SimpleNamespace(comic_command_handler=types.SimpleNamespace(
        config_manager=types.SimpleNamespace(get_enable_daily_comic=lambda: True)))
    c.context = types.SimpleNamespace(send_message=send_message, conversation_manager=None,
                                      get_registered_star=lambda n: types.SimpleNamespace(star_cls=gda))
    return c
def outbox():
    return [json.loads(x) for x in lc.OUTBOX.read_text("utf-8").splitlines()] if lc.OUTBOX.exists() else []
def sent_ev(c):  # 最後一條 sent（它後面還有一條 wrap_say）
    return [e for e in events(c) if e["kind"] == "sent"][-1]
def events(c):
    return [json.loads(x) for x in c.events_file.read_text("utf-8").splitlines()] if c.events_file.exists() else []
IMG = TMP / "comic_20001.png"
from PIL import Image  # noqa: E402
Image.new("RGB", (100, 150), (200, 220, 255)).save(IMG)
TOPICS = [{"topic": "抢饭", "detail": "小凛和本鱼抢饭", "contributors": ["小凛🍥", "陈"]}]
SB = {"panels": [{"scene": "x", "who": ["小凛"], "me": True, "lines": [{"who": "本鱼", "say": "这碗是本鱼的"}], "caption": "抢饭大战"}]}

# ---- 看過、發：圖連同那句話一條發進群 ----
c = new(); c._sb[G] = (SB, [{"call": "小凛", "name": "小凛🍥", "qq": "2"}])
S.conf = {"storyboard_provider_id": "bg"}
Prov.replies = ['{"看到的": "一格，抢饭", "post": true, "text": "今天的群漫画～", "私信爹爹": "爹爹，今天的群漫画发啦", "why": "画得挺好"}']
assert asyncio.run(c._publish(G, "今天", str(IMG), TOPICS)) == "已自动发群"
gs = [s for s in SENT if s[0].endswith(G)]
assert [g[1] for g in gs[-2:]] == [[("img", str(IMG))], [("text", "今天的群漫画～")]], gs  # 10-31 起图先发，话在图发完之后另外发（_wrap_say，这里没第二个回复，退回看图时的草稿）
seen = Prov.seen[-2]  # 最後一個是图发完后写话那次(没回复，退回草稿)
assert S.used == "storyboard_provider_id" and seen["images"] and seen["images"][0].endswith("comic_look_20001_1.jpg")
assert "测试群" in seen["system"] and "（人设）" in seen["system"] and "第 1 格「抢饭大战」" in seen["prompt"] and "抢饭（小凛🍥、陈 在聊）：小凛和本鱼抢饭" in seen["prompt"]
assert "小凛（群名片 小凛🍥）" in seen["prompt"]
assert any(d["umo"].endswith(G) and "配的话是「今天的群漫画～」" in d["text"] for d in outbox())
assert not [s for s in SENT if s[0].endswith(OWNER)]  # 10-29 起直接发群，不私信主人（她写了也不发）
assert "私信爹爹" not in seen["system"] and "图发完之后，话另外再发" in seen["system"] and "改没改过" in seen["system"]
assert sent_ev(c)["looked"] is True and "to_owner" not in sent_ev(c)
# 發了、沒寫給主人的話：不私信
SENT.clear()
c = new()
Prov.replies = ['{"看到的": "一格", "post": true, "text": "", "私信爹爹": "", "why": "好"}']
assert asyncio.run(c._publish(G, "今天", str(IMG), TOPICS)) == "已自动发群"
assert not [s for s in SENT if s[0].endswith(OWNER)] and [s for s in SENT if s[0].endswith(G)]

# ---- 她覺得有錯、改不了（過了點）：照樣發，那句話裡可以順手更正（10-26 晚起不再有「看過不發」）----
SENT.clear()
c = new()
Prov.replies = ['{"看到的": "第四格台词安到白岩头上了", "怎么改": "修图", "改什么": "第四格", "text": "第四格那句是西瓜头说的哈", "私信爹爹": "", "why": "台词落错人"}']
assert asyncio.run(c._publish(G, "今天", str(IMG), TOPICS)) == "已自动发群"
assert [s[1] for s in SENT if s[0].endswith(G)][-2:] == [[("img", str(IMG))], [("text", "第四格那句是西瓜头说的哈")]]
assert not c.state["pending"] and not [s for s in SENT if s[0].endswith(OWNER)]
assert "已经过了 00:00，这张不改了" in Prov.seen[-2]["system"]  # 過了點：照實告訴她不改了
assert "到 00:00 会发出去" in Prov.seen[-2]["system"] and "post" not in Prov.seen[-2]["system"]
ev = sent_ev(c)
assert ev["kind"] == "sent" and "fixes" not in ev  # 沒給改的機會，她寫了「怎么改」也不算
assert [e for e in events(c) if e["kind"] == "fix"] == []

# ---- 刚画的图：10-28 起谁那边都有，转不转她定；群分析插件自己的工具照旧拿掉 ----
class Ev:
    def __init__(self, qq, gid=""): self.qq, self.gid, self.message_str = qq, gid, ""
    def get_sender_id(self): return self.qq
    def get_group_id(self): return self.gid
class Tools:
    def __init__(self): self.t = {"lively_comic_post", "lively_draw", "group_daily_analysis_trigger"}
    def get_tool(self, k): return k in self.t
    def remove_tool(self, k): self.t.discard(k)
c._draw_denied = lambda qq: ""
req = types.SimpleNamespace(func_tool=Tools(), extra_user_content_parts=[])
asyncio.run(c.hide_tools(Ev("30001", G), req))
assert "lively_comic_post" in req.func_tool.t and "group_daily_analysis_trigger" not in req.func_tool.t
req = types.SimpleNamespace(func_tool=Tools(), extra_user_content_parts=[])
asyncio.run(c.hide_tools(Ev(OWNER, "20009"), req))
assert "lively_comic_post" in req.func_tool.t
c._refresh_names = lambda: asyncio.sleep(0)
c._served = lambda: [G]
r = asyncio.run(c.post_tool(Ev("30001", G), image="", group=G, text="x"))
assert r.startswith("没发：没写发哪张"), r                          # 11-02 起发图一定写图册编号

# 主人私聊拍的照片：按编号发到群，群號、群名裡的字都認（10-27 她寫「桐群」，以前回「不在群 桐群 服务」）
OWN_UMO = f"x:FriendMessage:{OWNER}"
c = new(); c._refresh_names = lambda: asyncio.sleep(0); c._note = lambda t: asyncio.sleep(0)
c._served = lambda: [G, "20002"]; c._groups = lambda: [G, "20002"]
pid = c.gallery.add(str(IMG), "拍照", where=OWN_UMO, chat="〈主人〉私聊", purpose="说说配图", prompt="a candid selfie", shot="自拍")
r = asyncio.run(c.post_tool(Ev(OWNER), image=f"#{pid}", group="测试", text="补一张"))
assert f"发了 #{pid} 到「测试群」" in r and "拍照·自拍" in r and "用途「说说配图」" in r and "之前没发过" in r and "拍的是：a candid selfie" in r, r
assert [s for s in SENT if s[0].endswith(G)][-1][1] == [("text", "补一张"), ("img", str(IMG))]
assert asyncio.run(c.post_tool(Ev(OWNER), image=str(pid), group="群", text="")).startswith("名字里带「群」的群有好几个：测试群（20001）")
assert asyncio.run(c.post_tool(Ev(OWNER), image=f"图{pid}", group="桐", text="")).startswith("没有名字里带「桐」的群；本鱼服务的群：测试群（20001）、第二群（20002）")
assert asyncio.run(c.post_tool(Ev(OWNER), image=str(pid), group="20009", text="")) == "群 20009 不在本鱼服务的群里"
r = asyncio.run(c.post_tool(Ev(OWNER), image=str(pid), group="20002", text=""))
assert f"发了 #{pid} 到「第二群」" in r and "之前发过：「测试群」" in r, r       # 发过哪里照实说
assert asyncio.run(c.post_tool(Ev(OWNER), image=str(pid), group="", text="")).startswith(f"#{pid} 要发到哪个群")   # 开着两个群没写

# 主人私聊裡發等著的群漫畫整頁：只能發回它自己的群
c = new(); c._refresh_names = lambda: asyncio.sleep(0); c._note = lambda t: asyncio.sleep(0)
c._served = lambda: [G, "20002"]; c._groups = lambda: [G, "20002"]
s1 = c.gallery.add(str(IMG), "群漫画单张", group=G, day="2026-11-01", k=1, n=1, title="抢饭")
page = c.gallery.add(str(IMG), "群漫画整页", group=G, day="2026-11-01", n=1, parent=[s1], status="没发成", failed="QQ 超时")
c.state["pending"][G] = {"path": str(IMG), "ts": 9e12, "label": "今天", "day": "2026-11-01"}
r = asyncio.run(c.post_tool(Ev(OWNER), image=str(s1)))
assert f"#{s1} 是群漫画里的一张" in r and f"这一组的整页是 #{page}" in r, r          # 单张不单发，指去整页
assert "只能发回它自己的群" in asyncio.run(c.post_tool(Ev(OWNER), image=str(page), group="20002"))   # 不跨群
assert "只能发回它自己的群" in asyncio.run(c.post_tool(Ev(OWNER), image=str(page), group="全部"))
r = asyncio.run(c.post_tool(Ev(OWNER), image=str(page)))
assert f"发了 #{page} 到「测试群」" in r and "群漫画整页" in r and not c.state["pending"], r
assert c.gallery.get(page)["status"] == "已发" and c.gallery.get(s1)["status"] == "已发"

# ---- 回答少了最後的 }、第一次看不懂再問一次 ----
c = new()
Prov.replies = ['嗯……', '{"看到的": "四格", "text": "来啦", "why": "好"']
assert asyncio.run(c._look(G, "今天", str(IMG), TOPICS)) == {"text": "来啦", "why": "好", "saw": "四格", "fix": None, "take": True}
# 沒告訴她能改：她寫了要改也不算
Prov.replies = ['{"怎么改": "修图", "改什么": "第一格", "why": "x"}']
assert asyncio.run(c._look(G, "今天", str(IMG), None))["fix"] is None
assert "（这张是重启前画好的" in Prov.seen[-1]["prompt"]
Prov.replies = ['{"怎么改": "重画", "改什么": "第二格换成抢饭", "why": "x"}']
assert asyncio.run(c._look(G, "今天", str(IMG), None, fix_note="可以改", can_fix=True))["fix"] == ("重画", "第二格换成抢饭")
Prov.replies = ['{"怎么改": "不改", "改什么": "第二格", "why": "x"}']
assert asyncio.run(c._look(G, "今天", str(IMG), None, fix_note="可以改", can_fix=True))["fix"] is None
Prov.replies = ['{"怎么改": "修图", "改什么": "第二格", "why": "x"}']
assert asyncio.run(c._look(G, "今天", str(IMG), None, fix_note="来不及改了"))["fix"] is None  # 告訴過她改不了
# 看改過的那張：問她用哪張
fixed = {"n": 1, "how": "修图", "change": "第四格名字牌改成西瓜头"}
Prov.replies = ['{"用哪张": "原来的", "why": "改坏了"}']
r = asyncio.run(c._look(G, "今天", str(IMG), None, "可以改", True, fixed=fixed))
assert r["take"] is False and "用哪张" in Prov.seen[-1]["system"] and "这是改过的一版（今天第 1 次改）" in Prov.seen[-1]["prompt"]
Prov.replies = ['{"用哪张": "改过的", "why": "好了"}']
assert asyncio.run(c._look(G, "今天", str(IMG), None, fixed=fixed))["take"] is True
Prov.replies = ['{"看到的": "x"}']
asyncio.run(c._look(G, "今天", str(IMG), None))
assert "用哪张" not in Prov.seen[-1]["system"]  # 第一次看不問

# ---- 沒看成：照以前直接發，告訴主人 ----
SENT.clear()
c = new()
Prov.replies = [RuntimeError("模型挂了")]
assert asyncio.run(c._publish(G, "今天", str(IMG), TOPICS)) == "已自动发群"
assert [s for s in SENT if s[0].endswith(G)][-1][1] == [("img", str(IMG))]
assert not [s for s in SENT if s[0].endswith(OWNER)]  # 沒看成就不私信（不替她寫句子）
assert [e["kind"] for e in events(c)][-3:] == ["look_fail", "sent", "wrap_say"]

# ---- comic_look 關：不看，直接發 ----
SENT.clear(); n = len(Prov.seen)
S.conf = {"comic_look": False}
c = new()
assert asyncio.run(c._publish(G, "今天", "http://x/y.png", TOPICS)) == "已自动发群"
assert len(Prov.seen) == n + 1 and [s for s in SENT if s[0].endswith(G)][-1][1] == [("url", "http://x/y.png")]
assert "画完直接发群" in c._how_post()
S.conf = {}
assert "先给她看，哪格不对她可以改（每张最多 2 次，赶得上就换），到 00:00 照发" in c._how_post(), c._how_post()
S.conf = {"comic_fix_max": 0}; assert "可以改" not in c._how_post()
S.conf = {}

# ---- 重啟前畫好、還沒發的：不重畫，拿那張接著看 ----
SENT.clear()
c = new()
c._topics = lambda *a: (_ for _ in ()).throw(AssertionError("不該重畫"))
Prov.replies = ['{"post": true, "text": "", "why": "好"}']
assert asyncio.run(c.draw(G, 0, True, done_path=str(IMG))) == "已自动发群"
assert c.state["inflight"] == {} and [s for s in SENT if s[0].endswith(G)]

# ---- 群漫畫那邊出的事：把事實交給她，說不說、怎麼說她定 ----
SENT.clear(); c = new(); notes = []
async def _note(t): notes.append(t)
c._note = _note
Prov.replies = ['{"say": "爹爹，测试群今天的群漫画没画成，群分析那边没给话题"}']
asyncio.run(c._report("今天「测试群」的群漫画没画成：群分析插件取了 3 次都没给出话题"))
assert [s[1] for s in SENT if s[0].endswith(OWNER)] == [[("text", "爹爹，测试群今天的群漫画没画成，群分析那边没给话题")]]
assert "测试群" in Prov.seen[-1]["prompt"] and "要不要私信爹爹说一声" in Prov.seen[-1]["system"] and not notes
SENT.clear()
Prov.replies = ['{"say": ""}']
asyncio.run(c._report("今天「测试群」群里没什么消息"))
assert not SENT and "没私信〈主人〉" in notes[-1]
Prov.replies = [RuntimeError("挂了")]
asyncio.run(c._report("x"))
assert not SENT and events(c)[-1]["kind"] == "report"

# ---- 取不到話題：隔一會兒再試，最多 comic_topic_tries 次；群裡沒消息不再試 ----
cm.TOPIC_RETRY_GAP = 0
c = new(); calls = []
async def topics_none(h, gid, off):
    calls.append(gid); return {"success": False, "reason": "no_topics"}
c._topics = topics_none
r = asyncio.run(c._generate(None, G, 0, True, False, "今天", "u"))
assert r == "今天「测试群」的群漫画没画成：群分析插件取了 3 次都没给出话题" and len(calls) == 3, (r, calls)
calls.clear()
async def topics_err_then_empty(h, gid, off):
    calls.append(gid)
    if len(calls) == 1:
        raise RuntimeError("超时")
    return {"success": False, "reason": "no_messages"}
c._topics = topics_err_then_empty
assert asyncio.run(c._generate(None, G, 0, True, False, "今天", "u")).endswith("今天群里没什么消息") and len(calls) == 2

# ---- 各群同時畫：不同群一起跑，同一個群不畫兩張 ----
c = new(); spans = {}
async def gen(handler, gid, offset, auto, test, label, umo):
    spans[gid] = [time.time()]; await asyncio.sleep(0.2); spans[gid].append(time.time()); return "已自动发群"
c._generate = gen
async def two():
    return await asyncio.gather(c.draw(G, 0, True), c.draw("20002", 0, True), c.draw(G, 0, True))
r = asyncio.run(two())
assert r[0] == r[1] == "已自动发群" and r[2] == "「测试群」的群漫画正在画着", r
assert spans["20002"][0] < spans[G][1] and spans[G][0] < spans["20002"][1]  # 兩個群的時間重疊
assert c.state["inflight"] == {}
spans.clear()
async def one_by_one():
    c._gen_sem = asyncio.Semaphore(1)
    await asyncio.gather(c.draw(G, 0, True), c.draw("20002", 0, True))
asyncio.run(one_by_one())
a, b = sorted(spans.values())
assert a[1] <= b[0]  # comic_parallel=1：一個一個來

# ---- 幾點開始：發的時間往前 comic_prep_min 分鐘（預設 30）----
c = new(); c.comic_at = "22:00"
assert c._start_at() == "21:30"  # 三段：21:30 取話題、拿到就畫、看了要改就改，22:00 發
S.conf = {"comic_prep_min": 0}; assert c._start_at() == "22:00"
S.conf = {}; c.comic_at = "00:05"; assert c._start_at() == "00:00"
c.comic_at = "00:00"; asyncio.run(asyncio.wait_for(c._wait_post(), 1))  # 已經過了就不等

# ---- 以前存的 inflight 是一張圖本身：讀進來換成按群放 ----
c = new()
c.state_file.write_text(json.dumps({"inflight": {"gid": G, "ts": 1, "auto": True}}), "utf-8")
assert c._load()["inflight"] == {G: {"gid": G, "ts": 1, "auto": True}}
print("comic look ok")
