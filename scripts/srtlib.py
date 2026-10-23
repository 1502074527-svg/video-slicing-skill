"""SRT / 切点表 解析与格式化（纯标准库，供 scripts/ 下各脚本共用）。"""
import re
from pathlib import Path


def to_sec(s):
    """'HH:MM:SS,mmm' / 'MM:SS' / '12.5' → 秒（浮点，保留毫秒）。"""
    s = str(s).strip().replace(',', '.')
    parts = [float(p) for p in s.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def fmt_srt(t):
    ms = max(0, int(round(t * 1000)))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def fmt_hms(t):
    """切点表用：带毫秒的 HH:MM:SS.mmm，切点靠毫秒卡字幕间隙。"""
    ms = max(0, int(round(t * 1000)))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}.{ms % 1000:03d}"


def fmt_dur(t):
    return f"{t:.1f}s"


def parse_srt(path):
    raw = Path(path).read_text(encoding='utf-8-sig')
    cues = []
    for block in re.split(r'\n\s*\n', raw.strip()):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'\s*([\d:,.]+)\s*-->\s*([\d:,.]+)', lines[1])
        if not m:
            continue
        cues.append({'start': to_sec(m.group(1)), 'end': to_sec(m.group(2)),
                     'text': '\n'.join(lines[2:]).strip()})
    return cues


def write_srt(cues, path):
    Path(path).write_text('\n'.join(
        f"{i}\n{fmt_srt(c['start'])} --> {fmt_srt(c['end'])}\n{c['text']}\n"
        for i, c in enumerate(cues, 1)), encoding='utf-8')


CUT_ROW = re.compile(
    r'\|\s*(\d+)\s*\|\s*([\d:.]+)\s*\|\s*([\d:.]+)\s*\|\s*[\d:.]+[a-z]*\s*\|\s*([^|]*)\|')


def load_cut_table(path):
    """读切点表 markdown：| # | 起 | 止 | 时长 | 首句 |。返回 [{num,start,end,title}]。"""
    rows = []
    for ln in Path(path).read_text(encoding='utf-8').splitlines():
        m = CUT_ROW.match(ln)
        if not m:
            continue
        rows.append({'num': int(m.group(1)), 'start': to_sec(m.group(2)),
                     'end': to_sec(m.group(3)), 'title': m.group(4).strip()})
    return rows


def safe_name(s, n=24):
    """切片目录/文件名：去掉路径分隔符等非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', '-', str(s)).strip()[:n]


def plain(s):
    """去掉标点与换行，用于标题。"""
    return re.sub(r'[\s，。、！？；：、,.!?;:…—\-]+', '', str(s))
