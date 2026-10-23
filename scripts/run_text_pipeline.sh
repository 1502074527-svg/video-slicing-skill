#!/usr/bin/env bash
# 一键串跑「文本段」机械环节：句级合并 → 术语替换 → 口语清理 → 断句字幕。
# 只跑确定性步骤；LLM 校对（proofread_llm）必须人工审 TSV，不放进自动链。
#
# 用法:
#   ./scripts/run_text_pipeline.sh <字级.srt> <输出目录> [--mode clause] [--lexicon 词表.txt] [--gap 1.2] [--force]
#
# 产出:
#   01-句级.srt    字级按静音/标点合并
#   02-术语.srt    确定性术语替换后（无词表则复制 01）
#   02-术语报告.md
#   03-口语.srt    去口水词
#   04-字幕.srt    按选定模式断句 + 帧吸附（最终交付）
#
# 缺少 pypinyin 或词表不影响本链；S3 切片见 references/sop.md Step 8。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -lt 2 ]; then
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi

SRC="$1"; OUT="$2"; shift 2
MODE="clause"; LEXICON=""; GAP="1.2"; FORCE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)    MODE="${2:-}"; shift 2 ;;
    --lexicon) LEXICON="${2:-}"; shift 2 ;;
    --gap)     GAP="${2:-}"; shift 2 ;;
    --force)   FORCE="--force"; shift ;;
    *) echo "✗ 未知参数: $1"; exit 1 ;;
  esac
done

[ -f "$SRC" ] || { echo "✗ 找不到字级字幕: $SRC"; exit 1; }
if [ -n "$LEXICON" ] && [ ! -f "$LEXICON" ]; then
  echo "✗ 找不到词表: $LEXICON"; exit 1
fi

mkdir -p "$OUT" || exit 1
S1="$OUT/01-句级.srt"
S2="$OUT/02-术语.srt"
REP="$OUT/02-术语报告.md"
S3="$OUT/03-口语.srt"
S4="$OUT/04-字幕.srt"

step() { printf '\n== %s ==\n' "$*"; }

step "1/4 字级 → 句级"
python3 "$ROOT/scripts/merge_srt.py" "$SRC" "$S1" --gap "$GAP" $FORCE || exit 1

if [ -n "$LEXICON" ]; then
  step "2/4 术语确定性替换"
  python3 "$ROOT/scripts/proofread.py" "$S1" "$S2" "$LEXICON" "$REP" $FORCE || exit 1
else
  step "2/4 跳过术语替换（未提供 --lexicon）"
  cp "$S1" "$S2"
  echo "  已复制为 $S2"
fi

step "3/4 口语清理"
python3 "$ROOT/scripts/clean_oral.py" "$S2" "$S3" $FORCE || exit 1

step "4/4 断句字幕（模式=${MODE}）"
python3 "$ROOT/scripts/build_subtitles.py" "$SRC" "$S3" "$S4" --mode "$MODE" $FORCE || exit 1

cat <<EOF

完成。机械环节产出：
  $S1
  $S2
  $S3
  $S4   ← 最终交付字幕

尚未完成（必须人工）：
  1. LLM 校对：proofread_llm.py review 出 TSV → 人工审 → apply（见 references/sop.md Step 4）
  2. 字幕质检：proofread_llm.py check（见 Step 7）
  3. 高光切片：propose_cuts.py → 人工复核 → generate_slices.py → verify_slices.py（Step 8）
EOF
