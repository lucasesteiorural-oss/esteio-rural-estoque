import os
import io
import json
import glob
import re
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
# 1.1 CONTROLE DE ACESSO POR SENHA (PROTEÇÃO DA NUVEM)
# ==============================================================================
def verificar_autenticacao() -> bool:
    """
    Bloqueia o aplicativo caso 'app_password' esteja definido em st.secrets.
    Se ainda não estiver definido, exibe um lembrete de segurança e permite o uso.
    """
    senha_correta = str(st.secrets.get("app_password", "")).strip()
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
# 2. DIRETÓRIOS, ESQUEMAS E PRESERVAÇÃO DE ZEROS À ESQUERDA
# ==============================================================================
PASTA_DADOS = "dados_esteio"
PASTA_BACKUPS = "backups_esteio"
os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_BACKUPS, exist_ok=True)

ARQUIVO_LOCAL = os.path.join(PASTA_DADOS, "estado_esteio.json")
DIAS_MAX_HISTORICO = 180
TAMANHO_LOTE_MIGRACAO = 4000 # ~0,18 MB por requisição (bem abaixo do limite de 2 MB do Google)

COLUNAS_NUMERICAS = {"saldo_geral", "saldo_lote", "custo_unitario", "qtd_vendida"}

ESQUEMA_ABAS = {
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


def normalizar_chave_coluna(nome: str) -> str:
    s = unicodedata.normalize("NFKD", str(nome)).encode("ASCII", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.lower()).strip("_")
    return s


def limpar_serie_texto(serie: pd.Series) -> pd.Series:
    """Limpeza vetorizada rápida que preserva zeros à esquerda e remove sufixos '.0' de inteiros."""
    s = serie.fillna("").astype(str).str.strip()
    s = s.where(~s.str.lower().isin(["nan", "none", "nat", "<na>"]), "")
    return s.str.replace(r"^(\d+)\.0$", r"\1", regex=True)


def converter_numero_br(serie: pd.Series) -> pd.Series:
    """Converte números em formato brasileiro (1.234,56) ou americano (1234.56) para float."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0.0).astype(float)

    def _parse(val):
        if pd.isna(val) or val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace("R$", "").replace(" ", "")
        if not s or s.lower() in {"nan", "none"}:
            return 0.0
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    return serie.apply(_parse).astype(float)


def converter_datas_deterministico(serie: pd.Series) -> pd.Series:
    """
    Converte datas testando formatos explícitos em ordem fixa.
    Impede que o Pandas adivinhe pela 1ª linha e troque dia por mês dependendo da ordem do ERP.
    """
    s_limpa = serie.fillna("").astype(str).str.strip().str.split(" ").str[0]
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
    """Garante que códigos e lotes fiquem como texto puro (preservando zeros) e saldos/custos como float."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        if col in COLUNAS_NUMERICAS:
            df[col] = converter_numero_br(df[col])
        else:
            df[col] = limpar_serie_texto(df[col])
    return df


def padronizar_dataframe(df: pd.DataFrame, nome_aba: str) -> pd.DataFrame:
    """
    Padroniza cabeçalhos, garante tipos corretos e elimina linhas duplicadas de (codigo, lote, data)
    para que uma limpeza interrompida nunca duplique saldos nem gere giro falso.
    """
    colunas_esperadas = ESQUEMA_ABAS.get(nome_aba, [])
    if df is None or df.empty:
        df_vazio = pd.DataFrame(columns=colunas_esperadas)
        return restaurar_tipos(df_vazio)

    df = df.loc[:, ~df.columns.duplicated()].copy()
    cols_norm = {col: normalizar_chave_coluna(col) for col in df.columns}

    renomear = {}
    colunas_usadas = set()

    for col_alvo in colunas_esperadas:
        sinonimos = MAPA_SINONIMOS.get(col_alvo, [col_alvo])
        for sin in sinonimos:
            encontrada = None
            for col_orig, norm in cols_norm.items():
                if col_orig not in colunas_usadas and norm == sin:
                    encontrada = col_orig
                    break
            if encontrada is not None:
                renomear[encontrada] = col_alvo
                colunas_usadas.add(encontrada)
                break

    df = df.rename(columns=renomear)

    if "codigo" in colunas_esperadas and "codigo" not in df.columns:
        if nome_aba == "estoque_atual" and df.shape[1] >= 6:
            novos_nomes = ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade"]
            if df.shape[1] >= 7:
                novos_nomes.append("data")
            df_pos = df.iloc[:, : len(novos_nomes)].copy()
            df_pos.columns = novos_nomes
            df = df_pos
        elif nome_aba == "historico" and df.shape[1] >= 5:
            if df.shape[1] >= 7:
                df_pos = df.iloc[:, :7].copy()
                df_pos.columns = ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"]
            else:
                df_pos = df.iloc[:, :5].copy()
                df_pos.columns = ["codigo", "saldo_geral", "lote", "saldo_lote", "data"]
            df = df_pos
        elif nome_aba == "custos" and df.shape[1] >= 3:
            df = df.iloc[:, :3].copy()
            df.columns = ["codigo", "descricao", "custo_unitario"]
        elif nome_aba == "base_inicial" and df.shape[1] >= 3:
            df = df.iloc[:, :3].copy()
            df.columns = ["codigo", "descricao", "qtd_vendida"]
        elif nome_aba == "ocultos" and df.shape[1] >= 2:
            df = df.iloc[:, :2].copy()
            df.columns = ["codigo", "descricao"]

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

    if nome_aba in ("estoque_atual", "historico"):
        df = df.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
    elif nome_aba in ("custos", "ocultos"):
        df = df.drop_duplicates(subset=["codigo"], keep="last")

    return df.reset_index(drop=True)


def podar_historico_180_dias(df_hist: pd.DataFrame) -> pd.DataFrame:
    """Mantém apenas os últimos 180 dias de histórico e garante ausência de duplicatas."""
    if df_hist is None or df_hist.empty or "data" not in df_hist.columns:
        return padronizar_dataframe(pd.DataFrame(), "historico")
    limite_str = (date.today() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")
    df_filtrado = df_hist[df_hist["data"] >= limite_str].copy()
    df_filtrado = df_filtrado.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
    return df_filtrado.reset_index(drop=True)


# ==============================================================================
# 3. CONEXÃO COM GOOGLE SHEETS (SEM CACHE DE ERRO + MIGRAÇÃO EM LOTES)
# ==============================================================================
@st.cache_resource(ttl=3600, show_spinner=False)
def _conectar_planilha_cached(nome_planilha: str):
    """
    Autentica e abre a planilha. Se falhar, LANÇA EXCEÇÃO para que o Streamlit
    JAMAIS guarde um erro de rede em cache por 1 hora.
    """
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
    """Retorna (planilha, None) ou (None, mensagem_de_erro) sem cachear falhas."""
    if "gcp_service_account" not in st.secrets:
        return None, "Bloco [gcp_service_account] ausente em st.secrets"
    try:
        nome_planilha = st.secrets.get("sheet_name", "Banco_Dados_Esteio_Rural")
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
    """Lê todas as células como texto puro (get_all_values) e já padroniza/desduplica uma única vez."""
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
    """
    Sobrescreve abas pequenas (estoque_atual, custos, base_inicial, ocultos, meta) a partir de A1
    SEM chamar clear() antes, redimensionando a aba somente após o término do envio.
    """
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

    ws = obter_ou_criar_aba(
        planilha, nome_aba, len(dados) + 10, max(len(cabecalho), 1) + 2
    )
    ws.update(values=dados, range_name="A1", value_input_option="RAW")
    ws.resize(rows=max(len(dados), 2), cols=max(len(cabecalho), 1))


def migrar_historico_em_lotes_seguros(planilha, ws_antiga, df_combinado: pd.DataFrame):
    """
    Migra um histórico antigo de 7 colunas para o novo formato de 5 colunas fatiando em blocos
    de 4.000 linhas (~0,18 MB por chamada) em uma aba temporária antes de substituir a antiga.
    Nunca envia >2 MB de uma só vez e nunca apaga os dados antigos antes de concluir a cópia.
    """
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
    """
    Grava no histórico usando estratégia APPEND-FIRST (Grava Primeiro, Apaga Depois):
    1. Anexa primeiro as novas linhas do dia (~5 colunas enxutas).
    2. Só depois que a gravação teve sucesso, remove as linhas antigas daquela mesma data
       e poda registros com mais de 180 dias.
    """
    if df_novo_dia is None or df_novo_dia.empty:
        return

    df_novo_padrao = padronizar_dataframe(df_novo_dia, "historico")
    df_str = df_novo_padrao.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    linhas_novas = df_str.values.tolist()

    ws = obter_ou_criar_aba(
        planilha, "historico", len(linhas_novas) + 100, len(cabecalho) + 2
    )
    primeira_linha = [str(c).strip() for c in ws.row_values(1)]

    if not primeira_linha:
        ws.update(
            values=[cabecalho] + linhas_novas,
            range_name="A1",
            value_input_option="RAW",
        )
        return

    limite_str = (date.today() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")

    # Se a aba ainda estiver no formato antigo de 7 colunas, migra em lotes pequenos (<0,2 MB)
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

    linhas_antigas_para_apagar = [
        i
        for i, val in enumerate(col_datas_antes, start=1)
        if i >= 2 and (str(val).strip() == str(data_ref).strip() or str(val).strip() < limite_str)
    ]

    # 1. GRAVA PRIMEIRO (Append-First)
    ws.append_rows(values=linhas_novas, value_input_option="RAW")

    # 2. APAGA DEPOIS (de baixo para cima, sem afetar o que foi anexado no rodapé)
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


# ==============================================================================
# 4. PERSISTÊNCIA INTELIGENTE E BACKUP COMPACTADO (.ZIP COM CSV + EXCEL LEVE)
# ==============================================================================
def salvar_espelho_e_backup_local(estado: dict, conectado_nuvem: bool = False):
    """Se estiver conectado ao Google Sheets, NÃO grava JSON pesado no disco temporário da nuvem."""
    if conectado_nuvem:
        return

    payload = {
        "estoque_atual": estado.get("estoque_atual", pd.DataFrame()).to_dict(orient="records"),
        "historico": podar_historico_180_dias(estado.get("historico", pd.DataFrame())).to_dict(orient="records"),
        "custos": estado.get("custos", pd.DataFrame()).to_dict(orient="records"),
        "base_inicial": estado.get("base_inicial", pd.DataFrame()).to_dict(orient="records"),
        "ocultos": estado.get("ocultos", pd.DataFrame()).to_dict(orient="records"),
        "dias_base": int(estado.get("dias_base", 87)),
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    temp_local = f"{ARQUIVO_LOCAL}.tmp"
    with open(temp_local, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(temp_local, ARQUIVO_LOCAL)

    hoje_str = datetime.now().strftime("%Y-%m-%d")
    arq_backup = os.path.join(PASTA_BACKUPS, f"backup_{hoje_str}.json")
    temp_bkp = f"{arq_backup}.tmp"
    with open(temp_bkp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(temp_bkp, arq_backup)

    backups = sorted(glob.glob(os.path.join(PASTA_BACKUPS, "backup_*.json")))
    while len(backups) > 7:
        try:
            os.remove(backups.pop(0))
        except OSError:
            pass


def carregar_espelho_local() -> dict:
    """Lê o estado salvo em disco apenas quando não há conexão com o Google Sheets."""
    estado_vazio = {
        "estoque_atual": padronizar_dataframe(pd.DataFrame(), "estoque_atual"),
        "historico": padronizar_dataframe(pd.DataFrame(), "historico"),
        "custos": padronizar_dataframe(pd.DataFrame(), "custos"),
        "base_inicial": padronizar_dataframe(pd.DataFrame(), "base_inicial"),
        "ocultos": padronizar_dataframe(pd.DataFrame(), "ocultos"),
        "dias_base": 87,
        "ultima_atualizacao": "Sem registros",
    }
    if not os.path.exists(ARQUIVO_LOCAL):
        return estado_vazio
    try:
        with open(ARQUIVO_LOCAL, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "estoque_atual": padronizar_dataframe(pd.DataFrame(d.get("estoque_atual", [])), "estoque_atual"),
            "historico": podar_historico_180_dias(
                padronizar_dataframe(pd.DataFrame(d.get("historico", [])), "historico")
            ),
            "custos": padronizar_dataframe(pd.DataFrame(d.get("custos", [])), "custos"),
            "base_inicial": padronizar_dataframe(pd.DataFrame(d.get("base_inicial", [])), "base_inicial"),
            "ocultos": padronizar_dataframe(pd.DataFrame(d.get("ocultos", [])), "ocultos"),
            "dias_base": int(d.get("dias_base", 87)),
            "ultima_atualizacao": d.get("ultima_atualizacao", "Local"),
        }
    except Exception:
        return estado_vazio


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_estado_completo() -> dict:
    """
    Fonte Única da Verdade: Lê do Google Sheets, padroniza e desduplica UMA ÚNICA VEZ,
    mantendo o resultado pronto em cache por 1 hora.
    """
    planilha, erro = obter_planilha_gsheets()
    if planilha is not None:
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

    if "gcp_service_account" in st.secrets:
        raise RuntimeError(f"Não foi possível conectar ao Google Sheets: {erro}")

    return carregar_espelho_local()


def gerar_pacote_backup_leve(estado: dict) -> bytes:
    """
    Gera um pacote .ZIP ultraleve (~2 segundos e <20 MB de RAM mesmo com 180 dias):
    - 'Tabelas_Atuais_Esteio.xlsx': Excel apenas com as abas pequenas (estoque_atual, custos, base_inicial, ocultos).
    - 'historico_180d.csv': Histórico completo em CSV compactado (evita o estouro de 685 MB do openpyxl).
    """
    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Excel rápido só com as abas pequenas
        buffer_xlsx = io.BytesIO()
        with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
            estado.get("estoque_atual", pd.DataFrame()).to_excel(writer, sheet_name="estoque_atual", index=False)
            estado.get("custos", pd.DataFrame()).to_excel(writer, sheet_name="custos", index=False)
            estado.get("base_inicial", pd.DataFrame()).to_excel(writer, sheet_name="base_inicial", index=False)
            estado.get("ocultos", pd.DataFrame()).to_excel(writer, sheet_name="ocultos", index=False)
        zf.writestr("Tabelas_Atuais_Esteio.xlsx", buffer_xlsx.getvalue())

        # 2. Histórico em CSV compactado dentro do ZIP
        df_hist = estado.get("historico", pd.DataFrame())
        csv_bytes = df_hist.to_csv(index=False, sep=";").encode("utf-8-sig")
        zf.writestr("historico_180d.csv", csv_bytes)

    return buffer_zip.getvalue()


# ==============================================================================
# 5. LEITURA DE UPLOADS (COM DETECÇÃO VISÍVEL DE DUPLICATAS) E MOTOR DE GIRO
# ==============================================================================
def ler_arquivo_upload(arquivo) -> pd.DataFrame:
    """Lê arquivos .xlsx ou .csv forçando dtype=str para jamais perder zeros à esquerda."""
    nome = arquivo.name.lower()
    if nome.endswith(".csv"):
        conteudo = arquivo.getvalue()
        for enc in ["utf-8-sig", "latin1", "cp1252"]:
            for sep in [";", ",", "\t"]:
                try:
                    df = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=enc, dtype=str)
                    if df.shape[1] >= 2:
                        return df
                except Exception:
                    continue
        raise ValueError("Não foi possível ler o arquivo CSV. Verifique o separador.")
    else:
        return pd.read_excel(arquivo, dtype=str)


def processar_planilha_estoque(arquivo, data_pos: date) -> tuple[pd.DataFrame, dict]:
    """
    Processa a planilha de estoque e retorna (df_padronizado, relatorio_duplicatas)
    para avisar na tela caso o ERP tenha exportado linhas repetidas de (codigo, lote).
    """
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 6:
        raise ValueError(
            f"A planilha de estoque precisa ter pelo menos 6 colunas (encontradas: {df_raw.shape[1]})."
        )

    df = pd.DataFrame()
    df["codigo"] = limpar_serie_texto(df_raw.iloc[:, 0])
    df["saldo_geral"] = converter_numero_br(df_raw.iloc[:, 1])
    df["descricao"] = limpar_serie_texto(df_raw.iloc[:, 2])
    df["lote"] = limpar_serie_texto(df_raw.iloc[:, 3])
    df["saldo_lote"] = converter_numero_br(df_raw.iloc[:, 4])
    df["validade"] = limpar_serie_texto(df_raw.iloc[:, 5])
    df["data"] = data_pos.strftime("%Y-%m-%d")

    df = df[df["codigo"] != ""].copy()
    df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod", "total"])].copy()

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
    }
    return df_final, info_dup


def processar_planilha_custos(arquivo) -> tuple[pd.DataFrame, int]:
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 3:
        raise ValueError("A planilha de custos precisa ter pelo menos 3 colunas (Código, Descrição, Custo).")

    df = pd.DataFrame()
    df["codigo"] = limpar_serie_texto(df_raw.iloc[:, 0])
    df["descricao"] = limpar_serie_texto(df_raw.iloc[:, 1])
    df["custo_unitario"] = converter_numero_br(df_raw.iloc[:, 2])

    df = df[df["codigo"] != ""].copy()
    df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod", "total"])].copy()
    qtd_dup_custos = int(df.duplicated(subset=["codigo"], keep="last").sum())

    return padronizar_dataframe(df, "custos"), qtd_dup_custos


def processar_planilha_base_vendas(arquivo) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 3:
        raise ValueError("A Base Inicial de Vendas precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade).")

    df = pd.DataFrame()
    df["codigo"] = limpar_serie_texto(df_raw.iloc[:, 0])
    df["descricao"] = limpar_serie_texto(df_raw.iloc[:, 1])
    df["qtd_vendida"] = converter_numero_br(df_raw.iloc[:, 2])

    df = padronizar_dataframe(df, "base_inicial")
    if not df.empty:
        df = df.groupby(["codigo", "descricao"], as_index=False)["qtd_vendida"].sum()
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_motor_giro_sazonal(
    df_estoque: pd.DataFrame,
    df_historico: pd.DataFrame,
    df_base_vendas: pd.DataFrame,
    dias_base_atual: int,
    janela_dias: int,
) -> tuple[pd.DataFrame, int, float]:
    """
    Motor Completo de Giro Sazonal (EM CACHE E VETORIZADO):
    - Desduplica (codigo, lote, data) mantendo o registro mais recente (imune a dia duplicado).
    - Calcula quedas diárias por lote dentro da janela (15 a 90 dias).
    - Aplica peso gradual automático e classifica a tendência sem recalcular a cada clique.
    """
    df_prod = (
        df_estoque.groupby("codigo", as_index=False)
        .agg(
            descricao=("descricao", "first"),
            saldo_atual=("saldo_geral", "first"),
        )
    )

    if not df_base_vendas.empty:
        df_prod = df_prod.merge(
            df_base_vendas[["codigo", "qtd_vendida"]], on="codigo", how="left"
        )
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
            intervalo_historico_dias = max(int((d_fim - d_ini).days), len(datas_win) - 1, 1)
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
            ).fillna(0.0)
            pivot_lotes = pivot_lotes[datas_win]

            deltas = pivot_lotes.diff(axis=1)
            quedas = deltas.where(deltas < 0.0, 0.0).abs()

            quedas_por_sku = quedas.groupby(level="codigo").sum()
            saida_total = quedas_por_sku.sum(axis=1)

            cols_transicao = datas_win[1:]
            meio = max(len(cols_transicao) // 2, 1)
            cols_antigas = cols_transicao[:meio]
            cols_recentes = cols_transicao[meio:] if len(cols_transicao) > 1 else cols_transicao

            taxa_antiga = quedas_por_sku[cols_antigas].sum(axis=1) / max(len(cols_antigas), 1)
            taxa_recente = quedas_por_sku[cols_recentes].sum(axis=1) / max(len(cols_recentes), 1)

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
        if ref <= 0.001 and atual <= 0.001:
            return "➡️ Sem Giro"
        if ref <= 0.001 and atual > 0.001:
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
# 6. CABEÇALHO PRINCIPAL E VERIFICAÇÃO DE STATUS DA NUVEM
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
        "☁️ Google Sheets" if conectado_nuvem else "⚠️ Modo Temporário"
    )
    st.markdown(
        f"""
        <div class="status-box">
            <div class="status-label">Status do Banco de Dados</div>
            <div class="status-value" title="{texto_status}">{texto_status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if not conectado_nuvem and "gcp_service_account" in st.secrets:
    st.error(
        f"❌ Oscilação de Conexão com Google Sheets: {erro_gsheets}. "
        "Clique em 'Tentar Reconectar' abaixo ou recarregue a página antes de importar."
    )
    if st.button("🔄 Tentar Reconectar ao Google Sheets Agora"):
        _conectar_planilha_cached.clear()
        carregar_estado_completo.clear()
        st.rerun()

try:
    estado = carregar_estado_completo()
except Exception as erro_leitura:
    st.error(f"❌ Erro ao ler dados do Google Sheets: {erro_leitura}")
    estado = carregar_espelho_local()

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
            f"🙈 Atualmente há **{len(codigos_ocultos)} produto(s) oculto(s)** dos relatórios (gerencie na Aba 6)."
        )
    with col_toggle_oc:
        mostrar_ocultos_temp = st.toggle(
            "👁️ Mostrar ocultos temporariamente", value=False
        )

if codigos_ocultos and not mostrar_ocultos_temp:
    df_estoque = df_estoque_bruto[~df_estoque_bruto["codigo"].isin(codigos_ocultos)]
    df_historico = df_historico_bruto[~df_historico_bruto["codigo"].isin(codigos_ocultos)]
else:
    df_estoque = df_estoque_bruto
    df_historico = df_historico_bruto

# ==============================================================================
# 7. NAVEGAÇÃO POR ABAS
# ==============================================================================
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(
    [
        "📥 1. Importação & Nuvem",
        "🛒 2. Sugestão de Compras & Giro",
        "⏳ 3. Radar de Validades (FEFO)",
        "📊 4. Curva ABC Financeira",
        "🔍 5. Auditoria de ERP",
        f"👁️‍🗨️ 6. Ocultar Produtos ({len(codigos_ocultos)})",
    ]
)

# ------------------------------------------------------------------------------
# ABA 1: CENTRAL DE IMPORTAÇÃO SEGURA E SINCRONIZAÇÃO COM NUVEM
# ------------------------------------------------------------------------------
with aba1:
    st.markdown("### Central de Importação Segura e Sincronização com Nuvem")
    st.caption(
        "Gravação incremental Append-First no Google Sheets, verificação explícita de duplicatas do ERP, "
        "poda de 180 dias e backup compactado (.zip com CSV + Excel leve)."
    )

    # Exibe mensagens persistentes da última sincronização (sobrevivem ao st.rerun)
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
            "Selecionar Estoque (.xlsx ou .csv)",
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
            "Selecionar Custos (.xlsx ou .csv)",
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
            "Selecionar Base Inicial (.xlsx ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_base",
        )

    st.markdown("---")
    col_btn_sync, col_btn_bkp = st.columns([3, 1])

    with col_btn_sync:
        btn_sincronizar = st.button(
            "🚀 Processar e Sincronizar com Segurança",
            type="primary",
            use_container_width=True,
        )

    # BACKUP LEVE EM .ZIP (EXCEL DAS ABAS PEQUENAS + HISTÓRICO EM CSV COMPACTADO)
    with col_btn_bkp:
        if not df_estoque_bruto.empty:
            if st.button("🛠️ Gerar Backup Leve (.zip)", use_container_width=True):
                with st.spinner("Compactando tabelas (.xlsx) + histórico (.csv)..."):
                    st.session_state["backup_zip_bytes"] = gerar_pacote_backup_leve(estado)
                    st.session_state["backup_zip_nome"] = (
                        f"Backup_Esteio_Rural_{date.today().strftime('%Y-%m-%d')}.zip"
                    )
            if "backup_zip_bytes" in st.session_state:
                st.download_button(
                    label="💾 Baixar Pacote (.zip)",
                    data=st.session_state["backup_zip_bytes"],
                    file_name=st.session_state.get("backup_zip_nome", "Backup_Esteio_Rural.zip"),
                    mime="application/zip",
                    use_container_width=True,
                )

    if btn_sincronizar:
        if not any([arq_estoque, arq_custos, arq_base]) and int(dias_base_input) == int(dias_base_atual):
            st.warning("⚠️ Selecione pelo menos uma planilha para importar ou altere o período da base.")
        else:
            with st.spinner("Processando arquivos e gravando de forma incremental segura no Google Sheets..."):
                try:
                    novo_estoque = df_estoque_bruto.copy()
                    novo_historico = df_historico_bruto.copy()
                    novos_custos = df_custos.copy()
                    nova_base = df_base_vendas.copy()
                    data_str = data_posicao.strftime("%Y-%m-%d")

                    mensagens_auditoria_upload = []
                    teve_duplicata = False

                    if arq_estoque is not None:
                        novo_estoque, info_dup_est = processar_planilha_estoque(arq_estoque, data_posicao)
                        if info_dup_est["qtd_duplicadas"] > 0:
                            teve_duplicata = True
                            amostra_txt = ", ".join(info_dup_est["exemplos"])
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Estoque:** {info_dup_est['qtd_duplicadas']} linha(s) duplicada(s) de mesmo "
                                f"(Código + Lote) foram mescladas mantendo a última ocorrência "
                                f"({info_dup_est['linhas_lidas']} lidas → {info_dup_est['linhas_finais']} únicas). "
                                f"Exemplos: {amostra_txt}"
                            )
                        else:
                            mensagens_auditoria_upload.append(
                                f"✔️ **Estoque:** {info_dup_est['linhas_finais']} linhas verificadas (0 duplicatas de Código + Lote)."
                            )

                        novo_lote_hist = padronizar_dataframe(novo_estoque, "historico")
                        if not novo_historico.empty and "data" in novo_historico.columns:
                            novo_historico = novo_historico[novo_historico["data"] != data_str].copy()
                        novo_historico = podar_historico_180_dias(
                            pd.concat([novo_historico, novo_lote_hist], ignore_index=True)
                        )

                    if arq_custos is not None:
                        novos_custos, qtd_dup_cus = processar_planilha_custos(arq_custos)
                        if qtd_dup_cus > 0:
                            teve_duplicata = True
                            mensagens_auditoria_upload.append(
                                f"⚠️ **Custos:** {qtd_dup_cus} código(s) repetido(s) na planilha de custos (mantido o último valor)."
                            )
                        else:
                            mensagens_auditoria_upload.append(
                                f"✔️ **Custos:** {len(novos_custos)} itens verificados (0 duplicatas)."
                            )

                    if arq_base is not None:
                        nova_base = processar_planilha_base_vendas(arq_base)

                    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    if "gcp_service_account" in st.secrets:
                        if not conectado_nuvem:
                            raise RuntimeError(
                                f"Google Sheets configurado, mas desconectado no momento ({erro_gsheets})."
                            )
                        if arq_estoque is not None:
                            gravar_aba_pequena_gsheets(planilha_gsheets, "estoque_atual", novo_estoque)
                            gravar_historico_incremental_gsheets(planilha_gsheets, novo_estoque, data_str)
                        if arq_custos is not None:
                            gravar_aba_pequena_gsheets(planilha_gsheets, "custos", novos_custos)
                        if arq_base is not None:
                            gravar_aba_pequena_gsheets(planilha_gsheets, "base_inicial", nova_base)

                        df_meta_novo = pd.DataFrame(
                            [
                                {"chave": "dias_base", "valor": str(int(dias_base_input))},
                                {"chave": "ultima_atualizacao", "valor": agora_str},
                            ]
                        )
                        gravar_aba_pequena_gsheets(planilha_gsheets, "meta", df_meta_novo)

                    novo_estado = {
                        "estoque_atual": novo_estoque,
                        "historico": novo_historico,
                        "custos": novos_custos,
                        "base_inicial": nova_base,
                        "ocultos": df_ocultos,
                        "dias_base": int(dias_base_input),
                        "ultima_atualizacao": agora_str,
                    }
                    salvar_espelho_e_backup_local(novo_estado, conectado_nuvem=conectado_nuvem)

                    st.session_state.pop("backup_zip_bytes", None)
                    carregar_estado_completo.clear()
                    calcular_motor_giro_sazonal.clear()

                    st.session_state["msg_sucesso_sync"] = (
                        f"✅ Dados processados e sincronizados com segurança em {agora_str}!"
                    )
                    if mensagens_auditoria_upload:
                        st.session_state["aviso_duplicatas_sync"] = {
                            "tipo": "warning" if teve_duplicata else "info",
                            "texto": " | ".join(mensagens_auditoria_upload),
                        }
                    st.rerun()

                except Exception as erro_gravacao:
                    st.error(
                        f"❌ Falha durante a sincronização (os dados anteriores permanecem preservados): {erro_gravacao}"
                    )

    r1, r2, r3, r4 = st.columns(4)
    qtd_skus_visiveis = df_estoque["codigo"].nunique() if (not df_estoque.empty and "codigo" in df_estoque.columns) else 0
    qtd_datas = df_historico_bruto["data"].nunique() if (not df_historico_bruto.empty and "data" in df_historico_bruto.columns) else 0
    qtd_custos = len(df_custos) if not df_custos.empty else 0
    r1.metric("Produtos Ativos nos Relatórios", f"{qtd_skus_visiveis} (Ocultos: {len(codigos_ocultos)})")
    r2.metric("Dias no Histórico (Máx 180d)", f"{qtd_datas} dia(s)")
    r3.metric("Itens com Custo Cadastrado", f"{qtd_custos}")
    r4.metric("Última Sincronização", estado.get("ultima_atualizacao", "-"))

# ------------------------------------------------------------------------------
# ABA 2: SUGESTÃO DE COMPRAS & MOTOR DE GIRO SAZONAL (EM CACHE)
# ------------------------------------------------------------------------------
with aba2:
    st.markdown("### 🛒 Sugestão de Compras & Motor de Giro Sazonal por Lote")
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 1 (ou verifique se todos os itens estão ocultos na Aba 6).")
    else:
        p1, p2, p3, p4, p5 = st.columns(5)
        janela_dias = p1.selectbox(
            "Janela Sazonal (dias):",
            options=[15, 30, 45, 60, 90],
            index=1,
            help="Período recente considerado para calcular as quedas diárias por lote e a tendência.",
        )
        cobertura_desejada = p2.number_input("Cobertura Desejada (dias):", min_value=5, max_value=180, value=30)
        lead_time = p3.number_input("Lead Time / Entrega (dias):", min_value=0, max_value=90, value=7)
        fator_sazonal = p4.slider("Ajuste Sazonal Extra (%):", min_value=-50, max_value=200, value=0, step=5)
        filtro_busca = p5.text_input("Filtrar Código ou Descrição:")

        df_base_giro, dias_hist_janela, peso_hist = calcular_motor_giro_sazonal(
            df_estoque=df_estoque,
            df_historico=df_historico,
            df_base_vendas=df_base_vendas,
            dias_base_atual=dias_base_atual,
            janela_dias=int(janela_dias),
        )

        df_calc = df_base_giro.copy()
        df_calc["giro_diario"] = (df_calc["giro_ponderado"] * (1.0 + (fator_sazonal / 100.0))).clip(lower=0.0)

        if not df_custos.empty:
            df_calc = df_calc.merge(
                df_custos[["codigo", "custo_unitario"]], on="codigo", how="left"
            )
            df_calc["custo_unitario"] = df_calc["custo_unitario"].fillna(0.0)
        else:
            df_calc["custo_unitario"] = 0.0

        dias_totais_nec = cobertura_desejada + lead_time
        df_calc["estoque_ideal"] = (df_calc["giro_diario"] * dias_totais_nec).round(1)
        df_calc["sugestao_compra"] = (
            (df_calc["estoque_ideal"] - df_calc["saldo_atual"]).round(0).clip(lower=0.0)
        )
        df_calc["investimento_estimado"] = df_calc["sugestao_compra"] * df_calc["custo_unitario"]
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

        df_compras = df_calc.sort_values("investimento_estimado", ascending=False)

        m1, m2, m3, m4 = st.columns(4)
        itens_comprar = int((df_compras["sugestao_compra"] > 0).sum())
        orcamento_total = df_compras["investimento_estimado"].sum()
        m1.metric("Itens com Necessidade de Compra", f"{itens_comprar} SKUs")
        m2.metric("Orçamento Estimado de Reposição", f"R$ {orcamento_total:,.2f}")
        m3.metric("Janela de Proteção (Cobertura + Lead Time)", f"{dias_totais_nec} dias")
        m4.metric(
            "Peso do Histórico vs Base",
            f"{int(round(peso_hist * 100))}% Hist. / {int(round((1 - peso_hist) * 100))}% Base",
            help=f"Calculado sobre {dias_hist_janela} dia(s) acumulados na janela de {janela_dias} dias.",
        )

        st.dataframe(
            df_compras[
                [
                    "codigo",
                    "descricao",
                    "tendencia",
                    "saldo_atual",
                    "giro_base",
                    "giro_historico",
                    "giro_diario",
                    "autonomia_dias",
                    "sugestao_compra",
                    "custo_unitario",
                    "investimento_estimado",
                ]
            ].rename(
                columns={
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "tendencia": "Tendência",
                    "saldo_atual": "Saldo Atual",
                    "giro_base": "Giro Base/Dia",
                    "giro_historico": f"Giro Lotes ({janela_dias}d)",
                    "giro_diario": "Giro Final/Dia",
                    "autonomia_dias": "Autonomia (Dias)",
                    "sugestao_compra": "Sugestão Compra",
                    "custo_unitario": "Custo Unit. (R$)",
                    "investimento_estimado": "Total Compra (R$)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

# ------------------------------------------------------------------------------
# ABA 3: RADAR DE VALIDADES (FEFO DETERMINÍSTICO)
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

        v1.metric("🔴 Vencidos", f"R$ {vlr_vencido:,.2f}")
        v2.metric("🟠 Vencendo em 30 dias", f"R$ {vlr_30d:,.2f}")
        v3.metric("🟡 Vencendo em 31-60 dias", f"R$ {vlr_60d:,.2f}")
        v4.metric("🔵 Vencendo em 61-90 dias", f"R$ {vlr_90d:,.2f}")

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

        st.dataframe(
            df_fefo_view[
                [
                    "status_fefo",
                    "codigo",
                    "descricao",
                    "lote",
                    "validade",
                    "dias_para_vencer",
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
                    "saldo_lote": "Saldo do Lote",
                    "valor_em_risco": "Capital no Lote (R$)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

# ------------------------------------------------------------------------------
# ABA 4: CURVA ABC FINANCEIRA
# ------------------------------------------------------------------------------
with aba4:
    st.markdown("### 📊 Curva ABC Financeira (Pareto 80 / 15 / 5)")
    if df_estoque.empty or df_custos.empty:
        st.info("Importe a Planilha de Estoque e a Planilha de Custos na Aba 1 para gerar a Curva ABC Financeira.")
    else:
        df_abc = (
            df_estoque.groupby("codigo", as_index=False)
            .agg(descricao=("descricao", "first"), saldo_geral=("saldo_geral", "first"))
            .merge(df_custos[["codigo", "custo_unitario"]], on="codigo", how="left")
        )
        df_abc["custo_unitario"] = df_abc["custo_unitario"].fillna(0.0)
        df_abc["valor_estoque"] = df_abc["saldo_geral"].clip(lower=0.0) * df_abc["custo_unitario"]
        df_abc = df_abc[df_abc["valor_estoque"] > 0].sort_values("valor_estoque", ascending=False).copy()

        total_fin = df_abc["valor_estoque"].sum()
        if total_fin > 0:
            df_abc["part_pct"] = ((df_abc["valor_estoque"] / total_fin) * 100.0).round(2)
            df_abc["acum_pct"] = df_abc["part_pct"].cumsum().round(2)
            df_abc["classe_abc"] = df_abc["acum_pct"].apply(
                lambda p: "Classe A (Até 80%)" if p <= 80.0 else ("Classe B (80% a 95%)" if p <= 95.0 else "Classe C (95% a 100%)")
            )

            a1, a2, a3 = st.columns(3)
            a1.metric("Capital Total Imobilizado", f"R$ {total_fin:,.2f}")
            a2.metric("Itens Classe A (80% do Valor)", f"{int((df_abc['classe_abc'].str.startswith('Classe A')).sum())} SKUs")
            a3.metric("Itens Classe B + C", f"{int((~df_abc['classe_abc'].str.startswith('Classe A')).sum())} SKUs")

            st.dataframe(
                df_abc[
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
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("Nenhum produto com saldo e custo positivos encontrado para calcular a Curva ABC.")

# ------------------------------------------------------------------------------
# ABA 5: AUDITORIA DE ERP (COMPLETA COM AS 3 VERIFICAÇÕES)
# ------------------------------------------------------------------------------
with aba5:
    st.markdown("### 🔍 Auditoria de Inconsistências de ERP")
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
                )
            )
            aud_lotes["diferenca"] = (aud_lotes["saldo_geral"] - aud_lotes["soma_lotes"]).round(3)
            div_lotes = aud_lotes[aud_lotes["diferenca"].abs() > 0.01].copy()
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

        au1, au2, au3 = st.columns(3)
        au1.metric("Divergências (Saldo Geral ≠ Soma Lotes)", len(div_lotes))
        au2.metric("Registros com Saldo Negativo", len(saldos_negativos))
        au3.metric("Produtos c/ Estoque e Sem Custo", len(sem_custo))

        st.markdown("#### 1. Divergência entre Saldo Geral e Soma dos Lotes")
        if div_lotes.empty:
            st.success("✅ Nenhuma divergência entre Saldo Geral e Soma de Lotes encontrada!")
        else:
            st.dataframe(
                div_lotes.rename(
                    columns={
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "saldo_geral": "Saldo Geral (ERP)",
                        "soma_lotes": "Soma dos Lotes",
                        "qtd_lotes": "Qtd. Lotes",
                        "diferenca": "Diferença",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### 2. Saldos Negativos no Sistema")
        if saldos_negativos.empty:
            st.success("✅ Nenhum saldo negativo encontrado!")
        else:
            st.dataframe(
                saldos_negativos[["codigo", "descricao", "saldo_geral", "lote", "saldo_lote"]].rename(
                    columns={
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "saldo_geral": "Saldo Geral",
                        "lote": "Lote",
                        "saldo_lote": "Saldo Lote",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### 3. Produtos com Estoque Físico Sem Custo Unitário")
        if sem_custo.empty:
            st.success("✅ Todos os itens com estoque positivo possuem custo cadastrado!")
        else:
            st.dataframe(
                sem_custo.rename(
                    columns={
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "saldo_geral": "Saldo Geral",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

# ------------------------------------------------------------------------------
# ABA 6: GERENCIADOR DE PRODUTOS OCULTOS (CAIXAS DE SELEÇÃO EM LOTE)
# ------------------------------------------------------------------------------
with aba6:
    st.markdown("### 👁️‍🗨️ Ocultar ou Restaurar Produtos dos Relatórios")
    st.caption(
        "Marque as caixas de seleção para ocultar vários produtos de uma só vez (ex: brindes, uso interno ou itens fora de linha). "
        "A lista fica salva no Google Sheets e pode ser restaurada a qualquer momento."
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
                f"Selecionar todos os {len(df_visiveis)} produtos listados abaixo",
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
                f"🙈 Ocultar Selecionados ({len(selecionados_para_ocultar)})",
                type="primary",
                use_container_width=True,
                disabled=selecionados_para_ocultar.empty,
            ):
                with st.spinner("Salvando produtos ocultos na nuvem..."):
                    try:
                        novos_ocultos = selecionados_para_ocultar[["codigo", "descricao"]].copy()
                        novos_ocultos["data_ocultado"] = date.today().strftime("%Y-%m-%d")

                        df_ocultos_atualizado = (
                            pd.concat([df_ocultos, novos_ocultos], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
                        )

                        if "gcp_service_account" in st.secrets:
                            if not conectado_nuvem:
                                raise RuntimeError(f"Sem conexão com Google Sheets ({erro_gsheets}).")
                            gravar_aba_pequena_gsheets(
                                planilha_gsheets, "ocultos", df_ocultos_atualizado, permitir_vazio=True
                            )

                        estado["ocultos"] = df_ocultos_atualizado
                        salvar_espelho_e_backup_local(estado, conectado_nuvem=conectado_nuvem)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success(f"✅ {len(selecionados_para_ocultar)} produto(s) ocultado(s) com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao ocultar produtos: {e}")

    # --- COLUNA DA DIREITA: PRODUTOS OCULTOS PARA RESTAURAR ---
    with col_dir:
        st.markdown(f"#### 🙈 Produtos Ocultos ({len(df_ocultos)})")
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
                f"Selecionar todos os {len(df_oc_view)} ocultos listados abaixo",
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
                    f"👁️ Restaurar Marcados ({len(selecionados_para_restaurar)})",
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
                with st.spinner("Restaurando produtos na nuvem..."):
                    try:
                        if btn_restaurar_todos:
                            df_ocultos_restante = padronizar_dataframe(pd.DataFrame(), "ocultos")
                        else:
                            cods_remover = set(selecionados_para_restaurar["codigo"].unique())
                            df_ocultos_restante = df_ocultos[~df_ocultos["codigo"].isin(cods_remover)].copy()

                        if "gcp_service_account" in st.secrets:
                            if not conectado_nuvem:
                                raise RuntimeError(f"Sem conexão com Google Sheets ({erro_gsheets}).")
                            gravar_aba_pequena_gsheets(
                                planilha_gsheets, "ocultos", df_ocultos_restante, permitir_vazio=True
                            )

                        estado["ocultos"] = df_ocultos_restante
                        salvar_espelho_e_backup_local(estado, conectado_nuvem=conectado_nuvem)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success("✅ Produto(s) restaurado(s) para os relatórios com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao restaurar produtos: {e}")
