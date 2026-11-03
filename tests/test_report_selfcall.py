"""日報的自稱檢查：私聊裡〈我〉提到自己時一半以上只說「我」才點名。stub 掉 astrbot 直接跑。

python3 tests/test_report_selfcall.py（號碼都是假的）
"""
import importlib, sys, types
from pathlib import Path


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
flt = types.SimpleNamespace(command=deco, event_message_type=deco, EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.star", Context=object, Star=object, register=deco, StarTools=object)
mod("astrbot.core"); mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: "/tmp")
mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=object)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
r = importlib.import_module("astrbot_plugin_lively_report.main")

fails = 0
def check(name, ok):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name)

A, B, C = "x:FriendMessage:20001", "x:FriendMessage:20002", "x:FriendMessage:20003"
rows = (
    [(A, "assistant", "我吃不着呀，你就当替我吃了")] * 5 + [(A, "assistant", "本鱼等着看你几点起")]
    + [(A, "user", "我做好饭啦")] * 9  # 對方說的「我」不算
    + [(B, "assistant", "本鱼在呢")] * 4 + [(B, "assistant", "我也是")] * 2  # 一半以下
    + [(C, "assistant", "我我我")] * 3  # 提到自己不到 4 句
    + [(B, "assistant", "我们一起去吧")] * 5  # 「我们」不算提到自己
)
got = dict((s, (a, b)) for s, a, b in r.self_call_drift(rows, ("本鱼", "小肥鱼")))
check("一半以上只说我的私聊会点名", got.get(A) == (5, 6))
check("一半以下不点名", B not in got)
check("太少不点名", C not in got)
check("对方说的我不算", got.get(A, (0, 0))[1] == 6)
check("小肥鱼也算自称", r.self_call_drift([(A, "assistant", "小肥鱼来啦，我在")] * 5, ("本鱼", "小肥鱼")) == [])
check("没有走样就没有提醒行", r.LivelyReport.drift_line([]) == "")
check("提醒行带名字和句数", "开摆（5/6 句）" in r.LivelyReport.drift_line(["开摆（5/6 句）"]))
print(f"\n{7 - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
