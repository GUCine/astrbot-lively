"""群漫畫取話題照 QQ 號認〈我〉（10-31）：群分析插件按 bot_self_ids 把〈我〉說的整段濾掉，群裡另一個叫「大肥鱼还在吃白饭」的號
就被畫成主人在跟它聊；話題描述裡的 [QQ號] 分鏡那邊也沒換成名字。
/usr/local/bin/python3 tests/test_comic_me.py（號碼都是假的：10001 主人、50001 她、60001 大肥鱼）"""
import asyncio, json, sys, types
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_made as tm  # noqa: E402  借它的假 astrbot
cm = tm.cm
ME, BIG = "50001", "60001"
tm.S.bot_qq = lambda self: ME

c = tm.new()
legacy = [{"sender": {"user_id": tm.OWNER, "nickname": "陈", "card": "小兔崽崽"}, "message": [{"type": "text", "data": {"text": f"@{ME} 你还记得吗"}}]},
          {"sender": {"user_id": ME, "nickname": "小肥鱼", "card": "小肥鱼"}, "message": [{"type": "text", "data": {"text": "本鱼只记得三天内的"}}]},
          {"sender": {"user_id": BIG, "nickname": "大肥鱼还在吃白饭", "card": ""}, "message": [{"type": "text", "data": {"text": "我也是肥鱼"}}]}]
out = c._mark_me(json.loads(json.dumps(legacy)), ME)
assert out[1]["sender"] == {"user_id": cm.ME_ID, "nickname": "本鱼", "card": "本鱼"}, out[1]
assert out[0]["message"][0]["data"]["text"] == f"@{cm.ME_ID} 你还记得吗"
assert out[2]["sender"]["user_id"] == BIG  # 名字里有「肥鱼」的别人不动

t = {"topic": "七天前", "contributors": ["小兔崽崽", "本鱼", "大肥鱼还在吃白饭"], "contributor_ids": [tm.OWNER, cm.ME_ID, BIG],
     "detail": f"[{tm.OWNER}] 问 [{cm.ME_ID}] 还记不记得，[{BIG}] 插了一句，[{ME}] 说只记得三天"}
assert c._named(t, {tm.OWNER: "陈"}) == "陈 问 本鱼 还记不记得，大肥鱼还在吃白饭 插了一句，本鱼 说只记得三天", c._named(t, {tm.OWNER: "陈"})

cast = c._cast([t], {tm.OWNER: [3, "小兔崽崽"], ME: [2, "小肥鱼"], BIG: [1, "大肥鱼还在吃白饭"]})
assert [x["qq"] for x in cast] == [tm.OWNER, BIG], cast  # 〈我〉不进出场名单

class SBProv:
    seen = None
    async def text_chat(self, prompt, system_prompt):
        SBProv.seen = prompt
        return types.SimpleNamespace(completion_text=json.dumps({"cast": [], "strips": [{"title": "x", "topic": "x", "panels": [
            {"scene": "x", "who": [], "me": True, "lines": [], "caption": ""}] * 3}]}, ensure_ascii=False))
tm.S.provider = lambda self, key="provider_id": SBProv()
asyncio.run(c._storyboard([t], [{"qq": tm.OWNER, "call": "陈", "name": "小兔崽崽", "n": 3}]))
assert "- 七天前（陈、本鱼）：陈 问 本鱼 还记不记得，大肥鱼还在吃白饭 插了一句" in SBProv.seen, SBProv.seen
print("comic me ok")
