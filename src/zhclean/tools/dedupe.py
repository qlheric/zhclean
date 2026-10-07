"""dedupe 工具：hash 精确去重 + rapidfuzz 语义去重。

F: 两级去重：精确（hash）+ 语义（rapidfuzz 相似度阈值）
R: tools/normalize.py（先去规范化再去重）
A: 被 cli.py 调用
S: 评测口径 recall≥95%；阈值不得用测试集调参
"""
