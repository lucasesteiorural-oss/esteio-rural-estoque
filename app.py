import io
import re
import math
import hmac
import zipfile
import unicodedata
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E VISUAL LIQUID GLASS (ALTO CONTRASTE)
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
    .stApp {
        background: radial-gradient(circle at 15% 15%, #0f2922 0%, #07120f 55%, #050a09 100%);
        color: #f1f5f9;
    }
    .glass-card {
        background: rgba(17, 37, 32, 0.72);
        border: 1px solid rgba(52, 211, 153, 0.28);
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(12px);
        margin-bottom: 14px;
    }
    .status-box {
        background: rgba(15, 34, 29, 0.85);
        border: 1px solid rgba(52, 211, 153, 0.45);
        border-radius: 14px;
        padding: 14px 18px;
        text-align: left;
    }
    .status-label {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .status-value {
        font-size: 1.35rem;
        font-weight: 800;
        color: #f8fafc;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .pill-tag {
        display: inline-block;
        background: rgba(20, 184, 166, 0.18);
        border: 1px solid rgba(45, 212, 191, 0.4);
        color: #5eead4;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-family: monospace;
        margin: 2px 3px 2px 0;
    }
    div[data-testid="stMetric"] {
        background: rgba(17, 37, 32, 0.75);
        border: 1px solid rgba(52, 211, 153, 0.25);
        border-radius: 12px;
        padding: 12px 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 1.1 ACESSO SEGURO AO ST.SECRETS E AUTENTICAÇÃO POR SENHA
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
        st.info(
            "🔓 **Dica de Segurança:** Para proteger o link com senha, adicione "
            "`app_password = \"SuaSenha\"` na aba **Secrets** do Streamlit Cloud."
        )
        return True

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
TAMANHO_LOTE_MIGRACAO = 4000
LIMITE_COINCIDENCIA_CATALOGO = 80.0

COLUNAS_NUMERICAS = {"saldo_geral", "saldo_lote", "custo_unitario", "qtd_vendida"}

ESQUEMA_ABAS = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "lote", "saldo_lote", "data"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "meta": ["chave", "valor"],
}

COLUNAS_OBRIGATORIAS_UPLOAD = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade"],
    "historico": ["codigo", "saldo_geral", "lote", "saldo_lote", "data"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao"],
    "meta": ["chave", "valor"],
}

ORDEM_POSICIONAL_PADRAO = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "lote", "saldo_lote", "data"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "meta": ["chave", "valor"],
}

MAPA_SINONIMOS = {
    "codigo": ["codigo", "cod", "cod_produto", "codigo_produto", "codigo_do_produto", "sku", "id", "item"],
    "saldo_geral": ["saldo_geral", "saldogeral", "estoque_geral", "saldo_total", "saldo_atual", "estoque_atual", "saldo_fisico", "saldo"],
    "descricao": ["descricao", "desc", "descricao_produto", "descricao_do_produto", "produto", "nome", "mercadoria"],
    "lote": ["lote", "codigo_do_lote", "cod_lote", "codigo_lote", "num_lote", "numero_lote", "lotes"],
    "saldo_lote": ["saldo_lote", "saldolote", "saldo_do_lote", "qtd_lote", "estoque_lote", "quant_lote"],
    "validade": ["validade", "data_validade", "dt_validade", "data_de_validade", "vencimento", "val"],
    "data": ["data", "data_posicao", "data_ref", "data_importacao", "dt", "dia"],
    "custo_unitario": ["custo_unitario", "custo_unitario_c1", "custo_c1", "custo", "preco_custo", "valor_unitario", "c1"],
    "qtd_vendida": ["qtd_vendida", "quantidade_vendida", "quantidade", "qtd", "vendas", "saida", "total_vendido"],
    "data_ocultado": ["data_ocultado", "data", "ocultado_em"],
    "chave": ["chave", "key", "parametro", "config"],
    "valor": ["valor", "value", "conteudo"],
}


def formatar_num_br(valor, casas: int = 0) -> str:
    """Formata número no padrão brasileiro (ex: 10.927.761,00 ou 1.250)."""
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
    """Formata saldos e quantidades com separador de milhar (sem casas se inteiro, ou até 2 casas se fracionado)."""
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
    """Formata valores monetários no padrão R$ 10.927.761,00."""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return "R$ 0,00"
    return f"R$ {formatar_num_br(v, 2)}"


def formatar_pct_br(valor, casas: int = 1, com_sinal: bool = False) -> str:
    """Formata percentuais no padrão brasileiro (ex: 12,5% ou +12,5%)."""
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
    """Converte para texto preservando zeros à esquerda e formatando datas/inteiros vindos do Excel."""
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


def converter_numero_br(serie: pd.Series) -> pd.Series:
    """
    Conversão inteligente que preserva 100% dos valores numéricos nativos do Excel (ex: float 13.071)
    sem confundi-los com milhares, e desambigua textos de CSV/Sheets olhando o contexto da coluna:
    1. Valores já numéricos (int/float vindos do Excel): mantidos exatamente como float (13.071 -> 13.071).
    2. Textos com vírgula decimal ('1.234,56' ou '13,071'): ponto é milhar, vírgula é decimal.
    3. Textos com 2 ou mais pontos ('1.234.567'): pontos são milhar (1234567.0).
    4. Textos com 1 único ponto e 3 dígitos ('1.000' vs '13.071'):
       - Se a coluna usa ponto como separador decimal (ex: dados do Google Sheets ou CSV com '10.5', '4.25'),
         '13.071' é lido como decimal 13.071.
       - Só é tratado como milhar (1000.0) se a coluna for explicitamente texto no padrão BR (com vírgulas
         decimais na coluna e sem decimais com ponto).
    """
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0.0).astype(float)

    # Separa elementos que já vieram como int/float nativos do Excel (preserva 13.071 intacto)
    mask_nativo_num = serie.map(lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and pd.notna(x))
    if mask_nativo_num.all():
        return serie.astype(float)

    s_str = (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.replace("R$", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    # Analisa os elementos que vieram originalmente como texto na coluna
    s_apenas_str = s_str[~mask_nativo_num]
    tem_virgula_decimal_na_coluna = s_apenas_str.str.contains(r",\d+$", regex=True).any()
    tem_ponto_nao_3_digitos = s_apenas_str.str.match(r"^[+-]?\d+\.\d{1,2}$|^[+-]?\d+\.\d{4,}$").any()

    # Só interpreta '1.000' (1 ponto + 3 dígitos) como milhar se a coluna de texto nunca usar ponto para 1, 2 ou 4+ casas decimais
    # e tiver estilo brasileiro (ou for coluna exclusivamente de inteiros formatados como '1.000')
    tratar_1ponto_3dig_como_milhar = (not tem_ponto_nao_3_digitos) and tem_virgula_decimal_na_coluna

    def _parse_elemento(val):
        if pd.isna(val) or val is None:
            return 0.0
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        txt = (
            str(val)
            .strip()
            .replace("R$", "")
            .replace("\u00a0", "")
            .replace(" ", "")
        )
        if not txt or txt.lower() in ("nan", "none", "nat", "<na>"):
            return 0.0

        # Caso A: Possui vírgula e ponto
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                # Ex: 1.234,56 (BR)
                txt = txt.replace(".", "").replace(",", ".")
            else:
                # Ex: 1,234.56 (US)
                txt = txt.replace(",", "")
        # Caso B: Possui apenas vírgula (Ex: 13,071 ou 45,90)
        elif "," in txt:
            txt = txt.replace(",", ".")
        # Caso C: Possui apenas ponto(s)
        elif "." in txt:
            # Múltiplos pontos (Ex: 1.234.567) -> certeza absoluta de milhar
            if txt.count(".") >= 2 and re.match(r"^[+-]?\d{1,3}(\.\d{3}){2,}$", txt):
                txt = txt.replace(".", "")
            # Único ponto com 3 dígitos (Ex: '13.071' ou '1.000')
            elif tratar_1ponto_3dig_como_milhar and re.match(r"^[+-]?\d{1,3}\.\d{3}$", txt):
                txt = txt.replace(".", "")

        try:
            return float(txt)
        except ValueError:
            return 0.0

    return serie.map(_parse_elemento).astype(float)


def converter_datas_deterministico(serie: pd.Series) -> pd.Series:
    s_limpa = serie.fillna("").astype(str).str.strip().str.split(r"[ T]", regex=True).str[0]
    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    formatos_explicitos = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    for fmt in formatos_explicitos:
        faltantes = resultado.isna() & (s_limpa != "")
        if not faltantes.any():
            break
        convertido = pd.to_datetime(s_limpa[faltantes], format=fmt, errors="coerce")
        resultado.loc[faltantes] = convertido

    return resultado


def restaurar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        if col in COLUNAS_NUMERICAS:
            df[col] = converter_numero_br(df[col])
        else:
            df[col] = limpar_serie_texto(df[col])
    return df


def estruturar_dataframe_bruto(
    df: pd.DataFrame,
    nome_aba: str,
    exigir_colunas_obrigatorias: bool = False,
) -> pd.DataFrame:
    colunas_esperadas = ESQUEMA_ABAS.get(nome_aba, [])
    if df is None or df.empty:
        return restaurar_tipos(pd.DataFrame(columns=colunas_esperadas))

    df_orig = df.loc[:, ~df.columns.duplicated()].copy()

    if nome_aba == "historico" and df_orig.shape[1] >= 7:
        cols_norm_hist = [normalizar_chave_coluna(c) for c in df_orig.columns]
        if "codigo" not in cols_norm_hist:
            df_pos = df_orig.iloc[:, :7].copy()
            df_pos.columns = ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"]
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

    ordem_padrao = ORDEM_POSICIONAL_PADRAO.get(nome_aba, colunas_esperadas)
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
        obrigatorias = COLUNAS_OBRIGATORIAS_UPLOAD.get(nome_aba, [])
        ausentes = [c for c in obrigatorias if c not in df.columns]
        if ausentes:
            raise ValueError(
                f"Estrutura incompleta para '{nome_aba}': colunas obrigatórias ausentes ({', '.join(ausentes)})."
            )

    for col_alvo in colunas_esperadas:
        if col_alvo not in df.columns:
            if col_alvo in COLUNAS_NUMERICAS:
                df[col_alvo] = 0.0
            elif col_alvo in ("data", "data_ocultado"):
                df[col_alvo] = date.today().strftime("%Y-%m-%d")
            else:
                df[col_alvo] = ""

    df = df[colunas_esperadas].copy()
    df = restaurar_tipos(df)

    if "codigo" in df.columns:
        df = df[df["codigo"] != ""].copy()
        df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod", "total"])].copy()

    return df.reset_index(drop=True)


def padronizar_dataframe(df: pd.DataFrame, nome_aba: str) -> pd.DataFrame:
    df = estruturar_dataframe_bruto(df, nome_aba)
    if df.empty:
        return df

    if nome_aba in ("estoque_atual", "historico"):
        df = df.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
    elif nome_aba in ("custos", "ocultos"):
        df = df.drop_duplicates(subset=["codigo"], keep="last")

    return df.reset_index(drop=True)


def podar_historico_180_dias(df_hist: pd.DataFrame) -> pd.DataFrame:
    if df_hist is None or df_hist.empty or "data" not in df_hist.columns:
        return padronizar_dataframe(pd.DataFrame(), "historico")

    df_h = df_hist.copy()
    dt_parsed = converter_datas_deterministico(df_h["data"])
    mask_valida = dt_parsed.notna()
    df_h = df_h.loc[mask_valida].copy()
    if df_h.empty:
        return padronizar_dataframe(pd.DataFrame(), "historico")

    dt_validas = dt_parsed.loc[mask_valida]
    df_h["data"] = dt_validas.dt.strftime("%Y-%m-%d")

    limite_ts = pd.Timestamp(date.today() - timedelta(days=DIAS_MAX_HISTORICO))
    df_filtrado = df_h[dt_validas >= limite_ts].copy()
    df_filtrado = df_filtrado.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
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
        return padronizar_dataframe(pd.DataFrame(), nome_aba)
    cabecalho = [
        str(c).strip() if str(c).strip() else f"col_{i}"
        for i, c in enumerate(valores[0])
    ]
    df = pd.DataFrame(valores[1:], columns=cabecalho)
    return padronizar_dataframe(df, nome_aba)


def gravar_aba_pequena_gsheets(planilha, nome_aba: str, df: pd.DataFrame, permitir_vazio: bool = False):
    if df is None:
        return
    if df.empty and not permitir_vazio:
        return

    df_padrao = padronizar_dataframe(df, nome_aba) if nome_aba in ESQUEMA_ABAS else df
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


def migrar_historico_em_lotes_seguros(planilha, ws_antiga, df_combinado: pd.DataFrame):
    import gspread

    df_padrao = podar_historico_180_dias(padronizar_dataframe(df_combinado, "historico"))
    df_str = df_padrao.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    todas_linhas = df_str.values.tolist()

    nome_temp = "historico_mig_temp"
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
    ws_temp.update_title("historico")


def gravar_historico_incremental_gsheets(
    planilha, df_novo_dia: pd.DataFrame, data_ref: str
):
    if df_novo_dia is None or df_novo_dia.empty:
        return

    df_novo_padrao = padronizar_dataframe(df_novo_dia, "historico")
    df_str = df_novo_padrao.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    linhas_novas = df_str.values.tolist()

    linhas_nec_inicial = len(linhas_novas) + 10
    cols_nec = max(len(cabecalho), 5)

    ws = obter_ou_criar_aba(planilha, "historico", linhas_nec_inicial + 50, cols_nec + 2)
    primeira_linha = [str(c).strip() for c in ws.row_values(1)]

    if not primeira_linha:
        if ws.row_count < linhas_nec_inicial or ws.col_count < cols_nec:
            ws.resize(rows=max(ws.row_count, linhas_nec_inicial), cols=max(ws.col_count, cols_nec))
        ws.update(
            values=[cabecalho] + linhas_novas,
            range_name="A1",
            value_input_option="RAW",
        )
        return

    limite_str = (date.today() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")

    if primeira_linha != cabecalho:
        df_antigo = ler_aba_bruta_gsheets(planilha, "historico")
        if not df_antigo.empty:
            df_antigo = df_antigo[
                (df_antigo["data"] != str(data_ref).strip())
                & (df_antigo["data"] >= limite_str)
            ].copy()
            df_combinado = pd.concat([df_antigo, df_novo_padrao], ignore_index=True)
        else:
            df_combinado = df_novo_padrao
        migrar_historico_em_lotes_seguros(planilha, ws, df_combinado)
        return

    idx_col_data = (primeira_linha.index("data") + 1) if "data" in primeira_linha else 5
    col_datas_antes = ws.col_values(idx_col_data)
    dt_col_parsed = converter_datas_deterministico(pd.Series(col_datas_antes))
    dt_col_iso = dt_col_parsed.dt.strftime("%Y-%m-%d").fillna("")

    linhas_antigas_para_apagar = [
        i
        for i, val_iso in enumerate(dt_col_iso, start=1)
        if i >= 2 and (val_iso == str(data_ref).strip() or (val_iso != "" and val_iso < limite_str))
    ]

    ws.append_rows(values=linhas_novas, value_input_option="RAW")

    if linhas_antigas_para_apagar:
        blocos = []
        inicio = fim = linhas_antigas_para_apagar[0]
        for r in linhas_antigas_para_apagar[1:]:
            if r == fim + 1:
                fim = r
            else:
                blocos.append((inicio, fim))
                inicio = fim = r
        blocos.append((inicio, fim))

        for ini, f in reversed(blocos):
            ws.delete_rows(ini, f)


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_estado_completo() -> dict:
    planilha, erro = obter_planilha_gsheets()
    if planilha is None:
        raise RuntimeError(f"Não foi possível conectar ao Google Sheets: {erro}")

    df_est = ler_aba_bruta_gsheets(planilha, "estoque_atual")
    df_hist = podar_historico_180_dias(ler_aba_bruta_gsheets(planilha, "historico"))
    df_cus = ler_aba_bruta_gsheets(planilha, "custos")
    df_base = ler_aba_bruta_gsheets(planilha, "base_inicial")
    df_ocul = ler_aba_bruta_gsheets(planilha, "ocultos")
    df_meta = ler_aba_bruta_gsheets(planilha, "meta")

    dias_base = 87
    ult_att = "Sincronizado via Nuvem"
    if not df_meta.empty and "chave" in df_meta.columns and "valor" in df_meta.columns:
        mapa_meta = dict(zip(df_meta["chave"], df_meta["valor"]))
        try:
            dias_base = int(float(mapa_meta.get("dias_base", 87)))
        except ValueError:
            dias_base = 87
        ult_att = mapa_meta.get("ultima_atualizacao", ult_att)

    return {
        "estoque_atual": df_est,
        "historico": df_hist,
        "custos": df_cus,
        "base_inicial": df_base,
        "ocultos": df_ocul,
        "dias_base": dias_base,
        "ultima_atualizacao": ult_att,
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

        eh_esquerda = any(p in titulo_norm for p in ["descricao", "diagnostico"])
        eh_moeda = any(p in titulo_norm for p in ["custo", "valor", "capital", "total_compra", "total_do_item"]) and "pct" not in titulo_norm and "variacao" not in titulo_norm
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
    df_meta_bkp = pd.DataFrame(
        [
            {"chave": "dias_base", "valor": str(estado.get("dias_base", 87))},
            {"chave": "ultima_atualizacao", "valor": str(estado.get("ultima_atualizacao", "-"))},
            {"chave": "data_exportacao_backup", "valor": datetime.now().strftime("%d/%m/%Y %H:%M:%S")},
        ]
    )

    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        estado.get("estoque_atual", pd.DataFrame()).to_excel(writer, sheet_name="estoque_atual", index=False)
        estado.get("custos", pd.DataFrame()).to_excel(writer, sheet_name="custos", index=False)
        estado.get("base_inicial", pd.DataFrame()).to_excel(writer, sheet_name="base_inicial", index=False)
        estado.get("ocultos", pd.DataFrame()).to_excel(writer, sheet_name="ocultos", index=False)
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
    """
    Mantém int/float nativos do Excel como números reais (ex: float 13.071 permanece 13.071),
    e preserva strings intactas com seus zeros à esquerda (ex: '0602002').
    """
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.strftime("%d/%m/%Y")
    return str(val).strip()


def ler_arquivo_upload(arquivo, exigir_multiplas_colunas: bool = False) -> pd.DataFrame:
    """
    Lê arquivos .xlsx, .xls ou .csv:
    - Para Excel (.xlsx/.xls): preserva números nativos como float/int (evitando que 13.071 vire texto '13.071')
      e mantém códigos/lotes de texto com zeros à esquerda intactos.
    - Para CSV: testa separadores exigindo >= 2 colunas primeiro.
    """
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
    df["codigo_lista"] = limpar_serie_texto(df_raw[col_cod])
    if col_desc is not None:
        df["descricao_lista"] = limpar_serie_texto(df_raw[col_desc])
    else:
        df["descricao_lista"] = ""

    df = df[df["codigo_lista"] != ""].copy()
    df = df[~df["codigo_lista"].str.lower().isin(["codigo", "código", "cod", "sku", "id", "item", "total"])].copy()
    df = df.drop_duplicates(subset=["codigo_lista"], keep="first").reset_index(drop=True)
    return df


def calcular_tabela_curva_abc(df_estoque_ref: pd.DataFrame, df_custos_ref: pd.DataFrame) -> pd.DataFrame:
    if df_estoque_ref is None or df_estoque_ref.empty or df_custos_ref is None or df_custos_ref.empty:
        return pd.DataFrame()

    df_abc = (
        df_estoque_ref.groupby("codigo", as_index=False)
        .agg(descricao=("descricao", "first"), saldo_geral=("saldo_geral", "first"))
        .merge(df_custos_ref[["codigo", "custo_unitario"]], on="codigo", how="left")
    )
    df_abc["custo_unitario"] = df_abc["custo_unitario"].fillna(0.0)
    df_abc["valor_estoque"] = df_abc["saldo_geral"].clip(lower=0.0) * df_abc["custo_unitario"]
    df_abc = (
        df_abc[df_abc["valor_estoque"] > 0]
        .sort_values(["valor_estoque", "codigo"], ascending=[False, True])
        .copy()
    )

    total_fin = float(df_abc["valor_estoque"].sum())
    if total_fin <= 0:
        return pd.DataFrame()

    df_abc["part_pct"] = ((df_abc["valor_estoque"] / total_fin) * 100.0).round(2)
    df_abc["acum_pct"] = df_abc["part_pct"].cumsum().round(2)
    df_abc["classe_abc_curta"] = df_abc["acum_pct"].apply(
        lambda p: "Classe A" if p <= 80.0 else ("Classe B" if p <= 95.0 else "Classe C")
    )
    df_abc["classe_abc"] = df_abc["acum_pct"].apply(
        lambda p: "Classe A (Até 80%)" if p <= 80.0 else ("Classe B (80% a 95%)" if p <= 95.0 else "Classe C (95% a 100%)")
    )
    return df_abc.reset_index(drop=True)


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

    cods_novos = set(df_novo["codigo"].unique())
    intersecao = cods_novos & codigos_referencia

    taxa_sobre_novo = (len(intersecao) / max(len(cods_novos), 1)) * 100.0
    taxa_sobre_anterior = (len(intersecao) / max(len(codigos_referencia), 1)) * 100.0
    taxa_avaliada = min(taxa_sobre_novo, taxa_sobre_anterior) if exigir_cobertura_total else taxa_sobre_novo

    if taxa_avaliada < LIMITE_COINCIDENCIA_CATALOGO and not ignorar_trava_catalogo:
        estranhos = sorted(list(cods_novos - codigos_referencia))[:8]
        amostra_estranhos = ", ".join(f"'{c}'" for c in estranhos) if estranhos else "N/A"
        raise ValueError(
            f"Trava contra Colunas Trocadas ({nome_planilha}): Apenas **{taxa_avaliada:.1f}%** dos códigos "
            f"coincidem com a base anterior ({len(intersecao)} coincidentes entre {len(cods_novos)} enviados "
            f"e {len(codigos_referencia)} cadastrados; mínimo exigido: {LIMITE_COINCIDENCIA_CATALOGO:.0f}%). "
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


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_motor_giro_sazonal(
    df_estoque: pd.DataFrame,
    df_historico: pd.DataFrame,
    df_base_vendas: pd.DataFrame,
    df_custos: pd.DataFrame,
    dias_base_atual: int,
    janela_dias: int,
    incluir_sem_estoque: bool = True,
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
    df_saidas_sku = pd.DataFrame(columns=["codigo", "giro_historico", "taxa_recente", "taxa_antiga"])

    if not df_historico.empty and "data" in df_historico.columns:
        datas_todas = sorted(df_historico["data"].unique())
        dt_max = pd.to_datetime(datas_todas[-1], format="%Y-%m-%d", errors="coerce")
        if pd.notna(dt_max):
            dt_corte = (dt_max - pd.Timedelta(days=int(janela_dias))).strftime("%Y-%m-%d")
            df_h_win = df_historico[df_historico["data"] >= dt_corte].copy()
        else:
            df_h_win = df_historico.copy()

        df_h_win = df_h_win.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")

        datas_win = sorted(df_h_win["data"].unique())
        if len(datas_win) >= 2:
            d_ini = pd.to_datetime(datas_win[0], format="%Y-%m-%d", errors="coerce")
            d_fim = pd.to_datetime(datas_win[-1], format="%Y-%m-%d", errors="coerce")
            dias_corridos_total = int((d_fim - d_ini).days) if (pd.notna(d_ini) and pd.notna(d_fim)) else 1
            intervalo_historico_dias = max(dias_corridos_total, len(datas_win) - 1, 1)
            peso_historico = min(float(intervalo_historico_dias) / float(janela_dias), 1.0)

            sem_lote = df_h_win["lote"] == ""
            df_h_win["chave_lote"] = df_h_win["lote"].where(~sem_lote, "__SEM_LOTE__")
            df_h_win["saldo_ref"] = df_h_win["saldo_lote"].where(~sem_lote, df_h_win["saldo_geral"])

            grade_lotes = (
                df_h_win.groupby(["codigo", "chave_lote", "data"], as_index=False)["saldo_ref"]
                .last()
            )
            pivot_lotes = grade_lotes.pivot(
                index=["codigo", "chave_lote"], columns="data", values="saldo_ref"
            ).fillna(0.0)[datas_win]

            deltas_lotes = pivot_lotes.diff(axis=1)
            quedas_lotes_sku = deltas_lotes.where(deltas_lotes < 0.0, 0.0).abs().groupby(level="codigo").sum()

            grade_geral = (
                df_h_win.groupby(["codigo", "data"], as_index=False)["saldo_geral"]
                .first()
            )
            pivot_geral = grade_geral.pivot(
                index="codigo", columns="data", values="saldo_geral"
            ).fillna(0.0)[datas_win]
            deltas_geral = pivot_geral.diff(axis=1)
            quedas_geral_sku = deltas_geral.where(deltas_geral < 0.0, 0.0).abs()

            quedas_por_sku = quedas_lotes_sku.combine(quedas_geral_sku, lambda s1, s2: s1.combine(s2, max))
            saida_total = quedas_por_sku.sum(axis=1)

            cols_transicao = datas_win[1:]
            meio = max(len(cols_transicao) // 2, 1)
            cols_antigas = cols_transicao[:meio]
            cols_recentes = cols_transicao[meio:] if len(cols_transicao) > 1 else cols_transicao

            dt_meio = pd.to_datetime(datas_win[meio], format="%Y-%m-%d", errors="coerce")
            if pd.notna(d_ini) and pd.notna(dt_meio) and pd.notna(d_fim):
                dias_antigos = max(int((dt_meio - d_ini).days), len(cols_antigas), 1)
                dias_recentes = (
                    max(int((d_fim - dt_meio).days), len(cols_recentes), 1)
                    if len(cols_transicao) > 1
                    else dias_antigos
                )
            else:
                dias_antigos = max(len(cols_antigas), 1)
                dias_recentes = max(len(cols_recentes), 1)

            taxa_antiga = quedas_por_sku[cols_antigas].sum(axis=1) / float(dias_antigos)
            taxa_recente = quedas_por_sku[cols_recentes].sum(axis=1) / float(dias_recentes)

            df_saidas_sku = pd.DataFrame(
                {
                    "codigo": quedas_por_sku.index,
                    "giro_historico": (saida_total / float(intervalo_historico_dias)).values,
                    "taxa_recente": taxa_recente.values,
                    "taxa_antiga": taxa_antiga.values,
                }
            )

    df_calc = df_prod.merge(df_saidas_sku, on="codigo", how="left")
    df_calc["giro_historico"] = df_calc["giro_historico"].fillna(0.0)
    df_calc["taxa_recente"] = df_calc.get("taxa_recente", pd.Series(0.0, index=df_calc.index)).fillna(0.0)
    df_calc["taxa_antiga"] = df_calc.get("taxa_antiga", pd.Series(0.0, index=df_calc.index)).fillna(0.0)

    df_calc["giro_ponderado"] = (
        (df_calc["giro_historico"] * peso_historico)
        + (df_calc["giro_base"] * (1.0 - peso_historico))
    )

    def _classificar_tendencia(row):
        if intervalo_historico_dias < 1:
            return "➡️ Base Inicial"
        ref = row["giro_base"] if row["giro_base"] > 0 else row["taxa_antiga"]
        atual = row["giro_historico"] if row["giro_base"] > 0 else row["taxa_recente"]
        if ref <= 0.0001 and atual <= 0.0001:
            return "➡️ Sem Giro"
        if ref <= 0.0001 and atual > 0.0001:
            return "📈 Alta (Novo Giro)"
        razao = atual / ref
        if razao >= 1.15:
            return f"📈 Alta (+{int(round((razao - 1.0) * 100))}%)"
        if razao <= 0.85:
            return f"📉 Baixa (-{int(round((1.0 - razao) * 100))}%)"
        return "➡️ Estável"

    df_calc["tendencia"] = df_calc.apply(_classificar_tendencia, axis=1)
    return df_calc, intervalo_historico_dias, peso_historico


# ==============================================================================
# 6. CABEÇALHO PRINCIPAL E VERIFICAÇÃO DE CONEXÃO COM A NUVEM
# ==============================================================================
planilha_gsheets, erro_gsheets = obter_planilha_gsheets()
conectado_nuvem = planilha_gsheets is not None

col_titulo, col_status = st.columns([3.4, 1.2])
with col_titulo:
    st.markdown(
        "## 🌾 Esteio Rural — Inteligência de Estoque & Giro Sazonal"
    )
with col_status:
    texto_status = (
        "☁️ Google Sheets (Online)" if conectado_nuvem else "❌ Sem Conexão"
    )
    st.markdown(
        f"""
        <div class="status-box">
            <div class="status-label">Status do Banco de Dados (100% Nuvem)</div>
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
df_custos = estado["custos"]
df_base_vendas = estado["base_inicial"]
df_ocultos = estado["ocultos"]
dias_base_atual = int(estado.get("dias_base", 87))

codigos_ocultos = set(df_ocultos["codigo"].unique()) if not df_ocultos.empty else set()

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
    df_base_vendas_rel = df_base_vendas[~df_base_vendas["codigo"].isin(codigos_ocultos)]
    df_custos_rel = df_custos[~df_custos["codigo"].isin(codigos_ocultos)]
else:
    df_estoque = df_estoque_bruto
    df_historico = df_historico_bruto
    df_base_vendas_rel = df_base_vendas
    df_custos_rel = df_custos

# ==============================================================================
# 7. NAVEGAÇÃO POR ABAS (100% NUVEM)
# ==============================================================================
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(
    [
        "📥 1. Importação & Backup",
        "🛒 2. Sugestão de Compras & Cotação",
        "⏳ 3. Radar de Validades (FEFO)",
        "📊 4. Curva ABC Financeira",
        "🔍 5. Auditoria de ERP",
        f"👁️‍🗨️ 6. Ocultar Produtos ({formatar_num_br(len(codigos_ocultos))})",
    ]
)

# ------------------------------------------------------------------------------
# ABA 1: CENTRAL DE IMPORTAÇÃO SEGURA E DOWNLOAD DO BANCO DE DADOS
# ------------------------------------------------------------------------------
with aba1:
    st.markdown("### Central de Importação Segura e Sincronização 100% Nuvem")
    st.caption(
        "Preservação exata de tipos numéricos do Excel (ex: custos com 3 casas decimais como 13,071), "
        "trava de 80% de coincidência de códigos, gravação do Histórico ANTES do Estoque e download do Banco."
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
                <strong>1. Planilha de Estoque (Diária - 6 colunas)</strong><br><br>
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
        data_posicao = st.date_input("Data desta posição de estoque:", value=date.today())
        arq_estoque = st.file_uploader(
            "Selecionar Estoque (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_estoque",
        )

    with c2:
        st.markdown(
            """
            <div class="glass-card">
                <strong>2. Planilha de Custos (Semanal - 3 colunas)</strong><br><br>
                <span class="pill-tag">Código</span>
                <span class="pill-tag">Descrição</span>
                <span class="pill-tag">Custo Unitário C1</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arq_custos = st.file_uploader(
            "Selecionar Custos (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_custos",
        )

    with c3:
        st.markdown(
            """
            <div class="glass-card">
                <strong>3. Base Inicial de Vendas (Apoio - 3 colunas)</strong><br><br>
                <span class="pill-tag">Código</span>
                <span class="pill-tag">Descrição</span>
                <span class="pill-tag">Quantidade Vendida</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        dias_base_input = st.number_input(
            "Período da base inicial (dias):",
            min_value=1,
            max_value=730,
            value=int(dias_base_atual),
            step=1,
        )
        arq_base = st.file_uploader(
            "Selecionar Base Inicial (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_base",
        )

    ignorar_trava_catalogo = st.checkbox(
        "🔓 Autorizar mudança estrutural de catálogo (ignorar trava de 80% de coincidência de códigos com o dia anterior)",
        value=False,
        help="Marque apenas se você estiver trocando de ERP ou importando uma linha de produtos totalmente nova.",
    )

    btn_sincronizar = st.button(
        "🚀 Processar e Sincronizar com Segurança",
        type="primary",
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("#### 💾 Salvar Cópia do Banco de Dados no Computador (Precaução)")
    st.caption(
        "Baixe quando quiser uma planilha Excel (`.xlsx`) com todas as abas ativas do seu banco de dados "
        "(`estoque_atual`, `custos`, `base_inicial`, `ocultos` e `meta`), ou o pacote `.zip` incluindo também os 180 dias de histórico."
    )
    col_bkp_xlsx, col_bkp_zip = st.columns(2)

    with col_bkp_xlsx:
        if not df_estoque_bruto.empty:
            if st.button("📊 Preparar Planilha do Banco (.xlsx)", use_container_width=True):
                with st.spinner("Montando planilha Excel do banco de dados..."):
                    st.session_state["bkp_db_xlsx_bytes"] = gerar_excel_banco_dados(estado)
                    st.session_state["bkp_db_xlsx_nome"] = (
                        f"Banco_Dados_Esteio_Rural_{date.today().strftime('%Y-%m-%d')}.xlsx"
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
                        f"Backup_Completo_Esteio_{date.today().strftime('%Y-%m-%d')}.zip"
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

    if btn_sincronizar:
        if not any([arq_estoque, arq_custos, arq_base]) and int(dias_base_input) == int(dias_base_atual):
            st.warning("⚠️ Selecione pelo menos uma planilha para importar ou altere o período da base.")
        else:
            abas_ja_gravadas = []
            with st.spinner("Validando colunas, códigos e saldos antes de sincronizar com o Google Sheets..."):
                try:
                    data_str = data_posicao.strftime("%Y-%m-%d")
                    mensagens_auditoria_upload = []
                    teve_alerta = False

                    codigos_ref_estoque = set(df_estoque_bruto["codigo"].unique()) if not df_estoque_bruto.empty else set()
                    codigos_ref_custos = (
                        set(df_custos["codigo"].unique())
                        if not df_custos.empty
                        else codigos_ref_estoque
                    )
                    codigos_ref_base = (
                        set(df_base_vendas["codigo"].unique())
                        if not df_base_vendas.empty
                        else codigos_ref_estoque
                    )

                    novo_estoque = None
                    novos_custos = None
                    nova_base = None

                    if arq_estoque is not None:
                        novo_estoque, info_dup_est = processar_planilha_estoque(
                            arq_estoque,
                            data_posicao,
                            codigos_ref=codigos_ref_estoque,
                            ignorar_trava_catalogo=ignorar_trava_catalogo,
                        )
                        codigos_ref_custos = codigos_ref_custos or set(novo_estoque["codigo"].unique())
                        codigos_ref_base = codigos_ref_base or set(novo_estoque["codigo"].unique())

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
                                f"✔️ **Estoque:** {formatar_num_br(info_dup_est['linhas_finais'])} linhas verificadas "
                                f"(0 duplicatas | {formatar_pct_br(info_dup_est['taxa_coincidencia'])} de códigos coincidentes)."
                            )

                    if arq_custos is not None:
                        novos_custos, info_cus = processar_planilha_custos(
                            arq_custos,
                            codigos_ref=codigos_ref_custos,
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
                                f"{formatar_num_br(info_cus['qtd_zerados']} com custo R$ 0,00 ({formatar_pct_br(pct_zero, 0)} | "
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
                            codigos_ref=codigos_ref_base,
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

                    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    if novo_estoque is not None:
                        gravar_historico_incremental_gsheets(planilha_gsheets, novo_estoque, data_str)
                        abas_ja_gravadas.append("historico")

                        gravar_aba_pequena_gsheets(planilha_gsheets, "estoque_atual", novo_estoque)
                        abas_ja_gravadas.append("estoque_atual")

                    if novos_custos is not None:
                        gravar_aba_pequena_gsheets(planilha_gsheets, "custos", novos_custos)
                        abas_ja_gravadas.append("custos")

                    if nova_base is not None:
                        gravar_aba_pequena_gsheets(planilha_gsheets, "base_inicial", nova_base)
                        abas_ja_gravadas.append("base_inicial")

                    df_meta_novo = pd.DataFrame(
                        [
                            {"chave": "dias_base", "valor": str(int(dias_base_input))},
                            {"chave": "ultima_atualizacao", "valor": agora_str},
                        ]
                    )
                    gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_novo)
                    abas_ja_gravadas.append("meta")

                    st.session_state.pop("bkp_db_xlsx_bytes", None)
                    st.session_state.pop("backup_zip_bytes", None)
                    carregar_estado_completo.clear()
                    calcular_motor_giro_sazonal.clear()

                    st.session_state["msg_sucesso_sync"] = (
                        f"✅ Dados validados e sincronizados com segurança na nuvem em {agora_str}!"
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

    r1, r2, r3, r4 = st.columns(4)
    qtd_skus_visiveis = df_estoque["codigo"].nunique() if (not df_estoque.empty and "codigo" in df_estoque.columns) else 0
    qtd_datas = df_historico_bruto["data"].nunique() if (not df_historico_bruto.empty and "data" in df_historico_bruto.columns) else 0
    qtd_custos = len(df_custos) if not df_custos.empty else 0
    r1.metric("Produtos Ativos com Saldo/Catálogo", f"{formatar_num_br(qtd_skus_visiveis)} (Ocultos: {formatar_num_br(len(codigos_ocultos))})")
    r2.metric("Dias no Histórico (Máx 180d)", f"{formatar_num_br(qtd_datas)} dia(s)")
    r3.metric("Itens com Custo Cadastrado", f"{formatar_num_br(qtd_custos)}")
    r4.metric("Última Sincronização", estado.get("ultima_atualizacao", "-"))

# ------------------------------------------------------------------------------
# ABA 2: SUGESTÃO DE COMPRAS & COTAÇÃO POR LISTA (PRECISÃO TOTAL E EDIÇÃO POR SKU)
# ------------------------------------------------------------------------------
with aba2:
    st.markdown("### 🛒 Sugestão de Compras, Giro Sazonal & Cotação por Lista")
    st.caption(
        "Catálogo unificado (inclui produtos com saldo zero que possuem histórico de vendas), precisão decimal completa no cálculo "
        "de giro, arredondamento protetivo para cima e edições vinculadas diretamente ao código do produto."
    )

    with st.expander("📋 Importar Planilha de Produtos para Cotação Direcionada (Opcional)", expanded=True):
        arq_lista_cotacao = st.file_uploader(
            "Subir planilha com Código e Nome dos produtos (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_lista_cotacao",
        )
        if arq_lista_cotacao is not None:
            st.success(
                "✅ Planilha de cotação ativa! Todos os produtos enviados abaixo serão mantidos na tabela e no Excel gerado (inclusive itens com sugestão 0)."
            )

    p1, p2, p3, p4, p5 = st.columns(5)
    janela_dias = p1.selectbox(
        "Janela de Giro (dias):",
        options=[15, 30, 45, 60, 90, 120, 180],
        index=5 if arq_lista_cotacao is not None else 1,
        help="Escolha 120 ou 180 dias para negociações de longo prazo com fornecedores.",
    )
    cobertura_desejada = p2.number_input("Cobertura Desejada (dias):", min_value=5, max_value=180, value=30)
    lead_time = p3.number_input("Lead Time / Entrega (dias):", min_value=0, max_value=90, value=7)
    fator_sazonal = p4.slider("Ajuste Sazonal Extra (%):", min_value=-50, max_value=200, value=0, step=5)
    filtro_busca = p5.text_input("Filtrar Código ou Descrição:")

    c_op1, c_op2, c_op3 = st.columns([1.5, 1.5, 1])
    with c_op1:
        incluir_zerados_com_giro = st.checkbox(
            "Incluir produtos sem estoque atual (Saldo = 0) que possuem histórico de giro",
            value=True,
        )
    with c_op2:
        arredondar_para_cima = st.checkbox(
            "Arredondar sugestão de compra para cima (garantir 100% da cobertura)",
            value=True,
        )
    with c_op3:
        if st.button("🔄 Limpar Edições Manuais da Cotação", use_container_width=True):
            st.session_state.pop("edicoes_cotacao_por_sku", None)
            st.rerun()

    df_est_fonte = df_estoque_bruto if arq_lista_cotacao is not None else df_estoque
    df_hist_fonte = df_historico_bruto if arq_lista_cotacao is not None else df_historico
    df_base_fonte = df_base_vendas if arq_lista_cotacao is not None else df_base_vendas_rel
    df_custos_fonte = df_custos if arq_lista_cotacao is not None else df_custos_rel

    if df_est_fonte.empty and df_base_fonte.empty and arq_lista_cotacao is None:
        st.info("Importe a Planilha de Estoque na Aba 1 para calcular o giro e as sugestões de compra.")
    else:
        df_base_giro, dias_hist_janela, peso_hist = calcular_motor_giro_sazonal(
            df_estoque=df_est_fonte,
            df_historico=df_hist_fonte,
            df_base_vendas=df_base_fonte,
            df_custos=df_custos_fonte,
            dias_base_atual=dias_base_atual,
            janela_dias=int(janela_dias),
            incluir_sem_estoque=True if arq_lista_cotacao is not None else incluir_zerados_com_giro,
        )
        df_calc = df_base_giro.copy()

        codigos_nao_encontrados_lista = []

        if arq_lista_cotacao is not None:
            try:
                df_lista = ler_lista_produtos_cotacao(arq_lista_cotacao)

                cods_conhecidos_erp = (
                    set(df_estoque_bruto["codigo"].unique())
                    | set(df_custos["codigo"].unique())
                    | set(df_base_vendas["codigo"].unique())
                    | set(df_historico_bruto["codigo"].unique())
                )

                mapa_sem_zero = {}
                for c_erp in cods_conhecidos_erp:
                    chave_sz = c_erp.lstrip("0") or "0"
                    if chave_sz not in mapa_sem_zero:
                        mapa_sem_zero[chave_sz] = c_erp

                df_lista["codigo"] = df_lista["codigo_lista"].apply(
                    lambda c: c if c in cods_conhecidos_erp else mapa_sem_zero.get(c.lstrip("0") or "0", c)
                )

                mask_inexistente = ~df_lista["codigo"].isin(cods_conhecidos_erp)
                if mask_inexistente.any():
                    codigos_nao_encontrados_lista = df_lista.loc[mask_inexistente, "codigo_lista"].tolist()

                df_merged = df_lista.merge(df_calc, on="codigo", how="left")
                df_merged["descricao"] = df_merged["descricao"].fillna("")
                df_merged["descricao"] = df_merged["descricao"].where(
                    df_merged["descricao"] != "", df_merged["descricao_lista"]
                )
                df_merged["saldo_atual"] = df_merged["saldo_atual"].fillna(0.0)
                df_merged["giro_base"] = df_merged["giro_base"].fillna(0.0)
                df_merged["giro_historico"] = df_merged["giro_historico"].fillna(0.0)
                df_merged["giro_ponderado"] = df_merged["giro_ponderado"].fillna(0.0)
                df_merged["tendencia"] = df_merged["tendencia"].fillna(
                    df_merged["codigo"].apply(
                        lambda c: "⚠️ Não Cadastrado no ERP" if c not in cods_conhecidos_erp else "➡️ Sem Histórico"
                    )
                )
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

        df_calc["giro_diario"] = (df_calc["giro_ponderado"] * (1.0 + (fator_sazonal / 100.0))).clip(lower=0.0)

        if not df_custos.empty:
            df_calc = df_calc.merge(
                df_custos[["codigo", "custo_unitario"]], on="codigo", how="left"
            )
            df_calc["custo_unitario"] = df_calc["custo_unitario"].fillna(0.0)
        else:
            df_calc["custo_unitario"] = 0.0

        df_abc_unificado = calcular_tabela_curva_abc(df_estoque, df_custos)
        mapa_abc = (
            dict(zip(df_abc_unificado["codigo"], df_abc_unificado["classe_abc_curta"]))
            if not df_abc_unificado.empty
            else {}
        )

        df_calc["classe_abc_tendencia"] = df_calc.apply(
            lambda r: (
                "⚠️ Não Cadastrado no ERP"
                if r["tendencia"] == "⚠️ Não Cadastrado no ERP"
                else f"{mapa_abc.get(r['codigo'], 'Sem Classe')} | {r['tendencia']}"
            ),
            axis=1,
        )

        mapa_venc_60d = {}
        if not df_est_fonte.empty:
            df_lotes_pos = df_est_fonte[df_est_fonte["saldo_lote"] > 0].copy()
            if not df_lotes_pos.empty:
                df_lotes_pos["dt_val"] = converter_datas_deterministico(df_lotes_pos["validade"])
                dias_venc = (df_lotes_pos["dt_val"] - pd.Timestamp(date.today())).dt.days
                df_curto = df_lotes_pos[dias_venc.notna() & (dias_venc <= 60)]
                if not df_curto.empty:
                    mapa_venc_60d = df_curto.groupby("codigo")["saldo_lote"].sum().to_dict()

        df_calc["vencendo_60d"] = df_calc["codigo"].map(mapa_venc_60d).fillna(0.0)

        dias_totais_nec = cobertura_desejada + lead_time
        df_calc["estoque_ideal"] = df_calc["giro_diario"] * float(dias_totais_nec)
        necessidade_bruta = (df_calc["estoque_ideal"] - df_calc["saldo_atual"]).clip(lower=0.0)

        if arredondar_para_cima:
            df_calc["sugestao_compra"] = necessidade_bruta.apply(lambda x: float(math.ceil(x - 1e-9)) if x > 0 else 0.0)
        else:
            df_calc["sugestao_compra"] = necessidade_bruta.round(0)

        df_calc["autonomia_dias"] = (
            (df_calc["saldo_atual"] / df_calc["giro_diario"].replace(0.0, pd.NA))
            .fillna(999.0)
            .round(1)
        )

        if filtro_busca:
            termo = filtro_busca.lower().strip()
            df_calc = df_calc[
                df_calc["codigo"].str.lower().str.contains(termo, na=False)
                | df_calc["descricao"].str.lower().str.contains(termo, na=False)
            ]

        if arq_lista_cotacao is None:
            df_calc["_inv_ord"] = df_calc["sugestao_compra"] * df_calc["custo_unitario"]
            df_compras = df_calc.sort_values(["_inv_ord", "descricao"], ascending=[False, True]).drop(columns=["_inv_ord"])
        else:
            df_compras = df_calc.copy()

        if "edicoes_cotacao_por_sku" not in st.session_state:
            st.session_state["edicoes_cotacao_por_sku"] = {}
        memoria_sku = st.session_state["edicoes_cotacao_por_sku"]

        qtd_inicial_lista = []
        custo_cotado_lista = []
        for _, r_item in df_compras.iterrows():
            cod_k = r_item["codigo"]
            sug_k = float(r_item["sugestao_compra"])
            if cod_k in memoria_sku:
                salvo = memoria_sku[cod_k]
                qtd_inicial_lista.append(salvo.get("qtd", sug_k))
                custo_cotado_lista.append(salvo.get("custo", 0.0))
            else:
                qtd_inicial_lista.append(sug_k)
                custo_cotado_lista.append(0.0)

        df_editor_input = pd.DataFrame(
            {
                "Código": df_compras["codigo"].values,
                "Descrição": df_compras["descricao"].values,
                "Classe ABC & Tendência": df_compras["classe_abc_tendencia"].values,
                "Saldo Atual": df_compras["saldo_atual"].values,
                "Vencido ou vencendo (≤60d)": df_compras["vencendo_60d"].values,
                "Giro Médio/Dia": df_compras["giro_diario"].values,
                "Autonomia (Dias)": df_compras["autonomia_dias"].values,
                "Sugestão Sistema": df_compras["sugestao_compra"].values,
                "Qtd. a Comprar": qtd_inicial_lista,
                "Último Custo ERP (R$)": df_compras["custo_unitario"].values,
                "Custo Atual / Cotado (R$)": custo_cotado_lista,
            }
        ).set_index("Código")

        st.markdown(
            "##### ✏️ Simulador de Cotação: edite a **Qtd. a Comprar** e o **Custo Atual / Cotado (R$)** (valores preservados por Código de SKU):"
        )

        styler_editor = estilizar_tabela_br(
            df_editor_input,
            formatadores={
                "Saldo Atual": formatar_qtd_br,
                "Vencido ou vencendo (≤60d)": formatar_qtd_br,
                "Giro Médio/Dia": lambda x: formatar_num_br(x, 3) if (pd.notna(x) and 0 < float(x) < 0.05) else formatar_num_br(x, 2),
                "Autonomia (Dias)": lambda x: "Sem Giro" if pd.notna(x) and float(x) >= 999.0 else formatar_num_br(x, 1),
                "Sugestão Sistema": formatar_qtd_br,
                "Qtd. a Comprar": formatar_qtd_br,
                "Último Custo ERP (R$)": formatar_moeda_br,
                "Custo Atual / Cotado (R$)": formatar_moeda_br,
            },
            colunas_esquerda=["Descrição"],
        )

        df_editado_idx = st.data_editor(
            styler_editor,
            hide_index=False,
            use_container_width=True,
            height=430,
            key=f"editor_cotacao_aba2_{janela_dias}_{cobertura_desejada}_{lead_time}_{fator_sazonal}",
            disabled=[
                "Descrição",
                "Classe ABC & Tendência",
                "Saldo Atual",
                "Vencido ou vencendo (≤60d)",
                "Giro Médio/Dia",
                "Autonomia (Dias)",
                "Sugestão Sistema",
                "Último Custo ERP (R$)",
            ],
            column_config={
                "Código": st.column_config.TextColumn("Código"),
                "Qtd. a Comprar": st.column_config.NumberColumn(
                    "✏️ Qtd. a Comprar", min_value=0, step=1
                ),
                "Custo Atual / Cotado (R$)": st.column_config.NumberColumn(
                    "✏️ Custo Atual / Cotado (R$)",
                    min_value=0.0,
                    step=0.01,
                    help="Deixe 0,00 para usar o Último Custo ERP ou digite o preço novo informado pelo fornecedor.",
                ),
            },
        )

        df_editado = df_editado_idx.reset_index()

        for _, r_ed in df_editado.iterrows():
            cod_ed = str(r_ed["Código"])
            sug_ed = float(r_ed["Sugestão Sistema"])
            qtd_ed = float(pd.to_numeric(r_ed["Qtd. a Comprar"], errors="coerce") or 0.0)
            cus_ed = float(pd.to_numeric(r_ed["Custo Atual / Cotado (R$)"], errors="coerce") or 0.0)
            if abs(qtd_ed - sug_ed) > 0.001 or cus_ed > 0.0:
                memoria_sku[cod_ed] = {"qtd": qtd_ed, "custo": cus_ed}
            elif cod_ed in memoria_sku:
                memoria_sku.pop(cod_ed, None)

        custo_erp_s = pd.to_numeric(df_editado["Último Custo ERP (R$)"], errors="coerce").fillna(0.0)
        custo_novo_s = pd.to_numeric(df_editado["Custo Atual / Cotado (R$)"], errors="coerce").fillna(0.0)
        qtd_comprar_s = pd.to_numeric(df_editado["Qtd. a Comprar"], errors="coerce").fillna(0.0)

        custo_efetivo_s = custo_novo_s.where(custo_novo_s > 0.0, custo_erp_s)
        variacao_pct_s = (
            ((custo_novo_s - custo_erp_s) / custo_erp_s.replace(0.0, pd.NA)) * 100.0
        ).where((custo_novo_s > 0.0) & (custo_erp_s > 0.0), 0.0).fillna(0.0).round(1)
        total_item_s = (qtd_comprar_s * custo_efetivo_s).round(2)

        df_completo_13_cols = df_editado.copy()
        df_completo_13_cols["Variação Custo (%)"] = variacao_pct_s
        df_completo_13_cols["Total do Item (R$)"] = total_item_s

        m1, m2, m3, m4 = st.columns(4)
        itens_com_pedido = int((qtd_comprar_s > 0).sum())
        orcamento_total = float(total_item_s.sum())
        m1.metric("Produtos Listados", f"{formatar_num_br(len(df_completo_13_cols))} SKUs (Comprar: {formatar_num_br(itens_com_pedido)})")
        m2.metric("Orçamento Total do Pedido", formatar_moeda_br(orcamento_total))
        m3.metric("Janela de Giro / Proteção", f"{janela_dias}d Giro | {dias_totais_nec}d Cobertura")
        m4.metric(
            "Peso Histórico vs Base",
            f"{int(round(peso_hist * 100))}% Hist. / {int(round((1 - peso_hist) * 100))}% Base",
            help=f"Calculado sobre {dias_hist_janela} dia(s) corridos na janela de {janela_dias} dias.",
        )

        with st.expander("👁️ Visualizar Tabela Final Completa com Total por Item (13 Colunas Centralizadas)", expanded=False):
            st.dataframe(
                estilizar_tabela_br(
                    df_completo_13_cols,
                    formatadores={
                        "Saldo Atual": formatar_qtd_br,
                        "Vencido ou vencendo (≤60d)": formatar_qtd_br,
                        "Giro Médio/Dia": lambda x: formatar_num_br(x, 3) if (pd.notna(x) and 0 < float(x) < 0.05) else formatar_num_br(x, 2),
                        "Autonomia (Dias)": lambda x: "Sem Giro" if pd.notna(x) and float(x) >= 999.0 else formatar_num_br(x, 1),
                        "Sugestão Sistema": formatar_qtd_br,
                        "Qtd. a Comprar": formatar_qtd_br,
                        "Último Custo ERP (R$)": formatar_moeda_br,
                        "Custo Atual / Cotado (R$)": lambda x: "-" if pd.isna(x) or float(x) <= 0 else formatar_moeda_br(x),
                        "Variação Custo (%)": lambda x: formatar_pct_br(x, 1, com_sinal=True),
                        "Total do Item (R$)": formatar_moeda_br,
                    },
                    colunas_esquerda=["Descrição"],
                ),
                use_container_width=True,
                hide_index=True,
            )

        if not df_completo_13_cols.empty:
            st.download_button(
                label="📥 Baixar Planilha de Sugestão & Cotação (.xlsx com 13 Colunas Centralizadas e Fórmulas Vivas)",
                data=gerar_excel_com_formulas_cotacao(df_completo_13_cols),
                file_name=f"Cotacao_Compras_Esteio_{janela_dias}d_{date.today().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )

# ------------------------------------------------------------------------------
# ABA 3: RADAR DE VALIDADES (FEFO DETERMINÍSTICO E CENTRALIZADO)
# ------------------------------------------------------------------------------
with aba3:
    st.markdown("### ⏳ Radar de Validades — Gestão FEFO (Primeiro que Vence, Primeiro que Sai)")
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 1 para monitorar os lotes e validades.")
    else:
        df_fefo = df_estoque[df_estoque["saldo_lote"] > 0].copy()
        if not df_custos.empty:
            df_fefo = df_fefo.merge(df_custos[["codigo", "custo_unitario"]], on="codigo", how="left")
            df_fefo["custo_unitario"] = df_fefo["custo_unitario"].fillna(0.0)
        else:
            df_fefo["custo_unitario"] = 0.0

        df_fefo["dt_validade"] = converter_datas_deterministico(df_fefo["validade"])

        hoje_ts = pd.Timestamp(date.today())
        df_fefo["dias_para_vencer"] = (df_fefo["dt_validade"] - hoje_ts).dt.days
        df_fefo["valor_em_risco"] = df_fefo["saldo_lote"] * df_fefo["custo_unitario"]

        def classificar_fefo(dias):
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

        df_fefo["status_fefo"] = df_fefo["dias_para_vencer"].apply(classificar_fefo)

        v1, v2, v3, v4 = st.columns(4)
        vlr_vencido = df_fefo.loc[df_fefo["status_fefo"] == "🔴 1. Vencido", "valor_em_risco"].sum()
        vlr_30d = df_fefo.loc[df_fefo["status_fefo"] == "🟠 2. Crítico (0 a 30 dias)", "valor_em_risco"].sum()
        vlr_60d = df_fefo.loc[df_fefo["status_fefo"] == "🟡 3. Atenção (31 a 60 dias)", "valor_em_risco"].sum()
        vlr_90d = df_fefo.loc[df_fefo["status_fefo"] == "🔵 4. Preventivo (61 a 90 dias)", "valor_em_risco"].sum()

        v1.metric("🔴 Vencidos", formatar_moeda_br(vlr_vencido))
        v2.metric("🟠 Vencendo em 30 dias", formatar_moeda_br(vlr_30d))
        v3.metric("🟡 Vencendo em 31-60 dias", formatar_moeda_br(vlr_60d))
        v4.metric("🔵 Vencendo em 61-90 dias", formatar_moeda_br(vlr_90d))

        opcoes_status = sorted(df_fefo["status_fefo"].unique())
        padrao_status = [s for s in opcoes_status if not s.startswith("🟢")] or opcoes_status
        filtro_status = st.multiselect(
            "Filtrar faixas de vencimento:",
            options=opcoes_status,
            default=padrao_status,
        )

        df_fefo_view = df_fefo[df_fefo["status_fefo"].isin(filtro_status)].sort_values(
            "dias_para_vencer", ascending=True
        )

        df_fefo_exibicao = df_fefo_view[
            [
                "status_fefo",
                "codigo",
                "descricao",
                "lote",
                "validade",
                "dias_para_vencer",
                "saldo_geral",
                "saldo_lote",
                "valor_em_risco",
            ]
        ].rename(
            columns={
                "status_fefo": "Faixa FEFO",
                "codigo": "Código",
                "descricao": "Descrição",
                "lote": "Código do Lote",
                "validade": "Validade",
                "dias_para_vencer": "Dias p/ Vencer",
                "saldo_geral": "Saldo Geral (SKU)",
                "saldo_lote": "Saldo do Lote",
                "valor_em_risco": "Capital no Lote (R$)",
            }
        )

        st.dataframe(
            estilizar_tabela_br(
                df_fefo_exibicao,
                formatadores={
                    "Dias p/ Vencer": lambda x: "-" if pd.isna(x) else formatar_num_br(x, 0),
                    "Saldo Geral (SKU)": formatar_qtd_br,
                    "Saldo do Lote": formatar_qtd_br,
                    "Capital no Lote (R$)": formatar_moeda_br,
                },
                colunas_esquerda=["Descrição"],
            ),
            use_container_width=True,
            hide_index=True,
        )

        if not df_fefo_exibicao.empty:
            st.download_button(
                label="📥 Baixar Relatório FEFO (.xlsx)",
                data=gerar_excel_relatorio(df_fefo_exibicao, "Radar_FEFO"),
                file_name=f"Radar_Validades_FEFO_{date.today().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ------------------------------------------------------------------------------
# ABA 4: CURVA ABC FINANCEIRA (UNIFICADA E CENTRALIZADA)
# ------------------------------------------------------------------------------
with aba4:
    st.markdown("### 📊 Curva ABC Financeira (Pareto 80 / 15 / 5)")
    if df_estoque.empty or df_custos.empty:
        st.info("Importe a Planilha de Estoque e a Planilha de Custos na Aba 1 para gerar a Curva ABC Financeira.")
    else:
        df_abc = calcular_tabela_curva_abc(df_estoque, df_custos)
        if not df_abc.empty:
            total_fin = float(df_abc["valor_estoque"].sum())
            qtd_classe_a = int((df_abc["classe_abc_curta"] == "Classe A").sum())
            qtd_classe_bc = int((df_abc["classe_abc_curta"] != "Classe A").sum())

            a1, a2, a3 = st.columns(3)
            a1.metric("Capital Total Imobilizado", formatar_moeda_br(total_fin))
            a2.metric("Itens Classe A (80% do Valor)", f"{formatar_num_br(qtd_classe_a)} SKUs")
            a3.metric("Itens Classe B + C", f"{formatar_num_br(qtd_classe_bc)} SKUs")

            df_abc_exibicao = df_abc[
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

            st.download_button(
                label="📥 Baixar Curva ABC (.xlsx)",
                data=gerar_excel_relatorio(df_abc_exibicao, "Curva_ABC"),
                file_name=f"Curva_ABC_Esteio_{date.today().strftime('%Y-%m-%d')}.xlsx",
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
                file_name=f"Auditoria_Divergencias_Lotes_{date.today().strftime('%Y-%m-%d')}.xlsx",
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

    # --- COLUNA DA ESQUERDA: PRODUTOS VISÍVEIS PARA OCULTAR ---
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
                    df_visiveis["codigo"].str.lower().str.contains(termo_v, na=False)
                    | df_visiveis["descricao"].str.lower().str.contains(termo_v, na=False)
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
                        novos_ocultos["data_ocultado"] = date.today().strftime("%Y-%m-%d")

                        df_ocultos_atualizado = (
                            pd.concat([df_ocultos, novos_ocultos], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
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

    # --- COLUNA DA DIREITA: PRODUTOS OCULTOS PARA RESTAURAR ---
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
                    df_oc_view["codigo"].str.lower().str.contains(termo_o, na=False)
                    | df_oc_view["descricao"].str.lower().str.contains(termo_o, na=False)
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

