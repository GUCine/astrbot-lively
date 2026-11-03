"""群漫畫：說到群漫畫、記事本裡有群漫畫時給她的實際做法（comic_brief）；畫圖回傳寫照誰的什麼畫的（_people_note）（10-29）。
起因 10-29 20:50 主人私聊：她記成「九点前把群漫端给爹爹」、以為要自己動手畫；20:56 照 fuyu 的定做形象畫對了金髮，她以為畫錯。

/usr/local/bin/python3 tests/test_comic_brief.py（號碼都是假的：10001 主人、20001 群、30001 祈、30002 西瓜头）
"""
import json, sys, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_comic_made as tm  # noqa: E402  借它 stub 好的 astrbot

cm, G = tm.cm, tm.G
c = tm.new()
c.s.groups = lambda: [G, "20002"]
tm.S.conf = {"comic_prep_min": 30}
c.comic_at = "22:00"
c.state.update({"off_groups": [], "last_day": {}})
c.events_file.write_text("", "utf-8")
F = lambda t: str(t).replace("〈我〉", "本鱼")
b = F(c.comic_brief())
assert "程序自己画的，不用本鱼动手，也不是交给谁" in b and "21:30 开始" in b and "22:00 照顺序发到各自的群里" in b, b
assert "「测试群」" in b and "「第二群」" in b and G not in b, b  # 不寫群號
assert "先交给本鱼看一眼" in b
# 今天各群到哪一步
c.state["inflight"] = {G: {"gid": G}}
day = c._day_of(0)
with c.events_file.open("a", encoding="utf-8") as f:
    f.write(json.dumps({"kind": "sent", "group": "20002", "auto": True, "day": day, "ts": time.time()}) + "\n")
b = F(c.comic_brief())
assert "「测试群」正在画" in b and "「第二群」" in b and "发了" in b, b
c.state["enabled"] = False
assert "关着" in c.comic_brief()
c.state["enabled"] = True
c.state["off_groups"] = [G, "20002"]
assert "没有开着的群" in c.comic_brief()

# 畫圖回傳：照定做形象畫的寫長相，照 QQ 頭像畫的照實說看不到
c.s.fill = lambda t: str(t).replace("〈我〉", "本鱼").replace("〈主人〉", "爹爹")
note = c._people_note({"people": [{"qq": tm.QI, "call": "祈", "made": {"desc": tm.DESC}},
                                  {"qq": tm.XG, "call": "西瓜头", "made": None}]})
assert note.startswith("（参考图：祈照 TA 定做的形象画的（亮草绿的长碎发") and "西瓜头照 TA 的 QQ 头像画的（头像本鱼这里看不到）" in note, note
assert c._people_note({"people": []}) == "" and c._people_note({}) == ""
print("test_comic_brief ok")
