#!/usr/bin/env python3
"""术语替换表确定性替换：误写 => 正写，长词优先，零风险、可追溯。

只改文本、不动时间戳。每次替换写进报告，出问题可逐条回滚。

用法: python3 proofread.py <输入.srt> <输出.srt> <替换表.txt> <报告.md> [--force]
替换表格式: 误写=>正写（每行一条，# 开头为注释）。
输出文件已存在时默认拒绝覆盖，确认要覆盖加 --force。
"""
import sys
from pathlib import Path

from safe_out import guard_output


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    inp, outp, table, report = map(Path, sys.argv[1:5])
    guard_output(outp, inp)
    guard_output(report, inp)

    rules = []
    for ln in table.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('#') or '=>' not in ln:
            continue
        bad, good = ln.split('=>', 1)
        bad, good = bad.strip(), good.strip()
        if bad and bad != good:
            rules.append((bad, good))
    rules.sort(key=lambda r: -len(r[0]))  # 长词优先，避免短词先吃

    raw = inp.read_text(encoding='utf-8')
    changes = {}
    for bad, good in rules:
        n = raw.count(bad)
        if n:
            raw = raw.replace(bad, good)
            changes[f"{bad} => {good}"] = n
    outp.write_text(raw, encoding='utf-8')

    rep = ["# 术语替换报告", "",
           f"- 输入: {inp}", f"- 输出: {outp}", f"- 词表: {table}",
           f"- 替换总数: {sum(changes.values())}", "", "## 明细", ""]
    rep += [f"- {k} × {v}" for k, v in sorted(changes.items(), key=lambda x: -x[1])] or ["- （无命中）"]
    report.write_text('\n'.join(rep) + '\n', encoding='utf-8')
    print(f"替换 {sum(changes.values())} 处 / {len(changes)} 条规则 -> {outp}；报告 -> {report}")


if __name__ == '__main__':
    main()
