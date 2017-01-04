
TICK=0
BAR=1
ORDER=2
FILL=3
LIMIT=4
STOP=5
CANCEL=6
EXIT=999
OPEN_ORDER=1
CLOSE_ORDER=0


class Event(object):
    '''
    This is the base event class
    it implements the __lt__ and __gt__ function
    which compares its own priority and other event's priority
    Other events that extends from this class must set the 'priority' attribution
    '''

    def set_priority(self,p=1):
        self.priority=p

    def __lt__(self, other):
        return self.priority<other.priority

    def __gt__(self, other):
        return self.priority>other.priority

class TickEvent(Event):
    '''
    TickEvent is created when a tick data arrived
    and will be handled by strategy and portfolio handler
    '''

    def __init__(self,ticker,timestamp,ask,bid):
        self.type=TICK
        self.set_priority(1)
        self.ticker=ticker
        self.time=timestamp
        self.ask=ask
        self.bid=bid


class BarEvent(Event):
    '''
    BarEvent is created when a bar data arrived
    and will be handled by strategy and portfolio handler
    '''

    def __init__(self,ticker,timestamp,openPrice,highPrice,lowPrice,closePrice,volume):
        self.type=BAR
        self.set_priority(1)
        self.ticker=ticker
        self.time=timestamp
        self.open=openPrice
        self.high=highPrice
        self.low=lowPrice
        self.close=closePrice
        self.volume=volume

class OrderEvent(Event):
    '''
    OrderEvent is created by a strategy when it wants to open an order and
    will be handled by Simulation or Trade section
    '''

    def __init__(self,timestamp,ticker,action,quantity,price,order_type=ORDER):
        self.type=order_type
        self.time=timestamp
        self.price=price
        self.ticker=ticker
        self.set_priority(0)
        self.action=action
        self.quantity=quantity

class CancelEvent(Event):
    '''
    CancelEvent is created by a strategy when it wants to cancel an limit or stop order
    and it will be handled by Simulation or Trade section
    '''

    def __init__(self,**conditions):
        self.type=CANCEL
        self.set_priority(0)
        self.conditions=conditions


class FillEvent(Event):
    '''
    FillEvent is created by Simulation section
    when it receives an OrderEvent or by Trade section
    when it receives signals from the internet
    and it will be handled by Portfolio handler to
    update portfolio information
    '''

    def __init__(self,timestamp,ticker,action,quantity,price,commission=0,lever=1,deposit_rate=1):
        self.type=FILL
        self.time=timestamp
        self.ticker=ticker
        self.set_priority(0)
        self.action=action
        self.quantity=quantity
        self.price=price
        self.commission=commission
        self.lever=lever
        self.deposit_rate=deposit_rate

class ExitEvent(Event):

    def __init__(self):
        self.type=EXIT
        self.set_priority(999)



