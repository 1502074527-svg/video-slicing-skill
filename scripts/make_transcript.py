#!/usr/bin/env python3
"""字幕 → 可读文字稿（S1 口播交付物，也可作为 S3 选段依据）。

按停顿自动分段：相邻字幕间隔 ≥ --para-gap（默认 2.0s）另起一段。
每段带一个 [起始时间] 标记，方便回查原片。

用法:
  python3 make_transcript.py <字幕.srt> <文字稿.md> [--para-gap 2.0] [--no-time] [--force]
"""
import sys
from pathlib import Path

from safe_out import guard_output
from srtlib import fmt_hms, parse_srt


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    srt, out = Path(sys.argv[1]), Path(sys.argv[2])
    args = sys.argv[3:]
    gap = float(args[args.index('--para-gap') + 1]) if '--para-gap' in args else 2.0
    with_time = '--no-time' not in args
    guard_output(out)

    cues = parse_srt(srt)
    paras, cur, last_end, t0 = [], [], None, None
    for c in cues:
        if last_end is not None and c['start'] - last_end >= gap:
            paras.append((t0, cur))
            cur, t0 = [], None
        if t0 is None:
            t0 = c['start']
        cur.append(c['text'].replace('\n', ' ').strip())
        last_end = c['end']
    if cur:
        paras.append((t0, cur))

    lines = [f"# 文字稿：{srt.stem}", "", f"> 共 {len(paras)} 段、{len(cues)} 条字幕。时间戳为段首，便于回查原片。", ""]
    for t, parts in paras:
        head = f"**[{fmt_hms(t)}]** " if with_time else ''
        lines.append(f"{head}{''.join(parts)}")
        lines.append("")
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f"文字稿 -> {out}（{len(paras)} 段 / {len(cues)} 条）")


if __name__ == '__main__':
    main()
