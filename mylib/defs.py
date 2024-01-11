import argparse
from datetime import date as dt
from datetime import datetime as dtm
import pytz
from datetime import timedelta
import os
import shutil
import pandas as pd
import json

def parseArgs():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--strat', '-s', type=str)
        parser.add_argument('--interval', '-i', type=int)
        parser.add_argument('--dflen', '-l', type=int) #размер df для тестирования
        parser.add_argument('--from_file', '-f', type=int) #взять из файла статистику
        all_args = vars(parser.parse_args())
        print(all_args)
        args = {}
        for k,v in all_args.items():
            if v is not None:
                args[k] = v
        if args['strat'] is not None:
            args['strat'] = args['strat'].split(',')
            print(args)
            return args
        else:
            print('Введите стратегию для анализа. -s')
            return None
    except:
        return None

def nowString():
    return dtm.now().strftime('%m-%d %H:%M')

def printTread0(tread,*txt):
    if tread!=0:
        return
    print(*txt)
#%%
def createPath(path,need_files_path=True):
    if not os.path.exists(path):
        os.makedirs(path)
        #for p in ['files','filters','chart']:
        if need_files_path:
            for p in ['files']:
                os.makedirs('{}{}/'.format(path,p))
                    
# %%
def createZip(path,output_file_with_path):
    shutil.make_archive(output_file_with_path, 'zip', path)
# %%
def concatDF(df1,df2):
    if df1 is None:
        df1 = df2.copy()
    else:
        df1 = pd.concat([df1,df2])
    return df1

def normalizeDFList(lst):
    '''Преобразовать список из панды для джанго'''
    lst=list(lst)
    lst.sort()
    return list(map(int,lst))

def getNonNanUniqueValues(df,col):
    return df[df[col].notna()][col].unique()

def convertPDListToJson(lst):
    '''Преобразовать список из панды в json'''
    lst=list(lst)
    lst.sort()
    return json.dumps(list(map(int,lst)))

def saveDfToXlsx(df,file_name):
    try:
        for col in df.select_dtypes(include=['datetime64[ns, UTC]']).columns:
            df.loc[~df[col].isnull(),col] = df[col].dt.tz_localize(None)
        df_max_size = 500000
        df[:df_max_size].to_excel(file_name)
    except:
        print('Cant save file',file_name)

def toTimestamp(date):
    if type(date) == pd._libs.tslibs.timestamps.Timestamp:
        return int(date.timestamp() * 1000)
    #date.timestamp() конвертирует с учетом часового пояса
    if date.tzinfo == pytz.utc:
        epoch = dtm(1970,1,1).replace(tzinfo=pytz.utc)
    else:
        epoch = dtm(1970,1,1)
    return int((date - epoch).total_seconds() * 1000)

def utcFromTimestamp(date):
    return dtm.utcfromtimestamp(date/1000)

def getStartDate(time_line):
    '''Выведем время с начала дня UTC'''
    start_date = dtm.utcnow().\
        replace(hour=0, minute=0, second=0,microsecond=0) - \
        timedelta(days=time_line)
    return start_date

def localizeColsInDF(df1):
    df = df1.copy()
    for col in df.select_dtypes(include=['datetime64[ns, UTC]']).columns:
        df.loc[~df[col].isnull(),col] = df[col].dt.tz_localize(None)
    return df
#%%