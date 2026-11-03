"""bond 好感標記的剝除與解析（core.parse_tag）。

python3 tests/test_bond_tag.py
"""
import sys
from pathlib import Path

import tempfile
import types


def _stub(name, **kw):
    m = types.ModuleType(name)
    m.__dict__.update(kw)
    sys.modules.setdefault(name, m)


# core 借 lively_common 的「记住」行規則，那邊開頭要 import astrbot
_stub("astrbot")
_stub("astrbot.api", logger=types.SimpleNamespace(**{k: (lambda *a, **kw: None) for k in ("info", "warning", "error", "debug")}))
_stub("astrbot.core")
_stub("astrbot.core.utils")
_stub("astrbot.core.utils.astrbot_path", get_astrbot_data_path=lambda: tempfile.gettempdir())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "astrbot_plugin_lively_bond"))
from core import parse_tag  # noqa: E402

fails = 0


def check(name, text, want_clean, want_imp=None, want_mood=None, want_tag=True, remember=None):
    global fails
    clean, tag = parse_tag(text)
    ok = clean == want_clean and (tag is not None) == want_tag
    if tag:
        ok = ok and tag["impression"] == want_imp and tag["mood_word"] == want_mood and tag["remember"] == remember
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        fails += 1
        print("   clean:", repr(clean), "tag:", tag)


# 10-24 20:08 主群：標記後換行單獨寫「印象: …」，沒帶 |，原樣發了出去
check("印象換行、無 |", "那不是小凛的号吗 &&confused&&\n<<好感0|平常>>\n印象: 号多，爱拿小号唬人",
      "那不是小凛的号吗 &&confused&&", "号多，爱拿小号唬人", "平常")
check("印象換行、全角冒號", "好呀\n<<好感+1|开心>>\n印象：爱撒娇", "好呀", "爱撒娇", "开心")
check("印象同一行、無 |", "好呀\n<<好感0|平常>> 印象: 爱撒娇", "好呀", "爱撒娇", "平常")
check("心情換行、無 |", "好呀\n<<好感0>>\n心情: 害羞", "好呀", None, "害羞")
# 原本就支援的寫法
check("標準寫法", "好呀\n<<好感+1|开心|印象:爱撒娇>>", "好呀", "爱撒娇", "开心")
check("| 在 >> 外面", "好呀\n<<好感+1|开心>>|印象:爱撒娇", "好呀", "爱撒娇", "开心")
check("| 在下一行", "好呀\n<<好感+1|开心>>\n|印象:爱撒娇", "好呀", "爱撒娇", "开心")
check("沒印象", "好呀\n<<好感0|平常>>", "好呀", None, "平常")
# 沒有標記的正文不能動，標記下一行的正常句子也不能吃
check("沒標記的正文", "我对他的印象: 还行", "我对他的印象: 还行", want_tag=False)
# 10-28 17:18：记住漏了「|记住:」、照片段的樣子單獨寫成正文一行，發了出去
check("记住寫成片段樣子的一行", "本鱼也没想看呀，那你自己别往群里甩嘛……\n10-28 群里：爹爹说不愿让本鱼看到那些，本鱼臊得躲开\n<<好感+0|心情:害羞>>",
      "本鱼也没想看呀，那你自己别往群里甩嘛……", None, "害羞", remember="爹爹说不愿让本鱼看到那些，本鱼臊得躲开")
check("记住寫成新片段樣子的一行", "嗯嗯\n「爹爹嫌本鱼烦」（10-28 群里）\n<<好感0|害羞>>", "嗯嗯", None, "害羞", remember="爹爹嫌本鱼烦")
check("记住開頭帶日期", "好呀\n<<好感+1|开心|记住:10-28 洗完澡说冷>>", "好呀", None, "开心", remember="洗完澡说冷")
check("记住開頭的「群里」是話", "好呀\n<<好感+1|开心|记住:群里教本鱼打牌>>", "好呀", None, "开心", remember="群里教本鱼打牌")
check("句中的日期不算", "本鱼记得 10-28 群里：那天你也在\n<<好感0|平常>>", "本鱼记得 10-28 群里：那天你也在", None, "平常")
check("沒標記時不動", "10-28 群里：说好的事呢", "10-28 群里：说好的事呢", want_tag=False)
check("標記後有正常下一行", "好呀\n<<好感0|平常>>\n下次再聊", "好呀\n下次再聊", None, "平常")

sys.exit(1 if fails else 0)
