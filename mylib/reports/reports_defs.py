class Beauty():
    def makeBeauty(self, df_agg):
        '''округлим'''
        if 'usd' in df_agg.columns:
            df_agg['usd'] = df_agg['usd'].astype(int)
            #if df_agg['usd'].max() > 10:
            #    df_agg['usd'] = round(df_agg['usd'],1)
        if 'rate' in df_agg.columns:
            try:
                df_agg['rate'] = df_agg['rate'].fillna(0)
                df_agg['rate'] = df_agg['rate'].astype(int)
            except:
                df_agg.to_csv('bad_df.csv', sep='\t', encoding='utf-8')
                print('Bad df')
                sys.exit()
        return df_agg