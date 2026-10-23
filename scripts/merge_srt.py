#!/usr/bin/env python3
"""把字级 SRT 按静音间隔合并成句级 SRT（便于阅读与后续 LLM 校对）。

字级 SRT 是时间轴金标准，但一句一条几百条没法校对。
本脚本只做「视图合并」：按标点或静音断句，不动任何字的时间戳。

用法: python3 merge_srt.py <字级.srt> <句级.srt> [--gap 1.2] [--force]
（输出文件已存在时默认拒绝覆盖，确认要覆盖加 --force）
"""
import re
import sys
from pathlib import Path

from safe_out import guard_output

SENT_END = re.compile(r'[。！？；…!?;]+$')


def parse_ts(s):
    m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', s)
    g = [int(x) for x in m.groups()]
    return g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000


def fmt_ts(t):
    ms = max(0, int(round(t * 1000)))
    return f"{ms//3600000:02d}:{ms%3600000//60000:02d}:{ms%60000//1000:02d},{ms%1000:03d}"


def parse_srt(path):
    raw = Path(path).read_text(encoding='utf-8')
    out = []
    for b in re.split(r'\n\s*\n', raw.strip()):
        L = b.strip().split('\n')
        if len(L) < 3:
            continue
        m = re.match(r'([\d:,.]+) --> ([\d:,.]+)', L[1])
        if not m:
            continue
        out.append((parse_ts(m.group(1)), parse_ts(m.group(2)), ''.join(L[2:]).strip()))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    guard_output(dst, src)
    gap = float(sys.argv[sys.argv.index('--gap') + 1]) if '--gap' in sys.argv else 1.2

    words = parse_srt(src)
    if not words:
        print(f"✗ 输入无有效字幕块: {src}")
        sys.exit(2)

    sents, cur_text, cur_start, cur_end = [], '', None, None
    for i, (s, e, w) in enumerate(words):
        if cur_start is None:
            cur_start = s
        cur_text += w
        cur_end = e
        nxt_gap = words[i + 1][0] - e if i + 1 < len(words) else 99
        if SENT_END.search(w) or nxt_gap >= gap:
            sents.append((cur_start, cur_end, cur_text))
            cur_text, cur_start, cur_end = '', None, None
    if cur_text:
        sents.append((cur_start, cur_end, cur_text))

    Path(dst).write_text('\n'.join(
        f"{i}\n{fmt_ts(s)} --> {fmt_ts(e)}\n{t}\n" for i, (s, e, t) in enumerate(sents, 1)),
        encoding='utf-8')
    print(f"字级条数={len(words)} → 句级条数={len(sents)} -> {dst}")


if __name__ == '__main__':
    main()
