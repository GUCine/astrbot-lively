"""回味連不上模型時退避（bond digest.py，10-29）：先等一分鐘、越等越久，等完還不通這一輪就停；
斷網不算那條記憶回味失敗（不會被當壞記憶跳過）；通了從頭算；模型回錯、慢照舊算失敗。

/usr/local/bin/python3 tests/test_digest_backoff.py（號碼都是假的）
"""
import asyncio, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和 bond

dg = tr.dg


class APIConnectionError(Exception):
    pass


slept = []


async def fake_sleep(t):
    slept.append(t)
dg.asyncio.sleep = fake_sleep


def make(results):
    d = dg.Digest.__new__(dg.Digest)
    d._fails, d._net_level, d.calls = {}, 0, 0
    async def ask(prompt, system):
        d.calls += 1
        r = results.pop(0) if results else {"片段": []}
        if isinstance(r, BaseException):
            raise r
        return r
    d._ask = ask
    return d


net = APIConnectionError("Connection error.")
# 判斷
assert dg.net_error(net)
assert dg.net_error(ConnectionResetError())
wrapped = RuntimeError("x"); wrapped.__cause__ = net
assert dg.net_error(wrapped)
assert not dg.net_error(asyncio.TimeoutError())
assert not dg.net_error(RuntimeError("模型没给出 JSON"))

# 斷一會兒又通：等 60、120 再試，通了歸零
slept.clear()
d = make([net, net, {"ok": 1}])
assert asyncio.run(d._ask_net("p", "s")) == {"ok": 1}
assert slept == [60, 120] and d._net_level == 0 and d.calls == 3

# 一直不通：60、120、300、600 都等過，拋 NetDown；之後同一輪不再等
slept.clear()
d = make([net] * 10)
try:
    asyncio.run(d._ask_net("p", "s")); raise AssertionError("該拋 NetDown")
except dg.NetDown:
    pass
assert slept == list(dg.NET_WAITS) and d.calls == 5
slept.clear()
try:
    asyncio.run(d._ask_net("p", "s")); raise AssertionError
except dg.NetDown:
    pass
assert slept == [] and d.calls == 6  # 下一輪只試一次

# 模型自己出錯不等、照拋
slept.clear()
d = make([RuntimeError("坏了")])
try:
    asyncio.run(d._ask_net("p", "s")); raise AssertionError
except RuntimeError as e:
    assert str(e) == "坏了"
assert slept == []

# digest()：斷網時這輪停下、不記失敗次數、不跳過記憶
marked = []
d = make([net] * 10)
d._net_level = len(dg.NET_WAITS)  # 已經等過一輪了
d.s = types.SimpleNamespace(get=lambda k, dflt=None: False)
d.group = None
docs = [{"doc_id": str(i)} for i in range(12)]
d._pending_docs = lambda limit: docs
d._batches = lambda ds: [ds[i:i + 6] for i in range(0, len(ds), 6)]
d._batch_prompt = lambda b: "p"
d.heart = types.SimpleNamespace(mark_digested=lambda *a: marked.append(a), db=types.SimpleNamespace(commit=lambda: None))
for _ in range(5):
    n_docs, n_mom, fail = asyncio.run(d.digest())
    assert (n_docs, fail) == (0, 1), (n_docs, fail)
assert d.calls == 5 and marked == [] and d._fails == {}

# 模型回不出 JSON 三次照舊跳過
d = make([None] * 10)
d.s, d.group, d._pending_docs, d._batches, d._batch_prompt, d.heart = (
    types.SimpleNamespace(get=lambda k, dflt=None: False), None, lambda limit: docs[:6], lambda ds: [ds], lambda b: "p",
    types.SimpleNamespace(mark_digested=lambda *a: marked.append(a), db=types.SimpleNamespace(commit=lambda: None)))
for _ in range(3):
    asyncio.run(d.digest())
assert len(marked) == 6 and all(m[1] == -1 for m in marked)

# update_hearts、pick_memories：斷網時停下
d = make([net] * 10)
d._net_level = len(dg.NET_WAITS)
d._due_hearts = lambda: ["10001", "10002", "10003"]
d._heart_material = lambda qq: "m"
assert asyncio.run(d.update_hearts()) == (0, 1) and d.calls == 1
d.memories_due = lambda: ["10001", "10002"]
d._memory_material = lambda qq: "m"
d.bond = types.SimpleNamespace(db=types.SimpleNamespace(commit=lambda: None))
assert asyncio.run(d.pick_memories()) == (0, 1) and d.calls == 2
print("ok")
