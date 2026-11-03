"""gate 群聊背景的圖片描述：先轉檔再送，讀不了的寫成「没看到这张图：原因」。stub 掉 astrbot 跑。

python3 tests/test_gate_caption.py
"""
import asyncio, importlib, os, sys, tempfile, types
from pathlib import Path

sys.argv = [sys.argv[0]]
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import test_gate_draft as base  # noqa: E402  先跑一遍舊的，順便拿 stub 好的 astrbot

g = base.g
tmp = tempfile.mkdtemp()


class TooBig(Exception):
    pass


class Resolver:
    def __init__(self, ref, media_type="image"): self.ref = ref
    def as_path(self): return self
    async def __aenter__(self):
        if self.ref.startswith("http"):
            raise OSError("HTTP status code: 400")
        self.path = Path(self.ref); return self
    async def __aexit__(self, *a): return False


async def prepare(ref, max_size, output_dir):
    data = Path(ref).read_bytes()
    if data.startswith(b"BIG"):
        raise TooBig(ref)
    if data.startswith(b"PNG"):
        return ref, False, False, ref
    if data.startswith(b"BMP"):
        out = Path(output_dir) / "conv.png"; out.write_bytes(b"PNG"); return str(out), False, True, ref
    return None


base.mod("astrbot.core.utils.media_utils", MODEL_IMAGE_MAX_INPUT_BYTES=20 * 1024 * 1024,
         ImageInputTooLargeError=TooBig, MediaResolver=Resolver, prepare_model_image=prepare)
sys.modules["astrbot.core.utils.astrbot_path"].get_astrbot_temp_path = lambda: tmp


def f(name, data):
    p = os.path.join(tmp, name); open(p, "wb").write(data); return p


sent = []
async def orig(this, url, pid, prompt):
    sent.append(url)
    if url.endswith("bad.png"):
        raise RuntimeError("400 unsupported image")
    return "一张图"

gate = base.new_gate({})
gate.context = types.SimpleNamespace(get_config=lambda: {})
run = lambda url, fn=orig: asyncio.run(gate._icl_caption(fn, None, url, "p", "q"))

assert run(f("a.png", b"PNG...")) == "一张图" and sent[-1].endswith("a.png")
assert run(f("a.bmp", b"BMP...")) == "一张图" and sent[-1].endswith("conv.png")
assert not os.path.exists(os.path.join(tmp, "conv.png"))  # 轉出來的暫存檔用完刪掉
assert run(f("a.heic", b"\0\0\0\x18ftypheic\0\0\0\0mif1")) == "没看到这张图：是 HEIC 格式（苹果相机拍的那种），这边打不开"
assert run(f("a.jpg", b"<html>expired</html>")) == "没看到这张图：下载下来的不是图片"
assert run(f("e.jpg", b"")) == "没看到这张图：下载下来是空的"
assert run(f("x.jpg", b"\x01\x02junk")) == "没看到这张图：图片格式打不开"
assert run(f("big.png", b"BIG")).startswith("没看到这张图：图太大了")
assert run("https://example.invalid/x") == "没看到这张图：图没下载下来（链接可能过期了）"
assert run(f("bad.png", b"PNG")) == "没看到这张图：看图那边出错了"

# QQ 商城表情：不下載，照實寫名字（10-26 群裡四張 gxh.vip.qq.com 都 404）
MF = "https://gxh.vip.qq.com/club/item/parcel/item/ab/abcdef/raw300.gif"
ev = base.Ev([base.Image(MF)] if hasattr(base, "Image") else [], "")
ev.message_obj.raw_message = {"message": [
    {"type": "image", "data": {"url": MF, "file": "abcdef.gif", "summary": "[摸摸猫猫]"}},
    {"type": "image", "data": {"url": "https://multimedia.nt.qq.com.cn/x", "summary": "", "sub_type": "0"}},
]}
assert g._mfaces(ev) == [([MF, "abcdef.gif"], "摸摸猫猫")]
n = len(sent)
gate._note_mfaces(ev)
assert ev.get_extra("lively_mfaces") == ["摸摸猫猫"]
assert run(MF) == "QQ 表情「摸摸猫猫」（只看得到名字，图 QQ 那边下载不到）" and len(sent) == n  # 沒送去看圖
assert run("https://gxh.vip.qq.com/club/item/parcel/item/cd/cdef/raw300.gif") == g.MFACE_NAMELESS
for i in range(g.MFACE_KEEP + 5):
    e2 = base.Ev([], ""); e2.message_obj.raw_message = {"message": [
        {"type": "image", "data": {"url": f"https://gxh.vip.qq.com/{i}/raw300.gif", "summary": f"[{i}]"}}]}
    gate._note_mfaces(e2)
assert len(gate._mface_names) <= g.MFACE_KEEP
plain = base.Ev([], "hi"); plain.message_obj.raw_message = {"message": [{"type": "text", "data": {"text": "hi"}}]}
gate._note_mfaces(plain); assert plain.get_extra("lively_mfaces") is None

# 包上超時之後也走同一條路
gate._patch_icl_caption()
cls = sys.modules["astrbot.builtin_stars.astrbot.group_chat_context"].GroupChatContext
assert asyncio.run(cls().get_image_caption(f("c.bmp", b"BMP"), "p", "q")) == "一张图"
# 記下描述給發完複查查（QQ 歷史裡同一張圖 rkey 不一樣，按 fileid 認）
assert gate.caption_of(f("c.bmp", b"BMP")) == "一张图"
gate._note_caption("https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQ1&rkey=AAA", "一只猫")
assert gate.caption_of("https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQ1&rkey=BBB") == "一只猫"
assert gate.caption_of("https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=Other") == ""
for i in range(g.CAPTION_KEEP + 5):
    gate._note_caption(f"https://x/download?fileid=k{i}", "图")
assert len(gate._captions) == g.CAPTION_KEEP and gate.caption_of("https://x/download?fileid=k0") == ""
asyncio.run(gate.terminate()) if hasattr(gate, "rhythm") else None

# 喊名字開頭的：AstrBot 剪掉名字，門禁補回去（10-27「小肥鱼呢」她只收到「呢」）
def named(raw, cur, wake=True):
    e = base.Ev([base.Plain(raw)], cur, wake); e.message_obj.message_str = raw; return e
gn = base.new_gate({}); gn.name = "小肥鱼"
e = named("小肥鱼呢", "呢"); gn._keep_name(e); assert e.message_str == "小肥鱼呢"
e = named("小肥鱼 今天吃啥", "今天吃啥"); gn._keep_name(e); assert e.message_str == "小肥鱼 今天吃啥"
e = named("小肥鱼 /好感", "/好感"); gn._keep_name(e); assert e.message_str == "/好感"          # 指令照舊
e = named("@小肥鱼 在吗", "在吗"); gn._keep_name(e); assert e.message_str == "在吗"            # 打出來的 @ 照舊
e = named("小肥鱼呢", "呢", wake=False); gn._keep_name(e); assert e.message_str == "呢"        # 不是喚醒的不動
e = named("早啊小肥鱼", "早啊小肥鱼"); gn._keep_name(e); assert e.message_str == "早啊小肥鱼"
gn.name = ""; e = named("小肥鱼呢", "呢"); gn._keep_name(e); assert e.message_str == "呢"
print("keep name ok")
print("caption convert ok")
