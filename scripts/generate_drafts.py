#!/usr/bin/env python3
"""按切点表批量生成剪映草稿：每段一个草稿（视频 + 精确字幕 + 统一样式）。

前置：装 capcut-cli（`capcut --version` 能跑通），并确认剪映装在本机。
不需要草稿时用 generate_slices.py 即可——它只产 mp4 + srt，不碰剪映。

用法:
  python3 generate_drafts.py <切点表.md> <源视频> <精确字幕.srt> <输出目录> \
      [--only N] [--drafts 草稿库] [--font-size 5] [--y -0.7] [--no-shadow] [--force]

  --drafts      草稿库目录；默认取 CAPCUT_DRAFT_DIR，否则按平台默认路径
  --font-size   字号（canvas 百分比，课程字幕实测 5）
  --y           字幕垂直位置（负数靠下，默认 -0.7）
  --no-shadow   不加阴影
  --force       同名草稿已存在时删除重建（默认拒绝，避免覆盖你手工调过的草稿）

产出：<输出目录>/NN-标题/NN-标题.mp4 + .srt，以及草稿库里的同名工程。
⚠️ 剪映正在运行时写草稿可能被回写覆盖，先退出剪映。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fix_text_style import apply_style
from generate_slices import cut, probe_duration
from srtlib import load_cut_table, parse_srt, safe_name, write_srt


def default_drafts_dir():
    env = os.environ.get("CAPCUT_DRAFT_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    return Path.home() / "Movies" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    table, src, srt, outdir = map(Path, sys.argv[1:5])
    args = sys.argv[5:]
    get = lambda k, d: (args[args.index(k) + 1] if k in args else d)
    only = int(get('--only', 0)) or None
    drafts = Path(get('--drafts', str(default_drafts_dir())))
    font_size = float(get('--font-size', 5))
    pos_y = float(get('--y', -0.7))
    shadow = '--no-shadow' not in args
    force = '--force' in args

    if not shutil.which('capcut'):
        sys.exit("✗ 没找到 capcut-cli。装好后再跑，或改用 generate_slices.py 只出 mp4+srt。")
    if not src.exists():
        sys.exit(f"✗ 源视频不存在：{src}")
    if outdir.exists() and any(outdir.iterdir()) and not force:
        sys.exit(f"✗ 输出目录非空：{outdir}\n  确认继续加 --force。")
    if not drafts.exists():
        sys.exit(f"✗ 草稿库不存在：{drafts}\n  用 --drafts 指定，或先打开一次剪映让它初始化。")

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
        clip, sub = seg / f"{name}.mp4", seg / f"{name}.srt"

        have = probe_duration(clip) if clip.exists() else None
        if not (clip.exists() and have is not None and abs(have - want) <= 0.5):
            err = cut(src, a, b, clip, '20', 'veryfast')
            if err:
                print(f"#{r['num']} ✗ ffmpeg 失败：{err[:200]}")
                failed += 1
                continue

        picked = []
        for c in cues:
            mid = (c['start'] + c['end']) / 2
            if not (a <= mid <= b):
                continue
            s2, e2 = max(c['start'], a) - a, min(c['end'], b) - a
            if e2 - s2 < 0.2:
                continue
            picked.append({'start': s2, 'end': e2, 'text': c['text']})
        write_srt(picked, sub)

        dpath = drafts / name
        if dpath.exists():
            if not force:
                print(f"#{r['num']} ✗ 草稿已存在：{dpath}（加 --force 删除重建）")
                failed += 1
                continue
            shutil.rmtree(dpath)
            print(f"#{r['num']} 删除旧草稿后重建：{name}")

        r2 = subprocess.run(['capcut', 'quickstart', name, '--video', str(clip), '--srt', str(sub),
                             '--drafts', str(drafts), '--jianying', '--ratio', '16:9',
                             '--template', 'bundled'],
                            capture_output=True, text=True)
        if r2.returncode != 0:
            print(f"#{r['num']} ✗ capcut 失败：{(r2.stderr or r2.stdout).strip()[:200]}")
            failed += 1
            continue
        apply_style(dpath, font_size, pos_y, shadow)
        print(f"#{r['num']} ✓ {name}  {want:.1f}s / {len(picked)} 条字幕 + 草稿")
        ok += 1

    print(f"\n完成 {ok} 段，失败 {failed} 段 -> 草稿库 {drafts}")
    print("提示：剪映需重启才能看到新草稿；样式改动同理。")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
