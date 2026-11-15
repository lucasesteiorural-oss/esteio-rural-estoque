import io
import re
import math
import hmac
import hashlib
import zipfile
import unicodedata
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def hoje_br() -> date:
    return datetime.now(FUSO_BR).date()


def agora_br() -> datetime:
    return datetime.now(FUSO_BR)


# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E VISUAL SAAS DARK NEON BENTO UI (ALTO CONTRASTE)
# ==============================================================================
st.set_page_config(
    page_title="Esteio Rural — Inteligência de Estoque & Giro Sazonal",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
    /* Fundo Obsidian Dark com luzes radiais suaves estilo Bento SaaS */
    .stApp {
        background:
            radial-gradient(circle at 12% 10%, rgba(124, 58, 237, 0.16) 0%, transparent 38%),
            radial-gradient(circle at 88% 16%, rgba(16, 185, 129, 0.12) 0%, transparent 40%),
            radial-gradient(circle at 50% 90%, rgba(59, 130, 246, 0.10) 0%, transparent 45%),
            linear-gradient(180deg, #0b0d14 0%, #0f131f 55%, #090b10 100%);
        color: #f8fafc;
    }
    /* Remove a barra preta superior do Streamlit e garante espaçamento perfeito para o cabeçalho e logo */
    header[data-testid="stHeader"] {
        background: transparent !important;
        background-color: transparent !important;
        backdrop-filter: none !important;
    }
    div[data-testid="stDecoration"] {
        display: none !important;
    }
    .block-container {
        padding-top: 3.6rem !important;
        padding-bottom: 2.5rem !important;
    }
    /* Cartões Bento Glassmorphism */
    .glass-card {
        background: linear-gradient(145deg, rgba(22, 27, 44, 0.88) 0%, rgba(15, 18, 30, 0.94) 100%);
        border: 1px solid rgba(139, 92, 246, 0.26);
        border-radius: 18px;
        padding: 18px 20px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(16px);
        margin-bottom: 14px;
        transition: transform 0.18s ease, border-color 0.18s ease;
    }
    .glass-card:hover {
        border-color: rgba(16, 185, 129, 0.45);
    }
    /* Caixa de Status Superior */
    .status-box {
        background: linear-gradient(135deg, rgba(22, 27, 44, 0.92) 0%, rgba(16, 22, 36, 0.96) 100%);
        border: 1px solid rgba(45, 212, 191, 0.40);
        border-radius: 16px;
        padding: 12px 18px;
        text-align: left;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45), 0 0 18px rgba(16, 185, 129, 0.12);
    }
    .status-label {
        font-size: 0.74rem;
        color: #94a3b8;
        margin-bottom: 3px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .status-value {
        font-size: 1.22rem;
        font-weight: 800;
        color: #f8fafc;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* Pílulas de Tags */
    .pill-tag {
        display: inline-block;
        background: rgba(139, 92, 246, 0.16);
        border: 1px solid rgba(167, 139, 250, 0.38);
        color: #c4b5fd;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        font-family: monospace;
        margin: 2px 4px 2px 0;
    }
    /* Barra de Abas Estilo Segmented Pill Neon (Inspirado no modelo de UI) */
    div[data-baseweb="tab-list"] {
        background: rgba(18, 22, 36, 0.90) !important;
        border: 1px solid rgba(148, 163, 184, 0.16) !important;
        border-radius: 16px !important;
        padding: 6px 8px !important;
        gap: 6px !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45) !important;
        margin-bottom: 18px !important;
        flex-wrap: wrap !important;
    }
    button[data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 11px !important;
        padding: 9px 16px !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: #f8fafc !important;
        background: rgba(139, 92, 246, 0.12) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: 1px solid rgba(196, 181, 253, 0.45) !important;
        box-shadow: 0 4px 18px rgba(124, 58, 237, 0.50) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] span,
    button[data-baseweb="tab"][aria-selected="true"] div {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    div[data-baseweb="tab-highlight"],
    div[data-baseweb="tab-border"] {
        display: none !important;
    }
    /* Cartões de Métricas Nativos Estilizados */
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(22, 27, 44, 0.90) 0%, rgba(14, 18, 30, 0.95) 100%);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 16px;
        padding: 14px 18px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.40);
    }
    /* Botões Primários com Gradiente Roxo/Indigo Neon */
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%) !important;
        border: 1px solid rgba(196, 181, 253, 0.40) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.38) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 25px rgba(124, 58, 237, 0.58) !important;
    }
    /* Bento Hero Grid Customizada (Topo do Dashboard) */
    .bento-grid {
        display: grid;
        grid-template-columns: 1.55fr 1.15fr 0.95fr 1.15fr;
        gap: 16px;
        margin-top: 8px;
        margin-bottom: 18px;
    }
    @media (max-width: 1100px) {
        .bento-grid {
            grid-template-columns: 1fr 1fr;
        }
    }
    @media (max-width: 680px) {
        .bento-grid {
            grid-template-columns: 1fr;
        }
    }
    .bento-card {
        position: relative;
        overflow: hidden;
        border-radius: 20px;
        padding: 20px 22px;
        background: linear-gradient(155deg, rgba(23, 28, 46, 0.95) 0%, rgba(13, 16, 28, 0.98) 100%);
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.07);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 168px;
    }
    .bento-card-emerald {
        background:
            radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.22) 0%, transparent 55%),
            linear-gradient(155deg, rgba(20, 31, 44, 0.96) 0%, rgba(11, 18, 26, 0.98) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .bento-card-purple {
        background:
            radial-gradient(circle at 85% 20%, rgba(139, 92, 246, 0.24) 0%, transparent 55%),
            linear-gradient(155deg, rgba(26, 23, 48, 0.96) 0%, rgba(14, 14, 28, 0.98) 100%);
        border: 1px solid rgba(139, 92, 246, 0.35);
    }
    .bento-card-amber {
        background:
            radial-gradient(circle at 50% 50%, rgba(249, 115, 22, 0.14) 0%, transparent 60%),
            linear-gradient(155deg, rgba(25, 24, 38, 0.96) 0%, rgba(14, 15, 25, 0.98) 100%);
        border: 1px solid rgba(249, 115, 22, 0.32);
        align-items: center;
        justify-content: center;
        text-align: center;
    }
    .bento-card-cyan {
        background:
            radial-gradient(circle at 90% 85%, rgba(6, 182, 212, 0.20) 0%, transparent 55%),
            linear-gradient(155deg, rgba(20, 27, 45, 0.96) 0%, rgba(12, 17, 29, 0.98) 100%);
        border: 1px solid rgba(6, 182, 212, 0.32);
    }
    .bento-title {
        font-size: 0.82rem;
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.02em;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
    }
    .bento-big-val {
        font-size: 1.85rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.02em;
        line-height: 1.15;
        margin-bottom: 8px;
    }
    .bento-badge-green {
        display: inline-flex;
        align-items: center;
        background: rgba(16, 185, 129, 0.18);
        border: 1px solid rgba(16, 185, 129, 0.45);
        color: #34d399;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        width: fit-content;
    }
    .bento-badge-purple {
        display: inline-flex;
        align-items: center;
        background: rgba(139, 92, 246, 0.20);
        border: 1px solid rgba(167, 139, 250, 0.45);
        color: #c4b5fd;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        width: fit-content;
    }
    .bento-badge-amber {
        display: inline-flex;
        align-items: center;
        background: rgba(245, 158, 11, 0.18);
        border: 1px solid rgba(251, 191, 36, 0.45);
        color: #fbbf24;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        width: fit-content;
    }
    .bento-sub {
        font-size: 0.77rem;
        color: #94a3b8;
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 1.1 ACESSO SEGURO AO ST.SECRETS E AUTENTICAÇÃO POR SENHA (FAIL-CLOSED)
# ==============================================================================
def obter_secret(chave: str, padrao=None):
    try:
        return st.secrets.get(chave, padrao)
    except Exception:
        return padrao


def tem_secret(chave: str) -> bool:
    try:
        return chave in st.secrets
    except Exception:
        return False


def verificar_autenticacao() -> bool:
    senha_correta = str(obter_secret("app_password", "")).strip()
    if not senha_correta:
        st.error(
            "🔒 **Acesso Bloqueado por Segurança:** A credencial `app_password` não foi configurada "
            "em `st.secrets`. Adicione `app_password = \"SuaSenhaForte\"` nas configurações de Secrets "
            "do Streamlit Cloud (ou em `.streamlit/secrets.toml`) para liberar o acesso ao sistema."
        )
        return False
    if st.session_state.get("autenticado_esteio", False):
        return True
    col_v1, col_login, col_v2 = st.columns([1, 1.4, 1])
    with col_login:
        st.markdown(
            """
            <div class="glass-card" style="margin-top: 40px; text-align: center;">
                <h3>🔒 Esteio Rural — Acesso Restrito</h3>
                <p style="color: #94a3b8; font-size: 0.9rem;">
                    Insira a credencial de operação para acessar o painel de estoque e custos.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_login_esteio"):
            senha_digitada = st.text_input("Senha de acesso:", type="password")
            btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
            if btn_entrar:
                if hmac.compare_digest(senha_digitada.encode("utf-8"), senha_correta.encode("utf-8")):
                    st.session_state["autenticado_esteio"] = True
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta. Tente novamente.")
    return False


if not verificar_autenticacao():
    st.stop()


# ==============================================================================
# 2. FORMATAÇÃO BRASILEIRA (1.000,00), CENTRALIZAÇÃO E ESQUEMAS DE DADOS
# ==============================================================================
DIAS_MAX_HISTORICO = 180
DIAS_PADRAO_SONECA_COMPRA = 15
TAMANHO_LOTE_MIGRACAO = 4000
LIMITE_COINCIDENCIA_CATALOGO = 80.0
COLUNAS_NUMERICAS = {
    "saldo_geral",
    "saldo_lote",
    "custo_unitario",
    "qtd_vendida",
    "qtd_entrada",
    "valor_entrada",
    "qtd_saida",
    "valor_venda",
    "qtd_comprada",
}
ESQUEMA_ABAS = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada", "valor_entrada", "data"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida", "valor_venda", "data"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "pedidos_transito": ["codigo", "descricao", "qtd_comprada", "data_compra", "silenciar_ate"],
    "meta": ["chave", "valor"],
}
COLUNAS_OBRIGATORIAS_UPLOAD = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao"],
    "pedidos_transito": ["codigo", "descricao"],
    "meta": ["chave", "valor"],
}
ORDEM_POSICIONAL_PADRAO = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada", "valor_entrada", "data"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida", "valor_venda", "data"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "pedidos_transito": ["codigo", "descricao", "qtd_comprada", "data_compra", "silenciar_ate"],
    "meta": ["chave", "valor"],
}
MAPA_SINONIMOS = {
    "codigo": [
        "codigo",
        "cod",
        "cod_produto",
        "codigo_produto",
        "codigo_do_produto",
        "codigo_produto_acabado",
        "cod_produto_acabado",
        "codigo_do_produto_acabado",
        "sku",
        "id",
        "item",
    ],
    "saldo_geral": [
        "saldo_geral",
        "saldogeral",
        "quantidade_do_saldo_inicial_dos_produtos_no_controle_de_saldo",
        "quantidade_do_saldo_inicial",
        "saldo_inicial",
        "estoque_geral",
        "saldo_total",
        "saldo_atual",
        "estoque_atual",
        "saldo_fisico",
        "saldo",
    ],
    "descricao": [
        "descricao",
        "descricao_do_produto_servico",
        "descricao_produto_servico",
        "descricao_do_produto_predominante",
        "descricao_produto_predominante",
        "produto_predominante",
        "descricao_do_produto_acabado",
        "descricao_produto_acabado",
        "desc",
        "descricao_produto",
        "descricao_do_produto",
        "produto",
        "nome",
        "mercadoria",
    ],
    "lote": [
        "lote",
        "codigo_do_lote",
        "cod_lote",
        "codigo_lote",
        "num_lote",
        "numero_lote",
        "lotes",
    ],
    "saldo_lote": [
        "saldo_lote",
        "sald_lot",
        "saldo_lot",
        "saldolote",
        "saldo_do_lote",
        "qtd_lote",
        "estoque_lote",
        "quant_lote",
    ],
    "validade": [
        "validade",
        "validade_tempo_germinacao",
        "data_de_validade_germinacao_do_lote",
        "data_validade_germinacao_do_lote",
        "validade_germinacao_do_lote",
        "validade_germinacao",
        "data_validade",
        "dt_validade",
        "data_de_validade",
        "vencimento",
        "data_vencimento",
        "validade_lote",
        "val",
    ],
    "data": [
        "data",
        "data_posicao",
        "data_ref",
        "data_importacao",
        "dt",
        "dia",
    ],
    "custo_unitario": [
        "custo_unitario",
        "custo_unitario_c1",
        "custo_c1",
        "c1",
        "custo",
        "custo_medio",
        "custo_medio_unitario",
        "preco_custo",
        "valor_unitario",
        "cmv",
    ],
    "qtd_vendida": [
        "qtd_vendida",
        "quantidade_vendida",
        "vend_pro",
        "venda_pro",
        "venda_produto",
        "vendas_produto",
        "qtd_venda",
        "quantidade",
        "qtd",
        "vendas",
        "saida",
        "total_vendido",
    ],
    "qtd_entrada": [
        "qtd_entrada",
        "quantidade_entrada",
        "ent_pro",
        "compra_pro",
        "qtd_compra",
        "entrada",
        "entradas",
        "qtd_comprada",
        "quantidade",
        "qtd",
    ],
    "valor_entrada": [
        "valor_entrada",
        "valor",
        "vlr",
        "valor_total",
        "vlr_total",
        "valor_total_entrada",
        "total_entrada",
        "valor_nf",
        "vlr_nf",
        "valor_liquido",
        "valor_bruto",
        "valor_total_da_proposta",
        "custo_total",
        "custo_unitario",
        "custo_c1",
        "valor_unitario",
    ],
    "qtd_saida": [
        "qtd_saida",
        "quantidade_saida",
        "vend_pro",
        "venda_pro",
        "venda_produto",
        "vendas_produto",
        "qtd_venda",
        "qtd_vendida",
        "quantidade_vendida",
        "saida",
        "saidas",
        "vendas",
        "quantidade",
        "qtd",
        "total_vendido",
    ],
    "valor_venda": [
        "valor_venda",
        "valor_total_da_proposta",
        "valor_total_proposta",
        "vlr_total_da_proposta",
        "vlr_total_proposta",
        "valor_da_proposta",
        "valor_proposta",
        "valor_total_venda",
        "valor_total",
        "faturamento",
        "receita",
        "valor_liquido",
        "total_venda",
        "vlr_venda",
    ],
    "data_ocultado": ["data_ocultado", "data", "ocultado_em"],
    "qtd_comprada": ["qtd_comprada", "quantidade_comprada", "qtd_pedido", "sugestao_compra", "qtd"],
    "data_compra": ["data_compra", "comprado_em", "data_pedido", "data"],
    "silenciar_ate": ["silenciar_ate", "ocultar_ate", "expira_em", "valido_ate"],
    "chave": ["chave", "key", "parametro", "config"],
    "valor": ["valor", "value", "conteudo"],
}


def formatar_num_br(valor, casas: int = 0) -> str:
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return str(valor)
    if casas <= 0:
        return f"{v:,.0f}".replace(",", ".")
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_qtd_br(valor) -> str:
    if pd.isna(valor) or valor is None:
        return "0"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return str(valor)
    if abs(v - round(v)) < 0.005:
        return formatar_num_br(round(v), 0)
    return formatar_num_br(v, 2)


def formatar_moeda_br(valor) -> str:
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return "R$ 0,00"
    if 0 < abs(v) < 1.0 and abs(v * 100 - round(v * 100)) > 0.01:
        return f"R$ {formatar_num_br(v, 3)}"
    return f"R$ {formatar_num_br(v, 2)}"


def formatar_pct_br(valor, casas: int = 1, com_sinal: bool = False) -> str:
    if pd.isna(valor) or valor is None:
        return "0,0%"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return "0,0%"
    prefixo = "+" if (com_sinal and v > 0) else ""
    return f"{prefixo}{formatar_num_br(v, casas)}%"


def estilizar_tabela_br(
    df: pd.DataFrame,
    formatadores: dict = None,
    colunas_esquerda: list = None,
):
    if df is None or df.empty:
        return df
    cols_esq = set(colunas_esquerda or ["Descrição"])
    cols_centro = [c for c in df.columns if c not in cols_esq]
    styler = df.style
    if formatadores:
        fmt_validos = {k: v for k, v in formatadores.items() if k in df.columns}
        if fmt_validos:
            styler = styler.format(fmt_validos, na_rep="-")
    if cols_centro:
        styler = styler.set_properties(subset=cols_centro, **{"text-align": "center"})
    cols_esq_presentes = [c for c in df.columns if c in cols_esq]
    if cols_esq_presentes:
        styler = styler.set_properties(subset=cols_esq_presentes, **{"text-align": "left"})
    styler = styler.set_table_styles(
        [{"selector": "th", "props": [("text-align", "center")]}]
    )
    return styler


def normalizar_chave_coluna(nome: str) -> str:
    s = unicodedata.normalize("NFKD", str(nome)).encode("ASCII", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.lower()).strip("_")
    return s


def limpar_serie_texto(serie: pd.Series) -> pd.Series:
    def _limpar_val(v):
        if pd.isna(v) or v is None:
            return ""
        if isinstance(v, (datetime, date, pd.Timestamp)):
            return v.strftime("%d/%m/%Y")
        if isinstance(v, float):
            if v.is_integer():
                return str(int(v))
            return str(v)
        s = str(v).strip()
        if s.lower() in ("nan", "none", "nat", "<na>"):
            return ""
        return re.sub(r"^(\d+)\.0$", r"\1", s)
    return serie.map(_limpar_val)


def normalizar_codigo_sku(val) -> str:
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat", "<na>"):
        return ""
    s = re.sub(r"^(\d+)\.0$", r"\1", s)
    s = re.sub(r"^0+(?=\d)", "", s)
    return s


def limpar_serie_codigo(serie: pd.Series) -> pd.Series:
    return limpar_serie_texto(serie).map(normalizar_codigo_sku)


def converter_numero_br(
    serie: pd.Series,
    nome_coluna: str = "",
    origem_gsheets: bool = False,
    bloquear_invalidos: bool = False,
    codigos_ref: pd.Series = None,
) -> pd.Series:
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0.0).astype(float)
    mask_nativo_num = serie.map(
        lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and pd.notna(x)
    )
    if mask_nativo_num.all():
        return serie.astype(float)
    s_str = (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.replace("R$", "", regex=False)
        .str.replace("r$", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    s_apenas_str = s_str[~mask_nativo_num]
    tem_virgula_decimal_na_coluna = s_apenas_str.str.contains(r",\d+$", regex=True).any()
    tem_ponto_nao_3_digitos = s_apenas_str.str.match(
        r"^[+-]?\d+\.\d{1,2}$|^[+-]?\d+\.\d{4,}$|^[+-]?0\.\d+$"
    ).any()
    if origem_gsheets:
        tratar_1ponto_3dig_como_milhar = False
    elif nome_coluna in ("saldo_geral", "saldo_lote", "qtd_vendida", "qtd_entrada", "qtd_saida"):
        tratar_1ponto_3dig_como_milhar = (not tem_ponto_nao_3_digitos) or tem_virgula_decimal_na_coluna
    else:
        tratar_1ponto_3dig_como_milhar = (not tem_ponto_nao_3_digitos) and tem_virgula_decimal_na_coluna
    erros_encontrados = []
    valores_convertidos = []
    for idx, val in serie.items():
        if pd.isna(val) or val is None:
            valores_convertidos.append(0.0)
            continue
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            v_flt = float(val)
            if math.isnan(v_flt) or math.isinf(v_flt):
                valores_convertidos.append(0.0)
            else:
                valores_convertidos.append(v_flt)
            continue
        txt_bruto = str(val).strip()
        txt = (
            txt_bruto.replace("R$", "")
            .replace("r$", "")
            .replace("\u00a0", "")
            .replace(" ", "")
        )
        if not txt or txt.lower() in ("-", "--", "nan", "none", "nat", "<na>"):
            valores_convertidos.append(0.0)
            continue
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            if txt.count(",") == 1:
                txt = txt.replace(",", ".")
            elif re.match(r"^[+-]?[1-9]\d{0,2}(,\d{3})+$", txt):
                txt = txt.replace(",", "")
        elif "." in txt:
            if txt.count(".") >= 2 and re.match(r"^[+-]?[1-9]\d{0,2}(\.\d{3}){2,}$", txt):
                txt = txt.replace(".", "")
            elif tratar_1ponto_3dig_como_milhar and re.match(r"^[+-]?[1-9]\d{0,2}\.\d{3}$", txt):
                txt = txt.replace(".", "")
        try:
            num = float(txt)
            if math.isnan(num) or math.isinf(num):
                raise ValueError("NaN/Inf")
            valores_convertidos.append(num)
        except ValueError:
            if bloquear_invalidos:
                cod_id = ""
                if codigos_ref is not None and idx in codigos_ref.index:
                    cod_id = str(codigos_ref.loc[idx]).strip()
                identificador = f"SKU '{cod_id}'" if cod_id else f"Linha {idx + 2}"
                erros_encontrados.append(f"{identificador} (valor lido: '{txt_bruto}')")
            valores_convertidos.append(0.0)
    if bloquear_invalidos and erros_encontrados:
        amostra = ", ".join(erros_encontrados[:8])
        raise ValueError(
            f"Trava de Segurança (Valor Numérico Inválido na coluna '{nome_coluna}'): "
            f"Foram encontrados {len(erros_encontrados)} registro(s) com texto inválido ou erro de fórmula "
            f"que seriam zerados indevidamente. Exemplos: {amostra}. "
            f"Corrija esses itens na planilha antes de importar."
        )
    return pd.Series(valores_convertidos, index=serie.index, dtype=float)


FORMATOS_DATA_ACEITOS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%y")


def _parse_data_segura_py(valor, ano_min: int = 2000, ano_max: int = None):
    if ano_max is None:
        ano_max = hoje_br().year + 15
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return datetime(valor.year, valor.month, valor.day) if (ano_min <= valor.year <= ano_max) else None
    s = str(valor).strip()
    if not s or s.lower() in {"nan", "none", "nat", "<na>", "0", "0.0", "-", "--", "sem validade", "s/v"}:
        return None
    s_data = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?.*$", "", s).strip()
    m_ano = re.search(r"\b(\d{4})\b", s_data)
    if m_ano:
        ano_int = int(m_ano.group(1))
        if ano_int < ano_min or ano_int > ano_max:
            return None
    for fmt in FORMATOS_DATA_ACEITOS:
        try:
            dt = datetime.strptime(s_data, fmt)
            if ano_min <= dt.year <= ano_max:
                return dt
            return None
        except ValueError:
            continue
    return None


def formatar_validade_padrao(valor) -> str:
    dt = _parse_data_segura_py(valor, ano_min=2000, ano_max=hoje_br().year + 15)
    return dt.strftime("%d/%m/%Y") if dt is not None else ""


def converter_datas_deterministico(serie: pd.Series) -> pd.Series:
    if serie is None or serie.empty:
        return pd.Series(dtype="datetime64[ns]")
    ano_teto = hoje_br().year + 15
    unicos = serie.dropna().unique()
    mapa = {val: _parse_data_segura_py(val, ano_min=2000, ano_max=ano_teto) for val in unicos}
    lista_dt = [mapa.get(v, None) if pd.notna(v) else None for v in serie]
    return pd.to_datetime(pd.Series(lista_dt, index=serie.index, dtype="object"), errors="coerce").astype("datetime64[ns]")


def restaurar_tipos(
    df: pd.DataFrame,
    origem_gsheets: bool = False,
    bloquear_invalidos: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        if col not in COLUNAS_NUMERICAS:
            if col == "codigo":
                df[col] = limpar_serie_codigo(df[col])
            elif col == "validade":
                df[col] = df[col].map(formatar_validade_padrao)
            else:
                df[col] = limpar_serie_texto(df[col])
    codigos_ref = df["codigo"] if "codigo" in df.columns else None
    for col in df.columns:
        if col in COLUNAS_NUMERICAS:
            df[col] = converter_numero_br(
                df[col],
                nome_coluna=col,
                origem_gsheets=origem_gsheets,
                bloquear_invalidos=bloquear_invalidos,
                codigos_ref=codigos_ref,
            )
    return df


def estruturar_dataframe_bruto(
    df: pd.DataFrame,
    nome_aba: str,
    exigir_colunas_obrigatorias: bool = False,
    origem_gsheets: bool = False,
) -> pd.DataFrame:
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    colunas_esperadas = ESQUEMA_ABAS.get(aba_esquema, [])
    if df is None or df.empty:
        return restaurar_tipos(pd.DataFrame(columns=colunas_esperadas), origem_gsheets=origem_gsheets)
    df_orig = df.loc[:, ~df.columns.duplicated()].copy()
    if aba_esquema == "historico" and not exigir_colunas_obrigatorias:
        cols_norm_hist = [normalizar_chave_coluna(c) for c in df_orig.columns]
        if "codigo" not in cols_norm_hist:
            if df_orig.shape[1] >= 7:
                df_pos = df_orig.iloc[:, :7].copy()
                df_pos.columns = ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"]
                df_orig = df_pos
            elif df_orig.shape[1] == 5:
                df_pos = df_orig.iloc[:, :5].copy()
                df_pos.columns = ["codigo", "saldo_geral", "lote", "saldo_lote", "data"]
                df_orig = df_pos
    cols_norm = {col: normalizar_chave_coluna(col) for col in df_orig.columns}
    renomear = {}
    colunas_orig_usadas = set()
    alvos_encontrados = set()
    for col_alvo in colunas_esperadas:
        sinonimos = MAPA_SINONIMOS.get(col_alvo, [col_alvo])
        for sin in sinonimos:
            encontrada = None
            for col_orig, norm in cols_norm.items():
                if col_orig not in colunas_orig_usadas and norm == sin:
                    encontrada = col_orig
                    break
            if encontrada is not None:
                renomear[encontrada] = col_alvo
                colunas_orig_usadas.add(encontrada)
                alvos_encontrados.add(col_alvo)
                break
    if aba_esquema in ("saidas_diarias", "entradas_diarias") and df_orig.shape[1] >= 4:
        col_fin_alvo = "valor_venda" if aba_esquema == "saidas_diarias" else "valor_entrada"
        if col_fin_alvo not in alvos_encontrados:
            termos_fin_validos = (
                ("valor", "vlr", "proposta", "faturamento", "receita", "preco", "liquido", "bruto", "total_venda")
                if aba_esquema == "saidas_diarias"
                else ("valor", "vlr", "custo", "c1", "nf", "nota", "preco", "liquido", "bruto", "total")
            )
            termos_nao_fin = (
                ("saldo", "estoque", "lote", "validade", "custo", "cmv", "cod", "qtd", "quant", "data")
                if aba_esquema == "saidas_diarias"
                else ("saldo", "estoque", "lote", "validade", "cod", "qtd", "quant", "data")
            )
            for col_cand in list(df_orig.columns)[3:]:
                norm_cand = cols_norm.get(col_cand, "")
                if (
                    col_cand not in colunas_orig_usadas
                    and any(t in norm_cand for t in termos_fin_validos)
                    and not any(b in norm_cand for b in termos_nao_fin)
                ):
                    renomear[col_cand] = col_fin_alvo
                    colunas_orig_usadas.add(col_cand)
                    alvos_encontrados.add(col_fin_alvo)
                    break
    if not exigir_colunas_obrigatorias:
        if aba_esquema == "saidas_diarias" and df_orig.shape[1] == 4 and "valor_venda" not in alvos_encontrados:
            ordem_padrao = ["codigo", "descricao", "qtd_saida", "data"]
        elif aba_esquema == "entradas_diarias" and df_orig.shape[1] == 4 and "valor_entrada" not in alvos_encontrados:
            ordem_padrao = ["codigo", "descricao", "qtd_entrada", "data"]
        else:
            ordem_padrao = ORDEM_POSICIONAL_PADRAO.get(aba_esquema, colunas_esperadas)
        cols_orig_lista = list(df_orig.columns)
        for idx_pos, col_alvo in enumerate(ordem_padrao):
            if col_alvo not in alvos_encontrados and idx_pos < len(cols_orig_lista):
                col_candidata = cols_orig_lista[idx_pos]
                if col_candidata not in colunas_orig_usadas:
                    renomear[col_candidata] = col_alvo
                    colunas_orig_usadas.add(col_candidata)
                    alvos_encontrados.add(col_alvo)
    df = df_orig.rename(columns=renomear)
    if exigir_colunas_obrigatorias:
        obrigatorias = COLUNAS_OBRIGATORIAS_UPLOAD.get(aba_esquema, [])
        ausentes = [c for c in obrigatorias if c not in df.columns]
        if ausentes:
            cols_lidas = ", ".join(f"'{c}'" for c in df_orig.columns[:10])
            raise ValueError(
                f"Trava contra Coluna Desconhecida ou Trocada ('{aba_esquema}'): "
                f"Não foi possível localizar a(s) coluna(s) obrigatória(s) **{', '.join(ausentes)}** pelo cabeçalho. "
                f"Cabeçalhos encontrados na planilha enviada: [{cols_lidas}]. "
                f"Verifique se a planilha está correta e com os títulos de coluna esperados."
            )
    for col_alvo in colunas_esperadas:
        if col_alvo not in df.columns:
            if col_alvo in COLUNAS_NUMERICAS:
                df[col_alvo] = 0.0
            elif col_alvo in ("data", "data_ocultado", "data_compra"):
                df[col_alvo] = hoje_br().strftime("%Y-%m-%d")
            elif col_alvo == "silenciar_ate":
                df[col_alvo] = (hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
            else:
                df[col_alvo] = ""
    df = df[colunas_esperadas].copy()
    if "codigo" in df.columns:
        df["codigo"] = limpar_serie_codigo(df["codigo"])
        df = df[df["codigo"] != ""].copy()
        df = df[
            ~df["codigo"].str.lower().isin(
                ["codigo", "código", "cod", "sku", "id", "item", "total", "total geral", "subtotal"]
            )
        ].copy()
    df = restaurar_tipos(
        df,
        origem_gsheets=origem_gsheets,
        bloquear_invalidos=exigir_colunas_obrigatorias and (not origem_gsheets),
    )
    return df.reset_index(drop=True)


def compactar_estoque_para_historico(df_est: pd.DataFrame) -> pd.DataFrame:
    """Compacta o estoque para 1 linha por SKU (apenas saldo_geral != 0) e 3 colunas (codigo, saldo_geral, data)."""
    if df_est is None or df_est.empty:
        return pd.DataFrame(columns=ESQUEMA_ABAS["historico"])
    df_h = estruturar_dataframe_bruto(df_est, "historico")
    if df_h.empty:
        return df_h
    df_h = df_h.drop_duplicates(subset=["codigo", "data"], keep="last")
    df_h = df_h[df_h["saldo_geral"].abs() > 1e-9].copy()
    return df_h.reset_index(drop=True)


def padronizar_dataframe(
    df: pd.DataFrame,
    nome_aba: str,
    origem_gsheets: bool = False,
) -> pd.DataFrame:
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    df = estruturar_dataframe_bruto(df, aba_esquema, origem_gsheets=origem_gsheets)
    if df.empty:
        return df
    if aba_esquema == "estoque_atual":
        df = df.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
    elif aba_esquema == "historico":
        df = df.drop_duplicates(subset=["codigo", "data"], keep="last")
        df = df[df["saldo_geral"].abs() > 1e-9].copy()
    elif aba_esquema in ("entradas_diarias", "saidas_diarias"):
        df = df.drop_duplicates(subset=["codigo", "data"], keep="last")
    elif aba_esquema in ("custos", "ocultos", "pedidos_transito"):
        df = df.drop_duplicates(subset=["codigo"], keep="last")
    return df.reset_index(drop=True)


def depurar_pedidos_transito_auto_despertar(
    df_transito: pd.DataFrame,
    df_entradas: pd.DataFrame,
) -> tuple[pd.DataFrame, list, list]:
    """
    Mantém apenas os itens em 'pedidos_transito' dentro do prazo de 15 dias e que ainda NÃO
    tiveram entrada na planilha de Entradas (NF) em data >= data_compra (Auto-Despertar).
    """
    if df_transito is None or df_transito.empty:
        return padronizar_dataframe(pd.DataFrame(), "pedidos_transito"), [], []
    df_t = padronizar_dataframe(df_transito, "pedidos_transito")
    if df_t.empty:
        return df_t, [], []

    hoje_iso = hoje_br().strftime("%Y-%m-%d")
    dt_comp_s = converter_datas_deterministico(df_t["data_compra"])
    dt_sil_s = converter_datas_deterministico(df_t["silenciar_ate"])

    datas_compra_iso = []
    datas_sil_iso = []
    for idx_r, r_t in df_t.iterrows():
        dc = dt_comp_s.loc[idx_r]
        ds = dt_sil_s.loc[idx_r]
        dc_iso = dc.strftime("%Y-%m-%d") if pd.notna(dc) else hoje_iso
        if pd.notna(ds):
            ds_iso = ds.strftime("%Y-%m-%d")
        else:
            dt_base_c = dc if pd.notna(dc) else pd.Timestamp(hoje_br())
            ds_iso = (dt_base_c + pd.Timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
        datas_compra_iso.append(dc_iso)
        datas_sil_iso.append(ds_iso)

    df_t["data_compra"] = datas_compra_iso
    df_t["silenciar_ate"] = datas_sil_iso

    mapa_ult_ent = {}
    if df_entradas is not None and not df_entradas.empty and "codigo" in df_entradas.columns and "data" in df_entradas.columns:
        df_e_pos = df_entradas[df_entradas["qtd_entrada"] > 0].copy()
        if not df_e_pos.empty:
            dt_e = converter_datas_deterministico(df_e_pos["data"])
            df_e_pos["_dt_iso"] = dt_e.dt.strftime("%Y-%m-%d").fillna("")
            df_e_pos = df_e_pos[df_e_pos["_dt_iso"] != ""]
            if not df_e_pos.empty:
                mapa_ult_ent = df_e_pos.groupby("codigo")["_dt_iso"].max().to_dict()

    cods_despertados_nf = []
    cods_expirados_15d = []
    indices_manter = []

    for idx_r, r_t in df_t.iterrows():
        cod = str(r_t["codigo"]).strip()
        dc_iso = str(r_t["data_compra"]).strip()
        ds_iso = str(r_t["silenciar_ate"]).strip()
        ult_ent_iso = mapa_ult_ent.get(cod, "")
        if ult_ent_iso and ult_ent_iso >= dc_iso:
            cods_despertados_nf.append(cod)
            continue
        if ds_iso < hoje_iso:
            cods_expirados_15d.append(cod)
            continue
        indices_manter.append(idx_r)

    df_ativos = df_t.loc[indices_manter].reset_index(drop=True)
    return df_ativos, cods_despertados_nf, cods_expirados_15d


def podar_historico_180_dias(df_hist: pd.DataFrame, nome_aba: str = "historico") -> pd.DataFrame:
    if df_hist is None or df_hist.empty or "data" not in df_hist.columns:
        return padronizar_dataframe(pd.DataFrame(), nome_aba)
    df_h = df_hist.copy()
    if "codigo" in df_h.columns:
        df_h["codigo"] = limpar_serie_codigo(df_h["codigo"])
    dt_parsed = converter_datas_deterministico(df_h["data"])
    mask_valida = dt_parsed.notna()
    df_h = df_h.loc[mask_valida].copy()
    if df_h.empty:
        return padronizar_dataframe(pd.DataFrame(), nome_aba)
    dt_validas = dt_parsed.loc[mask_valida]
    df_h["data"] = dt_validas.dt.strftime("%Y-%m-%d")
    limite_ts = pd.Timestamp(hoje_br() - timedelta(days=DIAS_MAX_HISTORICO))
    df_filtrado = df_h[dt_validas >= limite_ts].copy()
    chaves_dedup = ["codigo", "lote", "data"] if "lote" in df_filtrado.columns else ["codigo", "data"]
    df_filtrado = df_filtrado.drop_duplicates(subset=chaves_dedup, keep="last")
    if nome_aba == "historico" and "saldo_geral" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["saldo_geral"].abs() > 1e-9].copy()
    return df_filtrado.reset_index(drop=True)


# ==============================================================================
# 3. CONEXÃO 100% NUVEM COM GOOGLE SHEETS (RESIZE ANTES DO UPDATE)
# ==============================================================================
@st.cache_resource(ttl=3600, show_spinner=False)
def _conectar_planilha_cached(nome_planilha: str):
    import gspread
    from google.oauth2.service_account import Credentials
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credenciais = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=escopos
    )
    cliente = gspread.authorize(credenciais)
    return cliente.open(nome_planilha)


def obter_planilha_gsheets():
    if not tem_secret("gcp_service_account"):
        return None, "Bloco [gcp_service_account] ausente nas configurações de Secrets da nuvem."
    try:
        nome_planilha = str(obter_secret("sheet_name", "Banco_Dados_Esteio_Rural")).strip()
        planilha = _conectar_planilha_cached(nome_planilha)
        return planilha, None
    except Exception as e:
        return None, str(e)


def obter_ou_criar_aba(planilha, nome_aba: str, linhas: int = 100, cols: int = 10):
    import gspread
    try:
        return planilha.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        return planilha.add_worksheet(
            title=nome_aba, rows=max(linhas, 100), cols=max(cols, 10)
        )


def ler_aba_bruta_gsheets(planilha, nome_aba: str) -> pd.DataFrame:
    ws = obter_ou_criar_aba(planilha, nome_aba)
    valores = ws.get_all_values()
    if not valores or len(valores) < 2:
        return padronizar_dataframe(pd.DataFrame(), nome_aba, origem_gsheets=True)
    cabecalho = [
        str(c).strip() if str(c).strip() else f"col_{i}"
        for i, c in enumerate(valores[0])
    ]
    df = pd.DataFrame(valores[1:], columns=cabecalho)
    return padronizar_dataframe(df, nome_aba, origem_gsheets=True)


def gravar_aba_pequena_gsheets(planilha, nome_aba: str, df: pd.DataFrame, permitir_vazio: bool = False):
    if df is None:
        return
    if df.empty and not permitir_vazio:
        return
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    df_padrao = padronizar_dataframe(df, aba_esquema) if aba_esquema in ESQUEMA_ABAS else df
    df_str = df_padrao.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    if df_str.empty:
        dados = [cabecalho, ["" for _ in cabecalho]]
    else:
        dados = [cabecalho] + df_str.values.tolist()
    linhas_nec = max(len(dados), 2)
    cols_nec = max(len(cabecalho), 1)
    ws = obter_ou_criar_aba(planilha, nome_aba, linhas_nec + 10, cols_nec + 2)
    if ws.row_count < linhas_nec or ws.col_count < cols_nec:
        ws.resize(rows=max(ws.row_count, linhas_nec + 10), cols=max(ws.col_count, cols_nec))
    ws.update(values=dados, range_name="A1", value_input_option="RAW")
    ws.resize(rows=linhas_nec, cols=cols_nec)


def migrar_aba_incremental_em_lotes(planilha, ws_antiga, df_combinado: pd.DataFrame, nome_aba: str = "historico"):
    import gspread
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    df_padrao = podar_historico_180_dias(padronizar_dataframe(df_combinado, aba_esquema), aba_esquema)
    df_str = df_padrao.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    todas_linhas = df_str.values.tolist()
    nome_temp = f"{nome_aba[:18]}_mig_temp"
    try:
        ws_temp_existente = planilha.worksheet(nome_temp)
        planilha.del_worksheet(ws_temp_existente)
    except gspread.exceptions.WorksheetNotFound:
        pass
    ws_temp = planilha.add_worksheet(
        title=nome_temp,
        rows=max(len(todas_linhas) + 50, 100),
        cols=max(len(cabecalho), 5),
    )
    primeiro_bloco = todas_linhas[:TAMANHO_LOTE_MIGRACAO]
    ws_temp.update(
        values=[cabecalho] + primeiro_bloco,
        range_name="A1",
        value_input_option="RAW",
    )
    for ini in range(TAMANHO_LOTE_MIGRACAO, len(todas_linhas), TAMANHO_LOTE_MIGRACAO):
        bloco = todas_linhas[ini : ini + TAMANHO_LOTE_MIGRACAO]
        ws_temp.append_rows(values=bloco, value_input_option="RAW")
    ws_temp.resize(rows=max(len(todas_linhas) + 1, 2), cols=len(cabecalho))
    planilha.del_worksheet(ws_antiga)
    ws_temp.update_title(nome_aba)


def salvar_backup_automatico_aba_gsheets(
    planilha,
    nome_aba_origem: str,
    df_atual_memoria: pd.DataFrame,
    permitir_vazio: bool = False,
):
    """Salva uma cópia rápida em _bkp_<nome_aba> antes de qualquer alteração (suporta abas pequenas e grandes)."""
    if df_atual_memoria is None:
        return
    if df_atual_memoria.empty and not permitir_vazio:
        return
    nome_bkp = f"_bkp_{nome_aba_origem}"
    if len(df_atual_memoria) > TAMANHO_LOTE_MIGRACAO:
        ws_bkp = obter_ou_criar_aba(planilha, nome_bkp)
        migrar_aba_incremental_em_lotes(planilha, ws_bkp, df_atual_memoria, nome_aba=nome_bkp)
    else:
        gravar_aba_pequena_gsheets(planilha, nome_bkp, df_atual_memoria, permitir_vazio=permitir_vazio)


def remover_datas_aba_incremental_gsheets(
    planilha,
    nome_aba: str,
    datas_remover: set,
    df_atual_memoria: pd.DataFrame = None,
) -> int:
    """Remove de uma aba incremental todas as linhas das datas informadas, salvando backup automático antes."""
    datas_iso_alvo = set()
    for d in (datas_remover or set()):
        dt_p = converter_datas_deterministico(pd.Series([str(d).strip()]))
        if not dt_p.empty and pd.notna(dt_p.iloc[0]):
            datas_iso_alvo.add(dt_p.iloc[0].strftime("%Y-%m-%d"))
        elif str(d).strip():
            datas_iso_alvo.add(str(d).strip())
    if not datas_iso_alvo:
        return 0
    df_base = (
        df_atual_memoria.copy()
        if (df_atual_memoria is not None and not df_atual_memoria.empty)
        else ler_aba_bruta_gsheets(planilha, nome_aba)
    )
    if df_base.empty or "data" not in df_base.columns:
        return 0
    mask_rem = df_base["data"].isin(datas_iso_alvo)
    qtd_removidas = int(mask_rem.sum())
    if qtd_removidas <= 0:
        return 0
    salvar_backup_automatico_aba_gsheets(planilha, nome_aba, df_base, permitir_vazio=True)
    df_restante = df_base[~mask_rem].copy().reset_index(drop=True)
    if len(df_restante) <= TAMANHO_LOTE_MIGRACAO:
        gravar_aba_pequena_gsheets(planilha, nome_aba, df_restante, permitir_vazio=True)
    else:
        ws = obter_ou_criar_aba(planilha, nome_aba)
        migrar_aba_incremental_em_lotes(planilha, ws, df_restante, nome_aba=nome_aba)
    return qtd_removidas


def restaurar_backup_automatico_aba_gsheets(
    planilha,
    nome_aba_destino: str,
    df_atual_memoria: pd.DataFrame = None,
) -> int:
    """Restaura o conteúdo de _bkp_<nome_aba_destino> para qualquer aba do sistema (incluindo entradas, saídas, ocultos e histórico)."""
    import gspread
    nome_bkp = f"_bkp_{nome_aba_destino}"
    try:
        ws_bkp = planilha.worksheet(nome_bkp)
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Ainda não existe cópia automática anterior (`{nome_bkp}`) para restaurar.")
    valores = ws_bkp.get_all_values()
    aba_permite_vazio = nome_aba_destino in ("ocultos", "pedidos_transito", "entradas_diarias", "saidas_diarias")
    if not valores or len(valores) < 2:
        if aba_permite_vazio:
            df_vazio = padronizar_dataframe(pd.DataFrame(), nome_aba_destino)
            gravar_aba_pequena_gsheets(planilha, nome_aba_destino, df_vazio, permitir_vazio=True)
            return 0
        raise ValueError(f"A cópia automática (`{nome_bkp}`) está vazia.")
    cabecalho = [str(c).strip() if str(c).strip() else f"col_{i}" for i, c in enumerate(valores[0])]
    df_bkp = padronizar_dataframe(pd.DataFrame(valores[1:], columns=cabecalho), nome_aba_destino, origem_gsheets=True)
    if df_bkp.empty and not aba_permite_vazio:
        raise ValueError(f"Nenhum registro válido encontrado na cópia automática (`{nome_bkp}`).")
    if nome_aba_destino == "estoque_atual":
        datas_atuais = set()
        if df_atual_memoria is not None and not df_atual_memoria.empty and "data" in df_atual_memoria.columns:
            datas_atuais.update(str(d).strip() for d in df_atual_memoria["data"].unique() if str(d).strip())
        df_est_nuvem = ler_aba_bruta_gsheets(planilha, "estoque_atual")
        if not df_est_nuvem.empty and "data" in df_est_nuvem.columns:
            datas_atuais.update(str(d).strip() for d in df_est_nuvem["data"].unique() if str(d).strip())
        datas_rest = (
            {str(d).strip() for d in df_bkp["data"].unique() if str(d).strip()}
            if "data" in df_bkp.columns
            else set()
        )
        datas_indevidas = datas_atuais - datas_rest
        if datas_indevidas:
            remover_datas_aba_incremental_gsheets(planilha, "historico", datas_indevidas)
        gravar_aba_pequena_gsheets(planilha, nome_aba_destino, df_bkp)
        for dt_r in sorted(datas_rest):
            df_dia_rest = df_bkp[df_bkp["data"] == dt_r].copy()
            gravar_historico_incremental_gsheets(planilha, df_dia_rest, dt_r, criar_backup=False)
    elif len(df_bkp) > TAMANHO_LOTE_MIGRACAO:
        ws_dest = obter_ou_criar_aba(planilha, nome_aba_destino)
        migrar_aba_incremental_em_lotes(planilha, ws_dest, df_bkp, nome_aba=nome_aba_destino)
    else:
        gravar_aba_pequena_gsheets(planilha, nome_aba_destino, df_bkp, permitir_vazio=aba_permite_vazio)
    return len(df_bkp)


def gravar_aba_incremental_por_data_gsheets(
    planilha,
    nome_aba: str,
    df_novo_dia: pd.DataFrame,
    data_ref: str,
    somar_mesma_data: bool = False,
    df_atual_memoria: pd.DataFrame = None,
    hash_arquivo: str = "",
    criar_backup: bool = True,
):
    """
    Grava dados incrementais por data de forma atômica (sem janela inconsistente entre append e delete)
    e protege contra soma duplicada caso o mesmo arquivo seja reenviado após falha parcial.
    """
    if df_novo_dia is None or df_novo_dia.empty:
        return
    data_ref_str = str(data_ref).strip()
    limite_str = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")

    df_base_existente = (
        df_atual_memoria.copy()
        if (df_atual_memoria is not None and not df_atual_memoria.empty)
        else ler_aba_bruta_gsheets(planilha, nome_aba)
    )
    if not df_base_existente.empty:
        df_base_existente = podar_historico_180_dias(
            padronizar_dataframe(df_base_existente, nome_aba), nome_aba
        )

    if criar_backup and not df_base_existente.empty:
        salvar_backup_automatico_aba_gsheets(planilha, nome_aba, df_base_existente)

    if somar_mesma_data and nome_aba in ("entradas_diarias", "saidas_diarias"):
        col_qtd = "qtd_entrada" if nome_aba == "entradas_diarias" else "qtd_saida"
        registro_hashes = st.session_state.setdefault("hashes_soma_incremental", {})
        chave_op = f"{nome_aba}::{data_ref_str}"
        if (
            hash_arquivo
            and chave_op in registro_hashes
            and registro_hashes[chave_op].get("hash") == hash_arquivo
        ):
            df_mesmo_dia = registro_hashes[chave_op].get("df_base_antes", pd.DataFrame()).copy()
        elif not df_base_existente.empty and "data" in df_base_existente.columns:
            df_mesmo_dia = df_base_existente[df_base_existente["data"] == data_ref_str].copy()
            if hash_arquivo:
                registro_hashes[chave_op] = {
                    "hash": hash_arquivo,
                    "df_base_antes": df_mesmo_dia.copy(),
                }
        else:
            df_mesmo_dia = pd.DataFrame()
            if hash_arquivo:
                registro_hashes[chave_op] = {
                    "hash": hash_arquivo,
                    "df_base_antes": pd.DataFrame(),
                }

        if not df_mesmo_dia.empty:
            df_mesmo_dia = df_mesmo_dia.drop_duplicates(subset=["codigo", "data"], keep="last")
            df_unido = pd.concat([df_mesmo_dia, df_novo_dia], ignore_index=True)
            agg_inc = {
                "descricao": ("descricao", "last"),
                col_qtd: (col_qtd, "sum"),
            }
            if "valor_entrada" in df_unido.columns:
                agg_inc["valor_entrada"] = ("valor_entrada", "sum")
            if "valor_venda" in df_unido.columns:
                agg_inc["valor_venda"] = ("valor_venda", "sum")
            agg_inc["data"] = ("data", "last")
            df_novo_dia = df_unido.groupby("codigo", as_index=False).agg(**agg_inc)

    df_novo_padrao = (
        compactar_estoque_para_historico(df_novo_dia)
        if nome_aba == "historico"
        else padronizar_dataframe(df_novo_dia, nome_aba)
    )
    if df_novo_padrao.empty:
        return

    if not df_base_existente.empty and "data" in df_base_existente.columns:
        df_antigo_sem_data = df_base_existente[
            (df_base_existente["data"] != data_ref_str)
            & (df_base_existente["data"] >= limite_str)
        ].copy()
        df_combinado = pd.concat([df_antigo_sem_data, df_novo_padrao], ignore_index=True)
    else:
        df_combinado = df_novo_padrao.copy()

    df_combinado = podar_historico_180_dias(
        padronizar_dataframe(df_combinado, nome_aba), nome_aba
    )

    if len(df_combinado) <= TAMANHO_LOTE_MIGRACAO:
        gravar_aba_pequena_gsheets(planilha, nome_aba, df_combinado, permitir_vazio=True)
    else:
        ws = obter_ou_criar_aba(planilha, nome_aba, len(df_combinado) + 50, len(df_combinado.columns) + 2)
        migrar_aba_incremental_em_lotes(planilha, ws, df_combinado, nome_aba=nome_aba)


def gravar_historico_incremental_gsheets(
    planilha,
    df_novo_dia: pd.DataFrame,
    data_ref: str,
    df_atual_memoria: pd.DataFrame = None,
    criar_backup: bool = True,
):
    df_compacto = compactar_estoque_para_historico(df_novo_dia)
    gravar_aba_incremental_por_data_gsheets(
        planilha,
        "historico",
        df_compacto,
        data_ref,
        df_atual_memoria=df_atual_memoria,
        criar_backup=criar_backup,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_estado_completo() -> dict:
    planilha, erro = obter_planilha_gsheets()
    if planilha is None:
        raise RuntimeError(f"Não foi possível conectar ao Google Sheets: {erro}")
    df_est = ler_aba_bruta_gsheets(planilha, "estoque_atual")
    df_hist = podar_historico_180_dias(ler_aba_bruta_gsheets(planilha, "historico"), "historico")
    df_ent = podar_historico_180_dias(ler_aba_bruta_gsheets(planilha, "entradas_diarias"), "entradas_diarias")
    df_sai = podar_historico_180_dias(ler_aba_bruta_gsheets(planilha, "saidas_diarias"), "saidas_diarias")
    df_cus = ler_aba_bruta_gsheets(planilha, "custos")
    df_base = ler_aba_bruta_gsheets(planilha, "base_inicial")
    df_ocul = ler_aba_bruta_gsheets(planilha, "ocultos")
    df_trans_bruto = ler_aba_bruta_gsheets(planilha, "pedidos_transito")
    df_trans, cods_desp_nf, cods_exp_15d = depurar_pedidos_transito_auto_despertar(df_trans_bruto, df_ent)
    if len(df_trans) != len(df_trans_bruto):
        try:
            gravar_aba_pequena_gsheets(planilha, "pedidos_transito", df_trans, permitir_vazio=True)
        except Exception:
            pass
    df_meta = ler_aba_bruta_gsheets(planilha, "meta")
    dias_base = 87
    ult_att = "Sincronizado via Nuvem"
    grupos_pref_custom = {}
    grupos_sku_custom = {}
    if not df_meta.empty and "chave" in df_meta.columns and "valor" in df_meta.columns:
        mapa_meta = dict(zip(df_meta["chave"], df_meta["valor"]))
        try:
            dias_base = int(float(mapa_meta.get("dias_base", 87)))
        except ValueError:
            dias_base = 87
        ult_att = mapa_meta.get("ultima_atualizacao", ult_att)
        for ch_m, val_m in mapa_meta.items():
            ch_s = str(ch_m).strip()
            val_s = str(val_m).strip()
            if ch_s.startswith("grp_pref_") and val_s:
                pref_k = ch_s[len("grp_pref_"):].strip()
                if pref_k:
                    grupos_pref_custom[pref_k] = val_s
            elif ch_s.startswith("grp_sku_") and val_s:
                sku_k = normalizar_codigo_sku(ch_s[len("grp_sku_"):])
                if sku_k:
                    grupos_sku_custom[sku_k] = val_s
    return {
        "estoque_atual": df_est,
        "historico": df_hist,
        "entradas_diarias": df_ent,
        "saidas_diarias": df_sai,
        "custos": df_cus,
        "base_inicial": df_base,
        "ocultos": df_ocul,
        "pedidos_transito": df_trans,
        "despertados_nf_recente": cods_desp_nf,
        "expirados_15d_recente": cods_exp_15d,
        "dias_base": dias_base,
        "ultima_atualizacao": ult_att,
        "grupos_pref_custom": grupos_pref_custom,
        "grupos_sku_custom": grupos_sku_custom,
        "df_meta_bruto": df_meta,
    }


# ==============================================================================
# 4. EXPORTAÇÃO E BACKUP EM MEMÓRIA (PLANILHA DO BANCO .XLSX, .ZIP E RELATÓRIOS)
# ==============================================================================
def _formatar_e_centralizar_aba_openpyxl(ws):
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter
    alin_centro = Alignment(horizontal="center", vertical="center")
    alin_esq = Alignment(horizontal="left", vertical="center")
    fonte_cab = Font(bold=True)
    max_row = ws.max_row
    max_col = ws.max_column
    for col_idx in range(1, max_col + 1):
        letra = get_column_letter(col_idx)
        titulo = str(ws.cell(row=1, column=col_idx).value or "").strip()
        titulo_norm = normalizar_chave_coluna(titulo)
        ws.cell(row=1, column=col_idx).alignment = alin_centro
        ws.cell(row=1, column=col_idx).font = fonte_cab
        eh_esquerda = any(p in titulo_norm for p in ["descricao", "diagnostico", "acao_ia", "mecanica", "status_margem", "departamento"])
        eh_moeda = any(p in titulo_norm for p in ["custo", "valor", "capital", "preco", "recuperavel", "faturamento", "cmv", "imposto", "lucro", "compras_nf", "total_compra", "total_do_item", "total_estimado"]) and "pct" not in titulo_norm and "variacao" not in titulo_norm and "cresc" not in titulo_norm
        eh_pct = "%" in titulo or "pct" in titulo_norm or "variacao" in titulo_norm
        maior_tam = max(len(titulo), 12)
        for row_idx in range(2, max_row + 1):
            cel = ws.cell(row=row_idx, column=col_idx)
            cel.alignment = alin_esq if eh_esquerda else alin_centro
            val = cel.value
            if isinstance(val, (int, float)):
                if eh_moeda:
                    cel.number_format = "R$ #,##0.00"
                elif eh_pct:
                    cel.number_format = '0.00"%"'
                elif isinstance(val, float) and not val.is_integer():
                    cel.number_format = "#,##0.00"
                else:
                    cel.number_format = "#,##0"
            if val is not None:
                maior_tam = max(maior_tam, min(len(str(val)) + 4, 46))
        ws.column_dimensions[letra].width = max(maior_tam + 3, 14)


def gerar_excel_banco_dados(estado: dict) -> bytes:
    from openpyxl import load_workbook
    buffer_xlsx = io.BytesIO()
    linhas_meta_bkp = [
        {"chave": "dias_base", "valor": str(estado.get("dias_base", 87))},
        {"chave": "ultima_atualizacao", "valor": str(estado.get("ultima_atualizacao", "-"))},
        {"chave": "data_exportacao_backup", "valor": agora_br().strftime("%d/%m/%Y %H:%M:%S")},
    ]
    for pref_k, nome_g in sorted((estado.get("grupos_pref_custom") or {}).items()):
        linhas_meta_bkp.append({"chave": f"grp_pref_{pref_k}", "valor": str(nome_g)})
    for sku_k, nome_g in sorted((estado.get("grupos_sku_custom") or {}).items()):
        linhas_meta_bkp.append({"chave": f"grp_sku_{sku_k}", "valor": str(nome_g)})
    df_meta_bkp = pd.DataFrame(linhas_meta_bkp)
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        estado.get("estoque_atual", pd.DataFrame()).to_excel(writer, sheet_name="estoque_atual", index=False)
        estado.get("entradas_diarias", pd.DataFrame()).to_excel(writer, sheet_name="entradas_diarias", index=False)
        estado.get("saidas_diarias", pd.DataFrame()).to_excel(writer, sheet_name="saidas_diarias", index=False)
        estado.get("custos", pd.DataFrame()).to_excel(writer, sheet_name="custos", index=False)
        estado.get("base_inicial", pd.DataFrame()).to_excel(writer, sheet_name="base_inicial", index=False)
        estado.get("ocultos", pd.DataFrame()).to_excel(writer, sheet_name="ocultos", index=False)
        estado.get("pedidos_transito", pd.DataFrame()).to_excel(writer, sheet_name="pedidos_transito", index=False)
        df_meta_bkp.to_excel(writer, sheet_name="meta", index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    for nome_aba in wb.sheetnames:
        _formatar_e_centralizar_aba_openpyxl(wb[nome_aba])
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


def gerar_pacote_backup_leve(estado: dict) -> bytes:
    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        xlsx_bytes = gerar_excel_banco_dados(estado)
        zf.writestr("Banco_Dados_Esteio_Rural.xlsx", xlsx_bytes)
        df_hist = estado.get("historico", pd.DataFrame())
        csv_bytes = df_hist.to_csv(index=False, sep=";").encode("utf-8-sig")
        zf.writestr("historico_180d.csv", csv_bytes)
    return buffer_zip.getvalue()


@st.cache_data(ttl=3600, max_entries=20, show_spinner=False)
def gerar_excel_relatorio(df: pd.DataFrame, nome_aba: str = "Relatorio") -> bytes:
    from openpyxl import load_workbook
    buffer_xlsx = io.BytesIO()
    aba_limpa = nome_aba[:31]
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=aba_limpa, index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    _formatar_e_centralizar_aba_openpyxl(wb[aba_limpa])
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


@st.cache_data(ttl=3600, max_entries=20, show_spinner=False)
def gerar_excel_com_formulas_cotacao(df_cotacao: pd.DataFrame) -> bytes:
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    buffer_xlsx = io.BytesIO()
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df_cotacao.to_excel(writer, sheet_name="Cotacao_Compras", index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    ws = wb["Cotacao_Compras"]
    max_row = ws.max_row
    max_col = ws.max_column
    fonte_negrito = Font(bold=True)
    alin_centro = Alignment(horizontal="center", vertical="center")
    alin_esq = Alignment(horizontal="left", vertical="center")
    preenchimento_editavel = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")
    for c_idx in range(1, max_col + 1):
        ws.cell(row=1, column=c_idx).alignment = alin_centro
        ws.cell(row=1, column=c_idx).font = fonte_negrito
    for r in range(2, max_row + 1):
        for c_idx in range(1, max_col + 1):
            ws.cell(row=r, column=c_idx).alignment = alin_esq if c_idx == 2 else alin_centro
        ws[f"D{r}"].number_format = "#,##0"
        ws[f"E{r}"].number_format = "#,##0"
        ws[f"F{r}"].number_format = "#,##0.00"
        ws[f"G{r}"].number_format = "#,##0.0"
        ws[f"H{r}"].number_format = "#,##0"
        ws[f"I{r}"].number_format = "#,##0"
        ws[f"I{r}"].fill = preenchimento_editavel
        ws[f"K{r}"].fill = preenchimento_editavel
        val_k = ws[f"K{r}"].value
        if val_k is not None and float(val_k) == 0.0:
            ws[f"K{r}"].value = None
        ws[f"J{r}"].number_format = "R$ #,##0.00"
        ws[f"K{r}"].number_format = "R$ #,##0.00"
        ws[f"L{r}"] = f"=IF(AND(K{r}>0,J{r}>0),(K{r}-J{r})/J{r},0)"
        ws[f"L{r}"].number_format = "+0.0%;-0.0%;0.0%"
        ws[f"M{r}"] = f"=I{r}*IF(K{r}>0,K{r},J{r})"
        ws[f"M{r}"].number_format = "R$ #,##0.00"
    linha_total = max_row + 2
    ws[f"H{linha_total}"] = "TOTAL DO PEDIDO:"
    ws[f"H{linha_total}"].font = fonte_negrito
    ws[f"H{linha_total}"].alignment = Alignment(horizontal="right", vertical="center")
    ws[f"I{linha_total}"] = f"=SUM(I2:I{max_row})"
    ws[f"I{linha_total}"].font = fonte_negrito
    ws[f"I{linha_total}"].alignment = alin_centro
    ws[f"I{linha_total}"].number_format = "#,##0"
    ws[f"M{linha_total}"] = f"=SUM(M2:M{max_row})"
    ws[f"M{linha_total}"].font = fonte_negrito
    ws[f"M{linha_total}"].alignment = alin_centro
    ws[f"M{linha_total}"].number_format = "R$ #,##0.00"
    larguras = {
        "A": 14, "B": 38, "C": 26, "D": 15, "E": 26, "F": 16,
        "G": 16, "H": 17, "I": 18, "J": 20, "K": 22, "L": 18, "M": 20,
    }
    for col_letra, larg in larguras.items():
        ws.column_dimensions[col_letra].width = larg
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


# ==============================================================================
# 5. LEITURA DE UPLOADS (PRESERVANDO TIPOS NATIVOS DO EXCEL), CURVA ABC E GIRO
# ==============================================================================
def _preservar_celula_excel(val):
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.strftime("%d/%m/%Y")
    return str(val).strip()


def extrair_data_nome_arquivo(nome_arquivo: str):
    """Extrai a data contida no nome do arquivo (ex: 'Entrada 30-10-2026.xlsx' -> date(2026, 10, 30))."""
    if not nome_arquivo:
        return None
    base = re.sub(r"\.[a-zA-Z0-9]+$", "", str(nome_arquivo))
    m_dmy = re.search(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)", base)
    if m_dmy:
        try:
            return date(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
        except ValueError:
            pass
    m_ymd = re.search(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)", base)
    if m_ymd:
        try:
            return date(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
        except ValueError:
            pass
    return None


def validar_coerencia_data_upload(
    arquivo,
    data_selecionada: date,
    rotulo: str,
    ignorar_trava: bool = False,
) -> str:
    """Impede que uma planilha com data no nome (ex: 30-10-2026) seja importada com data diferente no seletor."""
    if arquivo is None:
        return ""
    nome_arq = getattr(arquivo, "name", "")
    dt_nome = extrair_data_nome_arquivo(nome_arq)
    if dt_nome is not None:
        if dt_nome != data_selecionada and not ignorar_trava:
            raise ValueError(
                f"Trava de Coerência de Data ({rotulo}): O arquivo enviado chama-se **'{nome_arq}'** "
                f"(indicando a data **{dt_nome.strftime('%d/%m/%Y')}**), mas o seletor de data na tela está marcado em "
                f"**{data_selecionada.strftime('%d/%m/%Y')}**. Ajuste a data no seletor para **{dt_nome.strftime('%d/%m/%Y')}** "
                f"antes de sincronizar para evitar gravar o movimento no dia errado!"
            )
        return ""
    return (
        f"ℹ️ **{rotulo}:** O arquivo `'{nome_arq}'` não traz data no nome; "
        f"foi gravado na data selecionada (**{data_selecionada.strftime('%d/%m/%Y')}**)."
    )


def ler_arquivo_upload(arquivo, exigir_multiplas_colunas: bool = False) -> pd.DataFrame:
    nome = arquivo.name.lower()
    conteudo = arquivo.getvalue()
    if nome.endswith(".csv"):
        candidato_1_col = None
        for enc in ["utf-8-sig", "latin1", "cp1252"]:
            for sep in [";", ",", "\t"]:
                try:
                    df = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=enc, dtype=str)
                    if df.shape[1] >= 2:
                        return df
                    if df.shape[1] == 1 and candidato_1_col is None:
                        candidato_1_col = df
                except Exception:
                    continue
        if candidato_1_col is not None and not exigir_multiplas_colunas:
            return candidato_1_col
        raise ValueError("Não foi possível ler o arquivo CSV. Verifique o separador.")
    else:
        df_preview = pd.read_excel(io.BytesIO(conteudo), nrows=0)
        conversores = {col: _preservar_celula_excel for col in df_preview.columns}
        return pd.read_excel(io.BytesIO(conteudo), converters=conversores)


def ler_lista_produtos_cotacao(arquivo) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=False)
    if df_raw is None or df_raw.empty:
        raise ValueError("A planilha enviada para cotação está vazia.")
    cols_norm = {col: normalizar_chave_coluna(col) for col in df_raw.columns}
    col_cod = None
    col_desc = None
    for orig, norm in cols_norm.items():
        if col_cod is None and norm in MAPA_SINONIMOS["codigo"]:
            col_cod = orig
        elif col_desc is None and norm in MAPA_SINONIMOS["descricao"]:
            col_desc = orig
    if col_cod is None:
        col_cod = df_raw.columns[0]
    if col_desc is None and df_raw.shape[1] >= 2:
        for c in df_raw.columns:
            if c != col_cod:
                col_desc = c
                break
    df = pd.DataFrame()
    df["codigo_lista"] = limpar_serie_codigo(df_raw[col_cod])
    if col_desc is not None:
        df["descricao_lista"] = limpar_serie_texto(df_raw[col_desc])
    else:
        df["descricao_lista"] = ""
    df = df[df["codigo_lista"] != ""].copy()
    df = df[~df["codigo_lista"].str.lower().isin(["codigo", "código", "cod", "sku", "id", "item", "total"])].copy()
    df = df.drop_duplicates(subset=["codigo_lista"], keep="first").reset_index(drop=True)
    return df



MAPA_DEPARTAMENTOS_SIAGRI = {
    "50": "50 - Veterinária & Reprodução",
    "70": "70 - Ferragens, Lonas & Selaria",
    "26": "26 - Nutrição & Matéria-Prima (MP)",
    "90": "90 - Rações, Milho & Grãos",
    "60": "60 - Máquinas, Pulv. & EPIs",
    "20": "20 - Domissanitários & Defensivos",
    "11": "11 - Hidráulica, Tubos & Parafusos",
    "12": "12 - Bombas, Boias & Conexões",
    "13": "13 - Botinas, Calçados & Vestuário",
    "15": "15 - Óleos, Graxas & Lubrificantes",
    "80": "80 - Arames, Cordoalhas & Cercas",
    "30": "30 - Adubos, Sementes & Agrícola",
    "10": "10 - Inseticidas & Desinfetantes",
    "16": "16 - Linha Pet & Aves",
}


def construir_mapa_departamentos(mapa_pref_custom: dict = None) -> dict:
    mapa = dict(MAPA_DEPARTAMENTOS_SIAGRI)
    if mapa_pref_custom:
        for k, v in mapa_pref_custom.items():
            ks = str(k).strip()
            vs = str(v).strip()
            if ks and vs:
                mapa[ks] = vs
    return mapa


def identificar_departamento_sku(
    codigo: str,
    mapa_pref_custom: dict = None,
    mapa_sku_custom: dict = None,
) -> str:
    cod_s = normalizar_codigo_sku(codigo)
    if not cod_s:
        cod_s = str(codigo).strip()
    if mapa_sku_custom and cod_s in mapa_sku_custom and str(mapa_sku_custom[cod_s]).strip():
        return str(mapa_sku_custom[cod_s]).strip()
    pref = cod_s[:2] if len(cod_s) >= 2 else cod_s
    mapa_base = construir_mapa_departamentos(mapa_pref_custom)
    return mapa_base.get(pref, f"Outros ({pref or 'S/C'})")


def montar_dataframe_meta_completo(
    dias_base_val: int,
    ult_att_val: str,
    grupos_pref_custom: dict = None,
    grupos_sku_custom: dict = None,
) -> pd.DataFrame:
    linhas = [
        {"chave": "dias_base", "valor": str(int(dias_base_val))},
        {"chave": "ultima_atualizacao", "valor": str(ult_att_val)},
    ]
    if grupos_pref_custom:
        for pk, pv in sorted(grupos_pref_custom.items()):
            if str(pk).strip() and str(pv).strip():
                linhas.append({"chave": f"grp_pref_{str(pk).strip()}", "valor": str(pv).strip()})
    if grupos_sku_custom:
        for sk, sv in sorted(grupos_sku_custom.items()):
            sk_norm = normalizar_codigo_sku(sk)
            if sk_norm and str(sv).strip():
                linhas.append({"chave": f"grp_sku_{sk_norm}", "valor": str(sv).strip()})
    return pd.DataFrame(linhas)


def _renderizar_dataframe_selecionavel(
    styler_ou_df,
    key: str,
    height: int = None,
    column_config: dict = None,
) -> list:
    """Renderiza st.dataframe com seleção de linha (on_select='rerun') e retorna os índices clicados."""
    kwargs_df = {
        "use_container_width": True,
        "hide_index": True,
        "key": key,
    }
    if height is not None:
        kwargs_df["height"] = height
    if column_config is not None:
        kwargs_df["column_config"] = column_config
    try:
        evento = st.dataframe(
            styler_ou_df,
            on_select="rerun",
            selection_mode="single-row",
            **kwargs_df,
        )
        if evento is not None and hasattr(evento, "selection") and hasattr(evento.selection, "rows"):
            return list(evento.selection.rows)
        if isinstance(evento, dict):
            return list(evento.get("selection", {}).get("rows", []))
    except TypeError:
        st.dataframe(styler_ou_df, **kwargs_df)
    return []


def _extrair_selecao_altair(evento, campo_alvo: str):
    """Extrai o valor clicado em um gráfico interativo st.altair_chart(on_select='rerun')."""
    if evento is None:
        return None
    sel_dict = None
    if hasattr(evento, "selection"):
        sel_dict = evento.selection
    elif isinstance(evento, dict):
        sel_dict = evento.get("selection")
    if not sel_dict:
        return None
    try:
        itens = dict(sel_dict) if not isinstance(sel_dict, dict) else sel_dict
    except Exception:
        return None
    for _, val_sel in itens.items():
        if isinstance(val_sel, list) and len(val_sel) > 0 and isinstance(val_sel[0], dict):
            if campo_alvo in val_sel[0]:
                return val_sel[0][campo_alvo]
        elif isinstance(val_sel, dict):
            if campo_alvo in val_sel:
                v_c = val_sel[campo_alvo]
                if isinstance(v_c, list) and v_c:
                    return v_c[0]
                if isinstance(v_c, str):
                    return v_c
    return None



def calcular_plano_promocional_fefo(
    df_estoque_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    df_giro_ref: pd.DataFrame,
    aliquota_impostos_pct: float = 0.0,
    margem_referencia_pct: float = 30.0,
    df_saidas_ref: pd.DataFrame = None,
) -> pd.DataFrame:
    if df_estoque_ref is None or df_estoque_ref.empty:
        return pd.DataFrame()
    df_f = df_estoque_ref[df_estoque_ref["saldo_lote"] > 0].copy()
    if df_f.empty:
        return pd.DataFrame()

    if df_custos_ref is not None and not df_custos_ref.empty:
        df_f = df_f.merge(df_custos_ref[["codigo", "custo_unitario"]], on="codigo", how="left")
        df_f["custo_unitario"] = df_f["custo_unitario"].fillna(0.0)
    else:
        df_f["custo_unitario"] = 0.0

    if df_giro_ref is not None and not df_giro_ref.empty and "giro_ponderado" in df_giro_ref.columns:
        mapa_giro = dict(zip(df_giro_ref["codigo"], df_giro_ref["giro_ponderado"].clip(lower=0.0)))
    else:
        mapa_giro = {}
    df_f["giro_diario"] = df_f["codigo"].map(mapa_giro).fillna(0.0)

    # Se já houver preço médio praticado nas saídas (quando coluna valor_venda estiver presente), aproveita-o
    mapa_preco_real = {}
    if (
        df_saidas_ref is not None
        and not df_saidas_ref.empty
        and "valor_venda" in df_saidas_ref.columns
        and "qtd_saida" in df_saidas_ref.columns
    ):
        df_s_val = df_saidas_ref[(df_saidas_ref["qtd_saida"] > 0) & (df_saidas_ref["valor_venda"] > 0)].copy()
        if not df_s_val.empty:
            soma_s = df_s_val.groupby("codigo", as_index=False).agg(
                tot_q=("qtd_saida", "sum"),
                tot_v=("valor_venda", "sum"),
            )
            soma_s["p_unit"] = soma_s["tot_v"] / soma_s["tot_q"]
            mapa_preco_real = dict(zip(soma_s["codigo"], soma_s["p_unit"]))

    df_f["dt_validade"] = converter_datas_deterministico(df_f["validade"])
    hoje_ts = pd.Timestamp(hoje_br())
    df_f["dias_para_vencer"] = (df_f["dt_validade"] - hoje_ts).dt.days
    df_f["valor_em_risco"] = df_f["saldo_lote"] * df_f["custo_unitario"]

    def _classificar_faixa_fefo(dias):
        if pd.isna(dias):
            return "⚪ Sem Data de Validade"
        if dias < 0:
            return "🔴 1. Vencido"
        if dias <= 30:
            return "🟠 2. Crítico (0 a 30 dias)"
        if dias <= 60:
            return "🟡 3. Atenção (31 a 60 dias)"
        if dias <= 90:
            return "🔵 4. Preventivo (61 a 90 dias)"
        return "🟢 5. Seguro (> 90 dias)"

    df_f["status_fefo"] = df_f["dias_para_vencer"].apply(_classificar_faixa_fefo)

    # Ordena por código e data de validade crescente para simular a fila real FEFO (apenas lotes não vencidos entram na fila de venda)
    df_f["_ord_dias"] = df_f["dias_para_vencer"].fillna(999999.0)
    df_f = df_f.sort_values(["codigo", "_ord_dias", "lote"], ascending=[True, True, True]).reset_index(drop=True)
    df_f["_saldo_vendavel"] = [
        float(sl) if (pd.notna(dv) and float(dv) >= 0) else 0.0
        for sl, dv in zip(df_f["saldo_lote"], df_f["dias_para_vencer"])
    ]
    df_f["acum_lote_fefo"] = df_f.groupby("codigo")["_saldo_vendavel"].cumsum()
    df_f["saldo_lotes_anteriores"] = (df_f["acum_lote_fefo"] - df_f["_saldo_vendavel"]).clip(lower=0.0)

    fator_imposto = max(1.0 - (float(aliquota_impostos_pct) / 100.0), 0.10)
    fator_margem_ref = max(1.0 - (float(margem_referencia_pct) / 100.0), 0.15)

    sobra_proj_list = []
    cap_sobra_list = []
    preco_atual_list = []
    tem_preco_real_list = []
    origem_preco_list = []
    preco_piso_list = []
    preco_promo_list = []
    desc_sug_list = []
    margem_liq_promo_list = []
    meta_giro_promo_list = []
    diagnostico_escala_list = []
    mecanica_ia_list = []
    precisa_promo_list = []

    for _, r in df_f.iterrows():
        cod = str(r["codigo"]).strip()
        saldo_l = float(r["saldo_lote"])
        saldo_ant = float(r["saldo_lotes_anteriores"])
        custo_u = float(r["custo_unitario"])
        giro_d = float(r["giro_diario"])
        dias_v = r["dias_para_vencer"]

        preco_piso = (custo_u / fator_imposto) if custo_u > 0 else 0.0
        preco_real_lido = float(mapa_preco_real.get(cod, 0.0))
        tem_preco_real = preco_real_lido > 0.0
        if tem_preco_real:
            preco_est = preco_real_lido
            origem_p_txt = "✔️ Venda Real (Saídas)"
        elif custo_u > 0:
            preco_est = max(custo_u / fator_margem_ref, preco_piso * 1.15)
            origem_p_txt = "⚠️ Estimado (Margem)"
        else:
            preco_est = 0.0
            origem_p_txt = "⚪ Sem Custo/Preço"

        if pd.isna(dias_v):
            sobra_p = 0.0
            cap_sobra = 0.0
            precisa_p = False
            diag_txt = "⚪ Sem Validade Cadastrada"
            mec_txt = "Conferir data física no lote"
            desc_pct = 0.0
            preco_promo = preco_est
            meta_giro_p = giro_d
        elif float(dias_v) < 0:
            sobra_p = saldo_l
            cap_sobra = sobra_p * custo_u
            precisa_p = True
            diag_txt = "🔴 Vencido (Bloquear Venda)"
            mec_txt = "🚫 Segregar no depósito / Solicitar troca ou baixa"
            desc_pct = 0.0
            preco_promo = 0.0
            meta_giro_p = 0.0
        else:
            d_pos = max(float(dias_v), 0.0)
            venda_ate_venc = d_pos * giro_d
            absorcao_lote = min(saldo_l, max(0.0, venda_ate_venc - saldo_ant))
            sobra_p = max(0.0, round(saldo_l - absorcao_lote, 2))
            cap_sobra = sobra_p * custo_u
            meta_giro_p = (saldo_l + saldo_ant) / max(d_pos, 1.0)

            if sobra_p < 0.5 or d_pos > 120:
                precisa_p = False
                if d_pos <= 120:
                    diag_txt = "🟢 Escoa no Giro Normal"
                    mec_txt = "✅ Manter Preço Cheio (Giro atual absorve o lote)"
                else:
                    diag_txt = "🟢 Prazo Seguro (> 120d)"
                    mec_txt = "✅ Venda normal no balcão"
                desc_pct = 0.0
                preco_promo = preco_est
            else:
                precisa_p = True
                if d_pos <= 30:
                    diag_txt = f"🔥 Sobra {formatar_qtd_br(sobra_p)} un. (Urgente ≤30d)"
                    alvo_p = max(preco_piso * 1.02, preco_est * 0.76) if preco_est > 0 else 0.0
                    mec_txt = (
                        "🔥 Queima Balcão / Kit Lote Fechado (Piso + 2%)"
                        if saldo_l >= 6
                        else "🔥 Liquidação Imediata de Balcão (Piso + 2%)"
                    )
                elif d_pos <= 60:
                    diag_txt = f"🟠 Sobra {formatar_qtd_br(sobra_p)} un. (Atenção 31-60d)"
                    alvo_p = max(preco_piso * 1.06, preco_est * 0.82) if preco_est > 0 else 0.0
                    mec_txt = (
                        "⚡ Promoção Leve 4 Pague 3 / Atacado (-18%)"
                        if saldo_l >= 6
                        else "⚡ Desconto Progressivo no Balcão (-15% a -18%)"
                    )
                elif d_pos <= 90:
                    diag_txt = f"🟡 Sobra {formatar_qtd_br(sobra_p)} un. (Preventivo 61-90d)"
                    alvo_p = max(preco_piso * 1.10, preco_est * 0.88) if preco_est > 0 else 0.0
                    mec_txt = "🎯 Combo Fazendeiro / Campanha WhatsApp (-12%)"
                else:
                    diag_txt = f"🔵 Sobra {formatar_qtd_br(sobra_p)} un. (91-120d)"
                    alvo_p = max(preco_piso * 1.14, preco_est * 0.92) if preco_est > 0 else 0.0
                    mec_txt = "📢 Foco Equipe de Vendas (-8%)"

                preco_promo = min(alvo_p, preco_est) if preco_est > 0 else 0.0
                desc_pct = (
                    max(0.0, ((preco_est - preco_promo) / preco_est) * 100.0)
                    if preco_est > 0
                    else 0.0
                )

        if preco_promo > 0 and custo_u > 0:
            imposto_r = preco_promo * (float(aliquota_impostos_pct) / 100.0)
            lucro_liq_u = preco_promo - imposto_r - custo_u
            mg_liq_pct = (lucro_liq_u / preco_promo) * 100.0
        else:
            mg_liq_pct = 0.0

        sobra_proj_list.append(sobra_p)
        cap_sobra_list.append(cap_sobra)
        preco_atual_list.append(round(preco_est, 2))
        tem_preco_real_list.append(tem_preco_real)
        origem_preco_list.append(origem_p_txt)
        preco_piso_list.append(round(preco_piso, 2))
        preco_promo_list.append(round(preco_promo, 2))
        desc_sug_list.append(round(desc_pct, 1))
        margem_liq_promo_list.append(round(mg_liq_pct, 1))
        meta_giro_promo_list.append(round(meta_giro_p, 2))
        diagnostico_escala_list.append(diag_txt)
        mecanica_ia_list.append(mec_txt)
        precisa_promo_list.append(precisa_p)

    df_f["sobra_projetada"] = sobra_proj_list
    df_f["capital_sobra"] = cap_sobra_list
    df_f["preco_atual_est"] = preco_atual_list
    df_f["tem_preco_real"] = tem_preco_real_list
    df_f["origem_preco"] = origem_preco_list
    df_f["preco_piso_imposto"] = preco_piso_list
    df_f["preco_promo_sug"] = preco_promo_list
    df_f["desconto_sug_pct"] = desc_sug_list
    df_f["margem_liq_promo_pct"] = margem_liq_promo_list
    df_f["meta_giro_dia"] = meta_giro_promo_list
    df_f["diagnostico_giro_fefo"] = diagnostico_escala_list
    df_f["mecanica_ia"] = mecanica_ia_list
    df_f["precisa_promocao"] = precisa_promo_list
    df_f["eh_mp"] = (
        df_f["descricao"].astype(str).str.strip().str.upper().str.startswith("MP ")
        | df_f["codigo"].astype(str).str.startswith("26")
    )
    return df_f.drop(columns=["_ord_dias", "_saldo_vendavel"]).reset_index(drop=True)


def gerar_textos_campanha_promocional_fefo(
    codigo: str,
    descricao: str,
    lote: str,
    validade: str,
    dias_vencer: int,
    saldo_lote: float,
    sobra_proj: float,
    custo_unit: float,
    preco_de: float,
    preco_por: float,
    preco_piso: float,
    desconto_pct: float,
    aliquota_imp_pct: float,
    mecanica_sugerida: str,
    meta_giro_dia: float,
    exibir_preco_de_whatsapp: bool = True,
) -> tuple[str, str]:
    economia_un = max(0.0, preco_de - preco_por)
    economia_lote_3 = economia_un * 3.0
    receita_total_lote = saldo_lote * preco_por
    imposto_total_lote = receita_total_lote * (aliquota_imp_pct / 100.0)
    custo_total_lote = saldo_lote * custo_unit
    resultado_liq_lote = receita_total_lote - imposto_total_lote - custo_total_lote
    margem_liq_pct = ((resultado_liq_lote / receita_total_lote) * 100.0) if receita_total_lote > 0 else 0.0

    if exibir_preco_de_whatsapp and economia_un > 0.01:
        bloco_preco_wpp = (
            f"💰 De: ~{formatar_moeda_br(preco_de)}~\n"
            f"🔥 *Por apenas: {formatar_moeda_br(preco_por)} à vista!* (*-{formatar_num_br(desconto_pct, 1)}%* de desconto)\n"
            f"📉 Economia imediata de *{formatar_moeda_br(economia_un)} por unidade* "
            f"(levando 3 un., você economiza *{formatar_moeda_br(economia_lote_3)}*)!\n\n"
        )
    else:
        bloco_preco_wpp = (
            f"🔥 *Preço Especial de Lote: {formatar_moeda_br(preco_por)} à vista!*\n\n"
        )

    txt_whatsapp_cliente = (
        f"🌾 *OPORTUNIDADE ESPECIAL ESTEIO RURAL — LOTE PROMOCIONAL!* 🌾\n\n"
        f"📦 *{descricao}*\n"
        f"✅ Lote selecionado p/ giro rápido (Validade: *{validade or 'Consultar'}* — *{formatar_qtd_br(saldo_lote)} un.* disponíveis)\n\n"
        f"{bloco_preco_wpp}"
        f"⚡ *Condição válida exclusivamente enquanto durar este lote ({formatar_qtd_br(saldo_lote)} unidades).*\n"
        f"📲 Responda aqui no WhatsApp ou fale com nossos vendedores no balcão para reservar o seu!"
    )

    txt_briefing_equipe = (
        f"🎯 *META DE ESCOAMENTO FEFO — EQUIPE DE VENDAS ESTEIO RURAL*\n"
        f"• *Produto:* [{codigo}] {descricao}\n"
        f"• *Lote Prioritário:* {lote or 'S/L'}  |  *Validade:* {validade or '-'} ({dias_vencer} dias restantes)\n"
        f"• *Saldo no Lote:* {formatar_qtd_br(saldo_lote)} un.  |  *Sobra Projetada s/ Ação:* {formatar_qtd_br(sobra_proj)} un.\n"
        f"• *Mecânica Recomendada:* {mecanica_sugerida}\n"
        f"• *Preço Tabela:* {formatar_moeda_br(preco_de)}  ➔  *Preço Promocional:* {formatar_moeda_br(preco_por)} (-{formatar_num_br(desconto_pct, 1)}%)\n"
        f"• *Piso Mínimo (Custo C1 + {formatar_num_br(aliquota_imp_pct, 1)}% Impostos):* {formatar_moeda_br(preco_piso)} "
        f"(Margem líquida na promoção: {formatar_pct_br(margem_liq_pct, 1)})\n"
        f"• *Meta da Equipe:* Vender pelo menos *{formatar_num_br(meta_giro_dia, 1)} un./dia* para zerar o lote antes do vencimento "
        f"e recuperar *{formatar_moeda_br(receita_total_lote)}* em caixa!"
    )
    return txt_whatsapp_cliente, txt_briefing_equipe


def calcular_tabela_curva_abc(
    df_estoque_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    incluir_zerados: bool = False,
    df_catalogo_extra: pd.DataFrame = None,
) -> pd.DataFrame:
    if (df_estoque_ref is None or df_estoque_ref.empty) and (df_catalogo_extra is None or df_catalogo_extra.empty):
        return pd.DataFrame()
    if df_estoque_ref is not None and not df_estoque_ref.empty:
        df_est_sku = df_estoque_ref.groupby("codigo", as_index=False).agg(
            descricao=("descricao", "first"),
            saldo_geral=("saldo_geral", "first"),
        )
    else:
        df_est_sku = pd.DataFrame(columns=["codigo", "descricao", "saldo_geral"])

    if incluir_zerados and df_catalogo_extra is not None and not df_catalogo_extra.empty:
        df_cat_limpo = (
            df_catalogo_extra[["codigo", "descricao"]]
            .dropna(subset=["codigo"])
            .drop_duplicates(subset=["codigo"], keep="first")
        )
        cods_ja_no_est = set(df_est_sku["codigo"].unique())
        df_faltantes = df_cat_limpo[~df_cat_limpo["codigo"].isin(cods_ja_no_est)].copy()
        if not df_faltantes.empty:
            df_faltantes["saldo_geral"] = 0.0
            df_est_sku = pd.concat([df_est_sku, df_faltantes[["codigo", "descricao", "saldo_geral"]]], ignore_index=True)

    if df_custos_ref is not None and not df_custos_ref.empty:
        df_abc = df_est_sku.merge(df_custos_ref[["codigo", "custo_unitario"]], on="codigo", how="left")
        df_abc["custo_unitario"] = df_abc["custo_unitario"].fillna(0.0)
    else:
        df_abc = df_est_sku.copy()
        df_abc["custo_unitario"] = 0.0

    df_abc["valor_estoque"] = df_abc["saldo_geral"].clip(lower=0.0) * df_abc["custo_unitario"]
    df_pos = (
        df_abc[df_abc["valor_estoque"] > 0]
        .sort_values(["valor_estoque", "codigo"], ascending=[False, True])
        .copy()
    )
    total_fin = float(df_pos["valor_estoque"].sum()) if not df_pos.empty else 0.0
    if total_fin > 0:
        part_exata = (df_pos["valor_estoque"] / total_fin) * 100.0
        acum_exato = (df_pos["valor_estoque"].cumsum() / total_fin) * 100.0
        acum_anterior = acum_exato - part_exata
        df_pos["part_pct"] = part_exata.round(2)
        df_pos["acum_pct"] = acum_exato.round(2)
        df_pos["classe_abc_curta"] = acum_anterior.apply(
            lambda p: "Classe A" if p < 80.0 else ("Classe B" if p < 95.0 else "Classe C")
        )
        df_pos["classe_abc"] = acum_anterior.apply(
            lambda p: "Classe A (Até 80%)" if p < 80.0 else ("Classe B (80% a 95%)" if p < 95.0 else "Classe C (95% a 100%)")
        )
    elif not incluir_zerados:
        return pd.DataFrame()

    if not incluir_zerados:
        return df_pos.reset_index(drop=True)

    df_zero = (
        df_abc[df_abc["valor_estoque"] <= 0]
        .sort_values(["saldo_geral", "custo_unitario", "descricao"], ascending=[False, False, True])
        .copy()
    )
    if not df_zero.empty:
        df_zero["part_pct"] = 0.0
        df_zero["acum_pct"] = 100.0 if total_fin > 0 else 0.0
        df_zero["classe_abc_curta"] = "Sem Saldo/Custo"
        df_zero["classe_abc"] = [
            "⚪ Saldo Zerado (R$ 0,00)" if float(sg) <= 0 else "⚪ Sem Custo no ERP (R$ 0,00)"
            for sg in df_zero["saldo_geral"]
        ]
        df_final_abc = pd.concat([df_pos, df_zero], ignore_index=True)
    else:
        df_final_abc = df_pos
    return df_final_abc.reset_index(drop=True)


def validar_estrutura_e_coincidencia_codigos(
    df_novo: pd.DataFrame,
    codigos_referencia: set,
    nome_planilha: str,
    ignorar_trava_catalogo: bool = False,
    exigir_cobertura_total: bool = True,
) -> float:
    if df_novo.empty or "codigo" not in df_novo.columns:
        return 100.0
    if "descricao" in df_novo.columns:
        df_desc_validas = df_novo[df_novo["descricao"] != ""]
        if not df_desc_validas.empty:
            desc_por_cod = df_desc_validas.groupby("codigo")["descricao"].nunique()
            codigos_ambiguos = desc_por_cod[desc_por_cod > 1]
            if len(codigos_ambiguos) > max(int(len(desc_por_cod) * 0.05), 10) and not ignorar_trava_catalogo:
                ex_amb = ", ".join(f"'{c}'" for c in codigos_ambiguos.index[:6])
                raise ValueError(
                    f"Trava contra Colunas Trocadas ({nome_planilha}): A coluna lida como 'Código' possui "
                    f"{len(codigos_ambiguos)} valores que se repetem em produtos com descrições diferentes "
                    f"(ex: {ex_amb}). Isso indica que uma coluna de Saldo ou Quantidade foi colocada no lugar do Código!"
                )
    if not codigos_referencia:
        return 100.0
    cods_novos = {normalizar_codigo_sku(c) for c in df_novo["codigo"].unique() if normalizar_codigo_sku(c)}
    cods_ref_norm = {normalizar_codigo_sku(c) for c in codigos_referencia if normalizar_codigo_sku(c)}
    if not cods_ref_norm:
        return 100.0
    intersecao = cods_novos & cods_ref_norm
    taxa_sobre_novo = (len(intersecao) / max(len(cods_novos), 1)) * 100.0
    taxa_sobre_anterior = (len(intersecao) / max(len(cods_ref_norm), 1)) * 100.0
    taxa_avaliada = min(taxa_sobre_novo, taxa_sobre_anterior) if exigir_cobertura_total else taxa_sobre_novo
    if taxa_avaliada < LIMITE_COINCIDENCIA_CATALOGO and not ignorar_trava_catalogo:
        estranhos = sorted(list(cods_novos - cods_ref_norm))[:8]
        amostra_estranhos = ", ".join(f"'{c}'" for c in estranhos) if estranhos else "N/A"
        raise ValueError(
            f"Trava contra Colunas Trocadas ({nome_planilha}): Apenas **{taxa_avaliada:.1f}%** dos códigos "
            f"coincidem com a base anterior ({len(intersecao)} coincidentes entre {len(cods_novos)} enviados "
            f"e {len(cods_ref_norm)} cadastrados; mínimo exigido: {LIMITE_COINCIDENCIA_CATALOGO:.0f}%). "
            f"Exemplos de códigos lidos na 1ª coluna: {amostra_estranhos}. "
            f"Verifique se a ordem das colunas da planilha não foi trocada!"
        )
    return taxa_avaliada


def processar_planilha_estoque(
    arquivo,
    data_pos: date,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
) -> tuple[pd.DataFrame, dict]:
    aviso_sem_data = validar_coerencia_data_upload(
        arquivo, data_pos, "Posição de Estoque", ignorar_trava=ignorar_trava_catalogo
    )
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 6:
        raise ValueError(
            f"A planilha de estoque precisa ter pelo menos 6 colunas (encontradas: {df_raw.shape[1]})."
        )
    df = estruturar_dataframe_bruto(df_raw, "estoque_atual", exigir_colunas_obrigatorias=True)
    df["data"] = data_pos.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Estoque): Nenhuma linha válida de produto foi encontrada na planilha."
        )
    soma_saldo_geral = float(df["saldo_geral"].abs().sum())
    if soma_saldo_geral <= 0:
        raise ValueError(
            "Trava de Segurança (Estoque): Todos os saldos gerais vieram ZERADOS (0). "
            "Verifique se a coluna 'Saldo Geral' está na posição correta (2ª coluna) ou se o arquivo está correto."
        )
    tem_lotes_informados = (df["lote"] != "").any()
    soma_saldo_lote = float(df["saldo_lote"].abs().sum())
    if tem_lotes_informados and soma_saldo_lote <= 0:
        raise ValueError(
            "Trava de Segurança (Estoque): Há lotes informados na planilha, mas todos os 'Saldos do Lote' "
            "vieram ZERADOS (0). Verifique a 5ª coluna do arquivo antes de importar."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Estoque",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=True,
    )
    linhas_antes = len(df)
    mask_dup = df.duplicated(subset=["codigo", "lote"], keep="last")
    qtd_duplicadas = int(mask_dup.sum())
    exemplos_dup = []
    if qtd_duplicadas > 0:
        df_ex = df.loc[mask_dup, ["codigo", "descricao", "lote"]].head(8)
        exemplos_dup = [
            f"{r['codigo']} ({r['descricao'][:25]} - Lote: {r['lote'] or 'S/L'})"
            for _, r in df_ex.iterrows()
        ]
    df_final = padronizar_dataframe(df, "estoque_atual")
    info_dup = {
        "linhas_lidas": linhas_antes,
        "linhas_finais": len(df_final),
        "qtd_duplicadas": qtd_duplicadas,
        "exemplos": exemplos_dup,
        "taxa_coincidencia": taxa_coincidencia,
        "aviso_sem_data": aviso_sem_data,
    }
    return df_final, info_dup


def processar_planilha_custos(
    arquivo,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
) -> tuple[pd.DataFrame, dict]:
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError("A planilha de custos precisa ter pelo menos 3 colunas (Código, Descrição, Custo).")
    df = estruturar_dataframe_bruto(df_raw, "custos", exigir_colunas_obrigatorias=True)
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Custos): Nenhum produto válido encontrado na planilha de custos."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Custos",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=False,
    )
    qtd_dup_custos = int(df.duplicated(subset=["codigo"], keep="last").sum())
    df_final = padronizar_dataframe(df, "custos")
    qtd_positivos = int((df_final["custo_unitario"] > 0).sum())
    if qtd_positivos == 0:
        raise ValueError(
            "Trava de Segurança (Custos): Todos os custos unitários vieram ZERADOS (R$ 0,00). "
            "A importação foi bloqueada para proteger a Curva ABC e o FEFO. Verifique a 3ª coluna da planilha."
        )
    qtd_zerados = int((df_final["custo_unitario"] <= 0).sum())
    info_custos = {
        "total_itens": len(df_final),
        "qtd_positivos": qtd_positivos,
        "qtd_zerados": qtd_zerados,
        "qtd_duplicadas": qtd_dup_custos,
        "taxa_coincidencia": taxa_coincidencia,
    }
    return df_final, info_custos


def processar_planilha_base_vendas(
    arquivo,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
) -> tuple[pd.DataFrame, dict]:
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError("A Base Inicial de Vendas precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade).")
    df = estruturar_dataframe_bruto(df_raw, "base_inicial", exigir_colunas_obrigatorias=True)
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Base de Vendas): Nenhum registro válido encontrado na planilha."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Base Inicial de Vendas",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=False,
    )
    desc_por_sku = df[df["descricao"] != ""].groupby("codigo")["descricao"].nunique()
    qtd_desc_divergentes = int((desc_por_sku > 1).sum())
    df_agrupado = df.groupby("codigo", as_index=False).agg(
        descricao=("descricao", "last"),
        qtd_vendida=("qtd_vendida", "sum"),
    )
    df_final = padronizar_dataframe(df_agrupado, "base_inicial")
    soma_vendas = float(df_final["qtd_vendida"].sum())
    if soma_vendas <= 0:
        raise ValueError(
            "Trava de Segurança (Base de Vendas): A soma das quantidades vendidas veio ZERADA (0). "
            "A importação foi bloqueada para não zerar o cálculo de giro. Verifique a 3ª coluna da planilha."
        )
    info_base = {
        "total_itens": len(df_final),
        "soma_vendas": soma_vendas,
        "qtd_zerados": int((df_final["qtd_vendida"] <= 0).sum()),
        "qtd_desc_divergentes": qtd_desc_divergentes,
        "taxa_coincidencia": taxa_coincidencia,
    }
    return df_final, info_base


def processar_planilha_movimento_diario(
    arquivo,
    data_mov: date,
    nome_aba: str,
    col_qtd: str,
    rotulo_amigavel: str,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
) -> tuple[pd.DataFrame, dict]:
    aviso_sem_data = validar_coerencia_data_upload(
        arquivo, data_mov, rotulo_amigavel, ignorar_trava=ignorar_trava_catalogo
    )
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError(
            f"A planilha de {rotulo_amigavel} precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade)."
        )
    coluna_valor_lida = ""
    eh_custo_unitario_direto = False
    if nome_aba == "saidas_diarias":
        termos_fin_v = ("valor", "vlr", "proposta", "faturamento", "receita", "preco", "liquido", "bruto", "total_venda")
        termos_nao_fin_v = ("saldo", "estoque", "lote", "validade", "custo", "cmv", "cod", "qtd", "quant", "data")
        for c_orig in df_raw.columns:
            n_c = normalizar_chave_coluna(c_orig)
            if n_c in MAPA_SINONIMOS["valor_venda"] or (
                any(t in n_c for t in termos_fin_v) and not any(b in n_c for b in termos_nao_fin_v)
            ):
                coluna_valor_lida = str(c_orig).strip()
                break
    elif nome_aba == "entradas_diarias":
        termos_fin_e = ("valor", "vlr", "custo", "c1", "nf", "nota", "preco", "liquido", "bruto", "total")
        termos_nao_fin_e = ("saldo", "estoque", "lote", "validade", "cod", "qtd", "quant", "data")
        for c_orig in df_raw.columns:
            n_c = normalizar_chave_coluna(c_orig)
            if n_c in MAPA_SINONIMOS["valor_entrada"] or (
                any(t in n_c for t in termos_fin_e) and not any(b in n_c for b in termos_nao_fin_e)
            ):
                coluna_valor_lida = str(c_orig).strip()
                if any(u in n_c for u in ("unitario", "unit", "c1", "medio")):
                    eh_custo_unitario_direto = True
                break
    df = estruturar_dataframe_bruto(df_raw, nome_aba, exigir_colunas_obrigatorias=True)
    if nome_aba == "entradas_diarias" and eh_custo_unitario_direto and "valor_entrada" in df.columns:
        df["valor_entrada"] = df["qtd_entrada"] * df["valor_entrada"]
    data_iso = data_mov.strftime("%Y-%m-%d")
    df["data"] = data_iso
    if df.empty:
        raise ValueError(
            f"Trava de Segurança ({rotulo_amigavel}): Nenhum registro válido encontrado na planilha."
        )
    taxa_coincidencia = 100.0
    if len(df) >= 5 and codigos_ref:
        taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
            df_novo=df,
            codigos_referencia=codigos_ref,
            nome_planilha=rotulo_amigavel,
            ignorar_trava_catalogo=ignorar_trava_catalogo,
            exigir_cobertura_total=False,
        )
    contagem_por_sku = df.groupby("codigo")[col_qtd].count()
    cods_repetidos = contagem_por_sku[contagem_por_sku > 1].index.tolist()
    qtd_codigos_repetidos = len(cods_repetidos)
    qtd_linhas_extras = int(df.duplicated(subset=["codigo"], keep="first").sum())
    exemplos_repetidos = []
    if qtd_codigos_repetidos > 0:
        for cod_r in cods_repetidos[:6]:
            sub_r = df[df["codigo"] == cod_r]
            parcelas_str = "+".join(formatar_qtd_br(v) for v in sub_r[col_qtd].tolist()[:4])
            if len(sub_r) > 4:
                parcelas_str += "+..."
            soma_r = float(sub_r[col_qtd].sum())
            exemplos_repetidos.append(f"SKU {cod_r} ({parcelas_str} = {formatar_qtd_br(soma_r)})")
    agg_mov = {
        "descricao": ("descricao", "last"),
        col_qtd: (col_qtd, "sum"),
    }
    if "valor_entrada" in df.columns:
        agg_mov["valor_entrada"] = ("valor_entrada", "sum")
    if "valor_venda" in df.columns:
        agg_mov["valor_venda"] = ("valor_venda", "sum")
    agg_mov["data"] = ("data", "last")
    df_agrupado = df.groupby("codigo", as_index=False).agg(**agg_mov)
    df_agrupado = df_agrupado[df_agrupado[col_qtd] > 0].copy()
    if df_agrupado.empty:
        raise ValueError(
            f"Trava de Segurança ({rotulo_amigavel}): Todas as quantidades vieram ZERADAS (0). "
            "Verifique a 3ª coluna da planilha antes de importar."
        )
    df_final = padronizar_dataframe(df_agrupado, nome_aba)
    soma_qtd = float(df_final[col_qtd].sum())
    soma_valor_venda = float(df_final["valor_venda"].sum()) if "valor_venda" in df_final.columns else 0.0
    soma_valor_entrada = float(df_final["valor_entrada"].sum()) if "valor_entrada" in df_final.columns else 0.0
    df_custos_extraidos = pd.DataFrame(columns=["codigo", "descricao", "custo_unitario"])
    if nome_aba == "entradas_diarias" and "valor_entrada" in df_final.columns:
        df_c_val = df_final[(df_final["qtd_entrada"] > 0) & (df_final["valor_entrada"] > 0)].copy()
        if not df_c_val.empty:
            df_c_val["custo_unitario"] = (df_c_val["valor_entrada"] / df_c_val["qtd_entrada"]).round(4)
            df_custos_extraidos = df_c_val[["codigo", "descricao", "custo_unitario"]].copy()
    return df_final, {
        "total_itens": len(df_final),
        "soma_qtd": soma_qtd,
        "soma_valor_venda": soma_valor_venda,
        "soma_valor_entrada": soma_valor_entrada,
        "coluna_valor_venda": coluna_valor_lida if nome_aba == "saidas_diarias" else "",
        "coluna_valor_entrada": coluna_valor_lida if nome_aba == "entradas_diarias" else "",
        "df_custos_extraidos": df_custos_extraidos,
        "data_iso": data_iso,
        "taxa_coincidencia": taxa_coincidencia,
        "qtd_codigos_repetidos": qtd_codigos_repetidos,
        "qtd_linhas_extras": qtd_linhas_extras,
        "exemplos_repetidos": exemplos_repetidos,
        "aviso_sem_data": aviso_sem_data,
    }


def atualizar_custos_via_entradas_df(
    df_custos_atual: pd.DataFrame,
    df_custos_novos_entrada: pd.DataFrame,
) -> tuple[pd.DataFrame, int, int]:
    """
    Faz o Upsert (atualização seletiva) na tabela de custos a partir dos custos unitários
    apurados na planilha de Entradas (Valor / Quantidade), preservando todos os demais SKUs.
    """
    if df_custos_novos_entrada is None or df_custos_novos_entrada.empty:
        return padronizar_dataframe(df_custos_atual, "custos"), 0, 0
    df_novos = df_custos_novos_entrada[df_custos_novos_entrada["custo_unitario"] > 0].copy()
    if df_novos.empty:
        return padronizar_dataframe(df_custos_atual, "custos"), 0, 0
    df_base_c = (
        padronizar_dataframe(df_custos_atual, "custos")
        if (df_custos_atual is not None and not df_custos_atual.empty)
        else padronizar_dataframe(pd.DataFrame(), "custos")
    )
    cods_existentes = set(df_base_c["codigo"].unique()) if not df_base_c.empty else set()
    cods_entrada = set(df_novos["codigo"].unique())
    qtd_atualizados = len(cods_entrada & cods_existentes)
    qtd_inseridos = len(cods_entrada - cods_existentes)
    df_combinado = pd.concat([df_base_c, df_novos[["codigo", "descricao", "custo_unitario"]]], ignore_index=True)
    df_final_c = padronizar_dataframe(df_combinado, "custos")
    return df_final_c, qtd_atualizados, qtd_inseridos


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_motor_giro_sazonal(
    df_estoque: pd.DataFrame,
    df_historico: pd.DataFrame,
    df_base_vendas: pd.DataFrame,
    df_custos: pd.DataFrame,
    dias_base_atual: int,
    janela_dias: int,
    incluir_sem_estoque: bool = True,
    df_entradas: pd.DataFrame = None,
    df_saidas: pd.DataFrame = None,
) -> tuple[pd.DataFrame, int, float]:
    if not df_estoque.empty:
        df_est_sku = df_estoque.groupby("codigo", as_index=False).agg(
            descricao_est=("descricao", "first"),
            saldo_atual=("saldo_geral", "first"),
        )
    else:
        df_est_sku = pd.DataFrame(columns=["codigo", "descricao_est", "saldo_atual"])
    if incluir_sem_estoque:
        frames_cat = []
        if not df_estoque.empty:
            frames_cat.append(df_estoque[["codigo", "descricao"]])
        if df_entradas is not None and not df_entradas.empty:
            frames_cat.append(df_entradas[["codigo", "descricao"]])
        if df_saidas is not None and not df_saidas.empty:
            frames_cat.append(df_saidas[["codigo", "descricao"]])
        if not df_base_vendas.empty:
            frames_cat.append(df_base_vendas[["codigo", "descricao"]])
        if not df_custos.empty:
            frames_cat.append(df_custos[["codigo", "descricao"]])
        if not df_historico.empty:
            df_h_cods = pd.DataFrame({"codigo": df_historico["codigo"].unique(), "descricao": ""})
            frames_cat.append(df_h_cods)
        if frames_cat:
            df_cat_total = pd.concat(frames_cat, ignore_index=True)
            df_cat_ComDesc = df_cat_total[df_cat_total["descricao"] != ""].drop_duplicates(subset=["codigo"], keep="first")
            todos_cods = pd.DataFrame({"codigo": df_cat_total["codigo"].unique()})
            df_prod = todos_cods.merge(df_cat_ComDesc, on="codigo", how="left")
            df_prod["descricao"] = df_prod["descricao"].fillna("Produto sem descrição ativa")
            df_prod = df_prod.merge(df_est_sku[["codigo", "saldo_atual"]], on="codigo", how="left")
            df_prod["saldo_atual"] = df_prod["saldo_atual"].fillna(0.0)
        else:
            df_prod = pd.DataFrame(columns=["codigo", "descricao", "saldo_atual"])
    else:
        df_prod = df_est_sku.rename(columns={"descricao_est": "descricao"}).copy()
    if not df_base_vendas.empty:
        df_base_uniq = df_base_vendas.groupby("codigo", as_index=False)["qtd_vendida"].sum()
        df_prod = df_prod.merge(df_base_uniq, on="codigo", how="left")
        df_prod["qtd_vendida"] = df_prod["qtd_vendida"].fillna(0.0)
        df_prod["giro_base"] = df_prod["qtd_vendida"] / max(int(dias_base_atual), 1)
    else:
        df_prod["qtd_vendida"] = 0.0
        df_prod["giro_base"] = 0.0
    intervalo_historico_dias = 0
    peso_historico = 0.0
    df_saidas_sku = pd.DataFrame(
        columns=[
            "codigo",
            "giro_historico",
            "giro_historico_sem_pico",
            "saida_ult_dia",
            "data_ult_dia",
            "queda_pico_recente",
            "data_pico_recente",
            "saldo_antes_pico",
            "alerta_nf_nao_refletida",
        ]
    )
    datas_candidatas = set()
    if df_historico is not None and not df_historico.empty and "data" in df_historico.columns:
        datas_candidatas.update(df_historico["data"].dropna().unique())
    if df_entradas is not None and not df_entradas.empty and "data" in df_entradas.columns:
        datas_candidatas.update(df_entradas["data"].dropna().unique())
    if df_saidas is not None and not df_saidas.empty and "data" in df_saidas.columns:
        datas_candidatas.update(df_saidas["data"].dropna().unique())
    datas_todas = sorted([d for d in datas_candidatas if str(d).strip() != ""])
    if datas_todas:
        dt_max = pd.to_datetime(datas_todas[-1], format="%Y-%m-%d", errors="coerce")
        dt_corte = (
            (dt_max - pd.Timedelta(days=int(janela_dias))).strftime("%Y-%m-%d")
            if pd.notna(dt_max)
            else ""
        )
        df_h_win = (
            df_historico[df_historico["data"] >= dt_corte].copy()
            if (df_historico is not None and not df_historico.empty and dt_corte)
            else (df_historico.copy() if df_historico is not None else pd.DataFrame())
        )
        df_ent_win = (
            df_entradas[df_entradas["data"] >= dt_corte].copy()
            if (df_entradas is not None and not df_entradas.empty and dt_corte)
            else (df_entradas.copy() if df_entradas is not None else pd.DataFrame())
        )
        df_sai_win = (
            df_saidas[df_saidas["data"] >= dt_corte].copy()
            if (df_saidas is not None and not df_saidas.empty and dt_corte)
            else (df_saidas.copy() if df_saidas is not None else pd.DataFrame())
        )
        datas_hist = sorted(df_h_win["data"].unique()) if not df_h_win.empty else []
        quedas_por_sku = pd.DataFrame()
        saldo_prev_sku = pd.DataFrame()
        dias_por_coluna = {}
        primeiro_saldo_sku = pd.Series(dtype=float)
        ultimo_saldo_sku = pd.Series(dtype=float)
        nf_nao_refletida_sku = pd.Series(dtype=str)

        if not df_h_win.empty:
            chaves_dedup_h = ["codigo", "lote", "data"] if "lote" in df_h_win.columns else ["codigo", "data"]
            df_h_win = df_h_win.drop_duplicates(subset=chaves_dedup_h, keep="last")
            grade_geral = (
                df_h_win.groupby(["codigo", "data"], as_index=False)["saldo_geral"]
                .first()
            )
            todos_cods_grade = df_prod["codigo"].unique() if not df_prod.empty else grade_geral["codigo"].unique()
            pivot_geral = (
                grade_geral.pivot(index="codigo", columns="data", values="saldo_geral")
                .reindex(index=todos_cods_grade, columns=datas_hist)
                .fillna(0.0)
            )
            primeiro_saldo_sku = pivot_geral[datas_hist[0]]
            ultimo_saldo_sku = pivot_geral[datas_hist[-1]]

        if len(datas_hist) >= 2:
            deltas_geral = pivot_geral.diff(axis=1)
            cols_fim_transicao = datas_hist[1:]
            cols_transicao = datas_hist[:-1]
            mapa_col_transicao = dict(zip(cols_fim_transicao, cols_transicao))
            deltas_geral = deltas_geral[cols_fim_transicao].rename(columns=mapa_col_transicao)

            for idx_t, dt_ini_t in enumerate(cols_transicao):
                dt_fim_t = datas_hist[idx_t + 1]
                t1 = pd.to_datetime(dt_ini_t, format="%Y-%m-%d", errors="coerce")
                t2 = pd.to_datetime(dt_fim_t, format="%Y-%m-%d", errors="coerce")
                dias_por_coluna[dt_ini_t] = max(int((t2 - t1).days), 1) if (pd.notna(t1) and pd.notna(t2)) else 1

            entradas_transicao = pd.DataFrame(0.0, index=pivot_geral.index, columns=cols_transicao)
            if not df_ent_win.empty:
                df_ent_grp = df_ent_win.groupby(["codigo", "data"], as_index=False)["qtd_entrada"].sum()
                for idx_t, dt_ini_t in enumerate(cols_transicao):
                    dt_fim_t = datas_hist[idx_t + 1]
                    mask_int = (df_ent_grp["data"] >= dt_ini_t) & (df_ent_grp["data"] < dt_fim_t)
                    if mask_int.any():
                        soma_ent = df_ent_grp.loc[mask_int].groupby("codigo")["qtd_entrada"].sum()
                        novos_idx = soma_ent.index.difference(entradas_transicao.index)
                        if len(novos_idx) > 0:
                            entradas_transicao = entradas_transicao.reindex(entradas_transicao.index.union(novos_idx), fill_value=0.0)
                            deltas_geral = deltas_geral.reindex(entradas_transicao.index, fill_value=0.0)
                        entradas_transicao.loc[soma_ent.index, dt_ini_t] = soma_ent.values

            saidas_transicao = pd.DataFrame(0.0, index=entradas_transicao.index, columns=cols_transicao)
            cols_com_planilha_saida = set()
            if not df_sai_win.empty:
                df_sai_grp = df_sai_win.groupby(["codigo", "data"], as_index=False)["qtd_saida"].sum()
                for idx_t, dt_ini_t in enumerate(cols_transicao):
                    dt_fim_t = datas_hist[idx_t + 1]
                    mask_sai = (df_sai_grp["data"] >= dt_ini_t) & (df_sai_grp["data"] < dt_fim_t)
                    if mask_sai.any():
                        cols_com_planilha_saida.add(dt_ini_t)
                        soma_sai = df_sai_grp.loc[mask_sai].groupby("codigo")["qtd_saida"].sum()
                        novos_idx = soma_sai.index.difference(saidas_transicao.index)
                        if len(novos_idx) > 0:
                            saidas_transicao = saidas_transicao.reindex(saidas_transicao.index.union(novos_idx), fill_value=0.0)
                            entradas_transicao = entradas_transicao.reindex(saidas_transicao.index, fill_value=0.0)
                            deltas_geral = deltas_geral.reindex(saidas_transicao.index, fill_value=0.0)
                        saidas_transicao.loc[soma_sai.index, dt_ini_t] = soma_sai.values

            # 1. Comparação direta das planilhas de Estoque Diário (captura quedas de saldo e consumo interno de fábrica)
            queda_direta = (-deltas_geral[cols_transicao]).clip(lower=0.0)

            # 2. Consumo parcial em alta de estoque: só é inferido quando NÃO há planilha de Saídas naquele dia
            # (se a planilha de Saídas do dia foi importada, a venda do dia já vem explícita em saidas_transicao,
            # evitando que uma Entrada ainda não lançada no saldo do ERP infle o consumo)
            cols_sem_planilha_saida = [c for c in cols_transicao if c not in cols_com_planilha_saida]
            consumo_em_alta = pd.DataFrame(0.0, index=entradas_transicao.index, columns=cols_transicao)
            if cols_sem_planilha_saida:
                ent_sem_sai = entradas_transicao[cols_sem_planilha_saida]
                del_sem_sai = deltas_geral[cols_sem_planilha_saida]
                mask_alta_parcial = (ent_sem_sai > 0.0) & (del_sem_sai > 0.0) & (del_sem_sai < ent_sem_sai)
                consumo_em_alta[cols_sem_planilha_saida] = (ent_sem_sai - del_sem_sai).where(mask_alta_parcial, 0.0)

            # Detecção de NF de Entrada que ainda não refletiu no saldo do ERP (para alerta de auditoria)
            mask_nf_nao_refletida = (
                (entradas_transicao > 0.0)
                & (deltas_geral[cols_transicao] <= 0.0)
                & (saidas_transicao <= 0.0)
            )
            if mask_nf_nao_refletida.any().any():
                alertas_nf_dict = {}
                for cod_nf in mask_nf_nao_refletida.index[mask_nf_nao_refletida.any(axis=1)]:
                    cols_nf = [c for c in cols_transicao if mask_nf_nao_refletida.loc[cod_nf, c]]
                    ult_dt_nf = cols_nf[-1]
                    qtd_nf = float(entradas_transicao.loc[cod_nf, ult_dt_nf])
                    dt_nf_fmt = pd.to_datetime(ult_dt_nf, format="%Y-%m-%d", errors="coerce")
                    str_dt_nf = dt_nf_fmt.strftime("%d/%m") if pd.notna(dt_nf_fmt) else str(ult_dt_nf)
                    alertas_nf_dict[cod_nf] = f"⏳ NF +{formatar_qtd_br(qtd_nf)} ({str_dt_nf}) s/ reflexo no saldo"
                nf_nao_refletida_sku = pd.Series(alertas_nf_dict)

            # 3. Cruzamento com Saídas/Vendas Diárias via max() (nunca soma duplicado com a queda de estoque)
            quedas_por_sku = queda_direta.combine(consumo_em_alta, lambda s1, s2: s1.combine(s2, max))
            quedas_por_sku = quedas_por_sku.combine(saidas_transicao, lambda s1, s2: s1.combine(s2, max))

            saldo_prev_base = (
                pivot_geral
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            entradas_alinhadas = (
                entradas_transicao
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            deltas_alinhados = (
                deltas_geral
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            entrada_nova_no_dia = entradas_alinhadas.where(
                (deltas_alinhados > 0.0) | (saldo_prev_base <= 0.0), 0.0
            )
            saldo_prev_sku = (saldo_prev_base + entrada_nova_no_dia).combine(
                quedas_por_sku, lambda s1, s2: s1.combine(s2, max)
            ).fillna(0.0)

        if not df_sai_win.empty:
            df_sai_grp_all = df_sai_win.groupby(["codigo", "data"], as_index=False)["qtd_saida"].sum()
            if len(datas_hist) >= 2:
                mask_fora = (df_sai_grp_all["data"] < datas_hist[0]) | (df_sai_grp_all["data"] >= datas_hist[-1])
                df_sai_extra = df_sai_grp_all.loc[mask_fora].copy()
            else:
                df_sai_extra = df_sai_grp_all.copy()
            if not df_sai_extra.empty:
                pivot_sai_extra = df_sai_extra.pivot(index="codigo", columns="data", values="qtd_saida").fillna(0.0)
                for col_dt_ex in pivot_sai_extra.columns:
                    dias_por_coluna[col_dt_ex] = 1
                if quedas_por_sku.empty:
                    quedas_por_sku = pivot_sai_extra.copy()
                    saldo_base_ex = primeiro_saldo_sku.reindex(pivot_sai_extra.index).fillna(0.0)
                    saldo_prev_sku = pivot_sai_extra.add(saldo_base_ex, axis=0)
                else:
                    idx_unido = quedas_por_sku.index.union(pivot_sai_extra.index)
                    quedas_por_sku = quedas_por_sku.reindex(idx_unido, fill_value=0.0)
                    saldo_prev_sku = saldo_prev_sku.reindex(idx_unido, fill_value=0.0)
                    saldo_base_ini = primeiro_saldo_sku.reindex(idx_unido).fillna(0.0)
                    saldo_base_fim = ultimo_saldo_sku.reindex(idx_unido).fillna(0.0)
                    for col_dt_ex in pivot_sai_extra.columns:
                        col_s_ex = pivot_sai_extra[col_dt_ex].reindex(idx_unido, fill_value=0.0)
                        quedas_por_sku[col_dt_ex] = col_s_ex
                        if datas_hist and col_dt_ex < datas_hist[0]:
                            saldo_prev_sku[col_dt_ex] = col_s_ex + saldo_base_ini
                        else:
                            saldo_prev_sku[col_dt_ex] = saldo_base_fim.combine(col_s_ex, max)
                    quedas_por_sku = quedas_por_sku[sorted(quedas_por_sku.columns)]
                    saldo_prev_sku = saldo_prev_sku[sorted(saldo_prev_sku.columns)]

        if not quedas_por_sku.empty:
            ts_hist = [pd.to_datetime(d, format="%Y-%m-%d", errors="coerce") for d in datas_hist]
            ts_hist = [t for t in ts_hist if pd.notna(t)]
            ts_mov = [pd.to_datetime(d, format="%Y-%m-%d", errors="coerce") for d in quedas_por_sku.columns]
            ts_mov = [t for t in ts_mov if pd.notna(t)]
            inicios_validos = ts_hist + ts_mov
            fins_validos = ts_hist + [t + pd.Timedelta(days=1) for t in ts_mov]
            if inicios_validos and fins_validos:
                d_ini = min(inicios_validos)
                d_fim = max(fins_validos)
                dias_corridos_total = int((d_fim - d_ini).days)
            else:
                dias_corridos_total = 1
            intervalo_historico_dias = max(dias_corridos_total, quedas_por_sku.shape[1], 1)
            peso_historico = min(float(intervalo_historico_dias) / float(janela_dias), 1.0)
            saida_total = quedas_por_sku.sum(axis=1)
            cols_mov = list(quedas_por_sku.columns)
            ult_col = cols_mov[-1]
            dt_ult_fmt = pd.to_datetime(ult_col, format="%Y-%m-%d", errors="coerce")
            str_ult_dia = dt_ult_fmt.strftime("%d/%m") if pd.notna(dt_ult_fmt) else str(ult_col)
            saida_ult_dia_s = quedas_por_sku[ult_col]

            cols_recentes_pico = cols_mov[-min(len(cols_mov), 5):]
            quedas_rec_df = quedas_por_sku[cols_recentes_pico]
            div_dias_rec = pd.Series({c: float(dias_por_coluna.get(c, 1)) for c in cols_recentes_pico})
            taxa_diaria_rec_df = quedas_rec_df.divide(div_dias_rec, axis=1)

            queda_pico_s = taxa_diaria_rec_df.max(axis=1)
            col_data_pico_s = taxa_diaria_rec_df.idxmax(axis=1)

            saldo_antes_pico_vals = []
            data_pico_fmt_vals = []
            queda_bruta_col_pico_vals = []
            dias_col_pico_vals = []
            for cod_idx, col_dt in col_data_pico_s.items():
                if cod_idx in saldo_prev_sku.index and col_dt in saldo_prev_sku.columns:
                    val_prev = saldo_prev_sku.loc[cod_idx, col_dt]
                    saldo_antes_pico_vals.append(0.0 if pd.isna(val_prev) else float(val_prev))
                else:
                    saldo_antes_pico_vals.append(0.0)
                queda_bruta_col_pico_vals.append(float(quedas_por_sku.loc[cod_idx, col_dt]))
                dias_col_pico_vals.append(float(dias_por_coluna.get(col_dt, 1)))
                dt_p = pd.to_datetime(col_dt, format="%Y-%m-%d", errors="coerce")
                data_pico_fmt_vals.append(dt_p.strftime("%d/%m") if pd.notna(dt_p) else str(col_dt))

            queda_bruta_pico_s = pd.Series(queda_bruta_col_pico_vals, index=quedas_por_sku.index)
            dias_sem_pico_s = pd.Series(
                [max(float(intervalo_historico_dias) - dp, 1.0) for dp in dias_col_pico_vals],
                index=quedas_por_sku.index,
            )
            saida_sem_pico = (saida_total - queda_bruta_pico_s).clip(lower=0.0)
            alerta_nf_s = nf_nao_refletida_sku.reindex(quedas_por_sku.index).fillna("")

            df_saidas_sku = pd.DataFrame(
                {
                    "codigo": quedas_por_sku.index,
                    "giro_historico": (saida_total / float(intervalo_historico_dias)).values,
                    "giro_historico_sem_pico": (saida_sem_pico / dias_sem_pico_s).values,
                    "saida_ult_dia": saida_ult_dia_s.values,
                    "data_ult_dia": str_ult_dia,
                    "queda_pico_recente": queda_pico_s.values,
                    "data_pico_recente": data_pico_fmt_vals,
                    "saldo_antes_pico": saldo_antes_pico_vals,
                    "alerta_nf_nao_refletida": alerta_nf_s.values,
                }
            )
    df_calc = df_prod.merge(df_saidas_sku, on="codigo", how="left")
    df_calc["giro_historico"] = df_calc["giro_historico"].fillna(0.0)
    df_calc["giro_historico_sem_pico"] = df_calc["giro_historico_sem_pico"].fillna(0.0)
    df_calc["saida_ult_dia"] = df_calc["saida_ult_dia"].fillna(0.0)
    df_calc["data_ult_dia"] = df_calc["data_ult_dia"].fillna("-")
    df_calc["queda_pico_recente"] = df_calc["queda_pico_recente"].fillna(0.0)
    df_calc["data_pico_recente"] = df_calc["data_pico_recente"].fillna("-")
    df_calc["saldo_antes_pico"] = df_calc["saldo_antes_pico"].fillna(0.0)
    df_calc["alerta_nf_nao_refletida"] = df_calc["alerta_nf_nao_refletida"].fillna("")
    df_calc["giro_ponderado"] = (
        (df_calc["giro_historico"] * peso_historico)
        + (df_calc["giro_base"] * (1.0 - peso_historico))
    )
    df_calc["giro_ponderado_sem_pico"] = (
        (df_calc["giro_historico_sem_pico"] * peso_historico)
        + (df_calc["giro_base"] * (1.0 - peso_historico))
    )
    return df_calc, intervalo_historico_dias, peso_historico


# ==============================================================================
# 6. CABEÇALHO PRINCIPAL E VERIFICAÇÃO DE CONEXÃO COM A NUVEM
# ==============================================================================
planilha_gsheets, erro_gsheets = obter_planilha_gsheets()
conectado_nuvem = planilha_gsheets is not None
col_titulo, col_status = st.columns([3.4, 1.2])
with col_titulo:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:14px; padding-top:4px;">
            <div style="background:linear-gradient(135deg,#7c3aed 0%,#10b981 100%); width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:1.55rem; box-shadow:0 6px 20px rgba(124,58,237,0.40);">
                🌾
            </div>
            <div>
                <div style="font-size:1.55rem; font-weight:800; color:#f8fafc; letter-spacing:-0.02em; line-height:1.15;">
                    Esteio Rural <span style="font-weight:400; color:#94a3b8;">| Torre de Controle & Giro Sazonal</span>
                </div>
                <div style="font-size:0.82rem; color:#94a3b8; margin-top:2px;">
                    Engenharia de Estoque, Curva ABC Cruzada, Radar FEFO e Sugestão Inteligente de Compras
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_status:
    texto_status = (
        "🟢 Google Sheets Online" if conectado_nuvem else "❌ Sem Conexão"
    )
    st.markdown(
        f"""
        <div class="status-box">
            <div class="status-label">Banco de Dados 100% Nuvem</div>
            <div class="status-value" title="{texto_status}">{texto_status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
if not conectado_nuvem:
    st.error(
        f"❌ **Não foi possível conectar ao Google Sheets:** {erro_gsheets}\n\n"
        "O sistema opera 100% em nuvem para garantir que nenhuma operação seja feita sobre dados "
        "desatualizados ou vazios. Verifique as credenciais em `st.secrets` ou clique abaixo para reconectar."
    )
    if st.button("🔄 Tentar Reconectar ao Google Sheets Agora", type="primary"):
        _conectar_planilha_cached.clear()
        carregar_estado_completo.clear()
        st.rerun()
    st.stop()
try:
    with st.spinner("Sincronizando dados com o Google Sheets..."):
        estado = carregar_estado_completo()
except Exception as erro_leitura:
    st.error(f"❌ Erro ao ler abas do Google Sheets: {erro_leitura}")
    if st.button("🔄 Tentar Novamente", type="primary"):
        _conectar_planilha_cached.clear()
        carregar_estado_completo.clear()
        st.rerun()
    st.stop()

df_estoque_bruto = estado["estoque_atual"]
df_historico_bruto = estado["historico"]
df_entradas_bruto = estado["entradas_diarias"]
df_saidas_bruto = estado["saidas_diarias"]
df_custos = estado["custos"]
df_base_vendas = estado["base_inicial"]
df_ocultos = estado["ocultos"]
df_pedidos_transito = estado.get("pedidos_transito", pd.DataFrame(columns=ESQUEMA_ABAS["pedidos_transito"]))
dias_base_atual = int(estado.get("dias_base", 87))
grupos_pref_custom = estado.get("grupos_pref_custom", {})
grupos_sku_custom = estado.get("grupos_sku_custom", {})
codigos_ocultos = set(df_ocultos["codigo"].unique()) if not df_ocultos.empty else set()
codigos_em_transito = set(df_pedidos_transito["codigo"].unique()) if not df_pedidos_transito.empty else set()
mostrar_ocultos_temp = False
if len(codigos_ocultos) > 0:
    col_aviso_oc, col_toggle_oc = st.columns([2.8, 1.2])
    with col_aviso_oc:
        st.caption(
            f"🙈 Atualmente há **{formatar_num_br(len(codigos_ocultos))} produto(s) oculto(s)** dos relatórios (gerencie na Aba 6)."
        )
    with col_toggle_oc:
        mostrar_ocultos_temp = st.toggle(
            "👁️ Mostrar ocultos temporariamente", value=False
        )
if codigos_ocultos and not mostrar_ocultos_temp:
    df_estoque = df_estoque_bruto[~df_estoque_bruto["codigo"].isin(codigos_ocultos)]
    df_historico = df_historico_bruto[~df_historico_bruto["codigo"].isin(codigos_ocultos)]
    df_entradas = df_entradas_bruto[~df_entradas_bruto["codigo"].isin(codigos_ocultos)]
    df_saidas = df_saidas_bruto[~df_saidas_bruto["codigo"].isin(codigos_ocultos)]
    df_base_vendas_rel = df_base_vendas[~df_base_vendas["codigo"].isin(codigos_ocultos)]
    df_custos_rel = df_custos[~df_custos["codigo"].isin(codigos_ocultos)]
else:
    df_estoque = df_estoque_bruto
    df_historico = df_historico_bruto
    df_entradas = df_entradas_bruto
    df_saidas = df_saidas_bruto
    df_base_vendas_rel = df_base_vendas
    df_custos_rel = df_custos


# ==============================================================================
# 7. NAVEGAÇÃO POR ABAS (100% NUVEM — DASHBOARD EM 1º E IMPORTAÇÃO EM ÚLTIMO)
# ==============================================================================
aba_dash, aba2, aba3, aba4, aba5, aba6, aba1 = st.tabs(
    [
        "📊 1. Dashboard Executivo (Power BI)",
        "🛒 2. Sugestão de Compras & Cotação",
        "⏳ 3. Radar FEFO & Promoções IA",
        "📈 4. Curva ABC Financeira",
        "🔍 5. Auditoria de ERP",
        f"👁️‍🗨️ 6. Ocultar Produtos ({formatar_num_br(len(codigos_ocultos))})",
        "📥 7. Importação & Backup",
    ]
)

# ------------------------------------------------------------------------------
# ABA 1 (NOVA): DASHBOARD EXECUTIVO ESTILO POWER BI (TOMADA DE DECISÃO)
# ------------------------------------------------------------------------------
with aba_dash:
    st.markdown("### 📊 Torre de Controle Executiva — Inteligência de Estoque & Capital (Power BI)")
    st.caption(
        "Visão gerencial consolidada para tomada de decisão: Saúde do Capital Imobilizado, Matriz Cruzada 2D (Estoque × Giro), "
        "Nível de Serviço dos Campeões de Venda, Risco FEFO Dinâmico e Fluxo Diário de Compras vs. Saídas."
    )
    if df_estoque.empty and df_base_vendas_rel.empty:
        st.info("Importe as planilhas de Estoque e Custos na Aba 7 (Importação & Backup) para ativar o Dashboard Executivo.")
    else:
        f_col1, f_col2, f_col3, f_col4 = st.columns([1.3, 1.8, 1.0, 1.0])
        with f_col1:
            visao_operacional_bi = st.selectbox(
                "🏢 Escopo Operacional:",
                options=[
                    "🏢 Tudo Consolidado (Loja + Fábrica)",
                    "🏪 Apenas Loja Comercial (Varejo)",
                    "🏭 Apenas Fábrica / Matéria-Prima (MP)",
                ],
                index=0,
                key="bi_escopo_op",
            )
        df_bi_base, dias_hist_bi, peso_hist_bi = calcular_motor_giro_sazonal(
            df_estoque=df_estoque,
            df_historico=df_historico,
            df_base_vendas=df_base_vendas_rel,
            df_custos=df_custos_rel,
            dias_base_atual=dias_base_atual,
            janela_dias=120,
            incluir_sem_estoque=True,
            df_entradas=df_entradas,
            df_saidas=df_saidas,
        )
        df_bi = df_bi_base.copy()
        if not df_custos_rel.empty:
            df_bi = df_bi.merge(df_custos_rel[["codigo", "custo_unitario"]], on="codigo", how="left")
            df_bi["custo_unitario"] = df_bi["custo_unitario"].fillna(0.0)
        else:
            df_bi["custo_unitario"] = 0.0

        df_bi["departamento"] = df_bi["codigo"].map(
            lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
        )
        df_bi["eh_mp"] = [
            True
            if (
                str(dep).strip().startswith("26")
                or "matéria-prima" in str(dep).lower()
                or "materia-prima" in str(dep).lower()
                or "(mp)" in str(dep).lower()
            )
            else (
                False
                if str(cod) in grupos_sku_custom
                else (
                    str(desc).strip().upper().startswith("MP ")
                    or str(cod).strip().startswith("26")
                )
            )
            for cod, desc, dep in zip(df_bi["codigo"], df_bi["descricao"], df_bi["departamento"])
        ]
        if visao_operacional_bi.startswith("🏪"):
            df_bi = df_bi[~df_bi["eh_mp"]].copy()
        elif visao_operacional_bi.startswith("🏭"):
            df_bi = df_bi[df_bi["eh_mp"]].copy()
        opcoes_depto_bi = sorted(df_bi["departamento"].unique())
        with f_col2:
            deptos_sel_bi = st.multiselect(
                "📂 Filtrar Departamento / Linha (vazio = Todos):",
                options=opcoes_depto_bi,
                default=[],
                key="bi_deptos_sel",
            )
        if deptos_sel_bi:
            df_bi = df_bi[df_bi["departamento"].isin(deptos_sel_bi)].copy()

        with f_col3:
            meta_cobertura_bi = st.number_input(
                "🎯 Meta Cobertura (dias):",
                min_value=15,
                max_value=240,
                value=120,
                step=15,
                key="bi_meta_cob",
                help="Padrão de 120 dias. Acima desta cobertura (em dias de giro), o capital passa a ser monitorado como Excesso Liberável.",
            )
        with f_col4:
            lead_bi = st.number_input(
                "🚚 Prazo Entrega Alerta (dias):",
                min_value=1,
                max_value=60,
                value=10,
                step=1,
                key="bi_lead_alerta",
                help="Itens com giro cuja autonomia atual seja menor ou igual a este prazo entram em alerta de Ruptura.",
            )

        df_bi["saldo_pos"] = df_bi["saldo_atual"].clip(lower=0.0)
        df_bi["valor_estoque"] = df_bi["saldo_pos"] * df_bi["custo_unitario"]
        df_bi["giro_dia"] = df_bi["giro_ponderado"].clip(lower=0.0)
        df_bi["cmv_diario"] = df_bi["giro_dia"] * df_bi["custo_unitario"]
        df_bi["cmv_mensal"] = df_bi["cmv_diario"] * 30.0
        df_bi["autonomia_dias"] = (
            (df_bi["saldo_pos"] / df_bi["giro_dia"].replace(0.0, float("nan")))
            .fillna(9999.0)
            .round(1)
        )

        # Classificação ABC Dupla: ABC de Estoque (Patrimônio) vs. ABC de Giro (CMV Mensal)
        df_bi = df_bi.sort_values(["valor_estoque", "codigo"], ascending=[False, True]).reset_index(drop=True)
        tot_cap_bi = float(df_bi["valor_estoque"].sum())
        if tot_cap_bi > 0:
            acum_cap_ant = (df_bi["valor_estoque"].cumsum() - df_bi["valor_estoque"]) / tot_cap_bi * 100.0
            df_bi["abc_estoque"] = [
                "Sem Estoque" if v <= 0 else ("A" if a < 80.0 else ("B" if a < 95.0 else "C"))
                for v, a in zip(df_bi["valor_estoque"], acum_cap_ant)
            ]
        else:
            df_bi["abc_estoque"] = "Sem Estoque"

        df_bi = df_bi.sort_values(["cmv_mensal", "codigo"], ascending=[False, True]).reset_index(drop=True)
        tot_cmv_bi = float(df_bi["cmv_mensal"].sum())
        if tot_cmv_bi > 0:
            acum_cmv_ant = (df_bi["cmv_mensal"].cumsum() - df_bi["cmv_mensal"]) / tot_cmv_bi * 100.0
            df_bi["abc_giro"] = [
                "Sem Giro" if v <= 0 else ("A" if a < 80.0 else ("B" if a < 95.0 else "C"))
                for v, a in zip(df_bi["cmv_mensal"], acum_cmv_ant)
            ]
        else:
            df_bi["abc_giro"] = "Sem Giro"

        teto_cobertura_longa_bi = max(180, int(meta_cobertura_bi) + 60)

        def _classificar_faixa_saude_bi(r):
            s_pos = float(r["saldo_pos"])
            g_dia = float(r["giro_dia"])
            aut = float(r["autonomia_dias"])
            if s_pos <= 0:
                return "0. Zerado"
            if g_dia <= 0:
                return "5. Estoque Parado (Sem Giro)"
            if aut <= float(lead_bi):
                return f"1. Crítico / Ruptura (≤ {int(lead_bi)}d)"
            if aut <= float(meta_cobertura_bi):
                return f"2. Saudável ({int(lead_bi)+1} a {int(meta_cobertura_bi)}d)"
            if aut <= float(teto_cobertura_longa_bi):
                return f"3. Cobertura Longa ({int(meta_cobertura_bi)+1} a {teto_cobertura_longa_bi}d)"
            return f"4. Excesso (> {teto_cobertura_longa_bi}d)"

        df_bi["faixa_saude"] = df_bi.apply(_classificar_faixa_saude_bi, axis=1)
        df_bi["estoque_alvo_val"] = df_bi["cmv_diario"] * float(meta_cobertura_bi)
        df_bi["capital_liberavel"] = [
            max(0.0, float(v) - float(alv)) if float(g) > 0 else float(v)
            for v, alv, g in zip(df_bi["valor_estoque"], df_bi["estoque_alvo_val"], df_bi["giro_dia"])
        ]

        # Cálculo de Risco FEFO Dinâmico (lotes que vencem em até 90d vs. giro)
        cods_escopo_bi = set(df_bi["codigo"].unique())
        df_lotes_bi = df_estoque[
            (df_estoque["codigo"].isin(cods_escopo_bi)) & (df_estoque["saldo_lote"] > 0)
        ].copy()
        vlr_fefo_90d = 0.0
        vlr_sobra_fefo_90d = 0.0
        if not df_lotes_bi.empty:
            df_lotes_bi["dt_val"] = converter_datas_deterministico(df_lotes_bi["validade"])
            hoje_ts_bi = pd.Timestamp(hoje_br())
            df_lotes_bi["dias_venc"] = (df_lotes_bi["dt_val"] - hoje_ts_bi).dt.days
            df_lotes_bi = df_lotes_bi.merge(
                df_bi[["codigo", "custo_unitario", "giro_dia"]], on="codigo", how="left"
            ).fillna({"custo_unitario": 0.0, "giro_dia": 0.0})
            df_lotes_bi["valor_lote"] = df_lotes_bi["saldo_lote"] * df_lotes_bi["custo_unitario"]
            lotes_ate_90 = df_lotes_bi[df_lotes_bi["dias_venc"].notna() & (df_lotes_bi["dias_venc"] <= 90)].copy()
            if not lotes_ate_90.empty:
                vlr_fefo_90d = float(lotes_ate_90["valor_lote"].sum())
                lotes_ate_90 = lotes_ate_90.sort_values(["codigo", "dias_venc"])
                lotes_ate_90["_sl_vendavel"] = [
                    float(sl) if float(dv) >= 0 else 0.0
                    for sl, dv in zip(lotes_ate_90["saldo_lote"], lotes_ate_90["dias_venc"])
                ]
                lotes_ate_90["acum_lote"] = lotes_ate_90.groupby("codigo")["_sl_vendavel"].cumsum()
                lotes_ate_90["antes_lote"] = (lotes_ate_90["acum_lote"] - lotes_ate_90["_sl_vendavel"]).clip(lower=0.0)
                lotes_ate_90["consumo_ate_venc"] = lotes_ate_90["dias_venc"].clip(lower=0.0) * lotes_ate_90["giro_dia"]
                lotes_ate_90["cap_absorcao"] = (lotes_ate_90["consumo_ate_venc"] - lotes_ate_90["antes_lote"]).clip(lower=0.0)
                lotes_ate_90["qtd_sobra"] = [
                    float(sl) if float(dv) < 0 else max(0.0, float(sl) - float(cap))
                    for sl, dv, cap in zip(lotes_ate_90["saldo_lote"], lotes_ate_90["dias_venc"], lotes_ate_90["cap_absorcao"])
                ]
                vlr_sobra_fefo_90d = float((lotes_ate_90["qtd_sobra"] * lotes_ate_90["custo_unitario"]).sum())

        # Indicadores de Nível de Serviço da Curva A de Giro (descontando itens já comprados em trânsito)
        df_giro_a = df_bi[df_bi["abc_giro"] == "A"]
        qtd_giro_a = len(df_giro_a)
        mask_rup_a_bi = ((df_giro_a["saldo_pos"] <= 0) | (df_giro_a["autonomia_dias"] <= float(lead_bi))) & (~df_giro_a["codigo"].isin(codigos_em_transito))
        qtd_giro_a_ruptura = int(mask_rup_a_bi.sum())
        nivel_servico_a_pct = ((qtd_giro_a - qtd_giro_a_ruptura) / max(qtd_giro_a, 1)) * 100.0 if qtd_giro_a > 0 else 100.0
        dio_global = (tot_cap_bi / (tot_cmv_bi / 30.0)) if tot_cmv_bi > 0 else 0.0
        tot_liberavel_bi = float(df_bi["capital_liberavel"].sum())
        skus_ativos_pos = int((df_bi["saldo_pos"] > 0).sum())

        falsos_c_count = int(((df_bi["abc_giro"] == "A") & (df_bi["abc_estoque"].isin(["C", "Sem Estoque"])) & (~df_bi["codigo"].isin(codigos_em_transito))).sum())
        elefantes_count = int(((df_bi["abc_estoque"] == "A") & (df_bi["abc_giro"].isin(["C", "Sem Giro"]))).sum())
        pct_liberavel_bi = (tot_liberavel_bi / max(tot_cap_bi, 1.0)) * 100.0 if tot_cap_bi > 0 else 0.0
        score_ring = max(0.0, min(100.0, nivel_servico_a_pct))
        cor_ring = "#10b981" if score_ring >= 90.0 else ("#f97316" if score_ring >= 75.0 else "#ef4444")
        dash_offset = 251.2 * (1.0 - (score_ring / 100.0))

        # Painel Bento UI Dark Neon (Inspirado no Design de Referência)
        st.markdown(
            f"""
            <div class="bento-grid">
                <div class="bento-card bento-card-emerald">
                    <div>
                        <div class="bento-title">
                            <span>💰 PATRIMÔNIO EM ESTOQUE</span>
                            <span style="background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:8px; font-size:0.72rem;">{formatar_num_br(skus_ativos_pos)} SKUs ativos</span>
                        </div>
                        <div class="bento-big-val">{formatar_moeda_br(tot_cap_bi)}</div>
                        <div class="bento-badge-green">🔄 Giro Mensal (CMV): {formatar_moeda_br(tot_cmv_bi)}</div>
                    </div>
                    <div style="margin-top:10px; display:flex; align-items:flex-end; justify-content:space-between;">
                        <span class="bento-sub">Cobertura Global: <strong style="color:#f8fafc;">{formatar_num_br(dio_global, 0)} dias</strong></span>
                        <svg width="120" height="36" viewBox="0 0 120 36" fill="none">
                            <path d="M2 30 C25 28, 35 14, 58 18 C80 22, 92 6, 116 4" stroke="#10b981" stroke-width="3" stroke-linecap="round"/>
                            <circle cx="116" cy="4" r="4" fill="#34d399" />
                        </svg>
                    </div>
                </div>
                <div class="bento-card bento-card-purple">
                    <div>
                        <div class="bento-title">
                            <span>🔓 CAIXA DESTRAVÁVEL</span>
                            <span style="color:#c4b5fd;">Meta ≤ {int(meta_cobertura_bi)}d</span>
                        </div>
                        <div class="bento-big-val">{formatar_moeda_br(tot_liberavel_bi)}</div>
                        <div class="bento-badge-purple">⚡ {formatar_pct_br(pct_liberavel_bi, 1)} do capital total</div>
                    </div>
                    <div class="bento-sub">
                        Excesso acima de {int(meta_cobertura_bi)}d + itens sem saída em 90d
                    </div>
                </div>
                <div class="bento-card bento-card-amber">
                    <div style="position:relative; width:104px; height:104px; display:flex; align-items:center; justify-content:center;">
                        <svg width="104" height="104" viewBox="0 0 100 100" style="transform:rotate(-90deg);">
                            <circle cx="50" cy="50" r="40" stroke="rgba(148,163,184,0.16)" stroke-width="9" fill="none"/>
                            <circle cx="50" cy="50" r="40" stroke="{cor_ring}" stroke-width="9" fill="none"
                                stroke-dasharray="251.2" stroke-dashoffset="{dash_offset:.1f}" stroke-linecap="round"/>
                        </svg>
                        <div style="position:absolute; text-align:center;">
                            <div style="font-size:1.35rem; font-weight:800; color:#ffffff; line-height:1.05;">{formatar_num_br(score_ring, 0)}%</div>
                            <div style="font-size:0.65rem; color:#94a3b8; font-weight:600;">Curva A</div>
                        </div>
                    </div>
                    <div style="font-size:0.76rem; color:#e2e8f0; font-weight:700; margin-top:6px;">
                        Disponibilidade Líderes ({formatar_num_br(qtd_giro_a - qtd_giro_a_ruptura)}/{formatar_num_br(qtd_giro_a)})
                    </div>
                </div>
                <div class="bento-card bento-card-cyan">
                    <div>
                        <div class="bento-title">
                            <span>⏳ RISCO FEFO REAL (≤ 90D)</span>
                            <span style="color:#38bdf8;">Sobra Projetada</span>
                        </div>
                        <div class="bento-big-val">{formatar_moeda_br(vlr_sobra_fefo_90d)}</div>
                        <div class="bento-badge-amber">🔥 {formatar_num_br(falsos_c_count)} Rupturas A  |  🐘 {formatar_num_br(elefantes_count)} Elefantes</div>
                    </div>
                    <div class="bento-sub">
                        Total em lotes ≤ 90d: <strong style="color:#f8fafc;">{formatar_moeda_br(vlr_fefo_90d)}</strong> (descontando giro)
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        g_col1, g_col2 = st.columns(2)
        faixa_saude_clicada = None
        depto_clicado = None

        with g_col1:
            st.markdown("#### 1. Saúde do Capital Imobilizado por Autonomia de Giro")
            st.caption("👆 **Clique em uma barra do gráfico ou em uma linha da tabela** para abrir os produtos daquele grupo!")
            df_ativos_bi = df_bi[df_bi["saldo_pos"] > 0].copy()
            if not df_ativos_bi.empty:
                res_saude_bi = (
                    df_ativos_bi.groupby("faixa_saude", as_index=False)
                    .agg(
                        SKUs=("codigo", "count"),
                        Capital=("valor_estoque", "sum"),
                        CMV_Mensal=("cmv_mensal", "sum"),
                    )
                    .sort_values("faixa_saude")
                    .reset_index(drop=True)
                )
                res_saude_bi["% Capital"] = (res_saude_bi["Capital"] / max(tot_cap_bi, 1.0)) * 100.0

                try:
                    import altair as alt
                    sel_bar_saude = alt.selection_point(fields=["faixa_saude"], name="sel_saude")
                    chart_saude = (
                        alt.Chart(res_saude_bi)
                        .mark_bar(cornerRadiusEnd=6, height=26)
                        .encode(
                            x=alt.X("Capital:Q", title="Capital Imobilizado (R$)"),
                            y=alt.Y("faixa_saude:N", sort=list(res_saude_bi["faixa_saude"]), title=None, axis=alt.Axis(labelLimit=260)),
                            color=alt.Color(
                                "faixa_saude:N",
                                legend=None,
                                scale=alt.Scale(scheme="tealblues"),
                            ),
                            opacity=alt.condition(sel_bar_saude, alt.value(1.0), alt.value(0.55)),
                            tooltip=[
                                alt.Tooltip("faixa_saude:N", title="Faixa de Saúde"),
                                alt.Tooltip("SKUs:Q", title="SKUs", format=",d"),
                                alt.Tooltip("Capital:Q", title="Capital (R$)", format=",.2f"),
                                alt.Tooltip("CMV_Mensal:Q", title="CMV Mensal (R$)", format=",.2f"),
                            ],
                        )
                        .add_params(sel_bar_saude)
                        .properties(height=235)
                    )
                    ev_chart_s = st.altair_chart(chart_saude, use_container_width=True, on_select="rerun", key="alt_chart_saude_bi")
                    faixa_saude_clicada = _extrair_selecao_altair(ev_chart_s, "faixa_saude")
                except Exception:
                    st.bar_chart(
                        res_saude_bi.set_index("faixa_saude")[["Capital"]],
                        use_container_width=True,
                        height=235,
                    )

                df_saude_exib = res_saude_bi.rename(
                    columns={
                        "faixa_saude": "Faixa de Saúde",
                        "Capital": "Capital (R$)",
                        "CMV_Mensal": "CMV/Mês (R$)",
                        "% Capital": "% Cap.",
                    }
                )
                linhas_sel_saude = _renderizar_dataframe_selecionavel(
                    estilizar_tabela_br(
                        df_saude_exib,
                        formatadores={
                            "SKUs": formatar_num_br,
                            "Capital (R$)": formatar_moeda_br,
                            "CMV/Mês (R$)": formatar_moeda_br,
                            "% Cap.": lambda x: formatar_pct_br(x, 1),
                        },
                        colunas_esquerda=["Faixa de Saúde"],
                    ),
                    key="df_sel_saude_bi",
                )
                if linhas_sel_saude:
                    idx_s = linhas_sel_saude[0]
                    if 0 <= idx_s < len(res_saude_bi):
                        faixa_saude_clicada = str(res_saude_bi.iloc[idx_s]["faixa_saude"])
            else:
                st.info("Nenhum item com saldo positivo no filtro atual.")

        with g_col2:
            st.markdown("#### 2. Capital Imobilizado vs. Giro Mensal (CMV) por Departamento")
            st.caption("👆 **Clique na linha do grupo (ex: `50 - Veterinária`) ou na barra** para abrir os produtos daquele grupo!")
            res_depto_bi = (
                df_bi.groupby("departamento", as_index=False)
                .agg(
                    SKUs=("codigo", lambda s: int((df_bi.loc[s.index, "saldo_pos"] > 0).sum())),
                    Capital=("valor_estoque", "sum"),
                    CMV_Mensal=("cmv_mensal", "sum"),
                )
                .sort_values("Capital", ascending=False)
            )
            res_depto_bi = res_depto_bi[(res_depto_bi["Capital"] > 0) | (res_depto_bi["CMV_Mensal"] > 0)].reset_index(drop=True)
            if not res_depto_bi.empty:
                res_depto_bi["Cobertura"] = [
                    round(c / (m / 30.0), 0) if m > 0 else 999.0
                    for c, m in zip(res_depto_bi["Capital"], res_depto_bi["CMV_Mensal"])
                ]
                try:
                    import altair as alt
                    sel_bar_dep = alt.selection_point(fields=["departamento"], name="sel_depto")
                    chart_dep = (
                        alt.Chart(res_depto_bi.head(12))
                        .mark_bar(cornerRadiusEnd=6, height=18)
                        .encode(
                            x=alt.X("Capital:Q", title="Capital Atual (R$)"),
                            y=alt.Y("departamento:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                            color=alt.value("#38bdf8"),
                            opacity=alt.condition(sel_bar_dep, alt.value(1.0), alt.value(0.55)),
                            tooltip=[
                                alt.Tooltip("departamento:N", title="Grupo / Departamento"),
                                alt.Tooltip("SKUs:Q", title="SKUs c/ Saldo", format=",d"),
                                alt.Tooltip("Capital:Q", title="Capital Atual (R$)", format=",.2f"),
                                alt.Tooltip("CMV_Mensal:Q", title="Giro CMV/Mês (R$)", format=",.2f"),
                            ],
                        )
                        .add_params(sel_bar_dep)
                        .properties(height=235)
                    )
                    ev_chart_d = st.altair_chart(chart_dep, use_container_width=True, on_select="rerun", key="alt_chart_depto_bi")
                    depto_clicado = _extrair_selecao_altair(ev_chart_d, "departamento")
                except Exception:
                    st.bar_chart(
                        res_depto_bi.set_index("departamento")[["Capital", "CMV_Mensal"]],
                        use_container_width=True,
                        height=235,
                    )

                df_dep_exib = res_depto_bi.rename(
                    columns={
                        "departamento": "Grupo / Departamento",
                        "SKUs": "SKUs",
                        "Capital": "Capital (R$)",
                        "CMV_Mensal": "CMV/Mês (R$)",
                    }
                )
                linhas_sel_dep = _renderizar_dataframe_selecionavel(
                    estilizar_tabela_br(
                        df_dep_exib,
                        formatadores={
                            "SKUs": formatar_num_br,
                            "Capital (R$)": formatar_moeda_br,
                            "CMV/Mês (R$)": formatar_moeda_br,
                            "Cobertura": lambda x: "Sem Giro" if pd.notna(x) and float(x) >= 999.0 else f"{formatar_num_br(x, 0)}d",
                        },
                        colunas_esquerda=["Grupo / Departamento"],
                    ),
                    key="df_sel_depto_bi",
                )
                if linhas_sel_dep:
                    idx_d = linhas_sel_dep[0]
                    if 0 <= idx_d < len(res_depto_bi):
                        depto_clicado = str(res_depto_bi.iloc[idx_d]["departamento"])

        # Painel de Detalhamento Interativo (Drill-Down) quando o usuário clica no Quadro 1 ou no Quadro 2
        if faixa_saude_clicada:
            df_det_s = (
                df_ativos_bi[df_ativos_bi["faixa_saude"] == faixa_saude_clicada]
                .sort_values(["valor_estoque", "cmv_mensal"], ascending=[False, False])
                .reset_index(drop=True)
            )
            with st.container():
                st.markdown(
                    f"##### 🔎 Produtos na Faixa Selecionada: **{faixa_saude_clicada}** "
                    f"({formatar_num_br(len(df_det_s))} SKUs | Capital: {formatar_moeda_br(df_det_s['valor_estoque'].sum())})"
                )
                cs1, cs2 = st.columns([2.2, 1.0])
                with cs1:
                    busca_det_s = st.text_input(
                        "🔍 Filtrar produto dentro desta faixa de saúde:",
                        placeholder="Digite código ou nome do produto...",
                        key="busca_drill_saude_bi",
                    )
                if busca_det_s and busca_det_s.strip():
                    ts_b = busca_det_s.lower().strip()
                    df_det_s = df_det_s[
                        df_det_s["codigo"].str.lower().str.contains(ts_b, na=False, regex=False)
                        | df_det_s["descricao"].str.lower().str.contains(ts_b, na=False, regex=False)
                    ].copy()
                df_det_s_exib = df_det_s[
                    ["codigo", "descricao", "departamento", "saldo_atual", "custo_unitario", "valor_estoque", "giro_dia", "cmv_mensal", "autonomia_dias"]
                ].rename(
                    columns={
                        "codigo": "Cód.",
                        "descricao": "Descrição",
                        "departamento": "Grupo / Departamento",
                        "saldo_atual": "Saldo",
                        "custo_unitario": "Custo Un. (R$)",
                        "valor_estoque": "Capital (R$)",
                        "giro_dia": "Giro/Dia",
                        "cmv_mensal": "CMV/Mês (R$)",
                        "autonomia_dias": "Autonomia",
                    }
                )
                with cs2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.download_button(
                        label="📥 Baixar Produtos desta Faixa (.xlsx)",
                        data=gerar_excel_relatorio(df_det_s_exib, "Produtos_Faixa_Saude"),
                        file_name=f"Produtos_Saude_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_drill_saude_bi",
                    )
                st.dataframe(
                    estilizar_tabela_br(
                        df_det_s_exib,
                        formatadores={
                            "Saldo": formatar_qtd_br,
                            "Custo Un. (R$)": formatar_moeda_br,
                            "Capital (R$)": formatar_moeda_br,
                            "Giro/Dia": lambda x: formatar_num_br(x, 3) if (pd.notna(x) and 0 < float(x) < 0.05) else formatar_num_br(x, 2),
                            "CMV/Mês (R$)": formatar_moeda_br,
                            "Autonomia": lambda x: "Sem Giro" if pd.notna(x) and float(x) >= 999.0 else f"{formatar_num_br(x, 1)}d",
                        },
                        colunas_esquerda=["Descrição", "Grupo / Departamento"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )

        if depto_clicado:
            df_det_d = (
                df_bi[(df_bi["departamento"] == depto_clicado) & ((df_bi["saldo_pos"] > 0) | (df_bi["cmv_mensal"] > 0))]
                .sort_values(["valor_estoque", "cmv_mensal"], ascending=[False, False])
                .reset_index(drop=True)
            )
            with st.container():
                st.markdown(
                    f"##### 📂 Produtos do Grupo Selecionado: **{depto_clicado}** "
                    f"({formatar_num_br(len(df_det_d))} SKUs | Capital: {formatar_moeda_br(df_det_d['valor_estoque'].sum())} | "
                    f"CMV/Mês: {formatar_moeda_br(df_det_d['cmv_mensal'].sum())})"
                )
                cd_b1, cd_b2 = st.columns([2.2, 1.0])
                with cd_b1:
                    busca_det_d = st.text_input(
                        f"🔍 Pesquisar produto dentro de '{depto_clicado}':",
                        placeholder="Digite código ou nome do produto...",
                        key="busca_drill_depto_bi",
                    )
                if busca_det_d and busca_det_d.strip():
                    td_b = busca_det_d.lower().strip()
                    df_det_d = df_det_d[
                        df_det_d["codigo"].str.lower().str.contains(td_b, na=False, regex=False)
                        | df_det_d["descricao"].str.lower().str.contains(td_b, na=False, regex=False)
                    ].copy()
                df_det_d_exib = df_det_d[
                    ["codigo", "descricao", "faixa_saude", "saldo_atual", "custo_unitario", "valor_estoque", "giro_dia", "cmv_mensal", "autonomia_dias"]
                ].rename(
                    columns={
                        "codigo": "Cód.",
                        "descricao": "Descrição",
                        "faixa_saude": "Faixa de Saúde",
                        "saldo_atual": "Saldo",
                        "custo_unitario": "Custo Un. (R$)",
                        "valor_estoque": "Capital (R$)",
                        "giro_dia": "Giro/Dia",
                        "cmv_mensal": "CMV/Mês (R$)",
                        "autonomia_dias": "Autonomia",
                    }
                )
                with cd_b2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.download_button(
                        label="📥 Baixar Produtos deste Grupo (.xlsx)",
                        data=gerar_excel_relatorio(df_det_d_exib, "Produtos_Grupo"),
                        file_name=f"Produtos_Grupo_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_drill_depto_bi",
                    )
                st.dataframe(
                    estilizar_tabela_br(
                        df_det_d_exib,
                        formatadores={
                            "Saldo": formatar_qtd_br,
                            "Custo Un. (R$)": formatar_moeda_br,
                            "Capital (R$)": formatar_moeda_br,
                            "Giro/Dia": lambda x: formatar_num_br(x, 3) if (pd.notna(x) and 0 < float(x) < 0.05) else formatar_num_br(x, 2),
                            "CMV/Mês (R$)": formatar_moeda_br,
                            "Autonomia": lambda x: "Zerado" if pd.notna(x) and float(x) <= 0 else ("Sem Giro" if pd.notna(x) and float(x) >= 999.0 else f"{formatar_num_br(x, 1)}d"),
                        },
                        colunas_esquerda=["Descrição", "Faixa de Saúde"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )

        st.markdown("---")
        st.markdown("#### 3. Matriz Estratégica 2D (ABC de Estoque × ABC de Giro) & Listas de Ação Imediata")
        st.caption(
            "As duas tabelas abaixo agora ficam **uma embaixo da outra em largura total (100%)** para nunca cortar colunas. "
            "👆 **Clique em qualquer linha da Matriz Estratégica 2D** para abrir todos os produtos daquele quadrante!"
        )
        quadrantes_bi = [
            (
                "🏆 Campeões Saudáveis (Est. A/B × Giro A)",
                df_bi["abc_estoque"].isin(["A", "B"]) & (df_bi["abc_giro"] == "A"),
                "Manter reposição contínua",
            ),
            (
                "🔥 Falsos Classe C / Ruptura Líderes (Est. C/Zero × Giro A)",
                df_bi["abc_estoque"].isin(["C", "Sem Estoque"]) & (df_bi["abc_giro"] == "A"),
                "Compra imediata (perdendo venda)",
            ),
            (
                "🐘 Elefantes Brancos (Est. A × Giro C/Sem Giro)",
                (df_bi["abc_estoque"] == "A") & df_bi["abc_giro"].isin(["C", "Sem Giro"]),
                "Travar compra e promocionar",
            ),
            (
                "📦 Giro Intermediário Equilibrado (Giro B)",
                df_bi["abc_giro"] == "B",
                "Reposição regular conforme cobertura",
            ),
            (
                "💤 Cauda Longa s/ Giro (Est. B/C × Sem Giro)",
                df_bi["abc_estoque"].isin(["B", "C"]) & (df_bi["abc_giro"] == "Sem Giro"),
                "Liquidar gradualmente no balcão",
            ),
        ]
        linhas_quad = []
        for nome_q, mask_q, acao_q in quadrantes_bi:
            sub_q = df_bi[mask_q]
            linhas_quad.append(
                {
                    "Quadrante Estratégico": nome_q,
                    "SKUs": len(sub_q),
                    "Capital Imobilizado (R$)": float(sub_q["valor_estoque"].sum()),
                    "Giro CMV Mensal (R$)": float(sub_q["cmv_mensal"].sum()),
                    "Ação Recomendada": acao_q,
                }
            )
        df_quad_exib = pd.DataFrame(linhas_quad)
        linhas_sel_quad = _renderizar_dataframe_selecionavel(
            estilizar_tabela_br(
                df_quad_exib,
                formatadores={
                    "SKUs": formatar_num_br,
                    "Capital Imobilizado (R$)": formatar_moeda_br,
                    "Giro CMV Mensal (R$)": formatar_moeda_br,
                },
                colunas_esquerda=["Quadrante Estratégico", "Ação Recomendada"],
            ),
            key="df_sel_matriz_2d_bi",
        )

        if linhas_sel_quad:
            idx_q = linhas_sel_quad[0]
            if 0 <= idx_q < len(quadrantes_bi):
                nome_q_sel, mask_q_sel, _ = quadrantes_bi[idx_q]
                df_det_q = (
                    df_bi[mask_q_sel]
                    .sort_values(["cmv_mensal", "valor_estoque"], ascending=[False, False])
                    .reset_index(drop=True)
                )
                st.markdown(
                    f"##### 🎯 Produtos do Quadrante Selecionado: **{nome_q_sel}** "
                    f"({formatar_num_br(len(df_det_q))} SKUs | Capital: {formatar_moeda_br(df_det_q['valor_estoque'].sum())} | "
                    f"CMV/Mês: {formatar_moeda_br(df_det_q['cmv_mensal'].sum())})"
                )
                cq1, cq2 = st.columns([2.2, 1.0])
                with cq1:
                    busca_det_q = st.text_input(
                        "🔍 Pesquisar produto dentro deste quadrante:",
                        placeholder="Digite código ou nome do produto...",
                        key="busca_drill_quad_bi",
                    )
                if busca_det_q and busca_det_q.strip():
                    tq_b = busca_det_q.lower().strip()
                    df_det_q = df_det_q[
                        df_det_q["codigo"].str.lower().str.contains(tq_b, na=False, regex=False)
                        | df_det_q["descricao"].str.lower().str.contains(tq_b, na=False, regex=False)
                    ].copy()
                df_det_q_exib = df_det_q[
                    ["codigo", "descricao", "departamento", "saldo_atual", "custo_unitario", "valor_estoque", "abc_estoque", "abc_giro", "cmv_mensal", "autonomia_dias"]
                ].rename(
                    columns={
                        "codigo": "Cód.",
                        "descricao": "Descrição",
                        "departamento": "Grupo / Departamento",
                        "saldo_atual": "Saldo",
                        "custo_unitario": "Custo Un. (R$)",
                        "valor_estoque": "Capital (R$)",
                        "abc_estoque": "ABC Est.",
                        "abc_giro": "ABC Giro",
                        "cmv_mensal": "CMV/Mês (R$)",
                        "autonomia_dias": "Autonomia",
                    }
                )
                with cq2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.download_button(
                        label="📥 Baixar Produtos deste Quadrante (.xlsx)",
                        data=gerar_excel_relatorio(df_det_q_exib, "Produtos_Quadrante"),
                        file_name=f"Produtos_Quadrante_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_drill_quad_bi",
                    )
                st.dataframe(
                    estilizar_tabela_br(
                        df_det_q_exib,
                        formatadores={
                            "Saldo": formatar_qtd_br,
                            "Custo Un. (R$)": formatar_moeda_br,
                            "Capital (R$)": formatar_moeda_br,
                            "CMV/Mês (R$)": formatar_moeda_br,
                            "Autonomia": lambda x: "Zerado" if pd.notna(x) and float(x) <= 0 else ("Sem Giro" if pd.notna(x) and float(x) >= 999.0 else f"{formatar_num_br(x, 1)}d"),
                        },
                        colunas_esquerda=["Descrição", "Grupo / Departamento"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=300,
                )

        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(
            [
                f"🔥 Top Campeões em Ruptura / Alerta ({formatar_num_br(qtd_giro_a_ruptura)})",
                f"🐘 Top Elefantes Brancos Est. A ({formatar_num_br(elefantes_count)})",
                "💰 Top 30 Oportunidades de Destravar Caixa",
            ]
        )
        with sub_tab1:
            df_rup_a = (
                df_bi[(df_bi["abc_giro"] == "A") & ((df_bi["saldo_pos"] <= 0) | (df_bi["autonomia_dias"] <= float(lead_bi))) & (~df_bi["codigo"].isin(codigos_em_transito))]
                .sort_values("cmv_mensal", ascending=False)
                .head(30)
            )
            if df_rup_a.empty:
                st.success("✅ Todos os produtos da Curva A de Giro estão com cobertura acima do prazo de entrega!")
            else:
                df_rup_exib = df_rup_a[
                    ["codigo", "descricao", "departamento", "saldo_atual", "autonomia_dias", "abc_estoque", "cmv_mensal", "custo_unitario"]
                ].rename(
                    columns={
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "departamento": "Grupo / Departamento",
                        "saldo_atual": "Saldo Atual",
                        "autonomia_dias": "Autonomia (d)",
                        "abc_estoque": "ABC Est.",
                        "cmv_mensal": "Giro CMV/Mês (R$)",
                        "custo_unitario": "Custo Unit. (R$)",
                    }
                )
                st.dataframe(
                    estilizar_tabela_br(
                        df_rup_exib,
                        formatadores={
                            "Saldo Atual": formatar_qtd_br,
                            "Autonomia (d)": lambda x: "Zerado" if pd.notna(x) and float(x) <= 0 else formatar_num_br(x, 1),
                            "Giro CMV/Mês (R$)": formatar_moeda_br,
                            "Custo Unit. (R$)": formatar_moeda_br,
                        },
                        colunas_esquerda=["Descrição", "Grupo / Departamento"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=280,
                )
        with sub_tab2:
            df_elef = (
                df_bi[(df_bi["abc_estoque"] == "A") & (df_bi["abc_giro"].isin(["C", "Sem Giro"]))]
                .sort_values("valor_estoque", ascending=False)
                .head(30)
            )
            if df_elef.empty:
                st.success("✅ Nenhum item Classe A de estoque está parado ou com giro C!")
            else:
                df_elef_exib = df_elef[
                    ["codigo", "descricao", "departamento", "saldo_atual", "custo_unitario", "valor_estoque", "abc_giro", "cmv_mensal"]
                ].rename(
                    columns={
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "departamento": "Grupo / Departamento",
                        "saldo_atual": "Saldo Atual",
                        "custo_unitario": "Custo Unit. (R$)",
                        "valor_estoque": "Capital Parado (R$)",
                        "abc_giro": "ABC Giro",
                        "cmv_mensal": "Giro CMV/Mês (R$)",
                    }
                )
                st.dataframe(
                    estilizar_tabela_br(
                        df_elef_exib,
                        formatadores={
                            "Saldo Atual": formatar_qtd_br,
                            "Custo Unit. (R$)": formatar_moeda_br,
                            "Capital Parado (R$)": formatar_moeda_br,
                            "Giro CMV/Mês (R$)": formatar_moeda_br,
                        },
                        colunas_esquerda=["Descrição", "Grupo / Departamento"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=280,
                )
        with sub_tab3:
            df_dest = (
                df_bi[df_bi["capital_liberavel"] > 0]
                .sort_values("capital_liberavel", ascending=False)
                .head(30)
            )
            df_dest_exib = df_dest[
                ["codigo", "descricao", "departamento", "saldo_atual", "autonomia_dias", "valor_estoque", "capital_liberavel"]
            ].rename(
                columns={
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "departamento": "Grupo / Departamento",
                    "saldo_atual": "Saldo Atual",
                    "autonomia_dias": "Autonomia (d)",
                    "valor_estoque": "Estoque Atual (R$)",
                    "capital_liberavel": f"Excesso >{int(meta_cobertura_bi)}d (R$)",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_dest_exib,
                    formatadores={
                        "Saldo Atual": formatar_qtd_br,
                        "Autonomia (d)": lambda x: "Sem Giro" if pd.notna(x) and float(x) >= 999.0 else formatar_num_br(x, 1),
                        "Estoque Atual (R$)": formatar_moeda_br,
                        f"Excesso >{int(meta_cobertura_bi)}d (R$)": formatar_moeda_br,
                    },
                    colunas_esquerda=["Descrição", "Grupo / Departamento"],
                ),
                use_container_width=True,
                hide_index=True,
                height=280,
            )

        st.markdown("---")
        st.markdown("#### 4. Evolução do Patrimônio Diário e Balanço de Entradas (NFs) vs. Saídas (CMV e Faturamento)")
        ev_col1, ev_col2 = st.columns(2)
        mapa_custo_bi = dict(zip(df_custos_rel["codigo"], df_custos_rel["custo_unitario"])) if not df_custos_rel.empty else {}
        with ev_col1:
            if not df_historico.empty and "data" in df_historico.columns:
                df_h_bi = df_historico[df_historico["codigo"].isin(cods_escopo_bi)].copy()
                if not df_h_bi.empty:
                    df_h_bi["custo_u"] = df_h_bi["codigo"].map(mapa_custo_bi).fillna(0.0)
                    df_h_bi["val_dia"] = df_h_bi["saldo_geral"].clip(lower=0.0) * df_h_bi["custo_u"]
                    evol_pat = (
                        df_h_bi.groupby("data", as_index=False)
                        .agg(Patrimonio_Estoque=("val_dia", "sum"), SKUs_Ativos=("codigo", "nunique"))
                        .sort_values("data")
                    )
                    st.line_chart(
                        evol_pat.set_index("data")[["Patrimonio_Estoque"]],
                        use_container_width=True,
                        height=230,
                    )
            else:
                st.info("Histórico diário ainda sem datas suficientes para o gráfico de evolução.")
        with ev_col2:
            frames_fluxo = []
            if not df_entradas.empty and "data" in df_entradas.columns:
                df_e_bi = df_entradas[df_entradas["codigo"].isin(cods_escopo_bi)].copy()
                if not df_e_bi.empty:
                    df_e_bi["val_ent"] = df_e_bi["qtd_entrada"] * df_e_bi["codigo"].map(mapa_custo_bi).fillna(0.0)
                    frames_fluxo.append(df_e_bi.groupby("data", as_index=False)["val_ent"].sum())
            if not df_saidas.empty and "data" in df_saidas.columns:
                df_s_bi = df_saidas[df_saidas["codigo"].isin(cods_escopo_bi)].copy()
                if not df_s_bi.empty:
                    df_s_bi["val_sai"] = df_s_bi["qtd_saida"] * df_s_bi["codigo"].map(mapa_custo_bi).fillna(0.0)
                    frames_fluxo.append(df_s_bi.groupby("data", as_index=False)["val_sai"].sum())
            if frames_fluxo:
                datas_flx = sorted(
                    list(
                        (set(df_entradas["data"].unique()) if not df_entradas.empty else set())
                        | (set(df_saidas["data"].unique()) if not df_saidas.empty else set())
                    )
                )
                df_flx = pd.DataFrame({"data": [d for d in datas_flx if str(d).strip()]})
                if not df_entradas.empty:
                    df_e_bi = df_entradas[df_entradas["codigo"].isin(cods_escopo_bi)].copy()
                    custo_est_e = df_e_bi["qtd_entrada"] * df_e_bi["codigo"].map(mapa_custo_bi).fillna(0.0)
                    if "valor_entrada" in df_e_bi.columns:
                        val_e_s = df_e_bi["valor_entrada"].fillna(0.0)
                        df_e_bi["Entradas_NF_Custo"] = val_e_s.where(val_e_s > 0.0, custo_est_e)
                    else:
                        df_e_bi["Entradas_NF_Custo"] = custo_est_e
                    df_flx = df_flx.merge(df_e_bi.groupby("data", as_index=False)["Entradas_NF_Custo"].sum(), on="data", how="left")
                else:
                    df_flx["Entradas_NF_Custo"] = 0.0
                if not df_saidas.empty:
                    df_s_bi = df_saidas[df_saidas["codigo"].isin(cods_escopo_bi)].copy()
                    df_s_bi["Saidas_CMV_Custo"] = df_s_bi["qtd_saida"] * df_s_bi["codigo"].map(mapa_custo_bi).fillna(0.0)
                    df_s_bi["Faturamento_Vendas"] = (
                        df_s_bi["valor_venda"].fillna(0.0) if "valor_venda" in df_s_bi.columns else 0.0
                    )
                    df_flx = df_flx.merge(
                        df_s_bi.groupby("data", as_index=False).agg(
                            Saidas_CMV_Custo=("Saidas_CMV_Custo", "sum"),
                            Faturamento_Vendas=("Faturamento_Vendas", "sum"),
                        ),
                        on="data",
                        how="left",
                    )
                else:
                    df_flx["Saidas_CMV_Custo"] = 0.0
                    df_flx["Faturamento_Vendas"] = 0.0
                df_flx = df_flx.fillna(0.0).sort_values("data")
                cols_chart_flx = (
                    ["Entradas_NF_Custo", "Saidas_CMV_Custo", "Faturamento_Vendas"]
                    if float(df_flx["Faturamento_Vendas"].sum()) > 0
                    else ["Entradas_NF_Custo", "Saidas_CMV_Custo"]
                )
                st.bar_chart(
                    df_flx.set_index("data")[cols_chart_flx],
                    use_container_width=True,
                    height=230,
                )
            else:
                st.info("Importe planilhas de Entradas e Saídas na Aba 7 para visualizar o fluxo financeiro diário.")

        st.markdown("---")
        st.markdown("#### 5. Resultado Comercial Real: Faturamento, Margem Líquida Pós-Impostos & Comparativo Mês a Mês")
        st.caption(
            "Cruza o **Valor Total da Proposta** (4ª coluna da planilha de Saídas/Vendas) com o **Custo Unitário C1** e desconta "
            "a alíquota estimada de impostos sobre vendas (**ICMS, PIS/COFINS, ST**) para revelar a margem real deixada por produto, departamento e mês."
        )
        imp_col1, imp_col2 = st.columns([1.2, 2.8])
        with imp_col1:
            aliq_imp_dash = st.number_input(
                "🏛️ Alíquota Média de Impostos s/ Venda (%):",
                min_value=0.0,
                max_value=35.0,
                value=0.0,
                step=0.5,
                key="bi_aliq_imposto_vendas",
                help="Padrão 0% (maioria dos medicamentos veterinários isentos/monofásicos). Ajuste se desejar simular ICMS, PIS/COFINS ou ST.",
            )

        df_sai_escopo = (
            df_saidas[df_saidas["codigo"].isin(cods_escopo_bi)].copy()
            if (df_saidas is not None and not df_saidas.empty)
            else pd.DataFrame()
        )
        df_ent_escopo = (
            df_entradas[df_entradas["codigo"].isin(cods_escopo_bi)].copy()
            if (df_entradas is not None and not df_entradas.empty)
            else pd.DataFrame()
        )

        if df_sai_escopo.empty and df_ent_escopo.empty:
            st.info(
                "💡 Importe suas planilhas de **Saídas / Vendas Diárias** (com a 4ª coluna `Valor Total da Proposta`) na Aba 7 "
                "para destravar a auditoria de Faturamento Bruto, Margem Líquida Pós-Impostos e o Comparativo Mês a Mês!"
            )
        else:
            if not df_sai_escopo.empty:
                if "valor_venda" not in df_sai_escopo.columns:
                    df_sai_escopo["valor_venda"] = 0.0
                df_sai_escopo["custo_u"] = df_sai_escopo["codigo"].map(mapa_custo_bi).fillna(0.0)
                df_sai_escopo["cmv_total"] = df_sai_escopo["qtd_saida"] * df_sai_escopo["custo_u"]
                df_sai_escopo["fat_bruto"] = df_sai_escopo["valor_venda"].fillna(0.0)
                df_sai_escopo["imposto_est"] = df_sai_escopo["fat_bruto"] * (float(aliq_imp_dash) / 100.0)
                df_sai_escopo["lucro_bruto"] = df_sai_escopo["fat_bruto"] - df_sai_escopo["cmv_total"]
                df_sai_escopo["lucro_liquido"] = df_sai_escopo["fat_bruto"] - df_sai_escopo["imposto_est"] - df_sai_escopo["cmv_total"]
                df_sai_escopo["mes_ano"] = df_sai_escopo["data"].astype(str).str.slice(0, 7)
            else:
                df_sai_escopo = pd.DataFrame(
                    columns=["codigo", "descricao", "qtd_saida", "valor_venda", "data", "custo_u", "cmv_total", "fat_bruto", "imposto_est", "lucro_bruto", "lucro_liquido", "mes_ano"]
                )

            if not df_ent_escopo.empty:
                df_ent_escopo["custo_u"] = df_ent_escopo["codigo"].map(mapa_custo_bi).fillna(0.0)
                custo_est_nf = df_ent_escopo["qtd_entrada"] * df_ent_escopo["custo_u"]
                if "valor_entrada" in df_ent_escopo.columns:
                    val_nf_s = df_ent_escopo["valor_entrada"].fillna(0.0)
                    df_ent_escopo["compras_nf_custo"] = val_nf_s.where(val_nf_s > 0.0, custo_est_nf)
                else:
                    df_ent_escopo["compras_nf_custo"] = custo_est_nf
                df_ent_escopo["mes_ano"] = df_ent_escopo["data"].astype(str).str.slice(0, 7)
            else:
                df_ent_escopo = pd.DataFrame(columns=["codigo", "descricao", "qtd_entrada", "data", "custo_u", "compras_nf_custo", "mes_ano"])

            df_sai_com_fat = df_sai_escopo[df_sai_escopo["fat_bruto"] > 0].copy()
            fat_total_periodo = float(df_sai_com_fat["fat_bruto"].sum())
            cmv_das_vendas_fat = float(df_sai_com_fat["cmv_total"].sum())
            imp_total_periodo = float(df_sai_com_fat["imposto_est"].sum())
            lucro_bruto_periodo = fat_total_periodo - cmv_das_vendas_fat
            lucro_liq_periodo = fat_total_periodo - imp_total_periodo - cmv_das_vendas_fat
            margem_bruta_pct = ((lucro_bruto_periodo / fat_total_periodo) * 100.0) if fat_total_periodo > 0 else 0.0
            margem_liq_pct = ((lucro_liq_periodo / fat_total_periodo) * 100.0) if fat_total_periodo > 0 else 0.0
            markup_medio_pct = (((fat_total_periodo / cmv_das_vendas_fat) - 1.0) * 100.0) if cmv_das_vendas_fat > 0 else 0.0

            with imp_col2:
                if fat_total_periodo > 0:
                    st.info(
                        f"📈 **Resumo Faturado no Período:** Receita Bruta: **{formatar_moeda_br(fat_total_periodo)}**  |  "
                        f"CMV (C1): **{formatar_moeda_br(cmv_das_vendas_fat)}**  |  "
                        f"Impostos ({formatar_num_br(aliq_imp_dash, 1)}%): **{formatar_moeda_br(imp_total_periodo)}**  |  "
                        f"Lucro Líquido Real: **{formatar_moeda_br(lucro_liq_periodo)} ({formatar_pct_br(margem_liq_pct, 1)})**"
                    )
                else:
                    st.warning(
                        "ℹ️ As saídas registradas neste filtro ainda não possuem a 4ª coluna (`Valor Total da Proposta` > R$ 0,00). "
                        "Ao subir planilhas como `Saida venda 12-11-2026.xlsx` na Aba 7, o faturamento e as margens aparecerão aqui automaticamente!"
                    )

            rm1, rm2, rm3, rm4, rm5 = st.columns(5)
            rm1.metric(
                "💵 Faturamento Bruto",
                formatar_moeda_br(fat_total_periodo),
                f"{formatar_num_br(df_sai_com_fat['data'].nunique() if not df_sai_com_fat.empty else 0)} dia(s) c/ receita",
            )
            rm2.metric(
                "📦 CMV das Vendas (C1)",
                formatar_moeda_br(cmv_das_vendas_fat),
                f"Markup médio: +{formatar_num_br(markup_medio_pct, 1)}%",
            )
            rm3.metric(
                "🏷️ Lucro Bruto Comercial",
                formatar_moeda_br(lucro_bruto_periodo),
                f"Margem Bruta: {formatar_pct_br(margem_bruta_pct, 1)}",
            )
            rm4.metric(
                f"🏛️ Impostos ({formatar_num_br(aliq_imp_dash, 1)}%)",
                formatar_moeda_br(imp_total_periodo),
                "ICMS + PIS/COFINS + ST",
            )
            rm5.metric(
                "💎 Lucro Líquido Real",
                formatar_moeda_br(lucro_liq_periodo),
                f"Margem Líq.: {formatar_pct_br(margem_liq_pct, 1)}",
                delta_color="normal" if lucro_liq_periodo >= 0 else "inverse",
            )

            tab_mom, tab_sku_lucro, tab_sku_alerta = st.tabs(
                [
                    "📅 Comparativo Mês a Mês (Compras NF × CMV × Faturamento × Lucro)",
                    "🏆 Top Produtos Campeões de Lucro Líquido",
                    "⚠️ Auditoria de Margem Baixa ou Negativa Pós-Impostos",
                ]
            )

            with tab_mom:
                meses_todos = sorted(
                    list(
                        (set(df_sai_escopo["mes_ano"].unique()) if not df_sai_escopo.empty else set())
                        | (set(df_ent_escopo["mes_ano"].unique()) if not df_ent_escopo.empty else set())
                    )
                )
                meses_todos = [m for m in meses_todos if str(m).strip() and len(str(m).strip()) >= 7]
                if not meses_todos:
                    st.info("Ainda não há meses registrados em Entradas ou Saídas.")
                else:
                    df_mom = pd.DataFrame({"mes_ano": meses_todos})
                    if not df_ent_escopo.empty:
                        grp_e_m = df_ent_escopo.groupby("mes_ano", as_index=False).agg(
                            compras_nf=("compras_nf_custo", "sum"),
                            qtd_ent=("qtd_entrada", "sum"),
                        )
                        df_mom = df_mom.merge(grp_e_m, on="mes_ano", how="left")
                    else:
                        df_mom["compras_nf"] = 0.0
                        df_mom["qtd_ent"] = 0.0

                    if not df_sai_escopo.empty:
                        grp_s_m = df_sai_escopo.groupby("mes_ano", as_index=False).agg(
                            dias_mov=("data", "nunique"),
                            qtd_sai=("qtd_saida", "sum"),
                            cmv_sai=("cmv_total", "sum"),
                            faturamento=("fat_bruto", "sum"),
                            impostos=("imposto_est", "sum"),
                            lucro_bruto=("lucro_bruto", "sum"),
                            lucro_liq=("lucro_liquido", "sum"),
                        )
                        df_mom = df_mom.merge(grp_s_m, on="mes_ano", how="left")
                    else:
                        for c_z in ["dias_mov", "qtd_sai", "cmv_sai", "faturamento", "impostos", "lucro_bruto", "lucro_liq"]:
                            df_mom[c_z] = 0.0

                    df_mom = df_mom.fillna(0.0).sort_values("mes_ano").reset_index(drop=True)
                    df_mom["margem_bruta_pct"] = [
                        ((lb / ft) * 100.0) if ft > 0 else 0.0
                        for lb, ft in zip(df_mom["lucro_bruto"], df_mom["faturamento"])
                    ]
                    df_mom["margem_liq_pct"] = [
                        ((ll / ft) * 100.0) if ft > 0 else 0.0
                        for ll, ft in zip(df_mom["lucro_liq"], df_mom["faturamento"])
                    ]
                    base_cresc = df_mom["faturamento"] if float(df_mom["faturamento"].sum()) > 0 else df_mom["cmv_sai"]
                    cresc_vals = [0.0]
                    for idx_m in range(1, len(df_mom)):
                        ant_v = float(base_cresc.iloc[idx_m - 1])
                        at_v = float(base_cresc.iloc[idx_m])
                        cresc_vals.append((((at_v - ant_v) / ant_v) * 100.0) if ant_v > 0 else 0.0)
                    df_mom["cresc_mom_pct"] = cresc_vals

                    df_mom_exib = df_mom.rename(
                        columns={
                            "mes_ano": "Mês/Ano",
                            "dias_mov": "Dias c/ Saída",
                            "compras_nf": "Compras NF a Custo (R$)",
                            "cmv_sai": "CMV das Saídas (R$)",
                            "faturamento": "Faturamento Bruto (R$)",
                            "impostos": "Impostos Est. (R$)",
                            "lucro_bruto": "Lucro Bruto (R$)",
                            "lucro_liq": "Lucro Líquido Real (R$)",
                            "margem_bruta_pct": "Margem Bruta (%)",
                            "margem_liq_pct": "Margem Líquida (%)",
                            "cresc_mom_pct": "Evolução Mês a Mês (%)",
                        }
                    )[
                        [
                            "Mês/Ano",
                            "Dias c/ Saída",
                            "Compras NF a Custo (R$)",
                            "CMV das Saídas (R$)",
                            "Faturamento Bruto (R$)",
                            "Impostos Est. (R$)",
                            "Lucro Bruto (R$)",
                            "Lucro Líquido Real (R$)",
                            "Margem Bruta (%)",
                            "Margem Líquida (%)",
                            "Evolução Mês a Mês (%)",
                        ]
                    ]
                    st.dataframe(
                        estilizar_tabela_br(
                            df_mom_exib,
                            formatadores={
                                "Dias c/ Saída": formatar_num_br,
                                "Compras NF a Custo (R$)": formatar_moeda_br,
                                "CMV das Saídas (R$)": formatar_moeda_br,
                                "Faturamento Bruto (R$)": formatar_moeda_br,
                                "Impostos Est. (R$)": formatar_moeda_br,
                                "Lucro Bruto (R$)": formatar_moeda_br,
                                "Lucro Líquido Real (R$)": formatar_moeda_br,
                                "Margem Bruta (%)": lambda x: formatar_pct_br(x, 1),
                                "Margem Líquida (%)": lambda x: formatar_pct_br(x, 1),
                                "Evolução Mês a Mês (%)": lambda x: "-" if (pd.isna(x) or float(x) == 0.0) else formatar_pct_br(x, 1, com_sinal=True),
                            },
                            colunas_esquerda=[],
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            with tab_sku_lucro:
                if df_sai_com_fat.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) para ver o ranking de lucro por produto.")
                else:
                    grp_sku_fat = (
                        df_sai_com_fat.groupby("codigo", as_index=False)
                        .agg(
                            descricao=("descricao", "last"),
                            qtd_vendida=("qtd_saida", "sum"),
                            custo_u=("custo_u", "last"),
                            cmv_total=("cmv_total", "sum"),
                            faturamento=("fat_bruto", "sum"),
                            impostos=("imposto_est", "sum"),
                            lucro_bruto=("lucro_bruto", "sum"),
                            lucro_liq=("lucro_liquido", "sum"),
                        )
                    )
                    grp_sku_fat["preco_medio_venda"] = grp_sku_fat["faturamento"] / grp_sku_fat["qtd_vendida"].replace(0.0, float("nan"))
                    grp_sku_fat["margem_bruta_pct"] = (grp_sku_fat["lucro_bruto"] / grp_sku_fat["faturamento"]) * 100.0
                    grp_sku_fat["margem_liq_pct"] = (grp_sku_fat["lucro_liq"] / grp_sku_fat["faturamento"]) * 100.0
                    top_lucro_df = grp_sku_fat.sort_values("lucro_liq", ascending=False).head(50).reset_index(drop=True)
                    top_lucro_exib = top_lucro_df.rename(
                        columns={
                            "codigo": "Código",
                            "descricao": "Descrição",
                            "qtd_vendida": "Qtd. Vendida",
                            "custo_u": "Custo Unit. C1 (R$)",
                            "preco_medio_venda": "Preço Médio Venda (R$)",
                            "faturamento": "Faturamento (R$)",
                            "cmv_total": "CMV Total (R$)",
                            "impostos": "Impostos Est. (R$)",
                            "lucro_liq": "Lucro Líquido Real (R$)",
                            "margem_bruta_pct": "Margem Bruta (%)",
                            "margem_liq_pct": "Margem Líquida (%)",
                        }
                    )[
                        [
                            "Código",
                            "Descrição",
                            "Qtd. Vendida",
                            "Custo Unit. C1 (R$)",
                            "Preço Médio Venda (R$)",
                            "Faturamento (R$)",
                            "CMV Total (R$)",
                            "Impostos Est. (R$)",
                            "Lucro Líquido Real (R$)",
                            "Margem Bruta (%)",
                            "Margem Líquida (%)",
                        ]
                    ]
                    st.dataframe(
                        estilizar_tabela_br(
                            top_lucro_exib,
                            formatadores={
                                "Qtd. Vendida": formatar_qtd_br,
                                "Custo Unit. C1 (R$)": formatar_moeda_br,
                                "Preço Médio Venda (R$)": formatar_moeda_br,
                                "Faturamento (R$)": formatar_moeda_br,
                                "CMV Total (R$)": formatar_moeda_br,
                                "Impostos Est. (R$)": formatar_moeda_br,
                                "Lucro Líquido Real (R$)": formatar_moeda_br,
                                "Margem Bruta (%)": lambda x: formatar_pct_br(x, 1),
                                "Margem Líquida (%)": lambda x: formatar_pct_br(x, 1),
                            },
                            colunas_esquerda=["Descrição"],
                        ),
                        use_container_width=True,
                        hide_index=True,
                        height=300,
                    )
                    st.download_button(
                        label="📥 Baixar Ranking Completo de Rentabilidade por Produto (.xlsx)",
                        data=gerar_excel_relatorio(top_lucro_exib, "Rentabilidade_SKUs"),
                        file_name=f"Rentabilidade_Real_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_rentabilidade_skus_bi",
                    )

            with tab_sku_alerta:
                if df_sai_com_fat.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) para auditar margens comprimidas.")
                else:
                    df_alerta_mg = grp_sku_fat[(grp_sku_fat["custo_u"] > 0) & (grp_sku_fat["margem_liq_pct"] < 10.0)].sort_values(
                        "lucro_liq", ascending=True
                    ).reset_index(drop=True)
                    if df_alerta_mg.empty:
                        st.success(f"✅ Excelente! Nenhum produto vendido com custo cadastrado teve margem líquida inferior a 10% (após descontar {formatar_num_br(aliq_imp_dash, 1)}% de impostos).")
                    else:
                        df_alerta_mg["status_margem"] = [
                            "🔴 Prejuízo Líquido (Abaixo de Custo + Impostos)" if float(m) < 0.0 else "🟠 Margem Comprimida (< 10% Líq.)"
                            for m in df_alerta_mg["margem_liq_pct"]
                        ]
                        df_alerta_exib = df_alerta_mg.rename(
                            columns={
                                "codigo": "Código",
                                "descricao": "Descrição",
                                "status_margem": "Status de Margem",
                                "qtd_vendida": "Qtd. Vendida",
                                "custo_u": "Custo Unit. C1 (R$)",
                                "preco_medio_venda": "Preço Praticado (R$)",
                                "faturamento": "Faturamento (R$)",
                                "lucro_liq": "Resultado Líquido (R$)",
                                "margem_liq_pct": "Margem Líquida (%)",
                            }
                        )[
                            [
                                "Código",
                                "Descrição",
                                "Status de Margem",
                                "Qtd. Vendida",
                                "Custo Unit. C1 (R$)",
                                "Preço Praticado (R$)",
                                "Faturamento (R$)",
                                "Resultado Líquido (R$)",
                                "Margem Líquida (%)",
                            ]
                        ]
                        st.dataframe(
                            estilizar_tabela_br(
                                df_alerta_exib,
                                formatadores={
                                    "Qtd. Vendida": formatar_qtd_br,
                                    "Custo Unit. C1 (R$)": formatar_moeda_br,
                                    "Preço Praticado (R$)": formatar_moeda_br,
                                    "Faturamento (R$)": formatar_moeda_br,
                                    "Resultado Líquido (R$)": formatar_moeda_br,
                                    "Margem Líquida (%)": lambda x: formatar_pct_br(x, 1),
                                },
                                colunas_esquerda=["Descrição", "Status de Margem"],
                            ),
                            use_container_width=True,
                            hide_index=True,
                            height=280,
                        )

# ------------------------------------------------------------------------------
# ABA 1: CENTRAL DE IMPORTAÇÃO SEGURA E DOWNLOAD DO BANCO DE DADOS
# ------------------------------------------------------------------------------
with aba1:
    st.markdown("### Central de Importação Segura e Sincronização 100% Nuvem")
    st.caption(
        "Importação por data de Estoque, Entradas (NF) e Saídas/Vendas diárias, histórico compacto (1 linha por SKU > 0), "
        "proteção contra estoque retroativo sobrescrever o atual, alerta de linhas repetidas somadas e cópia automática antes de sobrescrever."
    )
    if "msg_sucesso_sync" in st.session_state:
        st.success(st.session_state.pop("msg_sucesso_sync"))
    if "aviso_duplicatas_sync" in st.session_state:
        aviso_dup = st.session_state.pop("aviso_duplicatas_sync")
        if aviso_dup["tipo"] == "warning":
            st.warning(aviso_dup["texto"])
        else:
            st.info(aviso_dup["texto"])
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="glass-card">
                <strong>1. Posição de Estoque (6 colunas)</strong><br><br>
                <span class="pill-tag">Código</span>
                <span class="pill-tag">Saldo Geral</span>
                <span class="pill-tag">Descrição</span>
                <span class="pill-tag">Código do Lote</span>
                <span class="pill-tag">Saldo Lote</span>
                <span class="pill-tag">Validade</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        data_posicao = st.date_input("Data desta posição de estoque:", value=hoje_br())
        arq_estoque = st.file_uploader(
            "Selecionar Estoque (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_estoque",
        )
    with c2:
        st.markdown(
            """
            <div class="glass-card">
                <strong>2. Entradas Faturadas c/ Custo (Fatu416)</strong><br><br>
                <span class="pill-tag">Código</span>
                <span class="pill-tag">Descrição</span>
                <span class="pill-tag">Quantidade</span>
                <span class="pill-tag">Valor (Atualiza Custo!)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        data_entrada = st.date_input(
            "Data das Entradas (NF):",
            value=hoje_br() - timedelta(days=1),
            key="dt_entrada_aba1",
        )
        arq_entradas = st.file_uploader(
            "Selecionar Entradas (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_entradas",
        )
        somar_entradas_mesmo_dia = st.checkbox(
            "➕ Somar ao dia se já houver entrada nesta data",
            value=False,
            key="chk_somar_ent_dia",
            help="Desmarcado (padrão): substitui as entradas desta data. Marcado: soma o novo arquivo às entradas já salvas nesta mesma data.",
        )
    with c3:
        st.markdown(
            """
            <div class="glass-card">
                <strong>3. Saídas / Vendas por Data (3 ou 4 col.)</strong><br><br>
                <span class="pill-tag">Código</span>
                <span class="pill-tag">Descrição</span>
                <span class="pill-tag">Qtd.</span>
                <span class="pill-tag">Valor Proposta (Opc.)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        data_saida = st.date_input(
            "Data das Saídas / Vendas:",
            value=hoje_br() - timedelta(days=1),
            key="dt_saida_aba1",
        )
        arq_saidas = st.file_uploader(
            "Selecionar Saídas (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_saidas",
        )
        somar_saidas_mesmo_dia = st.checkbox(
            "➕ Somar ao dia se já houver saída nesta data",
            value=False,
            key="chk_somar_sai_dia",
            help="Desmarcado (padrão): substitui as saídas desta data. Marcado: soma o novo arquivo às saídas já salvas nesta mesma data.",
        )
    with st.expander("📦 Carga Geral Avulsa de Custos C1 ou Base Inicial Histórica de Vendas (Apoio Opcional)", expanded=False):
        st.caption(
            "💡 Os custos unitários já são atualizados automaticamente sempre que você sobe a planilha de **Entradas Faturadas (Fatu416 com coluna `Valor`)** acima! "
            "Use os campos abaixo apenas quando quiser fazer uma carga geral de custos do catálogo inteiro ou atualizar a Base Inicial de apoio."
        )
        cb0, cb1, cb2 = st.columns([1.4, 0.8, 1.4])
        with cb0:
            arq_custos = st.file_uploader(
                "Planilha Geral de Custos C1 (Código, Descrição, Custo Unitário):",
                type=["xlsx", "xls", "csv"],
                key="up_custos",
            )
        with cb1:
            dias_base_input = st.number_input(
                "Período da base inicial (dias):",
                min_value=1,
                max_value=730,
                value=int(dias_base_atual),
                step=1,
            )
        with cb2:
            arq_base = st.file_uploader(
                "Base Inicial de Vendas (Código, Descrição, Qtd. Vendida):",
                type=["xlsx", "xls", "csv"],
                key="up_base",
            )
    ignorar_trava_catalogo = st.checkbox(
        "🔓 Autorizar mudança estrutural de catálogo / data (ignorar trava de 80% de coincidência ou forçar estoque retroativo como atual)",
        value=False,
        help="Marque apenas se estiver trocando de ERP, importando uma linha de produtos nova ou se quiser forçar que um estoque de data anterior substitua o estoque atual.",
    )
    btn_sincronizar = st.button(
        "🚀 Processar e Sincronizar com Segurança",
        type="primary",
        use_container_width=True,
    )
    st.markdown("---")
    st.markdown("#### 💾 Salvar Cópia do Banco de Dados no Computador & Restauração Rápida")
    st.caption(
        "Baixe quando quiser uma planilha Excel (`.xlsx`) com todas as abas ativas do seu banco de dados "
        "(`estoque_atual`, `entradas_diarias`, `saidas_diarias`, `custos`, `base_inicial`, `ocultos` e `meta`), "
        "ou restaure a cópia automática imediatamente anterior caso tenha importado algum arquivo por engano."
    )
    col_bkp_xlsx, col_bkp_zip = st.columns(2)
    with col_bkp_xlsx:
        if not df_estoque_bruto.empty:
            if st.button("📊 Preparar Planilha do Banco (.xlsx)", use_container_width=True):
                with st.spinner("Montando planilha Excel do banco de dados..."):
                    st.session_state["bkp_db_xlsx_bytes"] = gerar_excel_banco_dados(estado)
                    st.session_state["bkp_db_xlsx_nome"] = (
                        f"Banco_Dados_Esteio_Rural_{hoje_br().strftime('%Y-%m-%d')}.xlsx"
                    )
            if "bkp_db_xlsx_bytes" in st.session_state:
                st.download_button(
                    label="📥 Baixar Planilha do Banco (.xlsx)",
                    data=st.session_state["bkp_db_xlsx_bytes"],
                    file_name=st.session_state.get("bkp_db_xlsx_nome", "Banco_Dados_Esteio_Rural.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
    with col_bkp_zip:
        if not df_estoque_bruto.empty:
            if st.button("📦 Preparar Banco + Histórico 180d (.zip)", use_container_width=True):
                with st.spinner("Compactando planilha do banco (.xlsx) + histórico (.csv)..."):
                    st.session_state["backup_zip_bytes"] = gerar_pacote_backup_leve(estado)
                    st.session_state["backup_zip_nome"] = (
                        f"Backup_Completo_Esteio_{hoje_br().strftime('%Y-%m-%d')}.zip"
                    )
            if "backup_zip_bytes" in st.session_state:
                st.download_button(
                    label="📥 Baixar Pacote Completo (.zip)",
                    data=st.session_state["backup_zip_bytes"],
                    file_name=st.session_state.get("backup_zip_nome", "Backup_Completo_Esteio.zip"),
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )
    with st.expander("⏪ Desfazer Última Importação ou Excluir Data de Movimento (Todas as Abas c/ Backup Automático)", expanded=False):
        st.caption(
            "Restaure a cópia automática imediatamente anterior (`_bkp_*`) de qualquer aba do sistema (Estoque, Entradas, Saídas, Custos, "
            "Histórico, Base Inicial, Ocultos ou Pedidos em Trânsito) ou remova os lançamentos de uma data específica."
        )
        cr1, cr2 = st.columns([2, 1])
        mapa_opcoes_restaurar = {
            "Posição de Estoque (estoque_atual)": ("estoque_atual", df_estoque_bruto),
            "Entradas Diárias (entradas_diarias)": ("entradas_diarias", df_entradas_bruto),
            "Saídas Diárias (saidas_diarias)": ("saidas_diarias", df_saidas_bruto),
            "Planilha de Custos (custos)": ("custos", df_custos),
            "Histórico de Estoque 180d (historico)": ("historico", df_historico_bruto),
            "Base Inicial de Vendas (base_inicial)": ("base_inicial", df_base_vendas),
            "Produtos Ocultos (ocultos)": ("ocultos", df_ocultos),
            "Pedidos em Trânsito / Já Comprei (pedidos_transito)": ("pedidos_transito", df_pedidos_transito),
        }
        with cr1:
            rotulo_aba_rest = st.selectbox(
                "Selecione qual base deseja reverter para a versão imediatamente anterior:",
                options=list(mapa_opcoes_restaurar.keys()),
                key="sel_aba_restaurar_bkp",
            )
            confirmar_restauracao_bkp = st.checkbox(
                "Confirmo que desejo substituir os dados atuais pela cópia automática anterior",
                value=False,
                key="chk_confirmar_restauracao_bkp",
            )
        with cr2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            btn_restaurar_bkp_auto = st.button(
                "⏪ Restaurar Versão Anterior",
                use_container_width=True,
                disabled=not confirmar_restauracao_bkp,
            )
        if btn_restaurar_bkp_auto and confirmar_restauracao_bkp:
            aba_alvo_rest, df_mem_alvo = mapa_opcoes_restaurar[rotulo_aba_rest]
            with st.spinner(f"Restaurando `_bkp_{aba_alvo_rest}` para `{aba_alvo_rest}`..."):
                try:
                    qtd_rest = restaurar_backup_automatico_aba_gsheets(
                        planilha_gsheets,
                        aba_alvo_rest,
                        df_atual_memoria=df_mem_alvo,
                    )
                    st.session_state.pop("bkp_db_xlsx_bytes", None)
                    st.session_state.pop("backup_zip_bytes", None)
                    carregar_estado_completo.clear()
                    calcular_motor_giro_sazonal.clear()
                    st.session_state["msg_sucesso_sync"] = (
                        f"✅ Versão anterior de `{aba_alvo_rest}` restaurada com sucesso ({formatar_num_br(qtd_rest)} registros)!"
                    )
                    st.rerun()
                except Exception as erro_rest:
                    st.error(f"❌ Não foi possível restaurar `{aba_alvo_rest}`: {erro_rest}")
        st.markdown("---")
        st.markdown("##### 🗑️ Excluir Lançamentos de uma Data Específica (Entradas, Saídas ou Histórico)")
        cd1, cd2, cd3 = st.columns([1.4, 1.2, 1.0])
        mapa_abas_data = {
            "Entradas Diárias (entradas_diarias)": ("entradas_diarias", df_entradas_bruto),
            "Saídas Diárias (saidas_diarias)": ("saidas_diarias", df_saidas_bruto),
            "Histórico de Estoque (historico)": ("historico", df_historico_bruto),
        }
        with cd1:
            rotulo_aba_del_dt = st.selectbox(
                "Aba incremental:",
                options=list(mapa_abas_data.keys()),
                key="sel_aba_del_data",
            )
        aba_del_escolhida, df_del_ref = mapa_abas_data[rotulo_aba_del_dt]
        datas_disp_del = (
            sorted([str(d).strip() for d in df_del_ref["data"].unique() if str(d).strip()], reverse=True)
            if (df_del_ref is not None and not df_del_ref.empty and "data" in df_del_ref.columns)
            else []
        )
        with cd2:
            data_del_escolhida = st.selectbox(
                "Data a excluir:",
                options=datas_disp_del if datas_disp_del else ["Nenhuma data gravada"],
                key="sel_dt_del_especifica",
                disabled=not bool(datas_disp_del),
            )
        with cd3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            btn_excluir_dt = st.button(
                "🗑️ Excluir Data",
                use_container_width=True,
                disabled=not bool(datas_disp_del),
            )
        if btn_excluir_dt and datas_disp_del:
            with st.spinner(f"Removendo registros de {data_del_escolhida} em `{aba_del_escolhida}`..."):
                try:
                    qtd_apagadas = remover_datas_aba_incremental_gsheets(
                        planilha_gsheets,
                        aba_del_escolhida,
                        {data_del_escolhida},
                        df_atual_memoria=df_del_ref,
                    )
                    st.session_state.pop("bkp_db_xlsx_bytes", None)
                    st.session_state.pop("backup_zip_bytes", None)
                    carregar_estado_completo.clear()
                    calcular_motor_giro_sazonal.clear()
                    st.session_state["msg_sucesso_sync"] = (
                        f"✅ {formatar_num_br(qtd_apagadas)} linha(s) da data {data_del_escolhida} removida(s) de `{aba_del_escolhida}`!"
                    )
                    st.rerun()
                except Exception as erro_del_dt:
                    st.error(f"❌ Erro ao excluir data: {erro_del_dt}")
    if btn_sincronizar:
        if (
            not any([arq_estoque, arq_entradas, arq_saidas, arq_custos, arq_base])
            and int(dias_base_input) == int(dias_base_atual)
        ):
            st.warning("⚠️ Selecione pelo menos uma planilha para importar ou altere o período da base.")
        else:
            abas_ja_gravadas = []
            with st.spinner("Validando colunas, códigos e saldos antes de sincronizar com o Google Sheets..."):
                try:
                    if arq_estoque is not None and not ignorar_trava_catalogo:
                        if arq_entradas is not None and data_entrada >= data_posicao:
                            raise ValueError(
                                f"Trava de Coerência Temporal: A data das **Entradas ({data_entrada.strftime('%d/%m/%Y')})** "
                                f"não pode ser igual ou posterior à **Posição de Estoque Inicial ({data_posicao.strftime('%d/%m/%Y')})** "
                                f"enviada no mesmo lote. Se as entradas são do dia anterior, selecione **{(data_posicao - timedelta(days=1)).strftime('%d/%m/%Y')}**."
                            )
                        if arq_saidas is not None and data_saida >= data_posicao:
                            raise ValueError(
                                f"Trava de Coerência Temporal: A data das **Saídas ({data_saida.strftime('%d/%m/%Y')})** "
                                f"não pode ser igual ou posterior à **Posição de Estoque Inicial ({data_posicao.strftime('%d/%m/%Y')})** "
                                f"enviada no mesmo lote. Se as saídas são do dia anterior, selecione **{(data_posicao - timedelta(days=1)).strftime('%d/%m/%Y')}**."
                            )
                    data_str = data_posicao.strftime("%Y-%m-%d")
                    mensagens_auditoria_upload = []
                    teve_alerta = False
                    codigos_ref_estoque = (
                        set(df_estoque_bruto["codigo"].unique()) if not df_estoque_bruto.empty else set()
                    )
                    codigos_ref_geral = (
                        codigos_ref_estoque
                        | (set(df_custos["codigo"].unique()) if not df_custos.empty else set())
                        | (set(df_base_vendas["codigo"].unique()) if not df_base_vendas.empty else set())
                    )
                    novo_estoque = None
                    novas_entradas = None
                    novas_saidas = None
                    novos_custos = None
                    nova_base = None
                    atualizar_aba_estoque_atual = True
                    if arq_estoque is not None:
                        novo_estoque, info_dup_est = processar_planilha_estoque(
                            arq_estoque,
                            data_posicao,
                            codigos_ref=codigos_ref_estoque,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        codigos_ref_geral = codigos_ref_geral | set(novo_estoque["codigo"].unique())
                        datas_est_existentes = (
                            sorted([str(d).strip() for d in df_estoque_bruto["data"].unique() if str(d).strip()])
                            if (not df_estoque_bruto.empty and "data" in df_estoque_bruto.columns)
                            else []
                        )
                        maior_data_est_atual = datas_est_existentes[-1] if datas_est_existentes else ""
                        if maior_data_est_atual and data_str < maior_data_est_atual and not ignorar_trava_catalogo:
                            atualizar_aba_estoque_atual = False
                            teve_alerta = True
                            dt_at_fmt = pd.to_datetime(maior_data_est_atual, format="%Y-%m-%d", errors="coerce")
                            str_dt_at = dt_at_fmt.strftime("%d/%m/%Y") if pd.notna(dt_at_fmt) else maior_data_est_atual
                            mensagens_auditoria_upload.append(
                                f"🛡️ **Proteção contra Estoque Retroativo:** O estoque enviado (**{data_posicao.strftime('%d/%m/%Y')}**) "
                                f"é anterior à Posição Atual do sistema (**{str_dt_at}**). Ele foi gravado apenas no **Histórico** "
                                f"para compor o giro, mantendo o `estoque_atual` intacto em **{str_dt_at}**!"
                            )
                        if info_dup_est["qtd_duplicadas"] > 0:
                            teve_alerta = True
                            amostra_txt = ", ".join(info_dup_est["exemplos"])
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Estoque:** {formatar_num_br(info_dup_est['qtd_duplicadas'])} linha(s) duplicada(s) de mesmo "
                                f"(Código + Lote) foram mescladas mantendo a última ocorrência "
                                f"({formatar_num_br(info_dup_est['linhas_lidas'])} lidas → {formatar_num_br(info_dup_est['linhas_finais'])} únicas | "
                                f"Coincidência: {formatar_pct_br(info_dup_est['taxa_coincidencia'])}). "
                                f"Exemplos: {amostra_txt}"
                            )
                        else:
                            mensagens_auditoria_upload.append(
                                f"✔️ **Estoque ({data_posicao.strftime('%d/%m')}):** {formatar_num_br(info_dup_est['linhas_finais'])} linhas verificadas "
                                f"(0 duplicatas | {formatar_pct_br(info_dup_est['taxa_coincidencia'])} de códigos coincidentes)."
                            )
                        if info_dup_est.get("aviso_sem_data"):
                            teve_alerta = True
                            mensagens_auditoria_upload.append(info_dup_est["aviso_sem_data"])
                    df_custos_via_entrada = pd.DataFrame()
                    qtd_custos_att_ent = 0
                    qtd_custos_ins_ent = 0
                    if arq_entradas is not None:
                        novas_entradas, info_ent = processar_planilha_movimento_diario(
                            arquivo=arq_entradas,
                            data_mov=data_entrada,
                            nome_aba="entradas_diarias",
                            col_qtd="qtd_entrada",
                            rotulo_amigavel="Entradas Diárias",
                            codigos_ref=codigos_ref_geral,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        modo_ent_str = "somadas ao dia" if somar_entradas_mesmo_dia else "gravadas"
                        col_val_ent_nome = info_ent.get("coluna_valor_entrada", "")
                        df_ext_c = info_ent.get("df_custos_extraidos", pd.DataFrame())
                        if info_ent.get("soma_valor_entrada", 0.0) > 0 and not df_ext_c.empty:
                            df_custos_via_entrada, qtd_custos_att_ent, qtd_custos_ins_ent = atualizar_custos_via_entradas_df(
                                df_custos, df_ext_c
                            )
                            rot_col_e = f" (coluna '{col_val_ent_nome}')" if col_val_ent_nome else ""
                            str_val_ent = (
                                f" | Valor Total NF{rot_col_e}: {formatar_moeda_br(info_ent['soma_valor_entrada'])} "
                                f"➔ 💰 **{formatar_num_br(qtd_custos_att_ent + qtd_custos_ins_ent)} custo(s) unitário(s) atualizado(s) automaticamente**"
                            )
                        else:
                            str_val_ent = ""
                        mensagens_auditoria_upload.append(
                            f"✔️ **Entradas ({data_entrada.strftime('%d/%m')}):** {formatar_num_br(info_ent['total_itens'])} SKUs {modo_ent_str} "
                            f"(Soma: {formatar_qtd_br(info_ent['soma_qtd'])} un.{str_val_ent})."
                        )
                        if info_ent.get("qtd_codigos_repetidos", 0) > 0:
                            teve_alerta = True
                            ex_rep_ent = ", ".join(info_ent["exemplos_repetidos"])
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Entradas (Linhas Repetidas Somadas):** {formatar_num_br(info_ent['qtd_codigos_repetidos'])} produto(s) "
                                f"apareceram mais de uma vez na planilha ({formatar_num_br(info_ent['qtd_linhas_extras'])} linha(s) extra) e tiveram "
                                f"suas quantidades somadas: {ex_rep_ent}."
                            )
                        if info_ent.get("aviso_sem_data"):
                            teve_alerta = True
                            mensagens_auditoria_upload.append(info_ent["aviso_sem_data"])
                    if arq_saidas is not None:
                        novas_saidas, info_sai = processar_planilha_movimento_diario(
                            arquivo=arq_saidas,
                            data_mov=data_saida,
                            nome_aba="saidas_diarias",
                            col_qtd="qtd_saida",
                            rotulo_amigavel="Saídas Diárias",
                            codigos_ref=codigos_ref_geral,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        modo_sai_str = "somadas ao dia" if somar_saidas_mesmo_dia else "gravadas"
                        col_val_nome = info_sai.get("coluna_valor_venda", "")
                        if info_sai.get("soma_valor_venda", 0.0) > 0:
                            rot_col_fat = f" (coluna '{col_val_nome}')" if col_val_nome else ""
                            str_fat_sai = f" | Faturamento Bruto{rot_col_fat}: {formatar_moeda_br(info_sai['soma_valor_venda'])}"
                        else:
                            str_fat_sai = " | Sem coluna de faturamento"
                        mensagens_auditoria_upload.append(
                            f"✔️ **Saídas ({data_saida.strftime('%d/%m')}):** {formatar_num_br(info_sai['total_itens'])} SKUs {modo_sai_str} "
                            f"(Soma: {formatar_qtd_br(info_sai['soma_qtd'])} un.{str_fat_sai})."
                        )
                        if info_sai.get("qtd_codigos_repetidos", 0) > 0:
                            teve_alerta = True
                            ex_rep_sai = ", ".join(info_sai["exemplos_repetidos"])
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Saídas (Linhas Repetidas Somadas):** {formatar_num_br(info_sai['qtd_codigos_repetidos'])} produto(s) "
                                f"apareceram mais de uma vez na planilha ({formatar_num_br(info_sai['qtd_linhas_extras'])} linha(s) extra) e tiveram "
                                f"suas quantidades somadas: {ex_rep_sai}."
                            )
                        if info_sai.get("aviso_sem_data"):
                            teve_alerta = True
                            mensagens_auditoria_upload.append(info_sai["aviso_sem_data"])
                    if arq_custos is not None:
                        novos_custos, info_cus = processar_planilha_custos(
                            arq_custos,
                            codigos_ref=codigos_ref_geral,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        if info_cus["qtd_duplicadas"] > 0:
                            teve_alerta = True
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Custos:** {formatar_num_br(info_cus['qtd_duplicadas'])} código(s) repetido(s) (mantido o último valor)."
                            )
                        if info_cus["qtd_zerados"] > 0:
                            pct_zero = (info_cus["qtd_zerados"] / max(info_cus["total_itens"], 1)) * 100.0
                            if pct_zero >= 30.0:
                                teve_alerta = True
                            mensagens_auditoria_upload.append(
                                f"ℹ️ **Custos:** {formatar_num_br(info_cus['qtd_positivos'])} com valor positivo e "
                                f"{formatar_num_br(info_cus['qtd_zerados'])} com custo R$ 0,00 ({formatar_pct_br(pct_zero, 0)} | "
                                f"Coincidência: {formatar_pct_br(info_cus['taxa_coincidencia'])})."
                            )
                        else:
                            mensagens_auditoria_upload.append(
                                f"✔️ **Custos:** {formatar_num_br(info_cus['total_itens'])} itens verificados "
                                f"(100% com custo > R$ 0 | Coincidência: {formatar_pct_br(info_cus['taxa_coincidencia'])})."
                            )
                    if arq_base is not None:
                        nova_base, info_base = processar_planilha_base_vendas(
                            arq_base,
                            codigos_ref=codigos_ref_geral,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        msg_base = (
                            f"✔️ **Base Inicial:** {formatar_num_br(info_base['total_itens'])} SKUs consolidados "
                            f"(Soma das vendas: {formatar_num_br(info_base['soma_vendas'])} un. | "
                            f"Coincidência: {formatar_pct_br(info_base['taxa_coincidencia'])})"
                        )
                        if info_base.get("qtd_desc_divergentes", 0) > 0:
                            msg_base += f" — {formatar_num_br(info_base['qtd_desc_divergentes'])} SKU(s) tinham mais de uma descrição e foram unificados pelo código."
                        mensagens_auditoria_upload.append(msg_base)
                    agora_str = agora_br().strftime("%d/%m/%Y %H:%M:%S")
                    if novo_estoque is not None:
                        if atualizar_aba_estoque_atual:
                            salvar_backup_automatico_aba_gsheets(planilha_gsheets, "estoque_atual", df_estoque_bruto)
                            gravar_aba_pequena_gsheets(planilha_gsheets, "estoque_atual", novo_estoque)
                            abas_ja_gravadas.append("estoque_atual")
                        gravar_historico_incremental_gsheets(
                            planilha_gsheets,
                            novo_estoque,
                            data_str,
                            df_atual_memoria=df_historico_bruto,
                            criar_backup=True,
                        )
                        abas_ja_gravadas.append("historico")
                    if novas_entradas is not None:
                        hash_arq_ent = hashlib.sha256(arq_entradas.getvalue()).hexdigest()[:16] if arq_entradas is not None else ""
                        gravar_aba_incremental_por_data_gsheets(
                            planilha_gsheets,
                            "entradas_diarias",
                            novas_entradas,
                            data_entrada.strftime("%Y-%m-%d"),
                            somar_mesma_data=somar_entradas_mesmo_dia,
                            df_atual_memoria=df_entradas_bruto,
                            hash_arquivo=hash_arq_ent,
                            criar_backup=True,
                        )
                        abas_ja_gravadas.append("entradas_diarias")
                        if not df_pedidos_transito.empty:
                            df_ent_comb_temp = pd.concat([df_entradas_bruto, novas_entradas], ignore_index=True)
                            df_trans_pos_nf, cods_desp_sync, _ = depurar_pedidos_transito_auto_despertar(
                                df_pedidos_transito, df_ent_comb_temp
                            )
                            if cods_desp_sync:
                                salvar_backup_automatico_aba_gsheets(
                                    planilha_gsheets, "pedidos_transito", df_pedidos_transito, permitir_vazio=True
                                )
                                gravar_aba_pequena_gsheets(
                                    planilha_gsheets, "pedidos_transito", df_trans_pos_nf, permitir_vazio=True
                                )
                                abas_ja_gravadas.append("pedidos_transito")
                                mensagens_auditoria_upload.append(
                                    f"🔔 **Auto-Despertar ('Já Comprei'):** {formatar_num_br(len(cods_desp_sync))} produto(s) "
                                    f"que estavam ocultos em trânsito chegaram nesta NF de Entrada e voltaram automaticamente ao painel!"
                                )
                    if novas_saidas is not None:
                        hash_arq_sai = hashlib.sha256(arq_saidas.getvalue()).hexdigest()[:16] if arq_saidas is not None else ""
                        gravar_aba_incremental_por_data_gsheets(
                            planilha_gsheets,
                            "saidas_diarias",
                            novas_saidas,
                            data_saida.strftime("%Y-%m-%d"),
                            somar_mesma_data=somar_saidas_mesmo_dia,
                            df_atual_memoria=df_saidas_bruto,
                            hash_arquivo=hash_arq_sai,
                            criar_backup=True,
                        )
                        abas_ja_gravadas.append("saidas_diarias")
                    if novos_custos is not None:
                        if not df_custos_via_entrada.empty:
                            novos_custos, _, _ = atualizar_custos_via_entradas_df(novos_custos, info_ent["df_custos_extraidos"])
                        salvar_backup_automatico_aba_gsheets(planilha_gsheets, "custos", df_custos)
                        gravar_aba_pequena_gsheets(planilha_gsheets, "custos", novos_custos)
                        abas_ja_gravadas.append("custos")
                    elif not df_custos_via_entrada.empty:
                        salvar_backup_automatico_aba_gsheets(planilha_gsheets, "custos", df_custos)
                        gravar_aba_pequena_gsheets(planilha_gsheets, "custos", df_custos_via_entrada)
                        abas_ja_gravadas.append("custos")
                    if nova_base is not None:
                        salvar_backup_automatico_aba_gsheets(planilha_gsheets, "base_inicial", df_base_vendas)
                        gravar_aba_pequena_gsheets(planilha_gsheets, "base_inicial", nova_base)
                        abas_ja_gravadas.append("base_inicial")
                    df_meta_novo = montar_dataframe_meta_completo(
                        dias_base_val=int(dias_base_input),
                        ult_att_val=agora_str,
                        grupos_pref_custom=grupos_pref_custom,
                        grupos_sku_custom=grupos_sku_custom,
                    )
                    gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_novo)
                    abas_ja_gravadas.append("meta")
                    st.session_state.pop("bkp_db_xlsx_bytes", None)
                    st.session_state.pop("backup_zip_bytes", None)
                    carregar_estado_completo.clear()
                    calcular_motor_giro_sazonal.clear()
                    st.session_state["msg_sucesso_sync"] = (
                        f"✅ Dados validados, copiados em segurança (`_bkp_*`) e sincronizados na nuvem em {agora_str}!"
                    )
                    if mensagens_auditoria_upload:
                        st.session_state["aviso_duplicatas_sync"] = {
                            "tipo": "warning" if teve_alerta else "info",
                            "texto": " | ".join(mensagens_auditoria_upload),
                        }
                    st.rerun()
                except Exception as erro_gravacao:
                    if not abas_ja_gravadas:
                        st.error(
                            f"❌ **Importação bloqueada antes de gravar na nuvem (nenhum dado anterior foi alterado):**\n\n"
                            f"{erro_gravacao}"
                        )
                    else:
                        carregar_estado_completo.clear()
                        calcular_motor_giro_sazonal.clear()
                        abas_str = ", ".join(abas_ja_gravadas)
                        st.error(
                            f"⚠️ **Falha parcial durante a gravação na nuvem:** {erro_gravacao}\n\n"
                            f"As seguintes abas já haviam sido atualizadas antes da falha: **`{abas_str}`**. "
                            f"Clique em sincronizar novamente para concluir as demais."
                        )

    with st.expander("🗂️ Gerenciar e Editar Grupos / Departamentos de Produtos (Por Prefixo ou Produto Específico)", expanded=False):
        st.caption(
            "Os grupos do Dashboard Executivo são definidos pelos **2 primeiros dígitos do código do produto no Siagri** (ex: `50` = Veterinária, `70` = Ferragens). "
            "Aqui você pode **renomear ou criar grupos por prefixo** e também **mover produtos específicos** (ex: `903001 - MP MILHO MOIDO 40KG`) para outro grupo!"
        )
        frames_cat_grp = []
        for df_g_src in [df_estoque_bruto, df_entradas_bruto, df_saidas_bruto, df_custos, df_base_vendas]:
            if df_g_src is not None and not df_g_src.empty and "codigo" in df_g_src.columns and "descricao" in df_g_src.columns:
                frames_cat_grp.append(df_g_src[["codigo", "descricao"]])
        if frames_cat_grp:
            df_cat_grp = (
                pd.concat(frames_cat_grp, ignore_index=True)
                .loc[lambda d: d["descricao"] != ""]
                .drop_duplicates(subset=["codigo"], keep="first")
                .reset_index(drop=True)
            )
        else:
            df_cat_grp = pd.DataFrame(columns=["codigo", "descricao"])

        df_cat_grp["prefixo"] = df_cat_grp["codigo"].astype(str).str.strip().str.slice(0, 2)
        contagem_pref = df_cat_grp.groupby("prefixo")["codigo"].count().to_dict() if not df_cat_grp.empty else {}
        exemplo_pref = (
            df_cat_grp.groupby("prefixo")
            .apply(lambda g: f"[{g['codigo'].iloc[0]}] {g['descricao'].iloc[0][:38]}")
            .to_dict()
            if not df_cat_grp.empty
            else {}
        )

        mapa_depto_ativo = construir_mapa_departamentos(grupos_pref_custom)
        todos_prefixos = sorted(set(mapa_depto_ativo.keys()) | set(contagem_pref.keys()))
        linhas_editor_pref = []
        for pref_p in todos_prefixos:
            if not str(pref_p).strip():
                continue
            linhas_editor_pref.append(
                {
                    "Prefixo (2 dígitos)": str(pref_p).strip(),
                    "Nome do Grupo / Departamento": mapa_depto_ativo.get(str(pref_p).strip(), f"Outros ({pref_p})"),
                    "SKUs no Catálogo": int(contagem_pref.get(str(pref_p).strip(), 0)),
                    "Exemplo de Produto no ERP": exemplo_pref.get(str(pref_p).strip(), "-"),
                }
            )
        df_ed_pref_in = pd.DataFrame(linhas_editor_pref)

        st.markdown("##### 1. Editar Nomes dos Grupos por Prefixo (2 Primeiros Dígitos do Código)")
        ed_pref_out = st.data_editor(
            df_ed_pref_in,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key="editor_grupos_prefixo_aba7",
            disabled=["SKUs no Catálogo", "Exemplo de Produto no ERP"],
            column_config={
                "Prefixo (2 dígitos)": st.column_config.TextColumn(
                    "Prefixo (2 dígitos)",
                    help="2 primeiros dígitos do código do produto no Siagri (ex: 50, 70, 26, 90).",
                    width="small",
                ),
                "Nome do Grupo / Departamento": st.column_config.TextColumn(
                    "Nome do Grupo / Departamento",
                    help="Clique duas vezes para editar o nome deste grupo como preferir.",
                    width="medium",
                ),
                "SKUs no Catálogo": st.column_config.NumberColumn(
                    "SKUs no Catálogo",
                    help="Quantidade de produtos cadastrados que começam com este prefixo.",
                    width="small",
                ),
                "Exemplo de Produto no ERP": st.column_config.TextColumn(
                    "Exemplo de Produto no ERP",
                    help="Exemplo de produto deste prefixo para ajudar a identificar grupos 'Outros'.",
                    width="medium",
                ),
            },
        )
        cg_b1, cg_b2 = st.columns([1.6, 1.0])
        with cg_b1:
            if st.button("💾 Salvar Nomes dos Grupos por Prefixo na Nuvem", type="primary", use_container_width=True, key="btn_salvar_grp_pref"):
                with st.spinner("Salvando configuração de grupos no Google Sheets..."):
                    try:
                        novo_pref_dict = {}
                        for _, r_gp in ed_pref_out.iterrows():
                            p_k = str(r_gp.get("Prefixo (2 dígitos)", "")).strip()
                            n_v = str(r_gp.get("Nome do Grupo / Departamento", "")).strip()
                            if p_k and n_v:
                                novo_pref_dict[p_k] = n_v
                        df_meta_grp = montar_dataframe_meta_completo(
                            dias_base_val=int(dias_base_atual),
                            ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                            grupos_pref_custom=novo_pref_dict,
                            grupos_sku_custom=grupos_sku_custom,
                        )
                        gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_grp)
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.session_state["msg_sucesso_sync"] = "✅ Nomes dos grupos atualizados e salvos na nuvem com sucesso!"
                        st.rerun()
                    except Exception as e_gp:
                        st.error(f"❌ Erro ao salvar grupos: {e_gp}")
        with cg_b2:
            if st.button("🔄 Restaurar Nomes Padrão dos Prefixos", use_container_width=True, key="btn_reset_grp_pref"):
                with st.spinner("Restaurando nomes padrão..."):
                    try:
                        df_meta_grp = montar_dataframe_meta_completo(
                            dias_base_val=int(dias_base_atual),
                            ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                            grupos_pref_custom={},
                            grupos_sku_custom=grupos_sku_custom,
                        )
                        gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_grp)
                        carregar_estado_completo.clear()
                        st.session_state["msg_sucesso_sync"] = "✅ Nomes padrão dos prefixos restaurados!"
                        st.rerun()
                    except Exception as e_rst_gp:
                        st.error(f"❌ Erro ao restaurar: {e_rst_gp}")

        st.markdown("---")
        st.markdown("##### 2. Mover Produto(s) Específico(s) para Outro Grupo (Exceções por Código SKU)")
        st.caption(
            "Útil quando um produto foi cadastrado no Siagri com código de outra família (ex: `903001 - MP MILHO MOIDO 40KG` "
            "que começa com `90`, mas você quer que fique em `26 - Nutrição & Matéria-Prima (MP)`)."
        )
        if not df_cat_grp.empty:
            mapa_desc_cat = dict(zip(df_cat_grp["codigo"], df_cat_grp["descricao"]))
            opcoes_sku_mover = [
                f"[{r['codigo']}] {r['descricao']} (Grupo Atual: {identificar_departamento_sku(r['codigo'], grupos_pref_custom, grupos_sku_custom)})"
                for _, r in df_cat_grp.sort_values("descricao").iterrows()
            ]
            cods_sku_ordenados = df_cat_grp.sort_values("descricao")["codigo"].tolist()
            cm_sku1, cm_sku2, cm_sku3 = st.columns([1.8, 1.3, 0.9])
            with cm_sku1:
                indices_skus_sel = st.multiselect(
                    "Selecione um ou mais produtos para mudar de grupo:",
                    options=range(len(opcoes_sku_mover)),
                    format_func=lambda i: opcoes_sku_mover[i],
                    key="sel_skus_mover_grupo",
                )
            grupos_disponiveis_destino = sorted(
                list(
                    set(mapa_depto_ativo.values())
                    | set(grupos_sku_custom.values())
                    | {f"Outros ({p})" for p in todos_prefixos if p not in mapa_depto_ativo}
                )
            )
            with cm_sku2:
                grupo_destino_sel = st.selectbox(
                    "Grupo de Destino:",
                    options=grupos_disponiveis_destino + ["➕ Digitar Novo Nome de Grupo..."],
                    key="sel_grupo_destino_sku",
                )
                if grupo_destino_sel == "➕ Digitar Novo Nome de Grupo...":
                    grupo_destino_final = st.text_input(
                        "Digite o nome do novo grupo:",
                        placeholder="Ex: 99 - Uso Interno / Fábrica",
                        key="txt_novo_grupo_sku_custom",
                    ).strip()
                else:
                    grupo_destino_final = grupo_destino_sel
            with cm_sku3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button(
                    "📌 Fixar no Grupo",
                    type="primary",
                    use_container_width=True,
                    disabled=(not indices_skus_sel or not grupo_destino_final),
                    key="btn_fixar_sku_grupo",
                ):
                    with st.spinner("Salvando exceção de grupo no Google Sheets..."):
                        try:
                            novo_sku_custom = dict(grupos_sku_custom)
                            for idx_sel in indices_skus_sel:
                                cod_alvo_m = normalizar_codigo_sku(cods_sku_ordenados[int(idx_sel)])
                                if cod_alvo_m:
                                    novo_sku_custom[cod_alvo_m] = grupo_destino_final
                            df_meta_sku = montar_dataframe_meta_completo(
                                dias_base_val=int(dias_base_atual),
                                ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                grupos_pref_custom=grupos_pref_custom,
                                grupos_sku_custom=novo_sku_custom,
                            )
                            gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_sku)
                            carregar_estado_completo.clear()
                            st.session_state["msg_sucesso_sync"] = (
                                f"✅ {formatar_num_br(len(indices_skus_sel))} produto(s) movido(s) para o grupo '{grupo_destino_final}'!"
                            )
                            st.rerun()
                        except Exception as e_sk_g:
                            st.error(f"❌ Erro ao mover produto de grupo: {e_sk_g}")

            if grupos_sku_custom:
                st.markdown("###### 📌 Produtos com Grupo Personalizado Ativo")
                linhas_sku_cust = []
                for c_sk, g_sk in sorted(grupos_sku_custom.items()):
                    pref_orig = c_sk[:2] if len(c_sk) >= 2 else c_sk
                    linhas_sku_cust.append(
                        {
                            "remover": False,
                            "Código": c_sk,
                            "Descrição": mapa_desc_cat.get(c_sk, "Produto Cadastrado"),
                            "Grupo Original (Prefixo)": mapa_depto_ativo.get(pref_orig, f"Outros ({pref_orig})"),
                            "Grupo Personalizado Atual": g_sk,
                        }
                    )
                df_sku_cust_in = pd.DataFrame(linhas_sku_cust)
                ed_sku_cust = st.data_editor(
                    df_sku_cust_in,
                    use_container_width=True,
                    hide_index=True,
                    key="editor_excecoes_sku_grupo",
                    disabled=["Código", "Descrição", "Grupo Original (Prefixo)", "Grupo Personalizado Atual"],
                    column_config={
                        "remover": st.column_config.CheckboxColumn(
                            "Voltar ao Padrão?",
                            help="Marque para remover a exceção e devolver este produto ao grupo do seu prefixo original.",
                            default=False,
                            width="small",
                        )
                    },
                )
                sel_rem_sku_g = ed_sku_cust[ed_sku_cust["remover"] == True]
                if not sel_rem_sku_g.empty:
                    if st.button(
                        f"↩️ Devolver {formatar_num_br(len(sel_rem_sku_g))} Produto(s) Marcado(s) ao Grupo Original",
                        key="btn_rem_excecao_sku_grp",
                    ):
                        with st.spinner("Atualizando grupos no Google Sheets..."):
                            try:
                                novo_sku_custom = {
                                    k: v
                                    for k, v in grupos_sku_custom.items()
                                    if k not in set(sel_rem_sku_g["Código"].unique())
                                }
                                df_meta_sku = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_atual),
                                    ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=novo_sku_custom,
                                )
                                gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_sku)
                                carregar_estado_completo.clear()
                                st.session_state["msg_sucesso_sync"] = "✅ Produto(s) devolvido(s) ao grupo original!"
                                st.rerun()
                            except Exception as e_rm_sk:
                                st.error(f"❌ Erro ao remover exceção: {e_rm_sk}")

    r1, r2, r3, r4 = st.columns(4)
    qtd_skus_visiveis = df_estoque["codigo"].nunique() if (not df_estoque.empty and "codigo" in df_estoque.columns) else 0
    qtd_datas_hist = df_historico_bruto["data"].nunique() if (not df_historico_bruto.empty and "data" in df_historico_bruto.columns) else 0
    qtd_datas_ent = df_entradas_bruto["data"].nunique() if (not df_entradas_bruto.empty and "data" in df_entradas_bruto.columns) else 0
    qtd_datas_sai = df_saidas_bruto["data"].nunique() if (not df_saidas_bruto.empty and "data" in df_saidas_bruto.columns) else 0
    qtd_custos = len(df_custos) if not df_custos.empty else 0
    r1.metric("Produtos Ativos com Saldo/Catálogo", f"{formatar_num_br(qtd_skus_visiveis)} (Ocultos: {formatar_num_br(len(codigos_ocultos))})")
    r2.metric(
        "Histórico 180d (Est. / Ent. / Saí.)",
        f"{formatar_num_br(qtd_datas_hist)}d / {formatar_num_br(qtd_datas_ent)}d / {formatar_num_br(qtd_datas_sai)}d",
    )
    r3.metric("Itens com Custo Cadastrado", f"{formatar_num_br(qtd_custos)}")
    r4.metric("Última Sincronização", estado.get("ultima_atualizacao", "-"))

# ------------------------------------------------------------------------------
# ABA 2: SUGESTÃO DE COMPRAS, RADAR DE RUPTURA, PICO SAZONAL & COTAÇÃO
# ------------------------------------------------------------------------------
with aba2:
    st.markdown("### 🛒 Sugestão de Compras, Radar de Ruptura, Pico Sazonal & Cotação")
    st.caption(
        "Cruza automaticamente Estoque + Entradas (NF) + Saídas/Vendas por data, destaca Ruptura Iminente e Pico Sazonal, "
        "permite marcar produtos como **'Já Comprei'** (ocultando-os por 15 dias com **Auto-Despertar** assim que entrarem na NF) "
        "e exporta a planilha de cotação com fórmulas vivas."
    )
    if "msg_transito_aba2" in st.session_state:
        st.success(st.session_state.pop("msg_transito_aba2"))
    desp_rec = estado.get("despertados_nf_recente", [])
    if desp_rec:
        st.info(
            f"🔔 **Auto-Despertar Automático:** **{formatar_num_br(len(desp_rec))} produto(s)** que estavam ocultos em "
            f"*'Já Comprei'* apareceram em planilha recente de **Entradas (NF)** e voltaram automaticamente ao monitoramento!"
        )

    with st.expander("📋 Importar Planilha de Produtos para Cotação Direcionada (Opcional)", expanded=False):
        arq_lista_cotacao = st.file_uploader(
            "Subir planilha com Código e Nome dos produtos (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_lista_cotacao",
        )
        if arq_lista_cotacao is not None:
            st.success(
                "✅ Planilha de cotação ativa! Todos os produtos enviados abaixo serão mantidos na tabela e no Excel gerado (inclusive itens com sugestão 0)."
            )
    p1, p2, p3, p4, p5 = st.columns([1.0, 1.0, 1.0, 1.1, 2.0])
    janela_dias = p1.selectbox(
        "Janela de Giro (dias):",
        options=[15, 30, 45, 60, 90, 120, 180],
        index=5,
        help="Escolha 120 ou 180 dias para negociações de longo prazo com fornecedores.",
    )
    cobertura_desejada = p2.number_input("Cobertura Alvo (dias):", min_value=5, max_value=180, value=120)
    lead_time = p3.number_input("Entrega / Lead (dias):", min_value=0, max_value=90, value=10)
    fator_sazonal = p4.slider("Ajuste Sazonal (%):", min_value=-50, max_value=200, value=0, step=5)
    filtro_busca = p5.text_input(
        "🔍 Fornecedor / Linha / Produto (use vírgula p/ vários):",
        placeholder="Ex: tigre  |  roda d'água, gaxeta  |  joelho 25",
        help="Busca inteligente: ignora acentos/apóstrofos (encontra RODA D'AGUA, RODA DAGUA e RODA D AGUA), aceita palavras fora de ordem e múltiplos termos separados por vírgula.",
    )
    c_op1, c_op2, c_op3, c_op4, c_op5 = st.columns(5)
    with c_op1:
        incluir_zerados_com_giro = st.checkbox(
            "Incluir Saldo = 0 c/ giro",
            value=False,
        )
    with c_op2:
        usar_sugestao_reforcada_pico = st.checkbox(
            "⚡ Sugestão Reforçada (Pico)",
            value=True,
            help="Quando um produto sofre uma queda brusca em 1 dia (ex: D KELLBYOL caindo de 41 para 11), sugere recompor o lote consumido + cobertura regular.",
        )
    with c_op3:
        filtrar_apenas_ruptura = st.checkbox(
            "🔥 Apenas Ruptura Iminente",
            value=False,
            help="Mostra somente produtos com giro ativo cujo estoque atual acaba antes ou durante o prazo de entrega do fornecedor (Autonomia ≤ Entrega).",
        )
    with c_op4:
        filtrar_apenas_picos = st.checkbox(
            "🚨 Apenas Saídas de Pico",
            value=False,
            help="Filtra somente os produtos que tiveram queda brusca recente para você conferir se foi venda real ou ajuste no Siagri.",
        )
    with c_op5:
        mostrar_comprados_transito = st.checkbox(
            f"🚚 Mostrar 'Já Comprei' ({formatar_num_br(len(codigos_em_transito))})",
            value=False,
            help="Por padrão, produtos marcados como 'Já Comprei' ficam ocultos por 15 dias (ou até aparecerem na planilha de Entradas NF). Marque para exibi-los na tabela.",
        )

    mapa_silenciar_ate = (
        dict(zip(df_pedidos_transito["codigo"], df_pedidos_transito["silenciar_ate"]))
        if not df_pedidos_transito.empty
        else {}
    )

    df_est_fonte = df_estoque_bruto if arq_lista_cotacao is not None else df_estoque
    df_hist_fonte = df_historico_bruto if arq_lista_cotacao is not None else df_historico
    df_ent_fonte = df_entradas_bruto if arq_lista_cotacao is not None else df_entradas
    df_sai_fonte = df_saidas_bruto if arq_lista_cotacao is not None else df_saidas
    df_base_fonte = df_base_vendas if arq_lista_cotacao is not None else df_base_vendas_rel
    df_custos_fonte = df_custos if arq_lista_cotacao is not None else df_custos_rel
    if df_est_fonte.empty and df_base_fonte.empty and arq_lista_cotacao is None:
        st.info("Importe a Planilha de Estoque na Aba 7 (Importação & Backup) para calcular o giro e as sugestões de compra.")
    else:
        df_base_giro, dias_hist_janela, peso_hist = calcular_motor_giro_sazonal(
            df_estoque=df_est_fonte,
            df_historico=df_hist_fonte,
            df_base_vendas=df_base_fonte,
            df_custos=df_custos_fonte,
            dias_base_atual=dias_base_atual,
            janela_dias=int(janela_dias),
            incluir_sem_estoque=True if arq_lista_cotacao is not None else incluir_zerados_com_giro,
            df_entradas=df_ent_fonte,
            df_saidas=df_sai_fonte,
        )
        df_calc = df_base_giro.copy()
        codigos_nao_encontrados_lista = []
        cods_conhecidos_erp = (
            set(df_estoque_bruto["codigo"].unique())
            | set(df_entradas_bruto["codigo"].unique())
            | set(df_saidas_bruto["codigo"].unique())
            | set(df_custos["codigo"].unique())
            | set(df_base_vendas["codigo"].unique())
            | set(df_historico_bruto["codigo"].unique())
        )
        if arq_lista_cotacao is not None:
            try:
                df_lista = ler_lista_produtos_cotacao(arq_lista_cotacao)
                mapa_sem_zero = {}
                for c_erp in cods_conhecidos_erp:
                    chave_sz = normalizar_codigo_sku(c_erp)
                    if chave_sz not in mapa_sem_zero:
                        mapa_sem_zero[chave_sz] = c_erp
                df_lista["codigo"] = df_lista["codigo_lista"].apply(
                    lambda c: c if c in cods_conhecidos_erp else mapa_sem_zero.get(normalizar_codigo_sku(c), c)
                )
                df_lista = df_lista.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
                mask_inexistente = ~df_lista["codigo"].isin(cods_conhecidos_erp)
                if mask_inexistente.any():
                    codigos_nao_encontrados_lista = df_lista.loc[mask_inexistente, "codigo_lista"].tolist()
                df_merged = df_lista.merge(df_calc, on="codigo", how="left")
                df_merged["descricao"] = df_merged["descricao"].fillna("")
                df_merged["descricao"] = df_merged["descricao"].where(
                    df_merged["descricao"] != "", df_merged["descricao_lista"]
                )
                for col_num_fill in [
                    "saldo_atual", "giro_base", "giro_historico", "giro_historico_sem_pico",
                    "giro_ponderado", "giro_ponderado_sem_pico", "saida_ult_dia",
                    "queda_pico_recente", "saldo_antes_pico"
                ]:
                    if col_num_fill in df_merged.columns:
                        df_merged[col_num_fill] = df_merged[col_num_fill].fillna(0.0)
                df_merged["data_ult_dia"] = df_merged["data_ult_dia"].fillna("-")
                df_merged["data_pico_recente"] = df_merged["data_pico_recente"].fillna("-")
                df_merged["alerta_nf_nao_refletida"] = df_merged["alerta_nf_nao_refletida"].fillna("")
                df_calc = df_merged.drop(columns=["codigo_lista", "descricao_lista"])
            except Exception as e:
                st.error(f"❌ Erro ao processar a lista de produtos para cotação: {e}")
        if codigos_nao_encontrados_lista:
            lista_str = ", ".join(f"`{c}`" for c in codigos_nao_encontrados_lista[:20])
            sufixo = " ..." if len(codigos_nao_encontrados_lista) > 20 else ""
            st.warning(
                f"⚠️ **Atenção:** **{formatar_num_br(len(codigos_nao_encontrados_lista))} código(s)** da planilha enviada "
                f"**não foram encontrados** em nenhuma base do ERP (Estoque, Custos ou Vendas) e aparecem "
                f"com saldo 0: {lista_str}{sufixo}. Verifique se os códigos estão corretos antes de fechar o pedido."
            )

        # Oculta produtos marcados como 'Já Comprei / Em Trânsito' (15 dias ou até NF de Entrada)
        if codigos_em_transito and (not mostrar_comprados_transito) and (arq_lista_cotacao is None):
            df_calc = df_calc[~df_calc["codigo"].isin(codigos_em_transito)].copy()

        fator_mult = 1.0 + (fator_sazonal / 100.0)
        df_calc["giro_diario"] = (df_calc["giro_ponderado"] * fator_mult).clip(lower=0.0)
        df_calc["giro_diario_sem_pico"] = (df_calc["giro_ponderado_sem_pico"] * fator_mult).clip(lower=0.0)
        if not df_custos.empty:
            df_calc = df_calc.merge(
                df_custos[["codigo", "custo_unitario"]], on="codigo", how="left"
            )
            df_calc["custo_unitario"] = df_calc["custo_unitario"].fillna(0.0)
        else:
            df_calc["custo_unitario"] = 0.0
        mapa_venc_60d = {}
        if not df_est_fonte.empty:
            df_lotes_pos = df_est_fonte[df_est_fonte["saldo_lote"] > 0].copy()
            if not df_lotes_pos.empty:
                df_lotes_pos["dt_val"] = converter_datas_deterministico(df_lotes_pos["validade"])
                dias_venc = (df_lotes_pos["dt_val"] - pd.Timestamp(hoje_br())).dt.days
                df_curto = df_lotes_pos[dias_venc.notna() & (dias_venc <= 60)]
                if not df_curto.empty:
                    mapa_venc_60d = df_curto.groupby("codigo")["saldo_lote"].sum().to_dict()
        df_calc["vencendo_60d"] = df_calc["codigo"].map(mapa_venc_60d).fillna(0.0)
        dias_totais_nec = float(cobertura_desejada + lead_time)
        df_calc["estoque_ideal"] = df_calc["giro_diario"] * dias_totais_nec
        df_calc["estoque_ideal_sem_pico"] = df_calc["giro_diario_sem_pico"] * dias_totais_nec
        necessidade_padrao = (df_calc["estoque_ideal"] - df_calc["saldo_atual"]).clip(lower=0.0)
        df_calc["sugestao_padrao"] = necessidade_padrao.apply(
            lambda x: float(math.ceil(x - 1e-9)) if x > 0 else 0.0
        )
        df_calc["autonomia_dias"] = (
            (df_calc["saldo_atual"].clip(lower=0.0) / df_calc["giro_diario"].replace(0.0, float("nan")))
            .fillna(999.0)
            .round(1)
        )

        def _avaliar_ruptura_pico_e_sugestao(r):
            cod = str(r["codigo"])
            prefixo_tr = ""
            if cod in mapa_silenciar_ate:
                dt_s_fmt = pd.to_datetime(mapa_silenciar_ate[cod], format="%Y-%m-%d", errors="coerce")
                str_ate = dt_s_fmt.strftime("%d/%m") if pd.notna(dt_s_fmt) else str(mapa_silenciar_ate[cod])
                prefixo_tr = f"🚚 JÁ COMPRADO (Até {str_ate}) | "
            if cod not in cods_conhecidos_erp:
                return False, False, prefixo_tr + "⚠️ Não Cadastrado no ERP", 0.0
            queda_pico = float(r.get("queda_pico_recente", 0.0))
            saldo_antes = float(r.get("saldo_antes_pico", 0.0))
            saldo_at = float(r.get("saldo_atual", 0.0))
            giro_d = float(r.get("giro_diario", 0.0))
            giro_sem_p = float(r.get("giro_diario_sem_pico", 0.0))
            est_ideal = float(r.get("estoque_ideal", 0.0))
            est_ideal_sem_p = float(r.get("estoque_ideal_sem_pico", 0.0))
            sug_padrao = float(r.get("sugestao_padrao", 0.0))
            autonomia = float(r.get("autonomia_dias", 999.0))
            saida_ult = float(r.get("saida_ult_dia", 0.0))
            dt_ult = str(r.get("data_ult_dia", "-"))
            dt_pico = str(r.get("data_pico_recente", "-"))
            alerta_nf = str(r.get("alerta_nf_nao_refletida", "")).strip()
            eh_ruptura = (giro_d > 0.0) and (autonomia <= float(lead_time))
            nao_reposto = (saldo_antes <= 0.0) or (saldo_at < (saldo_antes * 0.85))
            proporcao_estoque = (queda_pico / saldo_antes) if saldo_antes > 0 else 1.0
            eh_pico = (
                queda_pico >= 3.0
                and nao_reposto
                and (
                    (queda_pico >= 5.0 and proporcao_estoque >= 0.35)
                    or (queda_pico >= 5.0 and giro_sem_p > 0 and queda_pico >= (giro_sem_p * 3.0))
                    or (queda_pico > sug_padrao and queda_pico > saldo_at)
                )
            )
            sug_ref = sug_padrao
            if eh_pico:
                reserva_min = max(est_ideal_sem_p, giro_d * float(lead_time))
                teto_recompor_anterior = (
                    min(saldo_antes, queda_pico + est_ideal)
                    if saldo_antes > 0
                    else (queda_pico + reserva_min)
                )
                alvo_reforcado = max(est_ideal, queda_pico + reserva_min, teto_recompor_anterior)
                nec_ref = max(0.0, alvo_reforcado - saldo_at)
                sug_ref = float(math.ceil(nec_ref - 1e-9)) if nec_ref > 0 else 0.0
                sug_ref = max(sug_ref, sug_padrao)
            if eh_pico and eh_ruptura:
                aut_str = "0d" if saldo_at <= 0 else f"{formatar_num_br(autonomia, 1)}d"
                txt_alerta = (
                    prefixo_tr + f"🔥 Rupt. ({aut_str}) + 🚨 Pico -{formatar_qtd_br(queda_pico)} ({dt_pico})"
                )
                return True, True, txt_alerta, sug_ref
            if eh_pico:
                txt_alerta = (
                    prefixo_tr + f"🚨 Pico -{formatar_qtd_br(queda_pico)} ({dt_pico}) | "
                    f"Pad.: {formatar_qtd_br(sug_padrao)}"
                )
                return True, False, txt_alerta, sug_ref
            if eh_ruptura:
                if saldo_at <= 0:
                    txt_alerta = prefixo_tr + "🔥 Zerado c/ Giro"
                else:
                    txt_alerta = prefixo_tr + f"🔥 Dura {formatar_num_br(autonomia, 1)}d (≤{lead_time}d)"
                return False, True, txt_alerta, sug_ref
            if alerta_nf:
                return False, False, prefixo_tr + alerta_nf, sug_padrao
            if saida_ult > 0:
                return False, False, prefixo_tr + f"✔️ -{formatar_qtd_br(saida_ult)} un. ({dt_ult})", sug_padrao
            return False, False, prefixo_tr + "➖ Sem saída", sug_padrao

        if not df_calc.empty:
            res_analise = df_calc.apply(_avaliar_ruptura_pico_e_sugestao, axis=1)
            df_calc["tem_pico"] = [x[0] for x in res_analise]
            df_calc["tem_ruptura"] = [x[1] for x in res_analise]
            df_calc["alerta_saida_recente"] = [x[2] for x in res_analise]
            df_calc["sugestao_reforcada"] = [x[3] for x in res_analise]
        else:
            df_calc["tem_pico"] = pd.Series(dtype=bool)
            df_calc["tem_ruptura"] = pd.Series(dtype=bool)
            df_calc["alerta_saida_recente"] = pd.Series(dtype=str)
            df_calc["sugestao_reforcada"] = pd.Series(dtype=float)

        if usar_sugestao_reforcada_pico:
            df_calc["sugestao_compra"] = df_calc["sugestao_reforcada"]
        else:
            df_calc["sugestao_compra"] = df_calc["sugestao_padrao"]

        def _canonizar_texto_busca(txt: str) -> str:
            s = unicodedata.normalize("NFKD", str(txt)).encode("ASCII", "ignore").decode("utf-8").lower()
            s = re.sub(r"\bd[\s'\-]*agua\b", "dagua", s)
            s = re.sub(r"[^a-z0-9]+", " ", s).strip()
            return s

        if filtro_busca and filtro_busca.strip() and not df_calc.empty:
            grupos_busca = [
                _canonizar_texto_busca(g)
                for g in re.split(r"[;,]+", filtro_busca)
                if _canonizar_texto_busca(g)
            ]
            if grupos_busca:
                serie_alvo = (df_calc["codigo"].astype(str) + " " + df_calc["descricao"].astype(str)).map(
                    _canonizar_texto_busca
                )
                mask_total = pd.Series(False, index=df_calc.index)
                for grp in grupos_busca:
                    palavras = grp.split()
                    mask_grp = pd.Series(True, index=df_calc.index)
                    for pal in palavras:
                        mask_grp = mask_grp & serie_alvo.str.contains(re.escape(pal), na=False)
                    mask_total = mask_total | mask_grp
                df_calc = df_calc[mask_total].copy()
        qtd_total_ruptura = int(df_calc["tem_ruptura"].sum()) if not df_calc.empty else 0
        qtd_total_picos = int(df_calc["tem_pico"].sum()) if not df_calc.empty else 0
        qtd_nf_pendente = int((df_calc["alerta_nf_nao_refletida"] != "").sum()) if not df_calc.empty else 0
        if qtd_total_ruptura > 0 or qtd_total_picos > 0 or qtd_nf_pendente > 0 or len(codigos_em_transito) > 0:
            partes_aviso = []
            if qtd_total_ruptura > 0:
                partes_aviso.append(
                    f"🔥 **{formatar_num_br(qtd_total_ruptura)} produto(s) em Ruptura Iminente** (estoque acaba antes dos {lead_time} dias de entrega)"
                )
            if qtd_total_picos > 0:
                partes_aviso.append(
                    f"🚨 **{formatar_num_br(qtd_total_picos)} produto(s) com Saída Fora do Padrão (Pico)**"
                )
            if len(codigos_em_transito) > 0:
                partes_aviso.append(
                    f"🚚 **{formatar_num_br(len(codigos_em_transito))} produto(s) oculto(s) em 'Já Comprei'** (15d ou até NF)"
                )
            if qtd_nf_pendente > 0:
                partes_aviso.append(
                    f"⏳ **{formatar_num_br(qtd_nf_pendente)} produto(s) com NF de Entrada sem reflexo no saldo seguinte**"
                )
            st.info(" | ".join(partes_aviso))
        if filtrar_apenas_ruptura:
            df_calc = df_calc[df_calc["tem_ruptura"] == True].copy()
        if filtrar_apenas_picos:
            df_calc = df_calc[df_calc["tem_pico"] == True].copy()
        if arq_lista_cotacao is None and not df_calc.empty:
            df_calc["_inv_ord"] = df_calc["sugestao_compra"] * df_calc["custo_unitario"]
            df_compras = df_calc.sort_values(
                ["tem_ruptura", "tem_pico", "_inv_ord", "descricao"],
                ascending=[False, False, False, True],
            ).drop(columns=["_inv_ord"])
        else:
            df_compras = df_calc.copy()
        df_compras = df_compras.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
        total_item_s = (df_compras["sugestao_compra"] * df_compras["custo_unitario"]).round(2)
        df_completo_13_cols = pd.DataFrame(
            {
                "Código": df_compras["codigo"].values,
                "Descrição": df_compras["descricao"].values,
                "Saída Recente & Alerta": df_compras["alerta_saida_recente"].values,
                "Saldo Atual": df_compras["saldo_atual"].values,
                "Vencido ou vencendo (≤60d)": df_compras["vencendo_60d"].values,
                "Giro Médio/Dia": df_compras["giro_diario"].values,
                "Autonomia (Dias)": df_compras["autonomia_dias"].values,
                "Sugestão Sistema": df_compras["sugestao_compra"].values,
                "Qtd. a Comprar": df_compras["sugestao_compra"].values,
                "Último Custo ERP (R$)": df_compras["custo_unitario"].values,
                "Custo Atual / Cotado (R$)": 0.0,
                "Variação Custo (%)": 0.0,
                "Total do Item (R$)": total_item_s.values,
            }
        )
        m1, m2, m3, m4 = st.columns(4)
        itens_com_pedido = int((df_compras["sugestao_compra"] > 0).sum())
        orcamento_total = float(total_item_s.sum())
        m1.metric(
            "Produtos Listados",
            f"{formatar_num_br(len(df_completo_13_cols))} SKUs (Sugeridos: {formatar_num_br(itens_com_pedido)})",
        )
        m2.metric("Orçamento Estimado (Último Custo)", formatar_moeda_br(orcamento_total))
        m3.metric(
            "🔥 Ruptura / 🚨 Pico",
            f"{formatar_num_br(qtd_total_ruptura)} / {formatar_num_br(qtd_total_picos)}",
            help="Quantidade de itens listados em Ruptura Iminente e Saída de Pico.",
        )
        m4.metric(
            "🚚 Em Trânsito ('Já Comprei')",
            f"{formatar_num_br(len(codigos_em_transito))} SKUs (15d / Auto-NF)",
            help=f"Produtos ocultos temporariamente por {DIAS_PADRAO_SONECA_COMPRA} dias ou até entrarem na NF.",
        )

        col_sel_tudo_c, col_dica_c = st.columns([1.4, 2.6])
        with col_sel_tudo_c:
            marcar_todos_compra_aba2 = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_compras))} itens listados abaixo como 'Já Comprei'",
                value=False,
                key="chk_todos_ja_comprei_aba2",
            )
        with col_dica_c:
            st.caption(
                "💡 **Dica rápida:** Clique na caixinha **'🛒 Já Comprei?'** (1ª coluna da tabela) nos produtos que você acabou de pedir ao fornecedor "
                "e confirme no botão abaixo da tabela para ocultá-los por **15 dias** (eles voltam sozinhos assim que entrarem na NF)."
            )

        df_editor_aba2 = pd.DataFrame(
            {
                "ja_comprei": [bool(marcar_todos_compra_aba2)] * len(df_compras),
                "Cód.": df_compras["codigo"].values,
                "Descrição": df_compras["descricao"].values,
                "Alerta & Saída": df_compras["alerta_saida_recente"].values,
                "Saldo": [formatar_qtd_br(v) for v in df_compras["saldo_atual"].values],
                "Venc. ≤60d": [formatar_qtd_br(v) for v in df_compras["vencendo_60d"].values],
                "Giro/Dia": [
                    formatar_num_br(v, 3) if (pd.notna(v) and 0 < float(v) < 0.05) else formatar_num_br(v, 2)
                    for v in df_compras["giro_diario"].values
                ],
                "Auton.": [
                    "S/ Giro" if (pd.notna(v) and float(v) >= 999.0) else f"{formatar_num_br(v, 1)}d"
                    for v in df_compras["autonomia_dias"].values
                ],
                "Sugestão": [formatar_qtd_br(v) for v in df_compras["sugestao_compra"].values],
                "Custo Un.": [formatar_moeda_br(v) for v in df_compras["custo_unitario"].values],
                "Total (R$)": [formatar_moeda_br(v) for v in total_item_s.values],
            }
        )

        ed_compras_aba2 = st.data_editor(
            df_editor_aba2,
            use_container_width=True,
            hide_index=True,
            height=450,
            key="editor_ja_comprei_aba2",
            disabled=[
                "Cód.",
                "Descrição",
                "Alerta & Saída",
                "Saldo",
                "Venc. ≤60d",
                "Giro/Dia",
                "Auton.",
                "Sugestão",
                "Custo Un.",
                "Total (R$)",
            ],
            column_config={
                "ja_comprei": st.column_config.CheckboxColumn(
                    "🛒",
                    help="Já Comprei? — Marque este produto para ocultá-lo da lista e dos alertas por 15 dias (ou até a NF de Entrada chegar).",
                    default=False,
                    width="small",
                ),
                "Cód.": st.column_config.TextColumn(
                    "Cód.",
                    help="Código do Produto (SKU no ERP Siagri).",
                    width="small",
                ),
                "Descrição": st.column_config.TextColumn(
                    "Descrição",
                    help="Descrição Completa do Produto no ERP.",
                    width="medium",
                ),
                "Alerta & Saída": st.column_config.TextColumn(
                    "Alerta & Saída",
                    help="Diagnóstico de Ruptura Iminente (estoque acaba antes do prazo de entrega), Pico Sazonal de Saída ou última venda registrada.",
                    width="medium",
                ),
                "Saldo": st.column_config.TextColumn(
                    "Saldo",
                    help="Saldo Geral Atual em Estoque Físico.",
                    width="small",
                ),
                "Venc. ≤60d": st.column_config.TextColumn(
                    "Venc. ≤60d",
                    help="Quantidade vencida ou vencendo nos próximos 60 dias (Radar FEFO).",
                    width="small",
                ),
                "Giro/Dia": st.column_config.TextColumn(
                    "Giro/Dia",
                    help="Giro Médio Diário Ponderado (unidades vendidas ou consumidas por dia).",
                    width="small",
                ),
                "Auton.": st.column_config.TextColumn(
                    "Auton.",
                    help="Autonomia Estimada do Estoque Atual em Dias (Saldo Atual ÷ Giro Médio/Dia).",
                    width="small",
                ),
                "Sugestão": st.column_config.TextColumn(
                    "Sugestão",
                    help="Sugestão Inteligente de Compra em unidades para cobrir (Cobertura Alvo + Prazo de Entrega).",
                    width="small",
                ),
                "Custo Un.": st.column_config.TextColumn(
                    "Custo Un.",
                    help="Último Custo Unitário C1 (R$) cadastrado ou atualizado automaticamente via NF de Entrada (Fatu416).",
                    width="small",
                ),
                "Total (R$)": st.column_config.TextColumn(
                    "Total (R$)",
                    help="Orçamento Total Estimado para o Item (Sugestão de Compra × Último Custo Unitário).",
                    width="small",
                ),
            },
        )

        indices_marcados_compra = ed_compras_aba2.index[ed_compras_aba2["ja_comprei"] == True].tolist()
        qtd_marcados_compra = len(indices_marcados_compra)

        b_act_col1, b_act_col2 = st.columns([1.3, 1.3])
        with b_act_col1:
            if st.button(
                f"🚚 Ocultar Marcados como 'Já Comprei' por 15 dias ({formatar_num_br(qtd_marcados_compra)} selecionado(s))",
                type="primary",
                use_container_width=True,
                disabled=(qtd_marcados_compra == 0),
            ):
                with st.spinner("Registrando pedido em trânsito no Google Sheets..."):
                    try:
                        hoje_str_c = hoje_br().strftime("%Y-%m-%d")
                        sil_ate_str_c = (hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
                        df_sel_c = df_compras.iloc[indices_marcados_compra].copy()
                        novos_transito = pd.DataFrame(
                            {
                                "codigo": df_sel_c["codigo"].values,
                                "descricao": df_sel_c["descricao"].values,
                                "qtd_comprada": df_sel_c["sugestao_compra"].values,
                                "data_compra": hoje_str_c,
                                "silenciar_ate": sil_ate_str_c,
                            }
                        )
                        df_trans_atualizado = (
                            pd.concat([df_pedidos_transito, novos_transito], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
                        )
                        salvar_backup_automatico_aba_gsheets(
                            planilha_gsheets, "pedidos_transito", df_pedidos_transito, permitir_vazio=True
                        )
                        gravar_aba_pequena_gsheets(
                            planilha_gsheets, "pedidos_transito", df_trans_atualizado, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.session_state["msg_transito_aba2"] = (
                            f"✅ {formatar_num_br(qtd_marcados_compra)} produto(s) marcado(s) como 'Já Comprei'! "
                            f"Eles ficarão ocultos por {DIAS_PADRAO_SONECA_COMPRA} dias (até {(hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime('%d/%m/%Y')}) "
                            f"ou despertarão automaticamente assim que aparecerem na planilha de Entradas (NF)."
                        )
                        st.rerun()
                    except Exception as e_tr:
                        st.error(f"❌ Erro ao salvar produtos em trânsito: {e_tr}")

        with b_act_col2:
            if not df_completo_13_cols.empty:
                st.download_button(
                    label="📥 Baixar Planilha de Sugestão & Cotação (.xlsx com 13 Colunas e Fórmulas Vivas)",
                    data=gerar_excel_com_formulas_cotacao(df_completo_13_cols),
                    file_name=f"Cotacao_Compras_Esteio_{janela_dias}d_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

    with st.expander(
        f"🚚 Gerenciar Produtos Marcados como 'Já Comprei / Em Trânsito' ({formatar_num_br(len(df_pedidos_transito))} ativo(s) — 15 dias ou até NF)",
        expanded=False,
    ):
        if df_pedidos_transito.empty:
            st.success("Nenhum produto está silenciado como 'Já Comprei' no momento.")
        else:
            st.caption(
                "Estes produtos foram marcados como comprados e estão temporariamente silenciados na Aba 2. "
                "Eles voltam sozinhos após 15 dias ou assim que o código entrar numa planilha de Entradas (NF) na Aba 7. "
                "Se marcou algum por engano, selecione abaixo para devolvê-lo imediatamente:"
            )
            df_tr_view = df_pedidos_transito.copy()
            hoje_ts_tr = pd.Timestamp(hoje_br())
            dt_sil_tr = converter_datas_deterministico(df_tr_view["silenciar_ate"])
            dt_comp_tr = converter_datas_deterministico(df_tr_view["data_compra"])
            dias_rest_tr = (dt_sil_tr - hoje_ts_tr).dt.days.fillna(0).astype(int)
            df_tr_view[" data_compra_fmt"] = dt_comp_tr.dt.strftime("%d/%m/%Y").fillna(df_tr_view["data_compra"])
            df_tr_view["silenciar_ate_fmt"] = dt_sil_tr.dt.strftime("%d/%m/%Y").fillna(df_tr_view["silenciar_ate"])
            df_tr_view["dias_restantes"] = [f"{max(int(d), 0)} dia(s)" for d in dias_rest_tr]

            df_tr_ed_input = pd.DataFrame(
                {
                    "devolver": [False] * len(df_tr_view),
                    "Código": df_tr_view["codigo"].values,
                    "Descrição": df_tr_view["descricao"].values,
                    "Qtd. Sugerida na Compra": [formatar_qtd_br(v) for v in df_tr_view["qtd_comprada"].values],
                    "Marcado em": df_tr_view[" data_compra_fmt"].values,
                    "Oculto até (15d)": df_tr_view["silenciar_ate_fmt"].values,
                    "Prazo Restante": df_tr_view["dias_restantes"].values,
                }
            )
            ed_transito_gestao = st.data_editor(
                df_tr_ed_input,
                hide_index=True,
                use_container_width=True,
                key="editor_gestao_transito_aba2",
                disabled=[
                    "Código",
                    "Descrição",
                    "Qtd. Sugerida na Compra",
                    "Marcado em",
                    "Oculto até (15d)",
                    "Prazo Restante",
                ],
                column_config={
                    "devolver": st.column_config.CheckboxColumn(
                        "Devolver?",
                        help="Marque para remover do modo 'Já Comprei' e voltar a exibir na lista de compras",
                        default=False,
                    )
                },
            )
            sel_devolver_tr = ed_transito_gestao[ed_transito_gestao["devolver"] == True]
            bt_tr1, bt_tr2 = st.columns(2)
            with bt_tr1:
                btn_dev_marcados = st.button(
                    f"↩️ Devolver Marcados para Lista de Compras ({formatar_num_br(len(sel_devolver_tr))})",
                    type="primary",
                    use_container_width=True,
                    disabled=sel_devolver_tr.empty,
                )
            with bt_tr2:
                btn_dev_todos = st.button(
                    "🔄 Devolver Todos os Itens em Trânsito",
                    use_container_width=True,
                )
            if btn_dev_marcados or btn_dev_todos:
                with st.spinner("Atualizando lista de trânsito no Google Sheets..."):
                    try:
                        if btn_dev_todos:
                            df_tr_restante = padronizar_dataframe(pd.DataFrame(), "pedidos_transito")
                        else:
                            cods_dev = set(sel_devolver_tr["Código"].unique())
                            df_tr_restante = df_pedidos_transito[~df_pedidos_transito["codigo"].isin(cods_dev)].copy()
                        salvar_backup_automatico_aba_gsheets(
                            planilha_gsheets, "pedidos_transito", df_pedidos_transito, permitir_vazio=True
                        )
                        gravar_aba_pequena_gsheets(
                            planilha_gsheets, "pedidos_transito", df_tr_restante, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.session_state["msg_transito_aba2"] = "✅ Produto(s) devolvido(s) para a lista ativa de compras!"
                        st.rerun()
                    except Exception as e_dev:
                        st.error(f"❌ Erro ao devolver produtos: {e_dev}")

# ------------------------------------------------------------------------------
# ABA 3: RADAR DE VALIDADES (FEFO) & CONSULTOR IA DE PROMOÇÕES ANTI-PERDA
# ------------------------------------------------------------------------------
with aba3:
    st.markdown("### ⏳ Radar de Validades (FEFO) & Consultor Inteligente de Promoções")
    st.caption(
        "Cruza a validade de cada lote com o **Giro Diário Real** do produto para descobrir quais lotes vão escoar sozinhos "
        "e quais deixarão **sobra no vencimento**, sugerindo descontos progressivos protegidos contra impostos (ICMS, PIS/COFINS, ST) "
        "e gerando o texto comercial pronto para WhatsApp e para a equipe de vendas."
    )
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 7 (Importação & Backup) para monitorar os lotes e validades.")
    else:
        c_p1, c_p2, c_p3, c_p4 = st.columns([1.2, 1.1, 1.1, 1.4])
        with c_p1:
            escopo_fefo = st.selectbox(
                "🏢 Escopo de Produtos:",
                options=[
                    "🏢 Todos os Produtos (Loja + Fábrica MP)",
                    "🏪 Apenas Loja Varejo (Ocultar MP Fábrica)",
                    "🏭 Apenas Fábrica / Matéria-Prima (MP)",
                ],
                index=0,
                key="fefo_escopo_sel",
                help="Por padrão exibe todos os produtos (Loja + Fábrica MP). Você pode filtrar apenas Varejo ou apenas MP.",
            )
        with c_p2:
            janela_giro_fefo = st.selectbox(
                "📊 Janela de Giro Base:",
                options=[30, 60, 90, 120, 180],
                index=3,
                key="fefo_janela_giro",
                help="Período usado para calcular a velocidade de venda diária de cada produto até a data de vencimento.",
            )
        with c_p3:
            aliquota_imp_fefo = st.number_input(
                "🏛️ Impostos s/ Venda (%):",
                min_value=0.0,
                max_value=35.0,
                value=0.0,
                step=0.5,
                key="fefo_aliq_imp",
                help="Padrão 0% (maioria dos medicamentos isentos). Ajuste se desejar embutir ICMS, PIS/COFINS ou ST no Preço Piso.",
            )
        with c_p4:
            margem_ref_fefo = st.number_input(
                "🏷️ Margem Comercial Padrão (%):",
                min_value=10.0,
                max_value=65.0,
                value=28.0,
                step=1.0,
                key="fefo_margem_ref",
                help="Usada para estimar o preço normal de prateleira quando o produto ainda não possui venda faturada registrada.",
            )

        df_giro_fefo_base, _, _ = calcular_motor_giro_sazonal(
            df_estoque=df_estoque,
            df_historico=df_historico,
            df_base_vendas=df_base_vendas_rel,
            df_custos=df_custos_rel,
            dias_base_atual=dias_base_atual,
            janela_dias=int(janela_giro_fefo),
            incluir_sem_estoque=False,
            df_entradas=df_entradas,
            df_saidas=df_saidas,
        )

        df_fefo = calcular_plano_promocional_fefo(
            df_estoque_ref=df_estoque,
            df_custos_ref=df_custos_rel,
            df_giro_ref=df_giro_fefo_base,
            aliquota_impostos_pct=float(aliquota_imp_fefo),
            margem_referencia_pct=float(margem_ref_fefo),
            df_saidas_ref=df_saidas,
        )

        if escopo_fefo.startswith("🏪"):
            df_fefo = df_fefo[~df_fefo["eh_mp"]].copy()
        elif escopo_fefo.startswith("🏭"):
            df_fefo = df_fefo[df_fefo["eh_mp"]].copy()

        if df_fefo.empty:
            st.success("Nenhum lote ativo encontrado para o filtro selecionado.")
        else:
            v1, v2, v3, v4, v5 = st.columns(5)
            vlr_vencido = float(df_fefo.loc[df_fefo["status_fefo"] == "🔴 1. Vencido", "valor_em_risco"].sum())
            vlr_30d = float(df_fefo.loc[df_fefo["status_fefo"] == "🟠 2. Crítico (0 a 30 dias)", "valor_em_risco"].sum())
            vlr_60d = float(df_fefo.loc[df_fefo["status_fefo"] == "🟡 3. Atenção (31 a 60 dias)", "valor_em_risco"].sum())
            vlr_90d = float(df_fefo.loc[df_fefo["status_fefo"] == "🔵 4. Preventivo (61 a 90 dias)", "valor_em_risco"].sum())
            df_sobra_ate_90 = df_fefo[
                df_fefo["dias_para_vencer"].notna()
                & (df_fefo["dias_para_vencer"] >= 0)
                & (df_fefo["dias_para_vencer"] <= 90)
                & (df_fefo["sobra_projetada"] >= 0.5)
            ]
            vlr_sobra_real_90d = float(df_sobra_ate_90["capital_sobra"].sum())
            qtd_lotes_acao = int(len(df_sobra_ate_90))

            v1.metric("🔴 Vencidos (< 0d)", formatar_moeda_br(vlr_vencido))
            v2.metric("🟠 Crítico (0 a 30d)", formatar_moeda_br(vlr_30d))
            v3.metric("🟡 Atenção (31 a 60d)", formatar_moeda_br(vlr_60d))
            v4.metric("🔵 Preventivo (61 a 90d)", formatar_moeda_br(vlr_90d))
            v5.metric(
                "🤖 Sobra Real p/ Promocionar (≤90d)",
                formatar_moeda_br(vlr_sobra_real_90d),
                f"{formatar_num_br(qtd_lotes_acao)} lote(s) não escoam sozinhos",
                delta_color="inverse" if qtd_lotes_acao > 0 else "normal",
            )

            f_f1, f_f2, f_f3 = st.columns([1.8, 1.2, 1.2])
            opcoes_status = sorted(df_fefo["status_fefo"].unique())
            padrao_status = [s for s in opcoes_status if not s.startswith("🟢")] or opcoes_status
            with f_f1:
                filtro_status = st.multiselect(
                    "Filtrar faixas de vencimento:",
                    options=opcoes_status,
                    default=padrao_status,
                )
            with f_f2:
                busca_fefo = st.text_input(
                    "🔍 Buscar produto ou lote:",
                    placeholder="Ex: roboforte, prontostrep...",
                    key="fefo_busca_txt",
                )
            with f_f3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                apenas_com_sobra_fefo = st.checkbox(
                    "🔥 Apenas lotes que NÃO escoam no giro",
                    value=False,
                    key="chk_apenas_sobra_fefo",
                    help="Oculta os lotes cujo giro diário normal já vai consumir todo o estoque antes do vencimento.",
                )

            df_fefo_view = df_fefo[df_fefo["status_fefo"].isin(filtro_status)].copy()
            if apenas_com_sobra_fefo:
                df_fefo_view = df_fefo_view[df_fefo_view["precisa_promocao"] == True].copy()
            if busca_fefo and busca_fefo.strip():
                t_b_fefo = busca_fefo.lower().strip()
                df_fefo_view = df_fefo_view[
                    df_fefo_view["codigo"].str.lower().str.contains(t_b_fefo, na=False, regex=False)
                    | df_fefo_view["descricao"].str.lower().str.contains(t_b_fefo, na=False, regex=False)
                    | df_fefo_view["lote"].str.lower().str.contains(t_b_fefo, na=False, regex=False)
                ].copy()

            df_fefo_view = df_fefo_view.sort_values(
                ["dias_para_vencer", "capital_sobra"], ascending=[True, False]
            ).reset_index(drop=True)

            df_fefo_exibicao = df_fefo_view[
                [
                    "status_fefo",
                    "codigo",
                    "descricao",
                    "lote",
                    "validade",
                    "dias_para_vencer",
                    "saldo_lote",
                    "giro_diario",
                    "sobra_projetada",
                    "diagnostico_giro_fefo",
                    "mecanica_ia",
                    "preco_piso_imposto",
                    "preco_promo_sug",
                    "desconto_sug_pct",
                    "valor_em_risco",
                    "capital_sobra",
                ]
            ].rename(
                columns={
                    "status_fefo": "Faixa",
                    "codigo": "Cód.",
                    "descricao": "Descrição",
                    "lote": "Lote",
                    "validade": "Validade",
                    "dias_para_vencer": "Dias",
                    "saldo_lote": "Qtd. Lote",
                    "giro_diario": "Giro/d",
                    "sobra_projetada": "Sobra",
                    "diagnostico_giro_fefo": "Diagnóstico FEFO",
                    "mecanica_ia": "Ação IA Sugerida",
                    "preco_piso_imposto": "Piso (R$)",
                    "preco_promo_sug": "Promo (R$)",
                    "desconto_sug_pct": "Desc.",
                    "valor_em_risco": "Cap. Lote",
                    "capital_sobra": "Cap. Sobra",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_fefo_exibicao,
                    formatadores={
                        "Dias": lambda x: "-" if pd.isna(x) else formatar_num_br(x, 0),
                        "Qtd. Lote": formatar_qtd_br,
                        "Giro/d": lambda x: formatar_num_br(x, 3) if (pd.notna(x) and 0 < float(x) < 0.05) else formatar_num_br(x, 2),
                        "Sobra": formatar_qtd_br,
                        "Piso (R$)": formatar_moeda_br,
                        "Promo (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0) else formatar_moeda_br(x),
                        "Desc.": lambda x: "-" if (pd.isna(x) or float(x) <= 0) else f"-{formatar_pct_br(x, 1)}",
                        "Cap. Lote": formatar_moeda_br,
                        "Cap. Sobra": formatar_moeda_br,
                    },
                    colunas_esquerda=["Descrição", "Diagnóstico FEFO", "Ação IA Sugerida"],
                ),
                use_container_width=True,
                hide_index=True,
                height=390,
                column_config={
                    "Faixa": st.column_config.TextColumn("Faixa", help="Faixa de urgência FEFO (Primeiro que Vence, Primeiro que Sai).", width="small"),
                    "Cód.": st.column_config.TextColumn("Cód.", help="Código do Produto no ERP.", width="small"),
                    "Descrição": st.column_config.TextColumn("Descrição", help="Descrição Completa do Produto.", width="medium"),
                    "Lote": st.column_config.TextColumn("Lote", help="Código do Lote físico.", width="small"),
                    "Validade": st.column_config.TextColumn("Validade", help="Data de Validade do Lote.", width="small"),
                    "Dias": st.column_config.TextColumn("Dias", help="Dias restantes até o vencimento do lote.", width="small"),
                    "Qtd. Lote": st.column_config.TextColumn("Qtd. Lote", help="Saldo físico atual disponível neste lote.", width="small"),
                    "Giro/d": st.column_config.TextColumn("Giro/d", help="Giro Médio Diário do Produto.", width="small"),
                    "Sobra": st.column_config.TextColumn("Sobra", help="Quantidade projetada que sobrará sem vender na data de vencimento se mantiver o giro atual.", width="small"),
                    "Diagnóstico FEFO": st.column_config.TextColumn("Diagnóstico FEFO", help="Indica se o lote escoa sozinho no giro normal ou quantas unidades sobrarão no vencimento.", width="medium"),
                    "Ação IA Sugerida": st.column_config.TextColumn("Ação IA Sugerida", help="Mecânica comercial recomendada pela IA para zerar o lote antes de vencer.", width="medium"),
                    "Piso (R$)": st.column_config.TextColumn("Piso (R$)", help="Preço Piso de Equilíbrio (Custo Unitário C1 + Impostos configurados).", width="small"),
                    "Promo (R$)": st.column_config.TextColumn("Promo (R$)", help="Preço Promocional Sugerido pela IA (sempre acima do Piso).", width="small"),
                    "Desc.": st.column_config.TextColumn("Desc.", help="Percentual de Desconto Promocional Sugerido sobre o preço normal.", width="small"),
                    "Cap. Lote": st.column_config.TextColumn("Cap. Lote", help="Capital Total Imobilizado neste Lote (Saldo do Lote × Custo Unitário).", width="small"),
                    "Cap. Sobra": st.column_config.TextColumn("Cap. Sobra", help="Capital Financeiro em Risco Real de Sobra no Vencimento (Sobra Projetada × Custo Unitário).", width="small"),
                },
            )
            if not df_fefo_exibicao.empty:
                st.download_button(
                    label="📥 Baixar Relatório FEFO & Plano de Promoções IA (.xlsx)",
                    data=gerar_excel_relatorio(df_fefo_exibicao, "Radar_FEFO_Promocoes"),
                    file_name=f"Radar_FEFO_Promocoes_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

            st.markdown("---")
            st.markdown("#### 🤖 Simulador Interativo de Promoção & Gerador de Campanhas (WhatsApp / Equipe de Vendas)")
            st.caption(
                "Selecione abaixo qualquer lote crítico para ajustar o preço promocional respeitando o **Piso Tributário (Custo C1 + ICMS/PIS/COFINS/ST)** "
                "e gerar instantaneamente a mensagem para clientes no WhatsApp e a meta diária para os vendedores no balcão."
            )
            df_candidatos_sim = df_fefo[
                df_fefo["dias_para_vencer"].notna()
                & (df_fefo["dias_para_vencer"] >= 0)
                & (df_fefo["dias_para_vencer"] <= 120)
            ].sort_values(["precisa_promocao", "capital_sobra", "dias_para_vencer"], ascending=[False, False, True]).reset_index(drop=True)

            if df_candidatos_sim.empty:
                st.info("Não há lotes vencendo nos próximos 120 dias para simular promoções.")
            else:
                opcoes_lote_sim = [
                    f"[{r['codigo']}] {r['descricao']} — Lote: {r['lote'] or 'S/L'} | Vence em {int(r['dias_para_vencer'])}d ({r['validade']}) | "
                    f"Saldo: {formatar_qtd_br(r['saldo_lote'])} un. | Sobra Projetada: {formatar_qtd_br(r['sobra_projetada'])} un. ({formatar_moeda_br(r['capital_sobra'])})"
                    for _, r in df_candidatos_sim.iterrows()
                ]
                idx_lote_escolhido = st.selectbox(
                    "🎯 Escolha o lote para simular a promoção e gerar os textos:",
                    options=range(len(opcoes_lote_sim)),
                    format_func=lambda i: opcoes_lote_sim[i],
                    key="sel_lote_sim_fefo",
                )
                lote_sel = df_candidatos_sim.iloc[int(idx_lote_escolhido)]
                cod_sim = str(lote_sel["codigo"])
                desc_sim = str(lote_sel["descricao"])
                lote_cod_sim = str(lote_sel["lote"])
                val_sim = str(lote_sel["validade"])
                dias_v_sim = int(lote_sel["dias_para_vencer"])
                saldo_l_sim = float(lote_sel["saldo_lote"])
                sobra_p_sim = float(lote_sel["sobra_projetada"])
                custo_u_sim = float(lote_sel["custo_unitario"])
                piso_imp_sim = float(lote_sel["preco_piso_imposto"])
                tem_preco_real_sim = bool(lote_sel.get("tem_preco_real", False))
                origem_preco_sim = str(lote_sel.get("origem_preco", ""))
                preco_base_padrao = max(float(lote_sel["preco_atual_est"]), custo_u_sim * 1.25, 1.0)
                desc_sug_padrao = float(lote_sel["desconto_sug_pct"]) if float(lote_sel["desconto_sug_pct"]) > 0 else 15.0

                s_col1, s_col2, s_col3 = st.columns(3)
                with s_col1:
                    rotulo_preco_tab = (
                        "💵 Preço Normal Balcão (✔️ Real Saídas):"
                        if tem_preco_real_sim
                        else "💵 Preço Normal Balcão (⚠️ Estimado — Confira):"
                    )
                    preco_tabela_input = st.number_input(
                        rotulo_preco_tab,
                        min_value=0.01,
                        max_value=100000.0,
                        value=float(round(preco_base_padrao, 2)),
                        step=1.0,
                        key=f"p_tab_sim_{cod_sim}_{lote_cod_sim}",
                    )
                with s_col2:
                    desconto_aplicado_pct = st.slider(
                        "🏷️ Desconto Promocional a Aplicar (%):",
                        min_value=0.0,
                        max_value=60.0,
                        value=float(min(max(desc_sug_padrao, 0.0), 60.0)),
                        step=1.0,
                        key=f"desc_sim_{cod_sim}_{lote_cod_sim}",
                    )
                preco_por_calculado = round(preco_tabela_input * (1.0 - (desconto_aplicado_pct / 100.0)), 2)
                with s_col3:
                    preco_por_final = st.number_input(
                        "🔥 Preço Promocional Final ('Por R$'):",
                        min_value=0.01,
                        max_value=100000.0,
                        value=float(max(preco_por_calculado, 0.01)),
                        step=0.50,
                        key=f"p_por_sim_{cod_sim}_{lote_cod_sim}_{desconto_aplicado_pct}",
                    )

                desc_efetivo_pct = max(0.0, ((preco_tabela_input - preco_por_final) / max(preco_tabela_input, 0.01)) * 100.0)
                imposto_un_sim = preco_por_final * (float(aliquota_imp_fefo) / 100.0)
                lucro_liq_un_sim = preco_por_final - imposto_un_sim - custo_u_sim
                margem_liq_sim_pct = ((lucro_liq_un_sim / preco_por_final) * 100.0) if preco_por_final > 0 else 0.0
                caixa_recuperado_total = saldo_l_sim * preco_por_final
                lucro_liq_total_lote = saldo_l_sim * lucro_liq_un_sim

                sm1, sm2, sm3, sm4 = st.columns(4)
                sm1.metric(
                    "Preço Piso (Custo + Impostos)",
                    formatar_moeda_br(piso_imp_sim),
                    f"Custo C1: {formatar_moeda_br(custo_u_sim)}",
                )
                sm2.metric(
                    "Preço Promo ('Por R$')",
                    formatar_moeda_br(preco_por_final),
                    f"-{formatar_num_br(desc_efetivo_pct, 1)}% s/ tabela",
                )
                sm3.metric(
                    "Margem Líquida Pós-Impostos",
                    formatar_pct_br(margem_liq_sim_pct, 1),
                    f"{formatar_moeda_br(lucro_liq_un_sim)} livres/un.",
                    delta_color="normal" if lucro_liq_un_sim >= 0 else "inverse",
                )
                sm4.metric(
                    "Caixa Total Recuperado no Lote",
                    formatar_moeda_br(caixa_recuperado_total),
                    f"Resultado Líq.: {formatar_moeda_br(lucro_liq_total_lote)}",
                )

                if preco_por_final < piso_imp_sim and custo_u_sim > 0:
                    st.warning(
                        f"⚠️ **Alerta Tributário:** O preço promocional escolhido (**{formatar_moeda_br(preco_por_final)}**) está abaixo do "
                        f"**Piso de Equilíbrio com Impostos ({formatar_moeda_br(piso_imp_sim)})**, gerando perda líquida de "
                        f"**{formatar_moeda_br(abs(lucro_liq_un_sim))} por unidade** após descontar {formatar_num_br(aliquota_imp_fefo, 1)}% de impostos. "
                        f"Use apenas se o objetivo for desova de emergência para evitar perda de 100% no vencimento!"
                    )

                preco_foi_editado_manual = abs(float(preco_tabela_input) - float(round(preco_base_padrao, 2))) >= 0.01
                if not tem_preco_real_sim and not preco_foi_editado_manual:
                    st.info(
                        f"💡 **Atenção ao Preço 'De' ({origem_preco_sim}):** Este produto ainda não possui venda com valor faturado na aba `saidas_diarias`, "
                        f"portanto o preço normal de **{formatar_moeda_br(preco_tabela_input)}** foi estimado pela margem ({formatar_num_br(margem_ref_fefo, 0)}%). "
                        f"Confira/ajuste o preço real de prateleira no campo acima ou desmarque a opção abaixo para enviar o WhatsApp apenas com o preço final **'Por R$'**!"
                    )

                exibir_de_wpp = st.checkbox(
                    "🏷️ Exibir preço antigo ('De: ~R$ X,XX~') e cálculo de economia na mensagem do WhatsApp",
                    value=True,
                    key=f"chk_exibir_de_wpp_{cod_sim}_{lote_cod_sim}",
                    help="Se desmarcado, a mensagem de WhatsApp mostrará direto o Preço Especial de Lote ('Por R$'), sem exibir o preço 'De:'.",
                )

                txt_wpp_cli, txt_brief_eq = gerar_textos_campanha_promocional_fefo(
                    codigo=cod_sim,
                    descricao=desc_sim,
                    lote=lote_cod_sim,
                    validade=val_sim,
                    dias_vencer=dias_v_sim,
                    saldo_lote=saldo_l_sim,
                    sobra_proj=sobra_p_sim,
                    custo_unit=custo_u_sim,
                    preco_de=preco_tabela_input,
                    preco_por=preco_por_final,
                    preco_piso=piso_imp_sim,
                    desconto_pct=desc_efetivo_pct,
                    aliquota_imp_pct=float(aliquota_imp_fefo),
                    mecanica_sugerida=str(lote_sel["mecanica_ia"]),
                    meta_giro_dia=float(lote_sel["meta_giro_dia"]),
                    exibir_preco_de_whatsapp=exibir_de_wpp,
                )

                col_msg1, col_msg2 = st.columns(2)
                with col_msg1:
                    st.markdown("##### 📲 1. Mensagem Pronta para WhatsApp (Clientes / Fazendeiros)")
                    st.code(txt_wpp_cli, language="markdown")
                with col_msg2:
                    st.markdown("##### 🎯 2. Briefing de Meta para Equipe de Vendas (Balcão / Interno)")
                    st.code(txt_brief_eq, language="markdown")

# ------------------------------------------------------------------------------
# ABA 4: CURVA ABC FINANCEIRA (UNIFICADA, CENTRALIZADA E C/ OPÇÃO DE ZERADOS)
# ------------------------------------------------------------------------------
with aba4:
    st.markdown("### 📈 Curva ABC Financeira (Pareto 80 / 15 / 5)")
    st.caption(
        "Classificação financeira do capital imobilizado na prateleira (80% Classe A, 15% Classe B e 5% Classe C). "
        "Marque a opção abaixo quando quiser visualizar também os itens do catálogo com saldo zerado ou sem custo (ex: linha completa de um fornecedor)."
    )
    if df_estoque.empty and df_custos_rel.empty:
        st.info("Importe a Planilha de Estoque e a Planilha de Custos na Aba 7 (Importação & Backup) para gerar a Curva ABC Financeira.")
    else:
        col_f_abc1, col_f_abc2 = st.columns([2.2, 1.3])
        with col_f_abc1:
            busca_abc = st.text_input(
                "🔍 Pesquisar Fornecedor / Linha / Produto (use vírgula p/ vários):",
                placeholder="Ex: matsuda  |  ouro fino, ceva  |  505084",
                key="busca_curva_abc",
            )
        with col_f_abc2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            incluir_zerados_abc = st.checkbox(
                "⚪ Incluir itens com Saldo = 0 ou Sem Custo (R$ 0,00)",
                value=False,
                key="chk_incluir_zerados_abc",
                help="Desmarcado por padrão (mostra apenas produtos com valor financeiro > R$ 0,00). Quando marcado, exibe também os itens zerados do catálogo mantendo o cálculo de 80/15/5% intacto.",
            )

        frames_cat_abc = []
        for df_src_abc in [df_estoque, df_entradas, df_saidas, df_base_vendas_rel, df_custos_rel]:
            if df_src_abc is not None and not df_src_abc.empty and "codigo" in df_src_abc.columns and "descricao" in df_src_abc.columns:
                frames_cat_abc.append(df_src_abc[["codigo", "descricao"]])
        df_cat_extra_abc = (
            pd.concat(frames_cat_abc, ignore_index=True).drop_duplicates(subset=["codigo"], keep="first")
            if frames_cat_abc
            else pd.DataFrame(columns=["codigo", "descricao"])
        )

        df_abc = calcular_tabela_curva_abc(
            df_estoque,
            df_custos_rel,
            incluir_zerados=incluir_zerados_abc,
            df_catalogo_extra=df_cat_extra_abc,
        )
        if not df_abc.empty:
            total_fin = float(df_abc["valor_estoque"].sum())
            qtd_classe_a = int((df_abc["classe_abc_curta"] == "Classe A").sum())
            qtd_classe_bc = int(df_abc["classe_abc_curta"].isin(["Classe B", "Classe C"]).sum())
            qtd_sem_saldo_custo = int((df_abc["classe_abc_curta"] == "Sem Saldo/Custo").sum())

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Capital Total Imobilizado", formatar_moeda_br(total_fin))
            a2.metric("Itens Classe A (80% do Valor)", f"{formatar_num_br(qtd_classe_a)} SKUs")
            a3.metric("Itens Classe B + C (20% do Valor)", f"{formatar_num_br(qtd_classe_bc)} SKUs")
            a4.metric(
                "Itens Zerados / Sem Custo",
                f"{formatar_num_br(qtd_sem_saldo_custo)} SKUs" if incluir_zerados_abc else "Ocultos (Marque acima)",
            )

            df_abc_filtrado = df_abc.copy()
            if busca_abc and busca_abc.strip():
                def _norm_abc_txt(txt: str) -> str:
                    s = unicodedata.normalize("NFKD", str(txt)).encode("ASCII", "ignore").decode("utf-8").lower()
                    s = re.sub(r"\bd[\s'\-]*agua\b", "dagua", s)
                    return re.sub(r"[^a-z0-9]+", " ", s).strip()

                grupos_abc = [_norm_abc_txt(g) for g in re.split(r"[;,]+", busca_abc) if _norm_abc_txt(g)]
                if grupos_abc:
                    alvo_s_abc = (df_abc_filtrado["codigo"].astype(str) + " " + df_abc_filtrado["descricao"].astype(str)).map(_norm_abc_txt)
                    mask_busca_abc = pd.Series(False, index=df_abc_filtrado.index)
                    for grp in grupos_abc:
                        m_g = pd.Series(True, index=df_abc_filtrado.index)
                        for pal in grp.split():
                            m_g = m_g & alvo_s_abc.str.contains(re.escape(pal), na=False)
                        mask_busca_abc = mask_busca_abc | m_g
                    df_abc_filtrado = df_abc_filtrado[mask_busca_abc].copy()

                if not incluir_zerados_abc:
                    df_abc_com_z = calcular_tabela_curva_abc(
                        df_estoque,
                        df_custos_rel,
                        incluir_zerados=True,
                        df_catalogo_extra=df_cat_extra_abc,
                    )
                    if not df_abc_com_z.empty:
                        alvo_z = (df_abc_com_z["codigo"].astype(str) + " " + df_abc_com_z["descricao"].astype(str)).map(_norm_abc_txt)
                        m_z_tot = pd.Series(False, index=df_abc_com_z.index)
                        for grp in grupos_abc:
                            m_g = pd.Series(True, index=df_abc_com_z.index)
                            for pal in grp.split():
                                m_g = m_g & alvo_z.str.contains(re.escape(pal), na=False)
                            m_z_tot = m_z_tot | m_g
                        qtd_ocultos_zero_busca = int(len(df_abc_com_z[m_z_tot]) - len(df_abc_filtrado))
                        if qtd_ocultos_zero_busca > 0:
                            st.info(
                                f"ℹ️ Existem mais **{formatar_num_br(qtd_ocultos_zero_busca)} produto(s)** para a busca `'{busca_abc.strip()}'` "
                                f"que estão com **Saldo = 0** (ou sem custo). Marque a caixa **'⚪ Incluir itens com Saldo = 0 ou Sem Custo'** "
                                f"acima à direita para visualizar todos os {formatar_num_br(len(df_abc_com_z[m_z_tot]))} itens!"
                            )

            df_abc_exibicao = df_abc_filtrado[
                ["classe_abc", "codigo", "descricao", "saldo_geral", "custo_unitario", "valor_estoque", "part_pct", "acum_pct"]
            ].rename(
                columns={
                    "classe_abc": "Classe ABC",
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "saldo_geral": "Saldo Geral",
                    "custo_unitario": "Custo Unit. (R$)",
                    "valor_estoque": "Valor Total (R$)",
                    "part_pct": "% Individual",
                    "acum_pct": "% Acumulado",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_abc_exibicao,
                    formatadores={
                        "Saldo Geral": formatar_qtd_br,
                        "Custo Unit. (R$)": formatar_moeda_br,
                        "Valor Total (R$)": formatar_moeda_br,
                        "% Individual": lambda x: formatar_pct_br(x, 2),
                        "% Acumulado": lambda x: formatar_pct_br(x, 2),
                    },
                    colunas_esquerda=["Descrição"],
                ),
                use_container_width=True,
                hide_index=True,
            )
            if not df_abc_exibicao.empty:
                st.download_button(
                    label="📥 Baixar Curva ABC (.xlsx)",
                    data=gerar_excel_relatorio(df_abc_exibicao, "Curva_ABC"),
                    file_name=f"Curva_ABC_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.warning("Nenhum produto com saldo e custo positivos encontrado para calcular a Curva ABC.")

# ------------------------------------------------------------------------------
# ABA 5: AUDITORIA DE ERP COM CLASSIFICAÇÃO DE DIVERGÊNCIAS
# ------------------------------------------------------------------------------
with aba5:
    st.markdown("### 🔍 Auditoria e Classificação de Divergências de ERP")
    st.caption(
        "Os valores originais do ERP nunca são alterados automaticamente. "
        "Abaixo, cada divergência é classificada por natureza operacional para facilitar a conferência no Siagri."
    )
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 1 para auditar divergências de lote e saldos.")
    else:
        df_com_lote = df_estoque[df_estoque["lote"] != ""].copy()
        if not df_com_lote.empty:
            aud_lotes = (
                df_com_lote.groupby("codigo", as_index=False)
                .agg(
                    descricao=("descricao", "first"),
                    saldo_geral=("saldo_geral", "first"),
                    soma_lotes=("saldo_lote", "sum"),
                    qtd_lotes=("lote", "count"),
                    lotes_zerados=("saldo_lote", lambda s: int((s == 0).sum())),
                )
            )
            aud_lotes["diferenca"] = (aud_lotes["saldo_geral"] - aud_lotes["soma_lotes"]).round(3)
            div_lotes = aud_lotes[aud_lotes["diferenca"].abs() > 0.01].copy()

            def _diagnosticar_divergencia(r):
                sg = float(r["saldo_geral"])
                sl = float(r["soma_lotes"])
                if sg < 0 or sl < 0:
                    return "🟠 Saldo Negativo (Furo de estoque físico ou de lote)"
                if sl > sg:
                    return "🔴 Soma dos Lotes > Saldo Geral (Falta de baixa de lote na saída ou unidade diferente)"
                return "🟡 Saldo Geral > Soma dos Lotes (Rastreabilidade parcial / Entrada sem lote)"

            if not div_lotes.empty:
                div_lotes["diagnostico"] = div_lotes.apply(_diagnosticar_divergencia, axis=1)
        else:
            div_lotes = pd.DataFrame()
        saldos_negativos = df_estoque[
            (df_estoque["saldo_geral"] < -0.001) | (df_estoque["saldo_lote"] < -0.001)
        ].copy()
        if not df_custos.empty:
            cods_com_custo = set(df_custos.loc[df_custos["custo_unitario"] > 0, "codigo"])
        else:
            cods_com_custo = set()
        prod_positivos = (
            df_estoque.groupby("codigo", as_index=False)
            .agg(descricao=("descricao", "first"), saldo_geral=("saldo_geral", "first"))
        )
        sem_custo = prod_positivos[
            (prod_positivos["saldo_geral"] > 0) & (~prod_positivos["codigo"].isin(cods_com_custo))
        ].copy()
        qtd_lotes_maior = int((div_lotes["soma_lotes"] > div_lotes["saldo_geral"]).sum()) if not div_lotes.empty else 0
        qtd_geral_maior = int((div_lotes["saldo_geral"] > div_lotes["soma_lotes"]).sum()) if not div_lotes.empty else 0
        au1, au2, au3, au4 = st.columns(4)
        au1.metric("🔴 Soma Lotes > Saldo Geral", formatar_num_br(qtd_lotes_maior))
        au2.metric("🟡 Saldo Geral > Soma Lotes", formatar_num_br(qtd_geral_maior))
        au3.metric("🟠 Registros c/ Saldo Negativo", formatar_num_br(len(saldos_negativos)))
        au4.metric("⚪ Com Estoque e Sem Custo", formatar_num_br(len(sem_custo)))
        st.markdown("#### 1. Classificação de Divergências entre Saldo Geral e Soma dos Lotes")
        if div_lotes.empty:
            st.success("✅ Nenhuma divergência entre Saldo Geral e Soma de Lotes encontrada!")
        else:
            opcoes_diag = sorted(div_lotes["diagnostico"].unique())
            filtro_diag = st.multiselect(
                "Filtrar por tipo de diagnóstico:",
                options=opcoes_diag,
                default=opcoes_diag,
            )
            df_div_filtrada = div_lotes[div_lotes["diagnostico"].isin(filtro_diag)].copy()
            df_div_exib = df_div_filtrada[
                ["codigo", "descricao", "diagnostico", "saldo_geral", "soma_lotes", "diferenca", "qtd_lotes", "lotes_zerados"]
            ].rename(
                columns={
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "diagnostico": "Diagnóstico Provável",
                    "saldo_geral": "Saldo Geral (ERP)",
                    "soma_lotes": "Soma dos Lotes",
                    "diferenca": "Diferença (Geral - Lotes)",
                    "qtd_lotes": "Qtd. Lotes",
                    "lotes_zerados": "Lotes Zerados",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_div_exib,
                    formatadores={
                        "Saldo Geral (ERP)": formatar_qtd_br,
                        "Soma dos Lotes": formatar_qtd_br,
                        "Diferença (Geral - Lotes)": formatar_qtd_br,
                        "Qtd. Lotes": formatar_qtd_br,
                        "Lotes Zerados": formatar_qtd_br,
                    },
                    colunas_esquerda=["Descrição", "Diagnóstico Provável"],
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                label="📥 Baixar Divergências de Lotes Classificadas (.xlsx)",
                data=gerar_excel_relatorio(df_div_exib, "Divergencias_Lotes"),
                file_name=f"Auditoria_Divergencias_Lotes_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.markdown("#### 2. Saldos Negativos no Sistema")
        if saldos_negativos.empty:
            st.success("✅ Nenhum saldo negativo encontrado!")
        else:
            df_neg_exib = saldos_negativos[["codigo", "descricao", "saldo_geral", "lote", "saldo_lote"]].rename(
                columns={
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "saldo_geral": "Saldo Geral",
                    "lote": "Lote",
                    "saldo_lote": "Saldo Lote",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_neg_exib,
                    formatadores={
                        "Saldo Geral": formatar_qtd_br,
                        "Saldo Lote": formatar_qtd_br,
                    },
                    colunas_esquerda=["Descrição"],
                ),
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("#### 3. Produtos com Estoque Físico Sem Custo Unitário")
        if sem_custo.empty:
            st.success("✅ Todos os itens com estoque positivo possuem custo cadastrado!")
        else:
            df_sc_exib = sem_custo.rename(
                columns={
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "saldo_geral": "Saldo Geral",
                }
            )
            st.dataframe(
                estilizar_tabela_br(
                    df_sc_exib,
                    formatadores={"Saldo Geral": formatar_qtd_br},
                    colunas_esquerda=["Descrição"],
                ),
                use_container_width=True,
                hide_index=True,
            )

# ------------------------------------------------------------------------------
# ABA 6: GERENCIADOR DE PRODUTOS OCULTOS (100% NUVEM)
# ------------------------------------------------------------------------------
with aba6:
    st.markdown("### 👁️‍🗨️ Ocultar ou Restaurar Produtos dos Relatórios")
    st.caption(
        "Marque as caixas de seleção para ocultar vários produtos de uma só vez (ex: brindes, uso interno ou itens fora de linha). "
        "A lista fica salva diretamente no Google Sheets e pode ser restaurada a qualquer momento."
    )
    frames_catalogo = []
    if not df_estoque_bruto.empty:
        frames_catalogo.append(df_estoque_bruto[["codigo", "descricao"]])
    if not df_entradas_bruto.empty:
        frames_catalogo.append(df_entradas_bruto[["codigo", "descricao"]])
    if not df_saidas_bruto.empty:
        frames_catalogo.append(df_saidas_bruto[["codigo", "descricao"]])
    if not df_custos.empty:
        frames_catalogo.append(df_custos[["codigo", "descricao"]])
    if not df_base_vendas.empty:
        frames_catalogo.append(df_base_vendas[["codigo", "descricao"]])
    if frames_catalogo:
        df_catalogo = (
            pd.concat(frames_catalogo, ignore_index=True)
            .drop_duplicates(subset=["codigo"], keep="first")
            .sort_values("descricao")
            .reset_index(drop=True)
        )
    else:
        df_catalogo = pd.DataFrame(columns=["codigo", "descricao"])
    col_esq, col_dir = st.columns(2)
    with col_esq:
        st.markdown("#### ✅ Produtos Visíveis nos Relatórios")
        if df_catalogo.empty:
            st.info("Importe suas planilhas na Aba 1 para listar os produtos aqui.")
        else:
            df_visiveis = df_catalogo[~df_catalogo["codigo"].isin(codigos_ocultos)].copy()
            busca_visiveis = st.text_input(
                "🔍 Pesquisar produto visível (Código ou Nome):",
                key="busca_visiveis_oc",
            )
            if busca_visiveis:
                termo_v = busca_visiveis.lower().strip()
                df_visiveis = df_visiveis[
                    df_visiveis["codigo"].str.lower().str.contains(termo_v, na=False, regex=False)
                    | df_visiveis["descricao"].str.lower().str.contains(termo_v, na=False, regex=False)
                ].copy()
            marcar_todos_visiveis = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_visiveis))} produtos listados abaixo",
                value=False,
                key="chk_todos_visiveis",
            )
            df_visiveis.insert(0, "selecionar", marcar_todos_visiveis)
            ed_visiveis = st.data_editor(
                df_visiveis,
                hide_index=True,
                use_container_width=True,
                height=380,
                key="editor_ocultar",
                disabled=["codigo", "descricao"],
                column_config={
                    "selecionar": st.column_config.CheckboxColumn(
                        "Ocultar?",
                        help="Marque para ocultar este produto dos relatórios",
                        default=False,
                    ),
                    "codigo": st.column_config.TextColumn("Código"),
                    "descricao": st.column_config.TextColumn("Descrição"),
                },
            )
            selecionados_para_ocultar = ed_visiveis[ed_visiveis["selecionar"] == True]
            if st.button(
                f"🙈 Ocultar Selecionados ({formatar_num_br(len(selecionados_para_ocultar))})",
                type="primary",
                use_container_width=True,
                disabled=selecionados_para_ocultar.empty,
            ):
                with st.spinner("Salvando produtos ocultos no Google Sheets..."):
                    try:
                        novos_ocultos = selecionados_para_ocultar[["codigo", "descricao"]].copy()
                        novos_ocultos["data_ocultado"] = hoje_br().strftime("%Y-%m-%d")
                        df_ocultos_atualizado = (
                            pd.concat([df_ocultos, novos_ocultos], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
                        )
                        salvar_backup_automatico_aba_gsheets(
                            planilha_gsheets, "ocultos", df_ocultos, permitir_vazio=True
                        )
                        gravar_aba_pequena_gsheets(
                            planilha_gsheets, "ocultos", df_ocultos_atualizado, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success(f"✅ {formatar_num_br(len(selecionados_para_ocultar))} produto(s) ocultado(s) com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao ocultar produtos: {e}")
    with col_dir:
        st.markdown(f"#### 🙈 Produtos Ocultos ({formatar_num_br(len(df_ocultos))})")
        if df_ocultos.empty:
            st.success("Nenhum produto está oculto no momento. Todos os itens estão visíveis nos relatórios!")
        else:
            busca_ocultos = st.text_input(
                "🔍 Pesquisar entre os ocultos:",
                key="busca_ocultos_oc",
            )
            df_oc_view = df_ocultos.copy()
            if busca_ocultos:
                termo_o = busca_ocultos.lower().strip()
                df_oc_view = df_oc_view[
                    df_oc_view["codigo"].str.lower().str.contains(termo_o, na=False, regex=False)
                    | df_oc_view["descricao"].str.lower().str.contains(termo_o, na=False, regex=False)
                ].copy()
            marcar_todos_ocultos = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_oc_view))} ocultos listados abaixo",
                value=False,
                key="chk_todos_ocultos",
            )
            df_oc_view.insert(0, "restaurar", marcar_todos_ocultos)
            ed_ocultos = st.data_editor(
                df_oc_view,
                hide_index=True,
                use_container_width=True,
                height=380,
                key="editor_restaurar",
                disabled=["codigo", "descricao", "data_ocultado"],
                column_config={
                    "restaurar": st.column_config.CheckboxColumn(
                        "Voltar?",
                        help="Marque para voltar a exibir este produto nos relatórios",
                        default=False,
                    ),
                    "codigo": st.column_config.TextColumn("Código"),
                    "descricao": st.column_config.TextColumn("Descrição"),
                    "data_ocultado": st.column_config.TextColumn("Ocultado em"),
                },
            )
            selecionados_para_restaurar = ed_ocultos[ed_ocultos["restaurar"] == True]
            b_rest_1, b_rest_2 = st.columns(2)
            with b_rest_1:
                btn_restaurar_sel = st.button(
                    f"👁️ Restaurar Marcados ({formatar_num_br(len(selecionados_para_restaurar))})",
                    type="primary",
                    use_container_width=True,
                    disabled=selecionados_para_restaurar.empty,
                )
            with b_rest_2:
                btn_restaurar_todos = st.button(
                    "🔄 Restaurar Todos",
                    use_container_width=True,
                )
            if btn_restaurar_sel or btn_restaurar_todos:
                with st.spinner("Restaurando produtos no Google Sheets..."):
                    try:
                        if btn_restaurar_todos:
                            df_ocultos_restante = padronizar_dataframe(pd.DataFrame(), "ocultos")
                        else:
                            cods_remover = set(selecionados_para_restaurar["codigo"].unique())
                            df_ocultos_restante = df_ocultos[~df_ocultos["codigo"].isin(cods_remover)].copy()
                        salvar_backup_automatico_aba_gsheets(
                            planilha_gsheets, "ocultos", df_ocultos, permitir_vazio=True
                        )
                        gravar_aba_pequena_gsheets(
                            planilha_gsheets, "ocultos", df_ocultos_restante, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success("✅ Produto(s) restaurado(s) para os relatórios com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao restaurar produtos: {e}")
