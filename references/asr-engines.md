# ASR 三方案详细对比

> 同一段 297 秒音频、20 句人工精校真值的实测对比。
> 结论先行：**字级时间戳是切片场景的硬约束**，主推方案 A。

## 对比表

| 维度 | A. 剪映 ASR | B. Whisper.cpp | C. 火山方舟豆包语音 |
|---|---|---|---|
| **CER（字错误率）** | **15.2%** | 17.7% | ~15% |
| **字级时间戳** | ✅ 有 | ❌ 无 | ✅ 有 |
| **自带标点** | ❌ 无 | ✅ 有 | ✅ 有 |
| **热词注入** | ❌ 无 | ⚠️ 通过 Prompt 有限支持 | ✅ 强 |
| **成本** | 免费 | 免费（本地） | 约 1-5 元/小时 |
| **隐私** | 本地（调剪映引擎） | 完全本地 | 云端 |
| **安装难度** | 中（需 VideoCaptioner） | 中（需编译 whisper.cpp + 下模型） | 低（只需 API Key） |
| **适用场景** | 课程切片主力 | 抓漏字对照 | 商业项目、热词强需求 |

## 方案 A：剪映 ASR（主推）

**核心优势**：字级时间戳精确到每个汉字，这是「时间轴金标准」的物理基础。
**核心劣势**：无标点、无热词注入——都靠后处理补。

### 安装

```bash
# VideoCaptioner 是调剪映 ASR 引擎的命令行封装
git clone https://github.com/WEIFENG2333/VideoCaptioner ~/VideoCaptioner
cd ~/VideoCaptioner && uv sync
```

前置：装 [uv](https://github.com/astral-sh/uv)（Python 包管理器）。

### 使用

```bash
cd ~/VideoCaptioner
uv run videocaptioner transcribe "<源视频>.mp4" \
  --asr jianying --language zh --word-timestamps --format srt \
  -o "字级.srt"
```

关键参数：
- `--asr jianying`：用剪映 ASR 引擎（免费、无需登录）
- `--word-timestamps`：输出字级时间戳（**必须加**，否则变句级）
- `--format srt`：输出 SRT 格式

## 方案 B：Whisper.cpp + 领域 Prompt（对照抓漏字）

**核心优势**：自带标点、本地跑、可通过 Prompt 注入领域知识。
**核心劣势**：无字级时间戳，不能直接当时间轴用。

### 安装

```bash
# macOS (Apple Silicon)
brew install whisper-cpp

# 下载模型（推荐 large-v3，4.6GB）
mkdir -p ~/.cache/whisper
curl -L -o ~/.cache/whisper/ggml-large-v3.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin
```

### 使用

```bash
whisper-cli \
  -m ~/.cache/whisper/ggml-large-v3.bin \
  -l zh \
  --prompt "以下是儒学课程的转写，涉及《大学》《中庸》《论语》《孟子》等经典，术语：人禽之辨、义利之辨、恻然、截然、牟宗三、钱穆..." \
  -f "<音频>.wav" \
  -osrt -of "whisper句级"
```

**Prompt 是关键**：把领域高频术语列进去，能显著提升术语准确率（四辨命中 0/4 → 4/4）。

## 方案 C：火山方舟豆包语音（商业方案）

**核心优势**：热词注入最强、字级时间戳、自带标点、与剪映 ASR 同源（豆包语音大模型）。
**核心劣势**：按量付费、需火山引擎账号与 API Key。

### 准备

1. 注册火山引擎 → 开通「豆包语音」服务
2. 创建 API Key + Secret Key
3. 准备热词表（TXT，一行一词）

### 使用（示例 SDK 调用，详见火山文档）

```python
# 伪代码示意，具体 API 见火山引擎文档
from volcengine import speech

client = speech.Client(ak, sk)
result = client.transcribe(
    audio="源视频.mp3",
    language="zh",
    word_timestamps=True,        # 字级时间戳
    hot_words="热词表.txt",      # 热词注入
    enable_punctuation=True      # 自带标点
)
```

## 选型决策树

```
要不要字级时间戳？
├─ 要 → 有预算且要热词？ ── 是 → 方案 C
│        └─ 否 → 方案 A（主推）
└─ 不要 → 只做对照抓漏字 → 方案 B
```

**推荐组合**：
- **精度优先**：A 主力 + B 对照（抓漏字类错误，词表和拼音都抓不到的那种）
- **效率优先**：A 单通道
- **商业项目**：C 单通道（热词一次注入，省后处理）

## 常见坑

1. **VideoCaptioner 的 whisper 通道**：`--asr whisper` 模式下 zh 语言的 Prompt 是硬编码的泛化 Prompt，**不会注入你的术语**。要用 Whisper 就自己调 `whisper-cli`。
2. **字级时间戳的精度**：剪映 ASR 给的是字级，但字的边界不一定 100% 准——这是物理上限，靠后处理吸附到帧边界。
3. **火山的签名 URL 有效期短**：SDK 返回的下载 URL 只有几分钟有效期，要立刻下载。
