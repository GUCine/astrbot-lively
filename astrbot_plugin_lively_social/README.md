# 好友與群邀請管家

> 好友申請、群邀請、禁言踢出通知，熟人自動通過，其餘私信主人決定

AstrBot 插件，屬於「擬真群友」（lively）插件套件。適用 AstrBot >=4.29.0 + NapCat（aiocqhttp）。

主人、群、機器人名字、人設用詞這些共用設定在 [astrbot_plugin_lively_gate](https://github.com/GUCine/astrbot_plugin_lively_gate) 裡填，建議一起裝。

## 功能

```text
機器人的社交管家：好友申請、群邀請、被禁言/踢出/設管理的通知。

- 聊過天的熟人加好友：自動通過（每天有上限）；〈我〉討厭 TA（好感度 <−8）或態度到了戒備，
  就不自動通過，私信主人時帶上原因（問 bond 的關係讀口）
- 加上好友後不替〈我〉發招呼語（10-26 起）：TA 的私聊裡記一筆、心跳看手機時列在「新加的好友」，打不打招呼、怎麼說〈我〉自己定
- 其他好友申請、別人拉〈我〉進群：私信主人，主人回「同意 / 拒絕 / 拉黑 [QQ或群號]」
- 主人拉〈我〉進群：不找主人審批，記在主人的私聊裡讓〈我〉知道，進不進〈我〉自己定（10-26 用戶定）
- 工具 lively_requests：〈我〉看還在等的申請、同意或拒絕。同意別人的申請要主人說了才做得成；主人拉的群和拒絕〈我〉自己就能做
- 重啟、斷線那半分鐘來的群邀請事件收不到，QQ 那邊還留著：每 5 分鐘問一次 NapCat，漏掉的照現場來的處理
- 被禁言、被踢、被拉進新群、管理員變動：私信主人；禁言期間那個群的消息不再交給模型（反正發不出去）
- 所有事件記進 events.jsonl，給每日彙報用
```

## 依賴

可選 astrbot_plugin_lively_bond（用聊天次數判斷是不是熟人）。

## 配置

在 AstrBot WebUI 的插件配置裡填，或者直接編輯 `data/config/astrbot_plugin_lively_social_config.json`。留空的公共項（主人、群、機器人名字、平台）會用 astrbot_plugin_lively_gate 裡填的。

| 配置項 | 說明 | 預設 |
| --- | --- | --- |
| `groups` | 服務的群（留空用門禁插件裡填的） | （空） |
| `owner_qq` | 主人 QQ（留空用門禁插件裡填的） | （空） |

## 資料

執行資料在 `data/plugin_data/astrbot_plugin_lively_social/`。

## 許可

MIT，見 [LICENSE](LICENSE)。
