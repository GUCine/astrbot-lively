"""她自己發語音（voice lively_voice，10-29）：工具能用才看得到；念不出來的去掉；合成失敗、太長、到上限照實回、什麼都不發；
NapCat 報 1200 Timeout 當作發出去了；不再按機率把回覆換成語音。

/usr/local/bin/python3 tests/test_voice_tool.py（號碼都是假的：10001 主人、20001 群友、30001 群）
"""
import asyncio, importlib, json, sys, tempfile, types
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="voice_tool_test_"))


def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class L:
    def __getattr__(self, k): return lambda *a, **k2: None
def deco(*a, **k): return lambda f: f
class Star:
    def __init__(self, context=None): self.context = context
class Record:
    def __init__(self, b): self.b = b
    @classmethod
    def fromBase64(cls, b): return cls(b)
class MessageChain:
    def __init__(self, chain=None): self.chain = chain or []
    def message(self, t): self.chain.append(t); return self
flt = types.SimpleNamespace(event_message_type=deco, on_llm_request=deco, llm_tool=deco,
                            EventMessageType=types.SimpleNamespace(ALL=0, PRIVATE_MESSAGE=1))
mod("astrbot"); mod("astrbot.api", logger=L(), AstrBotConfig=dict)
mod("astrbot.api.event", AstrMessageEvent=object, filter=flt)
mod("astrbot.api.message_components", Record=Record, Plain=object)
mod("astrbot.api.star", Context=object, Star=Star, register=deco,
    StarTools=types.SimpleNamespace(get_data_dir=lambda name: str(TMP / name)))
mod("astrbot.core"); mod("astrbot.core.message"); mod("astrbot.core.message.message_event_result", MessageChain=MessageChain)
mod("astrbot.core.utils"); mod("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: str(TMP))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
vm = importlib.import_module("astrbot_plugin_lively_voice.main")
notes = []
vm.note_outbox = lambda umo, text, kind="": notes.append((umo, text, kind))
fails = []


def check(name, ok, got=None):
    print(("ok  " if ok else "FAIL"), name, "" if ok else f"→ {got!r}")
    if not ok:
        fails.append(name)


class Ev:
    def __init__(self, qq="20001", gid="30001", send_err=None):
        self.qq, self.gid, self.sent, self.send_err = qq, gid, [], send_err
        self.unified_msg_origin = f"napcat_onebot:GroupMessage:{gid}" if gid else f"napcat_onebot:FriendMessage:{qq}"
    def get_sender_id(self): return self.qq
    def get_group_id(self): return self.gid
    async def send(self, chain):
        if self.send_err:
            raise RuntimeError(self.send_err)
        self.sent.append(chain)


class Tools:
    def __init__(self): self.names = {"lively_voice", "other"}
    def get_tool(self, n): return n in self.names
    def remove_tool(self, n): self.names.discard(n)


(TMP / "astrbot_plugin_lively_voice").mkdir(parents=True, exist_ok=True)
p = vm.LivelyVoice(context=None, config={})
p.s.get = lambda k, d=None: {"breeze_key": "brz_x", "breeze_voice_cute": "voc_a"}.get(k, d)
calls = []


async def fake_tts(text, style="cute", tone=""):
    calls.append((text, style, tone))
    return b"mp3" * 500, 4.2
p.tts = fake_tts


async def main():
    # 念不出來的去掉
    check("去掉表情动作链接标签", vm.speakable("嘿嘿（摆尾巴）😄 &&happy&& 看 https://x.cn/a 这个") == "嘿嘿，看，这个",
          vm.speakable("嘿嘿（摆尾巴）😄 &&happy&& 看 https://x.cn/a 这个"))
    check("全是表情就空", vm.speakable("😄😄（＾ω＾）") == "", vm.speakable("😄😄（＾ω＾）"))

    # 開著：工具留著；關了拿掉
    req = types.SimpleNamespace(func_tool=Tools())
    await p.hide_voice_tool(Ev(), req)
    check("开着工具在", req.func_tool.get_tool("lively_voice"))
    p.state["enabled"] = False
    req = types.SimpleNamespace(func_tool=Tools())
    await p.hide_voice_tool(Ev(), req)
    check("关了工具拿掉", not req.func_tool.get_tool("lively_voice") and req.func_tool.get_tool("other"))
    r = await p.tool_voice(Ev(), text="你好")
    check("关着叫了不发", r.startswith("没发：语音关着") and not calls, r)
    p.state["enabled"] = True

    # 正常發：群友叫的也行
    ev = Ev()
    r = await p.tool_voice(ev, text="本鱼来啦（转圈）", style="可爱")
    check("发了", "语音发出去了" in r and "「本鱼来啦」" in r and len(ev.sent) == 1, r)
    check("发的是语音", isinstance(ev.sent[0].chain[0], Record))
    check("合成拿到的字和声线", calls[-1] == ("本鱼来啦", "cute", ""), calls[-1])
    check("回传说后面的字另外发", "另外作为文字发出去" in r, r)
    r = await p.tool_voice(Ev(gid=""), text="晚安", style="gentle")
    check("私聊温柔", "温柔" in r and calls[-1] == ("晚安", "gentle", ""), r)
    ev_lines = [json.loads(x) for x in (TMP / "astrbot_plugin_lively_voice" / "events.jsonl").read_text().splitlines()]
    check("记成 said（不是 sent，evolve 不拿它调概率）", [e["kind"] for e in ev_lines] == ["said", "said"], ev_lines)

    # 不對的
    r = await p.tool_voice(Ev(), text="嗯", style="sad")
    check("声线不对", r.startswith("没发：style"), r)
    r = await p.tool_voice(Ev(), text="😄（摆尾巴）")
    check("没字能念", r.startswith("没发：这句去掉"), r)
    r = await p.tool_voice(Ev(), text="啊" * 301)
    check("太长", "最多念 300 字" in r, r)
    r = await p.tool_voice(Ev(), text="啊" * 300)
    check("300 字能发", "语音发出去了" in r, r)

    # 合成太久：轉背景，好了自己發、記 outbox
    async def slow_tts(text, style="cute", tone=""):
        await asyncio.sleep(0.3)
        return b"mp3" * 500, 70.0
    p.tts, vm.WAIT = slow_tts, 0.1
    ev = Ev()
    r = await p.tool_voice(ev, text="很长的一段")
    check("超时先回还在合成", r.startswith("还在合成") and not ev.sent, r)
    await asyncio.sleep(0.5)
    check("背景合成好了自己发", len(ev.sent) == 1)
    check("结果记进 outbox", notes and "语音发出去了" in notes[-1][1] and notes[-1][2] == "后台:语音", notes)
    p.tts, vm.WAIT = fake_tts, 100

    # 合成失敗
    async def bad_tts(text, style="cute", tone=""):
        raise RuntimeError("语音那边回了 503：loading")
    p.tts = bad_tts
    ev = Ev()
    r = await p.tool_voice(ev, text="在吗")
    check("合成失败照实说、什么都没发", "没合成出来" in r and "503" in r and not ev.sent, r)
    p.tts = fake_tts

    # NapCat 1200 Timeout 當作發了；別的錯照實說
    n = p.state["count"]
    r = await p.tool_voice(Ev(send_err="retcode=1200 Timeout"), text="哼")
    check("超时当发了", "语音发出去了" in r and p.state["count"] == n + 1, r)
    r = await p.tool_voice(Ev(send_err="boom"), text="哼")
    check("别的发送错误", r.startswith("没发：发送时出错了"), r)

    # 一天上限
    p.state["count"] = vm.DAILY_MAX
    r = await p.tool_voice(Ev(), text="再来一条")
    check("到上限", "一天的上限" in r, r)
    p.state["count"] = 0

    # BreezeBlue（11-03）：沒密鑰、沒聲音拿掉；聲音標籤留著、別的方括號照剪；語氣帶過去
    for conf, name in (({}, "没密钥工具拿掉"), ({"breeze_key": "brz_x"}, "没选声音工具拿掉")):
        p.s.get = lambda k, d=None, c=conf: c.get(k, d)
        req = types.SimpleNamespace(func_tool=Tools())
        await p.hide_voice_tool(Ev(), req)
        check(name, not req.func_tool.get_tool("lively_voice"))
    p.s.get = lambda k, d=None: {"breeze_key": "brz_x", "breeze_voice_cute": "voc_a"}.get(k, d)
    req = types.SimpleNamespace(func_tool=Tools())
    await p.hide_voice_tool(Ev(), req)
    check("breeze 配好工具在", req.func_tool.get_tool("lively_voice"))
    check("breeze 每轮说一声有声音、怎么念", "lively_voice" in (req.system_prompt or "") and "tone" in req.system_prompt and "[叹气]" in req.system_prompt, getattr(req, "system_prompt", None))
    req2 = types.SimpleNamespace(func_tool=Tools(), system_prompt="人设")
    req2.func_tool.names.discard("lively_voice")
    await p.hide_voice_tool(Ev(), req2)
    check("别的插件拿掉了就不提", req2.system_prompt == "人设", req2.system_prompt)
    req3 = types.SimpleNamespace(func_tool=Tools(), system_prompt="人设")
    await p.hide_voice_tool(Ev(), req3); await p.hide_voice_tool(Ev(), req3)
    check("不重复加", req3.system_prompt.count("的声音]") == 1, req3.system_prompt)
    calls.clear()
    r = await p.tool_voice(Ev(), text="哼 [叹气] 好吧 [图片] [笑]", tone="  委屈地  ")
    check("标签留着、语气带过去", calls and calls[-1] == ("哼，[叹气]，好吧，[笑]", "cute", "委屈地"), calls)
    check("回传写了语气", "语气「委屈地」" in r, r)
    r = await p.tool_voice(Ev(), text="[笑]")
    check("只有标签不发", r.startswith("没发：这句去掉"), r)
    check("计费单位", vm.billable("你好[笑]") == 8 and vm.billable("hi") == 2)
    p.s.get = lambda k, d=None: {"breeze_key": "brz_x", "breeze_voice_cute": "voc_a"}.get(k, d)
    # 不再有按機率換成語音的鉤子；舊的 CosyVoice、MiniMax 兩條路下線了（11-03）
    check("没有 to_voice", not hasattr(p, "to_voice") and not hasattr(p, "mark_ask"))
    check("旧引擎拿掉了", not hasattr(p, "_minimax") and not hasattr(p, "engine")
          and "cosy" not in Path(vm.__file__).read_text("utf-8").split('"""', 2)[2].lower())


asyncio.run(main())
print("全部通过" if not fails else f"{len(fails)} 项没过：{fails}")
sys.exit(1 if fails else 0)
