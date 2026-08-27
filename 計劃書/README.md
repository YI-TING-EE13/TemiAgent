# 計劃書模組 README

> Status: HISTORICAL research/reference material. This directory is not
> runtime source, deployment input or contract authority.

最後更新日期：2026-05-31

## 本文件維護規則

這份 README 是 `計劃書/` 的快速入口。只要新增研究計畫、簡報、教授溝通稿或計畫對應表，都要同步更新本文件。

## 模組定位

`計劃書/` 保存原始研究計畫資料。這些文件提供專案目標與研究敘事背景，但工程實作以根目錄 README、`docs/architecture/` 與 `docs/project/` 的最新整理為準。

## 目前內容

```text
計劃書/
  AI 3.0 計劃書_以多模態大型語言模型為核心之高齡者在宅健康照護機器人.pdf
  子計畫三_分年工作項目整理.md
```

`子計畫三_分年工作項目整理.md` 用於整理本專案負責的多模態行為感知、隱私保護、邊緣 AI 與緊急應變分年工作項目。第一年度 Demo 的實作調整與驗收階段請對照 `docs/project/hermes_care_assistant_handoff.md` 與 `docs/project/first_year_demo_phase_tasks.md`。

## 與目前實作的對應

| 計畫書方向 | TemiAgent 目前落地方式 |
|---|---|
| 多模態大型語言模型 | Temi ASR + camera snapshots + Hermes / local VLM。 |
| 高齡者在宅健康照護 | Hermes care assistant skills、structured care memory、Home-ESI Lite。 |
| 異常行為偵測 | Vision snapshots + Hermes risk cognition + abnormal event log。 |
| 個人化提醒 | reminders/profile/daily state 與 memory actions。 |
| 緊急應變 | Demo-only `notify_caregiver_mock` 與 L1/L2 風險流程。 |

## 維護注意

- 原始 PDF 不應直接修改；新整理請放在 `docs/project/`。
- 若計畫書目標與工程 scope 有差異，請在 `docs/project/hermes_care_assistant_handoff.md` 補充轉換原因。
