import numpy    as np;
import pandas   as pd;
import altair   as alt;
import chardet
import calendar

#   dados
DATA: str = r"data/arrecadacao-estado.csv"

def clean_currency(col):
    # Se a coluna já for numérica, retorna sem alteração
    if pd.api.types.is_numeric_dtype(col):
        return col

    # Converte para string e remove espaços
    col = col.astype(str).str.strip()
    
    # Remove qualquer caractere que não seja dígito, vírgula ou ponto
    col = col.str.replace(r'[^\d,.]', '', regex=True)
    
    # Substitui vírgula (separador decimal) por ponto
    col = col.str.replace(',', '.', regex=False)
    
    # Função para converter cada valor, tratando pontos de milhar
    def convert_value(x):
        if x == '' or pd.isna(x):
            return np.nan
        # Separa por pontos
        parts = x.split('.')
        if len(parts) == 1:
            # Não tem ponto decimal (ex: '47953915')
            return float(parts[0])
        else:
            # Último segmento é a parte decimal
            decimal = parts[-1]
            # Junta os segmentos anteriores (removendo pontos de milhar)
            integer_part = ''.join(parts[:-1])
            # Reconstrói o número com ponto decimal
            return float(integer_part + '.' + decimal)
    
    return col.apply(convert_value)


#   detectar o character set utilizado nos dados
with open(DATA, "rb") as f:
    raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    print(f"charset encoding: {encoding}")

#   1.  Leitura e extração dos dados
#   ler com o encoding detectado
df = pd.read_csv(r"data/arrecadacao-estado.csv", encoding=encoding, sep=";")

#   2.  Pré-processamento: limpeza dos dados
#   Converte as strings que representam R$ para float
cols_to_clean       = [c for c in df.columns if c not in ['Ano', 'Mês', 'UF']];
df[cols_to_clean]   = df[cols_to_clean].apply(clean_currency);


#   3.  Pré-processamento: geração de novas features
#   criar associações mês -> número, número -> mês
meses_pt = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

month_to_number = {mes: str(i+1).zfill(2) for i, mes in enumerate(meses_pt)}

#   criação de novas colunas
df['Mês_Num'] = df['Mês'].map(month_to_number)  # cria coluna '01' a '12'
df['Data'] = pd.to_datetime(df['Ano'].astype(str) + '-' + df['Mês_Num'] + '-01')

#   4.  Pré-processamento: adequação ao formato esperado por biblioteca
#   transformação para formato long (melt) necessário ao Altair
#       colunas identificadoras
id_vars = ['Ano', 'Mês', 'UF', 'Mês_Num', 'Data']

#       colunas valor
value_vars = [c for c in df.columns if c not in id_vars]

#       -> melt
df_melt = df.melt(id_vars=id_vars, value_vars=value_vars, var_name='Imposto', value_name='Valor')
df_melt = df_melt.dropna(subset=['Valor']).query('Valor > 0')  # Remove zeros/NaNs

print(df_melt.shape)

#   5.  Visualização:   Série Temporal
#       Evolução da Arrecadação Total
# Agregar por Data (soma de todos os estados e impostos)
trend = df_melt.groupby('Data')['Valor'].sum().reset_index()

# Agregar por Data (soma de todos os estados e impostos)
trend = df_melt.groupby('Data')['Valor'].sum().reset_index()

# Calcular as métricas no pandas
trend['MA_12'] = trend['Valor'].rolling(12, min_periods=1).mean()
trend['Min_12'] = trend['Valor'].rolling(12, min_periods=1).min()
trend['Max_12'] = trend['Valor'].rolling(12, min_periods=1).max()

# Regressão via Altair (usando transform_regression)
reg = alt.Chart(trend).transform_regression('Data', 'Valor', method='linear').mark_line(color='orange', strokeWidth=2)

# Base com a série original (opcional, pode ocultar)
orig = alt.Chart(trend).mark_line(color='lightgray', opacity=0.3).encode(x='Data:T', y='Valor:Q')

# Banda e média móvel
band = alt.Chart(trend).mark_area(opacity=0.15, color='steelblue').encode(
    x='Data:T',
    y='Min_12:Q',
    y2='Max_12:Q'
)
ma = alt.Chart(trend).mark_line(color='steelblue', strokeWidth=2).encode(x='Data:T', y='MA_12:Q')

# Montagem
(band + ma + reg + orig).properties(
    title='?',
    width=700,
    height=400
).interactive()

#   Stacked Area
#   Participação de cada tributo ao longo do tempo

# Selecionar apenas os maiores impostos para não poluir
top_impostos = ['IRPF', 'IRPJ - DEMAIS EMPRESAS', 'COFINS - DEMAIS', 
                'CONTRIBUIÇÃO PARA O PIS/PASEP - DEMAIS', 'CSLL - DEMAIS',
                'IPI - AUTOMÓVEIS', 'IMPOSTO SOBRE IMPORTAÇÃO']

df_plot = df_melt[df_melt['Imposto'].isin(top_impostos)]
# Agregar por Data e Imposto (soma nacional)
df_agg = df_plot.groupby(['Data', 'Imposto'])['Valor'].sum().reset_index()

# Gráfico de áreas (stacked normalizado)
area_chart = alt.Chart(df_agg).mark_area(opacity=0.7).encode(
    x=alt.X('Data:T', title='Data'),
    y=alt.Y('Valor:Q', title='Arrecadação (R$)', stack='normalize'),
    color=alt.Color('Imposto:N', legend=alt.Legend(columns=2)),
    tooltip=['Data', 'Imposto', 'Valor']
).properties(
    title='Participação relativa dos principais tributos',
    width=700,
    height=400
).interactive()

# Linha vertical para marcar o início de 2004 (01/01/2004)
linha_2004 = alt.Chart(pd.DataFrame({'Data': ['2004-01-01']})).mark_rule(
    color='red', 
    strokeWidth=2,
    strokeDash=[5, 3]  # Linha tracejada para não poluir
).encode(
    x='Data:T'
)

# Unir os dois gráficos
(area_chart + linha_2004)