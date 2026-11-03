"""gate 的 lively_serve_group（10-26）：〈主人〉說了〈我〉自己把群加進服務的群或拿掉；別人叫的不改；
只能加〈我〉已經在裡面的群；群名裡的字也認；存進設定。stub 掉 astrbot，號碼都是假的：10001 主人、2000x 群友、3000x 群。

/usr/local/bin/python3 tests/test_serve_group.py
"""
import asyncio, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import test_gate_draft as base  # noqa: E402  先跑一遍舊的，順便拿 stub 好的 astrbot

fails = []


def check(name, ok, extra=""):
    print(("ok  " if ok else "FAIL"), name, "" if ok else extra)
    if not ok:
        fails.append(name)


class Cfg(dict):
    saved = 0
    fail = False
    def save_config(self):
        if self.fail:
            raise OSError("disk full")
        Cfg.saved += 1


class Bot:
    def __init__(self, groups=None, down=False):
        self.groups, self.down = groups if groups is not None else {30001: "浅梦心羽", 30002: "小凛无限趴", 30003: "小凛分部"}, down
        self.api = types.SimpleNamespace(call_action=self.call_action)
    async def call_action(self, action, **kw):
        assert action == "get_group_list", action
        if self.down:
            raise RuntimeError("offline")
        return [{"group_id": g, "group_name": n} for g, n in self.groups.items()]


class Comic:
    state = {"enabled": True, "off_groups": []}
    def __init__(self, gate): self.gate = gate
    def _groups(self): return [g for g in self.gate.cfg.get("groups", []) if g not in self.state["off_groups"]]


def gate_with(groups):
    gate = base.new_gate(Cfg(groups=list(groups)))
    fill = lambda t: t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    gate.s = types.SimpleNamespace(fill=fill, groups=lambda: list(gate.cfg.get("groups", [])),
                                   is_owner=lambda q: str(q) == "10001", client=lambda: None)
    comic = Comic(gate)
    gate.context = types.SimpleNamespace(get_registered_star=lambda n: types.SimpleNamespace(star_cls=comic, activated=True)
                                         if n == "astrbot_plugin_lively_comic" else None)
    return gate, comic


class Ev:
    def __init__(self, sender, bot): self.sender, self.bot = sender, bot
    def get_sender_id(self): return self.sender


gate, comic = gate_with(["30002"])
bot = Bot()
run = lambda who, group, action="加": asyncio.run(gate.tool_serve_group(Ev(who, bot), group, action))

r = run("20001", "30001")
check("别人叫的不改", r.startswith("没改") and "爹爹说了" in r and gate.cfg["groups"] == ["30002"], r)
r = run("10001", "30001")
check("主人说了就加上", gate.cfg["groups"] == ["30002", "30001"] and Cfg.saved == 1 and r.startswith("加上了：「浅梦心羽」（30001）")
      and "看得到" in r, (r, gate.cfg))
check("加上时说群漫画也会画", "群漫画" in r and "面板「群里」页能关" in r, r)
r = run("10001", "30001")
check("已经在里面不重复加", "本来就在本鱼服务的群里" in r and gate.cfg["groups"] == ["30002", "30001"], r)
r = run("10001", "30009")
check("不在的群加不了", r.startswith("没改：本鱼不在「30009」这个群里") and "已经在里面" in r and "30009" not in gate.cfg["groups"], r)
r = run("10001", "小凛")
check("群名对上好几个要说哪个", r.startswith("没改：好几个群都对得上") and "30002" in r and "30003" in r, r)
r = run("10001", "分部")
check("群名里的字也认", "30003" in gate.cfg["groups"] and r.startswith("加上了：「小凛分部」（30003）"), r)
comic.state["off_groups"] = ["30003"]
run("10001", "30003", "拿掉")
r = run("10001", "30003")
check("群漫画关着就不提", "群漫画" not in r, r)
r = run("10001", "浅梦", "拿掉")
check("拿掉", "30001" not in gate.cfg["groups"] and r.startswith("拿掉了：「浅梦心羽」（30001）") and "人还在群里" in r, r)
r = run("10001", "30001", "不要了")
check("本来就不在服务的群里", "本来就不在" in r, r)
check("服务的群没在 QQ 群列表里也能拿掉", run("10001", "30002", "去掉").startswith("拿掉了：群 30002") or "30002" not in gate.cfg["groups"])

g2, _ = gate_with(["30002"])
g2.cfg.fail = True
r = asyncio.run(g2.tool_serve_group(Ev("10001", Bot()), "30001"))
check("存不进去就不改", r == "没改：设置存不进去" and g2.cfg["groups"] == ["30002"], r)
r = asyncio.run(g2.tool_serve_group(Ev("10001", Bot(down=True)), "30001"))
check("QQ 掉线照实说", r.startswith("没改：QQ 那边拿不到群列表"), r)

print("all ok" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
