"""群友 QQ 頭像不一定是 JPEG（10-27 某個群 千面的頭像是 GIF、存成 .jpg，中轉站回「参考图损坏或无效」整張沒畫成）：
快取的頭像一律轉成真的 JPEG，讀不出來的不帶。

/usr/local/bin/python3 tests/test_avatar_jpeg.py
"""
import asyncio, io, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_draw_wait as base  # noqa: E402  拿 stub 好的 astrbot
from PIL import Image  # noqa: E402

ph = sys.modules["astrbot_plugin_lively_comic.phone"]
ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))


def img(fmt, mode="RGB", size=(100, 100)):
    b = io.BytesIO()
    Image.new(mode, size, (200, 30, 30, 0) if mode == "RGBA" else (200, 30, 30)).save(b, fmt)
    return b.getvalue()


gif, png, jpg = img("GIF", "P"), img("PNG", "RGBA", (640, 640)), img("JPEG")
for name, data in (("GIF", gif), ("带透明的 PNG", png), ("JPEG", jpg)):
    out = ph.jpeg_bytes(data)
    check(f"{name} 转成真的 JPEG", out and out[:2] == b"\xff\xd8" and Image.open(io.BytesIO(out)).format == "JPEG")
check("透明的地方铺白底", Image.open(io.BytesIO(ph.jpeg_bytes(png))).getpixel((5, 5)) == (255, 255, 255))
check("读不出来是 None", ph.jpeg_bytes(b"not an image" * 100) is None)

D = base.TMP / "avjpeg"
D.mkdir(parents=True, exist_ok=True)
phone = ph.Phone(types.SimpleNamespace(dir=D, s=base.S()))
ph.AVATAR_URL = "http://127.0.0.1:9/{qq}"  # 不上网：重拿一定失败
qd = phone.meta_dir / "qq"
qd.mkdir(parents=True, exist_ok=True)


async def main():
    (qd / "20001.jpg").write_bytes(gif)
    got = await phone.person("20001", "千面")
    f = qd / "20001.jpg"
    check("以前存的 GIF 头像：转成 JPEG 接着用", got and got[0] == f and f.read_bytes()[:2] == b"\xff\xd8", got)
    (qd / "20002.jpg").write_bytes(b"broken" * 200)
    got = await phone.person("20002", "坏图")
    check("读不出来的旧头像：删掉，拿不到就不带", got is None and not (qd / "20002.jpg").exists(), got)
    (qd / "20003.jpg").write_bytes(jpg)
    got = await phone.person("20003", "正常")
    check("本来就是 JPEG 的照旧", got and (qd / "20003.jpg").read_bytes() == jpg, got)


asyncio.run(main())
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
