"""audit 工具：清洗报告 + dry-run 预览 + 可回滚。

F: 输出清洗报告（改了什么/为什么/置信度）；dry-run 不落盘；支持回滚
R: tools/dedupe.py、tools/normalize.py（读取清洗结果）
A: 被 cli.py 调用
S: 报告数字必须可复现（同输入同输出）
"""
