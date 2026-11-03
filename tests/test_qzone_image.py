"""說說配圖：寫草稿時自己決定配不配圖、配什麼圖、借畫圖插件畫、給主人審、通過後先傳圖再發。stub 掉 astrbot 和空間介面直接跑。

python3 tests/test_qzone_image.py（號碼都是假的）
"""
import asyncio, importlib, json, sys, tempfile, types
from pathlib import Path


# ---- stub astrbot ----
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(event_message_type=deco, llm_tool=deco, on_llm_request=deco, EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
TMP = Path(tempfile.mkdtemp())
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
class Star:
    def __init__(self, context=None): self.context = context
class StarTools:
    @staticmethod
    def get_data_dir(name): p = TMP / name; p.mkdir(parents=True, exist_ok=True); return p
mod("astrbot.api.star", Context=object, Star=Star, register=deco, StarTools=StarTools)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
class MessageChain:
    def __init__(self): self.parts = []
    def message(self, t): self.parts.append(("text", t)); return self
    def file_image(self, p): self.parts.append(("image", p)); return self
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=MessageChain)
mod("aiohttp")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
q = importlib.import_module("astrbot_plugin_lively_qzone.main")


# ---- 假的模型、畫圖插件、空間介面 ----
REPLY = "本鱼回来啦，刚才脑子打结了～\n吃了碗白饭，满血复活🍚\n配图：a cute chibi whale girl hugging a big bowl of rice, sunrise, cute anime illustration [me]"
class Prov:
    async def text_chat(self, prompt, system_prompt):
        if "[后台的事" in system_prompt:  # 問她要不要跟主人說（lively_common.her_words）
            return types.SimpleNamespace(completion_text='{"say": "爹爹，配了张图的说说，你看看"}')
        Prov.system = system_prompt
        return types.SimpleNamespace(completion_text=REPLY)
class Comic:
    calls = []
    async def draw_bytes(self, prompt, with_self=False):
        Comic.calls.append((prompt, with_self)); return b"PNG"
sent = []
class Ctx:
    def get_registered_star(self, name):
        return types.SimpleNamespace(star_cls=Comic()) if name == "astrbot_plugin_lively_comic" else None
    async def send_message(self, umo, chain): sent.append((umo, chain.parts))
    def get_provider_by_id(self, pid): return None
class S:
    context = Ctx()
    def shared(self, k, d=None): return d
    def me(self): return "小鱼"
    def provider(self): return Prov()
    def persona_prompt(self): return "你是小鱼。"
    def owner(self): return "10001"
    def private_umo(self, qq): return f"p:FriendMessage:{qq}"
    def owner_text(self, t): return t
    def fill(self, t): return t
    def is_owner(self, qq): return str(qq) == "10001"

z = q.LivelyQzone.__new__(q.LivelyQzone)
z.context, z.s = Ctx(), S()
z._tasks = set()


def run(coro):
    """跑完再等背景裡私信主人的那些（asyncio.run 結束會把沒做完的取消掉）"""
    async def go():
        r = await coro
        await asyncio.gather(*list(z._tasks))
        return r
    return asyncio.run(go())
z.dir = StarTools.get_data_dir("astrbot_plugin_lively_qzone"); z.data = z.dir.parent
z.state_file, z.events_file = z.dir / "state.json", z.dir / "events.jsonl"
z.state = z._load(); z.state["mode"] = "auto"  # 自動模式下配圖的也要先審
z._today_bits = lambda: "今天群里没什么特别的事\n"
calls = []
async def fake_call(method, url, *, params=None, data=None, retry=True, timeout=30, full_cookies=False):
    calls.append((url, dict(data or {}), full_cookies))
    if url == q.UPLOAD_URL:
        return {"ret": 0, "data": {"albumid": "A", "lloc": "L", "sloc": "S", "type": 1, "height": 1024, "width": 1024,
                                   "url": "http://x/y?a=1&bo=BO123"}}
    return {"code": 0, "tid": "T1"}
z._call = fake_call
async def fake_login(force=False): return (10001, "sk", "psk", 0)
z._login = fake_login

msg = run(z.new_draft("恢复上线", image=True))
assert msg == "草稿已发给主人", msg
d = z.state["draft"]
assert "配图" not in d["text"] and d["text"].startswith("本鱼回来啦"), d
assert d["image"] and Path(d["image"]).read_bytes() == b"PNG"
assert Comic.calls == [("a cute chibi whale girl hugging a big bowl of rice, sunrise, cute anime illustration", True)], Comic.calls
assert "配图：" in Prov.system
(u1, said), (umo, parts) = sent[-2:]
assert said == [("text", "爹爹，配了张图的说说，你看看")], said  # 先是她的話
assert umo == "p:FriendMessage:10001" and parts[-1] == ("image", d["image"]) and parts[0][1].startswith("【后台】说说草稿")
assert "回「发」" not in parts[0][1]  # 沒有固定指令
assert not calls  # 還沒發
print("draft ok")

# 主人回「发」：先傳圖、再帶 richval／pic_bo 發
asyncio.run(z.publish(d["text"], d["image"]))
up, pub = calls[0], calls[1]
assert up[0] == q.UPLOAD_URL and up[2] and up[1]["base64"] == "1" and up[1]["picfile"] == "UE5H"
assert pub[0] == q.PUBLISH_URL and pub[1]["richtype"] == "1" and pub[1]["pic_bo"] == "BO123"
assert pub[1]["richval"] == ",A,L,S,1,1024,1024,,1024,1024" and pub[1]["con"] == d["text"]
name = Path(d["image"]).name
assert z.state["posted"][-1]["image"] == name
ev = [e for e in map(json.loads, z.events_file.read_text("utf-8").splitlines()) if e["kind"] != "report"]
assert ev[-2]["kind"] == "draft" and ev[-2]["image"] == name and ev[-2]["image_prompt"].startswith("a cute chibi")
assert ev[-1]["kind"] == "posted" and ev[-1]["image"] == name  # 記錄帶圖檔名，面板照名字取圖
print("publish ok")

# 沒寫配圖那行：不發草稿
REPLY = "就一句话没有图"
z.state["draft"] = None
assert run(z.new_draft("", image=True)).startswith("没想好配什么图") and z.state["draft"] is None
# 她自己決定（image=None，定時寫、面板「写一条」都是這樣）：提示詞說配不配隨她
# 這次沒想配圖 → 自動模式直接發、不畫不傳圖
calls.clear(); Comic.calls.clear()
run(z.new_draft(""))
assert "配不配图你自己决定" in Prov.system and "要配一张图" not in Prov.system
assert [c[0] for c in calls] == [q.PUBLISH_URL] and "richval" not in calls[0][1] and not Comic.calls
assert "image" not in z.state["posted"][-1]
# 她想配圖 → 畫好、先給主人審（配圖的一定先審），want_image 記成 None，重寫時還是她自己決定
REPLY = "窝在被子里吃白饭，幸福～\n配图：a whale girl in a blanket eating rice, cozy night, cute anime illustration [me]"
calls.clear()
assert run(z.new_draft("")) == "草稿已发给主人" and not calls
d = z.state["draft"]
assert d["image"] and d["want_image"] is None and d["text"] == "窝在被子里吃白饭，幸福～" and Comic.calls[-1][1] is True
# 她想配但畫不出來 → 只發字（一定要配圖的才放棄）
class Broken:
    async def draw_bytes(self, prompt, with_self=False): raise RuntimeError("额度用完")
z.context.get_registered_star = lambda name: types.SimpleNamespace(star_cls=Broken())
z.state["draft"] = None; calls.clear()
assert run(z.new_draft("")).startswith("已发布") and [c[0] for c in calls] == [q.PUBLISH_URL]
assert run(z.new_draft("", image=True)).startswith("配图没画出来")
# 介面指定不配（image=False，面板用）：寫了配圖行也拿掉、不畫
calls.clear()
assert run(z.new_draft("", image=False)).startswith("已发布")
assert "配图" not in calls[-1][1]["con"] and "配不配图" not in Prov.system
z.context.get_registered_star = Ctx().get_registered_star
print("self decide ok")
# 起草稿寫成說說：挑出終稿、配圖行留著；挑不出來不寫（自動模式會直接發出去）
REPLY = "情景：今天群里在聊白饭\n语气：懒洋洋，短\n写：今天也是吃白饭的一天🍚\n配图：a whale girl eating rice [me]"
t = asyncio.run(z.write("白饭", image=True))
assert t == "今天也是吃白饭的一天🍚\n配图：a whale girl eating rice [me]", t
REPLY = "情景：今天群里在聊白饭\n写：懒洋洋的一句，带表情\n好感 0，开心"
assert asyncio.run(z.write("白饭")) is None
print("draft guard ok")
print("all ok")
