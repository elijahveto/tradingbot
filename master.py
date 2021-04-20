from ib_insync import *
import ta
import numpy as np
import pandas as pd


class Bot:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7496, clientId=1)
        self.ib.sleep(1)

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
        #self.ib.sleep(10)


    def historical_data(self, stock, duration, barsize, what):
        bars = self.ib.reqHistoricalData(
            stock, endDateTime='', durationStr=duration,
            barSizeSetting=barsize, whatToShow=what, useRTH=True)
        for bar in bars:
            print(bar)


    """ ORDER METHODS """

    def __BracketOrder(self, parentOrderId, childOrderId1, childOrderId2,action, quantity, limitPrice, profitPercent, trailingPercent):
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = "LMT"
        parent.totalQuantity = quantity
        parent.lmtPrice = limitPrice
        parent.transmit = False

        if profitPercent != '':
            takeProfit = Order()
            takeProfit.orderId = childOrderId1
            takeProfit.action = "SELL" if action == "BUY" else "BUY"
            takeProfit.orderType = "LMT"
            takeProfit.totalQuantity = quantity
            takeProfit.lmtPrice = round((limitPrice * (100+profitPercent))/100,2)
            takeProfit.parentId = parentOrderId
            takeProfit.transmit = False

        stopLoss = Order()
        stopLoss.orderId = childOrderId2
        stopLoss.action = "SELL" if action == "BUY" else "BUY"
        stopLoss.orderType = "TRAIL"
        stopLoss.trailingPercent = trailingPercent
        stopLoss.trailStopPrice = round(limitPrice - limitPrice * (trailingPercent / 100),2)
        stopLoss.totalQuantity = quantity
        stopLoss.parentId = parentOrderId
        stopLoss.transmit = True

        if profitPercent:
            bracketOrder = [parent, takeProfit, stopLoss]
        else:
            bracketOrder = [parent, stopLoss]
        return bracketOrder

    def buy_order(self, stock, amount, limitPrice, profitPercent, trailPercent):
        bracket = self.__BracketOrder(self.ib.client.getReqId(), self.ib.client.getReqId(), self.ib.client.getReqId(), "BUY", amount, limitPrice, profitPercent, trailPercent)
        for o in bracket:
            trade = self.ib.placeOrder(stock, o)
            print(trade)
            trade.fillEvent += self.__orderFilled
            trade.commissionReportEvent += self.__commission

    """ REPORT METHODS (auto) """

    def __orderFilled(self, trade, fill):
        print('order has been filled')
        print(trade)
        print(f'commission: {fill.commissionReport.commission}')

    def __commission(self, trade, fill, commissionReport):
        print('commission Report availavle')
        print(commissionReport)
        print(commissionReport.commission)

    def __store(self, trade):
        pass


""" TRADING STRATEGIES """

""" price breaks triangle formation (lower highs and higher lows) & price > 50SMA """
class TriangleTrade(Bot):
    barsize = '1 min'
    smaperiod = 50
    bartime = 0
    amount = 1
    profitPercent=5
    trailPercent=2

    def __init__(self):
        super(TriangleTrade, self).__init__()

    def __onBarUpdate(self, bars, hasNewBar):

        if hasNewBar:
            # get latest values in last_bar
            last_bar = bars[-1]
            # set last params to compare against
            closes = [bar.close for bar in bars[:-2]]
            lastLow = bars[-2].low
            lastHigh = bars[-2].high
            lastClose = bars[-2].close
            close_array = pd.Series(np.asarray(closes))
            sma = ta.trend.sma_indicator(close=close_array, window=self.smaperiod, fillna=True)
            #print(sma[len(sma) - 1])

            # check for triangle break
            if last_bar.close > lastHigh \
                    and last_bar.low > lastLow \
                    and last_bar.close > sma[len(sma) - 1]:
                print('triangle formation broken')
                self.buy_order(stock,self.amount,last_bar.close,self.profitPercent,self.trailPercent)


    def run(self, stock):
        bars = self.ib.reqHistoricalData(stock,
                endDateTime = '',
                durationStr = '2 D',
                barSizeSetting = self.barsize,
                whatToShow = 'TRADES',
                useRTH = True,
                formatDate = 1,
                keepUpToDate = True)
        bars.updateEvent += self.__onBarUpdate



bot = TriangleTrade()
stock = bot.create_stock('AAPL')
bot.run(stock)
bot.ib.run()

