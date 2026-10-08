"""跨平台小兼容件（TASK-015：把 cli 里的编码修复抽成公共件，四个 demo 入口统一用）。

F: 在真实进程里把 stdout/stderr 设成 utf-8，避免 Windows 控制台默认 cp936 写坏汉字
R: cli.main 与 loop / tools.audit / tools.dedupe 的 __main__（凡直接打中文的入口）
A: `from ._compat import utf8_stdio`（tools 下用 `from .._compat import utf8_stdio`）
S: 只碰编码，不改任何业务口径；只对「真实流」生效，注入的测试流天然跳过

为什么放在这里而不是各入口各写一份：TASK-014 把修复塞进 cli.main 时只覆盖了 cli 一个入口，
loop / audit / dedupe 的 `python -m` 直跑仍会 GBK 乱码（RESULT-014 §5-6）。公共件后
四个入口一行调用即可，新增入口也不会再漏。
"""

from __future__ import annotations

import io
import sys


def utf8_stdio() -> None:
    """真实进程里把 stdout/stderr 设成 utf-8。

    注入的 StringIO（测试）不是 TextIOWrapper，`isinstance` 直接跳过，天然安全 ——
    所以测试里传 `stdout=StringIO()` 不会触发 reconfigure（StringIO 没有该方法）。
    """
    for s in (sys.stdout, sys.stderr):
        if isinstance(s, io.TextIOWrapper):
            s.reconfigure(encoding="utf-8")
