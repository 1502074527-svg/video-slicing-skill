#!/usr/bin/env python3
"""沉淀回写：把本轮人工确认的校对建议，回写进术语替换表 —— 越用越准。

工作方式：
 1. 读校对建议 TSV，挑出「改动=是 且 置信度≥阈值 且 未命中现有词表」的行。
 2. 从「原句 → 建议句」中 diff 出术语对（跨度 ≤ 2 字，避免整句替换混进词表）。
 3. 聚合统计每对出现次数与平均置信度。
 4. 默认只读（dry-run）打印清单；人工确认后加 --write 才追加写进词表文件。

用法:
  # 默认就是 dry-run，只打印清单，不写任何文件
  python3 consolidate_lexicon.py <校对建议.tsv> <术语替换表.txt>

  # 人工逐条确认后，显式加 --write 才真写
  python3 consolidate_lexicon.py <校对建议.tsv> <术语替换表.txt> --write

安全闸：
  - 默认只读，不加 --write 永不落盘（防止 Agent 自作主张改词表）
  - 默认只收 2 字及以上的术语对（--min-span 可调），防止单字替换过度泛化
  - 自动跳过现有规则的子串（如已有「人禽之变→人禽之辨」，不再收「变→辨」）
"""
import difflib
import sys
from collections import defaultdict
from pathlib import Path


def safe_conf(s):
    """置信度容错：手改 TSV 写成「高」「0.9左右」时不崩，按 0 处理（自动跳过）。"""
    try:
        return float(str(s).strip())
    except ValueError:
        return 0.0


def diff_pairs(old, new, max_span=2):
    """从 原句→建议句 diff 出短术语对（只收 ≤max_span 字的替换，防止整句被当术语）。"""
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            bad, good = old[i1:i2], new[j1:j2]
            if 0 < len(bad) <= max_span and 0 < len(good) <= max_span and bad != good:
                pairs.append((bad, good))
    return pairs


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    tsv_path, lex_path = Path(sys.argv[1]), Path(sys.argv[2])
    args = sys.argv[3:]
    dry_run = '--write' not in args
    min_conf = float(args[args.index('--min-conf') + 1]) if '--min-conf' in args else 0.9
    max_span = int(args[args.index('--max-span') + 1]) if '--max-span' in args else 2
    min_span = int(args[args.index('--min-span') + 1]) if '--min-span' in args else 2

    # 现有词表（避免重复回写 + 避免回写已有规则的子串）
    existing = set()
    if lex_path.exists():
        for ln in lex_path.read_text(encoding='utf-8').splitlines():
            ln = ln.strip()
            if not ln or ln.startswith('#') or '=>' not in ln:
                continue
            bad, _ = ln.split('=>', 1)
            existing.add(bad.strip())

    # 聚合候选
    stats = defaultdict(lambda: {'n': 0, 'conf_sum': 0.0, 'examples': []})
    with open(tsv_path, encoding='utf-8') as f:
        next(f, None)  # 表头
        for ln in f:
            p = ln.rstrip('\n').split('\t')
            if len(p) < 6:
                continue
            _, old, new, ch, conf, why = p[0], p[1], p[2], p[3], safe_conf(p[4]), p[5]
            if ch != '是' or conf < min_conf:
                continue
            for bad, good in diff_pairs(old, new, max_span):
                if len(bad) < min_span:
                    continue
                # 跳过已存在规则的子串（如已有「人禽之变→人禽之辨」，就不再收「变→辨」）
                if any(bad in ex for ex in existing):
                    continue
                # 防替换链：若正写本身已是某条规则的误写（乙=>丙），
                # 新收「甲=>乙」会在下一轮被二次替换成丙，语义跑偏
                if any(good == ex for ex in existing):
                    continue
                s = stats[(bad, good)]
                s['n'] += 1
                s['conf_sum'] += conf
                if len(s['examples']) < 2:
                    s['examples'].append((old, new, why))

    if not stats:
        print("没有可回写的新术语对（全部已命中现有词表，或置信度不足）。")
        return

    # 按出现次数排序打印
    rows = sorted(stats.items(), key=lambda kv: (-kv[1]['n'], -kv[1]['conf_sum']))
    print(f"发现 {len(rows)} 个候选术语对（置信度≥{min_conf}，跨度≤{max_span}字）：\n")
    for i, ((bad, good), s) in enumerate(rows, 1):
        avg = s['conf_sum'] / s['n']
        print(f"  {i}. {bad} => {good}   (×{s['n']}, 平均置信 {avg:.2f})")
        for old, new, why in s['examples']:
            print(f"       依据: {why}")
            print(f"       原句: {old[:60]}")
            print(f"       建议: {new[:60]}")

    if dry_run:
        print("\n(dry-run，未写文件。人工逐条确认后加 --write 再跑。)")
        return

    # 真写：先备份原词表，再追加（带时间戳注释）
    import shutil
    from datetime import datetime
    stamp = datetime.now().strftime('%Y-%m-%d')
    shutil.copy(lex_path, lex_path.with_name(lex_path.name + '.bak'))
    with open(lex_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# --- 沉淀回写 {stamp} ---\n")
        for (bad, good), _ in rows:
            f.write(f"{bad} => {good}\n")
    print(f"\n✅ 已追加 {len(rows)} 条到 {lex_path}")
    print(f"   原词表备份在 {lex_path.name}.bak（下次转写同领域内容自动应用）")


if __name__ == '__main__':
    main()
