"""說話節奏：每個人連發幾條之間大概隔多久、私聊裡回〈我〉大概要多久。

用處有三個（都在 main.py 裡接上）：
1. 傾聽：被叫到（私聊每條都算）後先等這個人說完，連發的幾條合成一條交給模型。等多久按這個人平時連發的間隔算，
   還沒攢夠樣本的陌生人用預設值；再看最後一句像不像說完了（？！結尾短一點，…，結尾長一點）
2. 停頓：合併的幾條中間停得比平時久很多、或最後一句沒說完就沒下文了，告訴模型停了多久、TA 平時多快，
   讓她按情境判斷 TA 是在猶豫、難受還是去忙了
3. 沉默：私聊裡聊到難受的事，〈我〉回完之後 TA 好久沒說話（比 TA 平時回〈我〉慢很多），讓她自己決定要不要再說一句
   （追問、安慰，或者先不打擾）

只記時間間隔，不記內容；存在 plugin_data/astrbot_plugin_lively_gate/rhythm.json。
"""
from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path

BURST_MIN = 0.2
BURST_MAX = 25.0  # 同一個人兩條隔超過這個就不算連發（換話題、去忙了）
LAG_MAX = 1800.0  # 私聊裡〈我〉說完之後 TA 隔多久回；超過半小時不算
KEEP_GAPS = 40
KEEP_LAGS = 20
MIN_GAPS = 6  # 攢夠這麼多次連發才按 TA 自己的節奏算
MIN_LAGS = 4
DEFAULT_GAP = 2.5  # 陌生人：連發兩條大約隔這麼久
DEFAULT_LAG = 40.0
SAVE_EVERY = 60.0

# 傾聽等多久：基準 = 平時間隔 × WAIT_K + WAIT_ADD，夾在 WAIT_MIN～WAIT_MAX
WAIT_K = 1.3
WAIT_ADD = 0.8
WAIT_MIN = 2.0
WAIT_MAX = 6.0
DONE_K = 0.5  # 以 ？！ 結尾或很長：像是說完了
MORE_K = 1.5  # 很短、或以 ，、… 結尾：明顯還有下文
MORE_MAX = 9.0
MAX_LISTEN = 15.0  # 從第一條算起最多等這麼久，一直在打也先回

# 停頓算「比平時久很多」：超過平時間隔的 SLOW_K 倍，而且至少多 SLOW_ADD 秒
SLOW_K = 3.0
SLOW_ADD = 4.0

UNFINISHED_RE = re.compile(
    r"(?:…|\.\.\.|。。|，|,|、|——)\s*$"
    r"|(?:但是|可是|然后|因为|所以|而且|如果|其实|的话|就是|那个|结果|我妈妈?她|我爸爸?他)\s*$"
)
DONE_RE = re.compile(r"[？?！!]\s*$|[哈嘿呵]{2,}\s*$")
# 沉默追問只在聊到難受的事時才考慮（關鍵詞只是篩一下，要不要說交給模型）
HEAVY_RE = re.compile(
    r"难受|难过|伤心|想哭|哭了|在哭|崩溃|撑不住|受不了|绝望|不想活|活着没意思|去世|走了|离开了我|没了|"
    r"分手|离婚|吵架|被骂|被打|失业|裁员|挂科|生病|住院|医院|手术|好累|累死|心累|烦死|好烦|委屈|"
    r"害怕|孤独|孤单|失眠|睡不着|怎么办|对不起|算了|唉|哎|呜呜"
)


def looks_unfinished(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and bool(UNFINISHED_RE.search(t))


def looks_heavy(text: str) -> bool:
    return bool(HEAVY_RE.search(text or ""))


class Rhythm:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.people: dict[str, dict] = {}
        self.last_msg: dict[tuple[str, str], float] = {}  # (umo, qq) -> 時間
        self.bot_sent: dict[str, float] = {}  # umo -> 〈我〉最後說話的時間
        self._dirty, self._saved = False, time.monotonic()
        try:
            data = json.loads(self.path.read_text("utf-8"))
            if isinstance(data, dict):
                self.people = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            pass

    # ---------- 記 ----------
    def on_message(self, umo: str, qq: str, now: float | None = None, dm: bool = False) -> float | None:
        """記一條消息；返回和這個人上一條的間隔（第一次見到返回 None）"""
        if not qq:
            return None
        now = time.time() if now is None else now
        key = (umo, qq)
        prev = self.last_msg.get(key)
        self.last_msg[key] = now
        p = self.people.setdefault(qq, {})
        gap = None
        if prev is not None:
            gap = now - prev
            if BURST_MIN <= gap <= BURST_MAX:
                p["g"] = (p.get("g") or [])[-(KEEP_GAPS - 1):] + [round(gap, 2)]
                self._dirty = True
        sent = self.bot_sent.get(umo)
        # 私聊裡〈我〉說完、TA 這是第一句回話
        if dm and sent and (prev is None or prev < sent) and 0 < now - sent <= LAG_MAX:
            p["l"] = (p.get("l") or [])[-(KEEP_LAGS - 1):] + [round(now - sent, 1)]
            self._dirty = True
        self.maybe_save()
        return gap

    def on_bot_sent(self, umo: str, now: float | None = None):
        self.bot_sent[umo] = time.time() if now is None else now

    def maybe_save(self, force: bool = False):
        if not self._dirty or (not force and time.monotonic() - self._saved < SAVE_EVERY):
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.people, ensure_ascii=False), "utf-8")
            tmp.replace(self.path)
            self._dirty, self._saved = False, time.monotonic()
        except Exception:
            pass

    # ---------- 讀 ----------
    def gap(self, qq: str) -> tuple[float, bool]:
        """(這個人平時連發的間隔, 是不是按 TA 自己的樣本算的)"""
        g = (self.people.get(qq) or {}).get("g") or []
        if len(g) < MIN_GAPS:
            return DEFAULT_GAP, False
        return float(statistics.median(g)), True

    def lag(self, qq: str) -> tuple[float, bool]:
        lg = (self.people.get(qq) or {}).get("l") or []
        if len(lg) < MIN_LAGS:
            return DEFAULT_LAG, False
        return float(statistics.median(lg)), True

    def wait_for(self, qq: str, text: str) -> float:
        """收到這條之後再等多久看還有沒有下文"""
        typ, _ = self.gap(qq)
        base = min(WAIT_MAX, max(WAIT_MIN, typ * WAIT_K + WAIT_ADD))
        t = (text or "").strip()
        if DONE_RE.search(t) or len(t) >= 30:
            return max(1.0, base * DONE_K)
        if len(t) <= 5 or looks_unfinished(t):
            return min(MORE_MAX, base * MORE_K)
        return base

    def is_slow(self, qq: str, pause: float) -> bool:
        typ, _ = self.gap(qq)
        return pause >= max(typ * SLOW_K, typ + SLOW_ADD)

    def silence_after(self, qq: str, k: float, lo: float, hi: float) -> float:
        """私聊裡〈我〉說完後，TA 多久沒回算「好久沒說話」"""
        lag, _ = self.lag(qq)
        return min(hi, max(lo, lag * k))


# ---------- 給模型的話 ----------
MERGED_HINT = "（TA 连着发了 {n} 条，上面已经合在一起：当成一段话，回一次就好，别一条条分开回）"
SLOW_HINT = "（TA 说完「{prev}」停了 {secs} 秒才接着说{usual}）"
UNFINISHED_HINT = (
    "（TA 最后那句像是没说完，之后 {secs} 秒都没再打字{usual}。可能是在犹豫、难受得说不下去，也可能只是去忙了）"
)
NAME_ONLY_HINT = "（TA 只喊了你一声，等了 {secs} 秒也没说别的）"
USUAL = "，TA 平时连着发大约隔 {typ} 秒"

SILENCE_SYSTEM = (
    "\n\n[现在不是在回谁的新消息] 下面是你和 TA 最近的私聊。你回完最后一句之后，TA 已经 {secs} 没说话了"
    "{usual}。刚才聊的事可能让 TA 不太好受。像真人朋友一样判断要不要再说一句：TA 可能说不下去了、"
    "在哭、在忙、或者只是睡了。想追问就追问，想安慰就安慰，觉得这时候该安静陪着、不打扰，就只输出「不说」。"
    "要说就只输出要发的那一两句话，用你平时的口吻和自称，不要解释、不要加括号说明、不要提「系统」「沉默」这些词。"
)
SILENCE_USUAL = "（TA 平时回你大约 {lag}）"
SILENCE_NOTE = "（系统记录：TA 上一句之后 {secs} 没说话，〈我〉又主动说了一句）"
SKIP_WORDS = ("不说", "（不说）", "[不说]", "不打扰", "")


def fmt_secs(secs: float) -> str:
    secs = int(round(secs))
    if secs < 90:
        return f"{secs} 秒"
    if secs < 3600:
        return f"{round(secs / 60)} 分钟"
    return f"{secs / 3600:.1f} 小时"


def pause_hints(rhythm: Rhythm, qq: str, pieces: list[tuple[float, str]], end: float, bot_name: str = "") -> list[str]:
    """傾聽結束時給模型的提醒：pieces 是 (時間, 文字)，end 是傾聽結束的時間"""
    out = []
    texts = [t for _, t in pieces]
    if len(pieces) >= 2:
        out.append(MERGED_HINT.format(n=len(pieces)))
    typ, known = rhythm.gap(qq)
    usual = USUAL.format(typ=f"{typ:.0f}" if typ >= 1.5 else f"{typ:.1f}") if known else ""
    for (t0, a), (t1, _b) in zip(pieces, pieces[1:]):
        if rhythm.is_slow(qq, t1 - t0):
            prev = re.sub(r"\s+", " ", a).strip()
            prev = prev if len(prev) <= 12 else prev[:12] + "…"
            out.append(SLOW_HINT.format(prev=prev, secs=round(t1 - t0), usual=usual))
    last = (texts[-1] if texts else "").strip()
    silence = round(end - pieces[-1][0]) if pieces else 0
    name = (bot_name or "").strip()
    if name and re.fullmatch(rf"{re.escape(name)}[呢呀啊吗嘛哦喔～~！!？?。.\s]*", last) and len(pieces) == 1:
        out.append(NAME_ONLY_HINT.format(secs=silence))
    elif looks_unfinished(last):
        out.append(UNFINISHED_HINT.format(secs=silence, usual=usual))
    return out
