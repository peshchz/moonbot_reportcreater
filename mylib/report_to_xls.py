
#%%
import xlsxwriter
from datetime import timedelta
from datetime import datetime as dtm
import pandas as pd
import pandas.io.formats.excel

class OldXlsVersion():
    def createEmptyFile(self):
        self.workbook = xlsxwriter.Workbook(self.xls_name)
        xls = self.workbook.add_worksheet()
        xls.set_column(0,0,25)
        weight = self.settings.get('column_width',5)
        xls.set_column(1,400,weight)
        self.xls = xls
    
    def writeHeader(self,col_name,second_col=None):
        row = self.first_table_row - 1
        col = self.column_num
        if second_col is None:
            self.xls.write(row,col,col_name,self.decor['gray_f'])
        else:
            if type(second_col) == int:
                second_col = str(second_col)
            elif type(second_col) != str:
                second_col = second_col.strftime('%d.%m')
            self.xls.write(row,col,second_col,self.decor['gray_f'])
            if self.current_header != col_name:
                self.current_header = col_name
                self.xls.write(row-1,col,col_name,self.decor['gray_f'])

    def writeColumn(self,col_name):
        values = self.df[col_name].values
        text = False
        self.previous_cell = None
        if type(col_name) == tuple:
            col_name = col_name[0]
        if col_name in ['Strategy','file','Coin']:
            self.style = {}
            text = True            
        elif col_name in ['1_order','pr_factor','q_index','loss_avg','non_prof_k']:
            style = self.decor['percent_format']
        elif col_name.find(',') > -1 and col_name.find('Run') == -1:
            style = self.decor['percent_format2']
        else:
            style = self.decor['value_format']
        i = self.first_table_row
        for v in values:
            args = [i,self.column_num,v]
            #if v == 0:
            #    i += 1
            #    continue
            if text == True:
                self.cell = v
                self.paintStrategy(col_name)
                self.xls.write(*args,self.style)
            else:
                try:
                    self.xls.write_number(*args,style)
                except:
                    try:
                        self.xls.write(*args)
                    except:
                        pass   
            i += 1

    def paintStrategy(self,col_name):
        styles = [{},self.decor['gray_f']]
        if col_name == 'Strategy' and self.paint_strats:
            if self.cell != self.previous_cell:
                self.previous_cell = self.cell
                styles.remove(self.style)
                self.style = styles[0]#сменим стиль

    def paintCells(self,col_name):
        def createQuantile(col):           
            qst_plus = [0.5,0.7]
            qst_minus = [0.3,0.5]
            q_plus = list(col.loc[col>0].quantile(qst_plus).dropna())
            q_minus = list(col.loc[col<0].quantile(qst_minus).dropna())
            if len(q_plus) == 0:
                q_plus = [0,0.1]
            if len(q_minus) == 0:
                q_minus = [-0.1,0]
            return q_plus,q_minus
            
        q_p,q_m = createQuantile(self.df[col_name])
        self.q_p = q_p
        self.q_m = q_m
        criterias = [
            {'type': 'cell','criteria': '>=','value': q_p[1],'format': self.decor['green_l']},
            {'type': 'cell','criteria': '<=','value': q_m[0],'format': self.decor['red_l']},
            ]
            #{'type': 'cell','criteria': 'between','minimum': q_m[0],'maximum': q_m[1],
            #    'format': self.decor['red_l']},
        for c in criterias:
            args = [self.first_table_row,self.column_num,
                len(self.df)+self.first_table_row,self.column_num, c]
            self.xls.conditional_format(*args)
    
    def paintUsd(self):
        criteria = {'type': 'cell','criteria': '<=','value': -2,'format': self.decor['red_l']}
        args = [self.first_table_row,self.column_num,
                len(self.df)+self.first_table_row,self.column_num, criteria]
        self.xls.conditional_format(*args)

    def hideColumn(self,start,stop=None):
        if stop is None:
            stop = start
        self.xls.set_column(start,stop,None,None,{'level':1,'hidden':1})

    def writeXls(self):
        self.createEmptyFile()
        self.setDecors()
        df = self.df.copy()
        self.current_header = None
        for col in df.columns[:self.len_agg]:
            self.writeHeader(col)
            self.writeColumn(col)
            if col == 'rate':
                self.paintCells(col)
            if col == 'usd':
                self.paintUsd()
            if col in ['joinkey','tr_key','tr_b_key','BVSV','SLoss','SL_plus','SellPr','Trail',\
                'PrDown','SellLvl','Other','NoData','FiltCheck','Panic','Jsell','q_index']:
                self.hideColumn(self.column_num)
            self.column_num += 1
        last_col = None
        for col in df.columns[self.len_agg:]:
            #*col == name,date
            if type(col) == str:
                if col.find(',') > -1:
                    self.writeHeader(*col.split(','))
                    last_col = self.column_num
                else:
                    self.writeHeader(col)
            else:
                self.writeHeader(*col)            
            self.writeColumn(col)
            if col[0] == 'rate':
                self.paintCells(col)
            if col[0] == 'usd':
                self.paintUsd()
            self.column_num += 1

        if self.settings.get('paint_way',0) == 'horizontal' and \
            self.settings.get('paint_type',0) == '3_color_scale':
            self.paintHorizontal3Color()
        if last_col is not None:
            start,stop = self.len_agg,last_col
            self.hideColumn(start,stop)
        self.hideColumns()
        self.freezePanes()
        self.decorColumns()
        self.xls.autofilter(1, 0, len(df), len(df.columns))
        self.workbook.close()

class CreateXlsReport(OldXlsVersion):
    def __init__(self,df,len_agg,xls_name,paint_strats=False,settings={}):
        self.df = df.loc[:,~df.columns.duplicated()].copy()
        self.len_agg = len_agg
        self.column_num = 0
        self.first_table_row = 2
        self.settings = settings
        self.xls_name = xls_name
        self.paint_strats = paint_strats

    def setDecors(self):
        workbook = self.workbook
        decor = {}
        decor['bold'] = workbook.add_format({'bold': 1})
        decor['value_format'] = workbook.add_format({'num_format': '### ###'})
        #decor['value_f_gray'] = decor['value_format'].set_bg_color('#D3D3D3')
        decor['date_format'] = workbook.add_format(
            {'num_format': 'dd.mm','align': 'left','bg_color': '#D3D3D3'})
        #decor['percent_format'] = workbook.add_format({'num_format': '0.0%'})
        decor['percent_format'] = workbook.add_format({'num_format': '0.0'})
        decor['percent_format2'] = workbook.add_format({'num_format': '0.00'})
        gray_f = workbook.add_format()
        gray_f.set_pattern(1)  # This is optional when using a solid fill.
        gray_f.set_bg_color('#D3D3D3')
        decor['gray_f'] = gray_f
        #cells
        decor['green'] = workbook.add_format({'bg_color': '#50EE50'})#'font_color': '#9C0006'
        decor['green_l'] = workbook.add_format({'bg_color': '#AEF8AE'})
        decor['red'] = workbook.add_format({'bg_color': '#FF7E93'})
        decor['red_l'] = workbook.add_format({'bg_color': '#FFC7CE'})
        self.decor = decor

    def setColumnsSize(self):
        self.xls.set_column(0,0,25)
        weight = self.settings.get('column_width',7)
        self.xls.set_column(1,400,weight)

    def decorColumns(self):
        for col in self.settings.get('float_cols',[]):
            style = self.decor['percent_format']
            self.xls.set_column(col,col,None,style)
        for col in self.settings.get('integer_cols',[]):
            style = self.decor['value_format']
            self.xls.set_column(col,col,None,style)
        if 'integer_cols_names' in self.settings:
            style = self.decor['value_format']
            for index,col in enumerate(self.df.columns):
                if col in self.settings['integer_cols_names']:
                    self.xls.set_column(index,index,None,style)

    def decorHeader(self):
        row_num = 0
        self.xls.set_row(row_num,None,self.decor['gray_f']) 

    def writeMyDf(self):        
        pandas.io.formats.excel.ExcelFormatter.header_style = None
        writer = pd.ExcelWriter(self.xls_name, engine='xlsxwriter')
        self.df.to_excel(writer, sheet_name='Sheet1',index=False)
        self.workbook  = writer.book
        self.xls = writer.sheets['Sheet1']
        self.setColumnsSize()

    def hideColumns(self):
        columns = self.settings.get('hidden_columns',[])
        if columns == []:
            return
        start = columns[0]
        end = -1
        for col in columns:
            if col - 1 == end:
                end = col
            else:
                self.xls.set_column(start,end,None,None,{'level':1,'hidden':1})
                start,end = col,col
        self.xls.set_column(start,end,None,None,{'level':1,'hidden':1})

    def writeXlsV2(self):
        self.writeMyDf()
        self.setDecors()

        if self.settings.get('paint_way',0) == 'horizontal' and \
            self.settings.get('paint_type',0) == '3_color_scale':
            self.paintHorizontal3Color()

        self.hideColumns()
        self.freezePanes()
        self.decorColumns()
        self.decorHeader()
        self.xls.autofilter(0, 0, len(self.df), len(self.df.columns))
        self.workbook.close()

    def freezePanes(self):
        if self.settings.get('freeze_panes',0) != 0:
            self.xls.freeze_panes(1,1)

    def paintHorizontal3Color(self):
        start = self.settings['hour_columns']['start']
        stop = self.settings['hour_columns']['stop']
        for row in range(self.first_table_row,len(self.df)+self.first_table_row):
            criteria = {'type': '3_color_scale','min_color': '#f8696b','max_color': '#63be7b', 'mid_color':'#ffeb84'}
            args = [row,start,row,stop, criteria]
            self.xls.conditional_format(*args)


if __name__ == "__main__":
    
    df = r.df
    r.len_agg = 2
    settings = r.settings_xls
    file_name = 'xls-report.xlsx'
    x = CreateXlsReport(df,r.len_agg,file_name,0,settings)
    x.writeXlsV2()
    #x.writeXls()
    print('Done')
#%%

