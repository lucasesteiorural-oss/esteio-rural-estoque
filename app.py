import os
import glob
import shutil
from datetime import datetime, date
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Esteio Rural | Gestão Inteligente de Estoque",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# ESTILO VISUAL LIQUID GLASS FUMÊ (ALTO CONTRASTE E NITIDEZ TOTAL)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #F8FAFC !important;
    }

    /* Fundo escuro profundo de alto contraste */
    .stApp {
        background: radial-gradient(circle at 15% 15%, #132A21 0%, #0D1714 55%, #090E0C 100%) !important;
        color: #FFFFFF !important;
    }

    /* Força nitidez em títulos, textos e rótulos de campos */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
    }

    p, span, label, div[data-testid="stMarkdownContainer"] p {
        color: #F1F5F9 !important;
    }

    /* Destaque nítido para nomes de colunas em código (`Código`, `Saldo Geral`, etc.) */
    code {
        background-color: rgba(16, 185, 129, 0.22) !important;
        color: #6EE7B7 !important;
        border: 1px solid rgba(52, 211, 153, 0.45) !important;
        padding: 2px 7px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.92em !important;
    }

    /* Animação suave de entrada */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Cartões de Métricas (KPIs) em Vidro Escuro Fumê */
    div[data-testid="stMetric"] {
        background: rgba(20, 38, 31, 0.88) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(74, 222, 128, 0.35) !important;
        border-radius: 16px !important;
        padding: 18px 22px !important;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45) !important;
        transition: all 0.25s ease;
        animation: fadeInUp 0.4s ease-out both;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: #34D399 !important;
        box-shadow: 0 12px 32px rgba(16, 185, 129, 0.25) !important;
    }

    div[data-testid="stMetricLabel"] p {
        color: #A7F3D0 !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    div[data-testid="stMetricValue"] div {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Caixas de Informação (st.info / st.warning / st.success) com contraste forte */
    div[data-testid="stAlert"] {
        background: rgba(17, 45, 36, 0.92) !important;
        border: 1px solid rgba(52, 211, 153, 0.5) !important;
        border-left: 5px solid #10B981 !important;
        border-radius: 14px !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35) !important;
    }

    div[data-testid="stAlert"] p, div[data-testid="stAlert"] strong {
        color: #FFFFFF !important;
    }

    /* Caixas de Upload de Arquivos (corrige o título branco que sumia no fundo claro) */
    div[data-testid="stFileUploader"] {
        background: rgba(18, 30, 26, 0.92) !important;
        border: 1px dashed rgba(52, 211, 153, 0.55) !important;
        border-radius: 14px !important;
        padding: 14px !important;
    }

    div[data-testid="stFileUploader"] label p {
        color: #6EE7B7 !important;
        font-weight: 700 !important;
        font-size: 0.96rem !important;
    }

    /* Botões principais em Verde Esmeralda Vibrante */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg, #10B981 0%, #047857 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(167, 243, 208, 0.4) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 700 !important;
        box-shadow: 0 6px 18px rgba(4, 120, 87, 0.4) !important;
        transition: all 0.25s ease !important;
    }

    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-2px);
        background: linear-gradient(135deg, #34D399 0%, #059669 100%) !important;
        box-shadow: 0 10px 24px rgba(16, 185, 129, 0.55) !important;
    }

    /* Abas do topo com leitura clara */
    button[data-baseweb="tab"] {
        background: rgba(24, 42, 35, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px 10px 0 0 !important;
        margin-right: 6px !important;
        padding: 10px 18px !important;
        color: #E2E8F0 !important;
        font-weight: 600 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #FFFFFF !important;
        border-color: #34D399 !important;
        box-shadow: 0 -4px 16px rgba(16, 185, 129, 0.35) !important;
    }

    /* Tabelas */
    div[data-testid="stDataFrame"] {
        border-radius: 14px;
        border: 1px solid rgba(74, 222, 128, 0.25);
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONFIGURAÇÃO DE PASTAS, GRAVAÇÃO ATÔMICA E GOOGLE SHEETS
# ==============================================================================
PASTA_DADOS = "dados_esteio"
PASTA_BACKUP = "backups_esteio"
MAX_BACKUPS_POR_ARQUIVO = 5
MAX_DIAS_HISTORICO_GUARDADO = 180

os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_BACKUP, exist_ok=True)

ARQ_ESTOQUE = os.path.join(PASTA_DADOS, "estoque_atual.csv")
ARQ_CUSTOS = os.path.join(PASTA_DADOS, "custos_atuais.csv")
ARQ_VENDAS = os.path.join(PASTA_DADOS, "vendas_atuais.csv")
ARQ_CONFIG = os.path.join(PASTA_DADOS, "config_dias.txt")
ARQ_HISTORICO = os.path.join(PASTA_DADOS, "historico_posicoes.csv")


def rotacionar_backups(prefixo):
    padrao = os.path.join(PASTA_BACKUP, f"{prefixo}_*.csv")
    arquivos = sorted(glob.glob(padrao), key=os.path.getmtime)
    while len(arquivos) > MAX_BACKUPS_POR_ARQUIVO:
        mais_antigo = arquivos.pop(0)
        try:
            os.remove(mais_antigo)
        except Exception:
            pass


def salvar_csv_atomico(df, caminho_final, prefixo_backup):
    if os.path.exists(caminho_final):
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino_bkp = os.path.join(PASTA_BACKUP, f"{prefixo_backup}_{carimbo}.csv")
        shutil.copy2(caminho_final, destino_bkp)
        rotacionar_backups(prefixo_backup)

    caminho_tmp = caminho_final + ".tmp"
    df.to_csv(caminho_tmp, index=False)
    os.replace(caminho_tmp, caminho_final)


def obter_planilha_gsheets():
    """Retorna o objeto da planilha do Google Sheets e exibe erros se houverem."""
    try:
        if "gcp_service_account" not in st.secrets:
            st.warning("⚠️ O bloco [gcp_service_account] não foi encontrado no arquivo secrets.toml.")
            return None
        import gspread
        from google.oauth2.service_account import Credentials

        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credenciais = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=escopos
        )
        cliente = gspread.authorize(credenciais)
        nome_planilha = st.secrets.get("sheet_name", "Banco_Dados_Esteio_Rural")
        return cliente.open(nome_planilha)
    except Exception as e:
        st.error(f"❌ Erro de Conexão com Google Sheets: {e}")
        return None


def salvar_aba_gsheets(nome_aba, df):
    sh = obter_planilha_gsheets()
    if sh is None:
        return False
    try:
        try:
            ws = sh.worksheet(nome_aba)
        except Exception:
            ws = sh.add_worksheet(title=nome_aba, rows=max(100, len(df) + 50), cols=max(10, len(df.columns) + 2))
        ws.clear()
        dados_envio = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
        ws.update(dados_envio)
        return True
    except Exception:
        return False


def carregar_aba_gsheets(nome_aba):
    sh = obter_planilha_gsheets()
    if sh is None:
        return pd.DataFrame()
    try:
        ws = sh.worksheet(nome_aba)
        registros = ws.get_all_records()
        return pd.DataFrame(registros)
    except Exception:
        return pd.DataFrame()


# ==============================================================================
# FUNÇÕES DE TRATAMENTO E NORMALIZAÇÃO
# ==============================================================================
def normalizar_codigo(serie):
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
        .replace("", "0")
    )


def converter_numero(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0.0)
    s = serie.astype(str).str.strip().str.replace("R$", "", regex=False).str.strip()
    tem_virgula = s.str.contains(",", na=False)
    s_br = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    s_final = s.where(~tem_virgula, s_br)
    return pd.to_numeric(s_final, errors="coerce").fillna(0.0)


def lote_valido(serie_lote):
    s = serie_lote.fillna("").astype(str).str.strip().str.upper()
    invalidos = {"", "NAN", "NONE", "NULL", "SEM LOTE", "S/L", "0", "0.0", "-"}
    return ~s.isin(invalidos)


def ler_planilha(arquivo_upload):
    nome = arquivo_upload.name.lower()
    if nome.endswith(".csv"):
        try:
            return pd.read_csv(arquivo_upload, sep=None, engine="python")
        except Exception:
            arquivo_upload.seek(0)
            return pd.read_csv(arquivo_upload, sep=";", encoding="latin1")
    else:
        return pd.read_excel(arquivo_upload)


def registrar_snapshot_diario(novo_est, data_ref_str):
    snap = novo_est[["Codigo", "Codigo_Lote", "Saldo_Geral", "Saldo_Lote"]].copy()
    snap["Data_Snapshot"] = data_ref_str

    if os.path.exists(ARQ_HISTORICO):
        hist = pd.read_csv(ARQ_HISTORICO, dtype={"Codigo": str, "Codigo_Lote": str})
        hist = hist[hist["Data_Snapshot"] != data_ref_str]
        hist = pd.concat([hist, snap], ignore_index=True)
    else:
        hist = snap

    hist["Data_DT"] = pd.to_datetime(hist["Data_Snapshot"], errors="coerce")
    if not hist["Data_DT"].dropna().empty:
        data_max = hist["Data_DT"].max()
        corte = data_max - pd.Timedelta(days=MAX_DIAS_HISTORICO_GUARDADO)
        hist = hist[hist["Data_DT"] >= corte].drop(columns=["Data_DT"])
    else:
        hist = hist.drop(columns=["Data_DT"], errors="ignore")

    salvar_csv_atomico(hist, ARQ_HISTORICO, "backup_historico")
    salvar_aba_gsheets("historico_posicoes", hist)


# ==============================================================================
# MOTOR DE CÁLCULO COM CACHE DE ALTA VELOCIDADE (@st.cache_data)
# ==============================================================================
@st.cache_data(show_spinner=False)
def carregar_bases_cacheadas(mtime_est, mtime_cus, mtime_ven, mtime_cfg):
    if not os.path.exists(ARQ_ESTOQUE):
        df_nuvem = carregar_aba_gsheets("estoque_atual")
        if not df_nuvem.empty:
            df_nuvem.to_csv(ARQ_ESTOQUE, index=False)
    if not os.path.exists(ARQ_CUSTOS):
        df_nuvem = carregar_aba_gsheets("custos_atuais")
        if not df_nuvem.empty:
            df_nuvem.to_csv(ARQ_CUSTOS, index=False)
    if not os.path.exists(ARQ_VENDAS):
        df_nuvem = carregar_aba_gsheets("vendas_atuais")
        if not df_nuvem.empty:
            df_nuvem.to_csv(ARQ_VENDAS, index=False)
    if not os.path.exists(ARQ_HISTORICO):
        df_nuvem = carregar_aba_gsheets("historico_posicoes")
        if not df_nuvem.empty:
            df_nuvem.to_csv(ARQ_HISTORICO, index=False)

    df_est = pd.read_csv(ARQ_ESTOQUE, dtype={"Codigo": str}) if os.path.exists(ARQ_ESTOQUE) else pd.DataFrame()
    df_cus = pd.read_csv(ARQ_CUSTOS, dtype={"Codigo": str}) if os.path.exists(ARQ_CUSTOS) else pd.DataFrame()
    df_ven = pd.read_csv(ARQ_VENDAS, dtype={"Codigo": str}) if os.path.exists(ARQ_VENDAS) else pd.DataFrame()

    if not df_est.empty:
        df_est["Saldo_Geral"] = converter_numero(df_est["Saldo_Geral"])
        df_est["Saldo_Lote"] = converter_numero(df_est["Saldo_Lote"])
    if not df_cus.empty:
        df_cus["Custo_C1"] = converter_numero(df_cus["Custo_C1"])
    if not df_ven.empty:
        df_ven["Qtd_Vendida"] = converter_numero(df_ven["Qtd_Vendida"])

    dias_hist = 90
    if os.path.exists(ARQ_CONFIG):
        try:
            with open(ARQ_CONFIG, "r") as f:
                dias_hist = int(f.read().strip())
        except Exception:
            dias_hist = 90

    return df_est, df_cus, df_ven, dias_hist


@st.cache_data(show_spinner=False)
def calcular_giro_aprendido(janela_dias, mtime_hist):
    if not os.path.exists(ARQ_HISTORICO):
        return pd.DataFrame(columns=["Codigo", "Saida_Aprendida", "Giro_Aprendido"]), 0

    hist = pd.read_csv(ARQ_HISTORICO, dtype={"Codigo": str, "Codigo_Lote": str})
    if hist.empty:
        return pd.DataFrame(columns=["Codigo", "Saida_Aprendida", "Giro_Aprendido"]), 0

    hist["Saldo_Geral"] = converter_numero(hist["Saldo_Geral"])
    hist["Saldo_Lote"] = converter_numero(hist["Saldo_Lote"])
    hist["Data_DT"] = pd.to_datetime(hist["Data_Snapshot"], errors="coerce")
    hist = hist.dropna(subset=["Data_DT"])

    datas_unicas = sorted(hist["Data_DT"].unique())
    if len(datas_unicas) < 2:
        return pd.DataFrame(columns=["Codigo", "Saida_Aprendida", "Giro_Aprendido"]), 0

    data_max = datas_unicas[-1]
    data_corte = data_max - pd.Timedelta(days=janela_dias)
    hist_janela = hist[hist["Data_DT"] >= data_corte].copy()

    datas_janela = sorted(hist_janela["Data_DT"].unique())
    if len(datas_janela) < 2:
        datas_janela = datas_unicas[-2:]
        hist_janela = hist[hist["Data_DT"].isin(datas_janela)].copy()

    dias_acumulados = max(1, (datas_janela[-1] - datas_janela[0]).days)

    prod_dia = (
        hist_janela.groupby(["Data_DT", "Codigo"], as_index=False)
        .agg(Saldo_Geral=("Saldo_Geral", "first"))
        .sort_values(["Codigo", "Data_DT"])
    )
    prod_dia["Saldo_Ant"] = prod_dia.groupby("Codigo")["Saldo_Geral"].shift(1)
    prod_dia["Queda_Geral"] = (prod_dia["Saldo_Ant"] - prod_dia["Saldo_Geral"]).clip(lower=0.0).fillna(0.0)
    saidas_geral = prod_dia.groupby(["Data_DT", "Codigo"], as_index=False)["Queda_Geral"].sum()

    lote_dia = (
        hist_janela.groupby(["Data_DT", "Codigo", "Codigo_Lote"], as_index=False)
        .agg(Saldo_Lote=("Saldo_Lote", "sum"))
        .sort_values(["Codigo", "Codigo_Lote", "Data_DT"])
    )
    lote_dia["Lote_Ant"] = lote_dia.groupby(["Codigo", "Codigo_Lote"])["Saldo_Lote"].shift(1)
    lote_dia["Queda_Lote"] = (lote_dia["Lote_Ant"] - lote_dia["Saldo_Lote"]).clip(lower=0.0).fillna(0.0)
    saidas_lote = lote_dia.groupby(["Data_DT", "Codigo"], as_index=False)["Queda_Lote"].sum()

    comp = pd.merge(saidas_geral, saidas_lote, on=["Data_DT", "Codigo"], how="outer").fillna(0.0)
    comp["Saida_Real_Dia"] = comp[["Queda_Geral", "Queda_Lote"]].max(axis=1)

    resumo = comp.groupby("Codigo", as_index=False).agg(Saida_Aprendida=("Saida_Real_Dia", "sum"))
    resumo["Giro_Aprendido"] = resumo["Saida_Aprendida"] / dias_acumulados

    return resumo, int(dias_acumulados)


@st.cache_data(show_spinner=False)
def consolidar_produtos(df_est, df_cus, df_ven, dias_hist, janela_sazonal, mtime_hist):
    if df_est.empty:
        return pd.DataFrame(), pd.DataFrame(), 0, 0.0

    df_est_proc = df_est.copy()
    df_est_proc["Tem_Lote_Linha"] = lote_valido(df_est_proc["Codigo_Lote"]) | (df_est_proc["Saldo_Lote"].abs() > 0.0001)

    prod_est = (
        df_est_proc.groupby("Codigo", as_index=False)
        .agg(
            Descricao=("Descricao", "first"),
            Saldo_Geral=("Saldo_Geral", "first"),
            Soma_Lotes=("Saldo_Lote", "sum"),
            Tem_Controle_Lote=("Tem_Lote_Linha", "any"),
            Qtd_Lotes=("Tem_Lote_Linha", "sum"),
        )
    )

    if not df_cus.empty:
        cus_unico = df_cus.groupby("Codigo", as_index=False).agg(Custo_C1=("Custo_C1", "last"))
        prod_est = pd.merge(prod_est, cus_unico, on="Codigo", how="left")
    else:
        prod_est["Custo_C1"] = 0.0
    prod_est["Custo_C1"] = prod_est["Custo_C1"].fillna(0.0)

    if not df_ven.empty:
        ven_unico = df_ven.groupby("Codigo", as_index=False).agg(Qtd_Vendida=("Qtd_Vendida", "sum"))
        prod_est = pd.merge(prod_est, ven_unico, on="Codigo", how="left")
    else:
        prod_est["Qtd_Vendida"] = 0.0
    prod_est["Qtd_Vendida"] = prod_est["Qtd_Vendida"].fillna(0.0)
    prod_est["Giro_Base_90d"] = prod_est["Qtd_Vendida"] / max(1, dias_hist)

    df_aprendido, dias_aprendidos = calcular_giro_aprendido(janela_sazonal, mtime_hist)
    prod_est = pd.merge(prod_est, df_aprendido[["Codigo", "Giro_Aprendido"]], on="Codigo", how="left")
    prod_est["Giro_Aprendido"] = prod_est["Giro_Aprendido"].fillna(0.0)

    peso_diario = min(1.0, dias_aprendidos / max(1, janela_sazonal))
    if df_ven.empty and dias_aprendidos > 0:
        peso_diario = 1.0

    prod_est["Giro_Diario"] = (
        (prod_est["Giro_Aprendido"] * peso_diario) +
        (prod_est["Giro_Base_90d"] * (1.0 - peso_diario))
    )

    def detectar_tendencia(r):
        if dias_aprendidos < 2:
            return "🌱 Base Inicial (Aguardando dias)"
        if r["Giro_Base_90d"] <= 0 and r["Giro_Aprendido"] > 0:
            return "🔥 Giro Novo Detectado"
        if r["Giro_Base_90d"] > 0:
            razao = r["Giro_Aprendido"] / r["Giro_Base_90d"]
            if razao >= 1.25:
                return "📈 Alta Sazonal (+25%)"
            elif razao <= 0.75:
                return "📉 Baixa Sazonal (-25%)"
        return "➡️ Giro Estável"

    prod_est["Tendencia_Sazonal"] = prod_est.apply(detectar_tendencia, axis=1)
    prod_est["Cobertura_Dias"] = prod_est.apply(
        lambda r: (r["Saldo_Geral"] / r["Giro_Diario"]) if r["Giro_Diario"] > 0 else 999.0, axis=1
    )
    prod_est["Valor_Estoque_R$"] = prod_est["Saldo_Geral"] * prod_est["Custo_C1"]

    prod_est["Divergencia_Lote"] = prod_est.apply(
        lambda r: (r["Saldo_Geral"] - r["Soma_Lotes"]) if r["Tem_Controle_Lote"] else 0.0,
        axis=1
    )

    df_lotes = df_est_proc.copy()
    df_lotes = pd.merge(df_lotes, prod_est[["Codigo", "Custo_C1"]], on="Codigo", how="left")
    df_lotes["Custo_C1"] = df_lotes["Custo_C1"].fillna(0.0)
    df_lotes["Valor_Lote_R$"] = df_lotes["Saldo_Lote"] * df_lotes["Custo_C1"]

    return prod_est, df_lotes, dias_aprendidos, peso_diario


# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================
col_tit1, col_tit2 = st.columns([3, 1])
with col_tit1:
    st.title("🌾 Esteio Rural — Inteligência de Estoque & Giro Sazonal")
with col_tit2:
    gs_conectado = obter_planilha_gsheets() is not None
    status_db = "☁️ Google Sheets Conectado" if gs_conectado else "💻 Banco Local Seguro (Atômico)"
    st.metric("Status do Banco de Dados", status_db)

mtime_est = os.path.getmtime(ARQ_ESTOQUE) if os.path.exists(ARQ_ESTOQUE) else 0
mtime_cus = os.path.getmtime(ARQ_CUSTOS) if os.path.exists(ARQ_CUSTOS) else 0
mtime_ven = os.path.getmtime(ARQ_VENDAS) if os.path.exists(ARQ_VENDAS) else 0
mtime_cfg = os.path.getmtime(ARQ_CONFIG) if os.path.exists(ARQ_CONFIG) else 0
mtime_hist = os.path.getmtime(ARQ_HISTORICO) if os.path.exists(ARQ_HISTORICO) else 0

df_est, df_cus, df_ven, dias_hist = carregar_bases_cacheadas(mtime_est, mtime_cus, mtime_ven, mtime_cfg)

abas = st.tabs([
    "📥 1. Importação & Nuvem",
    "🛒 2. Sugestão de Compras & Sazonalidade",
    "⏳ 3. Radar de Validades (FEFO)",
    "📊 4. Curva ABC Financeira",
    "🔍 5. Auditoria de ERP"
])

with abas[1]:
    c_cfg1, c_cfg2, c_cfg3 = st.columns(3)
    janela_sazonal = c_cfg1.selectbox(
        "Janela de Aprendizado Sazonal (Dias):",
        options=[15, 30, 60, 90, 120, 180],
        index=2,
        help="De 15 dias (campanhas rápidas) até 180 dias (estação completa de seca ou águas)."
    )
    meta_dias = c_cfg2.slider("Meta de Cobertura Desejada (Dias):", min_value=5, max_value=180, value=30, step=5)
    filtro_busca = c_cfg3.text_input("🔎 Buscar produto por Nome ou Código:")

df_produtos, df_lotes, dias_aprendidos, peso_diario = consolidar_produtos(
    df_est, df_cus, df_ven, dias_hist, janela_sazonal, mtime_hist
)

# ==============================================================================
# ABA 1: IMPORTAÇÃO DE PLANILHAS
# ==============================================================================
with abas[0]:
    st.subheader("Central de Importação Segura e Sincronização com Nuvem")
    st.markdown(
        "Gravação com **proteção atômica contra queda de energia**, rotação dos **últimos 5 backups** (incluindo histórico) "
        "e sincronização automática com **Google Sheets**."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("**1. Planilha de Estoque (Diária - 6 colunas)**\n\n`Código` · `Saldo Geral` · `Descrição` · `Código do Lote` · `Saldo Lote` · `Validade`")
        data_ref = st.date_input("Data desta posição de estoque:", value=date.today())
        up_est = st.file_uploader("Selecionar Estoque (.xlsx ou .csv)", type=["xlsx", "xls", "csv"], key="up_est")
        if up_est is not None and st.button("⚡ Processar Estoque e Aprender Giro", use_container_width=True):
            try:
                bruto = ler_planilha(up_est)
                if bruto.shape[1] < 6:
                    st.error(f"A planilha enviada tem apenas {bruto.shape[1]} colunas. São necessárias 6 colunas.")
                else:
                    novo_est = pd.DataFrame()
                    novo_est["Codigo"] = normalizar_codigo(bruto.iloc[:, 0])
                    novo_est["Saldo_Geral"] = converter_numero(bruto.iloc[:, 1])
                    novo_est["Descricao"] = bruto.iloc[:, 2].astype(str).str.strip()
                    novo_est["Codigo_Lote"] = bruto.iloc[:, 3].fillna("SEM LOTE").astype(str).str.strip()
                    novo_est["Saldo_Lote"] = converter_numero(bruto.iloc[:, 4])
                    novo_est["Validade"] = pd.to_datetime(bruto.iloc[:, 5], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")

                    novo_est = novo_est[novo_est["Codigo"] != "nan"]
                    salvar_csv_atomico(novo_est, ARQ_ESTOQUE, "backup_estoque")
                    salvar_aba_gsheets("estoque_atual", novo_est)

                    registrar_snapshot_diario(novo_est, data_ref.strftime("%Y-%m-%d"))

                    st.cache_data.clear()
                    st.success(f"Estoque de {data_ref.strftime('%d/%m/%Y')} salvo com segurança e histórico atualizado!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar estoque: {e}")

    with col2:
        st.info("**2. Planilha de Custos (Semanal - 3 colunas)**\n\n`Código` · `Descrição` · `Custo Unitário C1`")
        up_cus = st.file_uploader("Selecionar Custos (.xlsx ou .csv)", type=["xlsx", "xls", "csv"], key="up_cus")
        if up_cus is not None and st.button("⚡ Processar Custos", use_container_width=True):
            try:
                bruto = ler_planilha(up_cus)
                if bruto.shape[1] < 3:
                    st.error(f"A planilha enviada tem apenas {bruto.shape[1]} colunas. São necessárias 3 colunas.")
                else:
                    novo_cus = pd.DataFrame()
                    novo_cus["Codigo"] = normalizar_codigo(bruto.iloc[:, 0])
                    novo_cus["Descricao"] = bruto.iloc[:, 1].astype(str).str.strip()
                    novo_cus["Custo_C1"] = converter_numero(bruto.iloc[:, 2])
                    novo_cus = novo_cus[novo_cus["Codigo"] != "nan"]

                    salvar_csv_atomico(novo_cus, ARQ_CUSTOS, "backup_custos")
                    salvar_aba_gsheets("custos_atuais", novo_cus)

                    st.cache_data.clear()
                    st.success(f"Custos atualizados com sucesso! ({len(novo_cus)} produtos)")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar custos: {e}")

    with col3:
        st.info("**3. Base Inicial de Vendas (Apoio - 3 colunas)**\n\n`Código` · `Descrição` · `Quantidade Vendida`")
        dias_input = st.number_input("Período da base inicial (dias):", min_value=1, max_value=365, value=dias_hist)
        up_ven = st.file_uploader("Selecionar Base Inicial (.xlsx ou .csv)", type=["xlsx", "xls", "csv"], key="up_ven")
        if up_ven is not None and st.button("⚡ Processar Base Inicial", use_container_width=True):
            try:
                bruto = ler_planilha(up_ven)
                if bruto.shape[1] < 3:
                    st.error(f"A planilha enviada tem apenas {bruto.shape[1]} colunas. São necessárias 3 colunas.")
                else:
                    novo_ven = pd.DataFrame()
                    novo_ven["Codigo"] = normalizar_codigo(bruto.iloc[:, 0])
                    novo_ven["Descricao"] = bruto.iloc[:, 1].astype(str).str.strip()
                    novo_ven["Qtd_Vendida"] = converter_numero(bruto.iloc[:, 2])
                    novo_ven = novo_ven[novo_ven["Codigo"] != "nan"]

                    salvar_csv_atomico(novo_ven, ARQ_VENDAS, "backup_vendas")
                    salvar_aba_gsheets("vendas_atuais", novo_ven)
                    with open(ARQ_CONFIG, "w") as f:
                        f.write(str(int(dias_input)))

                    st.cache_data.clear()
                    st.success("Base inicial de vendas atualizada!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar vendas: {e}")

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Produtos Ativos", len(df_produtos))
    m2.metric("Dias Aprendidos no Histórico", f"{dias_aprendidos} dias")
    m3.metric("Peso do Aprendizado Diário", f"{peso_diario * 100:.0f}%")
    m4.metric("Peso da Base Inicial", f"{(1 - peso_diario) * 100:.0f}%")

# ==============================================================================
# ABA 2: SUGESTÃO DE COMPRAS & GIRO SAZONAL
# ==============================================================================
with abas[1]:
    if df_produtos.empty:
        st.warning("Importe primeiro a Planilha de Estoque na Aba 1.")
    else:
        st.info(
            f"🧠 **Motor Sazonal Ativo (Janela de {janela_sazonal} dias):** Acumulamos **{dias_aprendidos} dias** de histórico real. "
            f"O cálculo de giro combina **{peso_diario*100:.0f}% do Aprendizado Diário** + **{(1-peso_diario)*100:.0f}% da Base Inicial ({dias_hist}d)**."
        )

        df_comp = df_produtos.copy()
        df_comp["Estoque_Ideal"] = (df_comp["Giro_Diario"] * meta_dias).round(2)
        df_comp["Qtd_Sugerida_Compra"] = (df_comp["Estoque_Ideal"] - df_comp["Saldo_Geral"]).apply(lambda x: max(0.0, round(x, 2)))
        df_comp["Orcamento_Compra_R$"] = (df_comp["Qtd_Sugerida_Compra"] * df_comp["Custo_C1"]).round(2)

        if filtro_busca:
            termo = filtro_busca.lower()
            df_comp = df_comp[
                df_comp["Descricao"].str.lower().str.contains(termo, na=False) |
                df_comp["Codigo"].str.lower().str.contains(termo, na=False)
            ]

        apenas_comprar = st.checkbox("Mostrar apenas itens com necessidade de compra (Qtd Sugerida > 0)", value=True)
        if apenas_comprar:
            df_comp = df_comp[df_comp["Qtd_Sugerida_Compra"] > 0]

        df_comp = df_comp.sort_values(by="Orcamento_Compra_R$", ascending=False)

        k1, k2, k3 = st.columns(3)
        k1.metric("Itens para Reposição", len(df_comp))
        k2.metric("Orçamento Total Estimado (R$)", f"R$ {df_comp['Orcamento_Compra_R$'].sum():,.2f}")
        k3.metric("Janela Sazonal Selecionada", f"{janela_sazonal} dias")

        st.dataframe(
            df_comp[[
                "Codigo", "Descricao", "Tendencia_Sazonal", "Saldo_Geral",
                "Giro_Base_90d", "Giro_Aprendido", "Giro_Diario",
                "Cobertura_Dias", "Qtd_Sugerida_Compra", "Custo_C1", "Orcamento_Compra_R$"
            ]].round(2),
            use_container_width=True,
            hide_index=True
        )

        csv_comp = df_comp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 Baixar Sugestão de Compras (CSV/Excel)", data=csv_comp, file_name="sugestao_compras_esteio.csv", mime="text/csv")

# ==============================================================================
# ABA 3: RADAR DE VALIDADES (FEFO)
# ==============================================================================
with abas[2]:
    st.subheader("⏳ Radar de Validades e Lotes (Metodologia FEFO)")
    if df_lotes.empty:
        st.warning("Importe a Planilha de Estoque na Aba 1 para monitorar os lotes.")
    else:
        hoje = pd.Timestamp.today().normalize()
        lotes_fefo = df_lotes[df_lotes["Saldo_Lote"] > 0].copy()
        lotes_fefo["Data_Validade"] = pd.to_datetime(lotes_fefo["Validade"], errors="coerce")
        lotes_fefo["Dias_Para_Vencer"] = (lotes_fefo["Data_Validade"] - hoje).dt.days

        def classificar_risco(dias):
            if pd.isna(dias):
                return "⚪ Sem Data"
            elif dias < 0:
                return "🔴 1. Vencido"
            elif dias <= 30:
                return "🟠 2. Crítico (<= 30 dias)"
            elif dias <= 60:
                return "🟡 3. Atenção (31 a 60 dias)"
            elif dias <= 90:
                return "🔵 4. Alerta (61 a 90 dias)"
            else:
                return "🟢 5. Seguro (> 90 dias)"

        lotes_fefo["Status_FEFO"] = lotes_fefo["Dias_Para_Vencer"].apply(classificar_risco)
        lotes_fefo = lotes_fefo.sort_values(by=["Dias_Para_Vencer", "Valor_Lote_R$"], ascending=[True, False])

        vencidos_rs = lotes_fefo[lotes_fefo["Dias_Para_Vencer"] < 0]["Valor_Lote_R$"].sum()
        criticos_rs = lotes_fefo[(lotes_fefo["Dias_Para_Vencer"] >= 0) & (lotes_fefo["Dias_Para_Vencer"] <= 30)]["Valor_Lote_R$"].sum()
        atencao_rs = lotes_fefo[(lotes_fefo["Dias_Para_Vencer"] > 30) & (lotes_fefo["Dias_Para_Vencer"] <= 60)]["Valor_Lote_R$"].sum()

        r1, r2, r3 = st.columns(3)
        r1.metric("🔴 Vencidos (Risco em R$)", f"R$ {vencidos_rs:,.2f}")
        r2.metric("🟠 Crítico <= 30 dias (R$)", f"R$ {criticos_rs:,.2f}")
        r3.metric("🟡 Atenção 31-60 dias (R$)", f"R$ {atencao_rs:,.2f}")

        filtro_status = st.multiselect(
            "Filtrar por Status de Validade:",
            options=sorted(lotes_fefo["Status_FEFO"].unique()),
            default=sorted(lotes_fefo["Status_FEFO"].unique())
        )
        lotes_exib = lotes_fefo[lotes_fefo["Status_FEFO"].isin(filtro_status)]

        st.dataframe(
            lotes_exib[[
                "Status_FEFO", "Codigo", "Descricao", "Codigo_Lote",
                "Saldo_Lote", "Validade", "Dias_Para_Vencer", "Custo_C1", "Valor_Lote_R$"
            ]].round(2),
            use_container_width=True,
            hide_index=True
        )

# ==============================================================================
# ABA 4: CURVA ABC
# ==============================================================================
with abas[3]:
    st.subheader("📊 Análise de Curva ABC (Capital Imobilizado em Estoque)")
    if df_produtos.empty:
        st.warning("Importe os dados de Estoque e Custos na Aba 1.")
    else:
        abc = df_produtos[df_produtos["Saldo_Geral"] > 0].copy()
        abc = abc.sort_values(by="Valor_Estoque_R$", ascending=False)
        valor_total_estoque = abc["Valor_Estoque_R$"].sum()

        if valor_total_estoque > 0:
            abc["Participacao_%"] = (abc["Valor_Estoque_R$"] / valor_total_estoque) * 100
            abc["Acumulado_%"] = abc["Participacao_%"].cumsum()

            def definir_classe(acum):
                if acum <= 80.0:
                    return "Classe A (Até 80%)"
                elif acum <= 95.0:
                    return "Classe B (80% a 95%)"
                else:
                    return "Classe C (95% a 100%)"

            abc["Classe_ABC"] = abc["Acumulado_%"].apply(definir_classe)
        else:
            abc["Participacao_%"] = 0.0
            abc["Acumulado_%"] = 0.0
            abc["Classe_ABC"] = "Sem Custo C1"

        a1, a2, a3 = st.columns(3)
        a1.metric("Capital Total Imobilizado", f"R$ {valor_total_estoque:,.2f}")
        a2.metric("Itens Classe A (80% do Valor)", len(abc[abc["Classe_ABC"].str.startswith("Classe A")]))
        a3.metric("Itens Classe B e C", len(abc[~abc["Classe_ABC"].str.startswith("Classe A")]))

        st.dataframe(
            abc[[
                "Classe_ABC", "Codigo", "Descricao", "Saldo_Geral",
                "Custo_C1", "Valor_Estoque_R$", "Participacao_%", "Acumulado_%"
            ]].round(2),
            use_container_width=True,
            hide_index=True
        )

# ==============================================================================
# ABA 5: AUDITORIA DE DIVERGÊNCIAS DO ERP
# ==============================================================================
with abas[4]:
    st.subheader("🔍 Auditoria Inteligente de Divergências do ERP")
    if df_produtos.empty:
        st.warning("Importe a Planilha de Estoque na Aba 1.")
    else:
        div_lotes = df_produtos[
            (df_produtos["Tem_Controle_Lote"]) &
            (df_produtos["Divergencia_Lote"].abs() > 0.001)
        ].copy()

        itens_sem_controle_lote = len(df_produtos[~df_produtos["Tem_Controle_Lote"]])
        sem_custo = df_produtos[(df_produtos["Saldo_Geral"] > 0) & (df_produtos["Custo_C1"] <= 0)].copy()
        lotes_negativos = df_lotes[df_lotes["Saldo_Lote"] < 0].copy()

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("⚠️ Divergências Reais de Lote", len(div_lotes))
        d2.metric("ℹ️ Itens Sem Controle de Lote (Ignorados)", itens_sem_controle_lote)
        d3.metric("⚠️ Estoque Positivo Sem Custo C1", len(sem_custo))
        d4.metric("⚠️ Lotes com Saldo Negativo", len(lotes_negativos))

        st.markdown("#### 1. Divergências Reais (Apenas produtos com controle de lote onde Saldo Geral ≠ Soma dos Lotes)")
        if div_lotes.empty:
            st.success("Nenhuma divergência real encontrada nos produtos controlados por lote!")
        else:
            st.dataframe(
                div_lotes[["Codigo", "Descricao", "Saldo_Geral", "Soma_Lotes", "Divergencia_Lote", "Qtd_Lotes"]].round(2),
                use_container_width=True,
                hide_index=True
            )

        st.markdown("#### 2. Produtos com Saldo Positivo mas Sem Custo Unitário (C1) Cadastrado")
        if sem_custo.empty:
            st.success("Todos os produtos em estoque possuem custo cadastrado!")
        else:
            st.dataframe(
                sem_custo[["Codigo", "Descricao", "Saldo_Geral", "Custo_C1"]].round(2),
                use_container_width=True,
                hide_index=True
            )
