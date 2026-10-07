"""手写 Agent Loop：observe → think → act 循环（#1 件功夫）。

F: 循环控制：最大步数、停止条件、单条失败恢复、低置信度 HITL
R: tools/normalize.py（act 首选）、llm.py（低置信兜底）
A: 被 cli.py 调用
S: 单条数据失败不得中断整体清洗
"""
