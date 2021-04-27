Tradingbot running on TWS from Interactive Brokers

Required: 

- Interactive Brokers Account 
- TWS
- Market Data Subscription on IB 


Process:

- bot runs market screeners via selenium on tradingview
    - chose this over IB screeners because IB screeners are limited and require specific market data
      subscriptions, whereas tradingview provides a very large screener selection for free and for a minimal fee in near real-time

- bot executes trade with trailing stop loss

- once market is closed all trades (fills) of the day are logged to a csv file which is used for performance evaluation 
  - chose this over IB provided .fillEvent update function because I needed a log function that would a) allow me to run various strategies 
    (i.e. strategy bots) at the same time and b) not lose my strategy attribution in case the TWS connection is lost 
    
