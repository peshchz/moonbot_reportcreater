#%%
import os
import os.path
import sys
from datetime import timedelta
from datetime import datetime as dtm
import numpy as np
from pprint import pprint as pp
import pandas as pd

class calcRealRateForJoinedOrders():
    def __init__(self,df,strats_df):
        self.df = df
        self.strats_df = strats_df

    def fixJoinSellKInDf(self):
        if not self.sizes:
            self.df.loc[self.joined_index,['joined_sell_k','is_new_k']] = [self.joined_k,1]
        else:
            self.df.loc[self.joined_index,'joined_sell_k0'] = round(self.joined_value/self.sizes[0],1)
            self.df.loc[self.joined_index,'joined_sell_k1'] = round(self.joined_value/self.sizes[1],1)
            self.sizes = None
    
    def prepareOrders(self):
        self.joined_value = self.row[self.column]
        self.previous_o = list(self.previous_rows[self.column])
        self.next_o = list(self.next_rows[self.column])
        self.orders = [*self.previous_o,*self.next_o]
        self.orders.sort()

    def calcOrderSize(self):
        '''Подсчет размера изначального ордера'''
        self.sizes = None
        max_o = self.orders[1:]
        min_o = self.orders[:-1]
        for olist in [max_o,min_o]:
            if len(olist) == 0:
                continue
            if min(olist)/max(olist) > 0.8:
                poz = int(len(olist)/2)
                olist.sort()
                self.joined_k = round(self.joined_value/olist[poz],1)
                return
        for pair in [[self.previous_o,self.next_o],[self.next_o,self.previous_o]]:
            if self.joined_value < min(pair[0]) and self.joined_value > min(pair[1]):
                self.joined_k = round(self.joined_value/pair[1][0],1)
                return
        self.sizes = [min(self.orders),max(self.orders)]

    def getPreviousAndNextRows(self,rows_cnt):
        not_j_df = self.not_j_df
        self.previous_rows = not_j_df.loc[not_j_df['index'] < self.joined_index][-rows_cnt:]
        self.next_rows = not_j_df.loc[not_j_df['index'] > self.joined_index][:rows_cnt]

    def secondCalcJoinedK(self):
        '''Подсчет коэффициента там, где не удалось определить изначальный ордер'''
        self.sizes = None
        max_o = max(self.orders) * 1.3
        min_o = min(self.orders) * .7
        k0 = self.row['joined_sell_k0']
        k1 = self.row['joined_sell_k1']
        for pair in [[k0,k1],[k1,k0]]:
            #если первый коэффициент в пределах ближайших ордеров, 
            # а второй - вне пределов - то берем первый
            if pair[0] >= min_o and pair[0] <= max_o:
                if pair[1] < min_o or pair[1] > max_o:
                    self.joined_k = pair[0]
                    return
        print(f'cant calc join k. k0: {k0}, k1: {k1}, max/min neighbors {max_o}/ {min_o}')
        self.joined_k = round((k0+k1)/2,1)

    def calcJoinedK(self,iteration):
        joined_sell_df = self.df.loc[(self.df['sell_condition']=='JoinedSell')&(self.df['joined_sell_k'].isnull())]
        joined_strats = list(joined_sell_df['strat'].unique())
        for strat in joined_strats:
            joined_df = self.df.loc[(self.df['sell_condition']=='JoinedSell')&(self.df['joined_sell_k'].isnull())&\
                (self.df['strat']==strat)]
            if iteration == 0:
                #self.not_j_df = self.df.loc[(self.df['need_calc']==0)&(self.df['strat']==strat)].reset_index()
                self.not_j_df = self.df.loc[(self.df['sell_condition']!='JoinedSell') & \
                    (self.df['strat']==strat)].reset_index()
            else:
                self.not_j_df = self.df.loc[(self.df['sell_condition']=='JoinedSell')&(~self.df['joined_sell_k'].isnull())&\
                (self.df['strat']==strat)].reset_index()
            for self.joined_index,self.row in joined_df.iterrows():
                try:
                    if iteration == 0:
                        self.getPreviousAndNextRows(2)
                        self.column = 'spent_usd'
                        self.prepareOrders()
                        self.calcOrderSize()
                    else:
                        self.getPreviousAndNextRows(5)
                        self.column = 'joined_sell_k'
                        self.prepareOrders()
                        self.secondCalcJoinedK()
                    self.fixJoinSellKInDf()
                except:
                    pass

    def calcMultiOrder(self,row):
        spent_money = row['spent_usd']
        balance = spent_money + 0
        strat_order_size = row['spent_usd'] / row['joined_sell_k']
        size_step  = self.current_strat['m_o_size_step']
        buy_price_step = self.current_strat['m_price_step']
        multi_o_cnt = self.current_strat['m_orders_cnt']
        fact_orders_in_net = 0 #куплено ордеров в сетке
        self.fact_multi_o_size = 0 #потрачено на ордера в сетке
        while fact_orders_in_net < multi_o_cnt and balance > 0:
            fact_orders_in_net += 1
            if self.current_strat['m_o_size_kind'] == 'Linear':
                order_size_k =  1 + size_step/100*(fact_orders_in_net-1)
            else:
                order_size_k =  (size_step/100)**(fact_orders_in_net-1)
            current_price = strat_order_size *(1 + buy_price_step/100*(fact_orders_in_net-1))
            self.fact_multi_o_size += current_price * order_size_k
            balance -= current_price * order_size_k
            if balance < strat_order_size * 0.3:
                balance = 0
        self.fact_orders_in_net = round(fact_orders_in_net,1)
        nets_cnt = spent_money / self.fact_multi_o_size
        self.total_order_nets = int(nets_cnt) if nets_cnt%1 < 0.2 else int(nets_cnt)+1
        if self.total_order_nets == 0:
            self.total_order_nets = 1

    def addMultiorderData(self):
        multi_df = self.df.loc[(~self.df['joined_sell_k'].isnull())&(self.df['orders_in_net'].isnull())]
        for self.index,row in multi_df.iterrows():
            self.current_strat = self.strats_df[self.strats_df['name']==row['strat']].to_dict('records')[0]
            if self.current_strat['m_orders_cnt'] > 1:
                try:
                    self.calcMultiOrder(row)
                except:
                    continue
                cols = ['orders_in_net','total_order_nets','order_size_in_settings','is_new_k']
                vals = [self.fact_orders_in_net,self.total_order_nets,round((row['spent_usd']/row['joined_sell_k']),4),1]
                self.df.loc[self.index,cols] = vals
