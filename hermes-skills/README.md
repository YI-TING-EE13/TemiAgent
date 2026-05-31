# Hermes Temi Skills 模組 README

最後更新日期：2026-05-19

## 本文件維護規則

這份 README 是 `hermes-skills/` 的快速入口。只要 Temi 相關 skill 的角色、schema、reference、安裝方式或與 `hermes-agent/skills/temi-*` 的同步策略改變，都要同步更新本文件。

## 模組定位

`hermes-skills/` 是 repo root 的 Temi skill mirror，方便在不翻進 `hermes-agent/` 大型 checkout 的情況下快速讀取、審查與同步 Temi 專用 skill。實際 resident Hermes demo 優先讀取：

```text
hermes-agent/skills/temi-robot-control/
hermes-agent/skills/temi-care-memory/
hermes-agent/skills/temi-home-esi/
hermes-agent/skills/temi-discord-care-assistant/
```

`hermes-skills/` 與 `hermes-agent/skills/temi-*` 內容應保持一致；Discord/gateway 入口 skill 也要同步 mirror。

## Skill 分工

| Skill | 角色 | 重點 |
|---|---|---|
| `temi-robot-control` | Robot action contract | JSON-only output、安全 robot actions、MQTT/action schema、範例。 |
| `temi-care-memory` | 照護記憶規則 | profile、daily state、reminders、event log、summary 的讀寫邊界。 |
| `temi-home-esi` | 風險分級規則 | Home-ESI Lite `Normal/L3/L2/L1` 判斷與行動優先序。 |
| `temi-discord-care-assistant` | Discord/gateway 入口 | 讓 Hermes 在 Discord 遇到手勢、相機、指物或照護語句時載入 Temi skills。 |

## 與其他模組的關係

| 關聯模組 | 關係 |
|---|---|
| `hermes-agent/` | Hermes runtime 讀取 skill 的主要位置。 |
| `tools/hermes_resident_server.py` | 可用多個 `--skill-path` 預載 Temi skills。 |
| `hermes_temi_bridge/` | Bridge 依 skill contract 驗證 Hermes output。 |
| `docs/project/hermes_care_assistant_task_readme.md` | 記錄照護助理任務的 skill 分層與驗收標準。 |

## 主要結構

```text
hermes-skills/
  temi-robot-control/
    SKILL.md
    references/
      action_schema.json
      examples.md
      mqtt_topics.md
      safety_rules.md
    scripts/validate_temi_action.py
  temi-care-memory/
    SKILL.md
    references/structured_memory_contract.md
  temi-home-esi/
    SKILL.md
    references/home_esi_lite.md
  temi-discord-care-assistant/
    SKILL.md
    references/discord_temi_context.md
```

## Resident server 使用方式

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8765 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md
```

順序很重要：`temi-robot-control` 應先載入，作為 action contract；照護記憶與 Home-ESI policy 接在後面補充認知規則；`temi-discord-care-assistant` 最後補上 Discord/gateway 的相機、手勢與 skill routing 線索。

## 同步檢查

修改 `hermes-skills/temi-*` 後，請同步檢查：

```bash
diff -ru hermes-skills/temi-robot-control hermes-agent/skills/temi-robot-control
diff -ru hermes-skills/temi-care-memory hermes-agent/skills/temi-care-memory
diff -ru hermes-skills/temi-home-esi hermes-agent/skills/temi-home-esi
diff -ru hermes-skills/temi-discord-care-assistant hermes-agent/skills/temi-discord-care-assistant
```

若刻意不同，請在相關 README 或 task readme 中說明原因。
