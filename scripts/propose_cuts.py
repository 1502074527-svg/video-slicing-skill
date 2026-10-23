#!/usr/bin/env python3
"""从字幕自动提议切片切点（S3 高光剪辑第一步）。

判定依据是**字幕条的时间间隙**，不是字数——ASR 文本标点常缺，停顿才可靠：
 - 好的切点：落在前一条字幕结束与后一条开始的间隙里（默认 ≥0.8s），
   且前一条字幕不是以「然后/所以/就是…」这类连接词收尾（意思没说完）
 - 每段 ≥ --min-secs（默认 30s），≤ --max-secs（默认 300s）
 - 切点永远取间隙内的秒数，不落在任何一条字幕内部，保证语句不被腰斩

用法:
  python3 propose_cuts.py <字幕.srt> <切点表.md> [--min-secs 30] [--max-secs 300] [--pause 0.8] [--force]

产出：markdown 切点表（| # | 起 | 止 | 时长 | 首句 |），可直接交 generate_slices.py。
⚠️ 自动提议只做初筛，必须人工复核每一行的起止是否语义完整。
"""
import sys
from pathlib import Path

from safe_out import guard_output
from srtlib import fmt_hms, fmt_dur, parse_srt, plain

# 句尾挂着这些词 → 意思没说完，不能在这里切
TAIL = ('就是说', '那么', '然后', '所以', '但是', '就是', '这个', '那个', '的话',
        '因为', '如果', '好像', '等于', '比方', '还有', '以及', '接着', '然后呢',
        '那', '而', '像', '跟', '和', '或者')


def tail_hanging(text):
    t = plain(text)
    for w in sorted(TAIL, key=len, reverse=True):
        if t.endswith(w):
            return w
    return None


def natural_boundaries(cues, pause):
    """返回可用切点的 cue 下标（该下标处开始新的一段）。"""
    out = []
    for i in range(1, len(cues)):
        gap = cues[i]['start'] - cues[i - 1]['end']
        if gap >= pause and not tail_hanging(cues[i - 1]['text']):
            out.append(i)
    return out


def propose(cues, min_s, max_s, pause):
    bs = set(natural_boundaries(cues, pause))
    n = len(cues)
    segs, s = [], 0
    while s < n - 1:
        limit = cues[s]['start'] + max_s
        reach = [i for i in range(s + 1, n) if cues[i]['start'] <= limit]
        if not reach:
            break
        ok = [i for i in reach if i in bs and cues[i]['start'] - cues[s]['start'] >= min_s]
        if ok:
            b = ok[-1]
        else:
            any_b = [i for i in reach if i in bs]
            b = any_b[-1] if any_b else reach[-1]
        segs.append((s, b))
        s = b
    if s < n:
        segs.append((s, n))
    return segs


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    srt, out = Path(sys.argv[1]), Path(sys.argv[2])
    args = sys.argv[3:]
    get = lambda k, d: (args[args.index(k) + 1] if k in args else d)
    min_s, max_s, pause = float(get('--min-secs', 30)), float(get('--max-secs', 300)), float(get('--pause', 0.8))
    guard_output(out)
    cues = parse_srt(srt)
    if not cues:
        sys.exit(f"✗ {srt} 里没有可解析的字幕条")

    segs = propose(cues, min_s, max_s, pause)
    rows, short = [], 0
    for k, (a, b) in enumerate(segs, 1):
        st, en = cues[a]['start'], cues[b - 1]['end']
        dur = en - st
        if dur < min_s:
            short += 1
        rows.append(f"| {k} | {fmt_hms(st)} | {fmt_hms(en)} | {fmt_dur(dur)} | {plain(cues[a]['text'])[:20]} |")

    body = "\n".join([
        "# 切点表（自动提议）",
        "",
        f"> 共 {len(rows)} 段；每段 {min_s:g}s–{max_s:g}s；切点均落在相邻字幕条间隙，未切开任何一条字幕。",
        "> ⚠️ 这是初筛结果，**必须人工复核**每段起止是否语义完整、是否值得单独发布。",
        "",
        "| # | 起 | 止 | 时长 | 首句 |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ])
    out.write_text(body, encoding='utf-8')
    print(f"提议 {len(rows)} 段 -> {out}")
    if short:
        print(f"提示：有 {short} 段短于 {min_s:g}s（通常是片尾残余），可人工删除或与上一段合并。")
    print("下一步：人工复核切点表 → generate_slices.py 批量切片 → verify_slices.py 核验")


if __name__ == '__main__':
    main()
