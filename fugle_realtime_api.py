#!/usr/bin/env python
# coding: utf-8

# In[1]:
from fugle_realtime import intraday
import datetime
import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
from  dash.dependencies import Input, Output
import dash_daq as daq
from pytz import timezone
import talib as ta
import requests
import time


# In[2]:


class fugle_realtime_chart():
    
    def __init__(self, api_token, symbol_id):
        
        self.api_token = api_token
        self.symbol_id = symbol_id
        
    def query_minute_data(self, n):
        
        df = intraday.chart(symbolId=self.symbol_id, apiToken=self.api_token, output='dataframe')
        
        #調整時差(+8)問題
        timezone_func = lambda x: x.astimezone(None) + datetime.timedelta(hours=8)
        df['at'] = df['at'].apply(timezone_func)
        
        #取得現在時間
        now = datetime.datetime.now()
        #取得年、月、日
        year, month, day = now.year, now.month, now.day
        
        #取得今日開盤所有時間(以一分鐘為單位)
        time_list = []
        for i in range(9,14):
            for y in range(0,60):
                if datetime.datetime(year, month,day, i, y) <= datetime.datetime(year, month, day, 13, 25):
                    time_list.append(datetime.datetime(year, month, day, i, y))
                else:
                    pass

        df_time = pd.DataFrame(time_list[1:]).rename(columns={0:'at'})
        
        df = pd.merge(df_time, df, on='at', how='outer')
        df = df[df['at'] <= datetime.datetime(year, month, day, 13, 25)]
        
        #df_now -> 開盤後截至現在的交易資料
        #df_after -> 尚未有交易資料之時間
        df_now = df[df['at'] <= now]
        df_after = df[df['at'] > now]
        df_now = df_now.set_index('at')
        
        #df_ohlc -> 截至現在的開高低收價格資料
        #若該分鐘沒有交易行為，則將上一分鐘之收盤價，作為該分鐘的開高低收。
        df_ohlc = df_now[['open', 'high', 'low', 'close']]
        df_ohlc['close'] = df_ohlc['close'].fillna(method='ffill')
        df_ohlc = df_ohlc.fillna(method='bfill', axis=1)
        
        #df_volume -> 截至現在的每分鐘交易量資料
        #若該分鐘沒有交易行為，則交易量以0填補NaN值
        df_volume = df_now[['unit', 'volume']]
        df_volume = df_volume.fillna(0)
        
        #將開高低收及交易量資料合併
        df_all = pd.concat([df_ohlc, df_volume], axis=1, join='outer').reset_index()
        #將整理完成後且截止現在的資料與尚未發生時間之資料合併
        df_all = pd.concat([df_all, df_after], axis=0)
        
        #依照設定之時間區間取的分K資料(格式：list)
        list_min = []

        for z in range(len(df_all)):

            if (z+1) % n == 0:

                time_start = df_all['at'][z] - datetime.timedelta(minutes = n-1)
                time_now = df_all['at'][z]
                df_min = df_all[(df_all['at'] >= time_start) & (df_all['at'] <= time_now)].reset_index(drop=True)
                close_min = df_min['close'][n-1]
                open_min = df_min['open'][0]
                high_min = max(df_min['high'])
                low_min = min(df_min['low'])
                time_min = df_min['at'][n-1]

                list_min.append([close_min, open_min, high_min, low_min, time_min, df_all['volume'][z]])

            else:
                pass
            
        #將分K資料轉換為dataframe格式
        df_min = pd.DataFrame(list_min)
        df_min.columns=['close', 'open', 'high', 'low', 'at', 'volume']

        time_func = lambda x: datetime.time(x.hour, x.minute)

        df_min['at'] = df_min['at'].apply(time_func)
        
        return df_min
    
class plot_chart_data(fugle_realtime_chart):
    
    def __init__(self, api_token, symbol_id):
        
        super().__init__(api_token, symbol_id)
        
    def min_K(self, n, up_color, down_color):
        
        #將分K資料取出
        df = self.query_minute_data(n)
        self.df = df
        
        return {
            'type':'candlestick',
            'x':df['at'],
            'open':df['open'],
            'high':df['high'],
            'low':df['low'],
            'close':df['close'],
            'name':'K棒',
            'increasing':{'line':{'color':up_color}},
            'decreasing':{'line':{'color':down_color}}
        }
    
    def min_volume(self, up_color, down_color):
        
        df_volume = self.df
        
        volume_color = []
        
        for i in range(len(df_volume)):
            
            if df_volume['open'][i] - df_volume['close'][i] == 0:
                
                if df_volume['open'][i] - df_volume['close'][i] == 0:
                    try:
                        if df_volume['close'][i] > df_volume['close'][i-1]:

                            volume_color.append(up_color)

                        elif df_volume['close'][i] < df_volume['close'][i-1]:

                            volume_color.append(down_color)

                        else:
                            volume_color.append(volume_color[-1])
                            
                    except:
                        volume_color.append('gray')
                
            elif df_volume['open'][i] - df_volume['close'][i] > 0:
                
                volume_color.append(down_color)
                
            elif df_volume['open'][i] - df_volume['close'][i] < 0:
                
                volume_color.append(up_color)
        
        return {
            
            'type':'bar',
            'x':df_volume['at'],
            'y':df_volume['volume'],
            'marker':{'color':volume_color}
            
        }


# In[4]:


class fugle_realtime_trades():
    
    def __init__(self, api_token, symbol_id):
        
        self.api_token = api_token
        self.symbol_id = symbol_id
        
    def query_trades_data(self, n):
        
        df = intraday.trades(symbolId=self.symbol_id, apiToken=self.api_token, output='dataframe')
        
        timezone_func = lambda x: x.astimezone(None) + datetime.timedelta(hours=8)
        datetime_func = lambda x: datetime.datetime(x.year, x.month, x.day, x.hour, x.minute)
        
        df['at'] = df['at'].apply(timezone_func)
        df['time'] = df['at'].apply(datetime_func)
        
        df['p*v'] = df['price'] * df['unit']
        
        #取得現在時間
        now = datetime.datetime.now()
        #取得年、月、日
        year, month, day = now.year, now.month, now.day
        
        df = df.groupby(['time']).sum().reset_index()[['time','p*v', 'unit']]
        
        time_list = []
        for i in range(9,14):
            for y in range(0,60):
                if datetime.datetime(year, month,day, i, y) <= datetime.datetime(year, month, day, 13, 25):
                    time_list.append(datetime.datetime(year, month, day, i, y))
                else:
                    pass

        df_time = pd.DataFrame(time_list).rename(columns={0:'time'})
        
        df = pd.merge(df_time, df, on='time', how='outer')

        #df_now -> 開盤後截至現在的交易資料
        #df_after -> 尚未有交易資料之時間
        df_now = df[df['time'] <= now]
        df_after = df[df['time'] > now]
        df_now = df_now.fillna(0)
        
        df_all = pd.concat([df_now, df_after], axis=0)
        
        list_min = []
        for z in range(len(df_all)):

            if (z+1) % n == 0:

                time_start = df_all['time'][z] - datetime.timedelta(minutes = n-1)
                time_now = df_all['time'][z]
                df_min = df_all[(df_all['time'] >= time_start) & (df_all['time'] <= time_now)].reset_index(drop=True)
                sum_pv = sum(df_min['p*v'])
                sum_unit = sum(df_min['unit'])
                time = time_now+datetime.timedelta(minutes=1)

                list_min.append([time, sum_pv, sum_unit])

            else:
                pass
            
        df_min = pd.DataFrame(list_min)
        df_min.columns = ['time', 'p*v', 'unit']
        df_min = df_min[df_min['time'] <= datetime.datetime(year, month, day, 13, 25)]

        avg_cost = []
        for i in range(len(df_min)):
            if df_min['time'][i] <= now:
                avg_cost.append('%.4f' % (sum(df_min['p*v'][:i+1].fillna(0)) / sum(df_min['unit'][:i+1].fillna(0))))

            else:
                pass
            
        df_min['avg_cost'] = pd.DataFrame(avg_cost)
        
        time_func = lambda x: datetime.time(x.hour, x.minute)
        df_min['time'] = df_min['time'].apply(time_func)
        
        return df_min
    
    
class plot_trades_data(fugle_realtime_trades):
    
    def __init__(self, api_token, symbol_id):
        
        super().__init__(api_token, symbol_id)
        
        self.newest_price = intraday.meta(symbolId=symbol_id, apiToken=api_token, output='raw')['priceReference']
        
    def avg_cost_line(self, n, line_color):
        
        df = self.query_trades_data(n)
        
        return {
            'type':'scatter',
            'x':df['time'],
            'y':df['avg_cost'],
            'mode':'lines',
            'name':'avg_cost',
            'line':{'color':line_color}
        }
    
    def volume_of_price(self):
        
        df = intraday.trades(symbolId=self.symbol_id, apiToken=self.api_token, output='dataframe')
        df = df.groupby(['price']).sum().reset_index()[['price', 'unit']]
        
        color = []
        for i in df['price']:
            if i > self.newest_price:
                color.append('red')
            elif i < self.newest_price:
                color.append('green')
            else:
                color.append('gray')
        
        return {
            'type':'bar',
            'x':df['unit'],
            'y':df['price'],
            'orientation':'h',
            'marker':{'color':color}
        }


# In[6]:


class fugle_realtime_quote():
    
    def __init__(self, api_token, symbol_id):
        
        self.api_token = api_token
        self.symbol_id = symbol_id
    
    def get_first_order_book(self):

        message = intraday.quote(symbolId=self.symbol_id, apiToken=self.api_token, output='raw')

        df_ask = pd.DataFrame(message['order']['bestAsks'])[::-1][['price', 'unit']]
        df_ask = df_ask.rename(columns={'unit':'ask unit'})

        df_bid = pd.DataFrame(message['order']['bestBids'])[::-1][['unit', 'price']]
        df_bid = df_bid.rename(columns={'unit':'bid unit'})

        self.dataframe = pd.merge(df_ask, df_bid, how='outer')[['bid unit', 'price', 'ask unit']]


    def update_order_book(self):

        message = intraday.quote(symbolId=self.symbol_id, apiToken=self.api_token, output='raw')

        df_ask = pd.DataFrame(message['order']['bestAsks'])[::-1][['price', 'unit']]
        df_ask = df_ask.rename(columns={'unit':'ask unit'})

        df_bid = pd.DataFrame(message['order']['bestBids'])[::-1][['unit', 'price']]
        df_bid = df_bid.rename(columns={'unit':'bid unit'})

        update_df = pd.merge(df_ask, df_bid, how='outer')[['bid unit', 'price', 'ask unit']]

        self.price_list = update_df['price'].tolist()

        self.dataframe = pd.concat([self.dataframe, update_df], axis=0).drop_duplicates(subset='price', keep='last')
        self.dataframe = self.dataframe.sort_values('price', ascending=False).reset_index(drop=True)


# In[7]:


class plot_quote_data(fugle_realtime_quote):
    
    def __init__(self, api_token, symbol_id):
        
        super().__init__(api_token, symbol_id)
        
        
    def order_book(self, header_fontsize, cell_fontsize):
        
        newest_price = intraday.meta(symbolId=self.symbol_id, apiToken=self.api_token, output='raw')['priceReference']
        
        final_df = self.dataframe
        
        rows = []
        for i in range(len(final_df)):
            row = []
            for col in final_df.columns:
                value = final_df.iloc[i][col]

                if col == 'price':

                    if value not in self.price_list:
                        
                        cell = html.Td(html.A(href='https://www.fugle.tw/ai/'+self.symbol_id, children=value,style={'color':'gray'}),
                                       style={'font-size':cell_fontsize,'text-align':'center'})
                        
                    elif value in self.price_list:
                        
                        if value > newest_price:
                            cell = html.Td(html.A(href='https://www.fugle.tw/ai/'+self.symbol_id, children=value,style={'color':'red'}),
                                           style={'font-size':cell_fontsize,'text-align':'center'})
                        elif value < newest_price:
                            cell = html.Td(html.A(href='https://www.fugle.tw/ai/'+self.symbol_id, children=value,style={'color':'green'}),
                                           style={'font-size':cell_fontsize,'text-align':'center'})
                        else:
                            cell = html.Td(html.A(href='https://www.fugle.tw/ai/'+self.symbol_id, children=value),
                                           style={'font-size':cell_fontsize,'text-align':'center'})

                else:
                    cell = html.Td(children=value,style={'font-size':cell_fontsize,'text-align':'center'})

                row.append(cell)
            rows.append(html.Tr(row))

        return html.Table(
            [html.Tr([html.Th(col) for col in final_df.columns],
                     style={'font-size':header_fontsize,'text-align':'center', 'table-align':'center'})] +rows
        )


# In[8]:


class notify_setting():
    
    def __init__(self, api_token, line_token):
        
        self.api_token = api_token
        self.line_token = line_token
        
    def lineNotifyMessage(self, msg):
    
        headers = {
           "Authorization": "Bearer " + self.line_token, 
           "Content-Type" : "application/x-www-form-urlencoded"
       }

        payload = {'message': msg}
        r = requests.post("https://notify-api.line.me/api/notify", headers = headers, params = payload)
        return r.status_code
        
    def price_info(self, symbol_id):
        
        open_price = intraday.meta(apiToken=self.api_token, symbolId=symbol_id, output='raw')['priceReference']
        trade_price = intraday.quote(apiToken=self.api_token, symbolId=symbol_id, output='raw')['trade']['price']
        url = 'https://www.fugle.tw/trade?symbol_id=' + symbol_id + '&openExternalBrowser=1'
        
        self.open_price = open_price
        self.trade_price = trade_price
        self.url = url
        
        
    def price_change_strategy(self, symbol_id, up_rate, down_rate):
        
        while True:
            
            self.price_info(symbol_id)
            
            if (self.trade_price - self.open_price) / self.open_price >= up_rate:
                
                self.lineNotifyMessage('\nOH！'+ symbol_id +' 漲幅已經超過'+str(up_rate*100)+'% \n'+ self.url)
                break
                
            elif (self.trade_price - self.open_price) / self.open_price <= -down_rate:
                
                self.lineNotifyMessage('\nOH！'+ symbol_id +' 跌幅已經超過'+str(down_rate*100)+'% \n'+ self.url)
                break
                
            else:
                print('Nothing')
                time.sleep(5)
    
    def price_strategy(self, symbol_id ,up_price, down_price):
            
        self.price_info(symbol_id)

        if self.trade_price >= up_price:

            self.lineNotifyMessage('\nOH！'+ symbol_id +' 價格已經超過'+str(up_price)+'元 \n'+ self.url)

        elif self.trade_price <= down_price:

            self.lineNotifyMessage('\nOH！'+ symbol_id +' 價格已經低於'+str(down_price)+'元 \n'+ self.url)

        else:
            print('nothing')
            
            
    def line_strategy_bottom(self, id_name, label_name):
        
        return daq.BooleanSwitch(
            id=id_name,
            on=False,
            label=label_name)


# In[ ]:




