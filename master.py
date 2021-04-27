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
        self.strategy = 'default'

    def create_stock(self, stock):
        contract = Stock(stock, 'SMART', 'USD')
        return contract

    def __onScanData(self, bars, hasNewBar):
        if hasNewBar:
            last_bar = bars[-1]
            print(last_bar.close)

    """ RETRIEVE DATA METHODS """

    def realtime_price(self, stock):
        bars = self.ib.reqRealTimeBars(stock, 5, 'TRADES', False)
        bars.updateEvent += self.__onScanData


    def historical_data(self, stock, duration, barsize, what):
        bars = self.ib.reqHistoricalData(
            stock, endDateTime='', durationStr=duration,
            barSizeSetting=barsize, whatToShow=what, useRTH=True)
        #return bars
        for bar in bars:
            print(bar.close)

    """ ORDER METHODS """

    def __BracketOrder(self, parentOrderId, childOrderId1, childOrderId2, ordertype, action, quantity, limitPrice, profitPercent, trailingPercent):
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = ordertype
        parent.totalQuantity = quantity
        parent.lmtPrice = round(limitPrice*1.05,2)
        parent.transmit = False

        if profitPercent != '':
            takeProfit = Order()
            takeProfit.orderId = childOrderId1
            takeProfit.action = "SELL" if action == "BUY" else "BUY"
            takeProfit.orderType = 'LMT'
            takeProfit.totalQuantity = quantity
            takeProfit.lmtPrice = round((limitPrice * (100+profitPercent))/100,2)
            takeProfit.parentId = parentOrderId
            takeProfit.tif='GTC'
            takeProfit.transmit = False

        stopLoss = Order()
        stopLoss.orderId = childOrderId2
        stopLoss.action = "SELL" if action == "BUY" else "BUY"
        stopLoss.orderType = "TRAIL"
        stopLoss.trailingPercent = trailingPercent
        stopLoss.trailStopPrice = round(limitPrice - limitPrice * (trailingPercent / 100),2)
        stopLoss.totalQuantity = quantity
        stopLoss.parentId = parentOrderId
        stopLoss.tif='GTC'
        stopLoss.transmit = True

        if profitPercent:
            bracketOrder = [parent, takeProfit, stopLoss]
        else:
            bracketOrder = [parent, stopLoss]
        return bracketOrder

    def buy_order(self, stock, ordertype, amount, limitPrice, profitPercent, trailPercent):
        bracket = self.__BracketOrder(self.ib.client.getReqId(), self.ib.client.getReqId(), self.ib.client.getReqId(), ordertype,  "BUY", amount, limitPrice, profitPercent, trailPercent)
        for o in bracket:
            trade = self.ib.placeOrder(stock, o)
            trade.commissionReportEvent += self.__commissionAvailable

    """ REPORT METHODS (auto) """

    def log_trade(self, strategy, stock, price, amount):
        dic = {}
        dic[0] = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'strategy': strategy,
            'stock': stock,
            'action': 'BOT',
            'price': price*1.05,
            'amount': amount,
            'commission': None,
            'profit': None,
        }

        logdata = pd.DataFrame(dic).T
        df = pd.read_csv('log_trade.csv')
        df = df.append(logdata, ignore_index=True)
        df.to_csv('log_trade.csv')

    # def __commissionAvailable(self, trade, fill, commissionReport):
    #     dic = {}
    #     index = 0
    #     dic[index] = {
    #             'date': fill.time.strftime('%Y-%m-%d'),
    #             'strategy': self.strategy,
    #             'stock': fill.contract.symbol,
    #             'action': fill.execution.side,
    #             'price': fill.execution.avgPrice,
    #             'amount': fill.execution.shares,
    #             'commission': commissionReport.commission,
    #             'profit': commissionReport.realizedPNL,
    #         }
    #
    #     logdata = pd.DataFrame(dic).T
    #     df = pd.read_pickle('log.pkl')
    #     df = df.append(logdata, ignore_index=True)
    #     df.to_pickle('log.pkl')


""" TRADING STRATEGIES """

class TriangleTrade(Bot):
    barsize = '1 min'
    smaperiod = 50
    bartime = 0
    amount = 1
    ordertype = 'MKT'
    profitPercent=5
    trailPercent=2

    def __init__(self, stock):
        super(TriangleTrade, self).__init__()
        self.stock = stock

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
            #print(sma[len(sma) - 1])

            # check for triangle break
            if last_bar.close > lastHigh \
                    and last_bar.low > lastLow \
                    and last_bar.close > sma[len(sma) - 1]:
                print('triangle formation broken')
                #place order
                self.buy_order(self.stock, self.ordertype, self.amount,last_bar.close,self.profitPercent,self.trailPercent)


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


class NewPenny(Bot):
    strategy = 'new pennystock'
    ordertype = 'LMT'
    budget = 100
    profitPercent = ''
    trailPercent = 15

    def __init__(self):
        super(NewPenny, self).__init__()

    def run(self):
        screener = StockwitsScreener()
        tickers = screener.run()
        if tickers is not None:
            for ticker in tickers:
                stock = self.create_stock(ticker)

                # get quote on ticker
                [quote] = self.ib.reqTickers(stock)
                quote = quote.marketPrice()

                # determine amount
                amount = int(self.budget/quote)

                # place order
                self.buy_order(stock, self.ordertype, amount,quote,self.profitPercent,self.trailPercent)

pennyscreeners_dic = {
    '2xVolumePenny': '2vol',
    '2xVolumePenny&Osc': '2vol_wOscillators',
    'VWAP&LAST>EMA20': 'vwap',
    'VWAP&LAST>EMA20&Osc': 'vwap_wOscillators',
    'premarket': 'premarket',
    'volumeleaders': 'Volume leaders',
}

class PennyFilters(Bot):
    ordertype = 'LMT'
    total_budget = 1000
    budget_perstock = 10
    profitPercent = ''


    def __init__(self, strategy, trailPercent):
        super(PennyFilters, self).__init__()
        self.strategy = strategy
        self.screener = pennyscreeners_dic[strategy]
        self.trailPercent = trailPercent


    def run(self):
        screener = TradingviewScreener(self.screener)
        tickers = screener.run()
        for ticker in tickers:
            try:
                stock = self.create_stock(ticker)
                print(stock)

                # get quote on ticker
                [quote] = self.ib.reqTickers(stock)
                quote = quote.marketPrice()

                dps = str(self.ib.reqContractDetails(stock)[0].minTick + 1)[::-1].find('.') - 1
                orderPrice = round(quote + self.ib.reqContractDetails(stock)[0].minTick * 2, dps)

                # determine amount
                amount = int(self.budget_perstock/orderPrice)
                if amount == 0:
                    amount=1

                # place order
                self.buy_order(stock, self.ordertype, amount, orderPrice, self.profitPercent, self.trailPercent)
            except:
                continue


""" let function run during trading hours """

def runbot():
    bot = Bot()
    # now = datetime.now()
    # open = now.replace(hour=15, minute=30, second=0, microsecond=0)
    # close = now.replace(hour=22, minute=30, second=0, microsecond=0)

    # start all bots


    # run IB connection once at market open and sleep until market close

    bot.ib.sleep(1) ###### ALTER

    #bot.ib.run()
    # while open < now < close:
    #     continue

    # log trades and disconnect from IB
    logdata(bot)
    bot.ib.disconnect()



def logdata(bot):
    fills = bot.ib.fills()
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

    # map todays fills to the trading strategy logged for respective trade
    df_strategies = pd.read_csv('log_trade.csv')

    for index, row in logdata.iterrows():
        stock = row.stock
        amount = row.amount

        strategy = df_strategies.loc[(df_strategies.stock == stock) & (df_strategies.amount == amount)].strategy
        # account for a stock possible appearing on multiple screeners
        if len(strategy) > 1:
            print(f'{stock} has ambigous strategy log: {strategy}')
            continue
        row.at[row.name, 'strategy'] = strategy

    # update logdata file
    df_logdata = pd.read_csv('transactions_log.csv')
    df_logdata = df_logdata.append(logdata, ignore_index=True)
    df_logdata.to_csv('transactions_log.csv')





# p = test.ib.portfolio()
# for _ in p:
#     stock = test.create_stock(_.contract.symbol)
#     amount = _.position
#     price = _.marketPrice
#
#     stopLoss = Order()
#     stopLoss.action = "SELL"
#     stopLoss.orderType = "TRAIL"
#     stopLoss.trailingPercent = 15
#     stopLoss.tif = 'GTC'
#     stopLoss.trailStopPrice = round(price - price * (15 / 100), 2)
#     stopLoss.totalQuantity = amount
#     test.ib.placeOrder(stock,stopLoss)


