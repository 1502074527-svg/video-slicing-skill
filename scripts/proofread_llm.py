#!/usr/bin/env python3
"""LLM 校对：给转写稿找"同音/近音术语错"并补标点，产出**待人工审的 TSV**。

设计原则（铁律 2：文本只信人工校对）：
 - LLM 永远只提建议，不落笔。产出 TSV 后**必须人工审查**，确认后才 apply。
 - 标点：ASR 常把一整段吐成无标点流水句，LLM 补标点是一句一条字幕的前提。

用法:
  # 1) LLM 提校对建议（需 key）
  python3 proofread_llm.py review <in.srt> <校对建议.tsv> \
      [--prompt-file <校对员Prompt.md>] \
      [--terms <术语替换表.txt>] \
      [--api-base URL] [--model NAME] [--key KEY] [--batch 20] [--jobs 4]

  # 2) 人工审完 TSV 后，合入高置信建议
  python3 proofread_llm.py apply <in.srt> <校对建议.tsv> <out.srt> [--min-conf 0.9] [--only-terms]

Prompt 文件：
  --prompt-file 指定外部 Markdown 文件作为 system prompt（推荐，领域化）。
  不传时用内置 DEFAULT_PROMPT（通用听打校对员人设）。
  模板见 references/prompts/proofreader-template.md，儒学版见 proofreader-confucian.md。

环境变量：PROOFREAD_API_KEY / OPENAI_API_KEY，PROOFREAD_BASE_URL / OPENAI_BASE_URL。
TSV 列：起秒\t原句\t建议句\t改动\t置信度\t依据\t命中术语表
"""
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_PROMPT = """你是长视频听打稿的校对员。讲者口音不一，术语密集，转写稿用简体。

请逐句校对，只处理下面两类问题：
1) 同音/近音错字，尤其是术语与人名。
2) 缺少标点：把没标点的长流水句补上标点（，、。？！），**不要改动字词**（除了第 1 类错字）。

硬性要求：
- 绝对不得删除"啊、呃、嗯、这个、就是"等语气助词（后续有专门清理环节）。
- 不得改写、润色、简化、合并、增删讲者的意思。
- 不确定的不要改，把疑问写进 reason，confidence 给低分。
- 依据只能来自术语常识、上下文、经典原文。禁止编造。
- 输出必须是 JSON 数组，每项：{"i": 序号, "text": 校对后整句, "changed": true/false,
  "reason": "依据（一句话）", "confidence": 0.0~1.0}
"""


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
        out.append({'start': to_sec(m.group(1)), 'end': to_sec(m.group(2)),
                    'text': ''.join(L[2:])})
    return out


def fmt(t):
    ms = max(0, int(round(t * 1000)))
    return f"{ms//3600000:02d}:{ms%3600000//60000:02d}:{ms%60000//1000:02d},{ms%1000:03d}"


def call_llm(messages, key, base, model, timeout=180):
    body = json.dumps({'model': model, 'messages': messages, 'temperature': 0.1}).encode()
    req = urllib.request.Request(base.rstrip('/') + '/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return d['choices'][0]['message']['content']


def extract_json(txt):
    m = re.search(r'\[.*\]', txt, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def cmd_review(a):
    src, out = a[0], a[1]
    args = a[2:]
    get = lambda k, d=None: (args[args.index(k) + 1] if k in args else d)
    base = get('--api-base') or os.environ.get('PROOFREAD_BASE_URL') or os.environ.get('OPENAI_BASE_URL')
    key = get('--key') or os.environ.get('PROOFREAD_API_KEY') or os.environ.get('OPENAI_API_KEY')
    model = get('--model') or os.environ.get('PROOFREAD_MODEL') or 'deepseek-chat'
    batch = int(get('--batch', 20))
    jobs = int(get('--jobs', 4))
    prompt_file = get('--prompt-file')
    if not base or not key:
        print("缺少 --api-base/--key（或环境变量 PROOFREAD_BASE_URL / PROOFREAD_API_KEY）。")
        sys.exit(2)

    if prompt_file:
        sys_prompt = Path(prompt_file).read_text(encoding='utf-8')
        print(f"使用外部 Prompt: {prompt_file}")
    else:
        sys_prompt = DEFAULT_PROMPT
        print("未指定 --prompt-file，使用内置通用 Prompt（推荐改用领域版）")

    terms_path = get('--terms')
    terms = []
    if terms_path and Path(terms_path).exists():
        terms = [ln for ln in Path(terms_path).read_text(encoding='utf-8').splitlines()
                 if ln.strip() and not ln.startswith('#')]

    cues = parse_srt(src)
    batches = [cues[i:i + batch] for i in range(0, len(cues), batch)]

    def do(bi_batch):
        bi, b = bi_batch
        listing = '\n'.join(f"{j}. {c['text']}" for j, c in enumerate(b))
        user = (f"术语表（参考，格式 误写=>正写）：\n" + '\n'.join(terms[:80]) +
                f"\n\n待校对句子（共 {len(b)} 句）：\n{listing}\n\n只输出 JSON 数组。")
        try:
            raw = call_llm([{'role': 'system', 'content': sys_prompt},
                            {'role': 'user', 'content': user}], key, base, model)
            return bi, extract_json(raw)
        except Exception as e:
            print(f"  批次 {bi} 失败: {e}")
            return bi, []

    results = {}
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for bi, items in ex.map(do, list(enumerate(batches))):
            results[bi] = items

    term_pairs = [(ln.split('=>')[0].strip(), ln.split('=>')[1].strip())
                  for ln in terms if '=>' in ln]
    rows, n_changed = [], 0
    for bi, b in enumerate(batches):
        got = {x.get('i'): x for x in results.get(bi, []) if isinstance(x, dict)}
        for j, c in enumerate(b):
            x = got.get(j) or {}
            new = (x.get('text') or c['text']).strip()
            changed = bool(x.get('changed')) and new != c['text']
            hit = any(good and good in new and good not in c['text'] for _, good in term_pairs)
            if changed:
                n_changed += 1
            clean = lambda v: re.sub(r'[\t\r\n]+', ' ', str(v or '')).strip()
            rows.append((c['start'], clean(c['text']), clean(new), changed,
                         float(x.get('confidence') or 0.0), clean(x.get('reason')), hit))

    with open(out, 'w', encoding='utf-8') as f:
        f.write("起秒\t原句\t建议句\t改动\t置信度\t依据\t命中术语表\n")
        for st, old, new, ch, conf, why, hit in rows:
            f.write(f"{st:.2f}\t{old}\t{new}\t{'是' if ch else '否'}\t{conf:.2f}\t{why}\t{'是' if hit else '否'}\n")
    print(f"校对建议 -> {out}；共 {len(rows)} 句，建议改动 {n_changed} 句")
    print("⚠️  请人工审查 TSV 后再 apply，不要直接合入。")


def cmd_apply(a):
    src, tsv, dst = a[0], a[1], a[2]
    args = a[3:]
    min_conf = float(args[args.index('--min-conf') + 1]) if '--min-conf' in args else 0.9
    only_terms = '--only-terms' in args
    fixes = {}
    with open(tsv, encoding='utf-8') as f:
        next(f, None)
        for ln in f:
            p = ln.rstrip('\n').split('\t')
            if len(p) < 7:
                continue
            st, old, new, ch, conf, hit = p[0], p[1], p[2], p[3], float(p[4]), p[6]
            if ch != '是' or conf < min_conf:
                continue
            if only_terms and hit != '是':
                continue
            fixes[round(float(st), 1)] = new
    cues = parse_srt(src)
    n = 0
    for c in cues:
        k = round(c['start'], 1)
        if k in fixes and fixes[k] != c['text']:
            c['text'] = fixes[k]
            n += 1
    Path(dst).write_text('\n'.join(
        f"{i}\n{fmt(c['start'])} --> {fmt(c['end'])}\n{c['text']}\n"
        for i, c in enumerate(cues, 1)), encoding='utf-8')
    print(f"应用 {n} 条（置信度>={min_conf}{'，仅术语命中' if only_terms else ''}）-> {dst}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, rest = sys.argv[1], sys.argv[2:]
    {'review': cmd_review, 'apply': cmd_apply}[cmd](rest)


if __name__ == '__main__':
    main()
