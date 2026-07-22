# LM Studio Headless 啟動手冊：HDD 專案路徑與指定 GPU 組合

本手冊用於在 **Linux / headless / container-like environment** 中啟動 LM Studio local server，並將 LM Studio 的資料目錄固定在專案 HDD 路徑 `/TemiAgent/.lmstudio-data`，同時用 LMSTUDIO_VISIBLE_GPUS 控制 LM Studio daemon 與模型 worker 使用單卡、雙卡或三卡。

路徑說明：`/TemiAgent` 是 TemiAgent GPU container 內的專案路徑；host workspace 對應路徑是 `/home/yiting/TemiAgent`。
目前預設：載入 QAT 模型 `temi/gemma-4-31b-it-qat`，並用 `--identifier google/gemma-4-31b` 保持 Hermes / Bridge 既有 API model 名稱相容。下載命令：`lms get https://huggingface.co/unsloth/gemma-4-31B-it-qat-GGUF --gguf -y`；底層來源為 `unsloth/gemma-4-31B-it-qat-GGUF` 的 `UD-Q4_K_XL`。

`temi/gemma-4-31b-it-qat` 是專案提供的 LM Studio virtual model。`tools/start_lmstudio_3gpu.sh` 會把 `tools/lmstudio_model_definitions/gemma-4-31b-it-qat.model.yaml` 安裝到 LM Studio hub 目錄；它保留 Google 2026-07-09 canonical template 的 null、thinking、tool response、continuation 與 generation-prompt 修正，同時使用 LM Studio 相容的 tool-schema formatter，避免直接載入 Unsloth GGUF 時出現 Jinja `UndefinedValue` 錯誤。

目標架構如下：

```text
Hermes Agent / Bridge / Skills
        ↓
OpenAI-compatible API
        ↓
LM Studio local server
        ↓
QAT 模型 temi/gemma-4-31b-it-qat，API identifier google/gemma-4-31b
        ↓
GPU 組合由 LMSTUDIO_VISIBLE_GPUS 指定，預設 GPU 0
```

---

## 1. 適用情境

本手冊適用於以下情況：

- 你沒有 LM Studio GUI，只能使用 Linux CLI。
- 你希望 LM Studio 的 runtime、model cache、CLI 與相關資料放在 HDD 專案路徑。
- 你的專案路徑是：

```bash
/TemiAgent
```

- LM Studio 的 target dir 是：

```bash
/TemiAgent/.lmstudio-data
```

- 你有四張 GPU，但希望用 `LMSTUDIO_VISIBLE_GPUS` 控制 LM Studio 使用哪幾張，例如：

```text
單卡：GPU 0
雙卡：GPU 0, GPU 1
三卡：GPU 0, GPU 1, GPU 2
```

未列入 `LMSTUDIO_VISIBLE_GPUS` 的 GPU 會留給其他服務，例如 GPU 3 給 action viewer/llama.cpp。

---

## 2. 核心原則

啟動順序很重要。

`CUDA_VISIBLE_DEVICES` 必須套在 **LM Studio daemon 啟動時**，也就是：

```bash
CUDA_VISIBLE_DEVICES=0 lms daemon up     # 單卡
CUDA_VISIBLE_DEVICES=0,1 lms daemon up   # 雙卡
CUDA_VISIBLE_DEVICES=0,1,2 lms daemon up # 三卡
```

不能只套在：

```bash
lms load ...
```

因為 `lms load` 通常只是 client 指令，真正載入模型與管理 GPU 的 process 是 LM Studio daemon / worker。

---

## 3. 預設值與可調參數

目前 TemiAgent 預設使用：

```bash
export LMSTUDIO_MODEL_ID=temi/gemma-4-31b-it-qat
export LMSTUDIO_API_IDENTIFIER=google/gemma-4-31b
export LMSTUDIO_CONTEXT_LENGTH=64000
export LMSTUDIO_VISIBLE_GPUS=0
```

未來若要更換模型或 context window，只要同步調整：

- LM Studio 載入參數：`LMSTUDIO_MODEL_ID`、`LMSTUDIO_API_IDENTIFIER`、`LMSTUDIO_CONTEXT_LENGTH`、`LMSTUDIO_VISIBLE_GPUS`
- Hermes config：`model.default`、`model.context_length`、`auxiliary.compression.context_length`

如果 LM Studio 因為同名模型已載入而產生 `:2` 這類 suffix，先用 `lms unload --all` 清掉舊 instance，再重新載入，就可以讓預設 identifier 回到 `google/gemma-4-31b`。如果你刻意要同時載入多個同名 instance，則以 `lms ps` 顯示的 exact identifier 為準。

### 3.1 Gemma 4 12B 是否需要同步更新

12B 不影響目前的標準啟動流程；`tools/start_lmstudio_3gpu.sh` 預設只載入新版 31B。若 12B 只是保留在磁碟上而沒有作為 fallback、開發或 tool-calling 模型，可暫時不更新。

若會實際使用 `google/gemma-4-12b` 或 `google/gemma-4-12b-qat`，則建議重新下載 2026-07 canonical-template 更新後的量化版本。現有本機 12B 權重早於這次模板修正，重新載入舊檔不會取得 null handling、thinking preservation、tool-response continuation 等改善。

```bash
# 一般 12B GGUF
lms get https://huggingface.co/unsloth/gemma-4-12b-it-GGUF --gguf -y

# 12B QAT GGUF
lms get https://huggingface.co/unsloth/gemma-4-12B-it-qat-GGUF --gguf -y
```

直接載入新版 Unsloth GGUF 前，仍要用 LM Studio OpenAI-compatible API 做完整 tool-call 回歸。31B 實測顯示原始 canonical template 會在 LM Studio 的 tool-schema renderer 遇到 Jinja `UndefinedValue`；12B 若出現同樣錯誤，應建立獨立的 LM Studio-compatible virtual model，不要讓它覆蓋目前已驗證的 `temi/gemma-4-31b-it-qat`。

---

## 4. 完整啟動指令

請在 `/TemiAgent` 專案目錄下執行：

```bash
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID=${LMSTUDIO_MODEL_ID:-temi/gemma-4-31b-it-qat}
export LMSTUDIO_API_IDENTIFIER=${LMSTUDIO_API_IDENTIFIER:-google/gemma-4-31b}
export LMSTUDIO_CONTEXT_LENGTH=${LMSTUDIO_CONTEXT_LENGTH:-64000}
export LMSTUDIO_VISIBLE_GPUS=${LMSTUDIO_VISIBLE_GPUS:-0}
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
hash -r

lms unload --all
lms server stop
lms daemon down

CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up

lms server start --port 1234

lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max --identifier "$LMSTUDIO_API_IDENTIFIER"

lms ps
```

如果 `lms load` 進入互動選單，選擇要載入的模型，例如：

```text
temi/gemma-4-31b-it-qat
```

成功後可能會看到類似訊息：

```text
Model loaded successfully.
To use the model in the API/SDK, use the identifier "google/gemma-4-31b".
```

此時 Hermes Agent 可以使用：

```text
base_url = http://localhost:1234/v1
model = google/gemma-4-31b
api_key = lm-studio
```

若 Hermes Agent 的自動偵測把 LM Studio local model 判成 4096 context，請在 Hermes config 加上明確 context override。`/root/.hermes/config.yaml` 範例如下：

```yaml
model:
  provider: custom
  base_url: http://localhost:1234/v1
  default: google/gemma-4-31b
  context_length: 64000
auxiliary:
  compression:
    context_length: 64000
```

重點：

- `default` 要使用 `lms load` 成功後顯示的 64K identifier；目前預設是 `google/gemma-4-31b`。
- `model.context_length` 讓 Hermes main model 通過 64K context guard。
- `auxiliary.compression.context_length` 讓 Hermes auxiliary compression model 不被同一個 4096 auto-detect 問題擋住。

---

## 5. 指令逐行說明

### 5.1 指定 LM Studio 專案根目錄

```bash
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
```

這行指定 LM Studio 的 project root。  
在目前架構中，`/TemiAgent` 是主要專案目錄。

---

### 5.2 指定 LM Studio target dir

```bash
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
```

這行指定 LM Studio 的資料與 runtime 目錄。  
因為希望 LM Studio 放在 HDD 上，所以不要使用預設的 `~/.lmstudio` 作為主要資料位置，而是使用：

```bash
/TemiAgent/.lmstudio-data
```

這個目錄通常會包含：

- `bin/lms`
- `llmster`
- runtime files
- cache
- model metadata
- 其他 LM Studio headless 所需資料

---

### 5.3 將 HDD 版 lms 放到 PATH 最前面

```bash
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
```

這行確保執行 `lms` 時，使用的是 HDD target dir 裡的版本，而不是其他位置的舊版本。

如果不這樣做，可能會發生：

```text
Invalid passkey for lms CLI client
```

因為 CLI 和 daemon 不是同一套 LM Studio state。

---

### 5.4 清除 shell 的 command path cache

```bash
hash -r
```

Bash 會快取指令位置。  
修改 `PATH` 後執行 `hash -r`，可以強制 shell 重新尋找 `lms` 的實際位置。

---

### 5.5 卸載目前已載入的模型

```bash
lms unload --all
```

這行會卸載所有目前由 LM Studio 載入的模型。  
如果沒有模型，會出現：

```text
No models to unload.
```

這是正常的。

---

### 5.6 停止 LM Studio API server

```bash
lms server stop
```

這行停止目前的 LM Studio local server。  
通常 server 會跑在：

```text
http://localhost:1234
```

如果 server 沒有在跑，可能會顯示錯誤或無事可做，通常不影響後續流程。

---

### 5.7 停止 LM Studio daemon

```bash
lms daemon down
```

這行停止 `llmster` daemon。  
這一步非常重要，因為如果 daemon 已經存在，後續再執行：

```bash
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
```

可能不會重新套用新的 GPU 可見性設定。

---

### 5.8 用指定 GPU 組合啟動 daemon

```bash
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
```

這是整份手冊最重要的一行。

`LMSTUDIO_VISIBLE_GPUS=0` 時只讓 LM Studio daemon 看到 GPU 0；`0,1` 代表 GPU 0 與 GPU 1；`0,1,2` 代表前三張 GPU。未列入的 GPU 理論上不會被 LM Studio daemon / worker 使用。

---

### 5.9 啟動 LM Studio server

```bash
lms server start --port 1234
```

這行啟動 LM Studio local server，並監聽 port 1234。

Hermes Agent 之後可以透過 OpenAI-compatible API 呼叫：

```text
http://localhost:1234/v1
```

例如：

```text
POST /v1/chat/completions
GET  /v1/models
```

---

### 5.10 載入模型

```bash
lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max --identifier "$LMSTUDIO_API_IDENTIFIER"
```

這行載入 local model。

參數說明：

```bash
--context-length "$LMSTUDIO_CONTEXT_LENGTH"
```

設定 context window 長度。TemiAgent 目前預設為 64000 tokens。  
如果 VRAM 不足，可以降低，例如：

```bash
--context-length 32768
```

或：

```bash
--context-length 16384
```

```bash
--gpu max
```

表示盡可能使用 GPU offload。  
這不是指定哪幾張 GPU，而是指定模型盡量放到 GPU 上。  
真正指定可見 GPU 的地方是：

```bash
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
```

---

## 6. 驗證方式

### 6.0 本機驗證紀錄（2026-06-04）

在 `yiting.TemiAgent_gpu_all` container 內已確認：

- `llmster` daemon 與 `llmworker` process environment 均包含 `CUDA_VISIBLE_DEVICES=0,1,2`。
- 已執行 `lms unload --all` 後重新載入 `google/gemma-4-31b`，避免同名 instance 產生 `:2` suffix。
- `lms ps` 顯示：
  - `google/gemma-4-31b`：context `64000`
- `POST /v1/chat/completions` 使用 `google/gemma-4-31b` 可成功回覆。
- 已將 container 內 `/root/.hermes/config.yaml` 修正為 `default: google/gemma-4-31b`、`model.context_length: 64000`、`auxiliary.compression.context_length: 64000`，並先備份為 `/root/.hermes/config.yaml.bak.lmstudio_20260604_0826`。
- 使用真實 Hermes config 啟動 temporary resident probe 後，Hermes resident `/health` 成功回傳 `status: ok`、`model: google/gemma-4-31b`、`provider: custom`、`base_url: http://localhost:1234/v1`。

因此本手冊的核心操作是正確的：GPU 限制必須套在 daemon 啟動，而不是只套在 `lms load`。

### 6.1 確認目前使用哪個 lms

```bash
which lms
readlink -f "$(which lms)"
lms --version
```

理想輸出應該類似：

```text
/TemiAgent/.lmstudio-data/bin/lms
/TemiAgent/.lmstudio-data/bin/lms
CLI commit: 0b2a176
```

重點是 `which lms` 和 `readlink -f` 都應該指向：

```bash
/TemiAgent/.lmstudio-data/bin/lms
```

如果指到其他地方，可能會造成 passkey mismatch。

---

### 6.2 確認 daemon 有吃到 CUDA_VISIBLE_DEVICES

```bash
ps auxeww | grep -i "llmster" | grep -v grep | grep CUDA_VISIBLE_DEVICES
```

理想上應該看到：

```text
CUDA_VISIBLE_DEVICES=0,1,2
```

這表示 LM Studio daemon 是在只看前三張 GPU 的環境下啟動的。

---

### 6.3 確認 server 是否啟動

```bash
curl http://localhost:1234/v1/models
```

如果 server 正常運作，應該會回傳目前可用或已載入的模型資訊。

---

### 6.4 測試 Chat Completions API

請將 `model` 改成 `lms load` 成功後顯示的 identifier，例如：

```text
google/gemma-4-31b
```

測試指令：

```bash
curl http://localhost:1234/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "model": "google/gemma-4-31b",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ],
    "temperature": 0.7,
    "max_tokens": 64
  }'
```

如果有正常回應，代表 OpenAI-compatible API 可用。

---

### 6.5 確認 GPU 使用狀況

```bash
nvidia-smi
```

注意：`nvidia-smi` 仍然可能列出四張 GPU，這是正常的。  
重點不是 GPU 清單有幾張，而是 LM Studio 的 process 是否使用第 4 張 GPU。

更精準的查詢：

```bash
nvidia-smi --query-compute-apps=pid,process_name,gpu_uuid,used_memory --format=csv
```

或：

```bash
nvidia-smi pmon -c 1
```

檢查 LM Studio 相關 process，例如：

```text
llmster
llmworker
node
```

是否只出現在 GPU 0、1、2，而不是 GPU 3。

---

## 7. 常見問題與排查

### 問題 1：出現 Invalid passkey for lms CLI client

錯誤訊息：

```text
Failed to authenticate: Invalid passkey for lms CLI client.
Please make sure you are using the lms shipped with LM Studio.
```

常見原因：

- `lms` CLI 和 daemon 不是同一套 LM Studio installation。
- `PATH` 指到錯誤的 `lms`。
- `LMSTUDIO_TARGET_DIR` 沒有固定到 `/TemiAgent/.lmstudio-data`。
- daemon 是在舊環境下先被啟動的。

處理方式：

```bash
pkill -f llmster
pkill -f llmworker

export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
hash -r

which lms
readlink -f "$(which lms)"
lms --version

CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
```

確認 `which lms` 和 `readlink -f` 都指向：

```bash
/TemiAgent/.lmstudio-data/bin/lms
```

---

### 問題 2：daemon already running

訊息：

```text
The daemon is already running
```

這表示 daemon 已經存在。  
如果它不是用 `CUDA_VISIBLE_DEVICES=0,1,2` 啟動的，就需要先關掉：

```bash
lms daemon down
```

如果還關不掉：

```bash
pkill -f llmster
pkill -f llmworker
```

然後重新啟動：

```bash
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up
```

---

### 問題 3：`nvidia-smi` 還是看到四張 GPU

這是正常的。

`CUDA_VISIBLE_DEVICES=0,1,2` 限制的是 LM Studio daemon / worker process，不是整台機器。

你應該檢查的是：

```bash
nvidia-smi
```

底部 Processes 區塊中，LM Studio 相關 process 是否使用 GPU 3。

---

### 問題 4：模型載入後 Hermes Agent 找不到模型

請確認 `lms load` 完成後顯示的 identifier，例如：

```text
google/gemma-4-31b
```

Hermes Agent 裡的 model 應該填：

```text
google/gemma-4-31b
```

如果 identifier 變成 `google/gemma-4-31b:2`，通常代表同名模型已經載入過。若你要維持預設 identifier，請先執行：

```bash
lms unload --all
lms load google/gemma-4-31b --context-length 64000 --gpu max
lms ps
```

若你刻意保留 `:2` instance，Hermes config 也必須填同一個 exact identifier。

base_url 應該是：

```text
http://localhost:1234/v1
```

api_key 可以使用 placeholder：

```text
lm-studio
```

### 問題 5：Hermes 顯示 context window 只有 4096

Hermes 可能無法從 LM Studio OpenAI-compatible API 正確推得 runtime context。請在 `/root/.hermes/config.yaml` 加上明確整數值：

```yaml
model:
  provider: custom
  base_url: http://localhost:1234/v1
  default: google/gemma-4-31b
  context_length: 64000
auxiliary:
  compression:
    context_length: 64000
```

`model.context_length` 和 `auxiliary.compression.context_length` 都要同步，否則 resident Hermes 可能會在 auxiliary compression 檢查被擋下。

---

## 8. Hermes Agent 建議設定

如果使用 LM Studio OpenAI-compatible API，Hermes Agent 建議設定如下：

```text
BASE_URL=http://localhost:1234/v1
MODEL=google/gemma-4-31b
CONTEXT_LENGTH=64000
API_KEY=lm-studio
```

如果程式使用 OpenAI SDK，概念上會類似：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

response = client.chat.completions.create(
    model="google/gemma-4-31b",
    messages=[
        {"role": "user", "content": "Hello"}
    ]
)
```

### 8.1 Hermes resident health probe

重啟後可以用 temporary port 驗證 Hermes 是否能讀取目前模型：

```bash
cd /TemiAgent
python3 tools/hermes_resident_server.py \
  --host 127.0.0.1 \
  --port 8766 \
  --skill-path /TemiAgent/hermes-agent/skills/temi-robot-control/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-care-memory/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-home-esi/SKILL.md \
  --skill-path /TemiAgent/hermes-agent/skills/temi-discord-care-assistant/SKILL.md
```

另一個 terminal 驗證：

```bash
curl http://127.0.0.1:8766/health
```

成功時應看到：

```json
{"status":"ok","model":"google/gemma-4-31b","provider":"custom","base_url":"http://localhost:1234/v1"}
```

---

## 9. 固定啟動腳本

專案已提供固定啟動腳本：

```bash
tools/start_lmstudio_3gpu.sh
```

預設啟動：

```bash
cd /TemiAgent
./tools/start_lmstudio_3gpu.sh
```

臨時更換模型或 context：

```bash
cd /TemiAgent
LMSTUDIO_MODEL_ID=your/model-id LMSTUDIO_CONTEXT_LENGTH=32768 ./tools/start_lmstudio_3gpu.sh
```

腳本內容等價於：

```bash
#!/usr/bin/env bash
set -euo pipefail

export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID="${LMSTUDIO_MODEL_ID:-temi/gemma-4-31b-it-qat}"
export LMSTUDIO_API_IDENTIFIER="${LMSTUDIO_API_IDENTIFIER:-google/gemma-4-31b}"
export LMSTUDIO_CONTEXT_LENGTH="${LMSTUDIO_CONTEXT_LENGTH:-64000}"
export LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0}"
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH

hash -r

echo "[LM Studio] Using lms:"
which lms
readlink -f "$(which lms)"
lms --version

echo "[LM Studio] Unloading existing models..."
lms unload --all || true

echo "[LM Studio] Stopping server..."
lms server stop || true

echo "[LM Studio] Stopping daemon..."
lms daemon down || true

echo "[LM Studio] Starting daemon with GPU ${LMSTUDIO_VISIBLE_GPUS} only..."
CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up

echo "[LM Studio] Verifying daemon CUDA visibility..."
ps auxeww | grep -i "llmster" | grep -v grep | grep CUDA_VISIBLE_DEVICES || true

echo "[LM Studio] Starting server on port 1234..."
lms server start --port 1234

echo "[LM Studio] Loading model..."
lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max --identifier "$LMSTUDIO_API_IDENTIFIER"

echo "[LM Studio] Current models:"
lms ps
curl -s http://localhost:1234/v1/models || true

echo "[LM Studio] Done."
```

若腳本失去執行權限，可重新設定：

```bash
chmod +x tools/start_lmstudio_3gpu.sh
```

---

## 10. 最終啟動流程摘要

最短可用版：

```bash
export LMSTUDIO_PROJECT_ROOT=/TemiAgent
export LMSTUDIO_TARGET_DIR=/TemiAgent/.lmstudio-data
export LMSTUDIO_MODEL_ID=${LMSTUDIO_MODEL_ID:-temi/gemma-4-31b-it-qat}
export LMSTUDIO_API_IDENTIFIER=${LMSTUDIO_API_IDENTIFIER:-google/gemma-4-31b}
export LMSTUDIO_CONTEXT_LENGTH=${LMSTUDIO_CONTEXT_LENGTH:-64000}
export LMSTUDIO_VISIBLE_GPUS=${LMSTUDIO_VISIBLE_GPUS:-0}
export PATH=/TemiAgent/.lmstudio-data/bin:$PATH
hash -r

lms unload --all
lms server stop
lms daemon down

CUDA_VISIBLE_DEVICES="$LMSTUDIO_VISIBLE_GPUS" lms daemon up

lms server start --port 1234

lms load "$LMSTUDIO_MODEL_ID" --context-length "$LMSTUDIO_CONTEXT_LENGTH" --gpu max --identifier "$LMSTUDIO_API_IDENTIFIER"
lms ps
```

驗證：

```bash
which lms
readlink -f "$(which lms)"
ps auxeww | grep -i "llmster" | grep -v grep | grep CUDA_VISIBLE_DEVICES
curl http://localhost:1234/v1/models
curl http://127.0.0.1:8765/health
nvidia-smi
```

---

## 11. 注意事項

- `CUDA_VISIBLE_DEVICES` 或 `LMSTUDIO_VISIBLE_GPUS` 必須放在 `lms daemon up` 前面；目前建議預設是單卡 `0`。
- 不要讓 daemon 在未設定 GPU 限制時先自動啟動。
- `lms load --gpu max` 只代表盡可能使用 GPU offload，不代表指定 GPU index。
- 真正指定 GPU 可見性的地方是 daemon 啟動環境。
- `nvidia-smi` 顯示四張 GPU 不代表失敗；要看 LM Studio process 是否只佔用 `LMSTUDIO_VISIBLE_GPUS` 指定的 GPU。
- 如果使用 HDD target dir，務必確保 `LMSTUDIO_TARGET_DIR`、`PATH`、`which lms`、`readlink -f "$(which lms)"` 都一致。


---

## 13. 歷史紀錄：QAT 單卡/雙卡/三卡測試（2026-06-10）

以下效能數據來自更新前的 `google/gemma-4-31b-qat`，保留作為硬體比較基準；它不能直接代表 2026-07 更新後 `temi/gemma-4-31b-it-qat` 的速度。新版模型需另行重跑相同 prompt 才能建立可比較數據。當時的啟動參數如下：

```bash
LMSTUDIO_MODEL_ID=google/gemma-4-31b-qat
LMSTUDIO_API_IDENTIFIER=google/gemma-4-31b
LMSTUDIO_CONTEXT_LENGTH=64000
LMSTUDIO_VISIBLE_GPUS=0
```

`tools/start_lmstudio_3gpu.sh` 雖保留原檔名以維持相容，但目前可用 `LMSTUDIO_VISIBLE_GPUS` 控制單卡、雙卡或三卡：

```bash
# 單卡，建議預設
LMSTUDIO_VISIBLE_GPUS=0 ./tools/start_lmstudio_3gpu.sh

# 雙卡
LMSTUDIO_VISIBLE_GPUS=0,1 ./tools/start_lmstudio_3gpu.sh

# 三卡
LMSTUDIO_VISIBLE_GPUS=0,1,2 ./tools/start_lmstudio_3gpu.sh
```

模型載入指令使用 `--gpu max`，並可用 `lms log stream --stats --json` 的 `numGpuLayers: -1` 確認全層 GPU offload。實測時，單卡 GPU 0 載入後 VRAM 約 26.5 GiB，GPU 1/2 幾乎空閒；雙卡約分攤到 GPU 0/1 各 14 GiB；三卡約分攤到 GPU 0/1/2 各 9-11 GiB。

固定測速 prompt：

```bash
lms chat google/gemma-4-31b --stats -p "Generate exactly 220 short bullet points about safe home-care robot behaviors. Use plain English. Do not include an introduction or conclusion."
```

| GPU setting | Tokens/s | Result |
| --- | ---: | --- |
| 單卡 `0` | 63.00, 63.27 | 建議預設；`numGpuLayers=-1` |
| 雙卡 `0,1` | 62.73, 63.58 | 與單卡幾乎相同 |
| 三卡 `0,1,2` | 63.37 | 與單卡幾乎相同，但佔用三張卡 |

歷史結論：當時的 QAT 31B 模型在單張 32 GiB GPU 上可保持約 63 token/s，且可保留 GPU 1/2 給其他服務或測試。若新版模型的 context、parallel 或 VRAM 使用量增加，再以同一測試方法評估是否切到雙卡或三卡。
