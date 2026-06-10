# LM Studio (lms server) 指定可用 GPU：可能解法整理

## 重點結論
- 目前 LM Studio / `lms server` 沒有內建的「指定 GPU 編號」參數。
- `lms load --gpu` 只是控制 GPU offload 比例，**不是**選哪一張卡。
- 通用可行解法是用環境變數 `CUDA_VISIBLE_DEVICES` 限制可見的 GPU。

## 方式一：啟動前設定 CUDA_VISIBLE_DEVICES（最直接）
### Linux / macOS（Shell）
1. 先查 GPU 編號：
   ```bash
   nvidia-smi -L
   ```
2. 限制只使用 GPU 0 和 2：
   ```bash
   CUDA_VISIBLE_DEVICES=0,2 lms server start
   ```
   或先 export 再啟動：
   ```bash
   export CUDA_VISIBLE_DEVICES=0,2
   lms server start
   ```

### Windows（PowerShell）
```powershell
$env:CUDA_VISIBLE_DEVICES = "0,2"
lms server start
```

### Windows（CMD）
```bat
set CUDA_VISIBLE_DEVICES=0,2
lms server start
```

> 這樣 LM Studio 只能「看到」你指定的卡，其他卡就會空出來給別人使用。

## 方式一補充：不同程式使用不同 GPU
`CUDA_VISIBLE_DEVICES` 是每個行程自己的環境變數，可以讓不同程式看到不同 GPU。

範例（同一台機器）：
```bash
# LM Studio 只看到 0,1
CUDA_VISIBLE_DEVICES=0,1 lms server start

# 另一個程式只看到 2,3
CUDA_VISIBLE_DEVICES=2,3 python your_script.py
```

或在不同終端機中設定：
```bash
# Terminal A
export CUDA_VISIBLE_DEVICES=0,1
lms server start

# Terminal B
export CUDA_VISIBLE_DEVICES=2,3
python your_script.py
```

## 方式一補充：設定是否會沿用
- `CUDA_VISIBLE_DEVICES=0,1 lms server start` 只對**那一次指令**有效。
- 只有在**同一個終端機**先 `export CUDA_VISIBLE_DEVICES=0,1`，後續指令才會沿用。
- 若要長期固定，建議寫進啟動腳本或 systemd 服務。

## 方式二：用啟動腳本固定限制 GPU
### Linux（Bash）
建立 `start_lms.sh`：
```bash
#!/usr/bin/env bash
export CUDA_VISIBLE_DEVICES=0,2
lms server start
```
加上可執行權限：
```bash
chmod +x start_lms.sh
```

### Windows（BAT）
建立 `start_lms.bat`：
```bat
@echo off
set CUDA_VISIBLE_DEVICES=0,2
lms server start
```

## 方式三：以 systemd 服務方式固定（適合長期部署）
建立或編輯 service 檔，加入：
```
Environment=CUDA_VISIBLE_DEVICES=0,2
```
範例片段：
```
[Service]
Environment=CUDA_VISIBLE_DEVICES=0,2
ExecStart=/usr/bin/lms server start
```

## 補充注意
- `CUDA_VISIBLE_DEVICES` 只對 CUDA（NVIDIA）有效。
- 如果你是 AMD/Intel GPU，LM Studio 可能走 Vulkan/Metal，不一定支援相同方式。
- 可搭配 `lms load --gpu 0.5` 控制 offload 比例，但仍無法指定 GPU 編號。

## 參考來源
- LM Studio CLI 文件（`lms load --gpu` 說明）：https://lmstudio.ai/docs/cli/local-models/load
- 官方 Issue 討論（建議使用 `CUDA_VISIBLE_DEVICES`）：https://github.com/lmstudio-ai/lms/issues/126


## TemiAgent QAT 單卡/雙卡/三卡測試配方

目前 TemiAgent 的 LM Studio 預設模型是 QAT GGUF 權重 `gemma-4-31b-it-qat`，並用 `--identifier google/gemma-4-31b` 保持 Hermes config 相容。啟動腳本會用 `--gpu max` 載入模型，代表盡可能 100% GPU offload；在 `lms log stream --stats --json` 中看到 `numGpuLayers: -1` 可視為全層 GPU offload 驗證。

### 啟動命令

```bash
cd /TemiAgent

# 單卡，最新建議預設；只讓 LM Studio 看到 GPU 0
LMSTUDIO_VISIBLE_GPUS=0 ./tools/start_lmstudio_3gpu.sh

# 雙卡，讓 LM Studio 看到 GPU 0,1
LMSTUDIO_VISIBLE_GPUS=0,1 ./tools/start_lmstudio_3gpu.sh

# 三卡，讓 LM Studio 看到 GPU 0,1,2
LMSTUDIO_VISIBLE_GPUS=0,1,2 ./tools/start_lmstudio_3gpu.sh
```

啟動後確認：

```bash
lms ps
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
```

### 測速命令

先開一個 log stream 觀察 stats：

```bash
lms log stream --stats --json
```

另開一個 shell 跑固定 prompt：

```bash
lms chat google/gemma-4-31b --stats -p "Generate exactly 220 short bullet points about safe home-care robot behaviors. Use plain English. Do not include an introduction or conclusion."
```

### 2026-06-10 實測結果

| GPU setting | VRAM after load | Tokens/s | Notes |
| --- | --- | ---: | --- |
| `LMSTUDIO_VISIBLE_GPUS=0` | GPU0 約 26.5 GiB，GPU1/2 約 15 MiB | 63.00, 63.27 | `numGpuLayers=-1`，全 GPU offload；目前建議預設 |
| `LMSTUDIO_VISIBLE_GPUS=0,1` | GPU0 約 13.9 GiB，GPU1 約 14.4 GiB，GPU2 約 15 MiB | 62.73, 63.58 | 速度與單卡/三卡幾乎相同 |
| `LMSTUDIO_VISIBLE_GPUS=0,1,2` | GPU0 約 9.7 GiB，GPU1 約 9.0 GiB，GPU2 約 10.6 GiB | 63.37 | 速度沒有明顯優勢，但佔用三張卡 |

結論：QAT `gemma-4-31b-it-qat` 在單張 32 GiB GPU 上可用 `--gpu max` 全層 GPU offload，速度約 63 token/s，和雙卡/三卡幾乎相同。除非需要降低單卡 VRAM 壓力，建議先用單卡釋放 GPU 1/2 給其他服務。
