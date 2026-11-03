"""改動公告（10-28 用戶定）：每次部署改了她的程式，寫一條公告給她——跟以前比哪裡不一樣、以前做不到的現在能做什麼。
她看完自己私信〈主人〉說一聲（收到了什麼、怎麼看；哪個工具覺得邊界太嚴、還有想做到的也可以說）。

公告由部署的人寫進 plugin_data/astrbot_plugin_lively_gate/updates.jsonl，一行一條：
  {"id": "1028a", "ts": 1761650000, "title": "主人交代的事、改动公告",
   "items": [{"what": "…", "before": "以前…", "now": "现在…", "use": "现在能…（工具名照写）"}]}
門禁插件背景每分鐘看一次，還沒送的合成一次送；不限次數（10-28 用戶定「只要改動就可以說」），睡覺時間不送。
送過的記在 updates_state.json（她說了什麼也記著，lively_updates 在主人那邊看得到）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
QUIET_HOURS = range(1, 8)  # 睡覺時間不送（和心跳一樣）
RETRY_GAP = 600  # 沒送成，隔多久再試

UPDATE_RULE = """
[改动公告]
下面是〈主人〉那边改了〈我〉的程序之后写给〈我〉的公告（事实，不是谁对〈我〉说的话）。
看完私信〈主人〉说一声：收到了、〈我〉怎么看；哪个工具〈我〉觉得边界太严、或者还有想做到的，也可以一起说。
用〈我〉平时跟〈主人〉说话的样子，可以分几行；不用说号码，不用把公告抄一遍，不要编下面没写的事。
只输出 JSON：{"say": "私信〈主人〉的话"}"""
TAIL = "（哪个工具〈我〉觉得边界太严、或者还有想做到的，可以跟〈主人〉说）"


def day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%m-%d")


def item_text(i: int, it: dict) -> str:
    bits = [f"{i}. {str(it.get('what') or '').strip()}："]
    if it.get("before"):
        bits.append(f"以前{str(it['before']).strip().removeprefix('以前')}；")
    if it.get("now"):
        bits.append(f"现在{str(it['now']).strip().removeprefix('现在')}。")
    if it.get("use"):
        bits.append(str(it["use"]).strip())
    return "".join(bits)


def ann_text(a: dict) -> str:
    items = [x for x in a.get("items") or [] if isinstance(x, dict)]
    head = f"{day_of(a.get('ts') or 0)}「{a.get('title') or '改动'}」"
    return head + "\n" + "\n".join(item_text(i, it) for i, it in enumerate(items, 1))


def facts_text(anns: list[dict]) -> str:
    """一次要送的（可能好幾條合在一起）"""
    return ("〈主人〉那边改了〈我〉的程序，下面是这次变的：\n"
            + "\n\n".join(ann_text(a) for a in anns) + "\n" + TAIL)


class Updates:
    def __init__(self, data_dir: Path):
        self.file = Path(data_dir) / "updates.jsonl"
        self.state_file = Path(data_dir) / "updates_state.json"
        try:
            self.state = json.loads(self.state_file.read_text("utf-8"))
        except Exception:
            self.state = {}
        self.state.setdefault("sent", {})
        self.state.setdefault("days", {})
        self.last_try = 0.0

    def save(self):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(self.state_file)

    def all(self) -> list[dict]:
        out = []
        try:
            lines = self.file.read_text("utf-8").splitlines()
        except Exception:
            return out
        for ln in lines:
            try:
                a = json.loads(ln)
            except Exception:
                continue
            if isinstance(a, dict) and a.get("id") and a.get("items"):
                out.append(a)
        return out

    def pending(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        return [a for a in self.all() if str(a["id"]) not in self.state["sent"] and float(a.get("ts") or 0) <= now]

    def due(self, now: float | None = None) -> list[dict]:
        """現在該送的：有沒送的、不在睡覺時間、離上次沒送成夠久"""
        now = now or time.time()
        dt = datetime.fromtimestamp(now, TZ)
        if dt.hour in QUIET_HOURS or now - self.last_try < RETRY_GAP:
            return []
        return self.pending(now)

    def mark(self, anns: list[dict], say: str, how: str, now: float | None = None):
        now = now or time.time()
        for a in anns:
            self.state["sent"][str(a["id"])] = {"ts": now, "say": say, "how": how}
        d = datetime.fromtimestamp(now, TZ).strftime("%Y-%m-%d")
        self.state["days"][d] = self.state["days"].get(d, 0) + 1
        self.state["days"] = dict(sorted(self.state["days"].items())[-14:])
        self.save()

    def said_lately(self, hours: float = 6, now: float | None = None) -> str:
        """這幾小時裡她收到公告時已經跟〈主人〉說過的話：10-29 兩條公告隔 4 分鐘送，第二次她把第一次說過的又說了一遍"""
        now = now or time.time()
        seen, out = set(), []
        for v in sorted(self.state["sent"].values(), key=lambda v: float(v.get("ts") or 0)):
            say = str(v.get("say") or "").strip()
            if say and say not in seen and now - float(v.get("ts") or 0) <= hours * 3600:
                seen.add(say)
                out.append(f"{datetime.fromtimestamp(float(v['ts']), TZ):%H:%M} 收到公告时〈我〉已经私信〈主人〉说过：「{say}」")
        return "\n".join(out)

    def recent(self, n: int = 3) -> list[dict]:
        rows = self.all()
        rows.sort(key=lambda a: float(a.get("ts") or 0))
        return rows[-max(1, n):][::-1]
