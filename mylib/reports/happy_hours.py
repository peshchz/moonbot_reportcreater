#%%
import pandas as pd
import numpy as np
import sys
#%%
class StratByHours():
    def __init__(self,df,settings):
        self.df = df
        self.settings = settings
        self.settings_xls = {
            'paint_way':'horizontal',
            'paint_type':'3_color_scale',
            'column_width':4,
            }

    def calcQuantileSteps(self,date_df):
        qst_plus = [0,0.33,0.66,1]
        qst_minus = [0,0.33,0.66]
        self.ratings = [-3,-2,-1,1,2,3]

        qst_plus = [0,0.55,1]
        qst_minus = [0,0.55]
        self.ratings = [-2,-1,1,2]
        prft = date_df['rate']
        q_plus = prft.loc[prft>=0].quantile(qst_plus).dropna()
        q_minus = prft.loc[prft<0].quantile(qst_minus).dropna()   
        self.quint_steps = list(pd.concat([q_minus,q_plus]))

    def calcQuantiles(self,agg_type):
        #here best way https://dfedorov.spb.ru/pandas/%D0%A0%D0%B0%D0%B7%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85%20%D0%B2%20Pandas%20%D1%81%20%D0%BF%D0%BE%D0%BC%D0%BE%D1%89%D1%8C%D1%8E%20qcut%20%D0%B8%20cut.html
        prft = self.df_hour['rate']
        dates = self.df_hour['date']
        types_sl = self.df_hour['type_sl']
        col = 'quint'
        for date in list(dates.unique()):
            for type_sl in types_sl:
                date_df = self.df_hour[(self.df_hour['date']==date) & (self.df_hour['type_sl']==type_sl)]
                self.calcQuantileSteps(date_df)
                steps = self.quint_steps
                for i in range(len(steps)-1):
                    if i == len(steps)-2:
                        query = ((prft >= steps[i]) & (dates == date) & (types_sl == type_sl))
                    else:
                        query = ((prft >= steps[i]) & (prft <= steps[i+1]) & (dates == date) & (types_sl == type_sl))
                    self.df_hour.loc[query,col] = self.ratings[i]
        self.df_hour[col] = self.df_hour[col].astype(int)
        self.df_hour['quint_plus'] = 0
        self.df_hour.loc[self.df_hour['quint']>0,'quint_plus'] = self.df_hour['quint']
        #self.df_hour['quint_index'] = self.df_hour['quint_plus'] / self.df_hour['quint']
        self.df_hour = self.df_hour.set_index(['hour',agg_type,'date'])

    def filterTopStrats(self):
        top = self.settings['top']
        query = {
            'rate': pd.NamedAgg(column = 'profit', aggfunc = 'sum'),
            }
        df_agg = self.df.groupby(['strat','type_sl']).agg(**query).reset_index()
        self.strat_list = []
        for strat_type in df_agg['type_sl'].unique():
            largest = df_agg[df_agg['type_sl']==strat_type].nlargest(top, ['rate'])
            self.strat_list.extend(list(largest['strat'].unique()))
        self.df = self.df[self.df['strat'].isin(self.strat_list)]

    def prepareMainDF(self):
        print('len(self.df)',len(self.df))
        self.df['hour'] = self.df['buy_date'].dt.hour
        self.df['date'] = self.df['buy_date'].dt.date
        self.df.loc[self.df.is_short==True, 'type_sl'] = self.df.type + '_s'
        self.df.loc[self.df.is_short==False, 'type_sl'] = self.df.type + '_l'
        #self.df['day_of_week'] = self.df['date'].dt.day_name()

    def calcHourly(self,group_keys):
        query = {'rate': pd.NamedAgg(column = 'profit', aggfunc = 'sum'),
            'rate_plus': pd.NamedAgg(column = 'pr_plus', aggfunc = 'sum'),}
        self.df_hour = self.df.groupby(group_keys).agg(**query).reset_index()
        #self.df_hour['rate_index'] = self.df_hour['rate_plus'] / self.df_hour['rate']
        self.df_hour = self.addStratTypeColumn(self.df_hour)
        self.addDayOfWeek()

    def addStratTypeColumn(self,df):
        if 'type_sl' not in df.columns:
            df = pd.merge(df, self.strats_df,
                            on='strat',how='left')

            df.drop(['index'],errors = 'ignore')
        return df

    def createStratslDF(self):
        query = {
            'type_sl': pd.NamedAgg(column = 'type_sl', aggfunc = 'max'),}
        self.strats_df = self.df.groupby('strat').agg(**query).reset_index()

    def getHourColumnPositions(self):
        columns = list(self.df_agg.columns)
        start = columns.index(0)
        stop = columns.index(23)
        self.settings_xls['hour_columns'] = {'start':start,'stop':stop}

    def addDayOfWeek(self):
        df = self.df_hour.reset_index()
        df['day_of_week'] = df['date'].astype({'date':'datetime64[ns]'}).\
            dt.day_name()
        df['day_of_week1'] = (df['date'].astype({'date':'datetime64[ns]'}).\
            dt.dayofweek)
        df['week_n'] = (df['date'].astype({'date':'datetime64[ns]'}).\
            dt.week)
        self.df_hour = df

    def calcProfitIndex(self,df):
        for col in ['rate','quint']:
            df[f'{col}_index'] = df[f'{col}_plus'] / df[col]
            df[f'{col}_index'] = df[f'{col}_index'].round(decimals=1)
        return df

    def calcTotalInAllDf(self):
        for df_name in ['df_hour','df_week_days','df_total','df_week_n']:
            df = getattr(self,df_name)
            df = self.calcHourlyTotal(df)
            df = self.calcProfitIndex(df)
            df = df.drop('index',1)
            setattr(self,df_name,df)

    def calcHourlyTotal(self,df):
        df_total_daily = df.groupby(['strat','date'])[self.cols].\
            sum().reset_index()
        df_total_daily['hour'] = 'total'
        df_total_daily = df_total_daily.reset_index().set_index(self.index_cols)
        df = pd.concat([df,df_total_daily])
        return df
        
    def calcWeekDays(self):
        self.df_week_days = self.df_hour.groupby(['strat','hour','day_of_week1'])\
            [self.cols].sum().reset_index()
        self.df_week_days['date'] = self.df_week_days['day_of_week1'].astype(int).astype(str) +\
            '_w_day'
        self.df_week_days.set_index(self.index_cols,inplace=True)

    def calcWeekNumber(self):
        self.df_week_n = self.df_hour.groupby(['strat','hour','week_n'])\
            [self.cols].sum().reset_index()
        self.df_week_n['date'] = self.df_week_n['week_n'].astype(int).astype(str) +\
            '_week_n'
        self.df_week_n.set_index(self.index_cols,inplace=True)

    def calcStratTotal(self):
        self.df_total = self.df_hour.groupby(['strat','hour'])[self.cols].sum().\
            reset_index()
        self.df_total['date'] = 'total'
        self.df_total.set_index(self.index_cols,inplace=True)

    def groupDfsAndPivot(self):
        cols = ['rate','rate_index','quint','quint_index']
        dfs = []
        for df_name in ['df_hour','df_week_days','df_total','df_week_n']:
            df = getattr(self,df_name)
            df = df[cols].unstack(0).stack(0)
            df['type'] = df_name.replace('df_','')
            dfs.append(df)            
        self.df_agg = pd.concat(dfs).reset_index()

    def datesToStr(self):
        df_agg = self.df_agg
        df_agg['date1'] = pd.to_datetime(df_agg['date'], errors='coerce')
        df_agg.loc[~df_agg['date1'].isnull(),'date'] = df_agg['date1'].dt.strftime('%d.%m.%Y')
        df_agg.drop('date1',1,inplace=True)

    def createReport(self):
        '''группировка'''
        self.prepareMainDF()
        self.createStratslDF()
        if 'top' in self.settings:
            self.filterTopStrats()
        self.df_report = {}
        self.cols = ['rate','rate_plus','quint','quint_plus']
        for agg_type in ['strat']:#'type_sl']:
            for time in ['date']:#,'day_of_week']:
                #agg_set = ['type_sl'] if agg_type == 'type_sl' else ['type_sl','strat']
                self.index_cols = ['hour',agg_type,time]
                self.calcHourly(self.index_cols)
                #sort_cols = [agg_type,time]
                #self.df_agg = self.df_agg.sort_values(by=sort_cols, ascending=[False,False])#.reset_index()
                self.calcQuantiles(agg_type)                
                self.calcWeekDays()
                self.calcWeekNumber()
                self.calcStratTotal()
                self.calcTotalInAllDf()
                self.groupDfsAndPivot()
                self.getHourColumnPositions()
                self.df_agg.columns = map(str, list(self.df_agg.columns))
                self.datesToStr()
                self.df_agg = self.addStratTypeColumn(self.df_agg)
                self.df_report[agg_type] = {'df':self.df_agg,'settings':self.settings_xls}



#%%
if __name__ == "__main__":
    settings = {
    'time_line':2,
    'need_reports':'strat',
    'time_line1':60,
    'need_metrics':0,
    'telegram_id':299,
    'strategy_names':['50'],
    }
    r = GetInfo(settings)
    r.createHourlyReport()
#%%
    df_hour[df_hour.index.get_level_values(-1).str.startswith('weekly', na=False)][cols].unstack(0).stack(0)
# %%
