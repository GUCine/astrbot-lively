"""根據每個插件的說明文字（main.py 開頭的文檔字串）和 _conf_schema.json 生成插件目錄裡的 README.md。

改了插件說明或配置項以後執行：python3 scripts/gen_readme.py
"""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 依賴別的插件或外部服務的說明
NEEDS = {
    "gate": "無。建議第一個裝：其他插件的主人、群、機器人名字等公共設定都從這裡取。",
    "billing": "模型用的是 DeepSeek 官方 API（要查餘額）。畫圖費用要配合 astrbot_plugin_lively_comic 才統計。",
    "bond": "可選 [LivingMemory](https://github.com/lxfight/astrbot_plugin_livingmemory)：做人物卡時會讀它的記憶和聊天記錄。",
    "comic": "[群分析總結插件 astrbot_plugin_qq_group_daily_analysis](https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis)："
             "群漫畫的話題提取和畫圖配置都用它的（在那個插件裡配好畫圖模型，並關掉它自己的定時分析和自動漫畫）。",
    "evolve": "參數會被 astrbot_plugin_lively_voice / astrbot_plugin_lively_proactive / astrbot_plugin_lively_qzone 讀取；週五提案的封面圖用 astrbot_plugin_lively_comic 的畫圖配置。",
    "memtier": "[LivingMemory](https://github.com/lxfight/astrbot_plugin_livingmemory)（必需）。",
    "panel": "讀取同套件其他插件的狀態，沒裝的部分不顯示。外網訪問建議用 Cloudflare Tunnel + Cloudflare Access，不要直接暴露端口。",
    "proactive": "astrbot_plugin_lively_bond（用好感度挑人）；可選 LivingMemory（找聊天由頭）。",
    "qzone": "NapCat（用 get_cookies 拿 QQ 空間 Cookie）。發說說的介面參考了 "
             "[Zhalslar/astrbot_plugin_qzone](https://github.com/Zhalslar/astrbot_plugin_qzone)（MIT）。",
    "report": "讀取 astrbot_plugin_lively_bond、astrbot_plugin_lively_social、astrbot_plugin_lively_evolve 和 LivingMemory 的資料，沒裝的部分不寫。",
    "social": "可選 astrbot_plugin_lively_bond（用聊天次數判斷是不是熟人）。",
    "voice": "[MiniMax](https://www.minimaxi.com/) 語音合成 API；系統裡有 ffmpeg 時會把音量拉到合適的大小。",
}


def table(schema: dict) -> str:
    rows = ["| 配置項 | 說明 | 預設 |", "| --- | --- | --- |"]
    for k, v in schema.items():
        desc = v.get("description", "")
        if v.get("hint"):
            desc += "：" + v["hint"]
        d = v.get("default", "")
        d = "（空）" if d in ("", [], {}) else json.dumps(d, ensure_ascii=False)
        if len(d) > 40:
            d = d[:37] + "…\""
        rows.append(f"| `{k}` | {desc.replace('|', '/')} | {d} |")
    return "\n".join(rows)


# 已經單獨發佈、README 是手寫的插件，不覆蓋
GATE = "astrbot_plugin_lively_gate"

# 不隨倉庫發佈的第三方素材：從來源取得後放進去，沒放也能用
ASSETS = {
    "panel": "倉庫不附帶第三方素材，只附帶預設角色的形象圖（`static/brand.png`、`favicon.png`、`fish.webp`），可以換成自己的。\n\n"
             "| 素材 | 來源 | 放到哪裡 | 沒放會怎樣 |\n| --- | --- | --- | --- |\n"
             "| 桌寵動畫 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（素材禁止商用，轉載和改作需署名並附原倉庫連結） | `static/pet/` | 面板不顯示桌寵 |\n"
             "| 表情包 | 梗鯨 | `static/meme/` | 面板空狀態不配圖 |\n"
             "| 標題手寫字體 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet) | `static/font/rt.woff2`（子集）和 `rt-full.woff2` | 用系統字體 |\n\n"
             "桌寵每個動作三份：`<動作>.webm`（帶透明通道）、`<動作>.webp`（動圖）、`<動作>.p.webp`（靜態封面）。動作有：breakfast breathe bubble busy cheer crab cube curtsy dance dinner drag file float giggle hop hum look lunch mutter pout rice run shy sigh sleep startle stretch tail think token wave yawn。\n"
             "表情包：`ciallo` `cute` `dead` `full` `great` `keep` `meh` `rice` `sleep` `stress`，都是 `.webp`。面板用的 ECharts（`static/echarts.min.js`）是 Apache-2.0 許可。",
    "bond": "卡片的手寫字體不隨倉庫發佈：從 [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet) 取得後放到 `card_assets/rt.woff2`；"
            "沒放就用中文黑體（Debian/Ubuntu 裝 `fonts-noto-cjk`）。`card_assets/fish.webp` 是預設角色的形象圖，可以換成自己的。",
}

HANDWRITTEN = {"gate"}

for d in sorted(ROOT.glob("astrbot_plugin_lively_*")):
    short = d.name.removeprefix("astrbot_plugin_lively_")
    if short in HANDWRITTEN:
        continue
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", (d / "metadata.yaml").read_text("utf-8"), re.M))
    doc = ast.get_docstring(ast.parse((d / "main.py").read_text("utf-8"))) or ""
    schema = json.loads((d / "_conf_schema.json").read_text("utf-8"))
    out = [
        f"# {meta.get('display_name', d.name)}",
        "",
        f"> {meta.get('desc', '')}",
        "",
        f"AstrBot 插件，屬於「擬真群友」（lively）插件套件。適用 AstrBot {meta.get('astrbot_version', '').strip(chr(34))} + NapCat（aiocqhttp）。",
        "",
        f"主人、群、機器人名字、人設用詞這些共用設定在 [{GATE}](https://github.com/GUCine/{GATE}) 裡填，建議一起裝。",
        "",
        "## 功能",
        "",
        "```text",
        doc.strip(),
        "```",
        "",
        "## 依賴",
        "",
        NEEDS.get(short, "無"),
        "",
        *(["## 素材", "", ASSETS[short], ""] if short in ASSETS else []),
        "## 配置",
        "",
        "在 AstrBot WebUI 的插件配置裡填，或者直接編輯 `data/config/" + d.name + "_config.json`。"
        "留空的公共項（主人、群、機器人名字、平台）會用 astrbot_plugin_lively_gate 裡填的。",
        "",
        table(schema),
        "",
        *(["## 資料", "", f"執行資料在 `data/plugin_data/astrbot_plugin_lively_{short}/`。", ""]
          if "get_data_dir(" in (d / "main.py").read_text("utf-8") else []),
        "## 許可",
        "",
        "MIT，見 [LICENSE](LICENSE)。",
        "",
    ]
    (d / "README.md").write_text("\n".join(out), "utf-8")
    print("寫好", d.name)
