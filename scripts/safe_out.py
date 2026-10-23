#!/usr/bin/env python3
"""落盘安全闸：所有脚本共用的输出保护。

三条规则：
 1. 输出路径不能与输入相同（否则原地覆盖原稿，且不可回滚）。
 2. 输出文件已存在时拒绝写入，除非显式加 --force。
 3. 拒绝时说清下一步怎么做，而不是只丢一句报错。
"""
import os
import sys
from pathlib import Path


def guard_output(out, inp=None, force_flag='--force'):
    out_p = Path(out)
    if inp is not None and out_p.exists():
        try:
            if os.path.samefile(out_p, Path(inp)):
                sys.exit(f"✗ 输出路径与输入是同一个文件，会覆盖原稿：{out_p}\n"
                         f"  请换个输出文件名。")
        except OSError:
            pass
    if out_p.exists() and force_flag not in sys.argv:
        sys.exit(f"✗ 输出文件已存在，拒绝覆盖：{out_p}\n"
                 f"  确认覆盖请加 {force_flag}；或换个输出文件名。")
