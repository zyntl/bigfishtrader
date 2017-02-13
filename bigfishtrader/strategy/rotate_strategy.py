from bigfishtrader.strategy.base import Strategy


class RotateStrategy(Strategy):

    def initialize(self):
        self.ticker = self.context.tickers[0]
        self.context.target = []
        self.time_limit(self.week_end, isoweekday=5, priority=101)
        self.period = 10

    def handle_data(self):
        for key, value in self.portfolio.security.items():
            if key not in self.context.target:
                if self.data.can_trade(key):
                    self.close_position(key, value)

        for ticker in self.context.target:
            if ticker not in self.portfolio.security.keys():
                if self.data.can_trade(ticker):
                    self.open_position(ticker, 1000)

    def week_end(self):
        target = {}
        for ticker in self.context.tickers:
            if not self.data.can_trade(ticker):
                continue

            close = self.data.history(ticker, 'D', length=self.period)['close']
            up = close[-1]/close.min()
            if len(target) < 2:
                target[ticker] = up
                continue

            for key, value in target.copy().items():
                if value > up:
                    target.pop(key)
                    target[ticker] = up
                    break

        self.context.target = list(target.keys())
        print self.context.target


if __name__ == '__main__':
    from bigfishtrader.trader import Trader
    from bigfishtrader.router.exchange import PracticeExchange
    import pandas as pd
    from datetime import datetime

    p = Trader().initialize(
        ('router', lambda models, **kwargs: PracticeExchange(
            models['event_queue'], models['data'], models['portfolio']
        ), {})
    ).backtest(
        RotateStrategy,
        ['000001', '600016', '600036', '600000', '601166'], 'D',
        start=datetime(2015, 1, 1), ticker_type='HS', period=15
    )

    print pd.DataFrame(
        p.history
    )

    print pd.DataFrame(
        [position.show() for position in p.closed_positions]
    )


