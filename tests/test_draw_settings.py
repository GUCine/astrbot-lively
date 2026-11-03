"""面板值班頁的「画图」（10-27）：聊天裡畫圖開關、好感度門檻、每天張數，面板撥了馬上生效。

/usr/local/bin/python3 tests/test_draw_settings.py（號碼是假的：10001 主人）
"""
import asyncio, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_draw_wait as base  # noqa: E402  先跑一遍舊的，順便拿 stub 好的 astrbot

cm, TMP, Ev = base.cm, base.TMP, base.Ev
ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))


class Cfg(dict):
    saved = 0
    def save_config(self): Cfg.saved += 1


class S(base.S):
    def __init__(self): self.cfg = Cfg()
    def get(self, k, d=None): return self.cfg.get(k, d)


async def run():
    cls = next(v for v in vars(cm).values() if isinstance(v, type) and hasattr(v, "draw_tool"))
    sent = []
    async def send_message(umo, chain): sent.append(umo)
    async def good(prov, prompt, ref, size=""): return b"png"
    p = object.__new__(cls)
    p.s, p.draw_max, p.dir = S(), 20, TMP
    p.self_look, p.self_ref = "", None
    p.state = {"draw_day": "", "draw_count": 0, "draw_jobs": []}
    p._waiting = set(); p._seen = {}; p._names = {}
    p.context = types.SimpleNamespace(send_message=send_message, get_registered_star=base.get_star)
    p._save = lambda: None
    p._log = lambda *a, **k: None
    p._owner_umo = lambda: "x:FriendMessage:10001"
    p._drawing_providers = lambda: [{"model": "gpt-image-2.5"}, {"model": "gpt-image-2.5-flare"}]
    p._call_images = good
    p.phone = cm.Phone(p)

    b = p.draw_brief()
    check("簡報：預設開、門檻 70、20 張、兩個 GPT 模型", b["chat"] and b["min"] == 70 and b["max"] == 20
          and b["models"] == ["gpt-image-2.5", "gpt-image-2.5-flare"] and b["today"] == 0, b)
    r = await p.draw_tool(Ev(), "a cat")
    check("開著主人能畫", r.startswith("画好了"), r)
    check("簡報記到今天畫了 1 張", p.draw_brief()["today"] == 1)

    okk, msg = p.set_draw("draw_chat", False)
    check("關掉聊天裡畫圖，存進設定", okk and p.s.cfg["draw_chat"] is False and Cfg.saved == 1, (okk, msg))
    n = len(sent)
    r = await p.draw_tool(Ev(), "a cat")
    check("關了主人也畫不了、照實說", r.startswith("没画") and "关着" in r and len(sent) == n, r)

    class Tools:
        def __init__(self): self.names = {"lively_draw"}
        def get_tool(self, n): return n in self.names
        def remove_tool(self, n): self.names.discard(n)
    class Req:
        def __init__(self): self.func_tool, self.extra_user_content_parts = Tools(), []
    req = Req()
    await p.hide_tools(Ev(msg="给我画一张"), req)
    check("關了工具也拿掉", "lively_draw" not in req.func_tool.names, req.func_tool.names)
    hint = "".join(getattr(x, "text", "") for x in req.extra_user_content_parts) if req.extra_user_content_parts else ""
    check("說到畫畫時告訴她是關著（不是好感度不夠）", not hint or ("关着" in hint and "好感度" not in hint), hint)

    p.set_draw("draw_chat", True)
    okk, msg = p.set_draw("draw_min_score", "50")
    check("改門檻", okk and p._draw_min() == 50 and "50" in msg, (okk, msg))
    check("門檻越界不收", not p.set_draw("draw_min_score", 95)[0] and not p.set_draw("draw_min_score", "x")[0])
    r = await p.draw_tool(Ev("20002", gid="30001"), "a cat")
    check("好感度 50 的人門檻 50 能畫", r.startswith("画好了"), r)

    okk, msg = p.set_draw("draw_daily_max", "2")
    check("改張數馬上生效", okk and p.draw_max == 2 and p.s.cfg["draw_daily_max"] == 2, (okk, msg))
    r = await p.draw_tool(Ev(), "a cat")
    check("到上限照實說", r.startswith("没画") and "2 张" in r, r)
    check("張數越界不收", not p.set_draw("draw_daily_max", -1)[0] and not p.set_draw("draw_daily_max", 999)[0])
    check("別的鍵不收", not p.set_draw("comic_at", "21:00")[0])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(run())
