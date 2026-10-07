"""规则库包入口：六类词典注册与分发（核心资产）。

F: 规则库注册与按字段类型分发
R: rules/person、address、phone、company、amount、date
A: 被 tools/normalize.py 导入
S: 词典加载失败必须显式报错，不得静默降级为空库
"""
