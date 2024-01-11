#%%
#%load_ext autoreload
#%autoreload 2
import os
import os.path
import sys

from datetime import timedelta
from datetime import datetime as dtm
import json
from types import new_class
import pandas as pd
from pprint import pprint as pp
import pathlib
file_path = str(pathlib.Path(__file__).parent.resolve())
main_path = file_path[:file_path.find('/mylib')]

sys_path = [main_path,file_path,f'{main_path}/mylib',
            f'{main_path}/mylib/download_data',
            f'{main_path}/django_project']
for path in sys_path:
    sys.path.append(path)

import django
from django.db import connection
from django.db.models.aggregates import Max

os.environ['DJANGO_SETTINGS_MODULE'] = \
    'django_project.settings'
#%%
from defs import *
from calc_real_rate import calcRealRateForJoinedOrders
#%%

from django.db import connection
from django.db.utils import OperationalError
from django.apps import apps
django.setup()
from binancedata.models import FuturesData,FuturesCandles,SpotData,SpotCandles
from orders.models import Orders,OrderTask
from bot.models import User,Bot,Balance,BaseCoin,OrderSaver,Overload,Bans,Balance
from strategy.models import Strategy,StrategyType,StrategySettings
from sets.models import Sets,StratsInSet
from django_pandas.io import read_frame
pd.options.display.expand_frame_repr = False
#%%
class MainDefs():
    def getUserId(self):
        if 'user_id' in self.settings:
            self.user_id = self.settings['user_id']
        elif 'telegram_id' in self.settings:
            try:
                user = User.objects.filter(telegram_id=self.settings['telegram_id']).first()
            except OperationalError:
                connection.close()  
                user = User.objects.filter(telegram_id=self.settings['telegram_id']).first()
            self.user_id = user.id
        else:
            user = User.objects.filter(id=self.user_id).first()
            self.settings['telegram_id'] = user.telegram_id

    def getAllBotsDf(self,request1={},keys1=[]):
        request = {'user_id':self.user_id}
        request.update(request1)
        keys = ['id','name','correct_timezone_date','last_work_date','need_check_work_status']
        keys.extend(keys1)
        self.bots_df = read_frame(Bot.objects.filter(**request).values(*keys))
    
    def changeBot(self,id,new_values):
        request = {'id':id}
        Bot.objects.filter(**request).update(**new_values)

class BinanceData():
    def __init__(self,market,site):
        self.market = market
        self.site = site
        self.chooseMarketTables()

    def chooseMarketTables(self):
        if self.site == 'b':
            if self.market == 'spot':
                self.Seconds = SpotData
                self.Candles = SpotCandles
            else:
                self.Seconds = FuturesData
                self.Candles = FuturesCandles

    def getCoinData(self,pair,start,stop,time_type='seconds',values=[],add_query={}):
        if pair == 'All_coins':
            add_dict = {}
        elif pair.find('*') > -1:
            pair = pair.replace('*','')
            add_dict = {'symbol__endswith':pair}
        elif type(pair) == str:
            add_dict = {'symbol':pair}
        elif type(pair) == list:
            add_dict = {'symbol__in':pair}
        add_dict.update(add_query)
        if time_type == 'seconds':
            if values == []:
                answer = self.Seconds.objects.using('binance_data').filter(\
                    timestamp__gte=start,timestamp__lt=stop,**add_dict).order_by('timestamp')
            else:
                answer = self.Seconds.objects.using('binance_data').filter(\
                    timestamp__gte=start,timestamp__lt=stop,**add_dict).values(*values).\
                    order_by('timestamp')
        else:
            if values == []:
                answer = self.Candles.objects.using('binance_data').filter(\
                    close_time__gte=start,open_time__lt=stop,**add_dict).order_by('open_time')
            else:
                answer = self.Candles.objects.using('binance_data').filter(\
                    close_time__gte=start,open_time__lt=stop,**add_dict).values(*values).\
                    order_by('open_time')
        try:
            self.df = read_frame(answer)
        except Exception as e:
            print('---BD error!')
            print(pair,start,stop,time_type)
            raise e

class AccountBalance(MainDefs):
    def __init__(self):
        pass

    def writeAccountsInfo(self,accounts):
        for account in accounts:
            account['account'] = account['account'][:7]
            Balance.objects.create(**account)
    
    def getAccountsInfo(self,interval):
        start = dtm.utcnow() - timedelta(**interval)
        self.data = read_frame(Balance.objects.filter(date__gte=start))

class BotBans(MainDefs):
    def __init__(self,settings):
        self.settings = settings
        self.getUserId()
        if 'timedelta' not in self.settings:
            self.settings['timedelta'] = {'minutes':5}

    def getBans(self):
        start = dtm.utcnow() - timedelta(**self.settings['timedelta'])
        request = {'user_id':self.user_id,'date__gte':start}
        values = ['bot__name','bot__account','date','moon','binance']
        self.bans_df = read_frame(Bans.objects.filter(**request).values(*values))

    def getBotsInBannedAccounts(self,accounts_list):
        keys = ['id','name','telegram_token','telegram_chat_id','account__name']
        request = {'user_id':self.user_id,'account__in':accounts_list}
        self.bots_df = read_frame(Bot.objects.filter(**request).values(*keys))

class StratSets():
    def changeManualStopedSets(self,id_list,status):
        '''
        вкл/выкл сеты, которые ручками отключены
        '''
        request = {'user_id':self.user_id,'id__in':id_list}
        Sets.objects.filter(**request).update(current_active_status=status,manual_change_date=self.current_time)

    def changeManualStopedStrats(self,id_list,status):
        '''
        вкл/выкл страты, которые ручками отключены
        '''
        request = {'id__in':id_list}
        StratsInSet.objects.filter(**request).update(current_active_status=status,manual_change_date=self.current_time)

    def updateStratList(self,id_list,values):
        '''
        изменить значение в списке страт
        '''
        request = {'id__in':id_list}
        StratsInSet.objects.filter(**request).update(**values)

    def downloadSets(self):
        #self.changeManualStopedSets()
        #request = {'user_id':self.user_id,'current_active_status':True}
        request = {'user_id':self.user_id}
        sets = Sets.objects.filter(**request).values()
        self.sets_id_list =[]
        for s in sets:
            self.sets_id_list.append(s['id'])
        self.sets = read_frame(sets)

    def changeStrat(self,id,new_values):
        request = {'id':id}
        StratsInSet.objects.filter(**request).update(**new_values)

    def changeSet(self,id,new_values):
        request = {'id':id}
        Sets.objects.filter(**request).update(**new_values)

    def updateSet(self,query,vals):
        Sets.objects.filter(**query).update(**vals)

    def createSet(self,values):
        values['user_id'] = User(id=values['user_id'])
        values['bot'] = Bot.objects.all().first()
        s = Sets(**values)
        s.save()

    def createSetStrat(self,values):
        values['strat_set'] = Sets(id=values['strat_set'])
        values['strategy'] = Strategy(id=values['strategy'])
        s = StratsInSet(**values)
        s.save()

    def delSetStrat(self,set_id):
        StratsInSet.objects.filter(strat_set_id=set_id).delete()

    def downloadStatFromSets(self):
        #self.changeManualStopedStrats()
        values = ['id','strat_set__id','strategy__id','strategy__bot__id','strategy__name','strat_set_name','settings','manual_switch',
                'current_manual_status','current_order_size','current_active_status','auto_change_date','penalty_coins','in_top',
                'trigger_key','trigger_by_key']
        #request = {'strat_set__id__in':self.sets_id_list,'current_active_status':True}
        request = {'strat_set__id__in':self.sets_id_list}
        strats = StratsInSet.objects.filter(**request).values(*values)
        self.strats = read_frame(strats)

class ForTest():
    def actualizeBuyDate(self):
        now = dtm.utcnow()
        q = {'id__gt': 0}
        self.orders = StratsInSet.objects.filter(**q)#.update(buy_date=now)

class Strat():
    def getStratId(self):
        if 'strategy_names' in self.settings:
            strat_list = []
            need_remove = []
            for strat_name in self.settings['strategy_names']:
                if strat_name.find('*') > -1:
                    need_remove.append(strat_name)                    
                    strat_name = strat_name.replace('*','')
                    request = {'user_id':self.user_id,'name__contains':strat_name}
                    strats = list(Strategy.objects.filter(**request).values_list('id', flat=True))
                    strat_list.extend(strats)
            for strat_name in need_remove:
                self.settings['strategy_names'].remove(strat_name)
            if len(self.settings['strategy_names']) > 0:
                request = {'user_id':self.user_id,
                        'name__in':self.settings['strategy_names']}
                strats = list(Strategy.objects.filter(**request).values_list('id', flat=True))
                strat_list.extend(strats)
            self.settings['strategy__in'] = strat_list

    def getStratTypesId(self):
        if 'strategy_types' in self.settings:
            request = {'name__in':self.settings['strategy_types']}
            strategy_types = list(StrategyType.objects.filter(**request).\
                values_list('id', flat=True))
            self.settings['strategy_type__in'] = strategy_types
            self.settings['strategy__strategy_type__in'] = strategy_types
            #strat_list = list(Strategy.objects.filter(**request).\
            #    values_list('id', flat=True))
            #self.settings['strategy__in'] = strat_list

    def getStratTypeId(self):
        request = {'name__in':self.settings['strategy_types']}
        strategy_type = list(StrategyType.objects.filter(**request).\
            values_list('id', flat=True))[0]
        self.settings['strategy_type__id'] = strategy_type

    def getStrategyTypesID(self):
        request = {'name__in':self.settings['strategy_types']}
        self.strategy_types_id_list = list(StrategyType.objects.filter(**request).\
            values_list('id', flat=True))

    def getFiltredStrats(self):
        request = {'user_id':self.user_id,'m_orders_cnt__lte':self.settings['m_orders_cnt__lte']}
        if 'strategy_types' in self.settings:
            self.getStrategyTypesID()
            request['strategy_type__in'] = self.strategy_types_id_list
        self.strat_id_list = list(Strategy.objects.filter(**request).values_list('id', flat=True))

    def setStrategyType(self):
        request = {'id__in':self.settings['strategy__in']}
        Strategy.objects.filter(**request).update(strategy_type = self.settings['strategy_type__id'])

    def getStratsSetings(self):
        request = {'user_id':self.user_id,'settings__isnull':False}
        for col in ['site','market_type','strategy__in','strategy_names']:
            if col in self.settings:
                if col == 'strategy__in':
                    req_col = 'id__in'
                elif col == 'strategy_names':
                    req_col = 'name__in'
                else:
                    req_col = col
                request[req_col] = self.settings[col]
        if 'exclude_strats_names' in self.settings:
            ex = self.settings['exclude_strats_names']
            raw_data = Strategy.objects.filter(**request).exclude(name__in=ex).\
                order_by('id').values('id','name','settings')
        else:
            raw_data = Strategy.objects.filter(**request).\
                order_by('id').values('id','name','settings')
        raw_data = read_frame(raw_data)
        self.json_strat_data = list(map(json.loads,raw_data['settings']))
        self.df = pd.DataFrame.from_records(self.json_strat_data)
        self.getSettingsData()
        new_cols = []
        for col in self.df.columns:
            try:
                new_cols.append(self.settings_dict.get(int(col),col))
            except:
                new_cols.append(col)
        self.df.columns = new_cols
        del_col = ['FVersion','#']
        for col in del_col:
            if col in self.df.columns:
                del self.df[col]
        self.df['id'] = raw_data['id']
        self.df['name'] = raw_data['name']

    def getSettingsData(self):
        data = StrategySettings.objects.all().values('id','name','sort_order').order_by('sort_order')
        self.settings_dict = {}
        self.settings_list = []
        for d in data:
            self.settings_dict[d['id']] = d['name']
            self.settings_list.append(d['name'])

    def getAllStratsDf(self):
        request = {'user_id':self.user_id}
        keys = ['name','strategy_type__name','market_type','m_orders_cnt',
            'm_price_step','m_o_size_step','m_o_size_kind',]
        self.strats_df = read_frame(Strategy.objects.filter(**request).values(*keys))

    def getOrdersTask(self):
        keys = ['strategy__name','strategy__id','quantity','add_date']
        request = {
            'user_id':self.user_id,
            'add_date__gte':self.start_date,            
            }
        col = 'strategy__in'
        if col in self.settings:
            request[col] = self.settings[col]
        tasks = OrderTask.objects.filter(**request).values(*keys)
        self.tasks_df = read_frame(tasks)
        new_names = ['strat','strategy__id','task_quantity','buy_date']
        self.tasks_df.columns = new_names

class Overloads():
    def DownloadOverload(self):
        keys = ['bot__name','date','cpu','request','orders_1m','orders_10s']
        self.start_date = getStartDate(self.settings['time_line'])        
        request = {
            'bot__user_id':self.user_id,
            'date__gte':self.start_date,            
            }
        if 'duration' in self.settings:
            request['date__lt'] = self.getEndDate()
        orders = Overload.objects.filter(**request).values(*keys)
        self.df = read_frame(orders)


class DownloadOrdersFromBd(MainDefs,Strat,StratSets,Overloads):    
    def __init__(self,settings,telegram_id=None):
        connection.close()  
        self.settings = settings
        if telegram_id is not None:
            self.settings['telegram_id'] = telegram_id
        self.getUserId()
        #self.load_all_columns = True if settings.get('load_all_columns',0) == 1 \
        #    else False
        self.load_all_columns = False
        
    def getEndDate(self):
        return self.start_date + timedelta(days=self.settings['duration'])

    def getBaseCoins(self):
        self.base_coins = read_frame(BaseCoin.objects.all())


    def downloadLastOrders(self):
        keys = ['bot__name'] 
        start = dtm.utcnow() - timedelta(**self.settings['timedelta'])
        request = {
            'user_id':self.user_id,
            'buy_date__gte':start,            
            }
        orders = Orders.objects.filter(**request).values(*keys).annotate(max_date=Max('buy_date'))
        self.df = read_frame(orders)

    def downloadDataset(self):        
        keys = ['strategy__name','strategy__id','bot__name','strategy__path','strategy__strategy_type__name',
            'strategy__order_size', 'strategy__create_date','strategy__is_active',
            'strategy__join_sell_key',
            'strategy__trigger_key','strategy__trigger_by_key',
            'base_coin__name','site','market_type','buy_price','quantity',
            'coin','profit_percent','profit','order_size_in_settings',
            'sell_reason','sell_condition',
            'buy_date','moonbot_buy_date','order_create_date','close_date','is_short','joined_sell_k','orders_in_net',
            'total_order_nets','id','emulator','orders_list']
            #'btc5m','btc1m','c15m','c5m','c1m','id']
        more_keys = ['market24h','market1h','bvsv_current','btc24h','btc1h',
        'pump1h','dump1h','c24h','c3h','c1h']
        if self.load_all_columns:
            keys.extend(more_keys)
        if 'counted_timedelta' in self.settings:
            self.start_date = dtm.utcnow()- self.settings['counted_timedelta']
        elif 'timedelta' in self.settings:
            self.start_date = dtm.utcnow() - timedelta(**self.settings['timedelta'])
        else:
            self.start_date = getStartDate(self.settings['time_line'])        
        request = {
            'user_id':self.user_id,
            'buy_date__gte':self.start_date,            
            }#'base_coin':self.settings['base_coin_id'],
        if 'base_coin' in self.settings:
            self.getBaseCoins()
            try:
                base_coin = self.base_coins[self.base_coins['name']==\
                    self.settings['base_coin']].iloc[0].get('id',1)
            except:
                base_coin = 1
            request['base_coin'] = base_coin
        if 'strategy_names' in self.settings:
            self.getStratId()
        if 'strategy_types' in self.settings:
            self.getStratTypesId()
        if 'duration' in self.settings:
            request['buy_date__lt'] = self.getEndDate()
        for col in ['site','market_type','strategy__in','strategy__strategy_type__in','buy_date__lte']:
            if col in self.settings:
                request[col] = self.settings[col]
        if 'coins' in self.settings:
            request['coin__in'] = self.settings['coins']            
        if 'exclude_strats_names' in self.settings:
            ex = self.settings['exclude_strats_names']
            orders = Orders.objects.filter(**request).exclude(strategy__name__in=ex).values(*keys)
        else:
            orders = Orders.objects.filter(**request).values(*keys)

        self.df = read_frame(orders)
        new_names = ['strat','strategy__id','bot','strat_path','type','osize','age','active','joinkey','tr_key','tr_b_key',
            'base_coin','site',
            'market_type','buy_price','quantity','coin','profit','profit_usd','order_size_in_settings','sell_reason',
            'sell_condition',
            'buy_date','moonbot_buy_date','order_create_date','close_date','is_short','joined_sell_k','orders_in_net',
            'total_order_nets','bd_row_id','emulator','orders_list']#'btc5m','btc1m','c15m','c5m','c1m',
        if self.load_all_columns:
            new_names.extend(more_keys)
        self.df.columns = new_names
        if self.settings.get('use_create_date',0) == 1:
            print('used_create_date')
            self.df['order_buy_date'] = self.df['buy_date']
            self.df['buy_date'] = self.df['order_create_date']
        self.df['spent_usd'] = self.df['buy_price'] * self.df['quantity']
        #self.df.loc[(~self.df['age'].isna()),'age'] = (dtm.utcnow().date() - self.df['age']).dt.days + 1
        #self.df.loc[(self.df['age'] > 60), 'age'] = 60
        print(f'Downloaded {len(self.df)} rows')
        print('Strats:',self.df['strat'].unique()[:10])
        if len(self.df[(self.df['sell_condition']=='JoinedSell')&(self.df['joined_sell_k'].isnull())]) > 0:
            self.calcRealRateForJoined()        
            self.saveRealRate()
            print('Rate saved')
        self.delBlowout()
        #self.printBlowouts()
        #self.calcRealRateInDF()

    def printBlowouts(self):
        cols = ['buy_date','type','strat','profit','old_profit','q_min','profit_usd','order_size_in_settings','spent_usd','coin']
        if len(self.df) == 0:
            return
        print('largest profit')
        pp(self.df.nlargest(3,'profit')[cols])
        print('smallest profit')
        pp(self.df.nsmallest(5,'profit')[cols])

    def delBlowout(self):
        '''удалим выбросы'''
        df_full = self.df
        df_full['old_profit'] = df_full['profit']
        df_full['q_min'] = 0
        k = 3
        for strat in df_full['strat'].unique():
            qst = [0.05,0.95]
            query = (df_full['strat']==strat)
            df = df_full[query]
            min_percent = -50
            col = 'profit'
            q = list(df[col].quantile(qst))
            if df[col].max() > q[1] * k and df[col].max() > 0:
                df_full.loc[(df_full[col] > q[1] * k) & query,col] = q[1] * k
            if df[col].min() < 0 and abs(df[col].min()) > abs(q[0]) * k:
                min_val = max(q[0] * k, min_percent)
                q_min = (df_full[col].abs() > abs(q[0]) * k) & (df_full[col] < 0) &\
                    (df_full[col] < min_percent) & (df_full[col] < min_val)
                df_full.loc[q_min & query,[col,'q_min']] = [min_val,q[0]]
        self.df = df_full

    def delBlowout_old(self):
        '''удалим выбросы'''
        df_full = self.df
        df_full['old_spent_usd'] = df_full['spent_usd']
        k = 5
        for strat in df_full['strat'].unique():            
            qst = [0.05,0.95]
            query = (df_full['strat']==strat)
            df = df_full[query]
            for col in ['spent_usd']:
                q = list(df[col].quantile(qst))
                if df[col].max() > q[1] * k:
                    df_full.loc[(df_full[col] > q[1] * k) & query,col] = q[1] * k
                if df[col].min() < q[0] / k:
                    df_full.loc[(df_full[col] < q[0] / k) & query,col] = q[0]
        self.df = df_full

    def calcRealRateInDF(self):
        '''пересчет рэйта для Joined в df'''
        #request = (self.df['profit'] < 0) & (~self.df['joined_sell_k'].isnull())
        self.df['old_profit'] = self.df['profit']
        request = (~self.df['order_size_in_settings'].isnull())
        self.df.loc[request,'profit'] = (self.df['profit_usd'] / self.df['order_size_in_settings'])*100
        request = (self.df['order_size_in_settings'].isnull())
        self.df.loc[request,'profit'] = (self.df['profit_usd'] / self.df['spent_usd'])*100
        self.df['profit'] = round(self.df['profit'],1)
        self.df['profit_usd'] = round(self.df['profit_usd'],1)

    def calcRealRateForJoined(self):
        '''подсчет коэффициентов'''
        self.getAllStratsDf()
        c = calcRealRateForJoinedOrders(self.df,self.strats_df)
        c.calcJoinedK(0)
        c.calcJoinedK(1)
        c.addMultiorderData()
        self.df = c.df

    def saveRealRate(self):
        if 'is_new_k' in list(self.df.columns):
            print('len',len(self.df[self.df['is_new_k']==1]))
            for _,row in self.df[self.df['is_new_k']==1].iterrows():
                try:
                    u_data = {}
                    for val in ['joined_sell_k','orders_in_net','total_order_nets','order_size_in_settings']:
                        u_data[val] = row[val]
                    Orders.objects.filter(id=row['bd_row_id']).update(**u_data)
                except:
                    pass

    def formatDf(self):
        '''отформатируем файл'''        
        df = self.df
        #df['pr_plus'] = df['profit']
        #df['pr_minus'] = df['profit']
        df.loc[(df['profit'] >= 0), 'pr_plus'] = df['profit']
        df.loc[(df['profit'] < 0), 'pr_minus'] = df['profit']
        for reason in set(df['sell_reason'].unique())-set(['SLoss']):
            df.loc[(df['sell_reason']==reason),reason] = 1
        df['SL_plus'] = None
        df.loc[((df['sell_reason']=='SLoss') & (df['profit'] <= 0)),'SLoss'] = 1
        df.loc[((df['sell_reason']=='SLoss') & (df['profit'] > 0)),'SL_plus'] = 1
        self.df = df
        df['date'] = df['buy_date'].dt.date
        df['runtime'] = (df['close_date'] - df['buy_date']).dt.total_seconds().astype(int)
        self.df = df

#%%
if __name__ == "__main__":
    settings = {
    'time_line':1,
    'need_reports1':['strat','coin','coin_strat'],
    'need_reports':'strat',
    'market_type':'futures',
    'strategy_names':['123'],
    'base_coin_id':1,
    'time_line':10,
    'need_metrics':0,
    'top':5,
    'telegram_id':299,
    }
    settings = {
    'time_line':60,
    'need_reports':'strat',
    'strategy_names':['556','334'],
    'user_id':1,
    }
    telegram_id = None
    d = DownloadOrdersFromBd(settings,telegram_id)
    d.downloadDataset()
    #%%
   