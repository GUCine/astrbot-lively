"""心情慣性（bond core.inertia_step，10-26）：同方向的詞照換，反方向一句話不翻、連著兩輪才換；log 只記錄不改真的心情，on 照慣性走。

python3 tests/test_mood_inertia.py（號碼都是假的）
"""
import sys, tempfile, time
from datetime import datetime
from pathlib import Path

import types


def _stub(name, **kw):  # core 借 lively_common 的「记住」行規則，那邊開頭要 import astrbot
    m = types.ModuleType(name)
    m.__dict__.update(kw)
    sys.modules.setdefault(name, m)


_stub("astrbot")
_stub("astrbot.api", logger=types.SimpleNamespace(**{k: (lambda *a, **kw: None) for k in ("info", "warning", "error", "debug")}))
_stub("astrbot.core")
_stub("astrbot.core.utils")
_stub("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "astrbot_plugin_lively_bond"))
import core  # noqa: E402
from core import BondStore, inertia_step, mood_dir, mood_kind  # noqa: E402

T0 = time.time()

# ---- 方向 ----
assert mood_dir("害羞") == "good" and mood_dir("小生气") == "bad" and mood_dir("担心") == "bad"
assert mood_dir("平常") is None and mood_dir("认真") is None
assert mood_dir(mood_kind("心里软软的"), "心里软软的") == "good"
assert mood_dir(mood_kind("不服气"), "不服气") == "bad"
assert mood_dir(mood_kind("又软又心疼"), "又软又心疼") is None  # 兩邊都沾，不猜

# ---- 一步一步 ----
s, how = inertia_step({}, "害羞", "羞死了", T0)
assert how == "new" and s["level"] == 2 and s["word"] == "羞死了"
s, how = inertia_step(s, "开心", "开心", T0 + 60)  # 同方向：照換
assert how == "shade" and s["mood"] == "开心"
s, how = inertia_step(s, "嫌弃", "嫌弃", T0 + 120)  # 反方向第一次：留著，弱一級
assert how == "hold" and s["mood"] == "开心" and s["level"] == 1 and s["pend"] == "bad", s
s2, how = inertia_step(dict(s), "小生气", "哼", T0 + 180)  # 原來的只剩 1 級：直接換
assert how == "switch" and s2["mood"] == "小生气"
s = {**s, "level": 3}
s3, how = inertia_step(dict(s), "委屈", "委屈", T0 + 240)  # 連著兩輪反方向：換
assert how == "switch2" and s3["mood"] == "委屈" and not s3["pend"], s3
s4, how = inertia_step(dict(s), "委屈", "委屈", T0 + 120 + core.INERTIA_PEND + 1)  # 隔太久不算連著
assert how == "hold", how
# 按時間弱下去：90 分鐘弱一級，at 往前推
s5, how = inertia_step({"mood": "开心", "word": "开心", "level": 2, "at": T0}, "嫌弃", "嫌弃", T0 + 95 * 60)
assert how == "switch" and s5["mood"] == "嫌弃", (how, s5)
s6, how = inertia_step({"mood": "开心", "word": "开心", "level": 2, "at": T0}, "平常", "平常", T0 + 60)
assert how == "calm" and s6["level"] == 1

# ---- 店裡：log 不改真的，on 照慣性；主人那三天的真實順序 ----
REAL = """10-24 16:04:43 又软又心疼|10-24 16:08:03 软得发慌|10-24 20:23:03 软软的|10-24 21:09:33 羞得不行|10-24 21:19:26 害羞|
10-24 23:25:14 羞死了|10-24 23:53:44 害羞|10-24 23:53:59 羞死了|10-24 23:57:54 有点慌|10-24 23:58:35 害羞|10-25 09:52:19 害羞|
10-25 14:54:10 嘴硬|10-25 14:56:18 心动|10-25 14:56:38 嘴硬|10-25 15:01:09 暖|10-25 15:41:37 开心|10-25 15:42:09 害羞|
10-25 19:41:57 心跳|10-25 20:01:48 害羞|10-25 23:15:05 嘴硬|10-25 23:16:53 心软|10-26 00:57:44 担心|10-26 08:03:00 开心|
10-26 08:25:47 害羞|10-26 08:26:05 开心|10-26 08:52:48 害羞|10-26 09:22:51 开心|10-26 10:20:51 害羞|10-26 10:24:35 认真|
10-26 13:54:17 害羞|10-26 15:00:29 开心|10-26 15:02:57 害羞|10-26 15:04:06 嫌弃|10-26 15:04:31 害羞|10-26 16:33:32 开心|
10-26 16:36:01 不服气|10-26 16:38:03 心里软了一下|10-26 16:49:34 心里软软的|10-26 16:50:10 期待|10-26 17:00:07 开心"""
seq = []
for x in REAL.replace("\n", "").split("|"):
    d, w = x.strip().rsplit(" ", 1)
    seq.append((datetime.strptime("2026-" + d, "%Y-%m-%d %H:%M:%S").timestamp(), w))


def run(mode):
    db = BondStore(str(Path(tempfile.mkdtemp()) / "bond.db"))
    for ts, w in seq:
        db.apply_tag("30001", "阿A", {"delta": 0, "mood": mood_kind(w), "mood_word": w, "impression": None}, "dm", now=ts, inertia=mode)
    ev = lambda k: [r["note"] for r in db.db.execute("SELECT note FROM events WHERE kind=? ORDER BY ts", (k,))]
    return db, ev("mood"), ev("mood_inertia")


db, real, shadow = run("off")
assert not shadow and not db.db.execute("SELECT * FROM mood_shadow").fetchall()
off_moods = len(real)
db, real, shadow = run("log")
assert len(real) == off_moods  # 照舊換、照舊記
holds = [n for n in shadow if n.startswith("留在")]
changes = [n for n in shadow if n.startswith("换成")]
assert any("嫌弃" in n for n in holds) and any("不服气" in n for n in holds), holds  # 夾在害羞、開心中間的那一句不翻
assert len(changes) < off_moods, (len(changes), off_moods)
p = db.load("30001", now=seq[-1][0] + 60)
assert p["mood_word"] == "开心"
db, real_on, shadow_on = run("on")
assert len(real_on) == len(changes), (real_on, changes)  # on 的心情變化就是 log 記的「换成」
assert [n for n in shadow_on if n.startswith("留在")] == holds
pend = db.mood_shadow("30001")
assert set(pend) == {"pend", "pend_at"}  # on 時只留反方向的記號
print(f"mood inertia ok（真實順序：照舊換大類 {off_moods} 次，慣性下 {len(changes)} 次，留住 {len(holds)} 次：{holds}）")
