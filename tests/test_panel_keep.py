"""面板記錄保留：值班日誌寫檔、重啟後讀回最近 7 天，過期的搬進 archive/，events 按天數取。stub 掉 astrbot、aiohttp 直接跑。

python3 tests/test_panel_keep.py
"""
import importlib, json, logging, sys, tempfile, threading, time, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
TMP = Path(tempfile.mkdtemp())
mod("aiohttp", ClientTimeout=object, ClientSession=object); mod("aiohttp.web", middleware=lambda f: f, Request=object)
sys.modules["aiohttp"].web = sys.modules["aiohttp.web"]
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.star", Context=object, Star=type("Star", (), {"__init__": lambda self, c=None: None}), register=deco, StarTools=object)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pm = importlib.import_module("astrbot_plugin_lively_panel.main")

now = time.time()
day = 86400

# ---- 值班日誌：寫檔，重啟後讀回最近 7 天 ----
f = TMP / "logs.jsonl"
f.write_text("\n".join(json.dumps({"ts": now - d * day, "level": "WARNING", "src": "x", "msg": f"{d} 天前"}) for d in (10, 8, 3, 0)) + "\n壞行\n")
from collections import deque
buf = deque(pm._recent(f), maxlen=100)
assert [e["msg"] for e in buf] == ["3 天前", "0 天前"], list(buf)
lock = threading.Lock()
lg = logging.getLogger("astrbot.test_keep"); lg.propagate = False
lg.addHandler(pm._Ring(buf, f, lock)); lg.warning("新的警告 \x1b[31m红\x1b[0m"); lg.info("info 不记")
assert buf[-1]["msg"] == "新的警告 红" and len(buf) == 3
assert json.loads(f.read_text().splitlines()[-1])["msg"] == "新的警告 红"
print("ring ok")

# ---- 歸檔：過期的按月份搬進 archive/，壞行丟掉，留下的不動 ----
n = pm._archive(f, lock)
assert n == 2, n
left = [json.loads(x)["msg"] for x in f.read_text().splitlines()]
assert left == ["3 天前", "0 天前", "新的警告 红"], left
arch = list((TMP / "archive").glob("logs-*.jsonl"))
assert arch and sum(len(a.read_text().splitlines()) for a in arch) == 2
assert pm._archive(f, lock) == 0  # 再跑一次沒東西可搬
print("archive ok")

# ---- events：按天數取，不按條數 ----
pm.PD = TMP
ev = TMP / "astrbot_plugin_lively_social"; ev.mkdir()
rows = [{"ts": now - 9 * day, "kind": "friend_request", "qq": "old"}]
rows += [{"ts": now - i * 60, "kind": "friend_request", "qq": str(i)} for i in reversed(range(60))]  # 照時間追加，60 封，以前只給 40
rows += [{"ts": now, "kind": "muted"}]
(ev / "events.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
got = pm.LivelyPanel._events("astrbot_plugin_lively_social", {"friend_request"})
assert len(got) == 60 and got[0]["qq"] == "0" and all(e["qq"] != "old" for e in got), len(got)
print("all ok")
