"""normalize 工具：字段类型 + 脏值 → 规范值 + 置信度（Tool Design #3 件功夫）。

F: 规则打底 80% 确定性清洗；schema 显式；置信度必填
R: rules/*（六类规则词典）
A: 被 loop.py（act 首选）调用
S: 置信度必填；规则失败可回退 LLM，但结果结构不变
"""
