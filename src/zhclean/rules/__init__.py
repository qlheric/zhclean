"""规则库包入口：按字段类型分发到各字段的规则（核心资产）。

F: 规则库注册与按字段类型分发（未注册字段恒等处理）
R: rules/{person,address,phone,company,amount,date,idcard,email}.py（八类字段已全部注册）
A: 被 tools/normalize.py 导入
S: 词典加载失败必须显式报错，不得静默降级为空库
"""

from __future__ import annotations

from typing import Callable

from .address import normalize_address
from .amount import normalize_amount
from .common import CONF_NONE
from .company import normalize_company
from .date import normalize_date
from .email import normalize_email
from .idcard import normalize_idcard
from .person import normalize_person
from .phone import normalize_phone

# 注册表：field → handler(value) -> (规范值, 置信度)
DISPATCH: dict[str, Callable[[str], tuple[str, float]]] = {
    "person": normalize_person,
    "address": normalize_address,
    "phone": normalize_phone,
    "company": normalize_company,
    "amount": normalize_amount,
    "date": normalize_date,
    "idcard": normalize_idcard,
    "email": normalize_email,
}


def normalize_field(value: str, field: str) -> tuple[str, float]:
    """按字段分发；未注册的字段恒等返回（低置信，不猜）。"""
    handler = DISPATCH.get(field)
    if handler is None:
        return value, CONF_NONE
    return handler(value)
