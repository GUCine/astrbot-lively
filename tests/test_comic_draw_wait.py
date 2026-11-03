"""畫圖工具先等結果再回她（10-26）：畫好／沒畫成都回給她；等不到轉背景，之後的結果記進待讀消息；沒畫成不替她發話。

/usr/local/bin/python3 tests/test_comic_draw_wait.py（號碼是假的：10001 主人）
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
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Plain=object)
class Star:
    def __init__(self, context=None): self.context = context
class StarTools:
    @staticmethod
    def get_data_dir(name): p = TMP / name; p.mkdir(parents=True, exist_ok=True); return p
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=StarTools)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
mod("astrbot.core.agent"); mod("astrbot.core.agent.message", TextPart=object)
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=object)
mod("aiohttp")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
cm = importlib.import_module("astrbot_plugin_lively_comic.main")


class Chain:
    def __init__(self): self.parts = []
    def file_image(self, p): self.parts.append(("image", p)); return self
    def message(self, t): self.parts.append(("text", t)); return self
cm.MessageChain = Chain
notes = []
cm.note_outbox = lambda umo, text, kind="": notes.append((umo, text, kind))


class S:
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def is_owner(self, qq): return str(qq) == "10001"
    def owner_text(self, t): return self.fill(t)
    def get(self, k, d=None): return d
    def private_umo(self, qq): return f"x:FriendMessage:{qq}"


class Ev:
    def __init__(self, qq="10001", gid="", msg="画一张"):
        self.qq, self.gid, self.message_str = qq, gid, msg
        self.unified_msg_origin = f"x:GroupMessage:{gid}" if gid else f"x:FriendMessage:{qq}"
    def get_sender_id(self): return self.qq
    def get_group_id(self): return self.gid
    def get_sender_name(self): return {"20001": "阿月", "20002": "路人"}.get(self.qq, self.qq)


SCORES = {"20001": 80.0, "20002": 50.0}
class Bond:
    def relation(self, qq): return {"score": SCORES.get(qq, 0.0)}
def get_star(name): return types.SimpleNamespace(star_cls=Bond()) if name == "astrbot_plugin_lively_bond" else None


ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))


async def run():
    cls = next(v for v in vars(cm).values() if isinstance(v, type) and hasattr(v, "draw_tool"))
    sent = []
    async def send_message(umo, chain): sent.append((umo, chain.parts))
    def plug(draw):
        p = object.__new__(cls)
        p.s, p.draw_max, p.dir = S(), 20, TMP
        p.self_look, p.self_ref = "", None
        p.state = {"draw_day": "", "draw_count": 0, "draw_jobs": []}
        p._waiting = set(); p._seen = {}; p._names = {}
        p.context = types.SimpleNamespace(send_message=send_message, get_registered_star=get_star)
        p._save = lambda: None
        p._log = lambda *a, **k: None
        p._owner_umo = lambda: "x:FriendMessage:10001"
        p._drawing_providers = lambda: [{"model": "m1"}, {"model": "m2"}]
        p._call_images = draw
        p.phone = cm.Phone(p)
        return p

    async def good(prov, prompt, ref, size=""): return b"png"
    r = await plug(good).draw_tool(Ev(), "a cat")
    check("画好才回她", r.startswith("画好了"), r)
    check("图发到当前聊天", sent and sent[-1][1][0][0] == "image", sent[-1:])
    check("没记待读消息（她这轮就知道了）", not notes, notes)

    async def refused(prov, prompt, ref, size=""):
        raise RuntimeError("流式返回错误: {'message': 'Your request was rejected by the safety system'}")
    n = len(sent)
    r = await plug(refused).draw_tool(Ev(), "nsfw")
    check("被审核拒：原因回给她", r.startswith("没画成") and "审核" in r, r)
    check("没画成不往聊天里替她发话", len(sent) == n, sent[n:])

    async def slow(prov, prompt, ref, size=""):
        await asyncio.sleep(0.3); return b"png"
    cm.TOOL_WAIT = 0.05
    p = plug(slow)
    r = await p.draw_tool(Ev(), "a slow cat")
    check("等不到先说还在画", r.startswith("还在画"), r)
    await asyncio.sleep(0.5)
    check("后来画好了照样发图", sent[-1][1][0][0] == "image")
    check("后来画好的记进待读消息", notes and "画好，发到这里了" in notes[-1][1] and notes[-1][2] == "画图", notes)
    check("job 清掉了", not p.state["draw_jobs"] and not p._waiting)

    async def slow_bad(prov, prompt, ref, size=""):
        await asyncio.sleep(0.2); raise asyncio.TimeoutError()
    n = len(sent)
    r = await plug(slow_bad).draw_tool(Ev(), "x")
    await asyncio.sleep(0.6)
    check("后来没画成也记下来、不替她发话", "没画成" in notes[-1][1] and "太久没回" in notes[-1][1] and len(sent) == n, notes[-1:])
    cm.TOOL_WAIT = 100
    # 好感度 70 以上的人能用，不到的不行
    n = len(sent)
    r = await plug(good).draw_tool(Ev("20002", gid="30001"), "a cat")
    check("好感度不到 70 不画", r.startswith("没画") and "70" in r and len(sent) == n, r)
    r = await plug(good).draw_tool(Ev("20001", gid="30001"), "a cat")
    check("好感度 80 能画、发在群里", r.startswith("画好了") and "已经发到这里" in r and "图册 #" in r and sent[-1][0] == "x:GroupMessage:30001", (r, sent[-1:]))
    # 群里叫的、发到 TA 的私聊，带一句话
    notes.clear()
    r = await plug(good).draw_tool(Ev("20001", gid="30001", msg="想偷偷看小肥鱼今天的穿搭"), "outfit", True,
                                   to_private=True, text="就给你看哦")
    check("发到 TA 的私聊", r.startswith("画好了，已经发到TA 的私聊") or "TA 的私聊" in r, r)
    check("私聊里话和图一起发", sent[-1][0] == "x:FriendMessage:20001" and sent[-1][1] == [("text", "就给你看哦"), ("image", sent[-1][1][1][1])], sent[-1:])
    check("私聊记下起因（那边历史里没有）", notes and notes[-1][0] == "x:FriendMessage:20001" and "想偷偷看" in notes[-1][1]
          and "就给你看哦" in notes[-1][1], notes)
    async def no_friend(umo, chain): raise RuntimeError("not friend")
    pp = plug(good); pp.context.send_message = no_friend
    r = await pp.draw_tool(Ev("20001", gid="30001"), "x", to_private=True)
    check("私聊发不过去说原因", "可能还不是 QQ 好友" in r, r)
    # 主人私聊畫的發不出去：圖照樣記著，lively_comic_post 能轉到群（10-28 10:31 那張被當成沒發，轉群找不到）
    po = plug(good); po.context.send_message = no_friend
    r = await po.draw_tool(Ev(), "long manga page")
    check("主人私聊发不出去：图留着（转不转她定，不提转群）", "图留着" in r and "lively_comic_post" not in r and "QQ 好友" not in r
          and po.gallery.recent(kind="拍照")[0]["status"] == "没发成", r)
    # 記下每個聊天剛畫的那張（說說配「刚画的」）：群裡叫的、發到私聊，兩邊都算
    pd = plug(good)
    pd._gallery = type(pd.gallery)(Path(tempfile.mkdtemp()), None, lambda g: g)   # 这一段自己一本图册
    r = await pd.draw_tool(Ev("20001", gid="30001"), "legs", to_private=True)
    got_p, got_g = pd.recent_drawn("x:FriendMessage:20001"), pd.recent_drawn("x:GroupMessage:30001")
    check("剛畫的：發到的私聊和叫她畫的群都記", got_p and got_g and got_p["path"] == got_g["path"] and got_p["prompt"] == "legs",
          (got_p, got_g))
    check("別的聊天沒有", pd.recent_drawn("x:GroupMessage:39999") is None)
    pd.gallery.update(got_g["id"], ts=int(time.time()) - 3 * 3600)
    check("超過兩小時不算", pd.recent_drawn("x:GroupMessage:30001") is None)
    # 轉發到群：一定寫編號；別人私聊／群裡叫她拍的不往群裡轉，〈主人〉私聊拍的可以，帶一句話圖和字在同一條
    pd._groups = lambda: ["30001"]; pd._served = lambda: ["30001"]; pd._gname = lambda g: "小凛群"
    pd.state["pending"] = {}
    async def _noop(*a, **k): return None
    pd._refresh_names, pd._one_pending, pd._note = _noop, (lambda: None), _noop
    pd.s.group_umo = lambda g: f"x:GroupMessage:{g}"
    r = await pd.post_tool(Ev("10001"), "", "30001", "x")
    check("不写编号不发、列最近的图", r.startswith("没发：没写发哪张") and f"#{got_p['id']}" in r, r)
    n_sent = len(sent)
    r = await pd.post_tool(Ev("10001"), str(got_p["id"]), "30001", "x")
    check("别人私聊里拍的不往群里转", r.startswith(f"没发：#{got_p['id']}") and "不是爹爹私聊里画的" in r and len(sent) == n_sent, r)
    await pd.draw_tool(Ev(), "owner photo")
    mine = pd.gallery.recent(kind="拍照")[0]["id"]
    r = await pd.post_tool(Ev("10001"), f"#{mine}", "30001", "本鱼自己拍的&&shy&&")
    check("配字和圖一起發", sent[-1][0] == "x:GroupMessage:30001" and sent[-1][1][0] == ("text", "本鱼自己拍的")
          and sent[-1][1][1][0] == "image" and f"发了 #{mine} 到「小凛群」" in r and "配的话「本鱼自己拍的」" in r, (sent[-1], r))
    check("群那邊記下配的話", "配的话是「本鱼自己拍的」" in notes[-1][1], notes[-1:])
    r = await pd.post_tool(Ev("10001"), str(mine), "30001", "再发一次")
    check("已經發過：照實說之前發到哪", "之前发过：" in r and "「小凛群」" in r, r)
    # 工具藏不藏
    class Tools:
        def __init__(self): self.names = {"lively_draw", "lively_comic_post"}
        def get_tool(self, n): return n in self.names
        def remove_tool(self, n): self.names.discard(n)
    class Req:
        def __init__(self): self.func_tool, self.extra_user_content_parts = Tools(), []
    for qq, want in (("20001", {"lively_draw"}), ("20002", set()), ("10001", {"lively_draw", "lively_comic_post"})):
        req = Req()
        await plug(good).hide_tools(Ev(qq, gid="30001", msg="聊天"), req)
        check(f"工具可见：{qq}", req.func_tool.names == want, req.func_tool.names)
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(run())
