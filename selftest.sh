#!/usr/bin/env bash
# 回归自检：用内置样例跑通全链路，不需要视频、不需要联网、不需要 API Key。
# 用法：./selftest.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SAMPLE="$ROOT/examples/confucian-course/sample"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0
ok()   { echo "  ✓ $1"; pass=$((pass + 1)); }
bad()  { echo "  ✗ $1"; fail=$((fail + 1)); }
count() { grep -c -- ' --> ' "$1" 2>/dev/null || true; }

echo "== 1. 脚本语法检查 =="
if python3 -m py_compile "$ROOT"/scripts/*.py 2>/dev/null; then ok "6 个脚本语法通过"; else bad "语法检查失败"; fi

echo "== 2. 字级 → 句级 =="
python3 "$ROOT/scripts/merge_srt.py" "$SAMPLE/字级-样例.srt" "$TMP/句级.srt" >/dev/null
if [ "$(count "$TMP/句级.srt")" -eq 3 ]; then ok "句级 3 条（按标点+静音断句）"; else bad "句级条数异常：$(count "$TMP/句级.srt")"; fi

echo "== 3. 术语确定性替换 =="
python3 "$ROOT/scripts/proofread.py" "$TMP/句级.srt" "$TMP/句级-术语.srt" \
  "$SAMPLE/术语替换表-样例.txt" "$TMP/报告.md" >/dev/null
if grep -q '人禽之辨' "$TMP/句级-术语.srt"; then ok "人禽之变 → 人禽之辨"; else bad "术语未替换"; fi
if grep -q '人禽之变 => 人禽之辨' "$TMP/报告.md"; then ok "替换报告可追溯"; else bad "报告缺明细"; fi

echo "== 4. 口语清理（含哈佛误删守卫）=="
python3 "$ROOT/scripts/clean_oral.py" "$TMP/句级-术语.srt" "$TMP/句级-清理.srt" >/dev/null
if grep -q '哈佛' "$TMP/句级-清理.srt"; then ok "「哈佛」未被误删（回归守卫）"; else bad "「哈佛」被误删——哈字盲删回归"; fi
if ! grep -qE '[嗯呃]' "$TMP/句级-清理.srt"; then ok "口水词已清理"; else bad "口水词残留"; fi

echo "== 5. 三种断句模式 =="
for mode in sentence clause fragment; do
  python3 "$ROOT/scripts/build_subtitles.py" "$SAMPLE/字级-样例.srt" "$TMP/句级-清理.srt" \
    "$TMP/$mode.srt" --mode "$mode" >/dev/null
  if [ "$(count "$TMP/$mode.srt")" -ge 3 ]; then ok "$mode 模式产出 $(count "$TMP/$mode.srt") 条"; else bad "$mode 模式产出异常"; fi
done
# sentence 模式承诺只在 。？！ 断句，任何一条都不该以逗号结尾
if ! grep -q '，$' "$TMP/sentence.srt"; then ok "sentence 模式未在逗号处断句"; else bad "sentence 模式在逗号处断句"; fi

echo "== 6. 沉淀回写（默认只读 / --write 才落盘）=="
cp "$SAMPLE/术语替换表-样例.txt" "$TMP/词表.txt"
before="$(cksum < "$TMP/词表.txt")"
python3 "$ROOT/scripts/consolidate_lexicon.py" "$SAMPLE/校对建议-样例.tsv" "$TMP/词表.txt" >/dev/null
after="$(cksum < "$TMP/词表.txt")"
if [ "$before" = "$after" ]; then ok "不加 --write 不落盘"; else bad "默认状态竟改写了词表"; fi
python3 "$ROOT/scripts/consolidate_lexicon.py" "$SAMPLE/校对建议-样例.tsv" "$TMP/词表.txt" --write >/dev/null
if grep -q '结囊 => 截然' "$TMP/词表.txt"; then ok "--write 正确回写 2 字术语对"; else bad "--write 未回写"; fi
if ! grep -q '变 => 辨' "$TMP/词表.txt"; then ok "危险单字对已被拦截"; else bad "单字对污染词表"; fi

echo
echo "结果：$pass 通过 / $fail 失败"
[ "$fail" -eq 0 ] || exit 1
