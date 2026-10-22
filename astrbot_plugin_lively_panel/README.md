# 網頁控制面板

> 網頁控制面板：狀態、關係圖、印象卡冊、開關、待審核、飯錢、日誌（建議經 Cloudflare Tunnel + Access 訪問）

AstrBot 插件，屬於「擬真群友」（lively）插件套件。適用 AstrBot >=4.29.0 + NapCat（aiocqhttp）。

主人、群、機器人名字、人設用詞這些共用設定在 [astrbot_plugin_lively_gate](https://github.com/GUCine/astrbot_plugin_lively_gate) 裡填，建議一起裝。

## 功能

```text
機器人控制面板：網頁看狀態、關係圖、開關、待審核和日誌。

- 網頁服務跑在容器內 0.0.0.0:6200，只在 docker 內網，不映射到宿主機；外網經 Cloudflare Tunnel 進來
- 登入交給 Cloudflare Access（郵箱驗證碼），這裡再核對 Cf-Access-Authenticated-User-Email 是否在允許名單裡
  （名單在插件配置 allowed_emails）；容器內 127.0.0.1 和宿主機訪問放行，方便自檢
- 改東西的請求必須是 POST 且帶 X-Lively: 1 頭（跨站頁面帶不了自定義頭），每次操作記到 audit.jsonl
- 密鑰一律不出現在頁面和介面裡
```

## 依賴

讀取同套件其他插件的狀態，沒裝的部分不顯示。外網訪問建議用 Cloudflare Tunnel + Cloudflare Access，不要直接暴露端口。

## 素材

倉庫不附帶第三方素材，只附帶預設角色的形象圖（`static/brand.png`、`favicon.png`、`fish.webp`），可以換成自己的。

| 素材 | 來源 | 放到哪裡 | 沒放會怎樣 |
| --- | --- | --- | --- |
| 桌寵動畫 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（素材禁止商用，轉載和改作需署名並附原倉庫連結） | `static/pet/` | 面板不顯示桌寵 |
| 表情包 | 梗鯨 | `static/meme/` | 面板空狀態不配圖 |
| 標題手寫字體 | [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet) | `static/font/rt.woff2`（子集）和 `rt-full.woff2` | 用系統字體 |

桌寵每個動作三份：`<動作>.webm`（帶透明通道）、`<動作>.webp`（動圖）、`<動作>.p.webp`（靜態封面）。動作有：breakfast breathe bubble busy cheer crab cube curtsy dance dinner drag file float giggle hop hum look lunch mutter pout rice run shy sigh sleep startle stretch tail think token wave yawn。
表情包：`ciallo` `cute` `dead` `full` `great` `keep` `meh` `rice` `sleep` `stress`，都是 `.webp`。面板用的 ECharts（`static/echarts.min.js`）是 Apache-2.0 許可。

## 配置

在 AstrBot WebUI 的插件配置裡填，或者直接編輯 `data/config/astrbot_plugin_lively_panel_config.json`。留空的公共項（主人、群、機器人名字、平台）會用 astrbot_plugin_lively_gate 裡填的。

| 配置項 | 說明 | 預設 |
| --- | --- | --- |
| `title` | 面板標題：可以用〈名字〉代表機器人的名字。留空 = 〈名字〉的小帳本 | （空） |
| `allowed_emails` | 允許登入面板的郵箱：面板經 Cloudflare Access 登入，這裡核對 Cf-Access-Authenticated-User-Email。本機和宿主機訪問不受限制 | （空） |
| `host` | 監聽地址：docker 裡一般用 0.0.0.0（只在 docker 內網，不映射到宿主機端口） | "0.0.0.0" |
| `port` | 監聽端口 | 6200 |
| `owner_qq` | 主人 QQ（留空用門禁插件裡填的） | （空） |

## 資料

執行資料在 `data/plugin_data/astrbot_plugin_lively_panel/`。

## 許可

MIT，見 [LICENSE](LICENSE)。
