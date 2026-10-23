#!/usr/bin/env python3
"""拼音约束的术语归一：找出「读音相同但字形写错」的术语候选。

为什么需要：ASR 的错法高度集中在同音字（「人禽之辨」写成「人禽之变」）。
只靠词表逐条替换，必须事先想到每一种错法；用拼音做约束，可以主动发现
「词表里没列过、但读音对得上某个已知术语」的错写。

两段式（与 proofread_llm 同样的「机器只提议、人拍板」原则）：
  1) scan  ：扫描字幕，输出候选 TSV（采纳列默认=否）
  2) apply ：人工把要用的行改成「是」后，按 TSV 应用

依赖：需要 pypinyin（可选依赖，不装则脚本给出安装提示后退出）。
  pip install pypinyin

用法:
  python3 term_normalize.py scan <字幕.srt> <词表.txt> [--out 归一建议.tsv] [--min-len 2]
  python3 term_normalize.py apply <字幕.srt> <归一建议.tsv> <输出.srt>

词表格式：误写=>正写（# 开头为注释）；只用「正写」一侧的术语做约束。
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from safe_out import guard_output
from srtlib import parse_srt, write_srt


def load_terms(lexicon):
    terms = set()
    for ln in Path(lexicon).read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        good = ln.split('=>', 1)[1].strip() if '=>' in ln else ln
        good = re.sub(r'[\s，。、]', '', good)
        if len(good) >= 2:
            terms.add(good)
    return terms


def pinyin_seq(chars, Pinyin):
    return tuple(Pinyin(char)[0] for char in chars)


def cmd_scan(a):
    src, lexicon = Path(a[0]), Path(a[1])
    args = list(a[2:])
    out = Path(args[args.index('--out') + 1]) if '--out' in args else Path('归一建议.tsv')
    min_len = int(args[args.index('--min-len') + 1]) if '--min-len' in args else 2

    try:
        from pypinyin import lazy_pinyin as Pinyin
    except ImportError:
        sys.exit("✗ 需要 pypinyin：pip install pypinyin\n"
                 "  （若不愿装依赖，跳过本步，用词表替换 + LLM 校对已能覆盖大部分错法）")

    terms = {t for t in load_terms(lexicon) if len(t) >= min_len}
    by_py = defaultdict(set)
    for t in terms:
        by_py[pinyin_seq(t, Pinyin)].add(t)

    cues = parse_srt(src)
    hits = Counter()
    samples = {}
    for c in cues:
        text = re.sub(r'[\s，。、！？；：]', '', c['text'])
        for n in range(min_len, 5):
            for i in range(len(text) - n + 1):
                w = text[i:i + n]
                if w in terms:
                    continue
                cand = by_py.get(pinyin_seq(w, Pinyin))
                if not cand:
                    continue
                for good in cand:
                    if good == w:
                        continue
                    hits[(w, good)] += 1
                    samples.setdefault((w, good), c['text'][:40])

    guard_output(out)
    rows = sorted(hits.items(), key=lambda kv: -kv[1])
    with open(out, 'w', encoding='utf-8') as f:
        f.write("误写\t正写\t次数\t拼音\t采纳\t样例\n")
        for (bad, good), cnt in rows:
            f.write(f"{bad}\t{good}\t{cnt}\t{' '.join(Pinyin(bad))}\t否\t{samples[(bad, good)]}\n")
    print(f"候选 {len(rows)} 条 -> {out}")
    if rows:
        print("⚠️ 拼音只是约束不是证据：同音不同义很常见（如「期/其」）。")
        print("   请逐条核对，确认的把「采纳」改成「是」，再跑 apply。")
    else:
        print("没有发现同音候选（词表可能已覆盖，或字幕本身没有这类错法）。")


def cmd_apply(a):
    src, tsv, out = Path(a[0]), Path(a[1]), Path(a[2])
    guard_output(out, src)
    rules = []
    with open(tsv, encoding='utf-8') as f:
        next(f, None)
        for ln in f:
            p = ln.rstrip('\n').split('\t')
            if len(p) >= 5 and p[4].strip() == '是' and p[0].strip():
                rules.append((p[0].strip(), p[1].strip()))
    if not rules:
        sys.exit("✗ TSV 里没有「采纳=是」的行，未做任何修改")
    rules.sort(key=lambda r: -len(r[0]))
    cues = parse_srt(src)
    n = 0
    for c in cues:
        t = c['text']
        for bad, good in rules:
            if bad in t:
                t = t.replace(bad, good)
                n += 1
        c['text'] = t
    write_srt(cues, out)
    print(f"按 {len(rules)} 条采纳规则替换 {n} 处 -> {out}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == 'scan' and len(rest) >= 2:
        cmd_scan(rest)
    elif cmd == 'apply' and len(rest) >= 3:
        cmd_apply(rest)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
