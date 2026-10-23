#!/usr/bin/env python3
"""修正剪映草稿字幕样式：字号、垂直位置、阴影。

同步写 draft_content.json 与 draft_info.json 两个镜像——只改一边会导致样式回弹。
剪映打开过的草稿该文件会加密（不是以 { 开头），此时跳过并提示重建草稿。

用法:
  python3 fix_text_style.py <草稿目录> [--font-size 5] [--y -0.7] [--no-shadow]

  --font-size  字号（canvas 高度百分比；15 过大、8 偏大，课程字幕实测 5 合适）
  --y          垂直位置：clip.transform 的 y 为正 = 向上，底部字幕区用负值（默认 -0.7）
  --no-shadow  只改字号/位置，不加阴影
"""
import json
import sys
from pathlib import Path

# 剪映阴影（pyJianYingDraft TextShadow 导出格式）
CONTENT_SHADOW = {
    "diffuse": 15.0 / 100.0 / 6,   # 剪映内部映射：扩散 15
    "alpha": 1.0,
    "distance": 5.0,
    "content": {"solid": {"color": [0.0, 0.0, 0.0]}},
    "angle": -45.0,
}
TOP_SHADOW = {
    "has_shadow": True,
    "shadow_alpha": 0.8,
    "shadow_angle": -45.0,
    "shadow_color": "#000000FF",
    "shadow_distance": 8.0,
    "shadow_smoothing": 1.0,
}


def get_arg(key, default):
    args = sys.argv[2:]
    if key not in args:
        return default
    i = args.index(key) + 1
    if i >= len(sys.argv) - 1:
        sys.exit(f"✗ 参数 {key} 后面缺少取值")
    return sys.argv[i]


def apply_style(draft_dir, font_size=5.0, pos_y=-0.7, shadow=True):
    """直接改草稿 JSON；返回实际写入的镜像文件数（0 = 草稿不存在或已加密）。"""
    draft_dir = Path(draft_dir)
    changed = 0
    for fname in ("draft_content.json", "draft_info.json"):
        p = draft_dir / fname
        if not p.exists():
            continue
        raw = p.read_text(encoding='utf-8', errors='ignore')
        if not raw.lstrip().startswith('{'):
            print(f"  {fname}: 已加密（剪映打开过）— 跳过，改样式需删草稿重建")
            continue
        d = json.loads(raw)
        n_mat = n_seg = 0
        for t in d.get("materials", {}).get("texts", []):
            t["font_size"] = font_size
            if shadow:
                t.update(TOP_SHADOW)
                t["check_flag"] = int(t.get("check_flag", 7)) | 32   # +32 = 阴影生效位
            try:
                inner = json.loads(t.get("content", "{}"))
                for s in inner.get("styles", []):
                    s["size"] = font_size
                    if shadow:
                        s["shadows"] = [dict(CONTENT_SHADOW)]
                t["content"] = json.dumps(inner, ensure_ascii=False)
            except (ValueError, TypeError):
                pass
            n_mat += 1
        for tr in d.get("tracks", []):
            if tr.get("type") != "text":
                continue
            for seg in tr.get("segments", []):
                clip = seg.setdefault("clip", {"alpha": 1, "rotation": 0,
                                               "scale": {"x": 1, "y": 1},
                                               "transform": {"x": 0, "y": 0},
                                               "flip": {"horizontal": False, "vertical": False}})
                tf = clip.setdefault("transform", {"x": 0, "y": 0})
                tf["y"] = pos_y
                n_seg += 1
        p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        changed += 1
        print(f"  {fname}: 文本材料={n_mat} 字幕段={n_seg} size={font_size:g} y={pos_y:g} "
              f"shadow={'on' if shadow else 'off'}")
    return changed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    draft_dir = Path(sys.argv[1])
    font_size = float(get_arg('--font-size', 5.0))
    pos_y = float(get_arg('--y', -0.7))
    shadow = '--no-shadow' not in sys.argv
    if not apply_style(draft_dir, font_size, pos_y, shadow):
        sys.exit(f"✗ {draft_dir} 下没有可修改的 draft_*.json（草稿不存在或已加密）")
    print(f"完成 -> {draft_dir}（改样式后需重启剪映才能看到）")


if __name__ == '__main__':
    main()
