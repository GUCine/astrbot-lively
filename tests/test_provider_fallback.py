"""背景活的模型出錯改用備用（10-31，lively_common Settings.provider 的 fallback_<key>）。python3 tests/test_provider_fallback.py"""
import asyncio, sys
from pathlib import Path
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_beat_via_chat  # noqa: F401  stub 好 astrbot
import importlib
lc = importlib.import_module("astrbot_plugin_lively_bond.lively_common")

class Prov:
    def __init__(self, name, fail=False): self.name, self.fail, self.calls = name, fail, 0
    async def text_chat(self, **kw):
        self.calls += 1
        if self.fail: raise RuntimeError("网关断了")
        return self.name
    def meta(self): return self.name
wb, ds = Prov("wb", fail=True), Prov("ds")
class Ctx:
    def get_provider_by_id(self, pid): return {"wb": wb, "ds": ds}.get(pid)
    def get_using_provider(self): return ds
s = object.__new__(lc.Settings)
s.context = Ctx()
conf = {"provider_id": "wb", "fallback_provider_id": "ds"}
s.get = lambda k, d=None: conf.get(k, d)
p = s.provider()
assert asyncio.run(p.text_chat(prompt="x")) == "ds" and wb.calls == 1 and p.meta() == "wb"
wb.fail = False
assert asyncio.run(p.text_chat(prompt="x")) == "wb"
conf.pop("fallback_provider_id")
assert s.provider() is wb  # 沒填備用：照舊回原本的
print("provider fallback ok")
