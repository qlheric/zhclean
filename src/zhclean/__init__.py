"""zhclean —— 中文脏数据净化器（给 agent 的中文脏活基础设施）。

F: 包入口，导出核心符号与版本
R: 被 cli.py / tests 导入
A: import zhclean
S: 不写业务逻辑，只做导出与版本声明
"""

from .tools.normalize import normalize, normalize_with_confidence

__version__ = "0.1.0"

__all__ = ["__version__", "normalize", "normalize_with_confidence"]
