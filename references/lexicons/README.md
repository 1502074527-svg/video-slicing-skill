# 词表目录

每个领域一个词表文件，命名 `<领域>.txt`。

## 现有词表

| 文件 | 领域 | 条数 | 状态 |
|---|---|---|---|
| [confucian.txt](confucian.txt) | 儒学（四书五经） | ~94 条 | 实战检验 |
| [_template.txt](_template.txt) | 空白模板 | 0 | 复制改 |

## 词表格式

```
# 注释
误写 => 正写       # 术语替换（确定性，零风险）
正词              # 热词（供 ASR / LLM 参考，不直接替换）
```

## 怎么写自己领域的词表

见 [../domain-customization.md](../domain-customization.md)。

三种起草方法：
1. 从 PPT/讲义让 LLM 提取
2. 从初版转写稿反向归纳
3. 参考 confucian.txt 当模板

## 沉淀机制

每次人工审查确认的新术语对，用 `scripts/consolidate_lexicon.py` 回写到词表：

```bash
# 看建议（dry-run）
python3 ../../scripts/consolidate_lexicon.py 校对建议.tsv <你的领域>.txt --dry-run

# 确认后真写
python3 ../../scripts/consolidate_lexicon.py 校对建议.tsv <你的领域>.txt
```

**越用越准**：第 1 轮词表 20 条，第 3 轮 60 条，第 5 轮后 ASR 几乎不出术语错。
