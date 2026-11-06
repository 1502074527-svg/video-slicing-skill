#!/usr/bin/env python3
"""用【字级时间戳】生成精确字幕：支持 4 种电影级断句模式，不腰斩语义。

模式：
  sentence  整句：**只在 。？！ 后断**（不按字数强断，只在真实静音处另起），节奏舒缓，适合 B 站/学术讲座
  semantic  语义句（默认）：句界 。？！ 优先，整句 ≤16 字不拆，超长才在句内软标点处拆
  clause    半句：在 ，、；：。？！ 后都断，节奏明快，适合视频号/小红书
  fragment  碎句：所有标点后都断 + 长句强断，节奏紧凑，适合抖音/Shorts

原理：
 1. 字级 SRT（每字独立起止时间）与校对后文本做字符级对齐，得到每字真实起止时间。
 2. 按选定模式的标点集合把文本切成块，每块取真实起止时间作为一条字幕。
 3. 跨静音（>=1.2s）强制断条；过短碎块回并邻块；semantic/clause/fragment 另有过长强断。
 4. 所有时间戳吸附到帧边界（默认 30fps）。

用法:
  python3 build_subtitles.py <字级.srt> <校对稿.srt> <输出.srt> \\
      [--mode sentence|semantic|clause|fragment] [--max-chars N] [--max-secs 6.5] \\
      [--fps 30] [--punct-mode course|film] [--force]

  python3 build_subtitles.py check <字幕.srt> [--max-chars 16] [--max-cps 9]

check 是产出体检：单行铁律、阅读字数、纯标点卡、连接词悬空、读速上限。
✗ 为强制项（exit 1），△ 为质量建议项（不影响退出码）。
"""
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from safe_out import guard_output

STRONG_PUNCT = '。！？!?'
WEAK_PUNCT = '，、；：,;:'
ALL_PUNCT = STRONG_PUNCT + WEAK_PUNCT
SENT_TAIL = re.compile(r'[。！？!?…]+$')

# 阅读字数：标点与空白不计入（判超长、算读速都用这个口径）
PUNCT_CHARS = '。，、；：？！…—·「」『』（）《》〈〉【】“”‘’,.!?;:()"\''
PUNCT_RE = re.compile(r'[%s\s]' % re.escape(PUNCT_CHARS))

# 连接词：出现在一幕结尾即为「悬空」。含口语高频词（课程实录里挂得最多的就是这些）
CONNECTORS = ('也就是说', '换句话说', '总而言之', '总之', '但是', '然而', '所以', '因此',
              '而且', '并且', '或者', '还是', '不过', '可是', '再说', '另外', '同时',
              '其实', '毕竟', '那么', '然后', '就是', '这个', '那个', '的话', '因为',
              '如果', '比方', '等于', '好像')


def read_len(text):
    """阅读字数：只数实字，标点空白不算。"""
    return len(PUNCT_RE.sub('', text))


def dangling(text):
    """幕尾是否挂着连接词；句末标点收尾的不算悬空。返回该连接词或 None。"""
    if SENT_TAIL.search(text):
        return None
    t = PUNCT_RE.sub('', text)
    for w in sorted(CONNECTORS, key=len, reverse=True):
        if t.endswith(w):
            return w
    return None


def render_punct(text, mode):
    """course 保留全部标点；film 删句号、逗号类换空格、删引号，只留问号感叹号与书名号。"""
    if mode != 'film':
        return text
    t = re.sub(r'[。.]', '', text)
    t = re.sub(r'[，、；：,;:]', ' ', t)
    t = re.sub(r'[「」『』“”‘’]', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def check_rows(rows, max_chars, max_cps, label=''):
    """产出体检：rows = [(start, end, [行...])]。✗ 强制项 exit 1，△ 质量建议项只提示。"""
    hard = soft = 0
    print(f"== 字幕体检 {label}（{len(rows)} 条；上限 {max_chars} 字 / {max_cps} 字每秒） ==")
    for i, (s, e, lines) in enumerate(rows, 1):
        text = '\n'.join(lines).strip()
        rl = read_len(text)
        issues = []
        if len([x for x in lines if x.strip()]) > 1:
            issues.append(('✗', '两行及以上（单行铁律）'))
        if rl == 0:
            issues.append(('✗', '纯标点卡'))
        elif rl > max_chars:
            issues.append(('✗', f'超长 {rl} > {max_chars} 字'))
        d = dangling(text)
        if d:
            issues.append(('△', f'连接词悬空「{d}」'))
        cps = rl / max(e - s, 1e-9)
        if cps > max_cps:
            issues.append(('✗', f'读速 {cps:.1f} > {max_cps} 字/秒'))
        for lvl, msg in issues:
            if lvl == '✗':
                hard += 1
            else:
                soft += 1
            print(f"{lvl} 第{i}条 [{s:7.2f}-{e:7.2f}s] {msg}：{text[:24]}")
    print(f"强制违规 {hard} 处，质量建议 {soft} 处")
    return 1 if hard else 0

# 模式 -> (断句标点集合, 强断阈值字数（None = 不按字数强断）, 推荐最大时长)
MODES = {
    'sentence': (STRONG_PUNCT, None, 6.5),
    'semantic': (STRONG_PUNCT, 16, 5.0),
    'clause':   (ALL_PUNCT,    20, 5.0),
    'fragment': (ALL_PUNCT,    10, 3.5),
}


def to_sec(ts):
    m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts)
    g = [int(x) for x in m.groups()]
    return g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000


def parse_srt(path):
    raw = Path(path).read_text(encoding='utf-8')
    out = []
    for b in re.split(r'\n\s*\n', raw.strip()):
        L = b.strip().split('\n')
        if len(L) < 3:
            continue
        m = re.match(r'([\d:,.]+) --> ([\d:,.]+)', L[1])
        if not m:
            continue
        out.append((to_sec(m.group(1)), to_sec(m.group(2)), ''.join(L[2:]).strip()))
    return out


def align(word_cues, text):
    """把校对文本对齐到字级 cue 上，返回 [(char, start, end)]。"""
    a_chars, a_times = [], []
    for s, e, t in word_cues:
        for ch in t:
            a_chars.append(ch)
            a_times.append((s, e))
    b_chars = list(text)
    sm = SequenceMatcher(None, ''.join(a_chars), ''.join(b_chars), autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                out.append((b_chars[j1 + k], a_times[i1 + k][0], a_times[i1 + k][1]))
        elif tag == 'replace':
            if (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    out.append((b_chars[j1 + k], a_times[i1 + k][0], a_times[i1 + k][1]))
            elif i1 < len(a_times):
                st = a_times[i1][0]
                en = a_times[min(i2 - 1, len(a_times) - 1)][1]
                step = (en - st) / max(1, j2 - j1)
                for k in range(j2 - j1):
                    out.append((b_chars[j1 + k], st + k * step, st + (k + 1) * step))
        elif tag == 'insert':
            base = a_times[i1] if i1 < len(a_times) else (a_times[-1] if a_times else (0.0, 0.0))
            step = (base[1] - base[0]) / max(1, j2 - j1)
            for k in range(j2 - j1):
                out.append((b_chars[j1 + k], base[0] + k * step, base[0] + (k + 1) * step))
    return out


def cut_into_cues(chars, puncts, strong_max_chars, max_chars, max_secs,
                  min_secs=1.0, min_chars=4, silence_gap=1.2):
    """按模式分句：先在标点处断，跨静音强断，过长强断，过短回并。"""
    # 1) 先在标点 + 静音处断出原子块
    blocks, cur = [], []
    for i, c in enumerate(chars):
        cur.append(c)
        nxt_gap = chars[i + 1][1] - c[2] if i + 1 < len(chars) else 99
        if c[0] in puncts or nxt_gap >= silence_gap:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)

    # 2) 过长块在就近标点/最长停顿处强断（sentence 模式不做这一步，严守「只在句末断」）
    refined = []
    for blk in blocks:
        while (strong_max_chars is not None and len(blk) > 1
               and (read_len(''.join(c[0] for c in blk)) > strong_max_chars
                    or blk[-1][2] - blk[0][1] > max_secs)):
            cut = _preferred_cut(blk, strong_max_chars)
            cut = max(1, min(cut, len(blk) - 1))
            refined.append(blk[:cut])
            blk = blk[cut:]
        if blk:
            refined.append(blk)

    # 2.5) 连接词悬空：把切点前移到连接词之前（改时间轴切点，不搬文字——文字永不早于声音）
    protected = []
    for i, blk in enumerate(refined):
        text = ''.join(c[0] for c in blk)
        w = dangling(text)
        if w and i + 1 < len(refined):
            cut = len(blk) - len(w)
            head = ''.join(c[0] for c in blk[:cut])
            gap = refined[i + 1][0][1] - blk[-1][2]
            if cut > 0 and read_len(head) >= min_chars and gap < silence_gap:
                protected.append(blk[:cut])
                protected.append(blk[cut:])
                continue
        protected.append(blk)
    refined = protected

    # 2.6) 只剩连接词的短块（如「因此，」）：并到**下一块开头**，而不是并回上一块
    #      ——连接词本来属于下一句，往前后并都会造成悬空
    joined = []
    i = 0
    while i < len(refined):
        blk = refined[i]
        text = ''.join(c[0] for c in blk)
        if (i + 1 < len(refined) and read_len(text) <= 3 and dangling(text)
                and refined[i + 1][0][1] - blk[-1][2] < silence_gap):
            joined.append(blk + refined[i + 1])
            i += 2
            continue
        joined.append(blk)
        i += 1
    refined = joined

    # 3) 过短碎块回并邻块（不跨静音，也不跨句末标点——否则整句模式会被并回长条）
    out = []
    for blk in refined:
        t = ''.join(c[0] for c in blk)
        dur = blk[-1][2] - blk[0][1]
        gap = blk[0][1] - out[-1][-1][2] if out else 0.0
        prev_t = ''.join(c[0] for c in out[-1]) if out else ''
        if (out and (read_len(t) < min_chars or dur < min_secs) and gap < silence_gap
                and not SENT_TAIL.search(prev_t) and not dangling(prev_t)):
            merged_t = prev_t + t
            merged_d = blk[-1][2] - out[-1][0][1]
            if read_len(merged_t) <= max_chars and merged_d <= max_secs:
                out[-1] = out[-1] + blk
                continue
        out.append(blk)
    return [b for b in out if b]


def _preferred_cut(chars, max_chars):
    """在 [0, max_chars] 里挑断点：优先最近的标点，其次最长停顿，最后硬切。"""
    n = len(chars)
    end = min(max_chars, n)
    for k in range(end, 0, -1):
        if chars[k - 1][0] in ALL_PUNCT:
            return k
    best, best_gap = end, -1.0
    for k in range(max(1, end - 4), min(end + 4, n)):
        g = chars[k][1] - chars[k - 1][2]
        if g > best_gap:
            best_gap, best = g, k
    return best


def fmt(t, fps):
    snap = lambda x: round(x * fps) / fps
    ms = max(0, int(round(snap(t) * 1000)))
    return f"{ms//3600000:02d}:{ms%3600000//60000:02d}:{ms%60000//1000:02d},{ms%1000:03d}"


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == 'check':
        if len(sys.argv) < 3:
            print(__doc__)
            return 1
        args = sys.argv[3:]
        get = lambda k, d=None: (args[args.index(k) + 1] if k in args else d)
        max_chars = int(get('--max-chars', 16))
        max_cps = float(get('--max-cps', 9))
        raw = Path(sys.argv[2]).read_text(encoding='utf-8')
        rows = []
        for b in re.split(r'\n\s*\n', raw.strip()):
            L = b.strip().split('\n')
            if len(L) < 3:
                continue
            m = re.match(r'([\d:,.]+) --> ([\d:,.]+)', L[1])
            if not m:
                continue
            rows.append((to_sec(m.group(1)), to_sec(m.group(2)), L[2:]))
        return check_rows(rows, max_chars, max_cps, Path(sys.argv[2]).name)

    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    wl, pf, out = sys.argv[1], sys.argv[2], sys.argv[3]
    guard_output(out, wl)
    args = sys.argv[4:]
    get = lambda k, d=None: (args[args.index(k) + 1] if k in args else d)
    mode = get('--mode', 'semantic')
    if mode not in MODES:
        print(f"✗ --mode 必须是 {list(MODES)} 之一，收到 {mode!r}")
        sys.exit(2)
    punct_mode = get('--punct-mode', 'course')
    if punct_mode not in ('course', 'film'):
        print(f"✗ --punct-mode 必须是 course 或 film，收到 {punct_mode!r}")
        sys.exit(2)
    max_cps = float(get('--max-cps', 9))
    puncts, strong_max_chars, default_max_secs = MODES[mode]
    max_chars = int(get('--max-chars', 16 if mode == 'semantic' else 30))
    max_secs = float(get('--max-secs', default_max_secs))
    fps = float(get('--fps', 30))

    for label, fp in (("字级srt", wl), ("校对稿srt", pf)):
        if not Path(fp).exists():
            print(f"✗ 找不到{label}: {fp}")
            sys.exit(2)

    word_cues = parse_srt(wl)
    proof = parse_srt(pf)
    full = ''.join(t for _, _, t in proof).strip()
    aligned = align(word_cues, full)
    print(f"字级 cue={len(word_cues)} 校对稿字符={len(full)} 可对齐={len(aligned)} "
          f"({len(aligned)/max(1,len(full)):.1%})")

    cues = []
    for chunk in cut_into_cues(aligned, puncts, strong_max_chars, max_chars, max_secs):
        cues.append({'start': chunk[0][1], 'end': chunk[-1][2],
                     'text': render_punct(''.join(c[0] for c in chunk), punct_mode)})

    # 收尾：清重叠、保底时长
    cues = [c for c in cues if any('一' <= ch <= '鿿' for ch in c['text'])]
    for i in range(1, len(cues)):
        if cues[i]['start'] < cues[i - 1]['end']:
            mid = (cues[i]['start'] + cues[i - 1]['end']) / 2
            cues[i - 1]['end'] = mid
            cues[i]['start'] = mid
    for c in cues:
        if c['end'] - c['start'] < 0.6:
            c['end'] = c['start'] + 0.6

    Path(out).write_text('\n'.join(
        f"{i}\n{fmt(c['start'], fps)} --> {fmt(c['end'], fps)}\n{c['text']}\n"
        for i, c in enumerate(cues, 1)), encoding='utf-8')

    durs = [c['end'] - c['start'] for c in cues]
    lens = [read_len(c['text']) for c in cues]
    if durs:
        med = sorted(durs)[len(durs) // 2]
        if med < 0.8 and mode != 'fragment':
            print(f"⚠️  字幕时长中位仅 {med:.1f}s —— 请确认第一份 srt 是字级稿，不是句级稿。")
        if mode == 'sentence':
            overs = [c for c in cues if read_len(c['text']) > max_chars]
            if overs:
                print(f"⚠️  {len(overs)} 条字幕超过 {max_chars} 字（最长 "
                      f"{max(read_len(c['text']) for c in cues)} 字）。sentence 模式只在句末断句；"
                      f"若源稿缺标点，请先补标点，或改用 --mode clause。")
        print(f"输出 {out}: {len(cues)} 条；模式={mode}；"
              f"时长 中位={med:.1f}s；字数 中位={sorted(lens)[len(lens)//2]}")
    return check_rows([(c['start'], c['end'], [c['text']]) for c in cues],
                      max_chars, max_cps, Path(out).name)


if __name__ == '__main__':
    sys.exit(main())
