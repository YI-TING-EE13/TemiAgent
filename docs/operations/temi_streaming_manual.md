# TemiAgent 開發與部署手冊 (Multicast Edition)

本手冊提供 TemiAgent 專案的完整操作指南，包含環境設定、編譯、部署、多點廣播 (Multicast) 設定，以及電腦端大腦 (VLM / Hermes) 的接收與測試流程。

---

## 1. 專案環境與架構說明

*   **Android 端專案路徑**: `<android-project-root>`
*   **Python 後端專案路徑**: `<android-project-root>\temi_backend`
*   **Android Package**: `com.robotemi.agent`
*   **視覺傳輸協定**: Pure WebSocket (傳輸 H.264 影像與硬體時間戳)
*   **控制與語音協定**: MQTT (發布 ASR 結果，訂閱 Speak/Navigate 動作)
*   **核心特色**: 支援**多點廣播 (Multicast)**，Temi 可同時將視覺與聽覺同步傳送給多台電腦 (例如原生測試 PC 與 Hermes Agent 專用機)。

---

## 2. 環境變數設定 (local.properties)

在編譯之前，必須先設定 Temi 要連線的電腦 IP。
請開啟或建立 `<android-project-root>\local.properties`，並設定以下參數（支援以逗號分隔多組 IP 以開啟 Multicast 功能）：

先將 `<android-sdk-path>`、`<pc-ip>` 與 `<secondary-pc-ip>` 替換為目前開發環境的值；
不要把個人路徑或私人網路位址提交到版本控制。

```properties
# 您的 Android SDK 安裝路徑 (編譯時必須)
sdk.dir=<android-sdk-path>

# WebSocket 影像接收端 IP (可設定多個)
ws.server.urls=ws://<secondary-pc-ip>:8080,ws://<pc-ip>:8080

# MQTT 語音與動作中樞 IP (可設定多個)
mqtt.broker.urls=tcp://<secondary-pc-ip>:1883,tcp://<pc-ip>:1883

# 機器人的 MQTT 客戶端 ID 前綴
mqtt.client.id=temi-agent
```

---

## 3. 編譯指令 (Building APK)

每當修改 Java/XML 程式碼，或更新了 `local.properties` 後，請在專案根目錄執行此指令生成安裝檔：

```powershell
cd <android-project-root>
./gradlew assembleDebug
```

*   **成功生成檔案路徑**: `<android-project-root>\app\build\outputs\apk\debug\app-debug.apk`

---

## 4. 連線與部署 (ADB Deployment)

### A. 無線連接 Temi 機器人
確保您的電腦與 Temi 處於同一個 Wi-Fi 網域。
```powershell
adb connect <temi-ip>
```

### B. 安裝 APK 到 Temi
```powershell
adb install -r "<android-project-root>\app\build\outputs\apk\debug\app-debug.apk"
```
*   `-r`: 覆蓋安裝，保留原有授權與設定資料。

---

## 5. 應用程式控制 (App Management)

### A. 強制啟動 App
透過指令直接喚醒 Temi 上的 Agent 程式：
```powershell
adb shell am start -n com.robotemi.agent/.MainActivity
```

### B. 強制停止 App
當需要重啟或釋放相機資源時：
```powershell
adb shell am force-stop com.robotemi.agent
```

---

## 6. 電腦端接收中樞 (PC Backend / Hermes Agent)

為了讓大腦看見與聽見，您必須在目標電腦上啟動以下服務：

### A. 啟動 MQTT Broker
請確保您的電腦上已安裝並運行 Mosquitto (或任何相容的 Broker)，預設 Port 為 `1883`。

### B. 啟動 legacy backend

`temi_backend` 接收 WebSocket H.264 影像、維護 vision buffer，並提供 legacy
MQTT／VLM route。請在指定 container 內執行 package entrypoint：

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
cd /TemiAgent/temi_backend
uv run temi-backend
```

若 Android multicast 同時送往兩台 PC，每台接收端都必須各自啟動相容的
`temi_backend` 或 Overview adapter。

### C. 啟動 canonical Hermes／Bridge route

Canonical route 使用 `tools/temi_overview_adapter.py`、Hermes resident 與
HermesTemiBridge。Hermes 只回傳 JSON action plan；Bridge 驗證後才發布
`temi/{robot_id}/cmd/request`。不要讓 Hermes 直接呼叫硬體 script。

完整啟動順序與 health checks 見
[`temi_integration_runbook.md`](temi_integration_runbook.md)。

---

## 7. 標準開發工作流 (Workflow)

為保持開發高效率，建議遵循以下開發迴圈：
1. **修改與設定**: 調整 `local.properties` 或 Java 程式碼。
2. **一鍵編譯安裝與重啟**:
   ```powershell
   ./gradlew assembleDebug ; adb install -r "<android-project-root>\app\build\outputs\apk\debug\app-debug.apk" ; adb shell am force-stop com.robotemi.agent ; adb shell am start -n com.robotemi.agent/.MainActivity
   ```
3. **驗證連線**: 觀察 `temi_backend` 或 Overview adapter log 是否收到 frame，並檢查對應 port 與 health evidence。

---

## 8. 調錯與監控 (Diagnostics)

### 監控 Android 即時日誌
若懷疑網路連線失敗或 ASR 沒有觸發，可使用以下指令過濾出核心的 Logcat：
```powershell
adb logcat *:I | Select-String "MainActivity|WebSocketClient|MqttManager|CameraManager|AgentStateMachine"
```

**常見日誌狀態判讀**：
*   `WebSocketClient: Opening socket to...` ➔ 正在嘗試建立影片傳輸。
*   `MqttManager: Connected successfully.` ➔ 成功連線到 MQTT Broker。
*   `AgentStateMachine: Transitioned to: ASR_LISTENING` ➔ Temi 正在聆聽您的語音指令。
*   `MainActivity: ACTION_SPEAK: "你好"` ➔ 成功從 PC 端收到講話的 MQTT 指令。
