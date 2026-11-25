"""
database.py — Módulo de Conexão Supabase (PostgreSQL), DDL, Transações Atômicas,
Backups Automáticos, Gestão de Usuários e Carga de Estado (Esteio Rural — v37).
"""
import io
import re
import hmac
import hashlib
import zipfile
import threading
import unicodedata
from contextlib import contextmanager
from datetime import timedelta
import pandas as pd
import streamlit as st

from parsers import (
    DIAS_MAX_HISTORICO,
    COLUNAS_NUMERICAS,
    ESQUEMA_ABAS,
    hoje_br,
    agora_br,
    normalizar_codigo_sku,
    converter_datas_deterministico,
    compactar_estoque_para_historico,
    padronizar_dataframe,
    depurar_pedidos_transito_auto_despertar,
    podar_historico_max_dias,
    _preservar_celula_excel,
)




# ==============================================================================
# 1. ACESSO A SECRETS, HASH DE SENHAS E AUTENTICAÇÃO DE USUÁRIOS
# ==============================================================================


def obter_secret(chave: str, padrao=None):
    try:
        return st.secrets.get(chave, padrao)
    except Exception:
        return padrao


PBKDF2_ITERACOES_PADRAO = 310_000


def _normalizar_username(usuario: str) -> str:
    s = unicodedata.normalize("NFKD", str(usuario or "")).encode("ASCII", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9._-]+", "", s.strip().lower())


def gerar_hash_senha_segura(
    senha_plana: str,
    salt_hex: str = "",
    iteracoes: int = PBKDF2_ITERACOES_PADRAO,
) -> str:
    import secrets as _py_secrets
    if not salt_hex:
        salt_hex = _py_secrets.token_hex(16)
    n_iter = int(iteracoes) if int(iteracoes) > 0 else PBKDF2_ITERACOES_PADRAO
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(senha_plana).encode("utf-8"),
        bytes.fromhex(salt_hex),
        n_iter,
    )
    return f"pbkdf2_sha256${n_iter}${salt_hex}${dk.hex()}"


def verificar_senha_hash(senha_digitada: str, senha_hash_armazenada: str) -> bool:
    if not senha_digitada or not senha_hash_armazenada:
        return False
    partes = str(senha_hash_armazenada).split("$")
    if partes[0] != "pbkdf2_sha256":
        return False
    try:
        if len(partes) == 4:
            _, iter_str, salt_hex, _ = partes
            n_iter = int(iter_str)
            calculado = gerar_hash_senha_segura(senha_digitada, salt_hex=salt_hex, iteracoes=n_iter)
            return hmac.compare_digest(calculado.encode("utf-8"), str(senha_hash_armazenada).encode("utf-8"))
        elif len(partes) == 3:
            _, salt_hex, hash_hex = partes
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                str(senha_digitada).encode("utf-8"),
                bytes.fromhex(salt_hex),
                120_000,
            )
            return hmac.compare_digest(dk.hex().encode("utf-8"), hash_hex.encode("utf-8"))
    except Exception:
        return False
    return False


def obter_credencial_admin_mestre() -> tuple[str, str, str]:
    admin_user = _normalizar_username(obter_secret("admin_user", "admin")) or "admin"
    admin_nome = str(obter_secret("admin_nome", "Administrador (Esteio Rural)")).strip() or "Administrador"
    admin_pass = str(obter_secret("app_password", "")).strip()
    return admin_user, admin_nome, admin_pass


def _autenticar_usuario_no_banco(username_norm: str, senha_digitada: str) -> tuple[bool, str, bool, str]:
    """Valida usuário cadastrado na tabela `usuarios` do Supabase sem vazar detalhes internos."""
    db_url = obter_url_supabase_secrets()
    if not db_url:
        return False, "", False, "⚠️ Serviço de autenticação indisponível no momento."
    try:
        cliente_pg = _conectar_supabase_cached(db_url)
        garantir_tabela_usuarios_sql(cliente_pg)
        linhas = cliente_pg.executar_leitura(
            "SELECT nome_exibicao, senha_hash, eh_admin, ativo FROM usuarios WHERE username = %s",
            (username_norm,),
        )
        if not linhas:
            return False, "", False, "❌ Usuário ou senha incorretos."
        nome_exib, senha_hash, eh_adm, ativo = linhas[0]
        if not verificar_senha_hash(senha_digitada, str(senha_hash or "")):
            return False, "", False, "❌ Usuário ou senha incorretos."
        if not bool(ativo):
            return False, "", False, "🚫 Este usuário está desativado. Contate o Administrador."
        return True, (str(nome_exib or "").strip() or username_norm), bool(eh_adm), ""
    except Exception:
        return False, "", False, "⚠️ Não foi possível validar o acesso no momento. Tente novamente em instantes."


DDL_TABELA_USUARIOS = """
CREATE TABLE IF NOT EXISTS usuarios (
    username TEXT PRIMARY KEY,
    nome_exibicao TEXT DEFAULT '',
    senha_hash TEXT NOT NULL DEFAULT '',
    eh_admin BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TEXT DEFAULT ''
);
"""


def garantir_tabela_usuarios_sql(planilha) -> None:
    """Garante a existência da tabela `usuarios` no Supabase mesmo que a conexão tenha vindo de cache."""
    if planilha is None:
        return
    conn = planilha.conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL_TABELA_USUARIOS)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def _sincronizar_admin_mestre_supabase(planilha) -> None:
    """Garante que o usuário mestre configurado em `st.secrets` exista como Admin ativo na tabela `usuarios`."""
    if planilha is None:
        return
    admin_user, admin_nome, admin_pass = obter_credencial_admin_mestre()
    if not admin_pass:
        return
    try:
        garantir_tabela_usuarios_sql(planilha)
        linhas = planilha.executar_leitura(
            "SELECT senha_hash, eh_admin, ativo FROM usuarios WHERE username = %s",
            (admin_user,),
        )
        precisa_gravar = True
        if linhas:
            hash_atual, eh_adm_at, ativo_at = linhas[0]
            if bool(eh_adm_at) and bool(ativo_at) and verificar_senha_hash(admin_pass, str(hash_atual or "")):
                precisa_gravar = False
        if precisa_gravar:
            novo_hash = gerar_hash_senha_segura(admin_pass)
            agora_s = agora_br().strftime("%d/%m/%Y %H:%M:%S")
            conn = planilha.conectar()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios (username, nome_exibicao, senha_hash, eh_admin, ativo, criado_em)
                        VALUES (%s, %s, %s, TRUE, TRUE, %s)
                        ON CONFLICT (username) DO UPDATE SET
                            nome_exibicao = EXCLUDED.nome_exibicao,
                            senha_hash = EXCLUDED.senha_hash,
                            eh_admin = TRUE,
                            ativo = TRUE
                        """,
                        (admin_user, admin_nome, novo_hash, agora_s),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception:
        pass




# ==============================================================================
# 2. CONSTANTES SQL, DDL E GERENCIADOR DE CONEXÃO SUPABASE (POSTGRESQL)
# ==============================================================================


TABELAS_SQL_VALIDAS = {
    "estoque_atual",
    "historico",
    "entradas_diarias",
    "saidas_diarias",
    "custos",
    "base_inicial",
    "ocultos",
    "pedidos_transito",
    "meta",
    "usuarios",
    "_bkp_estoque_atual",
    "_bkp_entradas_diarias",
    "_bkp_saidas_diarias",
    "_bkp_custos",
    "_bkp_base_inicial",
    "_bkp_ocultos",
    "_bkp_pedidos_transito",
}


CHAVES_PRIMARIAS_SQL = {
    "estoque_atual": ["codigo", "lote", "data"],
    "historico": ["codigo", "data"],
    "entradas_diarias": ["codigo", "data"],
    "saidas_diarias": ["codigo", "data"],
    "custos": ["codigo"],
    "base_inicial": ["codigo"],
    "ocultos": ["codigo"],
    "pedidos_transito": ["codigo"],
    "meta": ["chave"],
}


DDL_INICIALIZACAO_SUPABASE = """
CREATE TABLE IF NOT EXISTS estoque_atual (
    codigo TEXT NOT NULL,
    saldo_geral DOUBLE PRECISION DEFAULT 0,
    descricao TEXT DEFAULT '',
    lote TEXT NOT NULL DEFAULT '',
    saldo_lote DOUBLE PRECISION DEFAULT 0,
    validade TEXT DEFAULT '',
    data TEXT NOT NULL,
    PRIMARY KEY (codigo, lote, data)
);
CREATE TABLE IF NOT EXISTS historico (
    codigo TEXT NOT NULL,
    saldo_geral DOUBLE PRECISION DEFAULT 0,
    data TEXT NOT NULL,
    PRIMARY KEY (codigo, data)
);
CREATE INDEX IF NOT EXISTS idx_historico_data ON historico (data);
CREATE TABLE IF NOT EXISTS entradas_diarias (
    codigo TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    qtd_entrada DOUBLE PRECISION DEFAULT 0,
    valor_entrada DOUBLE PRECISION DEFAULT 0,
    data TEXT NOT NULL,
    PRIMARY KEY (codigo, data)
);
CREATE INDEX IF NOT EXISTS idx_entradas_data ON entradas_diarias (data);
CREATE TABLE IF NOT EXISTS saidas_diarias (
    codigo TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    qtd_saida DOUBLE PRECISION DEFAULT 0,
    valor_venda DOUBLE PRECISION DEFAULT 0,
    data TEXT NOT NULL,
    PRIMARY KEY (codigo, data)
);
CREATE INDEX IF NOT EXISTS idx_saidas_data ON saidas_diarias (data);
CREATE TABLE IF NOT EXISTS custos (
    codigo TEXT PRIMARY KEY,
    descricao TEXT DEFAULT '',
    custo_unitario DOUBLE PRECISION DEFAULT 0,
    preco_tabela DOUBLE PRECISION DEFAULT 0
);
ALTER TABLE IF EXISTS custos ADD COLUMN IF NOT EXISTS preco_tabela DOUBLE PRECISION DEFAULT 0;
ALTER TABLE IF EXISTS _bkp_custos ADD COLUMN IF NOT EXISTS preco_tabela DOUBLE PRECISION DEFAULT 0;
CREATE TABLE IF NOT EXISTS base_inicial (
    codigo TEXT PRIMARY KEY,
    descricao TEXT DEFAULT '',
    qtd_vendida DOUBLE PRECISION DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ocultos (
    codigo TEXT PRIMARY KEY,
    descricao TEXT DEFAULT '',
    data_ocultado TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pedidos_transito (
    codigo TEXT PRIMARY KEY,
    descricao TEXT DEFAULT '',
    qtd_comprada DOUBLE PRECISION DEFAULT 0,
    data_compra TEXT DEFAULT '',
    silenciar_ate TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS usuarios (
    username TEXT PRIMARY KEY,
    nome_exibicao TEXT DEFAULT '',
    senha_hash TEXT NOT NULL DEFAULT '',
    eh_admin BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS _bkp_estoque_atual (LIKE estoque_atual INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_entradas_diarias (LIKE entradas_diarias INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_saidas_diarias (LIKE saidas_diarias INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_custos (LIKE custos INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_base_inicial (LIKE base_inicial INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_ocultos (LIKE ocultos INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _bkp_pedidos_transito (LIKE pedidos_transito INCLUDING ALL);
"""


def _sanitizar_database_url(url_bruta: str) -> str:
    if not url_bruta:
        return ""
    s = str(url_bruta).strip().strip('"').strip("'")
    s = re.sub(r":\[([^\[\]@]+)\]@", r":\1@", s)
    if s.startswith("postgres://"):
        s = "postgresql://" + s[len("postgres://"):]
    return s


def obter_url_supabase_secrets() -> str:
    for ch in ("database_url", "DATABASE_URL", "supabase_db_url", "SUPABASE_DB_URL", "postgres_url"):
        val = obter_secret(ch, "")
        if val and str(val).strip():
            return _sanitizar_database_url(str(val))
    try:
        conns = obter_secret("connections", {})
        if isinstance(conns, dict):
            for sub in ("postgresql", "supabase", "postgres"):
                if sub in conns and isinstance(conns[sub], dict) and conns[sub].get("url"):
                    return _sanitizar_database_url(str(conns[sub]["url"]))
    except Exception:
        pass
    return ""


class ConexaoSupabasePG:
    """Gerencia conexões PostgreSQL isoladas por thread (thread-safe) com reconexão automática."""

    def __init__(self, db_url: str):
        self.db_url = _sanitizar_database_url(db_url)
        self._local = threading.local()
        self._schema_lock = threading.RLock()
        self._esquema_verificado = False

    def _fechar_conn_local(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._local.conn = None

    def conectar(self):
        import psycopg2
        from psycopg2 import extensions as pg_ext
        conn = getattr(self._local, "conn", None)
        if conn is not None and getattr(conn, "closed", 1) == 0:
            if conn.info.transaction_status == pg_ext.TRANSACTION_STATUS_INTRANS:
                return conn
            try:
                if conn.info.transaction_status != pg_ext.TRANSACTION_STATUS_IDLE:
                    conn.rollback()
                with conn.cursor() as cur_ping:
                    cur_ping.execute("SELECT 1")
                conn.commit()
                return conn
            except Exception:
                self._fechar_conn_local()

        kwargs_conn = {"dsn": self.db_url, "connect_timeout": 15}
        if "sslmode=" not in self.db_url.lower() and (
            "supabase.com" in self.db_url.lower() or "supabase.co" in self.db_url.lower()
        ):
            kwargs_conn["sslmode"] = "require"
        conn = psycopg2.connect(**kwargs_conn)
        conn.autocommit = False
        self._local.conn = conn
        if not self._esquema_verificado:
            with self._schema_lock:
                if not self._esquema_verificado:
                    with conn.cursor() as cur_init:
                        cur_init.execute(DDL_INICIALIZACAO_SUPABASE)
                    conn.commit()
                    self._esquema_verificado = True
        return conn

    @contextmanager
    def transacao(self):
        conn = self.conectar()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                self._fechar_conn_local()
            raise

    def executar_leitura(self, sql: str, params=None) -> list:
        from psycopg2 import extensions as pg_ext
        for tentativa in range(2):
            conn = self.conectar()
            estava_idle = (conn.info.transaction_status == pg_ext.TRANSACTION_STATUS_IDLE)
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                    linhas = cur.fetchall()
                if estava_idle:
                    conn.commit()
                return linhas
            except Exception:
                if not estava_idle:
                    raise
                try:
                    conn.rollback()
                except Exception:
                    pass
                if tentativa == 0:
                    self._fechar_conn_local()
                else:
                    raise
        return []


@st.cache_resource(ttl=3600, show_spinner=False)
def _conectar_supabase_cached(db_url: str, versao_esquema: str = "v23") -> ConexaoSupabasePG:
    cliente_pg = ConexaoSupabasePG(db_url)
    cliente_pg.conectar()
    return cliente_pg


def obter_conexao_supabase():
    db_url = obter_url_supabase_secrets()
    if not db_url:
        return None, (
            'A chave `database_url` ainda não foi adicionada nos `Secrets` do Streamlit Cloud. '
            'Adicione `database_url = "postgresql://..."` no topo dos Secrets do Streamlit!'
        )
    try:
        cliente_pg = _conectar_supabase_cached(db_url)
        cliente_pg.conectar()
        return cliente_pg, None
    except Exception as e:
        return None, str(e)




# ==============================================================================
# 3. CRUD SQL, TRANSAÇÕES ATÔMICAS, BACKUPS AUTOMÁTICOS E SOMA INCREMENTAL
# ==============================================================================


def _validar_nome_tabela_sql(nome_aba: str) -> str:
    nome_limpo = str(nome_aba).strip()
    if nome_limpo not in TABELAS_SQL_VALIDAS:
        raise ValueError(f"Tabela SQL não reconhecida: {nome_limpo}")
    return nome_limpo


def _preparar_tuplas_para_insert(df: pd.DataFrame, colunas: list) -> list:
    if df is None or df.empty:
        return []
    df_c = df[colunas].copy()
    for col in colunas:
        if col in COLUNAS_NUMERICAS:
            df_c[col] = pd.to_numeric(df_c[col], errors="coerce").fillna(0.0).astype(float)
        else:
            df_c[col] = df_c[col].fillna("").astype(str)
    return [tuple(x) for x in df_c.to_numpy()]


def ler_tabela_sql(planilha: ConexaoSupabasePG, nome_aba: str) -> pd.DataFrame:
    tabela = _validar_nome_tabela_sql(nome_aba)
    aba_esquema = tabela[5:] if tabela.startswith("_bkp_") else tabela
    colunas = ESQUEMA_ABAS.get(aba_esquema, ["chave", "valor"])
    cols_sql = ", ".join(colunas)
    if aba_esquema in ("historico", "entradas_diarias", "saidas_diarias"):
        limite_str = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")
        sql = f"SELECT {cols_sql} FROM {tabela} WHERE data >= %s ORDER BY data ASC, codigo ASC"
        linhas = planilha.executar_leitura(sql, (limite_str,))
    else:
        sql = f"SELECT {cols_sql} FROM {tabela}"
        linhas = planilha.executar_leitura(sql)
    if not linhas:
        return padronizar_dataframe(pd.DataFrame(columns=colunas), aba_esquema, origem_banco=True)
    df = pd.DataFrame(linhas, columns=colunas)
    return padronizar_dataframe(df, aba_esquema, origem_banco=True)


def gravar_tabela_sql(
    planilha: ConexaoSupabasePG,
    nome_aba: str,
    df: pd.DataFrame,
    permitir_vazio: bool = False,
    conn_externa=None,
):
    from psycopg2.extras import execute_values
    if df is None:
        return
    if df.empty and not permitir_vazio:
        return
    tabela = _validar_nome_tabela_sql(nome_aba)
    aba_esquema = tabela[5:] if tabela.startswith("_bkp_") else tabela
    df_padrao = padronizar_dataframe(df, aba_esquema, origem_banco=True) if aba_esquema in ESQUEMA_ABAS else df.copy()
    colunas = ESQUEMA_ABAS.get(aba_esquema, list(df_padrao.columns))
    pk_cols = CHAVES_PRIMARIAS_SQL.get(aba_esquema, [colunas[0]])
    df_padrao = df_padrao.drop_duplicates(subset=pk_cols, keep="last").reset_index(drop=True)
    tuplas = _preparar_tuplas_para_insert(df_padrao, colunas)
    cols_sql = ", ".join(colunas)
    pk_sql = ", ".join(pk_cols)
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c not in pk_cols)
    clausula_conflito = (
        f"ON CONFLICT ({pk_sql}) DO UPDATE SET {set_sql}"
        if set_sql
        else f"ON CONFLICT ({pk_sql}) DO NOTHING"
    )

    if conn_externa is not None:
        with conn_externa.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {tabela}")
            if tuplas:
                sql_ins = f"INSERT INTO {tabela} ({cols_sql}) VALUES %s {clausula_conflito}"
                execute_values(cur, sql_ins, tuplas, page_size=2000)
        return

    with planilha.transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {tabela}")
            if tuplas:
                sql_ins = f"INSERT INTO {tabela} ({cols_sql}) VALUES %s {clausula_conflito}"
                execute_values(cur, sql_ins, tuplas, page_size=2000)


def salvar_backup_automatico_sql(
    planilha: ConexaoSupabasePG,
    nome_aba_origem: str,
    df_atual_memoria: pd.DataFrame = None,
    permitir_vazio: bool = False,
    conn_externa=None,
):
    """Salva uma cópia instantânea em _bkp_<nome_aba> diretamente no PostgreSQL antes de qualquer alteração."""
    if nome_aba_origem == "historico":
        return
    tabela_orig = _validar_nome_tabela_sql(nome_aba_origem)
    tabela_bkp = _validar_nome_tabela_sql(f"_bkp_{nome_aba_origem}")
    if df_atual_memoria is not None and not df_atual_memoria.empty:
        gravar_tabela_sql(
            planilha,
            tabela_bkp,
            df_atual_memoria,
            permitir_vazio=permitir_vazio,
            conn_externa=conn_externa,
        )
        return
    if conn_externa is not None:
        with conn_externa.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {tabela_orig}")
            qtd_atual = int(cur.fetchone()[0])
            if qtd_atual > 0 or permitir_vazio:
                cur.execute(f"TRUNCATE TABLE {tabela_bkp}")
                if qtd_atual > 0:
                    cur.execute(f"INSERT INTO {tabela_bkp} SELECT * FROM {tabela_orig}")
        return
    with planilha.transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {tabela_orig}")
            qtd_atual = int(cur.fetchone()[0])
            if qtd_atual > 0 or permitir_vazio:
                cur.execute(f"TRUNCATE TABLE {tabela_bkp}")
                if qtd_atual > 0:
                    cur.execute(f"INSERT INTO {tabela_bkp} SELECT * FROM {tabela_orig}")


def remover_datas_tabela_sql(
    planilha: ConexaoSupabasePG,
    nome_aba: str,
    datas_remover: set,
    df_atual_memoria: pd.DataFrame = None,
) -> int:
    tabela = _validar_nome_tabela_sql(nome_aba)
    datas_iso_alvo = []
    for d in (datas_remover or set()):
        dt_p = converter_datas_deterministico(pd.Series([str(d).strip()]))
        if not dt_p.empty and pd.notna(dt_p.iloc[0]):
            datas_iso_alvo.append(dt_p.iloc[0].strftime("%Y-%m-%d"))
        elif str(d).strip():
            datas_iso_alvo.append(str(d).strip())
    datas_iso_alvo = sorted(set(datas_iso_alvo))
    if not datas_iso_alvo:
        return 0

    if tabela in ("entradas_diarias", "saidas_diarias"):
        salvar_backup_automatico_sql(planilha, tabela, df_atual_memoria, permitir_vazio=True)

    conn = planilha.conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {tabela} WHERE data = ANY(%s)", (datas_iso_alvo,))
            qtd_removidas = int(cur.rowcount or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if tabela in ("entradas_diarias", "saidas_diarias"):
        reg_hashes = st.session_state.setdefault("hashes_soma_por_data", {})
        for dt_rm in datas_iso_alvo:
            reg_hashes.pop(f"{tabela}::{dt_rm}", None)
    return qtd_removidas


def restaurar_backup_automatico_sql(
    planilha: ConexaoSupabasePG,
    nome_aba_destino: str,
    df_atual_memoria: pd.DataFrame = None,
) -> int:
    tabela_dest = _validar_nome_tabela_sql(nome_aba_destino)
    tabela_bkp = _validar_nome_tabela_sql(f"_bkp_{nome_aba_destino}")
    aba_permite_vazio = tabela_dest in ("ocultos", "pedidos_transito", "entradas_diarias", "saidas_diarias")
    df_bkp = ler_tabela_sql(planilha, tabela_bkp)
    if df_bkp.empty and not aba_permite_vazio:
        raise ValueError(f"Ainda não há registros salvos na cópia automática anterior (`{tabela_bkp}`) para restaurar.")

    if tabela_dest == "estoque_atual":
        datas_atuais = set()
        if df_atual_memoria is not None and not df_atual_memoria.empty and "data" in df_atual_memoria.columns:
            datas_atuais.update(str(d).strip() for d in df_atual_memoria["data"].unique() if str(d).strip())
        df_est_nuvem = ler_tabela_sql(planilha, "estoque_atual")
        if not df_est_nuvem.empty and "data" in df_est_nuvem.columns:
            datas_atuais.update(str(d).strip() for d in df_est_nuvem["data"].unique() if str(d).strip())
        datas_rest = (
            {str(d).strip() for d in df_bkp["data"].unique() if str(d).strip()}
            if "data" in df_bkp.columns
            else set()
        )
        datas_indevidas = datas_atuais - datas_rest
        if datas_indevidas:
            remover_datas_tabela_sql(planilha, "historico", datas_indevidas)
        gravar_tabela_sql(planilha, "estoque_atual", df_bkp)
        for dt_r in sorted(datas_rest):
            df_dia_rest = df_bkp[df_bkp["data"] == dt_r].copy()
            gravar_historico_incremental_sql(planilha, df_dia_rest, dt_r)
    else:
        gravar_tabela_sql(planilha, tabela_dest, df_bkp, permitir_vazio=aba_permite_vazio)

    if tabela_dest in ("entradas_diarias", "saidas_diarias"):
        reg_hashes = st.session_state.setdefault("hashes_soma_por_data", {})
        chaves_limpar = [k for k in reg_hashes if k.startswith(f"{tabela_dest}::")]
        for k_l in chaves_limpar:
            reg_hashes.pop(k_l, None)
    return len(df_bkp)


def _calcular_hash_dataframe_dia(df_dia: pd.DataFrame, nome_aba: str) -> str:
    if df_dia is None or df_dia.empty:
        return ""
    df_p = padronizar_dataframe(df_dia, nome_aba, origem_banco=True).sort_values("codigo").reset_index(drop=True)
    if df_p.empty:
        return ""
    txt_serial = df_p.to_csv(index=False)
    return hashlib.sha256(txt_serial.encode("utf-8")).hexdigest()[:16]


def _verificar_sobreposicao_soma_mesmo_dia(
    df_existente_dia: pd.DataFrame,
    df_novo_dia: pd.DataFrame,
    col_qtd: str,
    hashes_ja_no_dia: list,
    hash_efetivo: str,
    permitir_somar_codigos_repetidos_dia: bool = False,
    rotulo_aba: str = "Movimento",
    data_ref_str: str = "",
) -> tuple[bool, list]:
    """
    Proteção em 3 camadas para o modo '➕ Somar ao dia':
    1) Bloqueia se o hash do arquivo já estiver registrado naquela data.
    2) Bloqueia se todos os pares (codigo, qtd) do arquivo enviado já constarem idênticos naquela data
       (protege inclusive datas importadas antes de existir registro de hash).
    3) Se houver códigos repetidos com quantidades diferentes na mesma data (>= 50% ou >= 5 itens) e
       'permitir_somar_codigos_repetidos_dia' estiver desmarcado, bloqueia com aviso claro.
    """
    if df_existente_dia is None or df_existente_dia.empty or df_novo_dia is None or df_novo_dia.empty:
        return False, []
    if hash_efetivo and hash_efetivo in hashes_ja_no_dia:
        return True, []

    mapa_qtd_exist = dict(zip(df_existente_dia["codigo"].astype(str), df_existente_dia[col_qtd].astype(float)))
    mapa_qtd_novo = dict(zip(df_novo_dia["codigo"].astype(str), df_novo_dia[col_qtd].astype(float)))

    cods_exist = set(mapa_qtd_exist.keys())
    cods_novos = set(mapa_qtd_novo.keys())
    cods_inter = sorted(cods_exist & cods_novos)

    if not cods_inter:
        return False, []

    todos_iguais = (len(cods_inter) == len(cods_novos)) and all(
        abs(mapa_qtd_exist[c] - mapa_qtd_novo[c]) < 1e-4 for c in cods_novos
    )
    if todos_iguais:
        return True, cods_inter

    sigs_novo = {f"sku:{c}:{mapa_qtd_novo[c]:.4f}" for c in cods_novos}
    if sigs_novo and sigs_novo.issubset(set(hashes_ja_no_dia)):
        return True, cods_inter

    taxa_sobreposicao = len(cods_inter) / max(len(cods_novos), 1)
    if (
        not permitir_somar_codigos_repetidos_dia
        and len(cods_inter) >= 1
        and (taxa_sobreposicao >= 0.50 or len(cods_inter) >= 5)
    ):
        dt_fmt = pd.to_datetime(data_ref_str, format="%Y-%m-%d", errors="coerce")
        str_dt = dt_fmt.strftime("%d/%m/%Y") if pd.notna(dt_fmt) else data_ref_str
        amostra_c = ", ".join(cods_inter[:6])
        raise ValueError(
            f"Trava contra Reexportação Duplicada no Modo 'Somar ao Dia' ({rotulo_aba} — {str_dt}): "
            f"**{len(cods_inter)} de {len(cods_novos)} produto(s)** deste arquivo ({taxa_sobreposicao*100:.0f}%) "
            f"**já possuem lançamento gravado na data {str_dt}** (ex: {amostra_c}). "
            f"Se você reexportou o relatório completo do dia no Siagri com alterações, **desmarque a caixa '➕ Somar ao dia'** "
            f"para atualizar o dia sem dobrar as quantidades! Caso realmente sejam duas notas diferentes do mesmo produto no mesmo dia, "
            f"marque nas Opções Avançadas a permissão para somar códigos já existentes na data."
        )
    return False, cods_inter


def gravar_historico_incremental_sql(
    db: ConexaoSupabasePG,
    df_novo_dia: pd.DataFrame,
    data_ref: str,
    conn_externa=None,
):
    """Grava o histórico diário compacto no PostgreSQL em uma única transação atômica (< 0,1s)."""
    from psycopg2.extras import execute_values
    df_novo_padrao = compactar_estoque_para_historico(df_novo_dia)
    if df_novo_padrao.empty:
        return
    data_ref_str = str(data_ref).strip()
    limite_str = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")
    df_novo_padrao["data"] = data_ref_str
    df_novo_padrao = df_novo_padrao.drop_duplicates(subset=["codigo", "data"], keep="last").reset_index(drop=True)
    tuplas = _preparar_tuplas_para_insert(df_novo_padrao, ["codigo", "saldo_geral", "data"])

    if conn_externa is not None:
        with conn_externa.cursor() as cur:
            cur.execute(
                "DELETE FROM historico WHERE data = %s OR data < %s",
                (data_ref_str, limite_str),
            )
            if tuplas:
                execute_values(
                    cur,
                    "INSERT INTO historico (codigo, saldo_geral, data) VALUES %s "
                    "ON CONFLICT (codigo, data) DO UPDATE SET saldo_geral = EXCLUDED.saldo_geral",
                    tuplas,
                    page_size=2500,
                )
        return

    with db.transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM historico WHERE data = %s OR data < %s",
                (data_ref_str, limite_str),
            )
            if tuplas:
                execute_values(
                    cur,
                    "INSERT INTO historico (codigo, saldo_geral, data) VALUES %s "
                    "ON CONFLICT (codigo, data) DO UPDATE SET saldo_geral = EXCLUDED.saldo_geral",
                    tuplas,
                    page_size=2500,
                )


def gravar_tabela_incremental_por_data_sql(
    planilha: ConexaoSupabasePG,
    nome_aba: str,
    df_novo_dia: pd.DataFrame,
    data_ref: str,
    somar_mesma_data: bool = False,
    df_atual_memoria: pd.DataFrame = None,
    hash_arquivo: str = "",
    criar_backup: bool = True,
    hashes_soma_atuais: dict = None,
    permitir_somar_codigos_repetidos_dia: bool = False,
    conn_externa=None,
) -> bool:
    from psycopg2.extras import execute_values
    if df_novo_dia is None or df_novo_dia.empty:
        return False
    if nome_aba == "historico":
        gravar_historico_incremental_sql(planilha, df_novo_dia, data_ref, conn_externa=conn_externa)
        return False

    tabela = _validar_nome_tabela_sql(nome_aba)
    data_ref_str = str(data_ref).strip()
    limite_str = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")

    df_base_existente = (
        df_atual_memoria.copy()
        if (df_atual_memoria is not None and not df_atual_memoria.empty)
        else ler_tabela_sql(planilha, tabela)
    )
    if not df_base_existente.empty:
        df_base_existente = podar_historico_max_dias(
            padronizar_dataframe(df_base_existente, tabela, origem_banco=True), tabela
        )

    registro_hashes_sessao = st.session_state.setdefault("hashes_soma_por_data", {})
    if hashes_soma_atuais:
        for k_h, lista_h in hashes_soma_atuais.items():
            if k_h not in registro_hashes_sessao:
                registro_hashes_sessao[k_h] = list(lista_h)

    chave_op = f"{tabela}::{data_ref_str}"
    hash_efetivo = str(hash_arquivo).strip() or _calcular_hash_dataframe_dia(df_novo_dia, tabela)
    ja_somado_ignorado = False

    df_mesmo_dia_existente = (
        df_base_existente[df_base_existente["data"] == data_ref_str].copy()
        if (not df_base_existente.empty and "data" in df_base_existente.columns)
        else pd.DataFrame()
    )

    col_qtd = "qtd_entrada" if tabela == "entradas_diarias" else "qtd_saida"
    sigs_atuais_sku = [
        f"sku:{r['codigo']}:{float(r[col_qtd]):.4f}"
        for _, r in df_novo_dia.iterrows()
    ]

    if somar_mesma_data and tabela in ("entradas_diarias", "saidas_diarias"):
        if df_mesmo_dia_existente.empty:
            registro_hashes_sessao[chave_op] = ([hash_efetivo] if hash_efetivo else []) + sigs_atuais_sku[:80]
        else:
            hashes_ja_no_dia = list(registro_hashes_sessao.get(chave_op, []))
            if not hashes_ja_no_dia:
                hash_base_antiga = _calcular_hash_dataframe_dia(df_mesmo_dia_existente, tabela)
                if hash_base_antiga:
                    hashes_ja_no_dia.append(hash_base_antiga)
                for _, r_ex in df_mesmo_dia_existente.iterrows():
                    hashes_ja_no_dia.append(f"sku:{r_ex['codigo']}:{float(r_ex[col_qtd]):.4f}")

            bloqueado_dup, _ = _verificar_sobreposicao_soma_mesmo_dia(
                df_existente_dia=df_mesmo_dia_existente,
                df_novo_dia=df_novo_dia,
                col_qtd=col_qtd,
                hashes_ja_no_dia=hashes_ja_no_dia,
                hash_efetivo=hash_efetivo,
                permitir_somar_codigos_repetidos_dia=permitir_somar_codigos_repetidos_dia,
                rotulo_aba="Entradas" if tabela == "entradas_diarias" else "Saídas",
                data_ref_str=data_ref_str,
            )
            if bloqueado_dup:
                ja_somado_ignorado = True
                df_novo_dia = df_mesmo_dia_existente.copy()
            else:
                df_mesmo_dia = df_mesmo_dia_existente.drop_duplicates(subset=["codigo", "data"], keep="last")
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
                if hash_efetivo:
                    hashes_ja_no_dia.append(hash_efetivo)
                hashes_ja_no_dia.extend(sigs_atuais_sku[:80])
                registro_hashes_sessao[chave_op] = hashes_ja_no_dia
    elif tabela in ("entradas_diarias", "saidas_diarias"):
        registro_hashes_sessao[chave_op] = ([hash_efetivo] if hash_efetivo else []) + sigs_atuais_sku[:80]

    if ja_somado_ignorado:
        return True

    df_novo_padrao = padronizar_dataframe(df_novo_dia, tabela, origem_banco=True)
    if df_novo_padrao.empty:
        return False

    if criar_backup and not df_base_existente.empty:
        salvar_backup_automatico_sql(planilha, tabela, df_base_existente, conn_externa=conn_externa)
    df_novo_padrao["data"] = data_ref_str
    colunas = ESQUEMA_ABAS[tabela]
    tuplas = _preparar_tuplas_para_insert(df_novo_padrao, colunas)
    cols_sql = ", ".join(colunas)
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c not in ("codigo", "data"))

    if conn_externa is not None:
        with conn_externa.cursor() as cur:
            cur.execute(
                f"DELETE FROM {tabela} WHERE data = %s OR data < %s",
                (data_ref_str, limite_str),
            )
            if tuplas:
                execute_values(
                    cur,
                    f"INSERT INTO {tabela} ({cols_sql}) VALUES %s "
                    f"ON CONFLICT (codigo, data) DO UPDATE SET {set_sql}",
                    tuplas,
                    page_size=2000,
                )
        return False

    with planilha.transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {tabela} WHERE data = %s OR data < %s",
                (data_ref_str, limite_str),
            )
            if tuplas:
                execute_values(
                    cur,
                    f"INSERT INTO {tabela} ({cols_sql}) VALUES %s "
                    f"ON CONFLICT (codigo, data) DO UPDATE SET {set_sql}",
                    tuplas,
                    page_size=2000,
                )
    return False


def migrar_arquivo_banco_para_supabase(planilha: ConexaoSupabasePG, arquivo_upload) -> dict:
    """
    Importa de uma só vez todas as abas de um arquivo Banco_Dados_Esteio_Rural.xlsx (ou pacote .zip)
    diretamente para as tabelas do Supabase PostgreSQL em uma transação atômica.
    """
    from psycopg2.extras import execute_values
    nome_arq = getattr(arquivo_upload, "name", "backup.xlsx").lower()
    conteudo = arquivo_upload.getvalue()
    abas_lidas = {}

    if nome_arq.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(conteudo), mode="r") as zf:
            nomes_zip = zf.namelist()
            for nz in nomes_zip:
                if nz.lower().endswith(".xlsx"):
                    bytes_xlsx = zf.read(nz)
                    xls = pd.ExcelFile(io.BytesIO(bytes_xlsx))
                    for sh in xls.sheet_names:
                        if sh in TABELAS_SQL_VALIDAS:
                            df_p = pd.read_excel(xls, sheet_name=sh, nrows=0)
                            conv = {c: _preservar_celula_excel for c in df_p.columns}
                            abas_lidas[sh] = pd.read_excel(xls, sheet_name=sh, converters=conv)
                elif nz.lower().endswith(".csv") and "historico" in nz.lower():
                    bytes_csv = zf.read(nz)
                    for enc in ("utf-8-sig", "cp1252", "latin1"):
                        for sep in (";", ",", "\t"):
                            try:
                                df_h_csv = pd.read_csv(io.BytesIO(bytes_csv), sep=sep, encoding=enc, dtype=str)
                                if df_h_csv.shape[1] >= 3:
                                    abas_lidas["historico"] = df_h_csv
                                    break
                            except Exception:
                                continue
                        if "historico" in abas_lidas:
                            break
    else:
        xls = pd.ExcelFile(io.BytesIO(conteudo))
        for sh in xls.sheet_names:
            if sh in TABELAS_SQL_VALIDAS:
                df_p = pd.read_excel(xls, sheet_name=sh, nrows=0)
                conv = {c: _preservar_celula_excel for c in df_p.columns}
                abas_lidas[sh] = pd.read_excel(xls, sheet_name=sh, converters=conv)

    if not abas_lidas:
        raise ValueError(
            "Nenhuma aba reconhecida do banco (`estoque_atual`, `historico`, `custos`, etc.) foi encontrada no arquivo enviado."
        )

    resumo_migrado = {}
    conn = planilha.conectar()
    try:
        with conn.cursor() as cur:
            for nome_tab, df_bruto in abas_lidas.items():
                aba_esq = nome_tab[5:] if nome_tab.startswith("_bkp_") else nome_tab
                if aba_esq not in ESQUEMA_ABAS:
                    continue
                df_pad = padronizar_dataframe(df_bruto, aba_esq, origem_banco=True)
                if aba_esq in ("historico", "entradas_diarias", "saidas_diarias"):
                    df_pad = podar_historico_max_dias(df_pad, aba_esq)
                colunas = ESQUEMA_ABAS[aba_esq]
                pk_cols = CHAVES_PRIMARIAS_SQL.get(aba_esq, [colunas[0]])
                df_pad = df_pad.drop_duplicates(subset=pk_cols, keep="last").reset_index(drop=True)
                tuplas = _preparar_tuplas_para_insert(df_pad, colunas)
                cols_sql = ", ".join(colunas)
                pk_sql = ", ".join(pk_cols)
                set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c not in pk_cols)
                clausula_conflito = (
                    f"ON CONFLICT ({pk_sql}) DO UPDATE SET {set_sql}"
                    if set_sql
                    else f"ON CONFLICT ({pk_sql}) DO NOTHING"
                )
                bkp_tab = f"_bkp_{nome_tab}"
                if (not nome_tab.startswith("_bkp_")) and (bkp_tab in TABELAS_SQL_VALIDAS) and (bkp_tab not in abas_lidas):
                    cur.execute(f"SELECT COUNT(*) FROM {nome_tab}")
                    if int(cur.fetchone()[0]) > 0:
                        cur.execute(f"TRUNCATE TABLE {bkp_tab}")
                        cur.execute(f"INSERT INTO {bkp_tab} SELECT * FROM {nome_tab}")
                cur.execute(f"TRUNCATE TABLE {nome_tab}")
                if tuplas:
                    execute_values(
                        cur,
                        f"INSERT INTO {nome_tab} ({cols_sql}) VALUES %s {clausula_conflito}",
                        tuplas,
                        page_size=2500,
                    )
                resumo_migrado[nome_tab] = len(tuplas)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return resumo_migrado




# ==============================================================================
# 4. GESTÃO DE USUÁRIOS, BACKUP SEMANAL E CARGA COMPLETA DO ESTADO
# ==============================================================================


def listar_usuarios_sql(planilha: ConexaoSupabasePG) -> pd.DataFrame:
    colunas_u = ["username", "nome_exibicao", "senha_hash", "eh_admin", "ativo", "criado_em"]
    garantir_tabela_usuarios_sql(planilha)
    linhas = planilha.executar_leitura(
        "SELECT username, nome_exibicao, senha_hash, eh_admin, ativo, criado_em FROM usuarios ORDER BY eh_admin DESC, username ASC"
    )
    if not linhas:
        return pd.DataFrame(columns=colunas_u)
    df_u = pd.DataFrame(linhas, columns=colunas_u)
    df_u["username"] = df_u["username"].astype(str).map(_normalizar_username)
    df_u["nome_exibicao"] = df_u["nome_exibicao"].fillna("").astype(str)
    df_u["senha_hash"] = df_u["senha_hash"].fillna("").astype(str)
    df_u["eh_admin"] = df_u["eh_admin"].fillna(False).astype(bool)
    df_u["ativo"] = df_u["ativo"].fillna(True).astype(bool)
    df_u["criado_em"] = df_u["criado_em"].fillna("").astype(str)
    return df_u


def salvar_usuario_sql(
    planilha: ConexaoSupabasePG,
    username: str,
    nome_exibicao: str,
    senha_plana: str,
    eh_admin: bool = False,
    ativo: bool = True,
):
    user_norm = _normalizar_username(username)
    if not user_norm or len(user_norm) < 3:
        raise ValueError("O nome de usuário deve ter pelo menos 3 caracteres (letras, números, ponto ou underline).")
    if not senha_plana or len(str(senha_plana)) < 4:
        raise ValueError("A senha deve ter pelo menos 4 caracteres.")
    nome_limpo = str(nome_exibicao or "").strip() or user_norm
    senha_h = gerar_hash_senha_segura(str(senha_plana))
    criado_s = agora_br().strftime("%d/%m/%Y %H:%M:%S")
    garantir_tabela_usuarios_sql(planilha)
    conn = planilha.conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_exibicao, senha_hash, eh_admin, ativo, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    nome_exibicao = EXCLUDED.nome_exibicao,
                    senha_hash = EXCLUDED.senha_hash,
                    eh_admin = EXCLUDED.eh_admin,
                    ativo = EXCLUDED.ativo
                """,
                (user_norm, nome_limpo, senha_h, bool(eh_admin), bool(ativo), criado_s),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def atualizar_status_ou_remover_usuarios_sql(
    planilha: ConexaoSupabasePG,
    atualizacoes_status: list,
    usernames_remover: list,
    admin_mestre_user: str,
):
    garantir_tabela_usuarios_sql(planilha)
    conn = planilha.conectar()
    try:
        with conn.cursor() as cur:
            for u_name, novo_nome, novo_ativo in atualizacoes_status:
                u_norm = _normalizar_username(u_name)
                if not u_norm:
                    continue
                if u_norm == admin_mestre_user:
                    novo_ativo = True
                cur.execute(
                    "UPDATE usuarios SET nome_exibicao = %s, ativo = %s WHERE username = %s",
                    (str(novo_nome or "").strip() or u_norm, bool(novo_ativo), u_norm),
                )
            for u_rm in usernames_remover:
                u_norm = _normalizar_username(u_rm)
                if u_norm and u_norm != admin_mestre_user:
                    cur.execute("DELETE FROM usuarios WHERE username = %s", (u_norm,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def registrar_backup_semanal_sql(planilha: ConexaoSupabasePG, data_bkp_iso: str = "") -> str:
    """Grava a data do último backup semanal baixado na tabela `meta` do Supabase."""
    dt_iso = str(data_bkp_iso).strip() or hoje_br().strftime("%Y-%m-%d")
    if planilha is not None:
        conn = planilha.conectar()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meta (chave, valor)
                    VALUES ('ultimo_backup_semanal', %s)
                    ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor
                    """,
                    (dt_iso,),
                )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
    st.session_state["ultimo_backup_semanal_sessao"] = dt_iso
    return dt_iso


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_estado_completo() -> dict:
    planilha, erro = obter_conexao_supabase()
    if planilha is None:
        raise RuntimeError(f"Não foi possível conectar ao Supabase (PostgreSQL): {erro}")
    df_est = ler_tabela_sql(planilha, "estoque_atual")
    df_hist = podar_historico_max_dias(ler_tabela_sql(planilha, "historico"), "historico")
    df_ent = podar_historico_max_dias(ler_tabela_sql(planilha, "entradas_diarias"), "entradas_diarias")
    df_sai = podar_historico_max_dias(ler_tabela_sql(planilha, "saidas_diarias"), "saidas_diarias")
    df_cus = ler_tabela_sql(planilha, "custos")
    df_base = ler_tabela_sql(planilha, "base_inicial")
    df_ocul = ler_tabela_sql(planilha, "ocultos")
    df_trans_bruto = ler_tabela_sql(planilha, "pedidos_transito")
    df_trans, cods_desp_nf, cods_exp_15d = depurar_pedidos_transito_auto_despertar(df_trans_bruto, df_ent)
    df_meta = ler_tabela_sql(planilha, "meta")
    dias_base = 87
    ult_att = "Sincronizado via Supabase SQL"
    ultima_data_custos_t1 = ""
    ultimo_backup_semanal = ""
    grupos_pref_custom = {}
    grupos_sku_custom = {}
    mp_custom_map = {}
    hashes_soma_meta = {}
    limite_iso_meta = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")
    if not df_meta.empty and "chave" in df_meta.columns and "valor" in df_meta.columns:
        mapa_meta = dict(zip(df_meta["chave"], df_meta["valor"]))
        try:
            dias_base = int(float(mapa_meta.get("dias_base", 87)))
        except ValueError:
            dias_base = 87
        ult_att = mapa_meta.get("ultima_atualizacao", ult_att)
        ultima_data_custos_t1 = str(mapa_meta.get("ultima_data_custos_t1", "")).strip()
        ultimo_backup_semanal = str(mapa_meta.get("ultimo_backup_semanal", "")).strip()
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
            elif ch_s.startswith("mp_flag_") and val_s in ("0", "1"):
                sku_mp = normalizar_codigo_sku(ch_s[len("mp_flag_"):])
                if sku_mp:
                    mp_custom_map[sku_mp] = val_s
            elif ch_s.startswith("soma_hashes_") and val_s:
                chave_aba_dt = ch_s[len("soma_hashes_"):].strip()
                partes_dt = chave_aba_dt.split("::")
                if len(partes_dt) == 2 and partes_dt[1] >= limite_iso_meta:
                    lista_h = [h.strip() for h in val_s.split(",") if h.strip()]
                    if lista_h:
                        hashes_soma_meta[chave_aba_dt] = lista_h
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
        "ultima_data_custos_t1": ultima_data_custos_t1,
        "ultimo_backup_semanal": ultimo_backup_semanal,
        "grupos_pref_custom": grupos_pref_custom,
        "grupos_sku_custom": grupos_sku_custom,
        "mp_custom_map": mp_custom_map,
        "hashes_soma_meta": hashes_soma_meta,
        "df_meta_bruto": df_meta,
    }
