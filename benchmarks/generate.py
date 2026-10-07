"""程序化扰动生成脏数据（benchmark 先行，可核是命门）。

F: 干净集 → 扰动（加空格/错别字/简称/重复/格式乱）→ 脏集；ground truth = 扰动前原值
R: src/zhclean/tools/normalize.py（评测对象）
A: python benchmarks/generate.py
S: 留出集独立划分；规则库不得针对测试扰动模式调参
"""
