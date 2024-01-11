#%%
import os
import os.path
import sys
from datetime import timedelta
from datetime import datetime as dtm
import numpy as np
from pprint import pprint as pp
import pandas as pd
import traceback

pd.options.display.expand_frame_repr = False
for path in ['.','./download_data']:
    sys.path.append(os.path.abspath(path))

from bd import DownloadOrdersFromBd
from defs import *
#%%

class StratManager():
    def __init__(self,settings):
        self.settings = settings

    def changeStratType(self):
        d = DownloadOrdersFromBd(self.settings)
        d.getStratId()
        d.getStratTypeId()
        d.setStrategyType()
    
    def getStratsSettings(self):
        self.settings_xls = {'column_width':10,'float_cols':[],'need_pass':1}
        d = DownloadOrdersFromBd(self.settings)
        if 'strategy_names' in self.settings:
            d.getStratId()
        if 'strategy_types' in self.settings:
            d.getStratTypesId()
        d.getStratsSetings()
        self.df = d.df
        self.df.fillna(0, inplace=True)
        self.moveColumns()
        self.renameDuplicateColumns()
        self.delColumnsWithOneUniqValue()
        self.convertColumns()        

    def renameDuplicateColumns(self):
        cols = list(self.df.columns)
        new_cols = []
        for index,col in enumerate(cols):
            if col not in new_cols:
                new_cols.append(col)
            else:
                new_cols.append(f'{col}{index}')
        self.df.columns = new_cols

    def moveColumns(self):
        cols = list(self.df.columns)
        cols.remove('StrategyName')
        cols.insert(0,'StrategyName')
        self.df = self.df[cols]

    def delColumnsWithOneUniqValue(self):        
        hidden_columns = []
        need_hide = ['SilentNoCharts','EmulatorMode']
        if len(self.df) > 0:
            for index,col in enumerate(self.df.columns):
                try:
                    uniq = len(self.df[col].unique())
                except:
                    print(self.df[col])
                if uniq == 1 or col in need_hide:
                    #hidden_columns.append(index)
                    del self.df[col]# else df1.loc['Total',col] = uniq
                    # df1.loc['Total','FVersion'] = 0
        #self.settings_xls['hidden_columns'] = hidden_columns
        self.settings_xls['freeze_panes'] = 1

    def convertColumns(self):
        self.df = self.df.convert_dtypes()
        for index,col in enumerate(self.df.columns):
            try:                
                float_col = pd.to_numeric(self.df[col], downcast='integer')
                int_col = float_col.astype(int)
                self.df[col] = float_col
                if int_col.sum() != float_col.sum():
                    self.settings_xls['float_cols'].append(index)
                continue 
            except:
                pass
            try:
                if self.df[col].str.len().max() > 6:
                    self.df[col] = pd.to_datetime(self.df[col])
                    self.df[col] = self.df[col].dt.strftime('%d.%m.%Y')
                    continue
            except:
                pass
            

#%%


if __name__ == "__main__":
    settings = {
    'telegram_id':299,
    'strategy_names':['*555'],
    'strategy_types1':['DropsDetection'],
    }
    settings1 = {'get_strat_settings': 1, 
    'market': 'futures',
    'strategy_types': ['DropsDetection'],
    'need_reports': False,
    'market_type': 'futures',
    'need_metrics': False, 
    'telegram_id': 299}
    r = StratManager(settings)
    r.getStratsSettings()
#%%
    r.df['Active'].str.len().max()
#%%

    r.df['BV_SV_FilterRatio'].unique()
#%%
    r.settings_xls
#%%
    from strategy.models import Strategy,StrategyType
    request = {'name__in':settings['strategy_names']}
    strats = Strategy.objects.filter(**request).values('name','strategy_type__name')
    for strat in strats:
        print(strat)
# %%
