# 儒学课程切片完整示例

> 用一段真实的 1.5 小时《孟子》答疑课录播，走完整条流水线。
> 你可以把这个目录当作「操作沙盘」——照着重做一遍，就知道每一步在干什么。

## 场景设定

- **源视频**：`孟子答疑课-20260315.mp4`（1 小时 38 分钟，台湾老师讲《孟子·离娄上》）
- **领域**：儒学 / 国学
- **目标平台**：视频号（主） + B 站（备）
- **词表**：直接用 `../../references/lexicons/confucian.txt`
- **校对 Prompt**：直接用 `../../references/prompts/proofreader-confucian.md`

## 逐步操作

### ① 任务摸底

回答 Agent 的三连问：
- 领域 → 儒学（有现成词表）
- 时长 → 98 分钟（标准流程）
- 现成资料 → 有，词表 + Prompt 都用仓库自带儒学版

### ② 选 ASR 方案

选 **方案 A（剪映 ASR）** —— 字级时间戳是后续一切的金标准，免费。

### ③ 领域词表

直接用 `references/lexicons/confucian.txt`，无需修改。

### ④ 转写 + 文字稿

```bash
# 转写（VideoCaptioner 调剪映 ASR）；装在别处就把 VC_HOME 改成实际路径
: "${VC_HOME:=$HOME/VideoCaptioner}"
cd "$VC_HOME"
uv run videocaptioner transcribe "孟子答疑课-20260315.mp4" \
  --asr jianying --language zh --word-timestamps --format srt \
  -o "字级.srt"

# 字级 → 句级（便于阅读）
python3 ../../scripts/merge_srt.py 字级.srt 句级.srt

# 术语替换（确定性，零风险）
python3 ../../scripts/proofread.py 句级.srt 句级-术语.srt \
  ../../references/lexicons/confucian.txt 术语替换报告.md

# 口语清理（去"啊、呃"等，守卫经典叠字）
python3 ../../scripts/clean_oral.py 句级-术语.srt 句级-清理.srt
```

中间产物：
- `字级.srt`：约 1.1 万条，每条 0.2–0.6 秒
- `句级.srt`：约 800 条，阅读用
- `句级-术语.srt`：替换「人禽之变 → 人禽之辨」「截染 → 截然」等约 40 处
- `句级-清理.srt`：去掉约 300 个口水字（「肫肫其仁」等经典叠字已守卫）

### ⑤ LLM 校对（双停）

**第一次停**：确认用 `proofreader-confucian.md`。

```bash
python3 ../../scripts/proofread_llm.py review 句级-清理.srt 校对建议.tsv \
  --prompt-file ../../references/prompts/proofreader-confucian.md \
  --terms ../../references/lexicons/confucian.txt \
  --api-base https://api.deepseek.com/v1 \
  --model deepseek-chat \
  --key $DEEPSEEK_KEY
```

**第二次停（关键）**：用 Excel/VSCode 打开 `校对建议.tsv`，人工审：
- 重点看「改动=是 且 置信度≥0.9」的行
- 不确定的把置信度改低（apply 会跳过）
- 发现改错的人工修正建议句

确认后合入：

```bash
python3 ../../scripts/proofread_llm.py apply 句级-清理.srt 校对建议.tsv 句级-校对.srt \
  --min-conf 0.9
```

### ⑥ 沉淀回写

```bash
# 默认只读，只看清单，不改词表
python3 ../../scripts/consolidate_lexicon.py 校对建议.tsv \
  ../../references/lexicons/confucian.txt
```

输出示例：

```
  1. 慎渎 => 慎独   (×4, 平均置信 0.93)
  2. 浩浩 => 皓皓   (×2, 平均置信 0.91)
```

人工确认「慎渎 → 慎独」要写进词表（高频且确定），「浩浩 → 皓皓」不写（可能只是泛指，不该一刀切）。手动删掉第 2 行后真写：

```bash
# 手动编辑 校对建议.tsv 把第 2 条删掉，再显式加 --write 真写：
python3 ../../scripts/consolidate_lexicon.py 校对建议.tsv \
  ../../references/lexicons/confucian.txt --write
```

下次转写同领域内容时「慎渎」会被自动替换成「慎独」——这就是**越用越准**。

### ⑦ 选断句模式

目标平台是视频号 → 选 `clause` 半句模式（节奏明快，适合 2–3 分钟知识短视频）。

### ⑧ 生成字幕 + 切片

```bash
python3 ../../scripts/build_subtitles.py 字级.srt 句级-校对.srt 精确字幕.srt \
  --mode clause --fps 30
```

输出统计：
- 共 487 条字幕
- 时长中位 2.6 秒
- 字数中位 11 字

自动提议切点（切点只落在字幕间隙，30 秒–5 分钟），**人工复核**后再切片：

```bash
python3 ../../scripts/propose_cuts.py 精确字幕.srt 切点表.md --min-secs 30 --max-secs 300
# ★ 必停：逐行复核起止是否语义完整（可先看字幕健康图，避开低覆盖区）
python3 ../../scripts/health_map.py 精确字幕.srt 字幕健康图.svg
python3 ../../scripts/make_table.py 切点表.md 精确字幕.srt 切点表-全文.md   # 每段配全文
```

复核后的切点表（`generate_slices.py` 按此表切片，字幕自动时间归零）：

```
| # | 起 | 止 | 内容 |
|---|----|----|------|
| 1 | 00:03:12 | 00:05:48 | 人禽之辨的当代意义 |
| 2 | 00:12:30 | 00:14:55 | 恻隐之心与四端 |
| 3 | 00:34:18 | 00:37:42 | 慎独工夫的入手处 |
```

```bash
# 批量切片（重编码，切点精确到帧）+ 每段字幕
python3 ../../scripts/generate_slices.py 切点表.md 孟子答疑课-20260315.mp4 精确字幕.srt 切片/
# 核验：时长、切点是否落在字幕间隙、片内字幕首末覆盖
python3 ../../scripts/verify_slices.py 切点表.md 精确字幕.srt 切片/
# 需要剪映草稿时（已装 capcut-cli）
python3 ../../scripts/generate_drafts.py 切点表.md 孟子答疑课-20260315.mp4 精确字幕.srt 切片/
```

产出结构：`切片/01-人禽之辨/01-人禽之辨.mp4` + 同名 `.srt`；加 `--burn` 额外生成烧字幕版本。

## 踩过的坑（都在 pitfalls.md 有详细解释）

1. **不要用句级 SRT 切片**——时间戳漂移，切出来语句被腰斩
2. **不要跳过人工审 TSV**——LLM 会把「恻然」改成「测然」之类的乌龙
3. **不要自动回写词表**——本轮「浩浩→皓皓」就是不该回写的反例
4. **不要混用断句模式**——同一视频一会儿 sentence 一会儿 clause 观众会乱

## 文件清单

这个目录按操作顺序会产生：

```
孟子答疑课-20260315.mp4     # 源视频（你自己准备）
字级.srt                     # Step ④ 产出
句级.srt                     # Step ④ 产出
句级-术语.srt                # Step ④ 产出
术语替换报告.md              # Step ④ 产出
句级-清理.srt                # Step ④ 产出
校对建议.tsv                 # Step ⑤ 产出 ★人工审
句级-校对.srt                # Step ⑤ 产出
精确字幕.srt                 # Step ⑧ 产出
切点表.md                    # Step ⑧ 产出 ★人工审
切片01-人禽之辨.mp4          # 最终交付
切片02-四端.mp4
切片03-慎独.mp4
```

## 内置样例（不需要视频就能跑）

`sample/` 下是给 `./selftest.sh` 用的最小数据集，也可以拿来对照格式：

| 文件 | 用途 |
|---|---|
| `字级-样例.srt` | 22 条字级 cue，含口水词与「人禽之变」错字 |
| `字级-长句.srt` | 30 字带逗号长句，验证 sentence 模式不在逗号处腰斩 |
| `句级-长句.srt` | 长句对应的校对稿输入 |
| `术语替换表-样例.txt` | 一条替换规则 |
| `校对建议-可合入.tsv` / `校对建议-对不上.tsv` | 验证 apply 的双键校验（后者故意改坏原句） |

```bash
cd ../.. && ./selftest.sh    # 30 项断言，全过说明链路可用
```
