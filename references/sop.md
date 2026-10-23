# 端到端 SOP

> 从拿到源视频到交付短视频的完整操作手册。
> 每一步的输入输出都是可读文本，随时可以人工插手。

## 前置检查

```bash
# 1. 基础依赖
which python3 ffmpeg ffprobe
python3 --version  # ≥ 3.9（方案 A 的 VideoCaptioner 需 3.10–3.12）

# 2. 按 ASR 方案选装
# 方案 A: VideoCaptioner（默认装在 ~/VideoCaptioner，可用 VC_HOME 指定别处）
: "${VC_HOME:=$HOME/VideoCaptioner}"
ls "$VC_HOME/pyproject.toml"

# 方案 B: whisper.cpp
which whisper-cli

# 方案 C: 火山方舟（无需本地装，要 API Key）
echo $VOLC_ACCESS_KEY
```

## 全流程命令（以方案 A 为例）

### Step 1 — 转写

```bash
: "${VC_HOME:=$HOME/VideoCaptioner}"
cd "$VC_HOME"
uv run videocaptioner transcribe "<源视频>.mp4" \
  --asr jianying --language zh --word-timestamps --format srt \
  -o "<工作目录>/字级.srt"
```

产出：**字级 SRT**（每个汉字都有独立起止时间）——这是时间轴的金标准。

### Step 2 — 字级 → 句级

```bash
python3 scripts/merge_srt.py 字级.srt 句级.srt
```

把字级 SRT 按静音间隔合并成句级（便于阅读与后续处理）。

### Step 3 — 术语替换（确定性）

```bash
python3 scripts/proofread.py 句级.srt 句级-术语.srt 术语替换表.txt 术语替换报告.md
```

把词表里的「误写 => 正写」确定性替换（长词优先、顺序应用），零风险。

### Step 4 — 口语清理（可选）

```bash
python3 scripts/clean_oral.py 句级-术语.srt 句级-清理.srt
```

只删「嗯、呃、啊、哦、噢、诶、哎、唉」这类纯口水音，**不删**「这个、就是、好」等正常用词，
也**不删**「哈」（否则「哈佛」会被削成「佛」）。默认表之外的字符需用 `--filler` 显式指定。
删完会顺手收掉因删字产生的粘连标点（「，，」→「，」），时间戳一律不动，「肫肫」「夭夭」等经典叠字有守卫不会误删。
本脚本**不做**「删讲错重讲」的语义判断——那需要听音频，交给人工。
**必须在字级对齐之前跑**——只改文本不动时间戳。

### Step 5 — LLM 校对（人工审）

```bash
# 5.1 LLM 出建议（必停选 Prompt，见 elicitation.md#4-llm-校对双停）
python3 scripts/proofread_llm.py review 句级-清理.srt 校对建议.tsv \
  --prompt-file references/prompts/proofreader-confucian.md \
  --terms 术语替换表.txt \
  --api-base <URL> --model <NAME> --key <KEY>

# 5.2 人工审查 TSV ★ 强制停

# 5.3 合入高置信
python3 scripts/proofread_llm.py apply 句级-清理.srt 校对建议.tsv 句级-校对.srt
```

### Step 6 — 沉淀回写

```bash
# 先看建议（默认只读，不写文件）
python3 scripts/consolidate_lexicon.py 校对建议.tsv 术语替换表.txt

# 用户逐条确认后真写
python3 scripts/consolidate_lexicon.py 校对建议.tsv 术语替换表.txt --write
```

### Step 7 — 生成精确字幕

```bash
python3 scripts/build_subtitles.py 字级.srt 句级-校对.srt 精确字幕.srt \
  --mode clause --fps 30
```

用字级时间戳对齐清理后的文本，按选定断句模式切条。

### Step 8 — 切片

```bash
# 快切（-c copy）：秒级完成，但切点会被吸附到最近的关键帧，
# 关键帧间隔 2s 时可能偏 ±1s，与「切点卡在字幕条间隙」的精度要求不符
ffmpeg -ss 00:10:23 -to 00:12:45 -i 源视频.mp4 -c copy 切片01-快切.mp4

# 精切（重编码）：切点精确到帧，慢一些但语句不会差几个字
ffmpeg -ss 00:10:23 -to 00:12:45 -i 源视频.mp4 \
  -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k 切片01.mp4
```

**怎么选**：交付级切片用精切；只是自己快速预览用 `-c copy`。
若源视频关键帧密集（GOP ≤ 1s），`-c copy` 的偏差通常可接受，可先用 `ffprobe` 看 `keyint`。

> v0.1 只给这条命令，批量切片与切点自动校验在 v0.3（见 README Roadmap）。

---

## 中间产物速查

| 文件 | 作用 | 可读 |
|---|---|---|
| 字级.srt | 时间轴金标准 | ✅ |
| 句级.srt | 阅读用 | ✅ |
| 句级-术语.srt | 确定性替换后 | ✅ |
| 句级-清理.srt | 去口水词后 | ✅ |
| 校对建议.tsv | LLM 提的待审稿 | ✅ |
| 句级-校对.srt | 人工确认后合入 | ✅ |
| 术语替换报告.md | 每次替换可追溯 | ✅ |
| 精确字幕.srt | 最终交付字幕 | ✅ |
| 切点表.md | 切片起止清单 | ✅ |

**任何一步出问题，回到上一步的文本文件改完再往下跑，不要从头重跑。**

## 覆盖保护（重跑必读）

所有脚本默认**拒绝覆盖已存在的输出文件**，两种解法：

```bash
# 1) 换一个输出名（推荐，保留上一版便于对比）
python3 scripts/merge_srt.py 字级.srt 句级-v2.srt

# 2) 确认旧产物没用了，显式加 --force
python3 scripts/merge_srt.py 字级.srt 句级.srt --force
```

输入与输出是同一个文件时无条件拒绝——那是唯一会**不可回滚**毁掉原稿的操作。

`proofread_llm.py apply` 另有一道双键校验：TSV 的「起秒 + 原句」必须与源稿逐字一致才合入，
对不上就整体中止、不写任何文件（退出码 3）。
