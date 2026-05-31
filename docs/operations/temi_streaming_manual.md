# TemiAgent 開發與部署手冊 (Multicast Edition)

本手冊提供 TemiAgent 專案的完整操作指南，包含環境設定、編譯、部署、多點廣播 (Multicast) 設定，以及電腦端大腦 (VLM / Hermes) 的接收與測試流程。

---

## 1. 專案環境與架構說明

*   **Android 端專案路徑**: `F:\sdk\TemiAgent`
*   **Python 後端專案路徑**: `F:\sdk\TemiAgent\temi_backend`
*   **Android Package**: `com.robotemi.agent`
*   **視覺傳輸協定**: Pure WebSocket (傳輸 H.264 影像與硬體時間戳)
*   **控制與語音協定**: MQTT (發布 ASR 結果，訂閱 Speak/Navigate 動作)
*   **核心特色**: 支援**多點廣播 (Multicast)**，Temi 可同時將視覺與聽覺同步傳送給多台電腦 (例如原生測試 PC 與 Hermes Agent 專用機)。

---

## 2. 環境變數設定 (local.properties)

在編譯之前，必須先設定 Temi 要連線的電腦 IP。
請開啟或建立 `F:\sdk\TemiAgent\local.properties`，並設定以下參數（支援以逗號分隔多組 IP 以開啟 Multicast 功能）：

```properties
# 您的 Android SDK 安裝路徑 (編譯時必須)
sdk.dir=C\:\\Users\\LAB-606\\AppData\\Local\\Android\\Sdk

# WebSocket 影像接收端 IP (可設定多個)
ws.server.urls=ws://192.168.50.233:8080,ws://192.168.50.236:8080

# MQTT 語音與動作中樞 IP (可設定多個)
mqtt.broker.urls=tcp://192.168.50.233:1883,tcp://192.168.50.236:1883

# 機器人的 MQTT 客戶端 ID 前綴
mqtt.client.id=temi-agent
```

---

## 3. 編譯指令 (Building APK)

每當修改 Java/XML 程式碼，或更新了 `local.properties` 後，請在專案根目錄執行此指令生成安裝檔：

```powershell
cd F:\sdk\TemiAgent
./gradlew assembleDebug
```

*   **成功生成檔案路徑**: `F:\sdk\TemiAgent\app\build\outputs\apk\debug\app-debug.apk`

---

## 4. 連線與部署 (ADB Deployment)

### A. 無線連接 Temi 機器人
確保您的電腦與 Temi 處於同一個 Wi-Fi 網域。
```powershell
adb connect 192.168.50.205
```

### B. 安裝 APK 到 Temi
```powershell
adb install -r "F:\sdk\TemiAgent\app\build\outputs\apk\debug\app-debug.apk"
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

### B. 啟動視覺神經中樞 (`vision_server.py`)
負責接收 WebSocket 影片流並解碼為 `debug_frames/`，供 LLM 取樣：
```powershell
cd F:\sdk\TemiAgent\temi_backend
uv run vision_server.py
```
*(注意：若使用 Multicast，兩台 PC 都必須各自啟動 `vision_server.py` 才能看見畫面)*

### C. 啟動大腦路由 (任選一)
1. **使用內建的 `agent_core.py` (串接 LMStudio)**:
   ```powershell
   uv run agent_core.py
   ```
2. **使用原生的 Hermes Agent**:
   將 `F:\sdk\TemiAgent\skills\temi_control` 資料夾放入 Hermes 的全域技能庫中，讓 Hermes 親自呼叫 `scripts/speak.py` 來發號施令。

---

## 7. 標準開發工作流 (Workflow)

為保持開發高效率，建議遵循以下開發迴圈：
1. **修改與設定**: 調整 `local.properties` 或 Java 程式碼。
2. **一鍵編譯安裝與重啟**:
   ```powershell
   ./gradlew assembleDebug ; adb install -r "F:\sdk\TemiAgent\app\build\outputs\apk\debug\app-debug.apk" ; adb shell am force-stop com.robotemi.agent ; adb shell am start -n com.robotemi.agent/.MainActivity
   ```
3. **驗證連線**: 觀察 PC 端的 `vision_server.py` 是否印出接收到 Frame 的紀錄。

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
