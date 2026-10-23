# video-slicing-skill

> 把 1.5–2 小时的课程/讲座录播，切成可直接发布的知识点短视频，**字幕逐字对齐不腰斩**，术语准确率越用越高。

**English**: An Agent skill that turns long lecture/course recordings into ready-to-publish short clips with frame-accurate, semantically-coherent subtitles. Built around three hard rules — word-level timestamps as the only source of truth for time, human review as the only source of truth for text, and a three-layer safety net for domain terminology. Ships with three ASR options, three cinematic subtitle-segmentation modes, and a "sediment" loop that makes the lexicon smarter every run.

---

## 为什么做这个

市面上的「AI 切片」工具大多直接给你成品视频，但课程/讲座场景有三个特殊要求它们都满足不了：

1. **字幕不能腰斩语义**——讲者一句话没说完就被切到下一屏，观众根本跟不上。
2. **术语不能错**——"人禽之辨" 识别成 "人禽之变"，学术内容立刻变笑话。
3. **校对权必须在人手里**——LLM 直接改字幕等于篡改讲者原话。

这套 Skill 把整条流水线拆成 **7 个可人工插手的步骤**，每一步的输入输出都是可读文本，LLM 只提建议、永不落笔。

## 核心特性

- **3 种 ASR 方案**：剪映 ASR（免费+字级时间戳）/ Whisper.cpp + 领域 Prompt（本地+自带标点）/ 火山方舟豆包语音（商业+热词注入），按场景选
- **3 种电影级字幕断句**：整句模式 / 半句模式 / 碎句模式，匹配不同平台节奏
- **领域化词表与 Prompt**：儒学/医学/法律/编程……每个领域一套，自带儒学完整示例
- **沉淀积累闭环**：每次人工校对确认的新术语自动回写词表，**越用越准**
- **引导式交互**：Agent 在 7 个关键决策点必须停下来问用户，不自作主张
- **纯文本中间产物**：SRT/TSV/词表全是可读文本，随时人工插手

## 30 秒快速开始

```bash
# 1. 克隆本仓库
git clone https://github.com/1502074527-svg/video-slicing-skill.git
cd video-slicing-skill

# 2. 让你的 Agent 加载 SKILL.md（Claude Code / Trae / Codex 均可）
#    直接把 SKILL.md 路径告诉 Agent，或放进 ~/.claude/skills/ 等约定位置

# 3. 对 Agent 说：「帮我把这段讲座切成短视频」
#    Agent 会按 SKILL.md 指引，在关键节点逐个向你确认方案
```

**前置依赖**（按需安装，见 [references/asr-engines.md](references/asr-engines.md)）：

| 依赖 | 用途 | 必需 |
|---|---|---|
| Python 3.9+ | 全部脚本 | ✅ |
| ffmpeg / ffprobe | 切片、探时长 | ✅ |
| VideoCaptioner | 方案 A：剪映 ASR 转写主力 | 推荐 |
| whisper.cpp | 方案 B：本地 Whisper 对照 | 可选 |
| 火山方舟账号 | 方案 C：商业 ASR + 热词 | 可选 |

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
| 端到端操作手册 | [references/sop.md](references/sop.md) |
| 选 ASR 方案 | [references/asr-engines.md](references/asr-engines.md) |
| 选字幕断句模式 | [references/subtitle-segmentation.md](references/subtitle-segmentation.md) |
| 定制自己领域的词表/Prompt | [references/domain-customization.md](references/domain-customization.md) |
| Agent 引导用户的话术集 | [references/elicitation.md](references/elicitation.md) |
| 已踩过的坑 | [references/pitfalls.md](references/pitfalls.md) |
| 儒学课程完整示例 | [examples/confucian-course/](examples/confucian-course/) |

## Roadmap

- **v0.1（当前）**：核心流水线 + 3 ASR 方案 + 3 断句模式 + 领域化词表 + 沉淀积累闭环
- **v0.2（规划中）**：拼音约束术语归一（同音错形自动拉齐）、字幕健康图（识别低覆盖区）、剪映草稿一键生成、切片核验（音频包络对齐）

## License

MIT — 随便用，改了不用告诉我，出问题了也别怪我。
