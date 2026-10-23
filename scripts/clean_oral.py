#!/usr/bin/env python3
"""口语清理：去「啊、呃、嗯」等口水词，保留所有语义内容。

铁律：
 1. 只删字符，不动时间戳 —— 时间轴永远回到字级 SRT。
 2. 经典原文守卫 —— 叠字（肫肫/夭夭/谆谆等）与术语白名单绝不许删，
    防止把《四书》原文当口水词误删。
 3. 本脚本**不做**"删讲错重讲"的语义判断 —— 那需要听音频，交给人工。

用法: python3 clean_oral.py <输入.srt> <输出.srt> [--filler "嗯呃啊哦噢诶哎唉"]

注意：哈/嘿/吼 默认**不删**——它们多是笑声而非口水词，盲删会把「哈佛」「哈耶克」
「吼叫」削掉一半。确需清理请显式传 --filler 覆盖默认表。
"""
import re
import sys
from pathlib import Path

# 只收真正的口水音。绝不把「这个/就是/好」放进列表——它们是正常用词，
# 曾因误删导致「很好」变「很」、语义被改。
DEFAULT_FILLER = '嗯呃啊哦噢诶哎唉'

# 经典原文守卫：这些字符串里出现的"filler 字符"不许删
# （例如「肫肫其仁」里的叠字不是口水词）
DEFAULT_GUARD = [
    '肫肫', '夭夭', '谆谆', '惶惶', '戚戚', '赫赫', '明明', '赳赳',
    '关关', '苍苍', '悠悠', '洋洋', '战战', '兢兢', '熙熙', '攘攘',
]


def get_arg(key, default):
    """取参数值；参数存在但后面没跟值时给出明确报错，而不是 IndexError。"""
    if key not in sys.argv:
        return default
    i = sys.argv.index(key) + 1
    if i >= len(sys.argv):
        print(f"✗ 参数 {key} 后面缺少取值")
        sys.exit(2)
    return sys.argv[i]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    inp, outp = Path(sys.argv[1]), Path(sys.argv[2])
    filler = get_arg('--filler', DEFAULT_FILLER)

    raw = inp.read_text(encoding='utf-8')

    # 守卫：先把白名单词替换成占位符，清完再还原
    placeholders = {}
    for i, g in enumerate(DEFAULT_GUARD):
        ph = f"\x00G{i}\x00"
        if g in raw:
            raw = raw.replace(g, ph)
            placeholders[ph] = g

    removed = 0
    lines = []
    for ln in raw.splitlines():
        if '-->' in ln or ln.strip().isdigit() or not ln.strip():
            lines.append(ln)
            continue
        before = ln
        ln = ''.join(ch for ch in ln if ch not in filler)
        # 清理因删字产生的粘连标点
        ln = re.sub(r'[，、]{2,}', '，', ln)
        ln = re.sub(r'[，、]\s*。', '。', ln)
        removed += sum(1 for ch in before if ch in filler)
        lines.append(ln)
    raw = '\n'.join(lines)

    for ph, g in placeholders.items():
        raw = raw.replace(ph, g)

    outp.write_text(raw, encoding='utf-8')
    print(f"清理口水字符 {removed} 个（守卫 {len(placeholders)} 条经典叠字未动）-> {outp}")


if __name__ == '__main__':
    main()
