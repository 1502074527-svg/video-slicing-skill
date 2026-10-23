#!/usr/bin/env python3
"""给切点表配全文：每段的起止、时长、字数、首句 + 完整讲稿，便于人工复核语义是否完整。

用法:
  python3 make_table.py <切点表.md> <字幕.srt> <带稿切点表.md> [--csv 表格.csv] [--force]

输入切点表由 propose_cuts.py 生成（或人工手写同格式：| # | 起 | 止 | 时长 | 首句 |）。
输出在表格前保留原表概览，表格后逐段附全文。
"""
import csv
import sys
from pathlib import Path

from safe_out import guard_output
from srtlib import fmt_hms, fmt_dur, load_cut_table, parse_srt, plain


def seg_text(cues, a, b):
    picked = [c for c in cues if a - 0.05 <= (c['start'] + c['end']) / 2 <= b + 0.05]
    return ' '.join(c['text'].replace('\n', ' ') for c in picked).strip()


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    table, srt, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    args = sys.argv[4:]
    csv_path = Path(args[args.index('--csv') + 1]) if '--csv' in args else None
    guard_output(out)
    if csv_path:
        guard_output(csv_path)

    rows = load_cut_table(table)
    cues = parse_srt(srt)
    if not rows:
        sys.exit(f"✗ {table} 里没读到切点行（格式应为 | # | 起 | 止 | 时长 | 首句 |）")

    brief, blocks, recs = [], [], []
    for r in rows:
        text = seg_text(cues, r['start'], r['end'])
        dur = r['end'] - r['start']
        title = r['title'] or plain(text)[:20]
        brief.append(f"| {r['num']} | {fmt_hms(r['start'])} | {fmt_hms(r['end'])} | "
                     f"{fmt_dur(dur)} | {len(plain(text))} | {title[:20]} |")
        blocks.append(
            f"## {r['num']}. {title[:40]}\n\n"
            f"`{fmt_hms(r['start'])} – {fmt_hms(r['end'])}` ｜ 时长 {fmt_dur(dur)} ｜ {len(plain(text))} 字\n\n"
            f"> {text or '（该区间内没有字幕，请检查切点）'}\n")
        recs.append([r['num'], fmt_hms(r['start']), fmt_hms(r['end']),
                     f"{dur:.1f}", len(plain(text)), title, text])

    body = "\n".join([
        "# 切点表（带稿）",
        "",
        f"> {len(rows)} 段。复核重点：每段首句是否从完整句开始、末句是否说完、段落之间是否重复或遗漏。",
        "",
        "| # | 起 | 止 | 时长 | 字数 | 标题 |",
        "|---|---|---|---|---|---|",
        *brief,
        "",
        "---",
        "",
        "\n".join(blocks),
    ])
    out.write_text(body, encoding='utf-8')
    print(f"带稿切点表 -> {out}（{len(rows)} 段）")

    if csv_path:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['#', '起', '止', '时长s', '字数', '标题', '正文'])
            w.writerows(recs)
        print(f"CSV -> {csv_path}")


if __name__ == '__main__':
    main()
