---
name: video-slicing-skill
description: 把 1.5–2 小时的课程/讲座/会议录播切成可直接发布的知识点短视频。字级时间戳做时间轴金标准，人工审查做文本兜底，领域词表做术语三层兜底。当用户提出「把这段讲座/课程/会议切成短视频」「给课程录像做字幕」「从长视频里提取知识点」等需求时启用。含 3 种 ASR 方案、3 种电影级字幕断句模式、沉淀积累闭环。
---

# video-slicing-skill

长视频 → 短视频的完整流水线。**你是流水线的协调者，不是决策者**——7 个关键决策点必须停下来问用户，不许自作主张。所有提问话术见 [references/elicitation.md](references/elicitation.md)。

---

## 三条铁律（开工前先读）

1. **时间轴只信字级时间戳**——任何替换/清理/重排操作都不许动时间戳，只许改文本
2. **文本只信人工校对**——LLM（包括你）永远只提建议，永不落笔改字幕
3. **任何自动替换都要可追溯、可回滚**——每次改动写进报告，出问题能退到上一步

---

## 场景边界（只管三个大场景）

本 Skill 的能力边界固定为 **S1 口播 / S2 字幕 / S3 高光剪辑**，不接第四类需求。接到任务先判场景，判定规则、依赖顺序（S2 → S1 → S3）、允许适配的参数、6 条硬性约束，全部见 [references/scope-and-adaptation.md](references/scope-and-adaptation.md)。

- 允许按用户情况适配：领域、ASR 方案、断句模式、目标平台、词表来源（必须问用户）
- 不允许适配：时间轴来源、文本决定权、可追溯性、词表回写的人工确认
- 超出 S1–S3 的需求：明确告知超范围，给替代建议，不硬做

**三场景共用同一套时间轴与文本纪律；S3 额外依赖 ffmpeg 与已完成字幕**：

| 场景 | 工具支撑 | 主链路 |
|---|---|---|
| S1 口播 | ✅ 完整 | merge → proofread → clean_oral → 文字稿 |
| S2 字幕 | ✅ 完整 | build_subtitles 三模式 + 帧吸附 |
| S3 高光剪辑 | ✅ 完整 | propose_cuts → 人工确认 → generate_slices → verify_slices |

---

## 工作流总览（8 步，其中 7 个必停点，★ = 必停问用户）

```
① 任务摸底 ★        → 问用户：视频时长/领域/有无现成词表
② 选 ASR 方案 ★     → 问用户：字级必需吗？预算？本地 or 云端？
③ 领域词表定制 ★    → 问用户：领域是？现成词表？要我帮你起草案吗？
④ 转写 + 文字稿      → 自动：ASR → 字级 SRT → 句级 → 术语替换
⑤ LLM 校对 ★★      → 自动出 TSV 后必停：请用户人工审查
⑥ 沉淀回写 ★        → 列出本轮新发现的术语对，问用户哪些写进词表
⑦ 选断句模式 ★      → 问用户：整句 / 半句 / 碎句？
⑧ 生成字幕 + 切片    → 自动：build_subtitles → 切点确认 ★ → ffmpeg 切片
```

**任何一步没问用户就往下跑，都是违规。**

---

## 各步骤要点

### ① 任务摸底（必停）

拿到视频后先问：

- 视频是什么领域？（儒学/医学/法律/编程/其他）
- 时长大概多少？
- 有没有现成的术语表 / 热词表 / 领域 Prompt？

**话术模板**：见 [references/elicitation.md#1-任务摸底](references/elicitation.md)

### ② 选 ASR 方案（必停）

3 个方案各有取舍，**不许默认**，必须让用户选：

| 方案 | 字级时间戳 | 自带标点 | 成本 | 隐私 | 适用 |
|---|---|---|---|---|---|
| A. 剪映 ASR | ✅ | ❌ | 免费 | ⚠️ 音频上传云端 | 主推：字级是时间轴金标准 |
| B. Whisper.cpp + 领域 Prompt | ❌ | ✅ | 免费（本地） | ✅ 完全离线 | 对照抓漏字 |
| C. 火山方舟豆包语音 | ✅ | ✅ | 按量付费 | ⚠️ 音频上传云端 | 商业项目、热词需求强 |

⚠️ **只有 B 全程离线**。A 走剪映云端（非官方逆向接口，可能随时失效）；C 走火山官方 API。
涉密/未公开课程必须先确认能否外传。方案 C 本仓库**只给接入示意、未提供实现**。

详细对比与安装：[references/asr-engines.md](references/asr-engines.md)
**话术模板**：[references/elicitation.md#2-选-asr-方案](references/elicitation.md)

### ③ 领域词表定制（必停）

- 如果用户有现成词表 → 让用户给路径，跳过
- 如果用户没有 → **主动提议帮他起草**，根据他提供的领域和样本视频，从 `references/lexicons/_template.txt` 出发填 20–50 个高频术语
- 儒学领域可以直接用 `references/lexicons/confucian.txt` 作起点

**话术模板**：[references/elicitation.md#3-领域词表定制](references/elicitation.md)

### ④ 转写 + 文字稿（自动）

按选定 ASR 方案跑转写，产字级 SRT：

```bash
# 方案 A（剪映 ASR）；装在别处就把 VC_HOME 改成实际路径
: "${VC_HOME:=$HOME/VideoCaptioner}"
cd "$VC_HOME" && uv run videocaptioner transcribe "<视频>" \
  --asr jianying --language zh --word-timestamps --format srt -o "字级.srt"

# 方案 B / C 见 references/asr-engines.md
```

然后跑文字稿流水线：

```bash
python3 scripts/merge_srt.py 字级.srt 句级.srt
python3 scripts/proofread.py 句级.srt 句级-术语替换.srt 术语替换表.txt 报告.md
python3 scripts/clean_oral.py 句级-术语替换.srt 句级-清理.srt  # 可选，去口水词
```

### ⑤ LLM 校对（必停两次）

**第一次停**：跑 `proofread_llm.py review` 前，确认用户选了哪个领域的校对 Prompt。

```bash
python3 scripts/proofread_llm.py review 句级-清理.srt 校对建议.tsv \
  --prompt-file references/prompts/proofreader-confucian.md \
  --terms 术语替换表.txt \
  --api-base <URL> --model <NAME> --key <KEY>
```

**第二次停**（**最关键**）：TSV 生成后，**禁止自动合入**。必须告诉用户：

> 「校对建议已生成在 `<路径>/校对建议.tsv`，共 N 句、建议改动 M 句。请人工审查后再让我合入。」

用户确认后才跑：

```bash
python3 scripts/proofread_llm.py apply 句级-清理.srt 校对建议.tsv 句级-校对.srt
```

### ⑥ 沉淀回写（必停）

校对完成后，问用户哪些新发现的术语对要写进词表：

```bash
python3 scripts/consolidate_lexicon.py 校对建议.tsv 术语替换表.txt
# 输出建议新增的术语对清单 → 让用户逐条勾选 → 确认后加 --write 才真写
```

这一步是**越用越准**的关键。详细说明：[references/domain-customization.md#沉淀机制](references/domain-customization.md)

### ⑦ 选断句模式（必停）

让用户从 3 种电影级断句中选 1 种：

| 模式 | 断句位置 | 节奏 | 适用平台 |
|---|---|---|---|
| `sentence` 整句 | 只在 。？！ | 舒缓 | B 站/学术讲座 |
| `clause` 半句 | 在 ，、；：。？！ | 明快 | 视频号/小红书 |
| `fragment` 碎句 | 所有标点 + 长句强断 | 紧凑 | 抖音/快手/Shorts |

详细对比：[references/subtitle-segmentation.md](references/subtitle-segmentation.md)
**话术模板**：[references/elicitation.md#6-选断句模式](references/elicitation.md)

### ⑧ 生成字幕 + 切片

```bash
python3 scripts/build_subtitles.py 字级.srt 句级-校对.srt 精确字幕.srt \
  --mode clause --fps 30

# S3 高光剪辑（S2 完成后才可开工）
python3 scripts/propose_cuts.py 精确字幕.srt 切点表.md --min-secs 30 --max-secs 300
# → 必停：人工复核切点表（可先用 health_map.py 看全片覆盖与长静音）
python3 scripts/make_table.py 切点表.md 精确字幕.srt 切点表-全文.md
python3 scripts/generate_slices.py 切点表.md 源视频.mp4 精确字幕.srt 切片目录
python3 scripts/verify_slices.py 切点表.md 精确字幕.srt 切片目录
# 需要剪映草稿时（已装 capcut-cli）
python3 scripts/generate_drafts.py 切点表.md 源视频.mp4 精确字幕.srt 切片目录
```

> 切片一律重编码（`-c copy` 会吸附关键帧，切点与字幕对不上）。`propose_cuts` 只做初筛，
> **没有人工复核切点表就切片 = 违规**。

---

## 红线（违反任何一条都是 bug）

- ❌ **不许跳过 elicitation 节点**：话术集里标「必停」的必须停
- ❌ **不许替用户选 ASR 方案 / 断句模式**：即使用户说「随便」也要列出选项让他确认
- ❌ **不许自动合入 LLM 校对建议**：必须人工审查 TSV 后再 apply
- ❌ **不许自动回写词表**：`consolidate_lexicon.py` 默认只读，用户加 `--write` 才真写
- ❌ **不许用句级 SRT 做切片依据**：时间轴永远回到字级 SRT

---

## 深入阅读

- 端到端 SOP：[references/sop.md](references/sop.md)
- ASR 三方案详细对比：[references/asr-engines.md](references/asr-engines.md)
- 字幕断句三种模式：[references/subtitle-segmentation.md](references/subtitle-segmentation.md)
- 领域化定制（词表 + Prompt）：[references/domain-customization.md](references/domain-customization.md)
- 引导用户话术集：[references/elicitation.md](references/elicitation.md)
- 已知坑：[references/pitfalls.md](references/pitfalls.md)
- 儒学完整示例：[examples/confucian-course/](examples/confucian-course/)
