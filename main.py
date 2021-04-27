from ib_insync import *
import ta
import numpy as np
import pandas as pd
from screeners import StockwitsScreener, TradingviewScreener
from datetime import datetime


class Bot:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=1)
        self.ib.sleep(1)

    """ MAIN METHODS """

    def create_stock(self, stock):
        contract = Stock(stock, 'SMART', 'USD')
        return contract

    def buy_order(self, strategy, stock, ordertype, amount, limitPrice, profitPercent, trailPercent):
        bracket = self.__BracketOrder(self.ib.client.getReqId(), self.ib.client.getReqId(), self.ib.client.getReqId(),
                                      ordertype, "BUY", amount, limitPrice, profitPercent, trailPercent)
        for o in bracket:
            self.ib.placeOrder(stock, o)

        self.log_trade(strategy, stock, limitPrice, amount)

    """ ORDER METHODS """

    def __BracketOrder(self, parentOrderId, childOrderId1, childOrderId2, ordertype, action, quantity, limitPrice,
                       profitPercent, trailingPercent):
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = ordertype
        parent.totalQuantity = quantity
        parent.lmtPrice = round(limitPrice, 2)
        parent.transmit = False

        if profitPercent != '':
            takeProfit = Order()
            takeProfit.orderId = childOrderId1
            takeProfit.action = "SELL" if action == "BUY" else "BUY"
            takeProfit.orderType = 'LMT'
            takeProfit.totalQuantity = quantity
            takeProfit.lmtPrice = round((limitPrice * (100 + profitPercent)) / 100, 2)
            takeProfit.parentId = parentOrderId
            takeProfit.tif = 'GTC'
            takeProfit.transmit = False

        stopLoss = Order()
        stopLoss.orderId = childOrderId2
        stopLoss.action = "SELL" if action == "BUY" else "BUY"
        stopLoss.orderType = "TRAIL"
        stopLoss.trailingPercent = trailingPercent
        stopLoss.trailStopPrice = round(limitPrice - limitPrice * (trailingPercent / 100), 2)
        stopLoss.totalQuantity = quantity
        stopLoss.parentId = parentOrderId
        stopLoss.tif = 'GTC'
        stopLoss.transmit = True

        if profitPercent:
            bracketOrder = [parent, takeProfit, stopLoss]
        else:
            bracketOrder = [parent, stopLoss]
        return bracketOrder

    """ RETRIEVE DATA METHODS """

    def realtime_price(self, stock):
        bars = self.ib.reqRealTimeBars(stock, 5, 'TRADES', False)
        bars.updateEvent += self.__onScanData

    def __onScanData(self, bars, hasNewBar):
        if hasNewBar:
            last_bar = bars[-1]
            print(last_bar.close)

    def historical_data(self, stock, duration, barsize, what):
        bars = self.ib.reqHistoricalData(
            stock, endDateTime='', durationStr=duration,
            barSizeSetting=barsize, whatToShow=what, useRTH=True)
        for bar in bars:
            print(bar.close)

    """ REPORT METHODS """

    def log_trade(self, strategy, stock, price, amount):
        dic = {}
        index=0
        dic[index] = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'strategy': strategy,
            'stock': stock.symbol,
            'action': 'BOT',
            'price': price,
            'amount': amount,
            'commission': None,
            'profit': None,
        }

        logdata = pd.DataFrame(dic).T
        df = pd.read_pickle('log_trade.pkl')
        df = df.append(logdata, ignore_index=True)
        df.to_pickle('log_trade.pkl')

    def logdata(self):
        fills = self.ib.fills()
        dic = {}
        index = 0
        for fill in fills:
            index += 1
            dic[index] = {
                'date': fill.time.strftime('%Y-%m-%d'),
                'strategy': 'tbd',
                'stock': fill.contract.symbol,
                'action': fill.execution.side,
                'price': fill.execution.avgPrice,
                'amount': fill.execution.shares,
                'commission': fill.commissionReport.commission,
                'profit': fill.commissionReport.realizedPNL,
            }
        logdata = pd.DataFrame(dic).T
        # map todays fills to the trading strategy logged for respective trade (either intraday or older)
        df_strategies = pd.read_pickle('log_trade.pkl')
        df_logdata = pd.read_csv('transactions_log.csv')

        for index, row in logdata.iterrows():
            stock = row.stock
            amount = row.amount
            action = row.action

            # locate trades - case stock bought:
            if action == 'BOT':
                num_strategies = len(df_strategies.loc[(df_strategies.stock == stock) & (df_strategies.amount == amount)])
                # in case ticker appeared on multiple screeners / to be determined manually
                if num_strategies > 1:
                    print(f'{stock} has ambigous strategy log')
                    continue
                index = df_strategies.loc[(df_strategies.stock == stock) & (df_strategies.amount == amount)].index.to_list()
                strategy = df_strategies.loc[index].strategy.to_list()
                row.strategy = strategy[0]

            # locate trades - case stock sold:
            else:
                # check if it was an older trade
                try:
                    # check for an unsold buy order
                    num_strategies = len(df_logdata.loc[(df_logdata.stock == stock) & (df_logdata.amount == amount) & (
                                    df_logdata.action == 'BOT')])
                    # in case ticker appeared on multiple screeners
                    if num_strategies > 1:
                        # attribute to last open oder
                        index = df_logdata.loc[(df_logdata.stock == stock) & (df_logdata.amount == amount) & (
                                    df_logdata.action == 'BOT')][-1].index.to_list()
                    else:
                        index = df_logdata.loc[
                        (df_logdata.stock == stock) & (df_logdata.amount == amount) & (
                                    df_logdata.action == 'BOT')].index.to_list()
                    strategy = df_logdata.loc[index].strategy.to_list()
                    row.strategy = strategy[0]

                # else intraday trade
                except:
                    num_strategies = len(
                        df_strategies.loc[(df_strategies.stock == stock) & (df_strategies.amount == amount)])
                    # in case ticker appeared on multiple screeners > attribute sale to first buy

                    if num_strategies > 1:
                        index = df_strategies.loc[
                            (df_strategies.stock == stock) & (df_strategies.amount == amount)][0].index.to_list()

                    elif num_strategies == 1:
                        index = df_strategies.loc[
                            (df_strategies.stock == stock) & (df_strategies.amount == amount)].index.to_list()

                    strategy = df_strategies.loc[index].strategy.to_list()
                    row.strategy = strategy[0]

        # update logdata file
        df_logdata = df_logdata.append(logdata, ignore_index=True)
        df_logdata = df_logdata.drop_duplicates()
        df_logdata.to_csv('transactions_log.csv')
        # reset trade_log file for new trading day
        df_strategies = df_strategies[0:0]
        df_strategies.to_pickle('log_trade.pkl')


""" TRADINGBOT CHILD STRATEGIES """

class TriangleTrade(Bot):
    strategy = 'TriangleTrade'
    barsize =  '1 min'
    smaperiod = 50
    ordertype = 'MKT'
    profitPercent=5
    trailPercent=2

    def __init__(self, stock, budget):
                super(TriangleTrade, self).__init__()
                self.stock = stock
                self.budget = budget

    def run(self):
        bars = self.ib.reqHistoricalData(self.stock,
                endDateTime = '',
                durationStr = '2 D',
                barSizeSetting = self.barsize,
                whatToShow = 'TRADES',
                useRTH = True,
                formatDate = 1,
                keepUpToDate = True)
        bars.updateEvent += self.__onBarUpdate

    def __onBarUpdate(self, bars, hasNewBar):
        if hasNewBar:
            # get latest values in last_bar
            last_bar = bars[-1]
            # set last params to compare against
            closes = [bar.close for bar in bars[:-2]]
            lastLow = bars[-2].low
            lastHigh = bars[-2].high
            close_array = pd.Series(np.asarray(closes))
            sma = ta.trend.sma_indicator(close=close_array, window=self.smaperiod, fillna=True)
            # print(sma[len(sma) - 1])

            # check for triangle break
            if last_bar.close > lastHigh \
                    and last_bar.low > lastLow \
                    and last_bar.close > sma[len(sma) - 1]:
                print('triangle formation broken')
                amount = int(self.budget / last_bar.close)
                self.buy_order(self.strategy, self.stock, self.ordertype, amount,
                               last_bar.close, self.profitPercent, self.trailPercent)

class NewPenny(Bot):
    strategy = 'newPennystock'
    ordertype = 'LMT'
    budget = 100
    profitPercent = ''

    def __init__(self, trailPercent=10):
        super(NewPenny, self).__init__()
        self.trailPercent=trailPercent

    def run(self):
        screener = StockwitsScreener()
        tickers = screener.run()
        if tickers is not None:
            for ticker in tickers:
                stock = self.create_stock(ticker)
                [quote] = self.ib.reqTickers(stock)
                quote = quote.marketPrice()
                amount = int(self.budget / quote)
                self.buy_order(self.strategy,stock, self.ordertype, amount, quote, self.profitPercent, self.trailPercent)


class PennyFilter(Bot):
    ordertype = 'LMT'
    budget_perstock = 10
    profitPercent = ''

    def __init__(self, strategy, trailPercent=10):
        super(PennyFilter, self).__init__()
        self.strategy = strategy
        self.screener = pennyscreeners_dic[strategy]
        self.trailPercent = trailPercent

    def run(self):
        screener = TradingviewScreener(self.screener)
        tickers = screener.run()
        for ticker in tickers:
            try:
                stock = self.create_stock(ticker)
                [quote] = self.ib.reqTickers(stock)
                quote = quote.marketPrice()
                dps = str(self.ib.reqContractDetails(stock)[0].minTick + 1)[::-1].find('.') - 1
                orderPrice = round(quote + self.ib.reqContractDetails(stock)[0].minTick * 2, dps)
                amount = int(self.budget_perstock / orderPrice)
                if amount == 0:
                    amount = 1
                self.buy_order(self.strategy,stock, self.ordertype, amount, orderPrice, self.profitPercent, self.trailPercent)
            except:
                continue

pennyscreeners_dic = {
    '2xVolumePenny': '2vol',
    '2xVolumePenny&Osc': '2vol_wOscillators',
    'VWAP&LAST>EMA20': 'vwap',
    'VWAP&LAST>EMA20&Osc': 'vwap_wOscillators',
    'volumeleaders': 'Volume leaders',
    '52high':'52high',
    'oversold':'oversold',
    'volume&hull':'volume&hull',
    'bolinger': 'bolinger',
}


""" let function run during trading hours """

def runbot():
    bot = Bot()

    # run trading strategies
    for strategy in pennyscreeners_dic:
        pennyFilter = PennyFilter(strategy)
        pennyFilter.run()

    # run IB connection once at market open and sleep until market close
    bot.ib.sleep(60*60*9)

    # log trades and disconnect from IB
    bot.logdata()
    bot.ib.disconnect()

runbot()


