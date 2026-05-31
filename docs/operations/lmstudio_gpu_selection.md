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
