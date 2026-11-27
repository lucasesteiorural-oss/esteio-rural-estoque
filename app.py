"""
app.py — Ponto de entrada Streamlit: configuração da página, autenticação, conexão/carregamento
do Supabase, cabeçalho e roteamento das 7 abas (Esteio Rural — Arquitetura Modular v37).
"""
import html
import pandas as pd
import streamlit as st

from parsers import (
    ESQUEMA_ABAS,
    hoje_br,
    formatar_num_br,
    gerar_pacote_backup_leve,
    avaliar_alerta_backup_semanal,
)
from database import (
    _sincronizar_admin_mestre_supabase,
    _conectar_supabase_cached,
    obter_conexao_supabase,
    registrar_backup_semanal_sql,
    carregar_estado_completo,
)
from ui.styles import aplicar_tema_obsidian_bento
from ui.auth import verificar_autenticacao
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_compras import render_tab_compras
from ui.tab_fefo import render_tab_fefo
from ui.tab_curva_abc import render_tab_curva_abc
from ui.tab_auditoria import render_tab_auditoria
from ui.tab_importacao import render_tab_importacao
from ui.tab_ocultos import render_tab_ocultos

# 1. Configuração da página & tema visual Obsidian Dark Neon Bento UI
st.set_page_config(
    page_title="Esteio Rural — Inteligência de Estoque & Giro Sazonal",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)
aplicar_tema_obsidian_bento()

# 2. Autenticação fail-closed
if not verificar_autenticacao():
    st.stop()

# 3. Conexão com Supabase (PostgreSQL) & cabeçalho principal
db_supabase, erro_db = obter_conexao_supabase()
conectado_nuvem = db_supabase is not None
if conectado_nuvem and not st.session_state.get("_admin_mestre_sincronizado_v22", False):
    _sincronizar_admin_mestre_supabase(db_supabase)
    st.session_state["_admin_mestre_sincronizado_v22"] = True

usuario_atual_logado = str(st.session_state.get("usuario_logado", "admin")).strip()
nome_atual_logado = str(st.session_state.get("nome_usuario_logado", usuario_atual_logado)).strip()
eh_usuario_admin = bool(st.session_state.get("eh_admin_esteio", False))
tag_perfil_topo = "👑 Admin" if eh_usuario_admin else "👤 Consulta"

col_titulo, col_status, col_user_box = st.columns([2.9, 1.15, 0.75])
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
    texto_status = "🟢 Supabase SQL Online" if conectado_nuvem else "❌ Sem Conexão"
    st.markdown(
        f"""
        <div class="status-box">
            <div class="status-label">{tag_perfil_topo}: {html.escape(nome_atual_logado)}</div>
            <div class="status-value" title="{html.escape(texto_status)}">{html.escape(texto_status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_user_box:
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True, key="btn_logout_esteio_v22"):
        for k_sair in ("autenticado_esteio", "usuario_logado", "nome_usuario_logado", "eh_admin_esteio"):
            st.session_state.pop(k_sair, None)
        st.rerun()

if not conectado_nuvem:
    st.error(
        f"❌ **Não foi possível conectar ao Supabase (PostgreSQL):** {erro_db}\n\n"
        "Verifique se a linha `database_url = \"postgresql://...\"` está colada no topo dos `Secrets` do Streamlit Cloud "
        "e se o projeto no Supabase está ativo (não pausado)."
    )
    if st.button("🔄 Tentar Reconectar ao Supabase Agora", type="primary"):
        _conectar_supabase_cached.clear()
        carregar_estado_completo.clear()
        st.rerun()
    st.stop()

try:
    with st.spinner("Carregando dados do Supabase (PostgreSQL)..."):
        estado = carregar_estado_completo()
except Exception as erro_leitura:
    st.error(f"❌ Erro ao ler tabelas do Supabase: {erro_leitura}")
    if st.button("🔄 Tentar Novamente", type="primary"):
        _conectar_supabase_cached.clear()
        carregar_estado_completo.clear()
        st.rerun()
    st.stop()

# 4. Desempacotamento do estado, filtros de ocultos e alerta semanal de backup
df_estoque_bruto = estado["estoque_atual"]
df_historico_bruto = estado["historico"]
df_entradas_bruto = estado["entradas_diarias"]
df_saidas_bruto = estado["saidas_diarias"]
df_custos = estado["custos"]
df_base_vendas = estado["base_inicial"]
df_ocultos = estado["ocultos"]
df_pedidos_transito = estado.get("pedidos_transito", pd.DataFrame(columns=ESQUEMA_ABAS["pedidos_transito"]))
dias_base_atual = int(estado.get("dias_base", 87))
ultima_data_custos_t1 = str(estado.get("ultima_data_custos_t1", "")).strip()
st.session_state["ultima_data_custos_t1_sessao"] = ultima_data_custos_t1
ultimo_backup_semanal = str(estado.get("ultimo_backup_semanal", "")).strip()
st.session_state["ultimo_backup_semanal_sessao"] = ultimo_backup_semanal

ultimas_att_caixas = dict(estado.get("ultimas_atualizacoes_caixas", {}))
df_meta_ref_caixas = estado.get("df_meta_bruto", pd.DataFrame())
if (
    df_meta_ref_caixas is not None
    and not df_meta_ref_caixas.empty
    and "chave" in df_meta_ref_caixas.columns
    and "valor" in df_meta_ref_caixas.columns
):
    mapa_meta_caixas = dict(zip(df_meta_ref_caixas["chave"].astype(str), df_meta_ref_caixas["valor"].astype(str)))
    for nome_cx in ("estoque", "entradas", "saidas", "custos", "base"):
        val_cx = str(mapa_meta_caixas.get(f"ult_att_{nome_cx}", "")).strip()
        if val_cx and not ultimas_att_caixas.get(nome_cx):
            ultimas_att_caixas[nome_cx] = val_cx


def _on_download_backup_confirmado():
    try:
        registrar_backup_semanal_sql(db_supabase)
        carregar_estado_completo.clear()
    except Exception:
        pass


grupos_pref_custom = estado.get("grupos_pref_custom", {})
grupos_sku_custom = estado.get("grupos_sku_custom", {})
mp_custom_map = estado.get("mp_custom_map", {})
st.session_state["mp_custom_map_sessao"] = dict(mp_custom_map)
hashes_soma_meta = estado.get("hashes_soma_meta", {})
if hashes_soma_meta:
    reg_h_init = st.session_state.setdefault("hashes_soma_por_data", {})
    for k_hm, v_hm in hashes_soma_meta.items():
        if k_hm not in reg_h_init:
            reg_h_init[k_hm] = list(v_hm)

codigos_ocultos = set(df_ocultos["codigo"].unique()) if not df_ocultos.empty else set()
codigos_em_transito = set(df_pedidos_transito["codigo"].unique()) if not df_pedidos_transito.empty else set()
mostrar_ocultos_temp = False
if len(codigos_ocultos) > 0:
    col_aviso_oc, col_toggle_oc = st.columns([2.8, 1.2])
    with col_aviso_oc:
        st.caption(
            f"🙈 Atualmente há **{formatar_num_br(len(codigos_ocultos))} produto(s) oculto(s)** dos relatórios (gerencie na Aba 7)."
        )
    with col_toggle_oc:
        mostrar_ocultos_temp = st.toggle("👁️ Mostrar ocultos temporariamente", value=False)

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

if eh_usuario_admin and (not df_estoque_bruto.empty):
    exibir_alerta_bkp, dias_sem_bkp, data_ult_bkp_br = avaliar_alerta_backup_semanal(ultimo_backup_semanal)
    if exibir_alerta_bkp:
        if dias_sem_bkp is None:
            txt_alerta_bkp = (
                "💾 **Lembrete Semanal de Backup:** Você ainda não baixou nenhuma cópia de segurança (`.zip`) "
                "do banco de dados no seu computador."
            )
        else:
            txt_alerta_bkp = (
                f"💾 **Lembrete Semanal de Backup:** Já se passaram **{formatar_num_br(dias_sem_bkp)} dia(s)** "
                f"desde o último backup baixado (em **{data_ult_bkp_br}**). Baixe o pacote `.zip` para manter uma cópia segura no seu computador."
            )
        col_bkp_msg, col_bkp_act1, col_bkp_act2 = st.columns([2.6, 1.0, 0.7])
        with col_bkp_msg:
            st.warning(txt_alerta_bkp)
        with col_bkp_act1:
            st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
            if "backup_zip_bytes" not in st.session_state:
                if st.button("📦 Preparar Backup (.zip)", type="primary", use_container_width=True, key="btn_prep_bkp_topo"):
                    with st.spinner("Gerando pacote de backup (.zip)..."):
                        st.session_state["backup_zip_bytes"] = gerar_pacote_backup_leve(estado)
                        st.session_state["backup_zip_nome"] = f"Backup_Completo_Esteio_{hoje_br().strftime('%Y-%m-%d')}.zip"
                    st.rerun()
            else:
                st.download_button(
                    label="📥 Baixar Backup (.zip)",
                    data=st.session_state["backup_zip_bytes"],
                    file_name=st.session_state.get("backup_zip_nome", "Backup_Completo_Esteio.zip"),
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    on_click=_on_download_backup_confirmado,
                    key="dl_bkp_zip_topo",
                )
        with col_bkp_act2:
            st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
            if st.button("⏭️ Adiar 7d", use_container_width=True, key="btn_adiar_bkp_topo", help="Marca o lembrete como visto e avisa novamente daqui a 7 dias."):
                try:
                    registrar_backup_semanal_sql(db_supabase)
                    carregar_estado_completo.clear()
                    st.rerun()
                except Exception as erro_adiar:
                    st.error(f"Erro ao registrar adiamento: {erro_adiar}")

# 5. Contexto compartilhado e roteamento das 7 abas
ctx = {
    "db_supabase": db_supabase,
    "eh_usuario_admin": eh_usuario_admin,
    "nome_atual_logado": nome_atual_logado,
    "estado": estado,
    "df_estoque": df_estoque,
    "df_estoque_bruto": df_estoque_bruto,
    "df_historico": df_historico,
    "df_historico_bruto": df_historico_bruto,
    "df_entradas": df_entradas,
    "df_entradas_bruto": df_entradas_bruto,
    "df_saidas": df_saidas,
    "df_saidas_bruto": df_saidas_bruto,
    "df_custos": df_custos,
    "df_custos_rel": df_custos_rel,
    "df_base_vendas": df_base_vendas,
    "df_base_vendas_rel": df_base_vendas_rel,
    "df_ocultos": df_ocultos,
    "df_pedidos_transito": df_pedidos_transito,
    "dias_base_atual": dias_base_atual,
    "ultima_data_custos_t1": ultima_data_custos_t1,
    "ultimo_backup_semanal": ultimo_backup_semanal,
    "ultimas_att_caixas": ultimas_att_caixas,
    "grupos_pref_custom": grupos_pref_custom,
    "grupos_sku_custom": grupos_sku_custom,
    "mp_custom_map": mp_custom_map,
    "hashes_soma_meta": hashes_soma_meta,
    "codigos_ocultos": codigos_ocultos,
    "codigos_em_transito": codigos_em_transito,
    "on_download_backup_confirmado": _on_download_backup_confirmado,
}

aba_dash, aba_compras, aba_fefo, aba_abc, aba_auditoria, aba_importacao, aba_ocultos = st.tabs(
    [
        "📊 1. Dashboard Executivo (Power BI)",
        "🛒 2. Sugestão de Compras & Cotação",
        "⏳ 3. Radar FEFO & Promoções IA",
        "📈 4. Curva ABC Financeira",
        "🔍 5. Auditoria de ERP",
        "📥 6. Importação & Backup",
        f"👁️‍🗨️ 7. Ocultar Produtos ({formatar_num_br(len(codigos_ocultos))})",
    ]
)

with aba_dash:
    render_tab_dashboard(ctx)
with aba_compras:
    render_tab_compras(ctx)
with aba_fefo:
    render_tab_fefo(ctx)
with aba_abc:
    render_tab_curva_abc(ctx)
with aba_auditoria:
    render_tab_auditoria(ctx)
with aba_importacao:
    render_tab_importacao(ctx)
with aba_ocultos:
    render_tab_ocultos(ctx)
