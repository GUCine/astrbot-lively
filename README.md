# 擬真群友（lively）插件套件

一組 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 插件，讓 QQ 機器人像一個有性格的群友一樣過日子：記得每個人、有好感和心情、會主動找熟人聊天、每天給主人寫日報、畫群漫畫、發 QQ 空間、自己總結經驗，每週五把群友的願望整理成提案交給主人。

機器人的名字、自稱、對主人的稱呼、印象卡的叫法都在門禁插件（astrbot_plugin_lively_gate）裡設定，各插件的提示詞和消息會自動套用；說話風格則跟著 AstrBot 裡選的人格走。

執行環境：AstrBot ≥ 4.29 + NapCat（aiocqhttp 平台），模型推薦 DeepSeek。

## 插件一覽

| 插件 | 作用 | 依賴 |
| --- | --- | --- |
| [lively_gate](https://github.com/GUCine/astrbot_plugin_lively_gate) 群組門禁與共用設定 | 只放行指定的群；群聊、私聊分別用不同模型；句子裡喊名字當作 @；識別表情包；攔截洩漏的內部標記。**也是整套的公共設定** | — |
| [lively_bond](https://github.com/GUCine/astrbot_plugin_lively_bond) 好感度與印象卡 | 熟悉度、好感、心情、印象、每週人物卡；群友要「印象卡」時發一張卡片圖 | 可選 LivingMemory |
| [lively_memtier](https://github.com/GUCine/astrbot_plugin_lively_memtier) 記憶分層壓縮 | 把 LivingMemory 的零碎記憶按日、周、月、季逐級壓縮，省 token | LivingMemory |
| [lively_proactive](https://github.com/GUCine/astrbot_plugin_lively_proactive) 主動私聊 | 偶爾主動私聊有過交互、好感夠的熟人 | bond |
| [lively_report](https://github.com/GUCine/astrbot_plugin_lively_report) 每日彙報 | 每晚私信主人彙報今天的情況 | — |
| [lively_comic](https://github.com/GUCine/astrbot_plugin_lively_comic) 每日群聊漫畫 | 每天把群聊畫成漫畫，主人審核後發群；主人可以讓它畫畫 | 群分析總結插件 |
| [lively_qzone](https://github.com/GUCine/astrbot_plugin_lively_qzone) QQ 空間說說 | 寫說說，主人審核後發佈 | NapCat |
| [lively_social](https://github.com/GUCine/astrbot_plugin_lively_social) 好友與群邀請管家 | 好友申請、群邀請、禁言踢出通知 | — |
| [lively_voice](https://github.com/GUCine/astrbot_plugin_lively_voice) 語音回覆 | 偶爾把短回覆變成語音 | MiniMax |
| [lively_evolve](https://github.com/GUCine/astrbot_plugin_lively_evolve) 自我成長 | 按大家的反應微調參數、總結經驗、例行動作、每週提案 | — |
| [lively_billing](https://github.com/GUCine/astrbot_plugin_lively_billing) DeepSeek 用量帳本 | 每小時記 DeepSeek 餘額，算每天真實花費，餘額不足提醒 | DeepSeek |
| [lively_panel](https://github.com/GUCine/astrbot_plugin_lively_panel) 網頁控制面板 | 網頁面板：狀態、關係圖、卡冊、開關、待審核、飯錢、日誌 | — |

每個插件都可以單獨裝，但 **astrbot_plugin_lively_gate 建議必裝**：其他插件的主人、群、機器人名字、人設用詞這些共用設定，沒單獨填時都從它那裡取。

## 安裝

挑需要的裝就行，**建議至少裝 astrbot_plugin_lively_gate**。三種方式任選：

- **插件市場**：在 AstrBot WebUI 的「插件市場」搜尋 `lively`，看中哪個裝哪個。
- **貼連結**：在 WebUI 的「安裝插件」裡貼上表格中某個插件的倉庫網址，例如 `https://github.com/GUCine/astrbot_plugin_lively_gate`。
- **一次全裝**：下載本倉庫，把 `astrbot_plugin_lively_*` 目錄全部（或挑幾個）複製到 AstrBot 的 `data/plugins/` 下；
  或者在 AstrBot 的 data 目錄所在的機器上執行：

  ```bash
  ./scripts/install_all.sh /path/to/AstrBot/data
  ```

  腳本會把 12 個插件的倉庫 clone 到 `data/plugins/`（已存在的跳過），也可以只列要的：`./scripts/install_all.sh /path/to/AstrBot/data gate bond panel`。

裝好以後：

1. 重啟 AstrBot，或在 WebUI 裡重載插件。依賴（`requirements.txt`）會自動安裝。
2. 在 WebUI 的插件配置裡填好 **astrbot_plugin_lively_gate**：
   - `owner_qq`：主人的 QQ 號（留空就用 AstrBot 的管理員 ID `admins_id`）
   - `groups`：要服務的群號
   - `bot_name`：機器人的名字（群友喊這個名字當作 @ 它；留空就不啟用這個功能，其他插件也只認 @ 和私聊）
   - `self_call` / `owner_call` / `card_name`：機器人的自稱、對主人的稱呼、印象卡的叫法（留空分別是「我」「主人」「印象卡」）
   - `owner_traditional`：各插件發給主人的消息轉成繁體（預設開啟；群聊和給模型的提示詞不轉）
   - 其他項（機器人 QQ、平台 ID、模型）留空會自動識別或用 AstrBot 預設
3. 其他插件按需在各自的配置裡選模型、調參數。不想用 WebUI 的話，配置文件在 `data/config/<插件目錄名>_config.json`。

## 設定是怎麼找的

每個插件裡一項設定按這個順序找，找到就用：

1. 插件自己的配置
2. astrbot_plugin_lively_gate 的配置（`owner_qq`、`groups`、`bot_qq`、`bot_name`、`self_call`、`owner_call`、`card_name`、`owner_traditional`、`platform_id`、`persona_id`）
3. AstrBot 本身：管理員 `admins_id`、第一個 aiocqhttp 平台、預設對話模型、預設人格

這部分邏輯在 `lively_common.py`。AstrBot 插件各自獨立安裝、沒法互相 import，所以每個插件目錄裡都有一份一樣的副本。改的時候改 [common/lively_common.py](common/lively_common.py)，再執行：

```bash
./scripts/sync_common.sh
```

改了插件說明或配置項以後，重新生成各插件的 README：

```bash
python3 scripts/gen_readme.py
```

## 字體和圖片

倉庫**不附帶**第三方素材，只附帶預設角色的形象圖（各插件的市場圖示 `logo.png`、面板的 `brand.png`、`favicon.png`、`fish.webp`，卡片的 `card_assets/fish.webp`），可以換成自己的。下面這些請從來源獲取後自己放進去，沒放也能用：

| 素材 | 來源 | 放到哪裡 | 沒放會怎樣 |
| --- | --- | --- | --- |
| 桌寵動畫 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（素材禁止商用，轉載和改作需署名並附原倉庫連結） | `astrbot_plugin_lively_panel/static/pet/` | 面板不顯示桌寵 |
| 表情包 | 梗鯨 | `astrbot_plugin_lively_panel/static/meme/` | 面板空狀態不配圖 |
| 標題手寫字體 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet) | 面板 `static/font/rt.woff2`（子集）和 `rt-full.woff2`；卡片 `astrbot_plugin_lively_bond/card_assets/rt.woff2` | 用系統字體；卡片用中文黑體（Debian/Ubuntu 裝 `fonts-noto-cjk`） |

面板認的文件名：

- 桌寵：每個動作三份——`<動作>.webm`（帶透明通道的動畫）、`<動作>.webp`（動圖）、`<動作>.p.webp`（靜態封面，系統開了「減少動態效果」時用）。動作有：
  breakfast breathe bubble busy cheer crab cube curtsy dance dinner drag file float giggle hop hum look lunch mutter pout rice run shy sigh sleep startle stretch tail think token wave yawn
- 表情包：`ciallo` `cute` `dead` `full` `great` `keep` `meh` `rice` `sleep` `stress`，都是 `.webp`

換成自己的角色時，直接用同樣的文件名替換即可。面板用的 ECharts（`static/echarts.min.js`）是 Apache-2.0 許可。

## 主人指令

各插件的管理指令（「飯錢」「群漫畫 開」「說說 狀態」等）只有主人能用，簡體、繁體都認。

## 安全

- 密鑰只放在 AstrBot 的配置裡，插件不會打印，也不會出現在面板頁面和介面裡。
- 面板預設只監聽 docker 內網，外網訪問請走 Cloudflare Tunnel + Cloudflare Access，並在 `allowed_emails` 裡寫允許的郵箱。
- 只有主人能用各插件的管理指令（私聊發）。

## 許可

MIT，見 [LICENSE](LICENSE)。QQ 空間發佈介面參考了 [Zhalslar/astrbot_plugin_qzone](https://github.com/Zhalslar/astrbot_plugin_qzone)（MIT）。
