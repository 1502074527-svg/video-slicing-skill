#!/usr/bin/env python3
"""按切点表批量切片：每段一个 mp4 + 一段时间归零的字幕（可选烧字幕）。

切片用重编码（-ss 精确到帧），不用 -c copy——后者会把切点吸附到关键帧，
关键帧间隔 2s 时开头可能多出或少掉一两秒，与切点表对不上。

字幕窗口规则：中点在 [起, 止] 内的字幕条归入该段，时间整体减去起点。
**只裁窗口、不二次拆分**——拆分正是「半句腰斩」的来源。

用法:
  python3 generate_slices.py <切点表.md> <源视频> <精确字幕.srt> <输出目录> \
      [--only N] [--burn] [--crf 20] [--force]

  --only N   只处理第 N 段
  --burn     额外生成一段烧了字幕的 mp4（*.burned.mp4）
  --force    输出目录非空时也继续（默认拒绝，防止旧切片混入新结果）

产出结构：<输出目录>/01-标题/01-标题.mp4 + .srt
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from srtlib import fmt_srt, load_cut_table, parse_srt, safe_name, write_srt


def probe_duration(path):
    for args in (['-show_entries', 'format=duration', '-of', 'csv=p=0'],
                 ['-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0']):
        r = subprocess.run(['ffprobe', '-v', 'error', *args, str(path)], capture_output=True, text=True)
        try:
            v = float(r.stdout.strip().splitlines()[0])
            if v > 0:
                return v
        except (ValueError, IndexError):
            continue
    return None


def cut(src, a, b, out, crf, preset):
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error',
                        '-ss', f"{a:.3f}", '-to', f"{b:.3f}", '-i', str(src),
                        '-c:v', 'libx264', '-preset', preset, '-crf', str(crf),
                        '-c:a', 'aac', '-b:a', '160k', str(out)],
                       capture_output=True, text=True)
    return r.stderr.strip()


def burn(seg_dir, name):
    src, sub = f"{name}.mp4", f"{name}.srt"
    burned = f"{name}.burned.mp4"
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src,
                        '-vf', f"subtitles={sub}", '-c:a', 'copy', burned],
                       capture_output=True, text=True, cwd=str(seg_dir))
    return r.stderr.strip()


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    table, src, srt, outdir = map(Path, sys.argv[1:5])
    args = sys.argv[5:]
    only = int(args[args.index('--only') + 1]) if '--only' in args else None
    do_burn = '--burn' in args
    force = '--force' in args
    crf = args[args.index('--crf') + 1] if '--crf' in args else '20'
    preset = args[args.index('--preset') + 1] if '--preset' in args else 'veryfast'

    if not src.exists():
        sys.exit(f"✗ 源视频不存在：{src}")
    if outdir.exists() and any(outdir.iterdir()) and not force:
        sys.exit(f"✗ 输出目录非空：{outdir}\n  确认继续加 --force（旧文件不会被删除，但可能有旧切片混入）。")
    rows = load_cut_table(table)
    cues = parse_srt(srt)
    if not rows:
        sys.exit(f"✗ {table} 里没读到切点行")
    outdir.mkdir(parents=True, exist_ok=True)

    ok, failed = 0, 0
    for r in rows:
        if only and r['num'] != only:
            continue
        a, b = r['start'], r['end']
        want = b - a
        if want <= 0:
            print(f"#{r['num']} 跳过：起止不合法")
            failed += 1
            continue
        name = f"{r['num']:02d}-{safe_name(r['title'] or 'slice')}"
        seg = outdir / name
        seg.mkdir(exist_ok=True)
        clip = seg / f"{name}.mp4"

        have = probe_duration(clip) if clip.exists() else None
        if clip.exists() and not force and have is not None and abs(have - want) <= 0.5:
            print(f"#{r['num']} 复用已有切片（{have:.1f}s ≈ {want:.1f}s）")
        else:
            if clip.exists():
                print(f"#{r['num']} 旧切片 {have and round(have, 1)}s 与切点表 {want:.1f}s 不符，重切")
            err = cut(src, a, b, clip, crf, preset)
            if err:
                print(f"#{r['num']} ✗ ffmpeg 失败：{err[:200]}")
                failed += 1
                continue
            got = probe_duration(clip)
            if got is not None and abs(got - want) > 1.0:
                print(f"#{r['num']} ⚠️ 实际 {got:.1f}s 与目标 {want:.1f}s 偏差较大，请核验")

        picked = []
        for c in cues:
            mid = (c['start'] + c['end']) / 2
            if not (a <= mid <= b):
                continue
            s2, e2 = max(c['start'], a) - a, min(c['end'], b) - a
            if e2 - s2 < 0.2:
                continue
            picked.append({'start': s2, 'end': e2, 'text': c['text']})
        write_srt(picked, seg / f"{name}.srt")

        if do_burn:
            err = burn(seg, name)
            if err:
                print(f"#{r['num']} ⚠️ 烧字幕失败：{err[:160]}")
        print(f"#{r['num']} ✓ {name}  {want:.1f}s / {len(picked)} 条字幕"
              f"{' + burned' if do_burn else ''}")
        ok += 1

    print(f"\n完成 {ok} 段，失败 {failed} 段 -> {outdir}")
    if ok:
        print("下一步：verify_slices.py 核验时长与切点是否与字幕对齐")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
