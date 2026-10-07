"""CLI 入口：子命令与参数解析，分发到 Agent Loop 或工具。

F: CLI 入口（normalize / dedupe / audit 子命令）
R: loop.py（清洗流程）、tools/*（三工具）
A: python -m zhclean.cli
S: 不含清洗逻辑；退出码语义固定（0 成功 / 非 0 失败）
"""
