#%%
#%load_ext autoreload
#%autoreload 2
import os
import os.path
import sys
from datetime import timedelta
from datetime import datetime as dtm
from datetime import date as dt
from pprint import pprint as pp
import pandas as pd
import numpy as np
import traceback
from functools import partial

pd.options.display.expand_frame_repr = False
for path in ['./mylib','./mylib/reports','./mylib/download_data']:
    sys.path.append(os.path.abspath(path))

from bd import DownloadOrdersFromBd
from defs import *
from happy_hours import StratByHours
from reports_defs import Beauty

import warnings
warnings.filterwarnings('ignore')
#%%

class Analitics(Beauty):
    def __init__(self,df,tasks_df=None):
        self.df = df
        self.tasks_df = tasks_df

    def createAnalitics(self,group_column,need_metrics=False):
        self.need_metrics = need_metrics
        self.group_column = group_column
        self.groupStrat()
        self.groupDaily()
        self.calcNonProfitDays()
        self.joinReports()
        self.changeColumnsOrder()
        self.df_report = self.df_report.fillna(0)

    def groupDaily(self):
        '''группировка по дням'''
        #perc95 = partial(np.percentile, q=95)
        query = {'rate': pd.NamedAgg(column = 'profit', aggfunc = 'sum'),
            #'max_orders_in_net': pd.NamedAgg(column = 'orders_in_net', aggfunc = 'max'),
            #'95_orders_in_net': pd.NamedAgg(column = 'orders_in_net', aggfunc = perc95),
            'cnt': pd.NamedAgg(column = 'profit', aggfunc = 'count'),
            'usd': pd.NamedAgg(column = 'profit_usd', aggfunc = 'sum'),
            'pr_plus': pd.NamedAgg(column = 'pr_plus', aggfunc = 'sum'),
            'pr_minus': pd.NamedAgg(column = 'pr_minus', aggfunc = 'sum'),
             }        
        df_agg = self.df.groupby(['date',self.group_column]).agg(**query)
        df_agg['pr_factor'] = round(df_agg['pr_plus'] / df_agg['pr_minus'],2).abs()
        df_agg.loc[df_agg['pr_minus']==0,'pr_factor'] = 10
        #df_agg = df_agg.drop(['rate'], 1)
        df_agg = self.makeBeauty(df_agg)
        #df_agg = df_agg.unstack(0)
        #cols = df_agg.columns.tolist()
        cols = ['cnt','pr_factor','usd','rate',]#'95_orders_in_net','max_orders_in_net',
        df_agg = df_agg[cols]
        self.df_daily = df_agg

    def calcNonProfitDays(self):
        df = self.df_daily.copy()
        df.reset_index(inplace=True)
        df = df[df['rate']<0]
        query = {'rate': pd.NamedAgg(column = 'rate', aggfunc = 'sum'),
                'cnt': pd.NamedAgg(column = 'rate', aggfunc = 'count'),
                }        
        df_agg = df.groupby([self.group_column]).agg(**query)
        df_agg.columns = ['non_profit_sum','non_profit_days']
        self.non_profit_df = df_agg#.reset_index()
        self.len_agg += 2

    def calcNonProfPercent(self):
        if len(self.df_report) == 0:
            return
        df = self.df_report
        df.loc[df['non_profit_sum'].isnull(),'non_profit_days']=0.1
        df.loc[df['non_profit_sum'].isnull(),'non_profit_sum']=0.1
        df.loc[df['rate']!=0,'non_prof_k'] = (df['non_profit_sum'] / df['rate']).\
            round(1)
        df.loc[df['non_prof_k']>0,'non_prof_k'] = -10
        df.loc[df['non_prof_k']<-1,'non_prof_k'] = -1
        self.len_agg += 1
        
    def joinReports(self):
        self.df_report = pd.merge(self.df_report,self.non_profit_df,
            on=self.group_column,how='left')
        self.calcNonProfPercent()
        self.df_report = pd.merge(self.df_report, self.df_daily.unstack(0), 
            on=self.group_column,how='left').\
            sort_values(by=['rate'], ascending=False)
        self.df_report = self.df_report.fillna(0)
        for c in self.df_report.columns:
            if 'cnt' in c:
                self.df_report[c] = self.df_report[c].astype(int)

    def changeColumnsOrder(self):
        cols = list(self.df_report.columns.values)
        num = self.len_agg
        new_col = cols[:num] + cols[-1:num-1:-1]
        self.df_report = self.df_report[new_col]
        #self.df_report.set_index(new_col, inplace=True)
        #self.df_report.reset_index(inplace=True)

    def addMetricsRuntimeAndDelta(self,df_agg):
        cols = ['SLoss','SL_plus','SellPr','BVSV','SellLvl','Trail','PrDown','FiltCheck','NoData']
        metr = ['runtime','c1m','c5m','c15m','btc1m','btc5m']   
        for index,row in df_agg.iterrows():
            part_df = self.df[self.df['strat']==row['strat']]            
            for m in metr:
                for c in cols:
                    segm = part_df.loc[(part_df[c]==1) & (part_df[m]>0)]
                    val = segm[m].mean() if len(segm)>0 else 0
                    col_name = f'{m},{c}'
                    df_agg.loc[index,col_name] = round(val,2)
        return df_agg

    def groupStrat(self):
        '''группировка за весь период'''
        #perc98 = partial(np.percentile, q=98)
        query = {
            'type': pd.NamedAgg(column = 'type', aggfunc = 'max'),
            'is_short': pd.NamedAgg(column = 'is_short', aggfunc = 'max'),
            'size': pd.NamedAgg(column = 'osize', aggfunc = 'max'),
            'age': pd.NamedAgg(column = 'age', aggfunc = 'max'),
            'active': pd.NamedAgg(column = 'active', aggfunc = 'max'),
            #'98_orders_in_net': pd.NamedAgg(column = 'orders_in_net', aggfunc = perc98),
            'sp': pd.NamedAgg(column = 'strat_path', aggfunc = 'max'),
            'joinkey': pd.NamedAgg(column = 'joinkey', aggfunc = 'max'),
            'tr_key': pd.NamedAgg(column = 'tr_key', aggfunc = 'max'),
            'tr_b_key': pd.NamedAgg(column = 'tr_b_key', aggfunc = 'max'),            
            'rate': pd.NamedAgg(column = 'profit', aggfunc = 'sum'),
            'usd':pd.NamedAgg(column = 'profit_usd', aggfunc = 'sum'),
            'cnt': pd.NamedAgg(column = 'profit', aggfunc = 'count'),
            'cnt_plus': pd.NamedAgg(column = 'pr_plus', aggfunc = 'count'),
            'cnt_minus': pd.NamedAgg(column = 'pr_minus', aggfunc = 'count'),
            'pr_plus': pd.NamedAgg(column = 'pr_plus', aggfunc = 'sum'),
            'pr_minus': pd.NamedAgg(column = 'pr_minus', aggfunc = 'sum'),   
            'runtime': pd.NamedAgg(column = 'runtime', aggfunc = 'mean'),
            'SL_plus': pd.NamedAgg(column = 'SL_plus', aggfunc = 'count'),
            }
        reasons = list(self.df['sell_reason'].unique())
        reasons.append('SL_plus')
        for reason in reasons:
            query[reason] = pd.NamedAgg(column = reason, aggfunc = 'count')
        
        df_agg = self.df.groupby(self.group_column).agg(**query).reset_index()
        if self.group_column == 'strat':
            query = {
                'task': pd.NamedAgg(column = 'task_quantity', aggfunc = 'sum'),
                }
            df_agg_task = self.tasks_df.groupby(self.group_column).agg(**query).reset_index()
            df_agg = pd.merge(df_agg, df_agg_task, on=self.group_column, how='left').reset_index(drop=True)
        df_agg['1_order'] = round(df_agg['rate'] / df_agg['cnt'],1)
        df_agg['pr_factor'] = round(df_agg['pr_plus'] / df_agg['pr_minus'],2).abs()
        df_agg.loc[df_agg['pr_minus']==0,'pr_factor'] = 10
        df_agg['loss_avg'] = round(df_agg['pr_minus'] / df_agg['cnt_minus'],2)
        #df_agg['q_index'] = round(df_agg['cnt_plus'] / df_agg['cnt'],1)
        
        for col in reasons:
            df_agg[col] = (df_agg[col] / df_agg['cnt'] *100).astype(int)
        df_agg['runtime'] = df_agg['runtime'].astype(int)
        if 'strat' in df_agg.columns:
            for index,row in df_agg.iterrows():
                part_df = self.df[self.df['strat']==row['strat']]
                bots = part_df['bot'].unique()
                df_agg.loc[index,'bot'] = ','.join(bots)
            if self.need_metrics == True:
                df_agg = self.addMetricsRuntimeAndDelta(df_agg)
        else:
            df_agg['bot'] = ''
        df_agg = df_agg.sort_values(by=['rate'], ascending=False)
        #df_agg = df_agg.drop(['cnt'], 1)
        df_agg = df_agg.drop(['pr_plus','cnt_plus','pr_minus'], 1)#,'cnt_minus'
        self.len_agg = len(df_agg.columns)
        self.df_report = self.makeBeauty(df_agg)


class Review(Analitics):
    def __init__(self,df):
        self.df = df

    def createReview(self,group_column='bot'):
        self.group_column = group_column
        self.groupData()
        self.reviewToStr()

    def groupData(self):
        '''группировка'''
        query = {
            'rate': pd.NamedAgg(column = 'profit', aggfunc = 'sum'),
            'usd':pd.NamedAgg(column = 'profit_usd', aggfunc = 'sum'),
            }
        df_agg = self.df.groupby(self.group_column).agg(**query).reset_index()
        #df_agg['pr_factor'] = round(df_agg['pr_plus'] / df_agg['rate'],1)
        df_agg = df_agg.sort_values(by=['bot'], ascending=True)
        #df_agg = df_agg.drop(['pr_plus'], 1)
        self.df_report = self.makeBeauty(df_agg)

    def reviewToStr(self):
        rows_len = [15,10]#,10
        columns = ['bot','usd']#,'rate'
        min_usd = 5
        def createRow(rows_len,txt):
            row = ''
            for i,rl in enumerate(rows_len):
                val = str(txt[i]).ljust(rl)
                row = f'{row}|{val}' if row != '' else val
            row = f'{row}\n'
            return row
        self.review_txt = createRow(rows_len,columns)
        for _,row in self.df_report.iterrows():
            if abs(row['usd']) < min_usd:
                continue
            vals = [row[col] for col in columns]
            self.review_txt += createRow(rows_len,vals)
        vals = ['Total',self.df_report['usd'].sum(),'']
        self.review_txt += createRow(rows_len,vals)

class Analitics2():
    def __init__(self,df,report_strat,report_coin):
        self.df = df
        self.r_strat = report_strat
        self.r_coin = report_coin

    def createReportsCoinsInStrat(self):
        df = self.df
        coins_report = pd.DataFrame(columns=self.r_coin.columns)
        for strat in self.r_strat['strat'].unique():
            strat_row = self.r_strat[self.r_strat['strat'] == \
                strat]
            df_cut = df[df['strat'] == strat]
            an = Analitics(df_cut)
            an.createAnalitics('coin')
            coin = an.df_report.sort_values(by=['rate'], ascending=False)
            coin['strat'] = strat
            coin['bot'] = strat_row['bot'].values[0]
            #strat_row.loc[0,'bot']
            coins_report = pd.concat([coins_report,coin,strat_row])
        coins_report['coin'].fillna('All_coins', inplace=True)
        coins_report.fillna(0, inplace=True)
        cols = coins_report.columns
        cols = cols.insert(0,'strat')
        cols = cols[:-1]
        self.df_report = coins_report[cols]

class GetInfo(Analitics):
    def __init__(self,settings,telegram_id=None):
        self.telegram_id = telegram_id
        self.settings = settings

    def createHourlyReport(self):
        d = DownloadOrdersFromBd(self.settings,self.telegram_id)
        d.downloadDataset()
        self.df = d.df
        self.df['pr_plus'] = self.df['profit']
        self.df.loc[(self.df['profit'] < 0), 'pr_plus'] = 0
        if len(d.df) == 0:
            print('len(d.df) == 0')
            self.hourly_reports = {}
            return
        self.an = StratByHours(d.df,self.settings)
        self.an.createReport()
        self.hourly_reports = self.an.df_report
        time_line = self.settings['time_line']
        if 'duration' in self.settings:
            dur = self.settings['duration']
            dur_txt = f'. duration {dur}'
        else:
            dur_txt = ''
        #self.hourly_report.loc['total','strat'] = f'Total. {time_line} d{dur_txt}'
        self.len_agg = 3

    def getRawData(self):
        self.settings_xls = {'hidden_columns':[]}
        d = DownloadOrdersFromBd(self.settings,self.telegram_id)
        d.downloadDataset()
        df = d.df
        if len(df) == 0:
            return
        for date in ['buy_date','close_date']:
            df[date] = df[date].dt.strftime('%d.%m.%Y %H:%M:%S')
            #df.loc[(~df[date].isnull()),date] = df[date].dt.strftime('%d.%m.%Y %H:%M')
        hide_cols = ['joinkey','tr_key','tr_b_key','btc5m','btc1m','c15m','c5m',
            'c1m','base_coin','site','market_type','type','is_short','bd_row_id']
        df['profit'] = df['profit'] * 10
        for index,col in enumerate(list(df.columns)):
            if col in hide_cols:
                self.settings_xls['hidden_columns'].append(index)
        self.df = df

    def createReview(self):
        '''краткая информация по ботам'''
        d = DownloadOrdersFromBd(self.settings,self.telegram_id)
        d.downloadDataset()
        an = Review(d.df)
        an.createReview('bot')
        self.review_txt = an.review_txt

    def createReports(self):
        self.createReportList()
        d = DownloadOrdersFromBd(self.settings,self.telegram_id)
        d.downloadDataset()
        try:
            d.formatDf()
        except:
            pass
        self.df = d.df
        d.settings['strategy__in'] = list(self.df['strategy__id'].unique())
        d.getOrdersTask()
        self.tasks_df = d.tasks_df
        self.createDataInterval()
        self.report = {}
        self.d = d
        self.an = Analitics(self.df,d.tasks_df)
        for report_type in self.report_list:            
            if report_type == 'strat' and 'coin' not in self.report_list:
                need_metrics = self.settings['need_metrics'] 
            else:
                need_metrics =  False
            self.an.createAnalitics(report_type,need_metrics)            
            self.report[report_type] = self.an.df_report
            self.len_agg = self.an.len_agg
        if 'coin_strat' in self.settings['need_reports']:
            an = Analitics2(
                d.df,self.report['strat'],self.report['coin'])
            an.createReportsCoinsInStrat()
            self.report['coin_strat'] = an.df_report

        print('Reports created!')

    def createReportList(self):
        self.report_list = []
        if type(self.settings['need_reports']) == str:
            self.settings['need_reports'] = [self.settings['need_reports']]
        if self.settings['need_reports'] == ['all']:
            self.settings['need_reports'] = ['strat','coin','coin_strat']
        for r in ['strat','coin']:
            if r in self.settings['need_reports']:
                self.report_list.append(r)
    
    def createDataInterval(self):
        self.data_interval = '{} - {}'.format(
                self.df['buy_date'].min().strftime('%d-%m %H:%M'),
                self.df['buy_date'].max().strftime('%d-%m %H:%M'))
        print(self.data_interval)

    def showReport(self,report_type='strat',filter=None):
        if not filter:
            return self.report[report_type]
        else:
            f = self.report[report_type]
            return f[f.index.str.contains(filter)]

class OverloadReport():
    def __init__(self,settings):
        #self.df = df
        self.settings = settings
        self.settings_xls = {'column_width':7}

    def createReport(self):
        self.downloadData()
        self.transformDf()
        self.dailyReport()
        self.totalReport()
        self.secReport()
        self.mergeReport()
        self.transformToPercent()
        self.renameHeader()

    def renameHeader(self):
        new_cols = []
        ren_dict = {'orders_10s':'10s','orders_1m':'1m','request':'r'}
        for col in self.df_report.columns:
            if type(col) == tuple:
                c0 = col[0]
                c1 = col[1]
                if type(c1) == dt:
                    c1 = c1.strftime('%d.%m')
                for n1,n2 in ren_dict.items():
                    if c0 == n1:
                        c0 = n2
                col = f'{c0}{c1} %'
            new_cols.append(col)
        self.df_report.columns = new_cols

    def transformToPercent(self):
        for base_col in ['orders_10s','orders_1m','cpu']:
            for col in self.df_report.columns:
                if type(col) == tuple:
                    if col[0] == base_col:
                        try:
                            self.df_report[col] = self.df_report[col].fillna(0)
                            self.df_report[col].replace(np.inf,0,inplace=True)
                            self.df_report[col] = \
                                self.df_report[col] / self.df_report[base_col] * 100
                            #self.df_report.loc[self.df_report[col] < 1, col] = 0
                            self.df_report[col] = self.df_report[col].astype(int)
                        except:
                            pass

    def downloadData(self):
        d = DownloadOrdersFromBd(self.settings)
        d.DownloadOverload()
        self.df = d.df

    def transformDf(self):
        df = self.df
        for col in ['cpu','request','orders_1m','orders_10s']:
            df[col] = df[col].astype(int)            
            df.loc[df[col]<=89, col] = 0
            df.loc[df[col]>89, col] = 1
        df['sec'] = df['date'].dt.second
        df['sec'] = df['sec']/10
        df['sec'] = df['sec'].astype(int)*10
        df['date'] = df['date'].dt.date#strftime('%d.%m')
        self.df = df
        
    def dailyReport(self):
        df_agg = self.df.groupby(['date','bot__name'])['orders_1m','orders_10s','cpu'].sum()#'cpu','request',
        self.df_daily = df_agg.unstack(0).reset_index()
        
    def secReportOld(self):
        df_agg = self.df.groupby(['sec','bot__name'])['orders_1m','request'].sum()
        df_agg = df_agg[(df_agg['orders_1m'] > 0) | (df_agg['request'] > 0) ]
        self.df_sec = df_agg.unstack(0).reset_index()

    def secReport(self):
        df_agg = self.df.groupby(['sec','bot__name'])['orders_1m'].sum()
        df_agg = df_agg[(df_agg > 0)]
        df_agg = df_agg.unstack(0).reset_index()
        new_col = []
        for col in df_agg.columns:
            if type(col) != str:
                col = ('orders_1m',col)
                #f'1m{col}'
            new_col.append(col)
        df_agg.columns = new_col
        self.df_sec = df_agg

    def totalReport(self):
        df_agg = self.df.groupby(['bot__name'])['cpu','request','orders_1m','orders_10s'].sum()
        self.df_total = df_agg.reset_index()

    def mergeReport(self):
        df1 = pd.merge(self.df_total, self.df_sec, on='bot__name').reset_index(drop=True)
        self.df_report = pd.merge(df1, self.df_daily, on='bot__name').reset_index(drop=True).\
            sort_values(by=['orders_1m'], ascending=False)

#%%
if __name__ == "__main__":
    settings = {
    'time_line':5,
    'need_reports':'all',
    'time_line1':60,
    'need_metrics':0,
    'user_id':2,
    '-telegram_id':299,
    'strategy_names':['1123'],
    }
    r = GetInfo(settings)
    #r.createHourlyReport()
    #r.getRawData()
    r.createReports()
#%%
# %%
