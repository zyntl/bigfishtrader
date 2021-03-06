# encoding: utf-8

from __future__ import unicode_literals
from enum import Enum

EMPTY_STRING = b''
EMPTY_UNICODE = ""
EMPTY_INT = 0
EMPTY_FLOAT = 0.0


class OrderType(Enum):
    MARKET = "市价"
    LIMIT = "限价"
    STOP = "止损"
    FAK = "FAK"
    FOK = "FOK"


class OrderStatus(Enum):
    GENERATE = "已生成"
    TRIGGERED = "已触发"
    NOTTRADED = "未成交"
    PARTTRADED = "部分成交"
    ALLTRADED = "全部成交"
    CANCELLED = "已撤销"
    UNKNOWN = "未知"


class Direction(Enum):
    NONE = "无方向"
    LONG = "多"
    SHORT = "空"
    UNKNOWN = "未知"
    NET = "净"


class OrderSide(Enum):
    BUY = "买"
    SELL = "卖"


class OrderAction(Enum):
    NONE = "无开平"
    OPEN = "开仓"
    CLOSE = "平仓"
    UNKNOWN = "未知"


class GatewayType(Enum):
    CTP = "CTP"
    IB = "IB"
