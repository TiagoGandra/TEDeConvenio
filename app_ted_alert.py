import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import io

# Configuração da página
st.set_page_config(layout="wide", page_icon="🐙" , page_title="ICMBio Alertas")

# --- Nomes dos arquivos base de dados ---
ARQUIVO_TEDS_ENVIADOS = 'TED Alert.xlsx'
ARQUIVO_TEDS_RECEBIDOS = 'TED Recebido.xlsx'
ARQUIVO_CONVENIOS = 'Convenios.xlsx'

# --- Inicialização do Session State (sem alterações) ---
if 'report_type' not in st.session_state: st.session_state.report_type = None
if 'status_selecionado_teds_enviados' not in st.session_state: st.session_state.status_selecionado_teds_enviados = []
if 'status_prazo_selecionado_teds_enviados' not in st.session_state: st.session_state.status_prazo_selecionado_teds_enviados = []
if 'status_selecionado_teds_recebidos' not in st.session_state: st.session_state.status_selecionado_teds_recebidos = []
if 'status_prazo_selecionado_teds_recebidos' not in st.session_state: st.session_state.status_prazo_selecionado_teds_recebidos = []
if 'status_selecionado_convenios' not in st.session_state: st.session_state.status_selecionado_convenios = []
if 'status_prazo_selecionado_convenios' not in st.session_state: st.session_state.status_prazo_selecionado_convenios = []

# --- Funções de Callback (sem alterações) ---
def selecionar_relatorio(tipo_selecionado):
    st.session_state.report_type = tipo_selecionado
    if tipo_selecionado != "TEDs_Enviados": st.session_state.status_selecionado_teds_enviados, st.session_state.status_prazo_selecionado_teds_enviados = [], []
    if tipo_selecionado != "TEDs_Recebidos": st.session_state.status_selecionado_teds_recebidos, st.session_state.status_prazo_selecionado_teds_recebidos = [], []
    if tipo_selecionado != "Convenios": st.session_state.status_selecionado_convenios, st.session_state.status_prazo_selecionado_convenios = [], []

# --- Função Auxiliar para Converter Moeda (sem alterações) ---
def converter_valor_monetario(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float, np.number)): return float(valor)
    if isinstance(valor, str):
        limpo = valor.replace('R$', '').strip()
        num_virgulas = limpo.count(',')
        if num_virgulas == 1 and '.' in limpo:
            if limpo.rfind('.') < limpo.rfind(','):
                 limpo = limpo.replace('.', '', regex=False)
                 limpo = limpo.replace(',', '.', regex=False)
        elif num_virgulas == 1:
            if len(limpo.split(',')[-1]) == 2: limpo = limpo.replace(',', '.', regex=False)
            else: limpo = limpo.replace(',', '', regex=False)
        elif num_virgulas == 0 and '.' in limpo:
            partes = limpo.split('.')
            if len(partes) > 1 and len(partes[-1]) != 2:
                 limpo = "".join(partes)
        convertido = pd.to_numeric(limpo, errors='coerce')
        return convertido if pd.notnull(convertido) else 0.0
    return 0.0

# --- FUNÇÕES DE PROCESSAMENTO DE DADOS ESPECÍFICAS ---

def processar_dados_df_teds_enviados(df_input):
    df = df_input.copy()
    tipo_item_str = "TED Enviado"
    colunas_originais = ['TED', 'Objeto', 'Convenente', 'Data Pagamento', 'Status', 'Valor (Opcional)']
    colunas_faltantes = [col for col in colunas_originais if col not in df.columns]
    if colunas_faltantes: return None, f"Colunas {tipo_item_str} obrigatórias não encontradas: {', '.join(colunas_faltantes)}."

    df = df.rename(columns={
        'TED': 'ID_Item',
        'Convenente': 'Proponente', # Padronizando para Proponente internamente
        'Valor (Opcional)': 'Valor_Calculo'
    })
    # Colunas 'Objeto' e 'Status' já têm nomes internos bons
    # 'Data Pagamento' já é o nome interno esperado

    try: df['Data Pagamento'] = pd.to_datetime(df['Data Pagamento'], errors='coerce')
    except Exception as e: return None, f"Erro {tipo_item_str} - Converter 'Data Pagamento': {e}."
    if df['Data Pagamento'].isnull().any(): return None, f"Erro {tipo_item_str} - Verifique formato/ausência em 'Data Pagamento'."

    df['Valor_Calculo'] = df['Valor_Calculo'].apply(converter_valor_monetario).fillna(0)
    df['Status'] = df['Status'].astype(str)
    df['Objeto'] = df['Objeto'].astype(str)
    df['Proponente'] = df['Proponente'].astype(str)

    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Restantes'] = (df['Data Pagamento'] - hoje).dt.days
    df['Dias Atraso'] = (hoje - df['Data Pagamento']).dt.days.apply(lambda x: x if x > 0 else 0)
    df['Status Prazo'] = 'Prazo OK (> 30d)'; nao_concluidos_mask = df['Status'].str.lower() != 'concluído'
    df.loc[df['Status'].str.lower() == 'concluído', 'Status Prazo'] = 'Concluído'
    df.loc[nao_concluidos_mask & (df['Dias Atraso'] > 0), 'Status Prazo'] = 'Atrasado'
    df.loc[nao_concluidos_mask & (df['Dias Restantes'] <= 15) & (df['Dias Restantes'] >= 0) & (df['Status Prazo'] != 'Atrasado'), 'Status Prazo'] = 'Próximo (<= 15d)'
    df.loc[nao_concluidos_mask & (df['Dias Restantes'] > 15) & (df['Dias Restantes'] <= 30) & (df['Status Prazo'] != 'Atrasado') & (df['Status Prazo'] != 'Próximo (<= 15d)'), 'Status Prazo'] = 'Atenção (16-30d)'
    df.loc[df['Dias Restantes'] < 0, 'Dias Restantes'] = 0
    return df, None

def processar_dados_df_teds_recebidos(df_input):
    df = df_input.copy()
    tipo_item_str = "TED Recebido"
    # Colunas conforme a imagem image_8adee7.png para TED Recebido
    map_colunas = {
        'Nº CONVÊNIO': 'ID_Item',
        'PROCESSO': 'Objeto',
        'UNIDADE DESCENTRALIZADORA': 'Proponente',
        'FIM DE VIGÊNCIA': 'Data Pagamento',
        'SITUAÇÃO': 'Status',
        'VALOR': 'Valor_Calculo'
        # Adicione 'ANO' e 'VIGÊNCIA' (range) ao map_colunas se quiser usá-los diretamente
        # 'ANO': 'Ano_Item',
        # 'VIGÊNCIA': 'Vigencia_Range_Str'
    }
    colunas_originais_obrigatorias = list(map_colunas.keys())
    colunas_faltantes = [col for col in colunas_originais_obrigatorias if col not in df.columns]
    if colunas_faltantes: return None, f"Colunas {tipo_item_str} obrigatórias não encontradas: {', '.join(colunas_faltantes)}."
    df = df.rename(columns=map_colunas)

    try: df['Data Pagamento'] = pd.to_datetime(df['Data Pagamento'], dayfirst=True, errors='coerce')
    except Exception as e: return None, f"Erro {tipo_item_str} - Converter 'Data Pagamento' (FIM DE VIGÊNCIA): {e}."

    df['Valor_Calculo'] = df['Valor_Calculo'].apply(converter_valor_monetario).fillna(0)
    df['Status'] = df['Status'].astype(str); df['Objeto'] = df['Objeto'].astype(str); df['Proponente'] = df['Proponente'].astype(str)
    
    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Restantes'] = (df['Data Pagamento'] - hoje).dt.days
    df['Dias Atraso'] = (hoje - df['Data Pagamento']).dt.days
    df['Dias Atraso'] = df['Dias Atraso'].apply(lambda x: x if pd.notnull(x) and x > 0 else 0)
    df['Status Prazo'] = 'Prazo OK (> 30d)'; nao_concluidos_mask = df['Status'].str.lower() != 'concluído'; data_valida_mask = df['Data Pagamento'].notnull()
    df.loc[df['Data Pagamento'].isnull() & nao_concluidos_mask, 'Status Prazo'] = 'Vigência Indefinida'
    df.loc[df['Data Pagamento'].isnull() & ~nao_concluidos_mask, 'Status Prazo'] = 'Concluído (Vig. Indef.)'
    df.loc[data_valida_mask & (df['Status'].str.lower() == 'concluído'), 'Status Prazo'] = 'Concluído'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Atraso'] > 0), 'Status Prazo'] = 'Atrasado'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Restantes'] <= 15) & (df['Dias Restantes'] >= 0) & (df['Status Prazo'] != 'Atrasado'), 'Status Prazo'] = 'Próximo (<= 15d)'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Restantes'] > 15) & (df['Dias Restantes'] <= 30) & (df['Status Prazo'] != 'Atrasado') & (df['Status Prazo'] != 'Próximo (<= 15d)'), 'Status Prazo'] = 'Atenção (16-30d)'
    df.loc[df['Dias Restantes'] < 0, 'Dias Restantes'] = 0
    df.loc[df['Data Pagamento'].isnull(), 'Dias Restantes'] = pd.NA
    return df, None

def processar_dados_df_convenios(df_input):
    df = df_input.copy()
    tipo_item_str = "Convênio"
    # Colunas esperadas para Convênios (baseado na sua estrutura original de Convênios)
    map_colunas = {
        'Nº CONVÊNIO': 'ID_Item', # Ou 'Convênio' se for o caso
        'PROCESSO': 'Objeto',
        'PROPONENTE': 'Proponente',
        'FIM DE VIGÊNCIA': 'Data Pagamento',
        'SITUAÇÃO': 'Status',
        'VALOR': 'Valor_Calculo'
    }
    colunas_originais_obrigatorias = list(map_colunas.keys())
    colunas_faltantes = [col for col in colunas_originais_obrigatorias if col not in df.columns]
    if colunas_faltantes: return None, f"Colunas {tipo_item_str} obrigatórias não encontradas: {', '.join(colunas_faltantes)}."
    df = df.rename(columns=map_colunas)

    try: df['Data Pagamento'] = pd.to_datetime(df['Data Pagamento'], dayfirst=True, errors='coerce')
    except Exception as e: return None, f"Erro {tipo_item_str} - Converter 'Data Pagamento' (FIM DE VIGÊNCIA): {e}."

    df['Valor_Calculo'] = df['Valor_Calculo'].apply(converter_valor_monetario).fillna(0)
    df['Status'] = df['Status'].astype(str); df['Objeto'] = df['Objeto'].astype(str); df['Proponente'] = df['Proponente'].astype(str)

    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Restantes'] = (df['Data Pagamento'] - hoje).dt.days
    df['Dias Atraso'] = (hoje - df['Data Pagamento']).dt.days
    df['Dias Atraso'] = df['Dias Atraso'].apply(lambda x: x if pd.notnull(x) and x > 0 else 0)
    df['Status Prazo'] = 'Prazo OK (> 30d)'; nao_concluidos_mask = df['Status'].str.lower() != 'concluído'; data_valida_mask = df['Data Pagamento'].notnull()
    df.loc[df['Data Pagamento'].isnull() & nao_concluidos_mask, 'Status Prazo'] = 'Vigência Indefinida'
    df.loc[df['Data Pagamento'].isnull() & ~nao_concluidos_mask, 'Status Prazo'] = 'Concluído (Vig. Indef.)'
    df.loc[data_valida_mask & (df['Status'].str.lower() == 'concluído'), 'Status Prazo'] = 'Concluído'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Atraso'] > 0), 'Status Prazo'] = 'Atrasado'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Restantes'] <= 15) & (df['Dias Restantes'] >= 0) & (df['Status Prazo'] != 'Atrasado'), 'Status Prazo'] = 'Próximo (<= 15d)'
    df.loc[data_valida_mask & nao_concluidos_mask & (df['Dias Restantes'] > 15) & (df['Dias Restantes'] <= 30) & (df['Status Prazo'] != 'Atrasado') & (df['Status Prazo'] != 'Próximo (<= 15d)'), 'Status Prazo'] = 'Atenção (16-30d)'
    df.loc[df['Dias Restantes'] < 0, 'Dias Restantes'] = 0
    df.loc[df['Data Pagamento'].isnull(), 'Dias Restantes'] = pd.NA
    return df, None

# --- CSS e Funções dos Cards (sem alterações) ---
card_css = """<style> /* Seu CSS COMPLETO aqui - Omitido para brevidade */ 
.flip-card { background-color: transparent; width: 100%; min-height: 140px; height: auto; perspective: 1000px; display: block; margin-bottom: 15px; }
.flip-card-inner { position: relative; width: 100%; height: 100%; min-height: 140px; text-align: center; transition: transform 0.6s; transform-style: preserve-3d; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2); border-radius: 10px; }
.flip-card:hover .flip-card-inner { transform: rotateY(180deg); }
.flip-card-front, .flip-card-back { position: absolute; width: 100%; height: 100%; -webkit-backface-visibility: hidden; backface-visibility: hidden; border-radius: 10px; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; padding: 8px 12px; box-sizing: border-box; }
.flip-card-back { transform: rotateY(180deg); display: flex; flex-direction: column; justify-content: center; align-items: center; }
.card-atrasado .flip-card-front { background-color: #D32F2F; } .card-atrasado .flip-card-back  { background-color: #B71C1C; }
.card-proximo .flip-card-front { background-color: #FFA000; } .card-proximo .flip-card-back  { background-color: #FF8F00; }
.card-atencao .flip-card-front { background-color: #FBC02D; color: #333; } .card-atencao .flip-card-back  { background-color: #F9A825; color: #333; }
.card-ok .flip-card-front { background-color: #388E3C; } .card-ok .flip-card-back { background-color: #1B5E20; }
.card-concluido .flip-card-front { background-color: #607D8B; } .card-concluido .flip-card-back { background-color: #455A64; }
.card-indefinido .flip-card-front { background-color: #757575; } .card-indefinido .flip-card-back { background-color: #424242; }
.card-default .flip-card-front { background-color: #424242; } .card-default .flip-card-back { background-color: #212121; }
.card-title-summary { font-size: 0.9em; font-weight: bold; margin-bottom: 5px; }
.card-data-summary { font-size: 2.0em; font-weight: bold; }
.flip-card-front .card-content-detail { font-size: 0.78em; text-align: left; width: 100%; line-height: 1.3; }
.flip-card-front .card-content-detail strong { font-weight: bold; }
.card-title-back { font-size: 0.9em; font-weight: bold; margin-bottom: 8px; }
.card-data-money { font-size: 1.6em; font-weight: bold; }
</style>"""
def create_flip_card_summary(front_title, front_data, back_title, back_data, card_type_class):
    # (função igual)
    if isinstance(back_data, (int, float, np.number)):
        try: formatted_back_data = f'R$ {back_data:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError): formatted_back_data = str(back_data)
    else: formatted_back_data = back_data
    front_html_content = f"""<div class="card-title-summary">{front_title}</div><div class="card-data-summary">{front_data}</div>"""
    back_html_content = f"""<div class="card-title-back">{back_title}</div><div class="card-data-money">{formatted_back_data}</div>"""
    card_html = f"""<div class="flip-card {card_type_class}"><div class="flip-card-inner"><div class="flip-card-front">{front_html_content}</div><div class="flip-card-back">{back_html_content}</div></div></div>"""
    return card_html
def create_flip_card_detalhe(id_item, processo_ou_objeto, proponente, data_vigencia, valor, card_type_class):
    # (função igual)
    data_str = data_vigencia.strftime('%d/%m/%Y') if pd.notnull(data_vigencia) else "Indefinida"
    if isinstance(valor, (int, float, np.number)):
        try: formatted_valor = f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError): formatted_valor = str(valor)
    else: formatted_valor = str(valor) if pd.notnull(valor) else "N/A"
    id_item_str = str(id_item) if pd.notnull(id_item) else "N/A"
    processo_ou_objeto_str = str(processo_ou_objeto) if pd.notnull(processo_ou_objeto) else "N/A"
    proponente_str = str(proponente) if pd.notnull(proponente) else "N/A"
    processo_disp = (processo_ou_objeto_str[:40] + '...') if len(processo_ou_objeto_str) > 43 else processo_ou_objeto_str
    proponente_disp = (proponente_str[:40] + '...') if len(proponente_str) > 43 else proponente_str
    front_html_content = f"""<div class='card-content-detail'><strong>Item:</strong> {id_item_str}<br><strong>Processo/Obj.:</strong> {processo_disp}<br><strong>Proponente:</strong> {proponente_disp}<br><strong>Vigência:</strong> {data_str}</div>"""
    back_html_content = f"""<div class="card-title-back">Valor</div><div class="card-data-money">{formatted_valor}</div>"""
    card_html = f"""<div class="flip-card {card_type_class}"><div class="flip-card-inner"><div class="flip-card-front">{front_html_content}</div><div class="flip-card-back">{back_html_content}</div></div></div>"""
    return card_html
st.markdown(card_css, unsafe_allow_html=True)

# --- Carregar e Processar Dados ---
df_teds_enviados, df_teds_recebidos, df_convenios = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
error_teds_enviados, error_teds_recebidos, error_convenios = None, None, None
try:
    df_raw = pd.read_excel(ARQUIVO_TEDS_ENVIADOS)
    if df_raw is not None and not df_raw.empty: df_teds_enviados, error_teds_enviados = processar_dados_df_teds_enviados(df_raw)
    elif df_raw is not None: error_teds_enviados = f"Arquivo '{ARQUIVO_TEDS_ENVIADOS}' vazio."
    else: error_teds_enviados = f"Falha leitura '{ARQUIVO_TEDS_ENVIADOS}'."
except FileNotFoundError: error_teds_enviados = f"Arquivo '{ARQUIVO_TEDS_ENVIADOS}' não encontrado."
except Exception as e: error_teds_enviados = f"Erro TEDs Enviados: {e}"

try:
    df_raw = pd.read_excel(ARQUIVO_TEDS_RECEBIDOS)
    if df_raw is not None and not df_raw.empty: 
        df_teds_recebidos, error_teds_recebidos = processar_dados_df_teds_recebidos(df_raw)
    elif df_raw is not None: error_teds_recebidos = f"Arquivo '{ARQUIVO_TEDS_RECEBIDOS}' vazio."
    else: error_teds_recebidos = f"Falha leitura '{ARQUIVO_TEDS_RECEBIDOS}'."
except FileNotFoundError: error_teds_recebidos = f"Arquivo '{ARQUIVO_TEDS_RECEBIDOS}' não encontrado."
except Exception as e: error_teds_recebidos = f"Erro TEDs Recebidos: {e}"

try:
    df_raw = pd.read_excel(ARQUIVO_CONVENIOS)
    if df_raw is not None and not df_raw.empty: df_convenios, error_convenios = processar_dados_df_convenios(df_raw)
    elif df_raw is not None: error_convenios = f"Arquivo '{ARQUIVO_CONVENIOS}' vazio."
    else: error_convenios = f"Falha leitura '{ARQUIVO_CONVENIOS}'."
except FileNotFoundError: error_convenios = f"Arquivo '{ARQUIVO_CONVENIOS}' não encontrado."
except Exception as e: error_convenios = f"Erro Convênios: {e}"

# --- Barra Lateral ---
with st.sidebar:
    try: st.image("icmbio.png", width=200)
    except: st.write("Logo ICMBio")
    if st.session_state.report_type == "TEDs_Enviados":
        st.header("Filtros TEDs Enviados")
        if not df_teds_enviados.empty:
            opts_status = sorted(df_teds_enviados['Status'].astype(str).unique().tolist())
            opts_prazo = sorted(df_teds_enviados['Status Prazo'].astype(str).unique().tolist())
            st.session_state.status_selecionado_teds_enviados = st.multiselect("Status", options=opts_status, default=st.session_state.status_selecionado_teds_enviados, key="ms_status_teds_e_sb")
            st.session_state.status_prazo_selecionado_teds_enviados = st.multiselect("Status Prazo", options=opts_prazo, default=st.session_state.status_prazo_selecionado_teds_enviados, key="ms_prazo_teds_e_sb")
        else: st.caption("Dados de TEDs Enviados não carregados.")
    elif st.session_state.report_type == "TEDs_Recebidos":
        st.header("Filtros TEDs Recebidos")
        if df_teds_recebidos is not None and not df_teds_recebidos.empty:
            opts_status = sorted(df_teds_recebidos['Status'].astype(str).unique().tolist())
            opts_prazo = sorted(df_teds_recebidos['Status Prazo'].astype(str).unique().tolist())
            st.session_state.status_selecionado_teds_recebidos = st.multiselect("Status", options=opts_status, default=st.session_state.status_selecionado_teds_recebidos, key="ms_status_teds_r_sb")
            st.session_state.status_prazo_selecionado_teds_recebidos = st.multiselect("Status Prazo", options=opts_prazo, default=st.session_state.status_prazo_selecionado_teds_recebidos, key="ms_prazo_teds_r_sb")
        else: st.caption("Dados de TEDs Recebidos não carregados.")
    elif st.session_state.report_type == "Convenios":
        st.header("Filtros Convênios")
        if not df_convenios.empty:
            opts_status = sorted(df_convenios['Status'].astype(str).unique().tolist())
            opts_prazo = sorted(df_convenios['Status Prazo'].astype(str).unique().tolist())
            st.session_state.status_selecionado_convenios = st.multiselect("Status", options=opts_status, default=st.session_state.status_selecionado_convenios, key="ms_status_conv_sb")
            st.session_state.status_prazo_selecionado_convenios = st.multiselect("Status Prazo", options=opts_prazo, default=st.session_state.status_prazo_selecionado_convenios, key="ms_prazo_conv_sb")
        else: st.caption("Dados de Convênios não carregados.")
    else: st.caption("Selecione um relatório para ver os filtros.")
    st.divider(); st.warning("""**Aviso:** Cards usam `unsafe_allow_html=True`.""", icon="⚠️")

# --- Título e Seleção de Relatório ---
st.title("Painel de Alertas ICMBio")
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1: st.button("Alertas TEDs Enviados", on_click=selecionar_relatorio, args=("TEDs_Enviados",), key="btn_teds_enviados", use_container_width=True)
with col_btn2: st.button("Alertas TEDs Recebidos", on_click=selecionar_relatorio, args=("TEDs_Recebidos",), key="btn_teds_recebidos", use_container_width=True)
with col_btn3: st.button("Alertas Convênios", on_click=selecionar_relatorio, args=("Convenios",), key="btn_convenios", use_container_width=True)
st.markdown("---")

# --- Função Genérica para Exibir Seção do Dashboard ---
def exibir_secao_dashboard(titulo_secao, df_dados, error_msg, session_state_filtros_status, session_state_filtros_prazo, tipo_item_singular="Item", id_col_para_kpi='ID_Item', proponente_col_interna='Proponente', objeto_col_interna='Objeto'):
    # (Função exibir_secao_dashboard igual à versão anterior, apenas atenção aos nomes das colunas internas como 'Proponente')
    # Certifique-se que as colunas passadas para create_flip_card_detalhe (row[id_col_para_kpi], row[objeto_col_interna], row[proponente_col_interna])
    # realmente existem no df_dados com esses nomes após o processamento.
    st.header(titulo_secao)
    if error_msg: st.error(error_msg)
    elif not df_dados.empty:
        df_filtrado = df_dados.copy()
        if session_state_filtros_status: df_filtrado = df_filtrado[df_filtrado['Status'].isin(session_state_filtros_status)]
        if session_state_filtros_prazo: df_filtrado = df_filtrado[df_filtrado['Status Prazo'].isin(session_state_filtros_prazo)]
        
        st.subheader(f"Resumo dos Alertas {tipo_item_singular}s")
        kpi1_sum, kpi2_sum, kpi3_sum = st.columns(3)
        df_atrasados_sum = df_filtrado[df_filtrado['Status Prazo'] == 'Atrasado']
        df_proximos_sum = df_filtrado[df_filtrado['Status Prazo'] == 'Próximo (<= 15d)']
        df_atencao_sum = df_filtrado[df_filtrado['Status Prazo'] == 'Atenção (16-30d)']
        count_atrasados = df_atrasados_sum[id_col_para_kpi].count(); valor_atrasados = df_atrasados_sum['Valor_Calculo'].sum()
        count_proximos = df_proximos_sum[id_col_para_kpi].count(); valor_proximos = df_proximos_sum['Valor_Calculo'].sum()
        count_atencao = df_atencao_sum[id_col_para_kpi].count(); valor_atencao = df_atencao_sum['Valor_Calculo'].sum()
        with kpi1_sum: st.markdown(create_flip_card_summary(f"{tipo_item_singular}s Atrasados", count_atrasados, "Valor Total", valor_atrasados if count_atrasados > 0 else "R$ 0,00", "card-atrasado"), unsafe_allow_html=True)
        with kpi2_sum: st.markdown(create_flip_card_summary(f"{tipo_item_singular}s Próximos", count_proximos, "Valor Total", valor_proximos if count_proximos > 0 else "R$ 0,00", "card-proximo"), unsafe_allow_html=True)
        with kpi3_sum: st.markdown(create_flip_card_summary(f"{tipo_item_singular}s Atenção", count_atencao, "Valor Total", valor_atencao if count_atencao > 0 else "R$ 0,00", "card-atencao"), unsafe_allow_html=True)
        st.divider()

        st.subheader(f"{tipo_item_singular}s Detalhados (Cards)")
        df_itens_cards = df_filtrado.sort_values(by=['Status Prazo', 'Dias Atraso', 'Dias Restantes'], ascending=[True, False, True])
        if df_itens_cards.empty: st.info(f"Nenhum {tipo_item_singular} para os filtros.")
        else:
            num_card_columns = 4; card_cols = st.columns(num_card_columns)
            for i, (index, row) in enumerate(df_itens_cards.iterrows()):
                col_idx = i % num_card_columns
                if row['Status Prazo'] == 'Atrasado': card_class = "card-atrasado"
                elif row['Status Prazo'] == 'Próximo (<= 15d)': card_class = "card-proximo"
                elif row['Status Prazo'] == 'Atenção (16-30d)': card_class = "card-atencao"
                elif row['Status Prazo'] == 'Concluído': card_class = "card-concluido"
                elif row['Status Prazo'] == 'Prazo OK (> 30d)': card_class = "card-ok"
                elif row['Status Prazo'] == 'Vigência Indefinida': card_class = "card-indefinido"
                elif row['Status Prazo'] == 'Concluído (Vig. Indef.)': card_class = "card-concluido"
                else: card_class = "card-default"
                with card_cols[col_idx]: st.markdown(create_flip_card_detalhe(row[id_col_para_kpi], row[objeto_col_interna], row[proponente_col_interna], row['Data Pagamento'], row['Valor_Calculo'], card_class), unsafe_allow_html=True)
        st.divider()

        st.subheader(f"Detalhes Completos {tipo_item_singular}s (Tabela)")
        def destacar_linhas(row):
            cor = '';
            if 'Status Prazo' in row:
                if row['Status Prazo'] == 'Atrasado': cor = 'background-color: #FF7979; color: black;'
                elif row['Status Prazo'] == 'Próximo (<= 15d)': cor = 'background-color: #FFB266; color: black;'
                elif row['Status Prazo'] == 'Atenção (16-30d)': cor = 'background-color: #FFD699; color: black;'
                elif row['Status Prazo'] == 'Concluído': cor = 'background-color: #ADD8E6; color: black;'
                elif row['Status Prazo'] == 'Prazo OK (> 30d)': cor = 'background-color: #C8E6C9; color: black;'
                elif row['Status Prazo'] == 'Vigência Indefinida': cor = 'background-color: #E0E0E0; color: black;'
                elif row['Status Prazo'] == 'Concluído (Vig. Indef.)': cor = 'background-color: #B0BEC5; color: black;'
            return [cor] * len(row)
        
        cols_tabela_principal = [id_col_para_kpi, objeto_col_interna, proponente_col_interna, 'Status', 'Data Pagamento', 'Dias Restantes', 'Dias Atraso', 'Status Prazo', 'Valor_Calculo']
        df_tabela_display = df_filtrado[cols_tabela_principal].copy() # Seleciona apenas as colunas necessárias
        if 'Valor_Calculo' in df_tabela_display.columns: df_tabela_display['Valor_Exibicao'] = df_tabela_display['Valor_Calculo'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if pd.notnull(x) else "R$ 0,00")
        
        # Ajuste column_order e column_config para usar os nomes internos e o novo Valor_Exibicao
        col_order_final = [id_col_para_kpi, objeto_col_interna, proponente_col_interna, 'Status', 'Data Pagamento', 'Dias Restantes', 'Dias Atraso', 'Status Prazo', 'Valor_Exibicao']
        col_config_final = {
            id_col_para_kpi: tipo_item_singular,
            objeto_col_interna: "Processo/Objeto",
            proponente_col_interna: "Proponente",
            "Status": "Status",
            "Data Pagamento": st.column_config.DateColumn("Data Vigência", format="DD/MM/YYYY"), # Mudado para Data Vigência
            "Dias Restantes": st.column_config.NumberColumn("Dias Rest.", format="%d d"),
            "Dias Atraso": st.column_config.NumberColumn("Dias Atr.", format="%d d"),
            "Status Prazo":"Status Prazo",
            "Valor_Exibicao": st.column_config.TextColumn("Valor")
        }

        st.dataframe(
            df_tabela_display.style.apply(destacar_linhas, axis=1, subset=pd.IndexSlice[:, col_order_final]),
            column_config=col_config_final,
            column_order = col_order_final,
            hide_index=True, use_container_width=True
        )

        st.subheader(f"Contagem {tipo_item_singular}s por Status Prazo")
        if not df_filtrado.empty and 'Status Prazo' in df_filtrado.columns:
            contagem_status_prazo = df_filtrado['Status Prazo'].value_counts().reset_index(); contagem_status_prazo.columns = ['Status Prazo', 'Contagem']
            fig = px.pie(contagem_status_prazo, values='Contagem', names='Status Prazo', hole=.4, color_discrete_map={'Atrasado': '#FF7979', 'Próximo (<= 15d)': '#FFB266', 'Atenção (16-30d)': '#FFD699', 'Prazo OK (> 30d)': '#A0E6A0', 'Concluído': '#ADD8E6', 'Vigência Indefinida': '#E0E0E0', 'Concluído (Vig. Indef.)': '#B0BEC5'})
            fig.update_layout(legend_title_text='Status prazo'); st.plotly_chart(fig, use_container_width=True, key=f"pie_chart_{tipo_item_singular.lower().replace(' ', '_')}")
        else: st.write(f"Nenhum {tipo_item_singular} filtrado para gráfico.")
    
    elif not error_msg : st.info(f"Nenhum dado de {tipo_item_singular}s carregado ou o arquivo está vazio.")


# --- Chamadas para exibir as seções do dashboard ---
if st.session_state.report_type == "TEDs_Enviados":
    exibir_secao_dashboard(
        titulo_secao="ALERTA TEDs Enviados",
        df_dados=df_teds_enviados,
        error_msg=error_teds_enviados,
        session_state_filtros_status=st.session_state.status_selecionado_teds_enviados,
        session_state_filtros_prazo=st.session_state.status_prazo_selecionado_teds_enviados,
        tipo_item_singular="TED Enviado",
        id_col_para_kpi='ID_Item', # Veio de 'TED'
        proponente_col_interna='Proponente', # Veio de 'Convenente'
        objeto_col_interna='Objeto'
    )
elif st.session_state.report_type == "TEDs_Recebidos":
    exibir_secao_dashboard(
        titulo_secao="ALERTA TEDs Recebidos",
        df_dados=df_teds_recebidos,
        error_msg=error_teds_recebidos,
        session_state_filtros_status=st.session_state.status_selecionado_teds_recebidos,
        session_state_filtros_prazo=st.session_state.status_prazo_selecionado_teds_recebidos,
        tipo_item_singular="TED Recebido",
        id_col_para_kpi='ID_Item', # Veio de 'Nº CONVÊNIO'
        proponente_col_interna='Proponente', # Veio de 'UNIDADE DESCENTRALIZADA'
        objeto_col_interna='Objeto' # Veio de 'PROCESSO'
    )
elif st.session_state.report_type == "Convenios":
    exibir_secao_dashboard(
        titulo_secao="ALERTA Convênios",
        df_dados=df_convenios,
        error_msg=error_convenios,
        session_state_filtros_status=st.session_state.status_selecionado_convenios,
        session_state_filtros_prazo=st.session_state.status_prazo_selecionado_convenios,
        tipo_item_singular="Convênio",
        id_col_para_kpi='ID_Item', # Veio de 'Nº CONVÊNIO' ou 'Convênio'
        proponente_col_interna='Proponente', # Veio de 'PROPONENTE'
        objeto_col_interna='Objeto' # Veio de 'PROCESSO'
    )
else:
    st.info("⬆️ Selecione um tipo de relatório acima para começar.")