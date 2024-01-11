#%%
import os
import sys
import traceback
from pprint import pprint as pp
import requests

from data.report_bot_settings import TOKEN

from datetime import datetime as dtm
from datetime import timedelta
import requests
from glob import glob

import telebot
from telebot import types
import warnings
warnings.filterwarnings('ignore')

for path in ['./mylib','./mylib/download_data','./set_master']:
    sys.path.append(os.path.abspath(path))
from report_creater import Analitics,GetInfo,OverloadReport
from mylib.report_to_xls import CreateXlsReport
from mylib.strats_manager import StratManager
#from set_master.set_test_if import SetTestIf

from bd import DownloadOrdersFromBd

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()

def createPath(path):
    if not os.path.exists(path):
        os.makedirs(path)

class ParceSettings():
    def replaceInRawTxt(self):
        replaces_list = ['/s_','/f_']
        for k in replaces_list:
            if self.txt.find(k) > -1:                
                days = int(self.txt.split('_')[1])
                replaces = {'/s_':f'market=s;time_line={days};reports=strat',
                        '/f_':f'market=f;time_line={days};reports=strat'}
                self.txt = replaces[k]
                return

    def parceTxt(self):
        def createList(txt):
            if txt.find(',') > -1:
                txt = list(txt.split(','))
            elif txt.find('\n') > -1:
                txt = list(txt.split('\n'))
            return txt
        def transformDataType(txt):
            if txt == 'None':
                txt = None
            elif txt.isdigit():
                txt = int(txt)
            elif txt.lstrip('-').isdigit():
                txt = int(txt) 
            return txt
        pairs = self.txt.split(';')
        self.settings = {'n_cores_multiprocessing':n_cores_multiprocessing}
        for pair in pairs:
            k,v = pair.split('=')
            v = v.strip()
            v = createList(v)
            if type(v) == list:
                for index,val in enumerate(v):
                    v[index] = transformDataType(val)
            else:
                v = transformDataType(v)
            self.settings[k.strip()] = v

    def replaceInSettings(self):
        for k,v in {'s':'spot','f':'futures'}.items():
            if self.settings.get('market',False) == k:
                self.settings['market'] = v
        keys = ['strategy_names','good_hours','bad_hours','medium_hours',
            'profit_interval1', 'profit_interval2','profit_interval3','min_profit_percent1',
            'min_profit_percent2','min_profit_percent3','turbo_profit_percent1',
            'turbo_order_size1','turbo_profit_percent2','turbo_order_size2',
            'penalty_timeout','penalty_profit','penalty_interval']
        for name in keys:
            if type(self.settings.get(name,[])) != list:
                self.settings[name] = [self.settings[name]]            
        self.settings['need_reports'] = self.settings.get('reports',False)
        self.settings['market_type'] = self.settings.get('market',False)
        self.settings['need_metrics'] = self.settings.get('metrics',False)

    def createSettings(self,txt):
        self.txt = txt
        self.date = dtm.now().strftime('%m-%d-%H-%M')
        self.replaceInRawTxt()
        try:
            self.parceTxt()
        except:
            return False
        self.workWithStrategyTypes()
        self.replaceInSettings()
        return True
        
    def workWithStrategyTypes(self):
        if 'set_strat_type' in self.settings:
            self.settings['strategy_types'] = self.settings['set_strat_type']
        if 'strategy_types' in self.settings:
            if type(self.settings['strategy_types']) == str:
                self.settings['strategy_types'] = [self.settings['strategy_types']]
            replaces = {'d':'DropsDetection','e':'EMA'}
            for i,val in enumerate(self.settings['strategy_types']):
                if val in replaces:
                    self.settings['strategy_types'][i] = replaces[val]

class ReportCreater(ParceSettings):
    def __init__(self,bot,token):
        self.bot = bot
        self.token = token
        self.path = '/home/strategy_reports/'
        self.outcoming = '{}outcoming_files/'.format(self.path)
        self.report_path = {}
        self.file_name = {}

    def changeStratType(self,message):
        print(self.settings)
        r = StratManager(self.settings)
        r.changeStratType()

    def getStratSettings(self,message):
        print(self.settings)
        r = StratManager(self.settings)
        r.getStratsSettings()
        chat_id = message.chat.id
        self.file_name[chat_id] = '{}{}-strat_settings.xlsx'.\
            format(self.report_path[chat_id],self.date)
        x = CreateXlsReport(r.df,2,self.file_name[chat_id],0,r.settings_xls)
        x.writeXlsV2()
        self.sendReport(chat_id)
        print('StratSettings is ready')

    def getRawData(self,message):
        chat_id = message.chat.id
        r = GetInfo(self.settings,chat_id)
        r.getRawData()
        self.file_name[chat_id] = '{}{}-{}-raw_data.xlsx'.\
            format(self.report_path[chat_id],self.date,self.settings['time_line'])
        x = CreateXlsReport(r.df,1,self.file_name[chat_id],0,r.settings_xls)
        x.writeXls()
        self.sendReport(chat_id)
    
    def createOverloadReport(self,message):
        r = OverloadReport(self.settings)
        r.createReport()
        chat_id = message.chat.id
        date = dtm.now().strftime('%m-%d-%H-%M')
        self.file_name[chat_id] = '{}{}-overload.xlsx'.format(self.report_path[chat_id],date)
        x = CreateXlsReport(r.df_report,2,self.file_name[chat_id],0,r.settings_xls)
        x.writeXls()
        self.sendReport(chat_id)
        print('Overload Report is ready')

    def createHourlyReport(self,message):
        chat_id = message.chat.id
        print(self.settings)
        r = GetInfo(self.settings,chat_id)
        r.createHourlyReport()
        records = len(r.df)
        text = f'Выгружено записей: {records}'
        bot.send_message(chat_id, text)
        date = dtm.now().strftime('%m-%d-%H-%M')
        duration = self.settings.get('duration','')
        if len(r.hourly_reports) == 0:
            bot.send_message(chat_id, 'Выгружено записей 0')
            return
        for report_name,report in r.hourly_reports.items():
            self.file_name[chat_id] = '{}{}-{}-{}days-hourly.xlsx'.\
                    format(self.report_path[chat_id],date,report_name,self.settings['time_line'])
            x = CreateXlsReport(report['df'],r.len_agg,self.file_name[chat_id],0,report['settings'])
            x.writeXls()
            self.sendReport(chat_id)
        print('HourlyReport is ready')

    def preparePath(self,chat_id):
        self.report_path[chat_id] = '{}{}/'.format(self.outcoming,chat_id)
        createPath(self.report_path[chat_id])

    def createReport(self,message):
        chat_id = message.chat.id
        self.preparePath(chat_id)
        r = GetInfo(self.settings,chat_id)
        r.createReports()
        date = dtm.now().strftime('%m-%d-%H-%M')
        text = f'Выгружены данные за {r.data_interval}'
        bot.send_message(chat_id, text)
        for name,df in r.report.items():
            paint_strat = 1 if name == 'coin_strat' else 0
            self.file_name[chat_id] = '{}{}-{}-{}.xlsx'.\
                format(self.report_path[chat_id],self.settings['market_type'],date,name)
            x = CreateXlsReport(df,r.len_agg,self.file_name[chat_id],paint_strat)
            x.writeXls()
            self.sendReport(chat_id)         
        try:
            pass
        except:
            bot.send_message(chat_id, 'Что-то пошло не так')

    def sendReport(self,chat_id):
        doc = open(self.file_name[chat_id], 'rb')
        bot.send_document(chat_id, doc)


rep = ReportCreater(bot,TOKEN)

#%%
# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.send_message(message.chat.id, """
Помощь
Стандартный отчет по стратегиям
market=f;time_line=5;reports=strat
                     
Стандартный отчет по стратегиям + разбивка по монетам
market=f;time_line=5;reports=all

Отчет по стратегиям с почасовой разбивкой
market=f;hourly=1;time_line=7;top=5
                     
Настройки стратегий
get_strat_settings=1;market=f
                     
Выгрузка трейдов по стратегии (исходные данные)
get_raw_data=1;market=f;time_line=7

Во все запросы можно добавить дополнительные условия
                     
duration=2 - выведутся только 2 дня, начиная с самого первого, который будет в time_line. 
Для time_line=10 и duration=2 выведутся данные за 10 и 9 день
strategy_names=*AAA - выведутся стратегии, содержащие AAA в названии      
strategy_names=AA1
AA2 - выведутся стратегии AA1 и AA2. Можно так же через запятую передавать
strategy_types=DropsDetection - выведутся только Дропсы
coins=BTC,ETH - список монет, которые попадут в отчет

например
market=f;time_line=30;reports=strat;duration=2;strategy_names=AA1,AA2;coins=BTC
выведутся данные за 30 и 29 день назад по стратегиям AA1,AA2. Только по BTC
""")
"""
market=f;time_line=5;reports=strat;metrics=1 - \
при использовании metrics выведутся данные для модификаторов

"""

@bot.message_handler(commands=['today','1day_ago'])
def report_today(message):
    if message.text == '/today':
        settings = {'time_line':0}
    elif message.text == '/1day_ago':
        settings = {'time_line':1,'duration':1}
    chat_id = message.chat.id
    r = GetInfo(settings,chat_id)
    r.createReview()        
    bot.send_message(chat_id,r.review_txt)


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    chat_id = message.chat.id
    if not rep.createSettings(message.text):
        bot.send_message(chat_id, 'Настройки переданы некоректно. См примеры /help')
        return
    rep.preparePath(chat_id)
    rep.settings['telegram_id'] = chat_id

    if rep.settings.get('hourly',0) != 0:
        bot.send_message(chat_id, 'Формирую отчет')
        rep.createHourlyReport(message)
    elif rep.settings.get('get_strat_settings',0) != 0:
        rep.getStratSettings(message)
    elif rep.settings.get('get_raw_data',0) != 0:
        bot.send_message(chat_id, 'Для удобства Profit,% умножен на 10')
        rep.getRawData(message)
    else:
        bot.send_message(chat_id, 'Формирую отчет')
        rep.createReport(message)
        print('Done')

	#bot.reply_to(message, message.text)

#%%
print('Poling')
bot.polling(True)

#%%