# Docs 模組 README

最後更新日期：2026-06-04

## 本文件維護規則

這份 README 是 `docs/` 的快速入口。新增文件時請先放入正確子目錄，並更新本索引；若文件是機器特定或歷史紀錄，請在標題或摘要明確標註。

## 文件結構

```text
docs/
  architecture/   # 系統設計、模組關係、contract narrative
  operations/     # runbooks、部署、硬體驗證、環境操作
  project/        # 計畫交接、任務 README、照護助理 scope
  schemas/        # 文件用 JSON schema 副本
  archive/        # 舊版或已取代文件
```

## 主要文件

| 文件 | 用途 |
|---|---|
| `architecture/project_overview.md` | Temi + Hermes 分層架構、MQTT topics、payload 與驗證計畫。 |
| `project/hermes_care_assistant_handoff.md` | 居家照護助理大腦的完整交接文件。 |
| `project/hermes_care_assistant_task_readme.md` | 照護助理任務的快速入口與更新紀錄。 |
| `project/continuous_vision_abnormal_behavior_handoff.md` | 持續影像串流與異常行為辨識需求的架構修改、實作原則、測試與交接文件。 |
| `project/first_year_demo_phase_tasks.md` | 第一年度 Demo 的 P0-P5 階段任務、驗收項目與 artifact 規劃。 |
| `project/first_year_demo_runbook.md` | 第一年度 Demo 現場操作、服務啟動、展示順序與故障切換。 |
| `project/first_year_demo_system_design_20260601.md` | 本次 Demo 最新系統設計、已實作功能、Bridge review 與 adapter ASR/camera-only 調整紀錄。 |
| `project/first_year_demo_e2e_operation_manual.md` | Temi 語音/影像到 Hermes 對話再回到 Temi TTS 的端到端操作手冊；包含 container 內操作與 resident multi-skill preload。 |
| `project/first_year_demo_scenario_script.md` | 三個照護 Demo scenario 的口頭腳本與 artifact 對應。 |
| `project/first_year_demo_acceptance_checklist.md` | Demo 前驗收 checklist、測試狀態與不納入主線項目。 |
| `operations/temi_integration_runbook.md` | 從 unit test 到 mock E2E、真 Hermes、硬體檢查的整合 runbook。 |
| `operations/temi_streaming_local_runbook.md` | 目前這台機器的 Temi streaming、ADB、實測狀態。 |
| `operations/temi_streaming_manual.md` | Android/PC 多點廣播開發部署手冊。 |
| `operations/lmstudio_gpu_selection.md` | LM Studio GPU selection 操作筆記；包含 TemiAgent 單卡、雙卡、三卡 QAT 實測。 |
| `operations/lmstudio_headless_3gpu_hdd_manual.md` | Headless LM Studio 使用 `/TemiAgent/.lmstudio-data`、預設 QAT `google/gemma-4-31b-qat` 權重、API identifier `google/gemma-4-31b`、64K context、支援單卡、雙卡、三卡 GPU 組合的啟動/換模型/debug 手冊。 |
| `operations/temi_e2e_stack_validation_manual.md` | TemiAgent 全服務重啟、LM Studio/Hermes/Bridge/MQTT/Temi/action viewer 健康檢查、mock 與真機端到端驗證操作手冊；包含一鍵測試腳本說明。 |
| `schemas/*.schema.json` | ASR event、Hermes output、command request/result 的文件副本。 |
| `../.hermes.md` / `../hermes-agent/docker/SOUL.md` | Discord/gateway 讓 Hermes 知道自己是 Temi 居家照護助理、可使用 Temi skills 的 runtime context。 |

## 目前文件狀態

2026-05-31 整理結果：

- 根目錄長篇文件已移入 `docs/architecture/`、`docs/operations/`、`docs/project/` 與 `docs/archive/`。
- 根 README 保留專案入口、模組索引與目前狀態快照。
- 第一年度 Demo 階段任務已整理在 `project/first_year_demo_phase_tasks.md`，P5 展示素材已整理為 runbook、scenario script、acceptance checklist 與 `project/first_year_demo_system_design_20260601.md`。
- Demo 實驗資料與 runtime artifacts 不納入文件索引；只保留 `logs/README.md` 與 `temi_shared/README.md` 說明用途。
- Android app 原始碼目前不在此 workspace；相關限制記錄在 `operations/temi_streaming_local_runbook.md`。

## 文件放置規則

- 架構與 contract：放 `docs/architecture/`。
- 操作步驟、啟動順序、IP、硬體狀態：放 `docs/operations/`。
- 計畫背景、任務交接、研究/demo scope：放 `docs/project/`。
- schema 文件副本：放 `docs/schemas/`；runtime schema 仍以模組內 schema 為準。
- 舊版 HTML 或已取代文件：放 `docs/archive/`，避免根目錄雜訊。

## 維護注意

- 根目錄 `README.md` 只做全專案入口，不承載長篇歷史紀錄。
- 模組自己的執行方式優先寫在該模組 README；docs 只放跨模組流程與背景。
- 文件搬移後請用 `rg` 檢查舊路徑引用。
