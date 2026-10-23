# video-slicing-skill

> 把 1.5–2 小时的课程/讲座录播，切成可直接发布的知识点短视频，**字幕逐字对齐不腰斩**，术语准确率越用越高。

**English**: An Agent skill that turns long lecture/course recordings into ready-to-publish short clips with frame-accurate, semantically-coherent subtitles. Built around three hard rules — word-level timestamps as the only source of truth for time, human review as the only source of truth for text, and a three-layer safety net for domain terminology. Ships with three ASR options, three cinematic subtitle-segmentation modes, and a "sediment" loop that makes the lexicon smarter every run.

---

## 为什么做这个

市面上的「AI 切片」工具大多直接给你成品视频，但课程/讲座场景有三个特殊要求它们都满足不了：

1. **字幕不能腰斩语义**——讲者一句话没说完就被切到下一屏，观众根本跟不上。
2. **术语不能错**——"人禽之辨" 识别成 "人禽之变"，学术内容立刻变笑话。
3. **校对权必须在人手里**——LLM 直接改字幕等于篡改讲者原话。

这套 Skill 把整条流水线拆成 **8 个步骤（其中 7 个必停点）**，每一步的输入输出都是可读文本，LLM 只提建议、永不落笔。

## 核心特性

- **3 种 ASR 方案**：剪映 ASR（免费+字级时间戳）/ Whisper.cpp + 领域 Prompt（本地+自带标点）/ 火山方舟豆包语音（商业+热词注入），按场景选
- **3 种电影级字幕断句**：整句模式 / 半句模式 / 碎句模式，匹配不同平台节奏
- **领域化词表与 Prompt**：儒学/医学/法律/编程……每个领域一套，自带儒学完整示例
- **沉淀积累闭环**：每次人工校对确认的新术语回写词表，**越用越准**
- **引导式交互**：Agent 在 7 个必停节点必须停下来问用户，不自作主张
- **开箱自检**：`./selftest.sh` 用内置样例跑通全链路，13 项断言，不需要视频和 API Key
- **纯文本中间产物**：SRT/TSV/词表全是可读文本，随时人工插手

## 5 分钟快速开始

### 1. 克隆并自检（不需要视频、不需要联网、不需要 API Key）

```bash
git clone https://github.com/1502074527-svg/video-slicing-skill.git
cd video-slicing-skill
./selftest.sh
```

看到「13 通过 / 0 失败」说明脚本链路可用。自检用的是内置样例
（`examples/confucian-course/sample/`），会顺便验证「哈佛不被误删」
「词表默认不被改写」这两条守卫。

### 2. 装基础依赖

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows（PowerShell）
winget install Gyan.FFmpeg
```

Python 需 ≥ 3.9。**6 个脚本只用标准库，无需 pip install、无需 requirements.txt。**

方案 A（剪映 ASR）还需装 VideoCaptioner，方案 B 需 whisper.cpp，方案 C 只需火山方舟账号——
安装步骤见 [references/asr-engines.md](references/asr-engines.md)。

### 3. 让 Agent 加载 SKILL.md

```bash
# Claude Code
mkdir -p ~/.claude/skills && ln -s "$PWD" ~/.claude/skills/video-slicing-skill

# Trae / Codex 等其他 Agent：直接把本仓库 SKILL.md 的绝对路径告诉它即可
```

### 4. 对 Agent 说

> 「帮我把这段讲座切成短视频」

Agent 会按 SKILL.md 指引，在 7 个必停节点逐个向你确认方案。

## 工作原理

```
源视频（1.5-2 小时录播）
   │
   ① 转写：3 选 1，产字级 SRT（时间轴金标准）
   ② 文字稿：字级 → 句级 → 术语表确定性替换
   ③ 校对：LLM 提建议（TSV）→ 人工审 → 高置信才合入
   ④ 沉淀：确认的新术语自动回写词表 ★ 越用越准
   ⑤ 字幕：按选定断句模式对齐字级时间戳，一句一条
   ⑥ 切点：AI 提议 + 人工确认
   ⑦ 成稿：每条切片一个视频文件 + 字幕
```

三条铁律（不可破）：

1. **时间轴只信字级时间戳**——任何替换/清理都不动时间戳，只改文本
2. **文本只信人工校对**——LLM 永远只提建议不落笔
3. **任何自动替换都可追溯、可回滚**——每次改动有记录，出问题能退

## 领域化定制

这套 Skill 的领域无关骨架 + 领域特定内容分离：

- **通用骨架**（`scripts/` + `references/sop.md`）：适用于任何讲座/课程
- **领域词表**（`references/lexicons/`）：每个领域一份，含儒学完整示例 + 空白模板
- **领域校对 Prompt**（`references/prompts/`）：每个领域一份，含儒学完整示例 + 通用模板

定制自己领域的方法：[references/domain-customization.md](references/domain-customization.md)

## 文档地图

| 你想做什么 | 去哪看 |
|---|---|
| Agent 加载入口 | [SKILL.md](SKILL.md) |
| 跑自检 / 看样例数据 | [selftest.sh](selftest.sh)、[examples/confucian-course/sample/](examples/confucian-course/sample/) |
| 场景边界与适配规范 | [references/scope-and-adaptation.md](references/scope-and-adaptation.md) |
| 端到端操作手册 | [references/sop.md](references/sop.md) |
| 选 ASR 方案 | [references/asr-engines.md](references/asr-engines.md) |
| 选字幕断句模式 | [references/subtitle-segmentation.md](references/subtitle-segmentation.md) |
| 定制自己领域的词表/Prompt | [references/domain-customization.md](references/domain-customization.md) |
| Agent 引导用户的话术集 | [references/elicitation.md](references/elicitation.md) |
| 已踩过的坑 | [references/pitfalls.md](references/pitfalls.md) |
| 儒学课程完整示例 | [examples/confucian-course/](examples/confucian-course/) |

## Roadmap

### v0.1（当前）

核心流水线 + 3 ASR 方案 + 3 断句模式 + 领域化词表 + 沉淀积累闭环。

### v0.2（即将发布）

以下四项正在收尾，上线后同步进本仓库：

- **拼音约束术语归一**（`term_normalize.py`）
  同音错形按拼音约束自动拉齐——「之辨 / 之变」「恻然 / 侧然」这类不用再逐条人工补进词表，词表规模能收窄一半。
- **字幕健康图**（`health_map.py`）
  把全片字幕覆盖度画成时间轴热图，低覆盖区一眼可见。这类区域通常是长静音、答疑插话或串场，选片时直接避开。
- **剪映草稿一键生成**（`generate_drafts.py`）
  精确字幕直接写成剪映草稿工程，省掉「导入 SRT → 手动对轨 → 调样式」的重复劳动。
- **切片核验**（`verify_slices.py`）
  用音频包络对齐源视频与切片，自动核对切点有没有偏移、语句有没有被截断。

### v0.3（计划）

以下四项与 v0.2 合计，覆盖原工具包尚未开源的 8 项能力：

- **切点自动提议**（`propose_cuts.py`）
  按语义完整度与时长窗口（30 秒–5 分钟）自动挑候选切片，人只需在结果上增删改，不用从零拉时间轴。
- **带稿切点表**（`make_table.py` / `make_transcript.py`）
  每条切片附上该段完整文字稿，选片时不用来回拖进度条；同时产出可读文字稿，供校对与选段共用。
- **剪映字幕样式修正**（`fix_text_style.py`）
  批量改字号、垂直位置、阴影，并同步 `draft_content.json` 与 `draft_info.json` 两个镜像，避免只改一边导致样式回弹。
- **工程化脚本**（`run_text_pipeline.sh` / `check_env.sh` / `selftest.sh`）
  一条命令串跑文字处理链、开工前环境自检、以及脚本改动后的回归自检。

## License

MIT — 随便用，改了不用告诉我，出问题了也别怪我。
