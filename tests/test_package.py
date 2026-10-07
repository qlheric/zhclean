"""骨架冒烟测试：包可导入、版本声明正确。

F: 验证骨架装得起来，供每个 TASK 的判据基线使用
R: src/zhclean/__init__.py
A: pytest tests/ -q
S: 只测骨架不测清洗逻辑
"""

import zhclean


def test_package_imports():
    assert zhclean.__version__ == "0.1.0"
