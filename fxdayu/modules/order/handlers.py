# encoding: utf-8

import copy
from collections import OrderedDict

import pandas as pd

from fxdayu.const import OrderStatus
from fxdayu.context import ContextMixin
from fxdayu.engine.handler import HandlerCompose, Handler
from fxdayu.event import EVENTS, OrderEvent, CancelEvent
from fxdayu.models.data import Security, ExecutionData
from fxdayu.models.order import OrderStatusData, OrderReq, CancelReq
from fxdayu.models.proxy import OrderProxy, OrderSenderMixin
from fxdayu.modules.order.style import *
from fxdayu.utils.api_support import api_method


class OrderStatusHandler(HandlerCompose, ContextMixin, OrderSenderMixin):
    def __init__(self, engine):
        super(OrderStatusHandler, self).__init__(engine)
        ContextMixin.__init__(self)
        OrderSenderMixin.__init__(self)
        self._execution_dao = None
        self._persistence = None
        self._adapter = None
        self._orders_dao = None
        self._order_status_dao = None
        self._open_orders = {}
        self._order_proxies = {}
        self._client_ord_id = 0
        self._handlers["on_order"] = Handler(self.on_order, EVENTS.ORDER, topic="", priority=0)
        self._handlers["on_execution"] = Handler(self.on_execution, EVENTS.EXECUTION, topic=".", priority=-100)
        self._handlers["on_order_status"] = Handler(self.on_order_status, EVENTS.ORD_STATUS, topic=".", priority=-100)

    def init(self):
        self._persistence = self.environment["persistence"]
        self._orders_dao = self._persistence.get_dao(OrderReq)
        self._order_status_dao = self._persistence.get_dao(OrderStatusData)
        self._execution_dao = self._persistence.get_dao(ExecutionData)
        self._adapter = OrderReqAdapter(self.context, self.environment)

    @property
    def next_ord_id(self):
        self._client_ord_id += 1
        return self._client_ord_id

    def _get_order(self, order):
        gateway, account, ord_id = order.split(".")
        return self._orders_dao.find(gateway, account, ord_id)

    def _get_order_status(self, order):
        gateway, account, ord_id = order.split(".")
        return self._order_status_dao.find(gateway, account, ord_id)

    def on_order(self, event, kwargs=None):
        """
        Args:
            event(fxdayu.event.OrderEvent): order event
            kwargs(dict): other optional parameters

        Returns:

        """
        order = event.data
        if order.clOrdID:
            status = OrderStatusData()
            status.exchange = order.exchange
            status.symbol = order.symbol
            status.clOrdID = order.clOrdID
            status.action = order.action
            status.side = order.side
            status.price = order.price
            status.orderQty = order.orderQty
            status.leavesQty = order.orderQty
            status.ordStatus = OrderStatus.GENERATE.value
            status.gateway = order.gateway
            status.account = order.account
            status.orderTime = self.context.current_time
            self._order_status_dao.insert(status)
            self._orders_dao.insert(order)
            order_proxy = OrderProxy(order, status, self)
            self._order_proxies[order.gClOrdID] = order_proxy
            if order.symbol not in self._open_orders:
                self._open_orders[order.symbol] = OrderedDict()
            self._open_orders[order.symbol][order.gClOrdID] = order_proxy
        else:
            pass  # TODO warning Order send failed

    def on_execution(self, event, kwargs=None):
        """

        Args:
            event(fxdayu.event.ExecutionEvent):
            kwargs:

        Returns:

        """
        execution = event.data
        self._execution_dao.insert(execution)

    def on_order_status(self, event, kwargs=None):
        """

        Args:
            event(fxdayu.event.OrderStatusEvent):
            kwargs:

        Returns:
            None
        """
        status_new = event.data
        self._order_status_dao.insert(status_new)
        self._order_proxies[status_new.gClOrdID]._order_stat = status_new
        # TODO patch of order proxies
        if status_new.ordStatus == OrderStatus.ALLTRADED.value or status_new.ordStatus == OrderStatus.CANCELLED.value:
            try:
                self._open_orders[status_new.symbol].pop(status_new.gClOrdID, None)
            except KeyError:
                pass

    def get_order_status(self, order):
        """

        Args:
            order:

        Returns:
            fxdayu.models.order.OrderStatusData
        """

        return self._get_order_status(order)

    @api_method
    def get_order(self, order_id):
        return self._order_proxies.get(order_id, None)

    @api_method
    def get_open_orders(self, security):
        if isinstance(security, Security):
            security = security.localSymbol
        if security is None:
            return self._open_orders
        elif security in self._open_orders:
            return self._open_orders[security]
        else:
            return OrderedDict()

    def _make_order_req(self, security, amount, style):
        order = self._adapter.parse(security, amount, style)
        if order:
            order.clOrdID = str(self.next_ord_id)
            return order

    def _miss_security(self):
        pass  # TODO warning

    @api_method
    def send_order(self, order):
        event = OrderEvent(order)
        self.engine.put(event)

    def _get_base_data(self, data, index="time", method="df"):
        if method == "df":
            if isinstance(data, dict):
                df = pd.DataFrame([item.to_dict() for item in data.values()])
            else:
                df = pd.DataFrame([item.to_dict() for item in data])
            if not df.empty:
                df = df.set_index(index, drop=False).sort_index()
            return df
        elif method == "raw":
            return copy.deepcopy(data)

    def get_status(self, method="df"):
        return self._get_base_data(self._order_status_dao.find_all(), index="orderTime", method=method)

    def get_orders(self, method="df"):
        return self._get_base_data(self._orders_dao.find_all(), index="transactTime", method=method)

    def get_executions(self, method="df"):
        return self._get_base_data(self._execution_dao.find_all(), index="time", method=method)

    @api_method
    def order(self, security, amount, style=None, limit_price=None, stop_price=None):
        """
        发送所指定手数amount的给定证券security的订单。从所使用的style参数推断订单类型。
        如果仅传入security和amount参数，则将订单视为为市价订单。

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            amount(int): 交易手数，整数。正值意味着买入，负值意味着卖出。
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)
            stop_price: deprecated, 向后兼容
            limit_price: deprecated, 向后兼容
        Returns:
            str: 订单ID
        """
        if not style:
            if limit_price and stop_price:
                style = StopLimitOrder(limit_price, stop_price)
            elif limit_price:
                style = LimitOrder(limit_price)
            elif stop_price:
                style = StopOrder(stop_price)
            else:
                style = MarketOrder()
        order = self._make_order_req(security, amount, style)
        if order:
            self.send_order(order)
            return order.gClOrdID
        else:
            self._miss_security()

    @api_method
    def order_target(self, security, amount, style=None):
        """

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            amount(int): 目标手数，整数。正值意味多头头寸，负值意味着空头头寸。（股票中若传入负值将报错）
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)

        Returns:
            str: 订单ID
        """
        if not isinstance(security, Security):
            security = self.environment.symbol(security)
        amount = int(amount)
        if security:
            position = self.context.portfolio.positions.get(security.symbol)
            if position:
                volume = position.volume
            else:
                volume = 0
            delta = amount - volume
            if delta != 0:
                return self.order(security, delta, style=style)
            else:
                return None
        else:
            self._miss_security()

    def _value2shares(self, security, value):
        # TODO 完成实时的current和history遍写
        point = self.data.current(security.symbol).close
        point_value = security.point_value if hasattr(security, "point_value") else 1
        return int(value / point / point_value)

    def _percent2shares(self, security, percent):
        value = self.context.portfolio.portfolio_value * percent
        return self._value2shares(security, value)

    @api_method
    def order_value(self, security, value, style=None):
        """
        根据给定价值value而不是给定的交易手数下单。传入负值代表卖出。交易手数总是被截断为整数手。

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            value(float): 证券的价值，据此计算交易手数，并截断为整数手。正值意味着买入，负值意味着卖出。
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)
        Examples:
            发送价值达￥10000的股票代码000002所代表股票的订单：order_value(symbol('000002'),10000)
            如果000002的价格是每股15元，这将购买6手(600股)，小数部分手数将被截断（不考虑滑点和交易成本）。

        Returns:
            str: 订单ID
        """

        if not isinstance(security, Security):
            security = self.environment.symbol(security)
        if security:
            return self.order(security, self._value2shares(security, value), style=style)
        else:
            self._miss_security()

    @api_method
    def order_target_value(self, security, value, style=None):
        """
        根据目标头寸价值value计算目标头寸手数，并截取整数手。正值意味多头头寸，负值意味着空头头寸。
        然后按order_target中的方式下达订单。

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            value(float): 目标头寸价值，据此计算目标头寸手数，并截断为整数手。正值意味多头头寸，负值意味着空头头寸。
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)

        Returns:
            str: 订单ID
        """
        if not isinstance(security, Security):
            security = self.environment.symbol(security)
        if security:
            return self.order_target(security, self._value2shares(security, value), style=style)
        else:
            self._miss_security()

    @api_method
    def order_percent(self, security, percent, style=None):
        """
        发送对应于当前资产净值的给定百分比（即头寸总市值和期末现金余额的总和）的订单。传入负百分比值表示卖出。订单总是被截断为全股。百分比必须以小数表示（0.50表示50％）。

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            percent(float): 百分比。正值意味着买入，负值意味着卖出。
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)

        Examples:
            order_percent(symbol('000002'),.5)将买入价值当前投资组合50%的股票000002。
            如果000002是15元/股，投资组合价值是100000元，这将购买33手（不考虑滑点和交易成本）。

        Returns:
            str: 订单ID
        """
        if not isinstance(security, Security):
            security = self.environment.symbol(security)
        if security:
            return self.order(security, self._percent2shares(security, percent), style=style)
        else:
            self._miss_security()

    @api_method
    def order_target_percent(self, security, percent, style=None):
        """
        根据目标头寸占当前账户净值百分比数计算目标头寸手数，并截取整数手。正值意味多头头寸，负值意味着空头头寸。
        然后按order_target中的方式下达订单。

        Args:
            security(str | fxdayu.models.data.Security): 证券，可以是证券代码或者Security对象。
            percent(float): 目标头寸价值占当前账户净值百分比数。正值意味多头头寸，负值意味着空头头寸。
            style(fxdayu.modules.order.style.OrderStyle): (可选)指定订单样式，默认值为市价订单。可用的订单样式有：
                style = MarketOrder(exchange)
                style = StopOrder(stop_price, exchange)
                style = LimitOrder(limit_price, exchange)
                style = StopLimitOrder(limit_price=price1, stop_price=price2, exchange)

        Returns:
            str: 订单ID
        """
        if not isinstance(security, Security):
            security = self.environment.symbol(security)
        if security:
            return self.order_target(security, self._percent2shares(security, percent), style=style)
        else:
            self._miss_security()

    @api_method
    def cancel_order(self, order):
        if isinstance(order, OrderReq):
            data = CancelReq(order.clOrdID)
        else:
            data = CancelReq(order)
        event = CancelEvent(data)
        self.engine.put(event)

    def link_context(self):
        # find order
        self.environment["get_order"] = self.get_order
        self.environment["get_open_orders"] = self.get_open_orders

        # place order
        self.environment["order"] = self.order
        self.environment["order_target"] = self.order_target
        self.environment["order_value"] = self.order_value
        self.environment["order_target_value"] = self.order_target_value
        self.environment["order_percent"] = self.order_percent
        self.environment["order_target_percent"] = self.order_target_percent
        self.environment["cancel_order"] = self.cancel_order
        self.environment["get_order_status"] = self.get_order_status

        # style
        self.environment["MarketOrder"] = MarketOrder
        self.environment["StopOrder"] = MarketOrder
        self.environment["LimitOrder"] = LimitOrder
        self.environment["StopLimitOrder"] = StopLimitOrder

        # private
        self.environment.set_private("make_order_req", self._make_order_req)
