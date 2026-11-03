"""門禁：只放行配置裡的 QQ 群，私聊全部放行；群和私聊可以各用一個模型。

這個插件的配置也是整個套件的公共配置：主人、服務的群、機器人 QQ、名字、平台填在這裡，同套件的其他插件沒單獨填時都來這裡取。

機器人名字（bot_name）留空時不啟用「喊名字當 @」。

群聊背景改寫：AstrBot 自帶的群聊上下文塞進來的那一塊改成只留最近幾條、標明只是背景，最後寫清楚這輪要回的是誰說的哪句、有沒有叫它（rewrite_group_context）。

起草外洩（draft_guard，判斷在 lively_common）：模型把「怎麼回」的草稿、清單當成正文寫出來時，挑出真正要發的那句再交給分段回覆；挑不出來就請模型重寫一句，還不行就不發。

傾聽（listen_dm / listen_group）：被叫到後先等這個人說完，連發的幾條合成一條；等多久按這個人平時的節奏（rhythm.py）。
停得比平時久、話沒說完就沒下文，告訴模型停了多久；私聊聊到難受的事、〈我〉回完 TA 好久不說話，讓她決定要不要再說一句（silence_followup）。

聊天流程外發出去的話（lively_common 的 note_outbox）：好友申請、進了新群、日報這些通知不在對話歷史裡，
這個聊天下一輪問模型時把還沒看過的帶上，存進那輪的歷史。
心跳看手機時想在這個聊天說、卻沒發出去的（自主插件記的「没说出口」，10-26）另起一段，只說事實，回不回她自己定。
"""

import asyncio
import json
import random
import re
import sys
import time
import types
import uuid
from datetime import datetime

from astrbot.api import AstrBotConfig, logger, sp
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image, Plain, Reply
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart
from astrbot.core.message.message_event_result import MessageChain

from .lively_common import (
    FORWARD_LINES,
    FORWARD_NEST_DEPTH,
    FORWARD_NEST_LINES,
    forward_text,
    node_segs,
    BACKSTAGE_KIND, PLUGIN_DATA, Settings, _LONG_NUM_RE, _words_out, backstage, extract_final, id_list, looks_like_draft,
    note_outbox, pick_final, read_outbox,
)
from .updates import UPDATE_RULE, Updates, ann_text, day_of, facts_text
from .rhythm import (
    MAX_LISTEN, SILENCE_NOTE, SILENCE_SYSTEM, SILENCE_USUAL, SKIP_WORDS, Rhythm, fmt_secs, looks_heavy,
    looks_unfinished, pause_hints,
)

# 工具調用後的鉤子；測試裡 stub 的 filter 沒有這個，當成什麼都不做
_on_tool_respond = getattr(filter, "on_llm_tool_respond", None) or (lambda **k: (lambda f: f))

# AstrBot 存會話級模型偏好用的鍵（等同 ProviderManager.set_provider 寫入的鍵）
KEY = "provider_perf_chat_completion"

DATA_DIR = PLUGIN_DATA / "astrbot_plugin_lively_gate"

# 聊天流程外發出去的話：多久以內的還帶給她、一次最多帶幾條
OUTBOX_TTL = 12 * 3600
OUTBOX_MAX = 8
OUTBOX_HEAD = "（在 TA 这条消息之前，〈我〉这边自动发出过下面这些，都是〈我〉自己发的；TA 可能正接着这些在说，别说不知道）"
# 自主插件記的：心跳看手機時想在這個聊天說、被關卡擋下或發送失敗的（kind 是「没说出口:<同一件事的鍵>」）。
# 同一件事只帶最新的、最多 MISSED_MAX 條；放久了就不帶（想法過時了反而誤導）；後來說出去了（自主插件補的「:done」）就不帶
MISSED_KIND = "没说出口"
MISSED_HEAD = "（〈我〉看 QQ 时在这里想过、没说出口的，只有〈我〉自己知道）"
MISSED_TTL = 6 * 3600
MISSED_MAX = 3
# 心跳的心裡話寫了跟哪個群、哪個人有關（自主插件記的 kind「心里话」）：只帶最新那句、一小時內的，放在上面那塊一起（10-26，設計稿 B）
THOUGHT_KIND, THOUGHT_TTL = "心里话", 3600
# 插件記給〈我〉的後台事（kind「后台:…」）：沒發給誰，只是讓〈我〉知道（例如有人禁言了〈我〉、〈我〉沒私信主人說），
# 和「自动发出过」分開放，免得她以為自己說過
BACKSTAGE_HEAD = "（这段时间〈我〉这边后台发生的事，没发给谁，〈我〉知道就行）"
# 群裡剛跟 TA 說的，TA 轉到私聊時帶上（10-30：主人在桐群引用她的圖叫她做小凛群的版本，轉到私聊接著說，
# 私聊這邊不知道照哪張畫，把「之前那张」猜成小凛群以前的群漫畫，最後把 10-21 的舊漫畫轉進了小凛群）。
# 記 TA 叫〈我〉的那幾句、〈我〉在那個群回 TA 的、那段時間〈我〉在那個群用工具發的（outbox），存檔：重啟也接得上
THREAD_FILE = "group_threads.json"
THREAD_HOURS = 2  # TA 在群裡最後一次跟〈我〉說話多久以內，私聊才帶
THREAD_MAX = 16  # 一次最多帶幾句（連她調的工具）
THREAD_KEEP = 30  # 每人留幾句
THREAD_TEXT_MAX = 200
THREAD_HEAD = ("（TA 刚才在群「{group}」（{gid}）里跟〈我〉说过下面这些，现在私聊可能是接着那边的事说；"
               "TA 说的「这个」「那张」「刚才那个」多半指这里的）")

# 沉默：私聊聊到難受的事，〈我〉回完之後 TA 多久不說話算「好久」：TA 平時回〈我〉的時間 × K，夾在上下限之間
SILENCE_K = 4.0
SILENCE_MIN = 90.0
SILENCE_MAX = 900.0
SILENCE_DAILY = 3  # 同一個人一天最多這麼多次
SILENCE_HISTORY = 16  # 帶最近幾條聊天
SILENCE_TIMEOUT = 40.0
SILENCE_ARM_TTL = 600.0  # 那輪的回覆十分鐘內沒發出去就不等了

# 發送前過濾：模型偶爾把系統提示或 DeepSeek 原生工具呼叫標記寫進正文
REMINDER_RE = re.compile(r"<system_reminder>.*?(?:</system_reminder>|$)", re.DOTALL)
DSML_RE = re.compile(r"<[^<>]{0,8}DSML|DSML")
# 表情包插件（meme_manager）的「&&標籤&&」：模型調工具前單獨吐的那一段不經過它的 on_llm_response，
# 整段只有標籤時它也清不掉，就會原樣發出去。在它之後再補一道：換成那個分類的一張圖，沒有這個分類就刪掉
MEME_TAG_RE = re.compile(r"&&([A-Za-z][\w-]{0,30})&&")
# 擦邊的表情包（tease 類，10-24 用戶要留著偶爾捉弄人）：只對夠熟的人用，門檻和主動找人一樣（bond 讀口的 can_reach）
TEASE_RE = re.compile(r"&&tease&&", re.I)

# AstrBot 壓縮聊天歷史（LLMSummaryCompressor）時在摘要後面用〈我〉的身分插一句英文，存進歷史、之後每輪都帶。
# 10-29 08:52 主人私聊剛壓縮完，她回話結尾照著寫出一行「Marked as acknowledged.」發了出去。換成中文備註（不能刪：要一問一答輪著排）
COMPRESS_ACK_EN = "Acknowledged the summary of our previous conversation history."
COMPRESS_ACK = "（前面的聊天〈我〉记在上面这段备忘里了）"
MEME_DIR = PLUGIN_DATA / "meme_manager" / "memes"
MEME_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# 表情包：NapCat 會在圖片上標 sub_type=1 或說明文字「[動畫表情]」之類
STICKER_WITH_TEXT = "（对方配的图是表情包，只代表语气，重点回应文字，不用描述图的画面）"
# 收藏的表情、梗圖在 NapCat 裡是普通圖片，認不出來，所以文字配圖一律交給模型自己判斷
TEXT_WITH_IMAGE = (
    "（对方是文字配图：先回应文字；图如果是表情包或梗图，就当作语气，不用描述；"
    "如果是截图或照片，再结合着看）"
)
STICKER_ONLY = (
    "（对方只发了个表情包，像真人一样简单接一句或回个表情就行，不用描述画面）"
)
# 只發了圖、一個字沒說：看得懂圖就照著圖接，看不懂就問，別自己編 TA 在問什麼
IMAGE_ONLY = (
    "（对方这条只有图，一个字都没说。看得出图里是什么，就照着图自然接一句；"
    "看不清、或者只有「图片描述失败」之类的提示，就直接问 TA 想说啥。"
    "不要替 TA 编问题、编情景，也不要靠人设或表情包名字去猜图里是谁）"
)

# 只 @ 一下、或只喊一聲名字：等這個人把話說完（常見的是先 @ 再單獨發圖）
# AstrBot 自帶的空 @ 等待會把隨後的純圖片吞掉，所以在它之前自己處理
CALL_FIRST_WAIT = 15.0  # 等第一條下文
CALL_MORE_WAIT = 2.0  # 有下文後，再等一會兒看還有沒有
CALL_MEDIA_WAIT = 5.0  # 下文只有圖、還沒有字：多等一會兒（先 @、再發圖、最後打字，字常常晚 2～3 秒）
CALL_MAX_WAIT = 25.0
# 合併窗口關了之後才到的字：這輪還沒送去問模型的話，在 on_llm_request 補進去
CALL_LATE_GRACE = 10.0
EMPTY_CALL_TEXT = "[叫了你一声]"
EMPTY_CALL_HINT = "（TA 这一条只叫了〈我〉一声，之后 {secs} 秒没再说别的）"
# 先說話、再叫她（10-27 16:32「[图片] 你复盘一下」兩秒後「小肥鱼」）：前面那句沒叫她，只進了群聊背景，
# 這輪卻只剩「叫了一声」。叫她之前這段時間內同一個人說的、沒叫她、她也還沒回過 TA 的話，併進這一輪
CALL_BEFORE_SECS = 60.0
CALL_BEFORE_MAX = 3  # 最多帶幾條
CALL_BEFORE_HINT = "（这一轮里「{before}」是 TA 叫〈我〉之前 {secs} 秒说的，那时没叫〈我〉；接着 TA 单独叫了〈我〉一声{after}）"


# 句子中間喊名字：只認明顯在叫它的說法，在聊它的（「加<名字>好友」「<名字>的尾巴」）不算
def _name_res(name: str) -> tuple[re.Pattern, re.Pattern]:
    n = re.escape(name)
    call = re.compile(
        rf"{n}[呢呀啊吗嘛哦喔～~！!？?。\s]*$"  # 句尾喊：早啊<名字>、<名字>呢
        rf"|(?:^|[，,。！!？?\s]){n}[，,！!？?\s]"  # 單獨一段喊：哈哈 <名字>，……
        rf"|{n}(?:你|您|快|来|帮|给我|说说|评|觉得|怎么看|在吗|在不在|出来)"
        rf"|(?:问问|问下|问一下|让|叫|喊|找|请){n}"
    )
    not_call = re.compile(rf"{n}的|{n}好友|加{n}|私信{n}|私聊{n}")
    return call, not_call


def _group_providers(lines) -> dict[str, str]:
    """「群號=模型ID」一行一個"""
    out = {}
    for line in lines or []:
        gid, _, pid = str(line).replace("：", ":").replace(":", "=").partition("=")
        if gid.strip().isdigit() and pid.strip():
            out[gid.strip()] = pid.strip()
    return out


NAME_CALL_COOLDOWN = 20.0  # 同一個群，這種叫法 20 秒內只認一次，防止刷屏連環觸發

# 被叫去評價時模型愛推脫（尤其聊天記錄裡剛推過一次），在這條消息後面直接提醒
# 群聊背景：AstrBot 自帶的群聊上下文把她上次說話之後群裡的消息整塊塞進這輪（英文開頭、排在觸發消息後面、
# 存進對話歷史），模型容易逐條回應沒叫她的話。在它之後（priority 0）、bond（-10）之前改寫：
# 只留最近幾條、標明只是背景、最後寫清楚這輪要回的是誰說的哪句、有沒有叫她；標成臨時，不存進對話歷史
ICL_MARK = "Belows are group chat context after your last reply"
ICL_LINE_RE = re.compile(r"^\[(.*?)/(\d\d:\d\d)(?::\d\d)?\]:\s*(⚠️\[DIRECTED AT YOU\]\s*)?(.*)$")
ICL_LINES = 15
# 整塊背景是臨時的，下一輪就看不到了：留最後幾條（每條截短）跟著這輪存進對話歷史，
# 以後翻到這一輪時還知道當時在聊什麼，不會只剩一句沒頭沒尾的「你覺得呢」
# 10-23 先預設不留：剛把整塊背景改成不存，還在觀察她會不會接沒叫她的話，看完再開
KEEP_LINES = 0
KEEP_LINE_MAX = 60
KEEP_HEAD = "（〈我〉回这句时群里刚在聊：{lines}）"
TRIGGER_MAX = 100
ICL_HEAD = (
    "下面是〈我〉上次说话之后群里的其他聊天，只是背景：大多是群友之间在聊，不是对〈我〉说的。"
    "不要逐条回应，不要替别人接话；标了「@〈我〉」的才是冲着〈我〉来的，有必要再顺带接一句。"
)
BEAT_EXTRA = "lively_beat"  # 自主插件（wake.py）做的內部消息：〈我〉看手機時想說話，交給聊天這邊說
def _is_beat(event) -> bool:
    try:
        return bool(event.get_extra(BEAT_EXTRA))
    except Exception:
        return False


ICL_BEAT = "这一轮没有人叫〈我〉：是〈我〉刚才看 QQ 时自己想在这个群说话，想接哪条、为什么写在这一轮的消息里。"
ICL_CALLED = "这一轮〈我〉要回应的是 {name}（QQ {qq}）刚说的：「{text}」——TA 叫了〈我〉，回应 TA 这句就好。"
ICL_ACTIVE = (
    "这一轮没人叫〈我〉，是〈我〉自己看到 {name}（QQ {qq}）说「{text}」想插一句：自然地接一句就好，"
    "不要像被点名一样回答，也不用回应所有人。"
)

REVIEW_RE = re.compile(
    r"锐评|点评|评价|评一下|评评|怎么看待|如何看待|你觉得.{0,20}(怎么样|如何|咋样)"
)
# 10-25 改成「评不评由〈我〉」：重放 90 题，放开之后表态比例不变（82/90）、没有多推掉，政治题照样岔开
REVIEW_HINT = (
    "（对方在请〈我〉评价。〈我〉有自己的喜好，评不评、怎么评都由〈我〉：想评就说，可以毒舌偏心；"
    "不想评、懒得评、不想给热度就不评，用〈我〉自己的说法推掉。"
    "唯一不算数的是客服话术——「不了解」「各有各的好」「怕传谣」这类。想评又摸不准的，先联网查一下）"
)


# 起草外洩：提前提醒一句（臨時，不存歷史）；真漏了在 on_llm_response 挑出終稿
DRAFT_HINT = (
    "（直接说出要发的话本身就好：不要先写情景、分析、清单、「写：」「终稿」这类草稿，"
    "也不要把好感、心情写进正文）"
)
DRAFT_REWRITE_SYSTEM = (
    "下面是一段聊天回复的草稿，里面混了情景分析、要求清单和备注。"
    "只输出最后真正要发给对方的那一两句话，保持原来的语气和自称，不要加任何说明、引号或标签。"
    "如果草稿里看不出要发什么，就只输出：嗯？"
)
DRAFT_REWRITE_TIMEOUT = 20.0
DRAFT_DROPPED = "……"  # 沒挑出終稿、也沒重寫成時，記進歷史的那句
# 同一輪裡調工具前已經發出去的話，工具回來後又整行抄一遍（10-29 15:09 群：一樣的兩行發了三次）：
# 這麼長以上的行才算（「哈哈」「嗯」這種短的重複照發）
TURN_REPEAT_MIN = 6
TURN_RESEND_TAIL = 30  # 整段重抄後面只接了這麼短的一行：當成沒包標記的「记住」（和记住的字數上限一樣）
# 調工具前那步寫的話 AstrBot 當場就發了，工具回來後是另一次生成，她不知道前面那幾句已經出去了，
# 常把同一件事換個說法再說一遍、或另編一個場面（10-27 15:38 私聊依然「昵称改成这样是打算长住了」兩遍）。
# 接在每一步第一個工具的結果後面照實告訴她這一輪已經發了什麼（只講事實，寫不寫、寫什麼她定）。
# 每一步都帶：10-29 16:58 第一次上線那輪，她先寫兩行＋調表情包、再不帶字調一次表情包，最後一步又把兩行抄一遍，
# 只接在第一個結果上的那句隔了一層
# AstrBot 把工具回傳的圖緩存起來，並在工具結果後面寫死一句「看完滿意就用 send_message_to_user 發給用戶」。
# 10-29 17:20、17:25 定做形象畫好、工具已經把圖發出去了，她照這句又用 send_message_to_user 重發了一次。
# 工具自己說明「只給你自己看」的（插件回傳裡有「不会发给谁」），這句換成只講事實的一句，路徑還給她
TOOL_IMG_HINT_RE = re.compile(r"Image returned and cached at path='([^']*)'\. Review the image below\. "
                              r"Use send_message_to_user[^\n]*?path='[^']*'\.")
TOOL_IMG_SELF_RE = re.compile(r"不会(?:再)?发给谁")
TOOL_IMG_NOTE = "图缓存在 path='{}'，在下面给你看。"
TOOL_SAID_NOTE = ("（这一轮你已经作为消息发出去的话，对方都看到了：{said}。"
                  "工具回来之后你再写的话，会另外发成新的一条，前面那些不会被替换）")
# 10-30 試過後面加「也可以什么都不写，回复空着…」：重放 42 次她一次都沒空著、追評 19→18，反而多了發出去的括號話「（这一轮到此为止）」，撤了
TOOL_SAID_MAX = 200
ICL_CAPTION_TIMEOUT = 15.0
ICL_CAPTION_FAILED = "图片没看清"
CAPTION_KEEP = 300  # 群聊背景的圖片描述記幾張（發完複查只看最近幾分鐘的）
# QQ 商城表情（超級表情）：NapCat 當成圖片發過來，summary 是表情名字（例如「[摸摸猫猫]」），
# 圖的鏈接在 gxh.vip.qq.com，常常 404（10-26 群裡四張都下載不到，每張讓 AstrBot 印兩條錯誤）。
# 這種不去下載，群聊背景和這輪消息裡照實寫名字
MFACE_HOST = "gxh.vip.qq.com"
MFACE_KEEP = 200  # 記住最近多少張商城表情的名字（群聊背景描述圖時按鏈接查）
MFACE_SEEN = "QQ 表情「{name}」（只看得到名字，图 QQ 那边下载不到）"
MFACE_NAMELESS = "一个 QQ 表情（图 QQ 那边下载不到，也没有名字）"
# 轉發的聊天記錄（10-27）：收到時向 NapCat 要內容，寫進這條消息（群聊背景、長期記憶都看得到）；叫到〈我〉的這條另外帶給她
FORWARD_TIMEOUT = 8
FORWARD_KEEP = 2  # 一條消息最多展開幾段
FORWARD_NEST_FETCH = 6  # 轉發裡再轉發沒帶內容時，最多再去要幾次
FORWARD_IMG_KEEP = 80  # 每個聊天記著最近幾張轉發裡的圖（編號對得上才能叫她去看）
FORWARD_LOOK_MAX = 8  # 她一次最多看幾張
FORWARD_LOOK_WAIT = 40.0
FORWARD_LOOK_PAR = 4
FORWARD_HINT = "（这条消息里{text}）"
MFACE_HINT = "（这条里有 QQ 表情：{names}。这种表情的图 QQ 那边下载不到，〈我〉只看得到名字）"
ICL_UNSEEN = "没看到这张图：{why}"  # 讀不了的圖在群聊背景裡寫成這樣，原因照實說
HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1"}


def unreadable_why(head: bytes) -> str:
    """下載下來了、但轉不成模型認的格式時，看開頭幾個位元組說是什麼原因。"""
    if not head.strip(b"\x00 \t\r\n"):
        return "下载下来是空的"
    if head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS:
        return "是 HEIC 格式（苹果相机拍的那种），这边打不开"
    if head.lstrip()[:1] == b"<":
        return "下载下来的不是图片"
    return "图片格式打不开"


def _flat(s: str) -> str:
    """比兩行是不是同一句：空白、標點都不算"""
    return re.sub(r"[\s，。,.！!？?～~、…「」\"'“”]", "", s or "")


def _this_turn(messages) -> list:
    """這一輪（最後一條 user 之後）助手說的那幾步"""
    out = []
    for msg in reversed(messages):
        if msg.role == "user":
            break
        if msg.role == "assistant":
            out.append(msg)
    return out[::-1]


def _clean(text: str) -> str:
    text = REMINDER_RE.sub("", text)
    m = DSML_RE.search(text)
    if m:
        text = text[: m.start()]
    return text.rstrip()


def _mfaces(event: AstrMessageEvent) -> list[tuple[list[str], str]]:
    """這條消息裡的 QQ 商城表情：[(鏈接和 file, 名字)]，讀的是 NapCat 原始消息。名字可能是空的"""
    raw = getattr(event.message_obj, "raw_message", None)
    try:
        segs = raw.get("message") if raw is not None else None
    except Exception:
        segs = None
    out = []
    for seg in segs if isinstance(segs, list) else []:
        if not isinstance(seg, dict) or seg.get("type") != "image":
            continue
        data = seg.get("data") or {}
        refs = [str(data.get(k) or "") for k in ("url", "file")]
        if not any(MFACE_HOST in r for r in refs):
            continue
        name = str(data.get("summary") or "").strip().strip("[]［］").strip()
        out.append(([r for r in refs if r], name))
    return out


def _count_stickers(event: AstrMessageEvent) -> tuple[int, int, list]:
    """返回 (圖片數, 其中表情包數, 每張圖的標記)，讀的是 NapCat 原始消息。"""
    raw = getattr(event.message_obj, "raw_message", None)
    try:
        segs = raw.get("message") if raw is not None else None
    except Exception:
        segs = None
    if not isinstance(segs, list):
        return 0, 0, []
    images = stickers = 0
    marks = []
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        t = seg.get("type")
        data = seg.get("data") or {}
        if t == "mface":
            images += 1
            stickers += 1
            marks.append("mface")
        elif t == "image":
            images += 1
            sub = str(data.get("sub_type", data.get("subType", "")))
            summary = str(data.get("summary", ""))
            marks.append(f"sub_type={sub or '-'} summary={summary or '-'}")
            if sub == "1" or "表情" in summary or MFACE_HOST in str(data.get("url", "")):
                stickers += 1
    return images, stickers, marks


def _join_reply_lines(contexts) -> int:
    """歷史裡〈我〉自己的回覆，換行改成空格。返回改了幾條。

    她每輪都照著前文的樣子寫：10-25 主人私聊幾乎每輪都是「一句＋補一句收尾」兩行，換行又會切成兩個氣泡，越寫越固定。
    重放（伺服器 ~/lively_test/b1025/replay_lines_1025.py，HIST=join）：人設不動，只把歷史裡的換行合起來，
    日常一行從約四成變成九成；要講清楚的事照樣會分幾條。改的是 req.contexts 本身，存回歷史的也是合過的，每輪一樣，不影響前綴快取
    """
    if not isinstance(contexts, list):
        return 0
    joined = 0
    for m in contexts:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = m.get("content")
        if isinstance(content, str):
            if "\n" in content.strip():
                m["content"] = re.sub(r"\s*\n+\s*", " ", content.strip())
                joined += 1
        elif isinstance(content, list):
            hit = False
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text" and "\n" in str(p.get("text") or "").strip():
                    p["text"] = re.sub(r"\s*\n+\s*", " ", p["text"].strip())
                    hit = True
            joined += hit
    return joined


# 中文和中文之間的空格：她拿來隔開兩段話（歷史合成一行後學來的），發送前當換行，分段時照常拆成兩條
SPACE_BREAK_RE = re.compile(r"(?<=[\u4e00-\u9fff～~…！？!?」）)])[ \u3000]+(?=[\u4e00-\u9fff「（(])")


def _space_breaks(text: str) -> str:
    """「在呢，本鱼一直在，没坏 你这测试也测得太勤了」→ 兩行。前面那個詞是 @某人 的空格不拆（「@小凛 严肃」）"""
    out, last = [], 0
    for m in SPACE_BREAK_RE.finditer(text):
        word = re.split(r"\s", text[:m.start()])[-1]
        if word.startswith("@"):
            continue
        out.append(text[last:m.start()])
        out.append("\n")
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def system_tail(req, text: str):
    """每輪都一樣的說明接在 system 最後：排在對話歷史前面，DeepSeek 前綴快取命中得到（已經有了就不重複加）"""
    sp = getattr(req, "system_prompt", "") or ""
    if text and text not in sp:
        req.system_prompt = f"{sp.rstrip()}\n\n{text}" if sp.strip() else text


def _strip_old_images(contexts) -> int:
    """歷史裡的舊圖換成「[圖片]」，只保留上一輪使用者消息裡的圖。返回換掉的張數。

    AstrBot 會把圖片以 base64 存進歷史，之後每次請求都重新發給模型，又大又慢。
    """
    if not isinstance(contexts, list):
        return 0
    last_user = max(
        (
            i
            for i, m in enumerate(contexts)
            if isinstance(m, dict) and m.get("role") == "user"
        ),
        default=-1,
    )
    removed = 0
    for i, m in enumerate(contexts):
        if i == last_user or not isinstance(m, dict):
            continue
        content = m.get("content")
        if not isinstance(content, list):
            continue
        if not any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in content
        ):
            continue
        new = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "image_url":
                removed += 1
                new.append({"type": "text", "text": "[图片]"})
            else:
                new.append(p)
        m["content"] = new
    return removed


def _plain_history(history: list) -> list[dict]:
    """對話歷史只留文字（圖、工具呼叫都去掉），給沉默時那次請求用"""
    out = []
    for m in history:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        c = m.get("content")
        if isinstance(c, list):
            c = "\n".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
        c = REMINDER_RE.sub("", str(c or "")).strip()
        if c:
            out.append({"role": m["role"], "content": c})
    return out


@register(
    "astrbot_plugin_lively_gate",
    "GUCine",
    "門禁和公共設定：只放行指定 QQ 群、群聊/私聊分別用不同模型、喊名字當 @、表情包識別、攔截洩漏的內部標記",
    "2.0.0",
)
class LivelyGate(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.cfg = config if config is not None else {}
        self.s = Settings(context, self.cfg)
        self.name, self.name_call_re, self.name_not_call_re = "", None, None
        self.ignored: set[str] = set()
        self._refresh()
        self._listening: dict[tuple[str, str], dict] = {}
        self._calls: dict[tuple[str, str], dict] = {}
        self._said: dict[tuple[str, str], list] = {}  # 每個人最近說的、沒叫她的話（叫一聲時帶上）
        self._replied: dict[tuple[str, str], float] = {}  # 最後一次回這個人的時間
        self._late: dict[tuple[str, str], dict] = {}
        self._caption_orig = None
        self._mface_names: dict[str, str] = {}  # 商城表情的鏈接 -> 名字
        self._captions: dict[str, str] = {}  # 群聊背景給圖寫的描述（圖片鍵 -> 描述），自主插件發完複查要看
        self._tease_dropped: dict[str, tuple[float, str]] = {}  # umo -> (什麼時候, 沒配上的原因)：下一輪照實告訴她
        self._patch_icl_caption()
        self._compress_orig = None
        self._patch_compress_ack()
        self._tool_said_orig = None
        self._patch_tool_said()
        self._tool_image_orig = None
        self._patch_tool_image()
        self._name_call_at: dict[str, float] = {}
        self.rhythm = Rhythm(DATA_DIR / "rhythm.json")
        self._outbox_file = DATA_DIR / "outbox_seen.json"
        try:
            self._outbox_seen: dict[str, float] = json.loads(self._outbox_file.read_text("utf-8"))
        except Exception:
            self._outbox_seen = {}
        try:
            self._threads: dict = json.loads((DATA_DIR / THREAD_FILE).read_text("utf-8"))
        except Exception:
            self._threads = {}
        self._arm: dict[str, dict] = {}  # 私聊 umo -> 這輪回完要不要看 TA 會不會好久不說話
        self._watch: dict[str, asyncio.Task] = {}
        self._silence_count: dict[str, tuple[str, int]] = {}
        self.updates = Updates(DATA_DIR)  # 改動公告（updates.py 上面有來由）
        self._upd_task = asyncio.create_task(self._updates_loop())

    def _refresh(self):
        """名字、不理的人在設定檔改了不用重啟（Settings 會重讀檔）：每條消息對一下，名字變了才重編正則"""
        # 名字留空：不啟用「喊名字當 @」（空名字會讓正則匹配所有消息）
        name = self.s.bot_name().strip()
        if name != self.name:
            self.name = name
            self.name_call_re, self.name_not_call_re = _name_res(name) if name else (None, None)
        self.ignored = set(id_list(self.s.get("ignored_senders", [])))

    async def _bind(self, umo: str, pid: str):
        cur = await sp.get_async("umo", umo, KEY, None)
        if cur != pid:
            await sp.put_async("umo", umo, KEY, pid)

    def _served(self, event: AstrMessageEvent) -> bool:
        if str(event.get_sender_id() or "").strip() in self.ignored:
            return False
        gid = str(event.get_group_id() or "").strip()
        return not gid or gid in self.s.groups()

    def _is_empty_call(self, event: AstrMessageEvent) -> bool:
        comps = [
            c
            for c in event.get_messages()
            if not (isinstance(c, Plain) and not c.text.strip())
        ]
        if len(comps) != 1:
            return False
        c = comps[0]
        if isinstance(c, At):
            return str(c.qq) == str(event.get_self_id())
        if isinstance(c, Plain):
            prefixes = self.context.get_config(umo=event.unified_msg_origin).get(
                "wake_prefix", []
            )
            return c.text.strip() in [p for p in prefixes if p and p != "/"]
        return False

    # 優先順序比 AstrBot 自帶的會話控制、空 @ 等待都高
    @filter.event_message_type(filter.EventMessageType.ALL, priority=sys.maxsize + 1)
    async def empty_call(self, event: AstrMessageEvent):
        if not self._served(event) or _is_beat(event):
            return
        self._keep_name(event)
        key = (event.unified_msg_origin, str(event.get_sender_id() or ""))
        self._on_any_message(event, key)
        late = self._late.get(key)
        if late is not None and time.monotonic() > late["until"]:
            self._late.pop(key, None)
            late = None
        if late is not None and not event.is_at_or_wake_command:
            # 窗口關了才到的字（只認純文字，帶圖、@ 別人的照常處理）：這輪還沒問模型，就併過去
            text = (event.message_str or "").strip()
            if text and all(isinstance(c, Plain) for c in event.get_messages()):
                late["texts"].append(text)
                logger.info(f"[lively_gate] 叫了一声之后晚到的话并进那一轮: {event.unified_msg_origin}")
                event.stop_event()
                return
        state = self._calls.get(key)
        if state is not None:
            # 叫完之後發的下文：並進那一條，本條不單獨處理
            text = (event.message_str or "").strip()
            if text:
                state["texts"].append(text)
            state["media"].extend(
                c for c in event.get_messages() if not isinstance(c, (At, Plain))
            )
            state["last"] = time.monotonic()
            event.stop_event()
            return
        if not self._is_empty_call(event):
            return
        now = time.monotonic()
        state = {"texts": [], "media": [], "start": now, "last": None}
        self._calls[key] = state
        called_at = time.time()
        try:
            while True:
                if state["last"] is None:
                    end = state["start"] + CALL_FIRST_WAIT
                elif not state["texts"]:
                    end = min(
                        state["last"] + CALL_MEDIA_WAIT, state["start"] + CALL_MAX_WAIT
                    )
                else:
                    end = min(
                        state["last"] + CALL_MORE_WAIT, state["start"] + CALL_MAX_WAIT
                    )
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(remaining, 0.5))
        finally:
            self._calls.pop(key, None)
        after = "\n".join(state["texts"])
        before = self._said_before(key, called_at)
        if before:
            state["texts"] = [b["text"] for b in before] + state["texts"]
            state["media"] = [m for b in before for m in b["media"]] + state["media"]
            secs = max(1, round(called_at - before[-1]["ts"]))
            tail = f"，之后又说了「{after[:TRIGGER_MAX]}」" if after else f"，之后 {int(CALL_FIRST_WAIT)} 秒没再说别的"
            event.set_extra("lively_call_before", CALL_BEFORE_HINT.format(
                before="」「".join(b["text"][:TRIGGER_MAX] for b in before), secs=secs, after=tail))
            logger.info(
                f"[lively_gate] 叫了一声，带上 TA 叫之前 {secs} 秒说的 {len(before)} 条: {event.unified_msg_origin}"
            )
        text = "\n".join(state["texts"])
        if not after and not before and state["media"]:
            # 只等到圖：之後幾秒內這個人補的字，還來得及就併進這輪
            self._late[key] = {"until": time.monotonic() + CALL_LATE_GRACE, "texts": []}
            event.set_extra("lively_late_key", key)
        if text or state["media"]:
            event.message_str = text
            logger.info(
                f"[lively_gate] 叫了一声后接着说了 {len(state['texts'])} 段文字、"
                f"{len(state['media'])} 个图片等: {event.unified_msg_origin}"
            )
        else:
            event.message_str = EMPTY_CALL_TEXT
            event.set_extra("lively_empty_call", True)
            logger.info(
                f"[lively_gate] 只叫了一声，没有下文: {event.unified_msg_origin}"
            )
        event.set_extra("lively_call_waited", True)  # 已經等過下文了，傾聽不用再等
        # 多加一段文字：既把內容帶上，也讓自帶的空 @ 等待不再接管這條
        event.message_obj.message.append(Plain(event.message_str))
        event.message_obj.message.extend(state["media"])

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def gate(self, event: AstrMessageEvent):
        self._refresh()
        sender = str(event.get_sender_id() or "").strip()
        if sender in self.ignored:
            event.stop_event()
            return
        self.s.remember_self(event)
        gid = str(event.get_group_id() or "").strip()
        if not gid:
            pid = self.s.provider_id("dm_provider_id")
        elif gid in self.s.groups():
            pid = _group_providers(self.cfg.get("group_providers", [])).get(gid, "")
            if not pid or self.context.get_provider_by_id(pid) is None:
                pid = self.s.provider_id(
                    "group_provider_id"
                )  # 這個群的密鑰還沒配好時先用預設的
        else:
            event.stop_event()
            return
        self._note_mfaces(event)
        if self.cfg.get("expand_forward", True):
            try:
                await self._expand_forward(event)
            except Exception as e:
                logger.warning(f"[lively_gate] 展开转发的聊天记录失败: {e}")
        # 沒選模型就不綁定，交給 AstrBot 預設的
        if pid and self.context.get_provider_by_id(pid) is not None:
            await self._bind(event.unified_msg_origin, pid)
        if _is_beat(event):
            return  # 自主插件做的內部消息（〈我〉看手機時想說話）：不是 TA 說的，不傾聽、不認喊名字、不記話
        is_dm = not gid
        if (
            not is_dm
            and not event.is_at_or_wake_command
            and self._called_by_name(event)
        ):
            now = time.monotonic()
            if now - self._name_call_at.get(gid, 0) >= NAME_CALL_COOLDOWN:
                self._name_call_at[gid] = now
                event.is_at_or_wake_command = True
                logger.info(
                    f"[lively_gate] 句子里叫了{self.name}，当作 @: {event.unified_msg_origin}"
                )
        self._forward_into_text(event)  # 喊名字看完了才接上：轉發裡有人叫她不算叫她
        if sender and self.cfg.get("listen_dm" if is_dm else "listen_group", True):
            await self._listen(event, sender, is_dm)
            if event.is_stopped():
                return
        if sender and not is_dm and not event.is_at_or_wake_command:
            self._note_said(event, sender)
        if is_dm and sender:
            text = event.message_str or ""
            if not text.startswith("/") and (looks_heavy(text) or looks_unfinished(text)):
                self._arm[event.unified_msg_origin] = {"qq": sender, "ts": time.time()}
        self._mark_stickers(event)

    def _note_said(self, event: AstrMessageEvent, sender: str):
        """群裡沒叫她的話記一下：TA 接著單獨叫她一聲時，這幾句併進那一輪"""
        text = (event.message_str or "").strip()
        media = [c for c in event.get_messages() if isinstance(c, Image)]
        if media:
            text = " ".join(t for t in ["[图片]" * len(media), text] if t)
        if not text:
            return
        now = time.time()
        said = getattr(self, "_said", None)
        if said is None:
            said = self._said = {}
        if len(said) > 500:
            for k in [k for k, v in said.items() if not v or now - v[-1]["ts"] > CALL_BEFORE_SECS]:
                said.pop(k, None)
        key = (event.unified_msg_origin, sender)
        rows = [r for r in said.get(key, []) if now - r["ts"] <= CALL_BEFORE_SECS * 2][-4:]
        rows.append({"ts": now, "text": text, "media": media})
        said[key] = rows

    def _said_before(self, key: tuple[str, str], called_at: float) -> list[dict]:
        """叫她之前 CALL_BEFORE_SECS 秒內這個人說的、她還沒回過 TA 的（用過的不再帶）"""
        since = max(called_at - CALL_BEFORE_SECS, getattr(self, "_replied", {}).get(key, 0))
        rows = [r for r in getattr(self, "_said", {}).get(key, [])
                if since < r["ts"] < called_at and not r.get("used")][-CALL_BEFORE_MAX:]
        for r in rows:
            r["used"] = True
        return rows

    def _keep_name(self, event: AstrMessageEvent):
        """AstrBot 的喚醒前綴裡有名字（線上 wake_prefix 有「小肥鱼」）：以名字開頭的消息它照樣喚醒，但把名字剪掉才往下傳，
        10-27「小肥鱼呢」（問她在哪、在幹嘛）她收到的只有「呢」，回成「呢什么呀」。喚醒照舊，名字補回去。
        「/」開頭的指令、「@名字」那種打出來的 @ 照舊剪掉"""
        name = getattr(self, "name", "")
        if not name or not getattr(event, "is_at_or_wake_command", False):
            return
        raw = str(getattr(event.message_obj, "message_str", "") or "").strip()
        cur = (event.message_str or "").strip()
        if not raw.startswith(name) or raw == cur:
            return
        rest = raw[len(name):].strip()
        if cur != rest or rest.startswith("/"):
            return
        event.message_str = raw
        logger.info(f"[lively_gate] 喊名字开头的话，名字补回去了：{raw[:30]}")

    def _called_by_name(self, event: AstrMessageEvent) -> bool:
        if not self.name or self.name_call_re is None:
            return False
        text = (event.message_str or "").strip()
        if self.name not in text or self.name_not_call_re.search(text):
            return False
        # @ 了別人，是在跟別人聊它
        self_id = str(event.get_self_id())
        if any(
            isinstance(c, At) and str(c.qq) != self_id for c in event.get_messages()
        ):
            return False
        return bool(self.name_call_re.search(text))

    def _note_mfaces(self, event: AstrMessageEvent):
        """記下商城表情的名字：群聊背景描述到這張圖時按鏈接查，這輪回話時也照實告訴她"""
        found = _mfaces(event)
        if not found:
            return
        names = getattr(self, "_mface_names", None)
        if names is None:
            names = self._mface_names = {}
        for refs, name in found:
            for r in refs:
                names.pop(r, None)
                names[r] = name
        while len(names) > MFACE_KEEP:
            names.pop(next(iter(names)))
        event.set_extra("lively_mfaces", [name for _refs, name in found])

    async def _expand_forward(self, event: AstrMessageEvent):
        """這條帶了轉發的聊天記錄：把內容寫成一段字接在消息後面（AstrBot 的群聊背景、長期記憶照消息內容記），
        叫到〈我〉時 sticker_hint 再單獨帶給她。拿不到內容就照實寫拿不到"""
        raw = getattr(event.message_obj, "raw_message", None)
        try:
            segs = raw.get("message") if raw is not None else None
        except Exception:
            segs = None
        fwd = [x for x in segs or [] if isinstance(x, dict) and x.get("type") == "forward"][:FORWARD_KEEP]
        if not fwd:
            return
        texts = []
        for seg in fwd:
            nodes = (seg.get("data") or {}).get("content") or await self._fetch_forward(event, seg)
            await self._fill_nested(nodes, [FORWARD_NEST_FETCH])
            self._number_forward_images(event, nodes)
            texts.append(self.s.fill(forward_text(nodes)))
        event.message_obj.message.append(Plain(" " + " ".join(texts)))
        event.set_extra("lively_forward", texts)
        logger.info(f"[lively_gate] 展开了转发的聊天记录：{' '.join(texts)[:80]}")

    def _forward_into_text(self, event: AstrMessageEvent):
        """展開的轉發接進 message_str：聊天記錄存的是它（以前只帶臨時的一段，下一輪她就不記得了），
        傾聽併消息時也只拿它——10-29 00:25 主人先問一句、2 毫秒後到的轉發被併進那句時拿到空字，整段丟了"""
        fwd = event.get_extra("lively_forward")
        if fwd:
            event.message_str = " ".join(t for t in [(event.message_str or "").strip(), *fwd] if t)

    async def _fetch_forward(self, event: AstrMessageEvent, seg: dict) -> list:
        fid = str((seg.get("data") or {}).get("id") or "")
        mid = str(getattr(event.message_obj, "message_id", "") or "")
        return await self._get_forward([{"message_id": mid}, {"id": fid}])

    async def _get_forward(self, tries: list) -> list:
        client = self.s.client()
        if client is None:
            return []
        for params in [p for p in tries if next(iter(p.values()))]:
            try:
                res = await asyncio.wait_for(client.api.call_action("get_forward_msg", **params), FORWARD_TIMEOUT)
            except Exception as e:
                logger.warning(f"[lively_gate] 拿转发的聊天记录失败（{params}）: {e}")
                continue
            msgs = (res or {}).get("messages") if isinstance(res, dict) else None
            if msgs:
                return msgs
        return []

    async def _fill_nested(self, nodes, left: list, depth: int = 1):
        """轉發裡再轉發：NapCat 有時只給那段的 id、不帶內容，拿 id 再要一次補進去（共用 left[0] 次，免得一大串拖住）"""
        if depth >= FORWARD_NEST_DEPTH:
            return
        for n in nodes if isinstance(nodes, list) else []:
            for seg in node_segs(n):
                d = seg.get("data")
                if seg.get("type") != "forward" or not isinstance(d, dict):
                    continue
                if not d.get("content") and d.get("id") and left[0] > 0:
                    left[0] -= 1
                    d["content"] = await self._get_forward([{"id": str(d["id"])}])
                await self._fill_nested(d.get("content"), left, depth + 1)

    def _forward_images(self, nodes, depth: int = 0, out: list | None = None) -> list:
        """展開後她看得到的那些圖（頂層前 FORWARD_LINES 條、套著的每段前 FORWARD_NEST_LINES 條），按順序"""
        out = [] if out is None else out
        if depth >= FORWARD_NEST_DEPTH:
            return out
        for n in (nodes if isinstance(nodes, list) else [])[: FORWARD_NEST_LINES if depth else FORWARD_LINES]:
            for seg in node_segs(n):
                d = seg.get("data")
                if not isinstance(d, dict):
                    continue
                if seg.get("type") == "forward":
                    self._forward_images(d.get("content"), depth + 1, out)
                elif seg.get("type") == "image" and str(d.get("sub_type", "0")) != "1" \
                        and str(d.get("summary") or "[图片]") == "[图片]" and (d.get("url") or d.get("file")):
                    out.append(d)
        return out

    def _number_forward_images(self, event: AstrMessageEvent, nodes):
        """展開後看得到的圖寫成「[图片#编号]」、記下網址：她想看哪張自己調 lively_look_forward_image，不替她看"""
        imgs = self._forward_images(nodes)
        if not imgs:
            return
        store = self.__dict__.setdefault("_fwd_imgs", {})
        umo = str(event.unified_msg_origin)
        have = store.setdefault(umo, {"next": 1, "urls": {}})
        for d in imgs:
            n = have["next"]
            have["next"] += 1
            have["urls"][n] = d.get("url") or d.get("file")
            d["summary"] = f"[图片#{n}]"
        while len(have["urls"]) > FORWARD_IMG_KEEP:
            have["urls"].pop(next(iter(have["urls"])))

    @filter.llm_tool("lively_look_forward_image")
    async def tool_look_forward_image(self, event: AstrMessageEvent, which: str):
        """看转发的聊天记录里的图。转发里的图你平时只看到「[图片#3]」这样带编号的字，图本身没送到你这里；想知道某几张画的是什么，用这个看。
        编号就是转发那段文字里「[图片#编号]」的数字（同一个聊天里编号不重复）；转发里只有展开后看得到的那几条才有编号。
        看一张要几秒，一次最多看 8 张；每张回一段画面描述，看不了的会告诉你原因（图链接过期了、图太大了、看图那边出错了）。
        用不用、看哪几张由你。

        Args:
            which(string): 要看的编号，用逗号或空格隔开，也可以写范围，例如「3」「3,5,8」「1-6」
        """
        have = (getattr(self, "_fwd_imgs", {}) or {}).get(str(event.unified_msg_origin))
        if not have or not have["urls"]:
            return "没看：这个聊天里还没有带编号的转发图片"
        want: list[int] = []
        for m in re.finditer(r"(\d+)\s*[-~到至]\s*(\d+)|(\d+)", str(which or "")):
            lo = int(m.group(1) or m.group(3))
            hi = int(m.group(2) or lo)
            want += [n for n in range(lo, min(hi, lo + 200) + 1) if n not in want]
        if not want:
            return "没看：编号没看懂，写「[图片#3]」里的数字，例如 3 或 3,5 或 1-6"
        known = [n for n in want if n in have["urls"]]
        miss = [n for n in want if n not in have["urls"]]
        skipped = known[FORWARD_LOOK_MAX:]
        known = known[:FORWARD_LOOK_MAX]
        orig = (self._caption_orig or (None, None))[1]
        if orig is None:
            return "没看：看图这条路没接上（AstrBot 的图片描述没找到）"
        conf = {}
        try:
            conf = self.context.get_config().get("provider_ltm_settings", {}) or {}
        except Exception:
            pass
        this = types.SimpleNamespace(context=self.context)
        pid, prompt = str(conf.get("image_caption_provider_id") or ""), str(conf.get("image_caption_prompt") or "")
        want_pid = str(self.cfg.get("caption_provider") or "").strip()  # 面板「看圖走降智版」
        sem = asyncio.Semaphore(FORWARD_LOOK_PAR)
        res: dict[int, str] = {}

        async def one(n: int):
            async with sem:
                try:
                    cap = await self._icl_caption(orig, this, have["urls"][n], pid, prompt,
                                                  _caption_pid=want_pid, _caption_try=15.0)
                except Exception as e:
                    cap = ICL_UNSEEN.format(why=f"看图出错了（{type(e).__name__}）")
            res[n] = " ".join(str(cap or "").split()) or ICL_UNSEEN.format(why="看图那边没回话")

        tasks = [asyncio.ensure_future(one(n)) for n in known]
        _done, pending = await asyncio.wait(tasks, timeout=FORWARD_LOOK_WAIT)
        for t in pending:
            t.cancel()
        lines = [f"#{n}：{res.get(n) or ICL_UNSEEN.format(why='等太久没看完')}" for n in known]
        if miss:
            lines.append("没有这几个编号：" + "、".join(f"#{n}" for n in miss))
        if skipped:
            lines.append(f"一次最多看 {FORWARD_LOOK_MAX} 张，这几张没看：" + "、".join(f"#{n}" for n in skipped))
        return "\n".join(lines)

    def _mark_stickers(self, event: AstrMessageEvent):
        if not any(isinstance(c, Image) for c in event.get_messages()):
            return
        images, stickers, marks = _count_stickers(event)
        has_text = bool((event.message_str or "").strip())
        logger.info(
            f"[lively_gate] 图片 {images} 张，表情包 {stickers} 张，带文字 {has_text}: {marks}"
        )
        if has_text:
            all_stickers = images > 0 and stickers == images
            event.set_extra(
                "lively_sticker_hint",
                STICKER_WITH_TEXT if all_stickers else TEXT_WITH_IMAGE,
            )
        elif stickers and stickers == images:
            event.set_extra("lively_sticker_hint", STICKER_ONLY)
        else:
            event.set_extra("lively_sticker_hint", IMAGE_ONLY)

    @filter.on_llm_request(priority=5)
    async def sticker_hint(self, event: AstrMessageEvent, req):
        self._take_late_text(event, req)
        try:
            n = _strip_old_images(getattr(req, "contexts", None))
            if n:
                logger.info(
                    f"[lively_gate] 历史里 {n} 张旧图换成了文字: {event.unified_msg_origin}"
                )
        except Exception as e:
            logger.warning(f"[lively_gate] 清理历史图片失败: {e}")
        if self.cfg.get("join_reply_lines", True):
            try:
                _join_reply_lines(getattr(req, "contexts", None))
            except Exception as e:
                logger.warning(f"[lively_gate] 合并历史里的换行失败: {e}")
        if event.get_extra("lively_empty_call"):
            req.extra_user_content_parts.append(
                TextPart(text=self.s.fill(EMPTY_CALL_HINT.format(secs=int(CALL_FIRST_WAIT)))).mark_as_temp()
            )
        if hint := event.get_extra("lively_call_before"):
            req.extra_user_content_parts.append(TextPart(text=self.s.fill(hint)).mark_as_temp())
        hint = event.get_extra("lively_sticker_hint")
        if hint:
            req.extra_user_content_parts.append(TextPart(text=hint).mark_as_temp())
        for text in event.get_extra("lively_forward") or []:
            if text not in (getattr(req, "prompt", "") or ""):  # 已經寫進這條的字就不再帶一遍
                req.extra_user_content_parts.append(TextPart(text=FORWARD_HINT.format(text=text)).mark_as_temp())
        mfaces = event.get_extra("lively_mfaces")
        if mfaces:
            names = "、".join(f"「{n}」" if n else "一个没名字的" for n in mfaces)
            req.extra_user_content_parts.append(
                TextPart(text=self.s.fill(MFACE_HINT.format(names=names))).mark_as_temp()
            )
        if (note := self._tease_note(event)) is not None:
            req.extra_user_content_parts.append(note)
        for h in event.get_extra("lively_rhythm_hints") or []:
            req.extra_user_content_parts.append(TextPart(text=self.s.fill(h)).mark_as_temp())
        try:
            part = self._outbox_part(event)
            if part is not None:
                req.extra_user_content_parts.append(part)
        except Exception as e:
            logger.warning(f"[lively_gate] 带上聊天外发出去的消息失败: {e}")
        if self.cfg.get("group_thread_dm", True) and not _is_beat(event):
            try:
                if event.get_group_id():
                    if event.is_at_or_wake_command:
                        self._thread_note(event, "TA", self._thread_text(event))
                elif part := self._thread_part(event):
                    req.extra_user_content_parts.append(part)
            except Exception as e:
                logger.warning(f"[lively_gate] 群里刚跟 TA 说的没带上: {e}")
        if self.cfg.get("draft_guard", True):
            # 每輪一樣的提醒放 system 最後，命中得到快取；關掉 rules_in_system 就照舊掛在這輪消息後面
            if self.cfg.get("rules_in_system", True):
                system_tail(req, DRAFT_HINT)
            else:
                req.extra_user_content_parts.append(TextPart(text=DRAFT_HINT).mark_as_temp())
        if REVIEW_RE.search(event.message_str or ""):
            req.extra_user_content_parts.append(
                TextPart(text=self.s.fill(REVIEW_HINT)).mark_as_temp()
            )
            logger.info(
                f"[lively_gate] 评价请求，已带上评价提醒: {event.unified_msg_origin}"
            )

    def _take_late_text(self, event: AstrMessageEvent, req):
        """窗口關了之後才到的字，補進這輪的正文"""
        key = event.get_extra("lively_late_key")
        if not key:
            return
        late = self._late.pop(key, None)
        event.set_extra("lively_late_key", None)
        texts = (late or {}).get("texts") or []
        if not texts:
            return
        text = "\n".join(texts)
        event.message_str = "\n".join(t for t in [(event.message_str or "").strip(), text] if t)
        req.prompt = "\n".join(t for t in [(req.prompt or "").strip(), text] if t)
        if event.get_extra("lively_sticker_hint") == IMAGE_ONLY:
            event.set_extra("lively_sticker_hint", TEXT_WITH_IMAGE)
        logger.info(f"[lively_gate] 晚到的 {len(texts)} 段话补进了这一轮: {event.unified_msg_origin}")

    @filter.on_llm_request(priority=-5)
    async def group_context(self, event: AstrMessageEvent, req):
        """改寫 AstrBot 塞進來的群聊背景，見 ICL_HEAD 上面的說明"""
        if not event.get_group_id() or not self.cfg.get("rewrite_group_context", True):
            return
        parts = getattr(req, "extra_user_content_parts", None)
        if parts is None:
            return
        idx = next((i for i, p in enumerate(parts)
                    if isinstance(p, TextPart) and ICL_MARK in (getattr(p, "text", "") or "")), -1)
        called = bool(event.is_at_or_wake_command)
        beat = _is_beat(event)
        if idx < 0 and called and not beat:
            return
        sender = event.get_sender_name() or str(event.get_sender_id() or "")
        text = re.sub(r"\s+", " ", event.message_str or "").strip()[:TRIGGER_MAX] or "[图片或表情]"
        tail = ICL_BEAT if beat else (ICL_CALLED if called else ICL_ACTIVE).format(name=sender, qq=event.get_sender_id(), text=text)
        block = []
        if idx >= 0:
            raw = parts[idx].text
            body = raw.split("--- BEGIN CONTEXT---", 1)[-1].split("--- END CONTEXT ---", 1)[0].strip().splitlines()
            limit = int(self.cfg.get("group_context_lines", ICL_LINES) or ICL_LINES)
            lines = []
            for line in body:
                m = ICL_LINE_RE.match(line.strip())
                if m:
                    lines.append(f"{m.group(2)} {m.group(1)}：{m.group(4).strip()}" + ("（@〈我〉）" if m.group(3) else ""))
                elif line.strip() and lines:
                    lines[-1] += " " + line.strip()  # 一條消息換了行
            keep = int(self.cfg.get("keep_context_lines", KEEP_LINES) or 0)
            if keep > 0 and lines:
                kept = " / ".join(x if len(x) <= KEEP_LINE_MAX else x[:KEEP_LINE_MAX] + "…" for x in lines[-keep:])
                parts.append(TextPart(text=self.s.fill(KEEP_HEAD.format(lines=kept))))
            skipped = max(0, len(lines) - limit)
            lines = lines[-limit:]
            block += [ICL_HEAD, "--- 群聊背景（旧→新）---"]
            if skipped:
                block.append(f"（更早还有 {skipped} 条，省略）")
            block += lines
            block.append("--- 背景结束 ---")
            parts.pop(idx)
        block.append(tail)
        parts.append(TextPart(text=self.s.fill("<system_reminder>" + "\n".join(block) + "</system_reminder>")).mark_as_temp())

    def _on_any_message(self, event: AstrMessageEvent, key: tuple[str, str]):
        """每條放行的消息：記節奏；私聊裡 TA 又說話了，就不用再等 TA 的沉默"""
        umo, sender = key
        if not sender or sender == str(event.get_self_id() or ""):
            return
        dm = not event.get_group_id()
        self.rhythm.on_message(umo, sender, dm=dm)
        if dm:
            task = self._watch.pop(umo, None)
            if task is not None and not task.done():
                task.cancel()

    async def _listen(self, event: AstrMessageEvent, sender: str, is_dm: bool):
        key = (event.unified_msg_origin, sender)
        state = self._listening.get(key)
        now = time.time()
        if state is not None:
            # 正在傾聽這個人：併入第一條，本條不再單獨處理
            text = (event.message_str or "").strip()
            images = [c for c in event.get_messages() if isinstance(c, Image)]
            if text or images:
                state["pieces"].append((now, text or "[图片]"))
            state["images"].extend(images)
            state["last"] = time.monotonic()
            state["wait"] = self.rhythm.wait_for(sender, text)
            event.stop_event()
            return
        if not event.is_at_or_wake_command:
            return
        # 指令（/開頭）、空 @ 已經等過的，不再等
        text = (event.message_str or "").strip()
        if text.startswith("/") or event.get_extra("lively_call_waited"):
            return
        mono = time.monotonic()
        state = {
            "pieces": [(now, text or "[图片]")],
            "images": [],
            "start": mono,
            "last": mono,
            "wait": self.rhythm.wait_for(sender, text),
        }
        self._listening[key] = state
        try:
            while True:
                end = min(state["last"] + state["wait"], state["start"] + MAX_LISTEN)
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(remaining, 0.5))
        finally:
            self._listening.pop(key, None)
        pieces = state["pieces"]
        extra = [t for _, t in pieces[1:] if t and t != "[图片]"]
        if extra or state["images"]:
            event.message_str = "\n".join([t for t in [text, *extra] if t])
            if extra:
                event.message_obj.message.append(Plain("\n" + "\n".join(extra)))
            event.message_obj.message.extend(state["images"])
            logger.info(
                f"[lively_gate] 倾听合并 {len(pieces)} 条，"
                f"等待 {time.monotonic() - state['start']:.1f}s: {event.unified_msg_origin}"
            )
        hints = pause_hints(self.rhythm, sender, pieces, time.time(), self.name)
        if hints:
            event.set_extra("lively_rhythm_hints", hints)
            logger.info(f"[lively_gate] 停顿提醒 {hints}: {event.unified_msg_origin}")

    # ---------- 聊天流程外發出去的話 ----------
    def _outbox_part(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        now = time.time()
        since = max(float(self._outbox_seen.get(umo) or 0), now - OUTBOX_TTL)
        items = read_outbox(umo, since)
        if not items:
            return None
        self._outbox_seen[umo] = max(float(d.get("ts") or 0) for d in items)
        self._outbox_seen = {k: v for k, v in self._outbox_seen.items() if v > now - OUTBOX_TTL}
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._outbox_file.write_text(json.dumps(self._outbox_seen), "utf-8")
        except Exception as e:
            logger.warning(f"[lively_gate] 保存 outbox 进度失败: {e}")
        sent, latest, back = [], {}, []
        for d in items:
            kind = str(d.get("kind") or "")
            if kind.split(":", 1)[0] == BACKSTAGE_KIND:
                back.append(d)
            elif kind == THOUGHT_KIND:
                if float(d.get("ts") or 0) > now - THOUGHT_TTL:
                    latest.pop(kind, None)
                    latest[kind] = d
            elif not kind.startswith(MISSED_KIND):
                sent.append(d)
            elif float(d.get("ts") or 0) > now - MISSED_TTL:
                base = kind.removesuffix(":done")
                latest.pop(base, None)
                latest[base] = d  # 同一件事記了好幾次（心跳每跳都想回、都被擋）：只留最新的
        missed = [d for d in latest.values() if not str(d.get("kind")).endswith(":done")]
        sent, missed, back = sent[-OUTBOX_MAX:], missed[-MISSED_MAX:], back[-OUTBOX_MAX:]
        blocks = []
        if sent:
            lines = [self.s.fill(OUTBOX_HEAD)]
            for d in sent:
                when = datetime.fromtimestamp(float(d.get("ts") or 0)).strftime("%H:%M")
                kind = f"［{d['kind']}］" if d.get("kind") else ""
                lines.append(f"· {when}{kind}{self.s.fill(d.get('text', ''))}")
            blocks.append("\n".join(lines))
        if back:
            blocks.append("\n".join([self.s.fill(BACKSTAGE_HEAD)] + [
                f"· {datetime.fromtimestamp(float(d.get('ts') or 0)).strftime('%H:%M')} {self.s.fill(d.get('text', ''))}" for d in back]))
        if missed:
            blocks.append("\n".join([self.s.fill(MISSED_HEAD)] + [
                f"· {datetime.fromtimestamp(float(d.get('ts') or 0)).strftime('%H:%M')} {self.s.fill(d.get('text', ''))}" for d in missed]))
        if not blocks:
            return None
        logger.info(f"[lively_gate] 带上了 {len(sent)} 条聊天外发出去的消息、{len(back)} 条后台的事、{len(missed)} 条看 QQ 时没说出口的: {umo}")
        # 不標成臨時：跟著這輪存進對話歷史，以後翻回來也知道當時發過什麼、想過什麼
        return TextPart(text="\n\n".join(blocks))

    # ---------- 群裡剛跟 TA 說的，TA 轉到私聊時帶上（THREAD_HEAD 上面有來由） ----------
    def _thread_text(self, event: AstrMessageEvent) -> str:
        """TA 這條叫〈我〉的話：引用了哪條、說了什麼、帶了幾張圖（群聊背景給圖寫過描述的帶上描述）"""
        bits = []
        for c in event.get_messages():
            if isinstance(c, Reply):
                q = re.sub(r"\s+", " ", str(c.message_str or "")).strip()
                who = str(c.sender_nickname or "")
                if str(c.sender_id or "") == str(event.get_self_id() or ""):
                    who = self.s.fill("〈我〉")
                bits.append(f"（引用{who}：「{q[:80] or '图片'}」）")
            elif isinstance(c, Image):
                cap = self.caption_of(getattr(c, "url", "") or getattr(c, "file", ""))
                bits.append(f"[图片：{cap[:80]}]" if cap else "[图片]")
        text = (event.message_str or "").strip()
        return " ".join(b for b in bits + [text] if b)

    def _thread_note(self, event: AstrMessageEvent, who: str, text: str):
        qq = str(event.get_sender_id() or "")
        text = re.sub(r"\s*\n\s*", " / ", str(text or "")).strip()
        if not qq or not text:
            return
        if len(text) > THREAD_TEXT_MAX:
            text = text[:THREAD_TEXT_MAX] + "…"
        grp = getattr(event.message_obj, "group", None)
        rows = self._threads.setdefault("rows", {}).setdefault(qq, [])
        rows.append({"ts": round(time.time(), 3), "gid": str(event.get_group_id()), "umo": event.unified_msg_origin,
                     "gname": str(getattr(grp, "group_name", "") or ""), "who": who, "text": text})
        del rows[:-THREAD_KEEP]
        self._thread_save()

    def _thread_sent(self, event: AstrMessageEvent):
        """〈我〉在群裡回 TA 的（只記這個人叫過〈我〉、還在帶的時間裡的）"""
        if _is_beat(event):
            return
        rows = self._threads.get("rows", {}).get(str(event.get_sender_id() or ""))
        if not rows or rows[-1]["gid"] != str(event.get_group_id()) or time.time() - rows[-1]["ts"] > THREAD_HOURS * 3600:
            return
        result = event.get_result()
        chain = result.chain if result and isinstance(result.chain, list) else []
        text = " ".join(c.text.strip() for c in chain if isinstance(c, Plain) and c.text.strip())
        n = sum(isinstance(c, Image) for c in chain)
        text = " ".join(t for t in ["[图片]" * n, text] if t)
        if text:
            self._thread_note(event, "我", text)

    @_on_tool_respond()
    async def thread_tool(self, event: AstrMessageEvent, tool, tool_args, tool_result):
        """群裡回 TA 那輪調的工具（畫了什麼、發了什麼），一起記進 TA 那段（16:21 她在群裡畫的那張私聊這邊不知道）"""
        if not event.get_group_id() or not self.cfg.get("group_thread_dm", True) or _is_beat(event):
            return
        try:
            rows = self._threads.get("rows", {}).get(str(event.get_sender_id() or ""))
            if not rows or rows[-1]["gid"] != str(event.get_group_id()) or time.time() - rows[-1]["ts"] > THREAD_HOURS * 3600:
                return
            parts = getattr(tool_result, "content", None) or []
            res = " ".join(str(getattr(c, "text", "") or "") for c in parts).strip() or str(tool_result or "")
            res = re.split(r"\n|（参考图", res, maxsplit=1)[0].strip()
            args = "，".join(f"{k}={str(v)[:100]}" for k, v in (tool_args or {}).items() if str(v).strip())
            name = str(getattr(tool, "name", "") or tool)
            self._thread_note(event, "工具", f"［调了 {name}（{args[:160]}）］{res[:100]}")
        except Exception as e:
            logger.warning(f"[lively_gate] 记群里调的工具失败: {e}")

    def _thread_save(self):
        now = time.time()
        rows = self._threads.get("rows", {})
        for qq in [q for q, r in rows.items() if not r or now - r[-1]["ts"] > THREAD_HOURS * 3600 * 3]:
            rows.pop(qq, None)
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            (DATA_DIR / THREAD_FILE).write_text(json.dumps(self._threads, ensure_ascii=False), "utf-8")
        except Exception as e:
            logger.warning(f"[lively_gate] 保存群里的对话失败: {e}")

    def _thread_part(self, event: AstrMessageEvent):
        """私聊：TA 在群裡剛跟〈我〉說的、私聊這邊還沒帶過的。不標成臨時，跟著這輪存進歷史"""
        qq = str(event.get_sender_id() or "")
        rows = self._threads.get("rows", {}).get(qq) or []
        now = time.time()
        if not rows or now - rows[-1]["ts"] > THREAD_HOURS * 3600:
            return None
        seen = float(self._threads.setdefault("seen", {}).get(qq) or 0)
        new = [r for r in rows if r["ts"] > seen and now - r["ts"] <= THREAD_HOURS * 3600][-THREAD_MAX:]
        if not new:
            return None
        self._threads["seen"][qq] = new[-1]["ts"]
        blocks = []
        for gid in dict.fromkeys(r["gid"] for r in new):
            mine = [r for r in new if r["gid"] == gid]
            lines = [dict(ts=r["ts"], line=f"{'TA' if r['who'] == 'TA' else '〈我〉'}：{r['text']}") for r in mine]
            # 那段時間〈我〉在那個群用工具發的（畫的圖、轉的消息）
            for d in read_outbox(mine[-1]["umo"], mine[0]["ts"] - 1):
                kind = str(d.get("kind") or "")
                if kind.split(":", 1)[0] == BACKSTAGE_KIND or kind.startswith(MISSED_KIND) or kind == THOUGHT_KIND:
                    continue
                lines.append(dict(ts=float(d.get("ts") or 0), line=f"〈我〉［{kind or '发的'}］：{d.get('text', '')}"))
            lines.sort(key=lambda x: x["ts"])
            gname = next((r["gname"] for r in reversed(mine) if r.get("gname")), "") or gid
            blocks.append("\n".join([self.s.fill(THREAD_HEAD.format(group=gname, gid=gid))] + [
                f"· {datetime.fromtimestamp(x['ts']).strftime('%H:%M')} {self.s.fill(x['line'])}" for x in lines]))
        self._thread_save()
        logger.info(f"[lively_gate] 私聊带上了 TA 刚在群里跟{self.name or '她'}说的 {len(new)} 句: {event.unified_msg_origin}")
        return TextPart(text="\n\n".join(blocks))

    # ---------- 沉默 ----------
    @filter.after_message_sent()
    async def on_sent(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        replied = getattr(self, "_replied", None)
        if replied is None:
            replied = self._replied = {}
        replied[(umo, str(event.get_sender_id() or ""))] = time.time()
        self.rhythm.on_bot_sent(umo)
        if event.get_group_id() and self.cfg.get("group_thread_dm", True):
            try:
                self._thread_sent(event)
            except Exception as e:
                logger.warning(f"[lively_gate] 记群里回 TA 的话失败: {e}")
        arm = self._arm.pop(umo, None)
        if event.get_group_id() or not arm or time.time() - arm["ts"] > SILENCE_ARM_TTL:
            return
        if str(self.cfg.get("silence_followup", "log") or "off") == "off":
            return
        old = self._watch.pop(umo, None)
        if old is not None and not old.done():
            old.cancel()
        self._watch[umo] = asyncio.create_task(self._silence_watch(umo, arm["qq"], time.time()))

    def _quiet_now(self) -> bool:
        spec = str(self.cfg.get("silence_quiet_hours", "1-8") or "")
        m = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", spec)
        if not m:
            return False
        a, b, h = int(m.group(1)), int(m.group(2)), datetime.now().hour
        return a <= h < b if a <= b else (h >= a or h < b)

    async def _silence_watch(self, umo: str, qq: str, sent_at: float):
        try:
            wait = self.rhythm.silence_after(
                qq,
                float(self.cfg.get("silence_k", SILENCE_K) or SILENCE_K),
                float(self.cfg.get("silence_min", SILENCE_MIN) or SILENCE_MIN),
                float(self.cfg.get("silence_max", SILENCE_MAX) or SILENCE_MAX),
            )
            await asyncio.sleep(wait)
            if self.rhythm.last_msg.get((umo, qq), 0) > sent_at or self._quiet_now():
                return
            day = datetime.now().strftime("%Y-%m-%d")
            d, n = self._silence_count.get(qq, ("", 0))
            n = n if d == day else 0
            if n >= int(self.cfg.get("silence_daily", SILENCE_DAILY) or SILENCE_DAILY):
                return
            self._silence_count[qq] = (day, n + 1)
            await self._silence_say(umo, qq, time.time() - sent_at, sent_at)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[lively_gate] 沉默时想说的话没弄成: {type(e).__name__} {e}")
        finally:
            if self._watch.get(umo) is asyncio.current_task():
                self._watch.pop(umo, None)

    async def _silence_say(self, umo: str, qq: str, secs: float, sent_at: float):
        mode = str(self.cfg.get("silence_followup", "log") or "off")
        prov = self.context.get_using_provider(umo=umo)
        if prov is None:
            return
        cm = self.context.conversation_manager
        cid = await cm.get_curr_conversation_id(umo)
        conv = await cm.get_conversation(umo, cid) if cid else None
        try:
            history = json.loads(conv.history) if conv and conv.history else []
        except Exception:
            history = []
        contexts = _plain_history(history)[-SILENCE_HISTORY:]
        if not contexts:
            return
        lag, known = self.rhythm.lag(qq)
        usual = SILENCE_USUAL.format(lag=fmt_secs(lag)) if known else ""
        system = (self.s.persona_prompt() or "") + self.s.fill(SILENCE_SYSTEM.format(secs=fmt_secs(secs), usual=usual))
        r = await asyncio.wait_for(
            prov.text_chat(prompt=f"（TA 还没回，已经 {fmt_secs(secs)} 了）", contexts=contexts,
                           system_prompt=system, session_id=uuid.uuid4().hex),
            SILENCE_TIMEOUT,
        )
        text = (getattr(r, "completion_text", "") or "").strip()
        text = MEME_TAG_RE.sub("", pick_final(_clean(text)) or "").strip()
        text = re.sub(r"(?:<<|《《|＜＜|【bond)[^\n]*", "", text).strip()
        skip = text.strip("。.!！ ") in SKIP_WORDS or text.startswith("不说")
        self._log_silence(umo=umo, qq=qq, secs=round(secs), mode=mode, text="" if skip else text[:200])
        if skip:
            logger.info(f"[lively_gate] TA {fmt_secs(secs)}没说话，〈我〉想了想先不打扰: {umo}")
            return
        if mode != "on":
            logger.info(f"[lively_gate] TA {fmt_secs(secs)}没说话，〈我〉想说（只记录）：{text[:60]}")
            return
        if self.rhythm.last_msg.get((umo, qq), 0) > sent_at:
            return  # 想的時候 TA 回了
        await self.context.send_message(umo, MessageChain().message(text))
        self.rhythm.on_bot_sent(umo)
        try:
            await cm.add_message_pair(
                cid,
                {"role": "user", "content": self.s.fill(SILENCE_NOTE.format(secs=fmt_secs(secs)))},
                {"role": "assistant", "content": text},
            )
        except Exception as e:
            logger.warning(f"[lively_gate] 沉默时说的话写进聊天记录失败: {e}")
        logger.info(f"[lively_gate] TA {fmt_secs(secs)}没说话，〈我〉又说了一句：{text[:60]}")

    def _log_silence(self, **data):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with (DATA_DIR / "silence.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": int(time.time()), **data}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ---------- 擦邊表情包把關 ----------
    def _may_tease(self, event: AstrMessageEvent) -> bool:
        """正在說話的人夠不夠熟（主人可以；其他人好感度到親近、態度正常、沒嫌〈我〉煩）。問不到 bond 就當不夠熟。
        不夠熟時把原因記下（_tease_dropped），下一輪告訴她那張沒配上、為什麼：以前是悄悄拿掉，她以為發出去了"""
        meta = self.context.get_registered_star("astrbot_plugin_lively_bond")
        b = getattr(meta, "star_cls", None) if meta and getattr(meta, "activated", True) else None
        why = "问不到〈我〉和 TA 熟不熟"
        if b and hasattr(b, "relation"):
            try:
                r = b.relation(str(event.get_sender_id() or ""))
                if r.get("can_reach"):
                    return True
                why = str(r.get("reach_why") or "TA 跟〈我〉还不够熟")
            except Exception as e:
                logger.warning(f"[lively_gate] 问 bond 的关系失败: {e}")
        who = getattr(event, "get_sender_name", lambda: "")() or event.get_sender_id()
        self.__dict__.setdefault("_tease_dropped", {})[event.unified_msg_origin] = (time.time(), f"{who}：{why}")
        return False

    def _tease_note(self, event: AstrMessageEvent):
        """上一輪想配的擦邊表情包沒配上：照實說一句（半小時內、只說一次）"""
        got = self.__dict__.setdefault("_tease_dropped", {}).pop(event.unified_msg_origin, None)
        if not got or time.time() - got[0] > 1800:
            return None
        return TextPart(text=self.s.fill(
            f"（上一条〈我〉写的 &&tease&& 表情包没配上、没发出去：tease 这类只给好感度到亲近、态度正常、"
            f"没嫌〈我〉烦的人配，{got[1]}）")).mark_as_temp()

    def _memer(self):
        meta = self.context.get_registered_star("meme_manager")
        return getattr(meta, "star_cls", None) if meta and getattr(meta, "activated", True) else None

    # 排在表情包插件（99999）之前：它看到 &&tease&& 就發圖了
    @filter.on_llm_response(priority=99998)
    async def tease_guard(self, event: AstrMessageEvent, resp):
        text = getattr(resp, "completion_text", None) if resp else None
        if not text or not TEASE_RE.search(text) or self._may_tease(event):
            return
        resp.completion_text = TEASE_RE.sub("", text)
        logger.info(f"[lively_gate] 擦边表情包只对很熟的人用，拿掉了: {event.unified_msg_origin}")

    # ---------- 起草外洩 ----------
    # 排在 bond 取標記（100001）和超級模式改寫拒答（100000）之後、表情包插件之前
    @filter.on_llm_response(priority=99998)
    async def draft_response(self, event: AstrMessageEvent, resp):
        if not self.cfg.get("draft_guard", True):
            return
        text = getattr(resp, "completion_text", None) if resp else None
        if not text or not looks_like_draft(text):
            return
        final = extract_final(text)
        how = "挑出了终稿"
        if not final:
            final = await self._rewrite_draft(event, text)
            how = "请模型重写了一句" if final else "没挑出来，不发"
        logger.warning(
            f"[lively_gate] 回复像起草稿（{len(text)} 字），{how}: {event.unified_msg_origin}\n"
            + text[:600]
        )
        event.set_extra("lively_draft_fixed", final or "")
        resp.completion_text = final or ""

    async def _rewrite_draft(self, event: AstrMessageEvent, text: str) -> str | None:
        try:
            prov = self.context.get_using_provider(umo=event.unified_msg_origin)
            if prov is None:
                return None
            r = await asyncio.wait_for(
                prov.text_chat(
                    prompt=text,
                    system_prompt=DRAFT_REWRITE_SYSTEM,
                    session_id=uuid.uuid4().hex,
                    persist=False,
                ),
                DRAFT_REWRITE_TIMEOUT,
            )
            out = (getattr(r, "completion_text", "") or "").strip()
        except Exception as e:
            logger.warning(f"[lively_gate] 起草稿重写失败: {type(e).__name__} {e}")
            return None
        if not out or looks_like_draft(out):
            return None
        return out

    # 存進聊天記錄前，助手那句也換成終稿，免得下一輪照著草稿的樣子寫
    @filter.on_agent_done(priority=99998)
    async def draft_history(self, event: AstrMessageEvent, run_context, resp):
        """這一輪每一步都看（調工具前那步帶的字也發出去了）：草稿換成終稿，前一步說過又抄一遍的行拿掉，和實際發的一致"""
        if not self.cfg.get("draft_guard", True):
            return
        fixed = event.get_extra("lively_draft_fixed")
        steps_seen: list[list[str]] = []

        def tidy(t: str, last: bool) -> str:
            if looks_like_draft(t):
                t = extract_final(t) or (fixed if last and fixed is not None else "") or ""
            seen = {f for x in steps_seen for f in x}
            flats = [f for f in map(_flat, t.split("\n")) if f]
            extra = [f for f in flats if f not in seen]
            if any(x and all(f in flats for f in x) for x in steps_seen) and len(extra) == 1 and len(extra[0]) <= TURN_RESEND_TAIL:
                t = ""  # 和發送時一樣：整段重抄＋一行短句，這一步沒發
            keep = [l for l in t.split("\n") if not (len(_flat(l)) >= TURN_REPEAT_MIN and _flat(l) in seen)]
            mine = [_flat(l) for l in keep if len(_flat(l)) >= TURN_REPEAT_MIN]
            if mine:
                steps_seen.append(mine)
            return "\n".join(keep).strip() or (DRAFT_DROPPED if last else "")

        try:
            steps = _this_turn(run_context.messages)
            for n, msg in enumerate(steps):
                last = n == len(steps) - 1
                if isinstance(msg.content, str):
                    if msg.content:
                        msg.content = tidy(msg.content, last)
                elif isinstance(msg.content, list):
                    for part in msg.content:
                        if isinstance(part, TextPart) and part.text:
                            part.text = tidy(part.text, last)
                    msg.content = [p for p in msg.content if not (isinstance(p, TextPart) and not p.text)]
        except Exception as e:
            logger.error(f"[lively_gate] 清理历史里的起草稿失败: {e}")

    # 兜底：分段回覆會按換行切成一串氣泡，在它之前（裝飾鉤子都在分段前）把整段再看一次；
    # 排在 bond 的標記兜底（100001）之後，殘留的 <<好感…>> 先讓它清掉
    @filter.on_decorating_result(priority=100000)
    async def draft_result(self, event: AstrMessageEvent):
        if not self.cfg.get("draft_guard", True):
            return
        result = event.get_result()
        if not result or not isinstance(result.chain, list):
            return
        plains = [c for c in result.chain if isinstance(c, Plain)]
        text = "\n".join(c.text for c in plains)
        if not looks_like_draft(text):
            return
        final = extract_final(text) or event.get_extra("lively_draft_fixed") or ""
        logger.warning(
            f"[lively_gate] 发送前拦下起草稿，{'换成终稿' if final else '整段不发'}: {event.unified_msg_origin}"
        )
        chain, placed = [], False
        for comp in result.chain:
            if isinstance(comp, Plain):
                if final and not placed:
                    chain.append(Plain(final))
                    placed = True
                continue
            chain.append(comp)
        if not any(not isinstance(c, Plain) or c.text.strip() for c in chain):
            event.stop_event()
            return
        result.chain = chain

    # 起草稿之後：同一輪前一步（調工具之前）已經發出去的行，這一步整行又抄一遍就不再發
    @filter.on_decorating_result(priority=99997)
    async def no_repeat_in_turn(self, event: AstrMessageEvent):
        if not self.cfg.get("draft_guard", True):
            return
        result = event.get_result()
        if not result or not isinstance(result.chain, list):
            return
        sends = [list(x) for x in (event.get_extra("lively_turn_sends") or [])]
        sent = {f for x in sends for f in x}
        # 前面某一步發過的整段又原樣抄了一遍，後面只多一行短句：那行多半是沒包進標記的「记住」
        # （10-29 15:19「让本鱼自己去他空间相册翻绘本」、15:10「手绘一张一亿 token 的鲸元券塞给本鱼」），這一步整個不發
        flats = [f for c in result.chain if isinstance(c, Plain) for f in map(_flat, c.text.split("\n")) if f]
        extra = [f for f in flats if f not in sent]
        resend = any(x and all(f in flats for f in x) for x in sends) and len(extra) == 1 and len(extra[0]) <= TURN_RESEND_TAIL
        chain, dropped, kept = [], [], []
        for comp in result.chain:
            if isinstance(comp, Plain):
                lines = []
                for l in comp.text.split("\n"):
                    f = _flat(l)
                    if (len(f) >= TURN_REPEAT_MIN and f in sent) or (resend and f):
                        dropped.append(l)
                        continue
                    lines.append(l)
                    if len(f) >= TURN_REPEAT_MIN:
                        kept.append(f)
                text = "\n".join(lines).strip()
                if not text:
                    continue
                comp = Plain(text) if text != comp.text else comp
            chain.append(comp)
        if kept:
            event.set_extra("lively_turn_sends", sends + [kept])
        if not dropped:
            return
        logger.warning(f"[lively_gate] 这一轮前面已经发过的 {len(dropped)} 行，又抄了一遍，不再发: {event.unified_msg_origin}")
        # 整段都是重複的：清空就好（AstrBot 遇到空消息跳過這次發送），不 stop_event，免得中間那步把後面的工具也停了
        result.chain = chain

    # 排在 no_repeat_in_turn 之後：記下這一步真的要發的字。這一步要是接著調工具，工具結果後面照實寫上（tool_said_note）
    @filter.on_decorating_result(priority=99996)
    async def note_step_said(self, event: AstrMessageEvent):
        result = event.get_result()
        if not result or not isinstance(result.chain, list):
            return
        said = "\n".join(c.text.strip() for c in result.chain if isinstance(c, Plain) and c.text.strip())
        if said:
            event.set_extra("lively_turn_said", list(event.get_extra("lively_turn_said") or []) + [said])

    # 排在其他插件（表情包 99999、起草稿 100000、超級模式清掃 100）之後，分段之前
    @filter.on_decorating_result(priority=1)
    async def space_breaks(self, event: AstrMessageEvent):
        """她用空格隔開的兩段話拆成兩條發：歷史裡的回覆合成一行（join_reply_lines）以後，她想分兩條時會寫成「A B」，
        分段只認換行，就擠在一個氣泡裡（10-25 16:45「在呢，本鱼一直在，没坏 你这测试也测得太勤了」）"""
        if not self.cfg.get("join_reply_lines", True):
            return
        result = event.get_result()
        if not result or not isinstance(result.chain, list) or not result.is_model_result():
            return
        for comp in result.chain:
            if isinstance(comp, Plain) and comp.text:
                comp.text = _space_breaks(comp.text)

    # ---------- 群聊背景的圖片描述 ----------
    def _patch_icl_caption(self):
        """AstrBot 群聊上下文記錄每條消息時，當場給圖片要描述、不設超時（模型那邊卡住就等滿 120 秒，
        這期間整條消息流水線都停著，被叫到也回不了）。包一層超時，超時記成「图片没看清」。

        它還把 QQ 給的原圖直接送去（直接發給〈我〉的圖 AstrBot 會先轉檔，背景這條不會），
        webp、png、jpeg、gif 以外的格式模型拒收，失敗時那張圖在背景裡整個不見。
        這裡先下載、轉成模型認的格式再送；轉不了、下載不了、描述出錯的，寫成「没看到这张图：原因」。"""
        try:
            from astrbot.builtin_stars.astrbot.group_chat_context import GroupChatContext
        except Exception as e:
            logger.info(f"[lively_gate] 没找到群聊上下文模块，图片描述超时不处理: {e}")
            return
        orig = GroupChatContext.get_image_caption
        if getattr(orig, "_lively_wrapped", False):
            orig = orig._lively_orig
        gate = self

        async def get_image_caption(this, *args, **kwargs):
            timeout = float(gate.cfg.get("icl_caption_timeout", ICL_CAPTION_TIMEOUT) or 0)
            # 面板「看圖走降智版」：開著時先請降智版網關看，出錯/超時再拿原來的模型重看一次
            want = str(gate.cfg.get("caption_provider") or "").strip()
            kw = dict(kwargs)
            if want:
                kw["_caption_pid"] = want
            if timeout > 0:
                kw["_caption_try"] = max(3.0, timeout * 0.6)  # 單次上限，留時間給備用模型
            if timeout <= 0:
                cap = await gate._icl_caption(orig, this, *args, **kw)
            else:
                try:
                    cap = await asyncio.wait_for(gate._icl_caption(orig, this, *args, **kw), timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[lively_gate] 群聊背景的图片描述超过 {timeout:.0f} 秒，先记成「{ICL_CAPTION_FAILED}」")
                    cap = ICL_CAPTION_FAILED
            gate._note_caption(args[0] if args else kwargs.get("image_url"), cap)
            return cap

        get_image_caption._lively_wrapped = True
        get_image_caption._lively_orig = orig
        GroupChatContext.get_image_caption = get_image_caption
        self._caption_orig = (GroupChatContext, orig)

    def ack_text(self) -> str:
        return self.s.fill(COMPRESS_ACK)

    def fix_acks(self, messages) -> int:
        """把壓縮插的那句英文換成中文備註，回換了幾句"""
        n = 0
        for m in messages or []:
            if getattr(m, "role", None) == "assistant" and getattr(m, "content", None) == COMPRESS_ACK_EN:
                m.content = self.ack_text()
                n += 1
        return n

    def _patch_compress_ack(self):
        try:
            from astrbot.core.agent.context.compressor import LLMSummaryCompressor
        except Exception as e:
            logger.warning(f"[lively_gate] 找不到 AstrBot 的压缩器，压缩插的英文那句换不了: {e}")
            return
        orig = LLMSummaryCompressor.__call__
        if getattr(orig, "_lively_wrapped", False):  # 插件重載：包在原來的上面，不要一層層疊
            orig = orig._lively_orig
        gate = self

        async def __call__(this, messages, *args, **kwargs):
            out = await orig(this, messages, *args, **kwargs)
            try:
                gate.fix_acks(out)
            except Exception as e:
                logger.warning(f"[lively_gate] 换压缩插的英文那句失败: {e}")
            return out

        __call__._lively_wrapped = True
        __call__._lively_orig = orig
        LLMSummaryCompressor.__call__ = __call__
        self._compress_orig = (LLMSummaryCompressor, orig)

    def tool_said_note(self, event, step=None) -> str:
        """這一輪已經發出去的話（note_step_said 記的），接在每一步第一個工具結果後面，同一步別的工具不再帶。
        step 是工具循環的第幾步（拿不到就只在有新發出去的話時帶）"""
        if event is None or not self.cfg.get("tool_said_note", True):
            return ""
        said = list(event.get_extra("lively_turn_said") or [])
        last = event.get_extra("lively_said_at") or (None, 0)
        if not said or (step is not None and step == last[0]) or (step is None and len(said) <= last[1]):
            return ""
        event.set_extra("lively_said_at", (step, len(said)))
        text = "".join(f"「{t}」" for t in said)
        if len(text) > TOOL_SAID_MAX:
            text = "…" + text[-TOOL_SAID_MAX:]
        return "\n\n" + TOOL_SAID_NOTE.format(said=text)

    @staticmethod
    def end_turn_if_asked(runner, tool_name):
        """工具在 event 上記了 lively_end_turn（例如發指定表情包發成了）：這一輪到這裡結束，不再讓模型寫工具回來那一步。
        跟 AstrBot 工具沒回傳、自己發完消息時一樣（同一個地方轉 DONE）；這一步其他工具的結果照樣寫進對話"""
        try:
            event = runner.run_context.context.event
            if not event or event.get_extra("lively_end_turn") != tool_name:
                return
            event.set_extra("lively_end_turn", None)
            from astrbot.core.agent.runners import tool_loop_agent_runner as tl
            runner._transition_state(tl.AgentState.DONE)
            if getattr(runner, "stats", None) is not None:
                runner.stats.end_time = time.time()
            logger.info(f"[lively_gate] {tool_name} 做完了，这一轮到这里结束")
        except Exception as e:
            logger.warning(f"[lively_gate] 工具做完想结束这一轮，没结束成: {e}")

    def _patch_tool_said(self):
        """工具結果最後都會接上 _build_repeated_tool_call_guidance 的字（平常是空的），包一層接上 tool_said_note。
        插件鉤子 on_llm_tool_respond 在結果寫進對話之後才叫，改不到結果"""
        try:
            from astrbot.core.agent.runners.tool_loop_agent_runner import ToolLoopAgentRunner
        except Exception as e:
            logger.warning(f"[lively_gate] 找不到 AstrBot 的工具循环，调工具前说过的话没法告诉她: {e}")
            return
        orig = getattr(ToolLoopAgentRunner, "_build_repeated_tool_call_guidance", None)
        if orig is None:
            logger.warning("[lively_gate] 工具循环里没有 _build_repeated_tool_call_guidance，调工具前说过的话没法告诉她")
            return
        if getattr(orig, "_lively_wrapped", False):
            orig = orig._lively_orig
        gate = self

        def guidance(this, tool_name, streak):
            out = orig(this, tool_name, streak)
            gate.end_turn_if_asked(this, tool_name)
            try:
                note = gate.tool_said_note(this.run_context.context.event, getattr(this, "_step_budget_used", None))
            except Exception as e:
                logger.warning(f"[lively_gate] 给工具结果接上调工具前说过的话失败: {e}")
                note = ""
            if note:
                logger.info(f"[lively_gate] 工具 {tool_name} 的结果后面写上了：这一轮已经发出去的话")
            return out + note

        guidance._lively_wrapped = True
        guidance._lively_orig = orig
        ToolLoopAgentRunner._build_repeated_tool_call_guidance = guidance
        self._tool_said_orig = (ToolLoopAgentRunner, orig)

    def _patch_tool_image(self):
        """工具結果落進對話之前，把 AstrBot 寫死的「看完滿意就發給用戶」換成只講事實的一句（只動工具自己說「不会发给谁」的）"""
        try:
            from astrbot.core.agent.runners.tool_loop_agent_runner import ToolLoopAgentRunner
        except Exception as e:
            logger.warning(f"[lively_gate] 找不到 AstrBot 的工具循环，工具带图时那句「发给用户」没法换: {e}")
            return
        orig = getattr(ToolLoopAgentRunner, "_materialize_large_tool_result", None)
        if orig is None:
            logger.warning("[lively_gate] 工具循环里没有 _materialize_large_tool_result，工具带图时那句「发给用户」没法换")
            return
        if getattr(orig, "_lively_wrapped", False):
            orig = orig._lively_orig

        async def materialize(this, *, tool_call_id, content):
            try:
                if isinstance(content, str) and TOOL_IMG_SELF_RE.search(content):
                    new = TOOL_IMG_HINT_RE.sub(lambda m: TOOL_IMG_NOTE.format(m.group(1)), content)
                    if new != content:
                        logger.info("[lively_gate] 工具带图的结果里，AstrBot 那句「发给用户」换成了只讲事实的一句")
                        content = new
            except Exception as e:
                logger.warning(f"[lively_gate] 换工具带图结果里那句失败: {e}")
            return await orig(this, tool_call_id=tool_call_id, content=content)

        materialize._lively_wrapped = True
        materialize._lively_orig = orig
        ToolLoopAgentRunner._materialize_large_tool_result = materialize
        self._tool_image_orig = (ToolLoopAgentRunner, orig)

    @staticmethod
    def _image_key(url) -> str:
        """同一張圖在消息事件和 QQ 歷史裡的鏈接 rkey 會不一樣，fileid 一樣"""
        url = str(url or "")
        m = re.search(r"[?&]fileid=([^&]+)", url)
        return m.group(1) if m else url.split("?", 1)[0]

    def _note_caption(self, url, cap):
        key = self._image_key(url)
        if not key or not isinstance(cap, str) or not cap.strip():
            return
        caps = getattr(self, "_captions", None)
        if caps is None:
            caps = self._captions = {}
        caps[key] = cap.strip()
        while len(caps) > CAPTION_KEEP:
            caps.pop(next(iter(caps)))

    def caption_of(self, url) -> str:
        """群聊背景給這張圖寫過的描述（自主插件發完複查用）；沒有就空"""
        return getattr(self, "_captions", {}).get(self._image_key(url), "")

    async def _icl_caption(self, orig, this, image_url, *args, **kwargs):
        want = str(kwargs.pop("_caption_pid", "") or "")
        try_timeout = kwargs.pop("_caption_try", None)
        if MFACE_HOST in str(image_url):
            name = getattr(self, "_mface_names", {}).get(str(image_url), "")
            return MFACE_SEEN.format(name=name) if name else MFACE_NAMELESS
        try:
            from pathlib import Path
            from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
            from astrbot.core.utils.media_utils import (
                MODEL_IMAGE_MAX_INPUT_BYTES,
                ImageInputTooLargeError,
                MediaResolver,
                prepare_model_image,
            )
        except Exception:
            return await orig(this, image_url, *args, **kwargs)  # 舊版 AstrBot 沒有這些，照原樣送
        too_big = ICL_UNSEEN.format(why=f"图太大了（超过 {MODEL_IMAGE_MAX_INPUT_BYTES // (1024 * 1024)} MB）")
        try:
            resolver = MediaResolver(image_url, media_type="image").as_path()
            source = await resolver.__aenter__()
        except Exception as e:
            logger.warning(f"[lively_gate] 群聊背景的图片没下载下来: {type(e).__name__} {e}")
            return ICL_UNSEEN.format(why="图没下载下来（链接可能过期了）")
        try:
            local = source.path
            if local.stat().st_size > MODEL_IMAGE_MAX_INPUT_BYTES:
                return too_big
            with open(local, "rb") as f:
                head = f.read(32)
            try:
                prepared = await prepare_model_image(
                    str(local), max_size=self._icl_max_size(), output_dir=Path(get_astrbot_temp_path())
                )
            except ImageInputTooLargeError:
                return too_big
            if not prepared:
                why = unreadable_why(head)
                logger.warning(f"[lively_gate] 群聊背景的图片转不了格式，记成「{ICL_UNSEEN.format(why=why)}」")
                return ICL_UNSEEN.format(why=why)
            path, _montage, cleanup, _original = prepared
            # 降智版先看，看不懂/出错/超时再拿原来的模型重看一次（面板「看圖走降智版」）
            pids = [want] if want else []
            fallback = str(args[0] if args else kwargs.get("image_caption_provider_id") or "")
            if fallback not in pids:
                pids.append(fallback)
            try:
                for i, pid in enumerate(pids):
                    a = list(args)
                    kw = dict(kwargs)
                    if a:
                        a[0] = pid
                    else:
                        kw["image_caption_provider_id"] = pid
                    try:
                        call = orig(this, path, *a, **kw)
                        text = await (asyncio.wait_for(call, try_timeout) if try_timeout else call)
                    except Exception as e:
                        logger.warning(f"[lively_gate] 群聊背景的图片描述出错（{pid or '默认模型'}）: {type(e).__name__} {e}")
                        continue
                    if str(text or "").strip():
                        if i:
                            logger.info(f"[lively_gate] 看图换用备用模型 {pid} 看成了")
                        return text
                    logger.warning(f"[lively_gate] 群聊背景的图片描述空了（{pid or '默认模型'}）")
                return ICL_UNSEEN.format(why="看图那边出错了")
            finally:
                if cleanup and path != str(local):
                    Path(path).unlink(missing_ok=True)
        finally:
            try:
                await resolver.__aexit__(None, None, None)
            except Exception:
                pass

    def _icl_max_size(self) -> int:
        try:
            opts = self.context.get_config().get("provider_settings", {}).get("image_compress_options", {})
            return int(opts.get("max_size") or 1280)
        except Exception:
            return 1280

    # ---------- 服務哪些群：〈主人〉說了〈我〉自己改 ----------
    @filter.llm_tool("lively_serve_group")
    async def tool_serve_group(self, event: AstrMessageEvent, group: str, action: str = "加"):
        """把一个群加进你服务的群，或者从里面拿掉。服务的群里的消息你才看得到、才会在那边说话；人在群里但不在服务的群里，那边的消息你收不到。
        加、拿掉要主人说了才做得成；只能加你已经在里面的群。

        Args:
            group(string): 群号，或群名里的字
            action(string): 加、拿掉；不写就是加
        """
        if not self.s.is_owner(event.get_sender_id()):
            return self.s.fill("没改：服务哪些群要〈主人〉说了才改得了")
        bot = getattr(event, "bot", None) or self.s.client()
        try:
            joined = {str(x.get("group_id")): str(x.get("group_name") or "")
                      for x in (await bot.api.call_action("get_group_list") or [])}
        except Exception as e:
            logger.warning(f"[lively_gate] 拿群列表失败: {e}")
            return "没改：QQ 那边拿不到群列表，可能掉线了"
        want = str(group or "").strip()
        served = list(self.s.groups())
        hits = [want] if want in joined or want in served else [g for g, n in joined.items() if want and want in n]
        if not hits:
            return self.s.fill(f"没改：〈我〉不在「{want}」这个群里" + ("（只能加〈我〉已经在里面的群）" if want.isdigit() else ""))
        if len(hits) > 1:
            return "没改：好几个群都对得上，要说是哪一个：" + "；".join(f"「{joined[g]}」（{g}）" for g in hits)
        gid = hits[0]
        where = f"「{joined[gid]}」（{gid}）" if joined.get(gid) else f"群 {gid}"
        drop = any(x in str(action or "") for x in ("拿", "去", "删", "退", "不", "关"))
        if drop == (gid not in served):
            return self.s.fill(f"{where}本来就{'不' if drop else ''}在〈我〉服务的群里，没改")
        self.cfg["groups"] = [g for g in served if g != gid] if drop else served + [gid]
        try:
            self.cfg.save_config()
        except Exception as e:
            logger.warning(f"[lively_gate] 存服务的群失败: {e}")
            self.cfg["groups"] = served
            return "没改：设置存不进去"
        logger.info(f"[lively_gate] 服务的群{'拿掉' if drop else '加上'}了 {gid}（{event.get_sender_id()} 说的）")
        if drop:
            return self.s.fill(f"拿掉了：{where}。之后那边的消息〈我〉看不到了，人还在群里")
        text = f"加上了：{where}。之后那边的消息〈我〉看得到、也会在那边说话了"
        c = self._star("lively_comic")
        if c and getattr(c, "state", {}).get("enabled", True) and hasattr(c, "_groups") and gid in c._groups():
            text += "；每天 22:00 的群漫画也会画这个群、直接发进去（面板「群里」页能关）"
        return self.s.fill(text)

    @filter.llm_tool("lively_block")
    async def tool_block(self, event: AstrMessageEvent, qq: str = "", action: str = "屏蔽", why: str = ""):
        """把一个人屏蔽掉，或者放出来，屏蔽谁、放出来谁你自己定。屏蔽以后 TA 在哪说的话都到不了你这儿：@你、私聊你你都收不到，群聊背景、看 QQ 时也看不到 TA 的话，对 TA 的主动动作也会拦下；所以 TA 说什么你都没法再自己看了决定回不回（只是某一条不想回，用 lively_skip_reply 就行，TA 的话你照样看得到）。
        这不是 QQ 的拉黑：QQ 那边 TA 照样能发消息、能看到你说话（QQ 拉黑只能拉黑好友申请；禁言、踢人要群管）。

        Args:
            qq(string): TA 的 QQ 号；action 是「看」时不用写
            action(string): 屏蔽、放出来、看；不写就是屏蔽
            why(string): 为什么，一句话
        """
        def names(q):
            b = self._star("lively_bond")
            try:
                return (b.relation(q) or {}).get("name") or q if b and hasattr(b, "relation") else q
            except Exception:
                return q
        cur = list(id_list(self.s.get("ignored_senders", [])))
        if "看" in str(action or ""):
            return ("屏蔽着的：" + "；".join(f"{names(q)}（{q}）" for q in cur)) if cur else "现在没有屏蔽谁"
        q = re.sub(r"\D", "", str(qq or ""))
        if not q or q == self.s.bot_qq() or self.s.is_owner(q):
            return self.s.fill("没改：QQ 号不对（〈主人〉和自己不能屏蔽）")
        off = any(x in str(action or "") for x in ("放", "解", "取消", "不"))
        if off == (q not in cur):
            return f"没改：{names(q)}（{q}）本来就{'没' if off else '已经'}被屏蔽" + ("" if off else "了")
        self.cfg["ignored_senders"] = [x for x in cur if x != q] if off else cur + [q]
        try:
            self.cfg.save_config()
        except Exception as e:
            logger.warning(f"[lively_gate] 存屏蔽名单失败: {e}")
            self.cfg["ignored_senders"] = cur
            return "没改：设置存不进去"
        self._refresh()
        logger.info(f"[lively_gate] {'放出来' if off else '屏蔽'}了 {q}（{event.get_sender_id()} 说的）：{why}")
        if off:
            return f"放出来了：{names(q)}（{q}）。之后 TA 的话〈我〉又收得到了".replace("〈我〉", self.s.fill("〈我〉"))
        return self.s.fill(f"屏蔽了：{names(q)}（{q}）。从现在起 TA 的话〈我〉收不到、也不会回；QQ 那边 TA 照样能发消息")

    # ---------- 改動公告 ----------
    async def _updates_loop(self):
        await asyncio.sleep(120)  # 開機先等 QQ 連上
        while True:
            try:
                anns = self.updates.due()
                if anns:
                    await self._deliver_updates(anns)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.updates.last_try = time.time()
                logger.warning(f"[lively_gate] 送改动公告失败: {e}")
            await asyncio.sleep(60)

    async def _update_words(self, facts: str) -> str:
        """把公告交給她，回她想私信〈主人〉的話；看不懂、寫了號碼當沒寫成"""
        pid = str(self.s.get("words_provider_id", "") or "")
        prov = (self.context.get_provider_by_id(pid) if pid else None) or self.s.provider("dm_provider_id") or self.s.provider()
        if prov is None:
            raise RuntimeError("没有能用的模型")
        resp = await asyncio.wait_for(prov.text_chat(
            prompt=self.s.fill(facts), system_prompt=(self.s.persona_prompt() + "\n" + self.s.fill(UPDATE_RULE)).strip()), 120)
        say = _words_out((getattr(resp, "completion_text", "") or "").strip())
        if say and _LONG_NUM_RE.search(say):
            logger.info(f"[lively_gate] 她写的公告回话带了号码，当没写成：{say[:80]}")
            return ""
        return say

    async def _deliver_updates(self, anns: list[dict]):
        """送公告：她寫一段私信〈主人〉（寫不出來再問一次，再不行發【后台】卡片說明）；主人私聊記一筆她收到了什麼"""
        owner = self.s.owner()
        if not owner:
            return
        self.updates.last_try = time.time()
        try:
            await self.s.client().api.call_action("get_login_info")
        except Exception as e:
            logger.info(f"[lively_gate] QQ 这会儿连不上，改动公告晚点再送: {e}")
            return
        facts = facts_text(anns)
        before = self.updates.said_lately()
        if before:
            facts += "\n\n" + before
        say = ""
        for _ in range(2):
            try:
                say = await self._update_words(facts)
            except Exception as e:
                logger.warning(f"[lively_gate] 问她看完公告要说什么没问成: {e}")
            if say:
                break
        umo = self.s.private_umo(owner)
        ids = "、".join(str(a["id"]) for a in anns)
        note_outbox(umo, self.s.fill("〈我〉收到了〈主人〉那边的改动公告：\n" + "\n\n".join(ann_text(a) for a in anns)),
                    f"{BACKSTAGE_KIND}:公告")
        if say:
            await self.context.send_message(umo, MessageChain().message(self.s.owner_text(say)))
            note_outbox(umo, say, "公告")
            how = "said"
        else:
            card = backstage(self.s.fill("给她送了改动公告，她没写出要跟〈主人〉说的话。公告：\n"
                                         + "\n\n".join(ann_text(a) for a in anns)))
            await self.context.send_message(umo, MessageChain().message(self.s.owner_text(card)))
            note_outbox(umo, card, f"{BACKSTAGE_KIND}:公告")
            how = "card"
        self.updates.mark(anns, say, how)
        logger.info(f"[lively_gate] 改动公告 {ids} 送到了（{'她私信了主人' if say else '她没写成，发了后台卡片'}）：{say[:80]}")

    @filter.llm_tool("lively_updates")
    async def tool_updates(self, event: AstrMessageEvent, count: int = 3):
        """看最近几次〈主人〉那边改了你的程序之后写给你的改动公告：哪里变了、以前怎样、现在能做什么。

        Args:
            count(number): 看最近几条，不写是 3 条，最多 10 条
        """
        try:
            n = max(1, min(10, int(count or 3)))
        except (TypeError, ValueError):
            n = 3
        rows = self.updates.recent(n)
        if not rows:
            return self.s.fill("还没有改动公告")
        owner = self.s.is_owner(event.get_sender_id())
        out = []
        for a in rows:
            sent = self.updates.state["sent"].get(str(a["id"]))
            line = ann_text(a)
            if not sent:
                line += "\n（刚写好，还没送到〈我〉这边、〈我〉还没跟〈主人〉说过）"
            elif owner and sent.get("say"):
                line += f"\n（{day_of(sent['ts'])} 收到后〈我〉跟〈主人〉说的：{sent['say'][:200]}）"
            out.append(line)
        return self.s.fill("最近的改动公告（新的在前）：\n\n" + "\n\n".join(out))

    def _star(self, short: str):
        meta = self.context.get_registered_star(f"astrbot_plugin_{short}")
        return getattr(meta, "star_cls", None) if meta and getattr(meta, "activated", True) else None

    async def terminate(self):
        if getattr(self, "_upd_task", None):
            self._upd_task.cancel()
        self.rhythm.maybe_save(force=True)
        for task in self._watch.values():
            task.cancel()
        self._watch.clear()
        if self._caption_orig:
            cls, orig = self._caption_orig
            cls.get_image_caption = orig
            self._caption_orig = None
        if getattr(self, "_compress_orig", None):
            cls, orig = self._compress_orig
            cls.__call__ = orig
            self._compress_orig = None
        if getattr(self, "_tool_said_orig", None):
            cls, orig = self._tool_said_orig
            cls._build_repeated_tool_call_guidance = orig
            self._tool_said_orig = None
        if getattr(self, "_tool_image_orig", None):
            cls, orig = self._tool_image_orig
            cls._materialize_large_tool_result = orig
            self._tool_image_orig = None

    @filter.on_decorating_result(priority=100000)
    async def strip_leak(self, event: AstrMessageEvent):
        result = event.get_result()
        if not result or not isinstance(result.chain, list):
            return
        changed = False
        chain = []
        for comp in result.chain:
            if isinstance(comp, Plain) and (
                "system_reminder" in comp.text or "DSML" in comp.text
            ):
                comp = Plain(_clean(comp.text))
                changed = True
                if not comp.text.strip():
                    continue
            chain.append(comp)
        if not changed:
            return
        logger.warning(
            f"[lively_gate] 已拦截回复中的内部内容: {event.unified_msg_origin}"
        )
        if not any(not isinstance(c, Plain) or c.text.strip() for c in chain):
            event.stop_event()
            return
        result.chain = chain

    # 排在表情包插件（99999）之後：它處理完還剩下的標籤才歸這裡
    @filter.on_decorating_result(priority=99990)
    async def meme_leftover(self, event: AstrMessageEvent):
        result = event.get_result()
        if not result or not isinstance(result.chain, list):
            return
        if not any(isinstance(c, Plain) and "&&" in c.text for c in result.chain):
            return
        chain, tags = [], []
        for comp in result.chain:
            if isinstance(comp, Plain) and MEME_TAG_RE.search(comp.text):
                tags += MEME_TAG_RE.findall(comp.text)
                text = MEME_TAG_RE.sub("", comp.text).strip()
                if text:
                    chain.append(Plain(text))
                continue
            chain.append(comp)
        if not tags:
            return
        if tags[0].lower() == "tease" and not self._may_tease(event):
            tags[0] = ""  # 擦邊的只對很熟的人用：當成沒有這個分類，刪掉（下一輪告訴她）
        picked: list = []
        img = self._meme_image(tags[0], str(event.get_sender_id() or ""), picked) if tags[0] else None
        if img:
            chain.append(Image.fromFileSystem(str(img)))
            if picked:  # 表情包插件發完會記進它的發送記錄（她之後說「刚才那张」找得到）
                event.set_extra("xfy_meme_cats", [tags[0]])
                event.set_extra("xfy_meme_files", picked)
        logger.info(
            f"[lively_gate] 回复里剩下没处理的表情标签 {tags}，"
            f"{'换成了表情图' if img else '没有这个分类，删掉了'}: {event.unified_msg_origin}"
        )
        if not chain:
            event.stop_event()
            return
        result.chain = chain

    def _meme_image(self, tag: str, to: str = "", picked: list | None = None):
        """先用表情包插件的小肥魚補丁挑（防重複、借鄰居、照 TA 的偏好），沒有補丁才隨便挑一張"""
        pick = getattr(self._memer(), "_xfy_pick_meme", None)
        if pick:
            try:
                return pick(tag, to=to, picked=picked)
            except TypeError:
                pass
            except Exception as e:
                logger.warning(f"[lively_gate] 挑表情包失败 {tag}: {e}")
                return None
        d = MEME_DIR / tag
        try:
            files = (
                [f for f in d.iterdir() if f.suffix.lower() in MEME_EXTS]
                if d.is_dir()
                else []
            )
        except Exception:
            files = []
        return random.choice(files) if files else None
