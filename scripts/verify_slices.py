#!/usr/bin/env python3
"""核验切片是否真的对得上切点表与字幕（防止「切点表改了、旧 mp4 没重切」事故）。

逐段检查 4 项：
 1) mp4 存在，且实际时长 ≈ 表中（止 - 起），容差 --tol（默认 0.5s）
 2) 起止落在字幕间隙内，没有从一条字幕中间切开
 3) 片内 srt 首条从 0 起（≤0.15s）
 4) 片内 srt 末条覆盖到片尾 2s 以内

用法:
  python3 verify_slices.py <切点表.md> <精确字幕.srt> <切片目录> [--tol 0.5] [--only N]
退出码：有任一段失败则为 1。
"""
import subprocess
import sys
from pathlib import Path

from srtlib import load_cut_table, parse_srt, safe_name


def probe_duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def check_gap(cues, a, b):
    """起止必须落在字幕间隙，不能从某条字幕中间切开。"""
    issues = []
    for c in cues:
        if c['start'] < a - 0.05 and c['end'] > a + 0.05:
            issues.append(f"起点 {a:.2f}s 落在字幕内部（「{c['text'][:12]}」）")
            break
    for c in cues:
        if c['start'] < b - 0.05 and c['end'] > b + 0.05:
            issues.append(f"止点 {b:.2f}s 落在字幕内部（「{c['text'][:12]}」）")
            break
    return issues


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    table, srt, slicedir = map(Path, sys.argv[1:4])
    args = sys.argv[4:]
    tol = float(args[args.index('--tol') + 1]) if '--tol' in args else 0.5
    only = int(args[args.index('--only') + 1]) if '--only' in args else None

    rows = load_cut_table(table)
    src_cues = parse_srt(srt)
    bad = 0
    for r in rows:
        if only and r['num'] != only:
            continue
        want = r['end'] - r['start']
        name = f"{r['num']:02d}-{safe_name(r['title'] or 'slice')}"
        seg = slicedir / name
        clip = seg / f"{name}.mp4"

        issues = []
        if not clip.exists():
            print(f"[FAIL] #{r['num']} {name}: mp4 缺失")
            bad += 1
            continue
        have = probe_duration(clip)
        corr = 0.0
        if have is None:
            issues.append("ffprobe 读不到时长")
        else:
            corr = max(0.0, 1 - abs(have - want) / max(want, 1e-6))
            if abs(have - want) > tol:
                issues.append(f"时长 {have:.2f}s ≠ 表中 {want:.2f}s（差 {have - want:+.2f}s）")

        issues += check_gap(src_cues, r['start'], r['end'])

        inner = seg / f"{name}.srt"
        n_cues, first, last = 0, None, None
        if inner.exists():
            ic = parse_srt(inner)
            n_cues = len(ic)
            if ic:
                first, last = ic[0]['start'], ic[-1]['end']
        else:
            issues.append("片内字幕缺失")
        if first is not None and first > 0.15:
            issues.append(f"片内首条字幕从 {first:.2f}s 才开始")
        if last is not None and have is not None and last < have - 2.0:
            issues.append(f"片内末条字幕只到 {last:.2f}s，片尾 {have:.2f}s 无字幕")
        if n_cues == 0:
            issues.append("片内字幕 0 条")

        state = "OK  " if not issues else "FAIL"
        print(f"[{state}] #{r['num']} {name[:26]}  时长={have and round(have, 2)}s/{want:.2f}s "
              f"字幕={n_cues}条 corr={corr:.3f}")
        for i in issues:
            print(f"        - {i}")
        if issues:
            bad += 1

    print(f"\n合计 {len(rows) if not only else 1} 段，异常 {bad} 段")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
