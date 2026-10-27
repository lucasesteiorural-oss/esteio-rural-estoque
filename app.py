import os
import io
import json
import glob
import unicodedata
from datetime import datetime, date
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
# 2. DIRETÓRIOS E REGRAS DE TIPAGEM (PRESERVAÇÃO DE ZEROS À ESQUERDA)
# ==============================================================================
PASTA_DADOS = "dados_esteio"
PASTA_BACKUPS = "backups_esteio"
os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_BACKUPS, exist_ok=True)

ARQUIVO_LOCAL = os.path.join(PASTA_DADOS, "estado_esteio.json")

# Apenas estas colunas são convertidas para float; código e lote são sempre texto (str)
COLUNAS_NUMERICAS = {"saldo_geral", "saldo_lote", "custo_unitario", "qtd_vendida"}
COLUNAS_TEXTO_PURO = {"codigo", "lote", "descricao", "validade", "data"}


def limpar_texto(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    # Remove apenas sufixo '.0' caso o Excel tenha exportado inteiro como float, preservando zeros à esquerda
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def converter_numero_br(serie: pd.Series) -> pd.Series:
    """Converte números em formato brasileiro (1.234,56) ou americano (1234.56) para float."""
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


def restaurar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que códigos e lotes fiquem como texto puro (preservando zeros) e saldos/custos como float."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        if col in COLUNAS_NUMERICAS:
            df[col] = converter_numero_br(df[col])
        else:
            df[col] = df[col].apply(limpar_texto)
    return df


# ==============================================================================
# 3. CONEXÃO COM GOOGLE SHEETS (COM CACHE E GRAVAÇÃO INCREMENTAL SEGURA)
# ==============================================================================
@st.cache_resource(ttl=3600, show_spinner=False)
def obter_planilha_gsheets():
    """Autentica e guarda a conexão em cache por 1 hora para evitar limite de 60 req/min."""
    if "gcp_service_account" not in st.secrets:
        return None, "Bloco [gcp_service_account] ausente em st.secrets"
    try:
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
        nome_planilha = st.secrets.get("sheet_name", "Banco_Dados_Esteio_Rural")
        return cliente.open(nome_planilha), None
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
    """Lê todas as células como texto (get_all_values) para nunca perder zeros à esquerda nos lotes."""
    ws = obter_ou_criar_aba(planilha, nome_aba)
    valores = ws.get_all_values()
    if not valores or len(valores) < 2:
        return pd.DataFrame()
    cabecalho = [str(c).strip() for c in valores[0]]
    df = pd.DataFrame(valores[1:], columns=cabecalho)
    return restaurar_tipos(df)


def gravar_aba_pequena_gsheets(planilha, nome_aba: str, df: pd.DataFrame):
    """
    Sobrescreve abas pequenas (estoque_atual, custos, base_inicial, meta) a partir de A1
    SEM chamar clear() antes, redimensionando a aba ao final.
    """
    if df is None or df.empty:
        return
    df_str = df.fillna("").astype(str)
    dados = [df_str.columns.tolist()] + df_str.values.tolist()

    ws = obter_ou_criar_aba(
        planilha, nome_aba, len(dados) + 10, len(df_str.columns) + 2
    )
    ws.update(values=dados, range_name="A1", value_input_option="RAW")
    ws.resize(rows=max(len(dados), 2), cols=max(len(df_str.columns), 1))


def gravar_historico_incremental_gsheets(
    planilha, df_novo_dia: pd.DataFrame, data_ref: str
):
    """
    Grava no histórico APENAS as linhas da data importada (~0,2 MB).
    Se a data já existir, apaga apenas as linhas daquela data e anexa as novas ao final.
    """
    if df_novo_dia is None or df_novo_dia.empty:
        return

    df_str = df_novo_dia.fillna("").astype(str)
    cabecalho = df_str.columns.tolist()
    linhas_novas = df_str.values.tolist()

    ws = obter_ou_criar_aba(
        planilha, "historico", len(linhas_novas) + 100, len(cabecalho) + 2
    )
    primeira_linha = ws.row_values(1)

    if not primeira_linha:
        ws.update(
            values=[cabecalho] + linhas_novas,
            range_name="A1",
            value_input_option="RAW",
        )
        return

    idx_col_data = (
        (primeira_linha.index("data") + 1) if "data" in primeira_linha else 1
    )
    col_datas = ws.col_values(idx_col_data)

    linhas_para_apagar = [
        i
        for i, val in enumerate(col_datas, start=1)
        if i >= 2 and str(val).strip() == str(data_ref).strip()
    ]

    if linhas_para_apagar:
        blocos = []
        inicio = fim = linhas_para_apagar[0]
        for r in linhas_para_apagar[1:]:
            if r == fim + 1:
                fim = r
            else:
                blocos.append((inicio, fim))
                inicio = fim = r
        blocos.append((inicio, fim))

        for ini, f in reversed(blocos):
            ws.delete_rows(ini, f)

    ws.append_rows(values=linhas_novas, value_input_option="RAW")


# ==============================================================================
# 4. PERSISTÊNCIA HÍBRIDA (FONTE ÚNICA NA NUVEM + BACKUP DIÁRIO LOCAL)
# ==============================================================================
def salvar_espelho_e_backup_local(estado: dict):
    """Grava arquivo local de forma atômica e mantém 1 backup por dia (últimos 7 dias)."""
    payload = {
        "estoque_atual": estado.get("estoque_atual", pd.DataFrame()).to_dict(orient="records"),
        "historico": estado.get("historico", pd.DataFrame()).to_dict(orient="records"),
        "custos": estado.get("custos", pd.DataFrame()).to_dict(orient="records"),
        "base_inicial": estado.get("base_inicial", pd.DataFrame()).to_dict(orient="records"),
        "dias_base": int(estado.get("dias_base", 87)),
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    temp_local = f"{ARQUIVO_LOCAL}.tmp"
    with open(temp_local, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(temp_local, ARQUIVO_LOCAL)

    # Rotação diária: 1 arquivo por data (múltiplos testes no mesmo dia não apagam ontem)
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
        "estoque_atual": pd.DataFrame(),
        "historico": pd.DataFrame(),
        "custos": pd.DataFrame(),
        "base_inicial": pd.DataFrame(),
        "dias_base": 87,
        "ultima_atualizacao": "Sem registros",
    }
    if not os.path.exists(ARQUIVO_LOCAL):
        return estado_vazio
    try:
        with open(ARQUIVO_LOCAL, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "estoque_atual": restaurar_tipos(pd.DataFrame(d.get("estoque_atual", []))),
            "historico": restaurar_tipos(pd.DataFrame(d.get("historico", []))),
            "custos": restaurar_tipos(pd.DataFrame(d.get("custos", []))),
            "base_inicial": restaurar_tipos(pd.DataFrame(d.get("base_inicial", []))),
            "dias_base": int(d.get("dias_base", 87)),
            "ultima_atualizacao": d.get("ultima_atualizacao", "Local"),
        }
    except Exception:
        return estado_vazio


@st.cache_data(ttl=600, show_spinner=False)
def carregar_estado_completo() -> dict:
    """
    Fonte Única da Verdade: Se conectado ao Google Sheets, lê direto da nuvem (com cache de 10 min).
    Caso contrário, utiliza o espelho local.
    """
    planilha, _ = obter_planilha_gsheets()
    if planilha is not None:
        df_est = ler_aba_bruta_gsheets(planilha, "estoque_atual")
        df_hist = ler_aba_bruta_gsheets(planilha, "historico")
        df_cus = ler_aba_bruta_gsheets(planilha, "custos")
        df_base = ler_aba_bruta_gsheets(planilha, "base_inicial")
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
            "dias_base": dias_base,
            "ultima_atualizacao": ult_att,
        }

    return carregar_espelho_local()


# ==============================================================================
# 5. LEITURA E PADRONIZAÇÃO DE PLANILHAS (EXCEL / CSV COM DTYPE=STR)
# ==============================================================================
def normalizar_nome_col(nome: str) -> str:
    s = unicodedata.normalize("NFKD", str(nome)).encode("ASCII", "ignore").decode("utf-8")
    return s.lower().strip()


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


def processar_planilha_estoque(arquivo, data_pos: date) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 6:
        raise ValueError(
            f"A planilha de estoque precisa ter pelo menos 6 colunas (encontradas: {df_raw.shape[1]})."
        )

    # Mapeamento inteligente por nome ou pelas 6 primeiras colunas na ordem padrão do ERP
    df = pd.DataFrame()
    df["codigo"] = df_raw.iloc[:, 0].apply(limpar_texto)
    df["saldo_geral"] = converter_numero_br(df_raw.iloc[:, 1])
    df["descricao"] = df_raw.iloc[:, 2].apply(limpar_texto)
    df["lote"] = df_raw.iloc[:, 3].apply(limpar_texto)
    df["saldo_lote"] = converter_numero_br(df_raw.iloc[:, 4])
    df["validade"] = df_raw.iloc[:, 5].apply(limpar_texto)
    df["data"] = data_pos.strftime("%Y-%m-%d")

    # Remove linhas vazias ou cabeçalhos repetidos no meio do relatório
    df = df[df["codigo"] != ""].copy()
    df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod", "total"])].copy()
    return restaurar_tipos(df)


def processar_planilha_custos(arquivo) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 3:
        raise ValueError("A planilha de custos precisa ter pelo menos 3 colunas (Código, Descrição, Custo).")

    df = pd.DataFrame()
    df["codigo"] = df_raw.iloc[:, 0].apply(limpar_texto)
    df["descricao"] = df_raw.iloc[:, 1].apply(limpar_texto)
    df["custo_unitario"] = converter_numero_br(df_raw.iloc[:, 2])

    df = df[df["codigo"] != ""].copy()
    df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod"])].copy()
    df = df.drop_duplicates(subset=["codigo"], keep="last")
    return restaurar_tipos(df)


def processar_planilha_base_vendas(arquivo) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo)
    if df_raw.shape[1] < 3:
        raise ValueError("A Base Inicial de Vendas precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade).")

    df = pd.DataFrame()
    df["codigo"] = df_raw.iloc[:, 0].apply(limpar_texto)
    df["descricao"] = df_raw.iloc[:, 1].apply(limpar_texto)
    df["qtd_vendida"] = converter_numero_br(df_raw.iloc[:, 2])

    df = df[df["codigo"] != ""].copy()
    df = df[~df["codigo"].str.lower().isin(["codigo", "código", "cod"])].copy()
    df = df.groupby(["codigo", "descricao"], as_index=False)["qtd_vendida"].sum()
    return restaurar_tipos(df)


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
        f"❌ Erro de Conexão com Google Sheets: {erro_gsheets}. "
        "Verifique as credenciais ou aguarde antes de importar para não salvar apenas em disco temporário."
    )

try:
    estado = carregar_estado_completo()
except Exception as erro_leitura:
    st.error(f"❌ Erro ao ler dados do Google Sheets: {erro_leitura}")
    estado = carregar_espelho_local()

df_estoque = estado["estoque_atual"]
df_historico = estado["historico"]
df_custos = estado["custos"]
df_base_vendas = estado["base_inicial"]
dias_base_atual = estado["dias_base"]

# ==============================================================================
# 7. NAVEGAÇÃO POR ABAS
# ==============================================================================
aba1, aba2, aba3, aba4, aba5 = st.tabs(
    [
        "📥 1. Importação & Nuvem",
        "🛒 2. Sugestão de Compras & Sazonalidade",
        "⏳ 3. Radar de Validades (FEFO)",
        "📊 4. Curva ABC Financeira",
        "🔍 5. Auditoria de ERP",
    ]
)

# ------------------------------------------------------------------------------
# ABA 1: CENTRAL DE IMPORTAÇÃO SEGURA E SINCRONIZAÇÃO COM NUVEM
# ------------------------------------------------------------------------------
with aba1:
    st.markdown("### Central de Importação Segura e Sincronização com Nuvem")
    st.caption(
        "Gravação incremental no Google Sheets (sem apagar o histórico), "
        "preservação de zeros à esquerda nos lotes e backup diário automático."
    )

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
    if st.button("🚀 Processar e Sincronizar com Segurança", type="primary", use_container_width=True):
        if not any([arq_estoque, arq_custos, arq_base]) and int(dias_base_input) == int(dias_base_atual):
            st.warning("⚠️ Selecione pelo menos uma planilha para importar ou altere o período da base.")
        else:
            with st.spinner("Processando arquivos e gravando de forma incremental no Google Sheets..."):
                try:
                    novo_estoque = df_estoque.copy()
                    novo_historico = df_historico.copy()
                    novos_custos = df_custos.copy()
                    nova_base = df_base_vendas.copy()
                    data_str = data_posicao.strftime("%Y-%m-%d")

                    if arq_estoque is not None:
                        novo_estoque = processar_planilha_estoque(arq_estoque, data_posicao)
                        if not novo_historico.empty and "data" in novo_historico.columns:
                            novo_historico = novo_historico[novo_historico["data"] != data_str].copy()
                        novo_historico = pd.concat([novo_historico, novo_estoque], ignore_index=True)

                    if arq_custos is not None:
                        novos_custos = processar_planilha_custos(arq_custos)

                    if arq_base is not None:
                        nova_base = processar_planilha_base_vendas(arq_base)

                    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    # Se o Google Sheets estiver configurado, exige sucesso na gravação em nuvem antes de confirmar
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

                    # Atualiza espelho e backup diário local
                    novo_estado = {
                        "estoque_atual": novo_estoque,
                        "historico": novo_historico,
                        "custos": novos_custos,
                        "base_inicial": nova_base,
                        "dias_base": int(dias_base_input),
                        "ultima_atualizacao": agora_str,
                    }
                    salvar_espelho_e_backup_local(novo_estado)

                    # Limpa o cache de leitura para exibir os dados novos imediatamente
                    carregar_estado_completo.clear()
                    st.success(
                        f"✅ Dados processados e sincronizados com segurança em {agora_str}!"
                    )
                    st.rerun()

                except Exception as erro_gravacao:
                    st.error(
                        f"❌ Falha durante a sincronização (nenhum dado antigo foi perdido): {erro_gravacao}"
                    )

    # Resumo do banco carregado
    r1, r2, r3, r4 = st.columns(4)
    qtd_skus = df_estoque["codigo"].nunique() if not df_estoque.empty else 0
    qtd_datas = df_historico["data"].nunique() if (not df_historico.empty and "data" in df_historico.columns) else 0
    qtd_custos = len(df_custos) if not df_custos.empty else 0
    r1.metric("Produtos no Estoque Atual", f"{qtd_skus}")
    r2.metric("Dias no Histórico Sazonal", f"{qtd_datas} dia(s)")
    r3.metric("Itens com Custo Cadastrado", f"{qtd_custos}")
    r4.metric("Última Sincronização", estado.get("ultima_atualizacao", "-"))

# ------------------------------------------------------------------------------
# ABA 2: SUGESTÃO DE COMPRAS & SAZONALIDADE
# ------------------------------------------------------------------------------
with aba2:
    st.markdown("### 🛒 Sugestão de Compras & Giro Sazonal")
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 1 para calcular o giro e as sugestões de compra.")
    else:
        p1, p2, p3, p4 = st.columns(4)
        cobertura_desejada = p1.number_input("Cobertura Desejada (dias):", min_value=5, max_value=180, value=30)
        lead_time = p2.number_input("Tempo de Entrega / Lead Time (dias):", min_value=0, max_value=90, value=7)
        fator_sazonal = p3.slider("Ajuste Sazonal de Demanda (%):", min_value=-50, max_value=200, value=0, step=5)
        filtro_busca = p4.text_input("Filtrar por Código ou Descrição:")

        # Consolida estoque por produto (Saldo Geral é único por código)
        df_prod = (
            df_estoque.groupby("codigo", as_index=False)
            .agg(
                descricao=("descricao", "first"),
                saldo_atual=("saldo_geral", "first"),
            )
        )

        # Calcula giro pelo histórico de variações diárias (se houver >= 2 datas)
        giro_hist = pd.DataFrame(columns=["codigo", "giro_historico"])
        if not df_historico.empty and "data" in df_historico.columns and df_historico["data"].nunique() >= 2:
            hist_diario = (
                df_historico.groupby(["codigo", "data"], as_index=False)["saldo_geral"]
                .first()
                .sort_values(["codigo", "data"])
            )
            hist_diario["delta"] = hist_diario.groupby("codigo")["saldo_geral"].diff()
            # Quedas de saldo representam saídas/vendas; subidas são entradas de nota fiscal
            hist_diario["saida"] = hist_diario["delta"].apply(lambda x: abs(x) if pd.notna(x) and x < 0 else 0.0)

            datas_unicas = sorted(df_historico["data"].unique())
            intervalo_dias = max(
                (pd.to_datetime(datas_unicas[-1]) - pd.to_datetime(datas_unicas[0])).days, 1
            )
            giro_hist = (
                hist_diario.groupby("codigo", as_index=False)["saida"]
                .sum()
                .rename(columns={"saida": "saida_total"})
            )
            giro_hist["giro_historico"] = giro_hist["saida_total"] / intervalo_dias

        df_calc = df_prod.merge(giro_hist[["codigo", "giro_historico"]], on="codigo", how="left")
        df_calc["giro_historico"] = df_calc["giro_historico"].fillna(0.0)

        # Junta com Base Inicial de Vendas
        if not df_base_vendas.empty:
            df_calc = df_calc.merge(
                df_base_vendas[["codigo", "qtd_vendida"]], on="codigo", how="left"
            )
            df_calc["qtd_vendida"] = df_calc["qtd_vendida"].fillna(0.0)
            df_calc["giro_base"] = df_calc["qtd_vendida"] / max(int(dias_base_atual), 1)
        else:
            df_calc["giro_base"] = 0.0

        # Usa o maior giro entre a base histórica e o acumulado diário, ajustado pela sazonalidade
        df_calc["giro_diario"] = df_calc[["giro_historico", "giro_base"]].max(axis=1) * (
            1.0 + (fator_sazonal / 100.0)
        )

        # Junta com Custos
        if not df_custos.empty:
            df_calc = df_calc.merge(
                df_custos[["codigo", "custo_unitario"]], on="codigo", how="left"
            )
            df_calc["custo_unitario"] = df_calc["custo_unitario"].fillna(0.0)
        else:
            df_calc["custo_unitario"] = 0.0

        dias_totais_nec = cobertura_desejada + lead_time
        df_calc["estoque_ideal"] = (df_calc["giro_diario"] * dias_totais_nec).round(1)
        df_calc["sugestao_compra"] = (df_calc["estoque_ideal"] - df_calc["saldo_atual"]).apply(
            lambda x: max(round(x), 0)
        )
        df_calc["investimento_estimado"] = df_calc["sugestao_compra"] * df_calc["custo_unitario"]
        df_calc["autonomia_dias"] = df_calc.apply(
            lambda r: round(r["saldo_atual"] / r["giro_diario"], 1) if r["giro_diario"] > 0 else 999.0,
            axis=1,
        )

        if filtro_busca:
            termo = filtro_busca.lower().strip()
            df_calc = df_calc[
                df_calc["codigo"].str.lower().str.contains(termo, na=False)
                | df_calc["descricao"].str.lower().str.contains(termo, na=False)
            ]

        df_compras = df_calc.sort_values("investimento_estimado", ascending=False)

        m1, m2, m3 = st.columns(3)
        itens_comprar = int((df_compras["sugestao_compra"] > 0).sum())
        orcamento_total = df_compras["investimento_estimado"].sum()
        m1.metric("Itens com Necessidade de Compra", f"{itens_comprar} SKUs")
        m2.metric("Orçamento Estimado de Reposição", f"R$ {orcamento_total:,.2f}")
        m3.metric("Janela de Proteção (Cobertura + Entrega)", f"{dias_totais_nec} dias")

        st.dataframe(
            df_compras[
                [
                    "codigo",
                    "descricao",
                    "saldo_atual",
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
                    "saldo_atual": "Saldo Atual",
                    "giro_diario": "Giro/Dia",
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
# ABA 3: RADAR DE VALIDADES (FEFO)
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

        df_fefo["dt_validade"] = pd.to_datetime(
            df_fefo["validade"], format="%d/%m/%Y", errors="coerce"
        )
        mask_iso = df_fefo["dt_validade"].isna()
        if mask_iso.any():
            df_fefo.loc[mask_iso, "dt_validade"] = pd.to_datetime(
                df_fefo.loc[mask_iso, "validade"], errors="coerce", dayfirst=True
            )

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

        filtro_status = st.multiselect(
            "Filtrar faixas de vencimento:",
            options=sorted(df_fefo["status_fefo"].unique()),
            default=[s for s in sorted(df_fefo["status_fefo"].unique()) if not s.startswith("🟢")],
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
            df_abc["part_pct"] = (df_abc["valor_estoque"] / total_fin) * 100.0
            df_abc["acum_pct"] = df_abc["part_pct"].cumsum()
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
# ABA 5: AUDITORIA DE ERP (ZERO FALSOS ALARMES)
# ------------------------------------------------------------------------------
with aba5:
    st.markdown("### 🔍 Auditoria de Inconsistências de ERP")
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 1 para auditar divergências de lote e saldos.")
    else:
        # 1. Divergência real entre Saldo Geral e Soma dos Lotes (apenas para produtos que possuem lote informado)
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

        # 2. Saldos gerais ou de lote negativos
        saldos_negativos = df_estoque[
            (df_estoque["saldo_geral"] < -0.001) | (df_estoque["saldo_lote"] < -0.001)
        ].copy()

        # 3. Produtos com estoque físico positivo mas sem custo cadastrado
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
