"""情感插件回味改讀記憶插件（bond digest.py，11-01）：第一次改讀記下 LivingMemory 各處總結到哪、那以前的不再讀；
切換前沒回味完的總結照舊讀完、之後的總結不讀；段落讀完才把 mem_cursors 往前推（沒讀成的那段卡住後面的）；
只有〈我〉自己說話的段落跳過；設定改回 livingmemory 或記憶插件沒載入就讀 LivingMemory。
關係讀口帶圖上的線（ties）：私聊裡記的不帶。

/usr/local/bin/python3 tests/test_bond_from_memory.py（號碼都是假的）
"""
import asyncio, json, sqlite3, sys, tempfile, time
from pathlib import Path

sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relation as tr  # noqa: E402  借它 stub 好的 astrbot 和 bond

dg, core, heart, rel = tr.dg, tr.core, tr.heart, tr.rel
A, B, G = "20001", "20002", "30001"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("✗", name, extra)


class S:
    conf = {}
    def get(self, k, d=None): return self.conf.get(k, d)
    def bot_qq(self): return "10000"
    def groups(self): return [G]
    def fill(self, t): return t
    def me(self): return "本鱼"
    def persona_prompt(self): return ""


class Mem:
    def __init__(self, docs): self.docs, self.calls = docs, []
    def windows(self, cursors, floors, limit):
        self.calls.append((dict(cursors), dict(floors)))
        return [d for d in self.docs if d["last"] > int(cursors.get(d["place"]) or 0)][:limit]


now = time.time()
tmp = Path(tempfile.mkdtemp())
lm_dir = tmp / "astrbot_plugin_livingmemory"
lm_dir.mkdir()
lm = sqlite3.connect(lm_dir / "livingmemory.db")
lm.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY, doc_id TEXT, text TEXT, metadata TEXT)")
def lm_doc(doc_id, sid, created, who):
    meta = {"session_id": sid, "create_time": created,
            "participant_identities": [{"sender_id": who, "display_name": "泠·月"}]}
    lm.execute("INSERT INTO documents(doc_id, text, metadata) VALUES (?,?,?)", (doc_id, f"总结{doc_id}", json.dumps(meta)))
lm_doc("old-done", f"napcat:GroupMessage:{G}", now - 7200, A)
lm_doc("old-todo", f"napcat:FriendMessage:{A}", now - 3600, A)
lm.commit()

store = core.BondStore(str(tmp / "bond.db"))
hs = heart.HeartStore(store.db)
hs.mark_digested("old-done", 1); store.db.commit()
d = dg.Digest(S(), store, hs, tmp)
docs = [
    {"doc_id": f"tl:g:{G}:1-5", "place": f"g:{G}", "last": 5, "ts": now - 3000, "gid": G, "dm": "",
     "people": {A: "泠·月"}, "text": "10:00 泠·月：在吗\n10:01 〈我〉：在"},
    {"doc_id": f"tl:g:{G}:6-8", "place": f"g:{G}", "last": 8, "ts": now - 2000, "gid": G, "dm": "",
     "people": {}, "text": "10:30 〈我〉：没人理我"},
    {"doc_id": f"tl:p:{A}:9-12", "place": f"p:{A}", "last": 12, "ts": now - 1000, "gid": "", "dm": A,
     "people": {A: "泠·月"}, "text": "11:00 泠·月：晚安"},
]
mem = Mem(docs)
d.mem = lambda: mem
check("記憶插件在、設定預設：讀記憶插件", d.source() is mem)
pend = d._pending_docs(10)
floors = json.loads(store.get_meta("mem_floors"))
check("第一次改讀：記下各處 LivingMemory 總結到哪", floors == {f"g:{G}": now - 7200, f"p:{A}": now - 3600}
      and float(store.get_meta("mem_switch")) >= now, floors)
check("交給記憶插件的是那些時間", mem.calls[-1][1] == floors)
ids = [x["doc_id"] for x in pend]
check("切換前沒回味的總結照舊讀、記憶插件的段落接在後面、只有〈我〉說話的段落跳過",
      ids == ["old-todo", f"tl:g:{G}:1-5", f"tl:p:{A}:9-12"] and f"tl:g:{G}:6-8" in hs.digested_ids(), ids)
lm_doc("new-after", f"napcat:GroupMessage:{G}", time.time() + 5, A); lm.commit()
check("切換以後 LivingMemory 新寫的總結不讀", "new-after" not in [x["doc_id"] for x in d._pending_docs(10)])

prompt = d._batch_prompt([x for x in pend if x.get("place")][:1])
check("給模型看的是聊天原文", "聊天原文：\n10:00 泠·月：在吗" in prompt, prompt)

# 回味：群那段失敗、私聊那段成功 → 群卡在 0（只推到跳過的那段之前不行），私聊推到 12
answers = {"tl:p": {"片段": [{"记忆": 1, "qq": A, "事": "泠·月说晚安", "感受": "开心", "类型": "日常", "重要": 2}]}}
async def ask(prompt, system):
    if "晚安" in prompt and "在吗" not in prompt:
        return answers["tl:p"]
    if "总结old-todo" in prompt:
        return {"片段": []}
    raise RuntimeError("模型坏了")
d._ask_net = ask
dg.BATCH_DOCS = 1  # 一段一批，好分開成敗
n_docs, n_mom, nfail = asyncio.run(d.digest(10))
cur = json.loads(store.get_meta("mem_cursors") or "{}")
check("讀成的段落記片段", n_mom == 1 and hs.moments_by_ref(f"tl:p:{A}:9-12"), (n_docs, n_mom, nfail))
check("沒讀成的那段卡住那個地方，讀成的地方往前推", cur == {f"p:{A}": 12}, cur)
for _ in range(dg.MAX_FAILS):
    asyncio.run(d.digest(10))
cur = json.loads(store.get_meta("mem_cursors") or "{}")
check("連著失敗跳過以後照樣往前推（跳過的那段後面那段本來就讀過）", cur.get(f"g:{G}") == 8, cur)
check("推過的不再拿", not [x for x in d._pending_docs(10) if x.get("place")])

S.conf = {"digest_source": "livingmemory"}
check("設定改回 livingmemory：讀 LivingMemory", d.source() is None)
S.conf = {}
d.mem = lambda: None
check("記憶插件沒載入：讀 LivingMemory", d.source() is None)

# ---------- 關係讀口帶圖上的線 ----------
R = rel.Relations(store, hs)
store.on_talk(A, "泠·月", now)
class M2:
    def ties(self, qq):
        return [{"rel": "答应", "other": "me", "name": "小肥鱼", "out": True, "private": True},
                {"rel": "在玩", "other": "t:原神", "name": "原神", "out": True, "private": False},
                {"rel": "夸", "other": f"qq:{B}", "name": "布丁", "out": False, "private": False}]
R.mem = lambda: M2()
r = R.of(A)
check("of() 帶 ties", len(r["ties"]) == 3)
check("說話那句帶圖上的線、私聊裡記的不帶", "记忆里记着：TA在玩原神、布丁夸TA" in R.say(r) and "答应" not in R.say(r), R.say(r))
check("提到的人那句一樣不帶私聊的", "TA在玩原神" in R.say_about(r) and "答应" not in R.say_about(r))
check("全部人的列表不查線（省事）", all(x["ties"] == [] for x in R.all()))
R.mem = lambda: None
check("記憶插件沒載入：沒有線", R.of(A)["ties"] == [] and "记忆里记着" not in R.say(R.of(A)))

print(f"bond_from_memory: {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
