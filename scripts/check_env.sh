#!/usr/bin/env bash
# 环境自检：跑任何流程前先确认本机有什么、缺什么。
# 用法: ./scripts/check_env.sh
# 退出码：必需项缺失为 1；可选缺失只提示，不影响退出码。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

ok()   { printf '  ✓ %s\n' "$*"; }
bad()  { printf '  ✗ %s\n' "$*"; fail=$((fail + 1)); }
note() { printf '  · %s\n' "$*"; }

echo "== 必需 =="

if command -v python3 >/dev/null 2>&1; then
  ver="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)'; then
    ok "python3 $ver"
  else
    bad "python3 $ver 过低（需 ≥ 3.7）"
  fi
else
  bad "python3 未安装"
fi

if command -v python3 >/dev/null 2>&1; then
  broken=0
  for f in "$ROOT"/scripts/*.py; do
    [ -e "$f" ] || continue
    if ! python3 -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' "$f" 2>/dev/null; then
      bad "语法错误：$(basename "$f")"
      broken=1
    fi
  done
  [ "$broken" -eq 0 ] && ok "scripts/*.py 语法检查通过"
fi

echo
echo "== 视频相关（S3 高光剪辑必需）=="

if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg $(ffmpeg -version 2>/dev/null | head -n 1 | awk '{print $3}')"
else
  note "ffmpeg 未安装 —— 只做 S1/S2（字幕）不需要；做切片必装"
fi

if command -v ffprobe >/dev/null 2>&1; then
  ok "ffprobe"
else
  note "ffprobe 未安装 —— generate_slices / verify_slices 需要"
fi

echo
echo "== 可选 =="

if python3 -c 'import pypinyin' >/dev/null 2>&1; then
  ok "pypinyin（term_normalize 可用）"
else
  note "pypinyin 未安装 —— term_normalize 不可用；需要时 pip install pypinyin"
fi

if command -v capcut >/dev/null 2>&1; then
  ok "capcut-cli（剪映草稿）"
else
  note "capcut-cli 未安装 —— 只影响生成剪映草稿，不影响 mp4/srt 产出"
fi

if command -v fc-list >/dev/null 2>&1; then
  ok "fc-list（烧字幕排障可用）"
else
  note "fc-list 未安装 —— 烧中文字幕黑屏时无法快速查字体"
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "结论：必需项齐全。"
else
  echo "结论：$fail 个必需项有问题，先修再跑。"
fi
exit $((fail > 0))
