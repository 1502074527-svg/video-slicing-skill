#!/usr/bin/env python3
"""字幕健康图：把整条时间轴的字幕覆盖率画成 SVG，一眼看出「哪里空、哪里断」。

用途（S3 高光剪辑的辅助判断，不替代人工）：
 - 深色柱 = 该时间段有字幕（讲解在进行）
 - 红色块 = 长静音（≥ --gap 秒，可能是翻页/答疑/休息/卡顿）
 - 黄色底 = 低覆盖窗口（覆盖率 < --low），通常是可疑停顿区，选段应避开

⚠️ 覆盖率只说明「有没有在说话」，不说明「说得对不对」。低覆盖 ≠ 无内容，
   也可能是 PPT 演示或现场操作；高覆盖也 ≠ 值得切片。必须回听确认。

用法:
  python3 health_map.py <字幕.srt> <健康图.svg> [--bin 10] [--gap 3] [--low 0.5] [--force]
纯标准库，不依赖 matplotlib。
"""
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from safe_out import guard_output
from srtlib import fmt_hms, parse_srt

W, H = 1200, 300
ML, MR, MT, MB = 70, 30, 50, 90


def get_arg(key, default):
    args = sys.argv[3:]
    if key not in args:
        return default
    i = args.index(key) + 1
    if i >= len(args):
        sys.exit(f"✗ 参数 {key} 后面缺少取值")
    return args[i]


def analyze(cues, bin_s, gap_s, low):
    start = cues[0]['start']
    end = max(c['end'] for c in cues)
    total = max(end - start, 0.001)
    nb = max(1, int(math.ceil(total / bin_s)))
    cov = [0.0] * nb
    for c in cues:
        a, b = max(c['start'], start), min(c['end'], end)
        while a < b:
            i = int((a - start) // bin_s)
            if i >= nb:
                break
            seg_end = min(b, start + (i + 1) * bin_s)
            cov[i] += seg_end - a
            a = seg_end
    cov = [min(1.0, x / bin_s) for x in cov]

    gaps = []
    for i in range(1, len(cues)):
        g = cues[i]['start'] - cues[i - 1]['end']
        if g >= gap_s:
            gaps.append((cues[i - 1]['end'], cues[i]['start'], g))
    gaps.sort(key=lambda x: -x[2])

    lows, cur = [], None
    for i, v in enumerate(cov):
        if v < low:
            cur = [i, i, v] if cur is None else [cur[0], i, cur[2] + v]
        elif cur is not None:
            lows.append(cur)
            cur = None
    if cur is not None:
        lows.append(cur)
    lows = [(start + a * bin_s, start + (b + 1) * bin_s, s / (b - a + 1))
            for a, b, s in lows]
    lows.sort(key=lambda x: -(x[1] - x[0]))

    speech = sum(c['end'] - c['start'] for c in cues)
    return {'start': start, 'end': end, 'total': total, 'cov': cov,
            'gaps': gaps, 'lows': lows, 'speech': min(speech / total, 1.0)}


def nice_step(total):
    for s in (10, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if total / s <= 12:
            return s
    return 3600


def render(st, bin_s):
    pw, ph = W - ML - MR, H - MT - MB
    x = lambda t: ML + (t - st['start']) / st['total'] * pw
    y = lambda v: MT + ph * (1 - v)  # 覆盖率 1 在顶部
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="system-ui,-apple-system,PingFang SC,sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#11151c"/>']

    # 低覆盖窗口（黄底）
    for a, b, avg in st['lows']:
        parts.append(f'<rect x="{x(a):.1f}" y="{MT}" width="{max(1, x(b) - x(a)):.1f}" '
                     f'height="{ph}" fill="#ffcc33" opacity="0.10"/>')

    # 覆盖率柱
    bw = pw / len(st['cov'])
    for i, v in enumerate(st['cov']):
        h = max(1.0, ph * v)
        color = '#4da3ff' if v >= 0.5 else '#7a8899'
        parts.append(f'<rect x="{ML + i * bw:.1f}" y="{MT + ph - h:.1f}" '
                     f'width="{max(0.8, bw - 0.4):.1f}" height="{h:.1f}" fill="{color}" opacity="0.85"/>')

    # 长静音（红色块，贴在柱状图下的细带）
    gy = MT + ph + 10
    for a, b, g in st['gaps']:
        parts.append(f'<rect x="{x(a):.1f}" y="{gy}" width="{max(1, x(b) - x(a)):.1f}" height="12" '
                     f'fill="#ff5b5b" opacity="0.9"><title>静音 {g:.1f}s @ {fmt_hms(a)}</title></rect>')

    # 坐标轴
    parts.append(f'<line x1="{ML}" y1="{MT + ph}" x2="{W - MR}" y2="{MT + ph}" stroke="#39424e"/>')
    step = nice_step(st['total'])
    t = math.ceil(st['start'] / step) * step
    while t <= st['end']:
        px = x(t)
        parts.append(f'<line x1="{px:.1f}" y1="{MT + ph}" x2="{px:.1f}" y2="{MT + ph + 5}" stroke="#39424e"/>')
        parts.append(f'<text x="{px:.1f}" y="{MT + ph + 22}" fill="#8b97a5" font-size="12" '
                     f'text-anchor="middle">{fmt_hms(t)[:8]}</text>')
        t += step

    # 图例与标题
    parts.append(f'<text x="{ML}" y="28" fill="#e8eef5" font-size="16">字幕健康图 · '
                 f'总时长 {st["total"] / 60:.1f} 分钟 · 覆盖率 {st["speech"]:.1%}</text>')
    lg = [('#4da3ff', '有字幕'), ('#ff5b5b', '长静音'), ('#ffcc33', '低覆盖窗口')]
    lx = W - MR - 300
    for color, label in lg:
        parts.append(f'<rect x="{lx}" y="{34}" width="12" height="12" fill="{color}" opacity="0.9"/>')
        parts.append(f'<text x="{lx + 18}" y="{44}" fill="#8b97a5" font-size="12">{escape(label)}</text>')
        lx += 100
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    bin_s = float(get_arg('--bin', 10))
    gap_s = float(get_arg('--gap', 3))
    low = float(get_arg('--low', 0.5))
    guard_output(out, src)

    cues = parse_srt(src)
    if not cues:
        sys.exit(f"✗ {src} 里没有可解析的字幕条")
    st = analyze(cues, bin_s, gap_s, low)
    out.write_text(render(st, bin_s), encoding='utf-8')

    print(f"字幕条={len(cues)} 总时长={st['total'] / 60:.1f}min "
          f"有效语音={st['speech']:.1%} -> {out}")
    if st['gaps']:
        print(f"长静音（≥{gap_s:g}s）{len(st['gaps'])} 处，最长 5 处：")
        for a, b, g in st['gaps'][:5]:
            print(f"  - {fmt_hms(a)} → {fmt_hms(b)}  静音 {g:.1f}s")
    if st['lows']:
        print(f"低覆盖窗口（<{low:g}）{len(st['lows'])} 处，最长 5 处：")
        for a, b, avg in st['lows'][:5]:
            print(f"  - {fmt_hms(a)} → {fmt_hms(b)}  覆盖 {avg:.0%}")
    print("提示：低覆盖/长静音多为翻页、答疑、现场操作；选段前请回听确认，不要只看图。")


if __name__ == '__main__':
    main()
