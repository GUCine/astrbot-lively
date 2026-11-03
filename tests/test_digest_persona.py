"""回味帶上人設和主人定的規矩（bond digest.py，10-26）：人設原文放在提示詞最前面、規矩接在後面，每次現讀；關掉或讀不到人設照舊。

/usr/local/bin/python3 tests/test_digest_persona.py（號碼都是假的）
"""
import asyncio, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和 bond

dg = tr.dg
PERSONA = "你是小肥鱼，一条爱吃白饭的鲸鱼娘。{这里有花括号也不能坏}"
RULES = ["有人要印象卡时发不发由〈我〉自己决定", "〈主人〉在私聊里试功能是那一次的事"]


class Ctx:
    def __init__(self, cfg): self.cfg = cfg
    def get_registered_star(self, name):
        if name != dg.EVOLVE_PLUGIN or self.cfg is None:
            return None
        return types.SimpleNamespace(config=self.cfg)


class S:
    def __init__(self, persona=PERSONA, on=True, evolve=None):
        self.persona, self.on, self.context, self.sent = persona, on, Ctx(evolve), []
    def get(self, k, d=None): return self.on if k == "digest_persona" else d
    def persona_prompt(self): return self.persona
    def fill(self, t): return t.replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
    def provider(self):
        me = self
        class P:
            async def text_chat(self, prompt, system_prompt):
                me.sent.append(system_prompt)
                return types.SimpleNamespace(completion_text='{"片段": []}')
        return P()


def digest_with(s):
    d = dg.Digest.__new__(dg.Digest)
    d.s = s
    return d


# 人設在最前面、規矩接在後面、最後才是回味自己的規則
s = S(evolve={"owner_rules": RULES + ["  "]})
d = digest_with(s)
t = d.self_text()
assert t.index("人设（最新的") < t.index(PERSONA) < t.index("〈主人〉定的规矩") < t.index(RULES[0]), t
assert t.count("\n- ") == 2 and t.endswith("---\n\n"), t
assert asyncio.run(d._ask("记忆", dg.HEART_RULE)) == {"片段": []}
sent = s.sent[-1]
assert sent.startswith("下面是本鱼自己的人设") and PERSONA in sent and sent.index(PERSONA) < sent.index("在整理自己心里对一个人的样子"), sent
assert "爹爹在私聊里试功能" in sent  # 規矩裡的〈主人〉也換掉了
# 兩種回味開頭一樣（前綴快取能共用）
asyncio.run(d._ask("记忆", dg.DIGEST_RULE.format(feelings="开心", kinds="日常")))
head = sent[:sent.index("---") + 3]
assert s.sent[-1].startswith(head)
# 每次現讀：人設、規矩改了下一次就是新的
s.persona = "你是小肥鱼（改过的人设）"
s.context.cfg["owner_rules"] = []
t = d.self_text()
assert "改过的人设" in t and "〈主人〉定的规矩" not in t, t
# evolve 沒裝：只有人設
assert "规矩" not in digest_with(S(evolve=None)).self_text().split("人设（最新的")[1]
# 關掉、讀不到人設：照舊只用規則
for s2 in (S(on=False), S(persona=""), S(persona=None)):
    d2 = digest_with(s2)
    assert d2.self_text() == ""
    asyncio.run(d2._ask("记忆", dg.HEART_RULE))
    assert s2.sent[-1] == s2.fill(dg.HEART_RULE)
print("digest persona ok")
