"""
ui/tab_importacao.py — Aba 6: Importação em lote 'Tudo ou Nada', restauração de backups,
grupos/prefixos, MP de fábrica e gestão de usuários.
"""
import hashlib
from datetime import timedelta
import pandas as pd
import streamlit as st

from parsers import (
    hoje_br,
    agora_br,
    formatar_num_br,
    formatar_qtd_br,
    formatar_moeda_br,
    formatar_pct_br,
    estilizar_tabela_br,
    normalizar_codigo_sku,
    padronizar_dataframe,
    depurar_pedidos_transito_auto_despertar,
    gerar_excel_banco_dados,
    gerar_pacote_backup_leve,
    gerar_excel_relatorio,
    processar_planilha_estoque,
    processar_planilha_custos,
    processar_planilha_base_vendas,
    processar_planilha_movimento_diario,
    construir_mapa_departamentos,
    identificar_departamento_sku,
    identificar_produto_mp,
    avaliar_alerta_backup_semanal,
    montar_dataframe_meta_completo,
)
from database import (
    _normalizar_username,
    obter_credencial_admin_mestre,
    gravar_tabela_sql,
    salvar_backup_automatico_sql,
    remover_datas_tabela_sql,
    restaurar_backup_automatico_sql,
    _calcular_hash_dataframe_dia,
    _verificar_sobreposicao_soma_mesmo_dia,
    gravar_historico_incremental_sql,
    gravar_tabela_incremental_por_data_sql,
    migrar_arquivo_banco_para_supabase,
    listar_usuarios_sql,
    salvar_usuario_sql,
    atualizar_status_ou_remover_usuarios_sql,
    carregar_estado_completo,
)
from analytics import (
    atualizar_custos_via_entradas_df,
    auditar_descontos_saidas_df,
    auditar_ajustes_c1_t1_df,
    calcular_motor_giro_sazonal,
)


def _obter_chave_uploader(nome_base: str) -> str:
    """Gera chave dinâmica versionada na sessão para limpar a caixa somente após sucesso total."""
    versao = int(st.session_state.get(f"_ver_uploader_{nome_base}", 0))
    return f"{nome_base}_v{versao}"


def _limpar_uploaders(*nomes_base: str) -> None:
    """Renova a chave dinâmica das caixas informadas para zerar os arquivos no próximo rerun."""
    for nome_b in nomes_base:
        chave_ver = f"_ver_uploader_{nome_b}"
        st.session_state[chave_ver] = int(st.session_state.get(chave_ver, 0)) + 1


def _normalizar_lista_uploaders(arquivos) -> list:
    """Normaliza retorno de st.file_uploader (None, arquivo único ou lista) em lista limpa."""
    if arquivos is None:
        return []
    if isinstance(arquivos, list):
        return [a for a in arquivos if a is not None]
    return [arquivos]


def _formatar_data_iso_br(data_iso: str) -> str:
    """Converte YYYY-MM-DD (ou timestamp) para DD/MM/AAAA de forma segura."""
    txt = str(data_iso or "").strip()
    if not txt:
        return ""
    dt_p = pd.to_datetime(txt[:10], format="%Y-%m-%d", errors="coerce")
    return dt_p.strftime("%d/%m/%Y") if pd.notna(dt_p) else txt


def render_tab_importacao(ctx: dict) -> None:
    """Renderiza a Aba 6 — Importação & Backup."""
    db_supabase = ctx["db_supabase"]
    eh_usuario_admin = ctx["eh_usuario_admin"]
    nome_atual_logado = ctx["nome_atual_logado"]
    estado = ctx["estado"]
    df_estoque = ctx["df_estoque"]
    df_estoque_bruto = ctx["df_estoque_bruto"]
    df_historico_bruto = ctx["df_historico_bruto"]
    df_entradas_bruto = ctx["df_entradas_bruto"]
    df_saidas_bruto = ctx["df_saidas_bruto"]
    df_custos = ctx["df_custos"]
    df_base_vendas = ctx["df_base_vendas"]
    df_ocultos = ctx["df_ocultos"]
    df_pedidos_transito = ctx["df_pedidos_transito"]
    dias_base_atual = ctx["dias_base_atual"]
    ultima_data_custos_t1 = ctx["ultima_data_custos_t1"]
    ultimo_backup_semanal = ctx["ultimo_backup_semanal"]
    ultimas_att_caixas = ctx["ultimas_att_caixas"]
    grupos_pref_custom = ctx["grupos_pref_custom"]
    grupos_sku_custom = ctx["grupos_sku_custom"]
    mp_custom_map = ctx["mp_custom_map"]
    hashes_soma_meta = ctx["hashes_soma_meta"]
    codigos_ocultos = ctx["codigos_ocultos"]
    _on_download_backup_confirmado = ctx["on_download_backup_confirmado"]

    st.markdown("### Central de Importação Segura e Sincronização 100% Supabase (PostgreSQL)")
    st.caption(
        "Banco de dados PostgreSQL de alta velocidade: importação por data de Estoque, Entradas (NF) e Saídas diárias, "
        "histórico compacto (1 linha por SKU > 0), travas independentes de segurança e backup instantâneo."
    )
    if not eh_usuario_admin:
        st.warning(
            f"🔒 **Acesso Somente Leitura ({nome_atual_logado}):** Apenas o usuário **Administrador** tem permissão para "
            "subir planilhas, restaurar backups ou alterar configurações do banco. Você pode consultar normalmente todas as abas de análise (Abas 1 a 5)."
        )
    else:
        with st.expander(
            "📤 Migrar / Restaurar Banco Completo (.xlsx ou .zip) para o Supabase (1 Clique)",
            expanded=df_estoque_bruto.empty,
        ):
            st.caption(
                "Suba aqui o seu arquivo **`Banco_Dados_Esteio_Rural.xlsx`** (ou o pacote `.zip` com o histórico) para importar "
                "todas as tabelas (`estoque_atual`, `historico`, `entradas_diarias`, `saidas_diarias`, `custos`, `base_inicial`, "
                "`ocultos`, `pedidos_transito` e `meta`) diretamente para o Supabase em poucos segundos."
            )
            cmig1, cmig2 = st.columns([2.2, 1.0])
            with cmig1:
                arq_migracao_banco = st.file_uploader(
                    "Selecionar arquivo de backup completo (.xlsx ou .zip):",
                    type=["xlsx", "zip"],
                    key=_obter_chave_uploader("up_migracao_completa_supabase"),
                )
            with cmig2:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                btn_executar_migracao = st.button(
                    "🚀 Importar Tudo para o Supabase",
                    type="primary",
                    use_container_width=True,
                    disabled=(arq_migracao_banco is None),
                    key="btn_exec_mig_supabase",
                )
            if btn_executar_migracao and arq_migracao_banco is not None:
                with st.spinner("Migrando todas as abas para o Supabase PostgreSQL..."):
                    try:
                        resumo_mig = migrar_arquivo_banco_para_supabase(db_supabase, arq_migracao_banco)
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        _limpar_uploaders("up_migracao_completa_supabase")
                        carregar_estado_completo.clear()
                        calcular_motor_giro_sazonal.clear()
                        detalhes_mig = ", ".join(
                            f"`{k}` ({formatar_num_br(v)})" for k, v in resumo_mig.items()
                        )
                        st.session_state["msg_sucesso_sync"] = (
                            f"✅ Banco de dados migrado com sucesso para o Supabase PostgreSQL! Tabelas importadas: {detalhes_mig}."
                        )
                        st.session_state["toast_sucesso_sync"] = "Backup completo restaurado no Supabase com sucesso!"
                        st.rerun()
                    except Exception as erro_mig:
                        st.error(f"❌ Erro ao migrar banco para o Supabase (arquivo mantido para revisão): {erro_mig}")
        if "toast_sucesso_sync" in st.session_state:
            st.toast(st.session_state.pop("toast_sucesso_sync"), icon="✅")
        if "msg_sucesso_sync" in st.session_state:
            st.success(st.session_state.pop("msg_sucesso_sync"))
        if "aviso_duplicatas_sync" in st.session_state:
            aviso_dup = st.session_state.pop("aviso_duplicatas_sync")
            if aviso_dup["tipo"] == "warning":
                st.warning(aviso_dup["texto"])
            else:
                st.info(aviso_dup["texto"])
        if st.session_state.get("auditoria_ajustes_c1_t1"):
            regs_aj_c1 = st.session_state["auditoria_ajustes_c1_t1"]
            dt_aj_c1_str = st.session_state.get("data_auditoria_ajustes_c1_t1", "")
            res_aj_c1 = st.session_state.get("resumo_auditoria_ajustes_c1_t1", {})
            df_aj_c1 = pd.DataFrame(regs_aj_c1)
            q_esq_f = int(res_aj_c1.get("qtd_esquecimento_fiscal", 0))
            q_def_t1 = int(res_aj_c1.get("qtd_defasagem_t1", 0))
            q_red_nf = int(res_aj_c1.get("qtd_reducao_nf", 0))
            q_bonif_m = int(res_aj_c1.get("qtd_bonificacao_mantida", 0))
            q_c1_alt = int(res_aj_c1.get("qtd_c1_alterado", 0))
            q_t1_alt = int(res_aj_c1.get("qtd_t1_alterado", 0))
            q_novos_c = int(res_aj_c1.get("qtd_novos", 0))
            with st.expander(
                f"📊 Conferência de Ajustes (C1 & T1) ({dt_aj_c1_str}) — "
                f"{formatar_num_br(len(df_aj_c1))} Ajuste(s) | 🚨 NF Acima do C1 (Fiscal): {formatar_num_br(q_esq_f)} | "
                f"⚠️ Defasagem T1: {formatar_num_br(q_def_t1)} | 🎁 Bonificação: {formatar_num_br(q_bonif_m)}",
                expanded=True,
            ):
                st.caption(
                    "Comparativo automático entre a carga atual de **C1 & T1**, os valores anteriores do banco e as **NFs de Entrada** "
                    "(separando suspeita de esquecimento fiscal acima da tolerância de frete/imposto de bonificações e reduções)."
                )
                fc1, fc2 = st.columns([2.1, 1.0])
                with fc1:
                    filtro_aj_c1 = st.selectbox(
                        "Filtrar movimentações de C1 & T1:",
                        options=[
                            f"📋 Todos os Ajustes & Eventos ({len(df_aj_c1)})",
                            f"🚨 NF Acima do C1 — Conferir Fiscal ({q_esq_f})",
                            f"⚠️ Defasagem: C1 Subiu s/ Reajuste no T1 ({q_def_t1})",
                            f"📉 Custo NF Menor que C1 ({q_red_nf})",
                            f"🎁 Bonificação / Desconto Promocional NF ({q_bonif_m})",
                            f"💰 Apenas Custo C1 Alterado ({q_c1_alt})",
                            f"🏷️ Apenas Tabela T1 Alterada ({q_t1_alt})",
                            f"🆕 Novos Produtos Cadastrados ({q_novos_c})",
                        ],
                        index=0,
                        key="sel_filtro_aud_c1_t1_aba6",
                    )
                df_aj_view = df_aj_c1.copy()
                if filtro_aj_c1.startswith("🚨 NF Acima"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Status Auditoria C1 & T1"].str.contains("NF Acima do C1", na=False)
                    ].copy()
                elif filtro_aj_c1.startswith("⚠️ Defasagem"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Status Auditoria C1 & T1"].str.contains("s/ Reajuste no T1", na=False)
                    ].copy()
                elif filtro_aj_c1.startswith("📉 Custo NF"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Status Auditoria C1 & T1"].str.contains("Custo NF Menor que C1", na=False)
                    ].copy()
                elif filtro_aj_c1.startswith("🎁 Bonificação"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Status Auditoria C1 & T1"].str.contains("Bonificação", na=False)
                    ].copy()
                elif filtro_aj_c1.startswith("💰 Apenas Custo C1"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Var. C1 (%)"].abs() > 0.01
                    ].copy()
                elif filtro_aj_c1.startswith("🏷️ Apenas Tabela T1"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Var. T1 (%)"].abs() > 0.01
                    ].copy()
                elif filtro_aj_c1.startswith("🆕 Novos"):
                    df_aj_view = df_aj_view[
                        df_aj_view["Status Auditoria C1 & T1"].str.contains("Novo Produto", na=False)
                    ].copy()
                with fc2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.download_button(
                        label="📥 Baixar Ajustes C1 & T1 (.xlsx)",
                        data=gerar_excel_relatorio(df_aj_view, "Ajustes_C1_T1"),
                        file_name=f"Conferencia_Ajustes_C1_T1_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_aud_ajustes_c1_t1_aba6",
                    )
                st.dataframe(
                    estilizar_tabela_br(
                        df_aj_view,
                        formatadores={
                            "C1 Anterior (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "C1 Novo (R$)": formatar_moeda_br,
                            "Var. C1 (%)": lambda x: "0,0%" if (pd.isna(x) or abs(float(x)) <= 0.01) else formatar_pct_br(x, 1, com_sinal=True),
                            "Custo NF (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "T1 Anterior (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "T1 Novo (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Var. T1 (%)": lambda x: "0,0%" if (pd.isna(x) or abs(float(x)) <= 0.01) else formatar_pct_br(x, 1, com_sinal=True),
                            "Nova Margem T1 (%)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_pct_br(x, 1),
                        },
                        colunas_esquerda=["Descrição", "Status Auditoria C1 & T1"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=280,
                )
        if st.session_state.get("auditoria_descontos_ultima_saida"):
            regs_desc_sai = st.session_state["auditoria_descontos_ultima_saida"]
            dt_aud_sai_str = st.session_state.get("data_auditoria_descontos_sai", "")
            df_aud_desc_sai = pd.DataFrame(regs_desc_sai)
            tot_desc_rs_nf = float(df_aud_desc_sai["Desconto Total (R$)"].sum()) if not df_aud_desc_sai.empty else 0.0
            with st.expander(
                f"🏷️ Conferência de Descontos > 5% nas Saídas ({dt_aud_sai_str}) — "
                f"{formatar_num_br(len(df_aud_desc_sai))} Item(ns) | Total Concedido: {formatar_moeda_br(tot_desc_rs_nf)}",
                expanded=True,
            ):
                st.caption(
                    "Comparação entre o **Preço Tabela Oficial (T1)** e o **Preço Vendido no Balcão** (sem sobrescrever nenhum dos dois). "
                    "O padrão normal do sistema é até 2,1%; abaixo estão os itens vendidos com desconto superior a **5,0%** "
                    "(o histórico permanente também fica sempre disponível na **Aba 5 — Seção 5** e na **Aba 6 — Seção 5**)."
                )
                st.download_button(
                    label="📥 Baixar Conferência de Descontos > 5% (.xlsx)",
                    data=gerar_excel_relatorio(df_aud_desc_sai, "Descontos_Saida_5pct"),
                    file_name=f"Conferencia_Descontos_Saida_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_conf_desc_sai_aba7",
                )
                st.dataframe(
                    estilizar_tabela_br(
                        df_aud_desc_sai,
                        formatadores={
                            "Qtd. Vendida": formatar_qtd_br,
                            "Preço Tabela T1 (R$)": formatar_moeda_br,
                            "Preço Vendido Balcão (R$)": formatar_moeda_br,
                            "Desconto (%)": lambda x: f"-{formatar_pct_br(x, 1)}",
                            "Desconto Total (R$)": formatar_moeda_br,
                            "Custo C1 (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Margem Real (%)": lambda x: formatar_pct_br(x, 1),
                        },
                        colunas_esquerda=["Descrição", "Status Desconto"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=260,
                )
        if st.session_state.get("auditoria_custos_ultima_nf"):
            regs_aud_nf = st.session_state["auditoria_custos_ultima_nf"]
            dt_aud_nf_str = st.session_state.get("data_auditoria_custos_nf", "")
            df_aud_nf = pd.DataFrame(regs_aud_nf)
            qtd_inalt_tab = int(df_aud_nf["Status Auditoria Fiscal"].str.contains("Inalterado", na=False).sum())
            qtd_var_tab = int(df_aud_nf["Status Auditoria Fiscal"].str.contains("Variação Brusca", na=False).sum())
            with st.expander(
                f"🔎 Conferência Fiscal de Custos da Última NF ({dt_aud_nf_str}) — "
                f"{formatar_num_br(qtd_inalt_tab)} Inalterado(s) 0,0% | {formatar_num_br(qtd_var_tab)} Variação >20%",
                expanded=(qtd_inalt_tab > 0 or qtd_var_tab > 0),
            ):
                st.caption(
                    "Use esta conferência para identificar produtos que entraram na NF com **custo idêntico ao anterior (0,0%)** "
                    "(indicando possível esquecimento na atualização de preço de custo pelo setor fiscal) ou com variação acima de 20%."
                )
                fa1, fa2 = st.columns([2.0, 1.0])
                with fa1:
                    filtro_aud_fiscal = st.selectbox(
                        "Filtrar itens da NF:",
                        options=[
                            f"🔎 Todos os Alertas (Inalterados 0,0%: {qtd_inalt_tab} + Variação >20%: {qtd_var_tab})",
                            f"🔎 Apenas Custo Inalterado 0,0% ({qtd_inalt_tab})",
                            f"⚠️ Apenas Variação Brusca >20% ({qtd_var_tab})",
                            f"📋 Todos os Itens da NF ({len(df_aud_nf)})",
                        ],
                        index=0 if (qtd_inalt_tab > 0 or qtd_var_tab > 0) else 3,
                        key="sel_filtro_aud_fiscal_nf",
                    )
                df_aud_view = df_aud_nf.copy()
                if filtro_aud_fiscal.startswith("🔎 Todos os Alertas"):
                    df_aud_view = df_aud_view[
                        df_aud_view["Status Auditoria Fiscal"].str.contains("Inalterado|Variação Brusca", na=False)
                    ].copy()
                elif filtro_aud_fiscal.startswith("🔎 Apenas Custo Inalterado"):
                    df_aud_view = df_aud_view[
                        df_aud_view["Status Auditoria Fiscal"].str.contains("Inalterado", na=False)
                    ].copy()
                elif filtro_aud_fiscal.startswith("⚠️ Apenas Variação"):
                    df_aud_view = df_aud_view[
                        df_aud_view["Status Auditoria Fiscal"].str.contains("Variação Brusca", na=False)
                    ].copy()
                with fa2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.download_button(
                        label="📥 Baixar Conferência Fiscal (.xlsx)",
                        data=gerar_excel_relatorio(df_aud_view, "Auditoria_Fiscal_Custos"),
                        file_name=f"Auditoria_Fiscal_Custos_NF_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_auditoria_fiscal_nf_aba7",
                    )
                st.dataframe(
                    estilizar_tabela_br(
                        df_aud_view,
                        formatadores={
                            "Custo Anterior (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Custo na NF (R$)": formatar_moeda_br,
                            "Variação (%)": lambda x: "0,0%" if (pd.isna(x) or abs(float(x)) < 0.05) else formatar_pct_br(x, 1, com_sinal=True),
                        },
                        colunas_esquerda=["Descrição", "Status Auditoria Fiscal"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=260,
                )
        # Monta textos discretos de "Última atualização" por caixa a partir do banco
        ult_est_txt = ultimas_att_caixas.get("estoque", "")
        if not ult_est_txt and not df_estoque_bruto.empty and "data" in df_estoque_bruto.columns:
            dts_e = sorted([str(d).strip() for d in df_estoque_bruto["data"].unique() if str(d).strip()])
            if dts_e:
                ult_est_txt = f"Posição de {_formatar_data_iso_br(dts_e[-1])}"

        ult_ent_txt = ultimas_att_caixas.get("entradas", "")
        if not ult_ent_txt and not df_entradas_bruto.empty and "data" in df_entradas_bruto.columns:
            dts_n = sorted([str(d).strip() for d in df_entradas_bruto["data"].unique() if str(d).strip()])
            if dts_n:
                ult_ent_txt = f"Última NF em {_formatar_data_iso_br(dts_n[-1])}"

        ult_sai_txt = ultimas_att_caixas.get("saidas", "")
        if not ult_sai_txt and not df_saidas_bruto.empty and "data" in df_saidas_bruto.columns:
            dts_s = sorted([str(d).strip() for d in df_saidas_bruto["data"].unique() if str(d).strip()])
            if dts_s:
                ult_sai_txt = f"Última saída em {_formatar_data_iso_br(dts_s[-1])}"

        ult_cus_txt = ultimas_att_caixas.get("custos", "")
        if not ult_cus_txt and ultima_data_custos_t1:
            ult_cus_txt = f"Tabela de {_formatar_data_iso_br(ultima_data_custos_t1)}"

        ult_base_txt = ultimas_att_caixas.get("base", "")
        if not ult_base_txt and not df_base_vendas.empty:
            ult_base_txt = f"{formatar_num_br(len(df_base_vendas))} SKUs carregados"

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                """
                <div class="glass-card">
                    <strong>1. Posição de Estoque (6 col.)</strong><br><br>
                    <span class="pill-tag">Código</span>
                    <span class="pill-tag">Saldo Geral</span>
                    <span class="pill-tag">Descrição</span>
                    <span class="pill-tag">Lote</span>
                    <span class="pill-tag">Saldo Lote</span>
                    <span class="pill-tag">Validade</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            data_posicao = st.date_input("Data desta posição de estoque:", value=hoje_br())
            arq_estoque_raw = st.file_uploader(
                "Selecionar Estoque (.xlsx, .xls ou .csv)",
                type=["xlsx", "xls", "csv"],
                accept_multiple_files=True,
                key=_obter_chave_uploader("up_estoque"),
            )
            st.caption(
                f"🕒 Última atualização: **{ult_est_txt}**"
                if ult_est_txt
                else "🕒 Última atualização: Nenhuma importação registrada ainda."
            )
        with c2:
            st.markdown(
                """
                <div class="glass-card">
                    <strong>2. Entradas NF c/ Custo (Fatu416)</strong><br><br>
                    <span class="pill-tag">Código</span>
                    <span class="pill-tag">Descrição</span>
                    <span class="pill-tag">Quantidade</span>
                    <span class="pill-tag">Valor (Custo NF)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            data_entrada = st.date_input(
                "Data das Entradas (NF):",
                value=hoje_br() - timedelta(days=1),
                key="dt_entrada_aba1",
            )
            arq_entradas_raw = st.file_uploader(
                "Selecionar Entradas (.xlsx, .xls ou .csv)",
                type=["xlsx", "xls", "csv"],
                accept_multiple_files=True,
                key=_obter_chave_uploader("up_entradas"),
            )
            st.caption(
                f"🕒 Última atualização: **{ult_ent_txt}**"
                if ult_ent_txt
                else "🕒 Última atualização: Nenhuma importação registrada ainda."
            )
            somar_entradas_mesmo_dia = st.checkbox(
                "➕ Somar ao dia se já houver entrada nesta data",
                value=False,
                key="chk_somar_ent_dia",
                help="Desmarcado (padrão): substitui as entradas desta data. Marcado: soma o novo arquivo às entradas já salvas nesta mesma data.",
            )
            atualizar_custo_pela_entrada = st.checkbox(
                "💰 Atualizar custo unitário pelos itens desta NF",
                value=True,
                key="chk_att_custo_ent_nf",
                help="Marcado (padrão): atualiza o custo unitário apenas para os produtos desta NF cuja data seja igual ou posterior à última entrada registrada. Desmarque em notas de bonificação quando quiser apenas auditar.",
            )
        with c3:
            st.markdown(
                """
                <div class="glass-card">
                    <strong>3. Saídas / Vendas (3 ou 4 col.)</strong><br><br>
                    <span class="pill-tag">Código</span>
                    <span class="pill-tag">Descrição</span>
                    <span class="pill-tag">Qtd.</span>
                    <span class="pill-tag">Valor Proposta</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            data_saida = st.date_input(
                "Data das Saídas / Vendas:",
                value=hoje_br() - timedelta(days=1),
                key="dt_saida_aba1",
            )
            arq_saidas_raw = st.file_uploader(
                "Selecionar Saídas (.xlsx, .xls ou .csv)",
                type=["xlsx", "xls", "csv"],
                accept_multiple_files=True,
                key=_obter_chave_uploader("up_saidas"),
            )
            st.caption(
                f"🕒 Última atualização: **{ult_sai_txt}**"
                if ult_sai_txt
                else "🕒 Última atualização: Nenhuma importação registrada ainda."
            )
            somar_saidas_mesmo_dia = st.checkbox(
                "➕ Somar ao dia se já houver saída nesta data",
                value=False,
                key="chk_somar_sai_dia",
                help="Desmarcado (padrão): substitui as saídas desta data. Marcado: soma o novo arquivo às saídas já salvas nesta mesma data.",
            )
        with c4:
            st.markdown(
                """
                <div class="glass-card">
                    <strong>4. Custos C1 & Tabela T1 (4 col.)</strong><br><br>
                    <span class="pill-tag">Código</span>
                    <span class="pill-tag">Descrição</span>
                    <span class="pill-tag">T1 (Tabela)</span>
                    <span class="pill-tag">C1 (Custo)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            data_custos = st.date_input(
                "Data Custos / Preços (C1/T1):",
                value=hoje_br(),
                key="dt_custos_aba1",
            )
            arq_custos_raw = st.file_uploader(
                "Selecionar Custo Preço (.xlsx, .xls ou .csv)",
                type=["xlsx", "xls", "csv"],
                accept_multiple_files=True,
                key=_obter_chave_uploader("up_custos"),
            )
            if ult_cus_txt:
                st.caption(f"🕒 Última atualização: **{ult_cus_txt}** | C1 sobrescreve NF.")
            else:
                st.caption(
                    "🕒 Última atualização: Nenhuma carga C1/T1 registrada ainda."
                )
        with st.expander("📦 Base Inicial Histórica de Vendas (Apoio Opcional)", expanded=False):
            cb1, cb2 = st.columns([0.8, 1.8])
            with cb1:
                dias_base_input = st.number_input(
                    "Período da base inicial (dias):",
                    min_value=1,
                    max_value=730,
                    value=int(dias_base_atual),
                    step=1,
                )
            with cb2:
                arq_base_raw = st.file_uploader(
                    "Base Inicial de Vendas (Código, Descrição, Qtd. Vendida):",
                    type=["xlsx", "xls", "csv"],
                    accept_multiple_files=True,
                    key=_obter_chave_uploader("up_base"),
                )
                st.caption(
                    f"🕒 Última atualização: **{ult_base_txt}**"
                    if ult_base_txt
                    else "🕒 Última atualização: Nenhuma base inicial importada ainda."
                )
        with st.expander("⚙️ Opções Avançadas de Auditoria Fiscal & Exceção de Travas", expanded=False):
            ca_f1, ca_f2, ca_f3 = st.columns([1.2, 1.2, 1.6])
            with ca_f1:
                janela_cruzamento_nf_c1_dias = st.number_input(
                    "📅 Janela Cruzamento NF × C1 (dias):",
                    min_value=1,
                    max_value=60,
                    value=3,
                    step=1,
                    key="num_janela_nf_c1_aba6",
                    help="Padrão de 3 dias: ao importar Custos C1 & T1, cruza com todas as NFs de Entrada lançadas nos últimos 3 dias para detectar esquecimentos fiscais.",
                )
            with ca_f2:
                tolerancia_frete_nf_c1_pct = st.number_input(
                    "⚖️ Tolerância Frete/Imposto NF × C1 (%):",
                    min_value=0.0,
                    max_value=10.0,
                    value=1.5,
                    step=0.5,
                    key="num_tol_frete_nf_c1_aba6",
                    help="Padrão de 1,5%: diferenças pequenas entre o valor líquido da NF (Fatu416) e o C1 do Siagri dentro desta margem não disparam alerta de esquecimento fiscal.",
                )
            with ca_f3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.caption("🛡️ A auditoria fiscal roda automaticamente mesmo se 'Atualizar custo pela NF' estiver desmarcado.")
            st.markdown("---")
            ct1, ct2, ct3, ct4 = st.columns(4)
            with ct1:
                ignorar_trava_catalogo = st.checkbox(
                    "🔓 Ignorar trava de 80% de códigos",
                    value=False,
                    key="chk_ign_trava_cat",
                    help="Marque apenas se estiver trocando de ERP ou importando uma linha de produtos totalmente nova.",
                )
            with ct2:
                ignorar_trava_data = st.checkbox(
                    "📅 Ignorar trava de data no nome",
                    value=False,
                    key="chk_ign_trava_dt",
                    help="Marque apenas se quiser forçar a gravação de um arquivo cuja data no nome seja diferente da data escolhida no seletor.",
                )
            with ct3:
                forcar_estoque_retroativo = st.checkbox(
                    "⏪ Forçar Estoque retroativo como Atual",
                    value=False,
                    key="chk_forcar_est_retro",
                    help="Por padrão, estoques de datas anteriores vão apenas para o Histórico. Marque apenas se quiser que um estoque antigo substitua o estoque_atual.",
                )
            with ct4:
                permitir_somar_codigos_repetidos_dia = st.checkbox(
                    "➕ Autorizar somar códigos já lançados no dia",
                    value=False,
                    key="chk_perm_somar_rep_dia",
                    help="Por padrão, se você marcar 'Somar ao dia' e enviar um arquivo em que >= 50% dos códigos já estão lançados naquela data, o sistema bloqueia para evitar somar um relatório reexportado. Marque apenas se forem duas notas diferentes dos mesmos produtos no mesmo dia.",
                )
        btn_sincronizar = st.button(
            "🚀 Processar e Sincronizar com Segurança",
            type="primary",
            use_container_width=True,
        )
        st.markdown("---")
        st.markdown("#### 💾 Salvar Cópia do Banco de Dados no Computador & Restauração Rápida")
        _, dias_bkp_aba6, dt_bkp_aba6_br = avaliar_alerta_backup_semanal(ultimo_backup_semanal)
        info_ult_bkp_txt = (
            f"📅 **Último backup baixado no computador:** **{dt_bkp_aba6_br}** (há {formatar_num_br(dias_bkp_aba6)} dia(s) — lembrete automático a cada 7 dias)."
            if dt_bkp_aba6_br
            else "📅 **Último backup baixado no computador:** Nenhum download registrado ainda (lembrete automático a cada 7 dias)."
        )
        st.caption(
            f"{info_ult_bkp_txt} Baixe uma planilha Excel (`.xlsx`) ou o pacote completo (`.zip`) com o histórico de 2 anos."
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
                        on_click=_on_download_backup_confirmado,
                    )
        with col_bkp_zip:
            if not df_estoque_bruto.empty:
                if st.button("📦 Preparar Banco + Histórico 2 Anos (.zip)", use_container_width=True):
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
                        on_click=_on_download_backup_confirmado,
                    )
        with st.expander("⏪ Desfazer Última Importação ou Excluir Data de Movimento (Backups Automáticos Leves)", expanded=False):
            st.caption(
                "Restaure a cópia automática imediatamente anterior (`_bkp_*`) das abas leves (Estoque Atual, Entradas, Saídas, Custos, "
                "Base Inicial, Ocultos ou Pedidos em Trânsito) ou remova os lançamentos de uma data específica no Histórico, Entradas ou Saídas."
            )
            cr1, cr2 = st.columns([2, 1])
            mapa_opcoes_restaurar = {
                "Posição de Estoque (estoque_atual + ajuste no histórico)": ("estoque_atual", df_estoque_bruto),
                "Entradas Diárias (entradas_diarias)": ("entradas_diarias", df_entradas_bruto),
                "Saídas Diárias (saidas_diarias)": ("saidas_diarias", df_saidas_bruto),
                "Planilha de Custos (custos)": ("custos", df_custos),
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
                        qtd_rest = restaurar_backup_automatico_sql(
                            db_supabase,
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
                        st.session_state["toast_sucesso_sync"] = f"Base {aba_alvo_rest} restaurada!"
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
                        qtd_apagadas = remover_datas_tabela_sql(
                            db_supabase,
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
                        st.session_state["toast_sucesso_sync"] = f"Data {data_del_escolhida} excluída!"
                        st.rerun()
                    except Exception as erro_del_dt:
                        st.error(f"❌ Erro ao excluir data: {erro_del_dt}")
        if btn_sincronizar:
            arqs_estoque = _normalizar_lista_uploaders(arq_estoque_raw)
            arqs_entradas = _normalizar_lista_uploaders(arq_entradas_raw)
            arqs_saidas = _normalizar_lista_uploaders(arq_saidas_raw)
            arqs_custos = _normalizar_lista_uploaders(arq_custos_raw)
            arqs_base = _normalizar_lista_uploaders(arq_base_raw)

            if (
                not any([arqs_estoque, arqs_entradas, arqs_saidas, arqs_custos, arqs_base])
                and int(dias_base_input) == int(dias_base_atual)
            ):
                st.warning("⚠️ Selecione pelo menos uma planilha para importar ou altere o período da base.")
            else:
                abas_ja_gravadas = []
                caixas_para_limpar = []
                resumo_toast_partes = []
                hashes_snapshot = {
                    k_snap: list(v_snap)
                    for k_snap, v_snap in st.session_state.get("hashes_soma_por_data", {}).items()
                }
                with st.spinner("Validando todos os arquivos do lote (regra Tudo ou Nada) antes de gravar no Supabase..."):
                    try:
                        if arqs_estoque and not ignorar_trava_data:
                            if arqs_entradas and data_entrada >= data_posicao:
                                raise ValueError(
                                    f"Trava de Coerência Temporal: A data das **Entradas ({data_entrada.strftime('%d/%m/%Y')})** "
                                    f"não pode ser igual ou posterior à **Posição de Estoque Inicial ({data_posicao.strftime('%d/%m/%Y')})** "
                                    f"enviada no mesmo lote. Se as entradas são do dia anterior, selecione **{(data_posicao - timedelta(days=1)).strftime('%d/%m/%Y')}**."
                                )
                            if arqs_saidas and data_saida >= data_posicao:
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

                        # ------------------------------------------------------
                        # CAIXA 1: ESTOQUE (Validação Tudo ou Nada para 1..N arquivos)
                        # ------------------------------------------------------
                        if arqs_estoque:
                            frames_est_lote = []
                            tot_lidas_est = 0
                            tot_dup_est = 0
                            exemplos_dup_est = []
                            avisos_sem_dt_est = []
                            for idx_e, arq_e_item in enumerate(arqs_estoque, 1):
                                try:
                                    df_e_i, info_e_i = processar_planilha_estoque(
                                        arq_e_item,
                                        data_posicao,
                                        codigos_ref=codigos_ref_estoque,
                                        ignorar_trava_catalogo=ignorar_trava_catalogo,
                                        ignorar_trava_data=ignorar_trava_data,
                                    )
                                except Exception as erro_item_e:
                                    prefixo_lote = (
                                        f"[Caixa Estoque — Arquivo {idx_e}/{len(arqs_estoque)}: '{arq_e_item.name}'] "
                                        if len(arqs_estoque) > 1
                                        else f"[Caixa Estoque: '{arq_e_item.name}'] "
                                    )
                                    raise ValueError(
                                        f"{prefixo_lote}{erro_item_e} (Nenhum arquivo do lote foi gravado — corrija e tente novamente)."
                                    ) from erro_item_e
                                frames_est_lote.append(df_e_i)
                                tot_lidas_est += int(info_e_i["linhas_lidas"])
                                tot_dup_est += int(info_e_i["qtd_duplicadas"])
                                exemplos_dup_est.extend(info_e_i.get("exemplos", []))
                                if info_e_i.get("aviso_sem_data"):
                                    avisos_sem_dt_est.append(info_e_i["aviso_sem_data"])

                            novo_estoque = pd.concat(frames_est_lote, ignore_index=True)
                            if len(arqs_estoque) > 1:
                                dup_inter_est = int(novo_estoque.duplicated(subset=["codigo", "lote"], keep="last").sum())
                                tot_dup_est += dup_inter_est
                                novo_estoque = (
                                    novo_estoque.drop_duplicates(subset=["codigo", "lote"], keep="last")
                                    .reset_index(drop=True)
                                )
                            taxa_coinc_est = (
                                (len(set(novo_estoque["codigo"].unique()) & codigos_ref_estoque) / max(len(novo_estoque["codigo"].unique()), 1)) * 100.0
                                if codigos_ref_estoque
                                else 100.0
                            )
                            codigos_ref_geral = codigos_ref_geral | set(novo_estoque["codigo"].unique())
                            datas_est_existentes = (
                                sorted([str(d).strip() for d in df_estoque_bruto["data"].unique() if str(d).strip()])
                                if (not df_estoque_bruto.empty and "data" in df_estoque_bruto.columns)
                                else []
                            )
                            maior_data_est_atual = datas_est_existentes[-1] if datas_est_existentes else ""
                            if maior_data_est_atual and data_str < maior_data_est_atual and not forcar_estoque_retroativo:
                                atualizar_aba_estoque_atual = False
                                teve_alerta = True
                                dt_at_fmt = pd.to_datetime(maior_data_est_atual, format="%Y-%m-%d", errors="coerce")
                                str_dt_at = dt_at_fmt.strftime("%d/%m/%Y") if pd.notna(dt_at_fmt) else maior_data_est_atual
                                mensagens_auditoria_upload.append(
                                    f"🛡️ **Proteção contra Estoque Retroativo:** O estoque enviado (**{data_posicao.strftime('%d/%m/%Y')}**) "
                                    f"é anterior à Posição Atual do sistema (**{str_dt_at}**). Ele foi gravado apenas no **Histórico** "
                                    f"para compor o giro, mantendo o `estoque_atual` intacto em **{str_dt_at}**!"
                                )
                            tag_arqs_est = f" ({len(arqs_estoque)} arqs)" if len(arqs_estoque) > 1 else ""
                            if tot_dup_est > 0:
                                teve_alerta = True
                                amostra_txt = ", ".join(exemplos_dup_est[:5])
                                mensagens_auditoria_upload.append(
                                    f"⚠️ **Estoque{tag_arqs_est}:** {formatar_num_br(tot_dup_est)} linha(s) duplicada(s) de mesmo "
                                    f"(Código + Lote) foram mescladas mantendo a última ocorrência "
                                    f"({formatar_num_br(tot_lidas_est)} lidas → {formatar_num_br(len(novo_estoque))} únicas | "
                                    f"Coincidência: {formatar_pct_br(taxa_coinc_est)}). "
                                    f"Exemplos: {amostra_txt}"
                                )
                            else:
                                mensagens_auditoria_upload.append(
                                    f"✔️ **Estoque ({data_posicao.strftime('%d/%m')}{tag_arqs_est}):** {formatar_num_br(len(novo_estoque))} linhas verificadas "
                                    f"(0 duplicatas | {formatar_pct_br(taxa_coinc_est)} de códigos coincidentes)."
                                )
                            for av_e in dict.fromkeys(avisos_sem_dt_est):
                                teve_alerta = True
                                mensagens_auditoria_upload.append(av_e)
                            caixas_para_limpar.append("up_estoque")
                            resumo_toast_partes.append(f"Estoque: {formatar_num_br(len(novo_estoque))} linhas")

                        # ------------------------------------------------------
                        # CAIXA 2: ENTRADAS NF (Validação Tudo ou Nada para 1..N arquivos)
                        # ------------------------------------------------------
                        df_custos_via_entrada = pd.DataFrame()
                        info_upsert_custo_ent = {}
                        hashes_lote_ent = []
                        ent_ja_somada_antes = False
                        somar_ent_efetivo = bool(somar_entradas_mesmo_dia)
                        if arqs_entradas:
                            dt_ent_iso = data_entrada.strftime("%Y-%m-%d")
                            chave_op_ent = f"entradas_diarias::{dt_ent_iso}"
                            hashes_ent_ja_no_dia = list(
                                st.session_state.get("hashes_soma_por_data", {}).get(
                                    chave_op_ent, hashes_soma_meta.get(chave_op_ent, [])
                                )
                            )
                            frames_ent_lote = []
                            frames_ext_c_lote = []
                            soma_val_ent_lote = 0.0
                            cols_val_ent_lote = []
                            qtd_rep_ent_lote = 0
                            qtd_extras_ent_lote = 0
                            exemplos_rep_ent_lote = []
                            avisos_sem_dt_ent = []

                            for idx_n, arq_n_item in enumerate(arqs_entradas, 1):
                                try:
                                    df_n_i, info_n_i = processar_planilha_movimento_diario(
                                        arquivo=arq_n_item,
                                        data_mov=data_entrada,
                                        nome_aba="entradas_diarias",
                                        col_qtd="qtd_entrada",
                                        rotulo_amigavel="Entradas Diárias",
                                        codigos_ref=codigos_ref_geral,
                                        ignorar_trava_catalogo=ignorar_trava_catalogo,
                                        ignorar_trava_data=ignorar_trava_data,
                                    )
                                except Exception as erro_item_n:
                                    prefixo_lote = (
                                        f"[Caixa Entradas — Arquivo {idx_n}/{len(arqs_entradas)}: '{arq_n_item.name}'] "
                                        if len(arqs_entradas) > 1
                                        else f"[Caixa Entradas: '{arq_n_item.name}'] "
                                    )
                                    raise ValueError(
                                        f"{prefixo_lote}{erro_item_n} (Nenhum arquivo do lote foi gravado — corrija e tente novamente)."
                                    ) from erro_item_n

                                h_n_i = hashlib.sha256(arq_n_item.getvalue()).hexdigest()[:16]
                                if h_n_i in hashes_lote_ent:
                                    raise ValueError(
                                        f"[Caixa Entradas — Arquivo {idx_n}/{len(arqs_entradas)}: '{arq_n_item.name}'] "
                                        f"Arquivo duplicado dentro do mesmo lote selecionado. Remova a cópia repetida e tente novamente."
                                    )
                                hashes_lote_ent.append(h_n_i)
                                frames_ent_lote.append(df_n_i)
                                soma_val_ent_lote += float(info_n_i.get("soma_valor_entrada", 0.0))
                                if info_n_i.get("coluna_valor_entrada"):
                                    cols_val_ent_lote.append(info_n_i["coluna_valor_entrada"])
                                df_c_i = info_n_i.get("df_custos_extraidos", pd.DataFrame())
                                if df_c_i is not None and not df_c_i.empty:
                                    frames_ext_c_lote.append(df_c_i)
                                qtd_rep_ent_lote += int(info_n_i.get("qtd_codigos_repetidos", 0))
                                qtd_extras_ent_lote += int(info_n_i.get("qtd_linhas_extras", 0))
                                exemplos_rep_ent_lote.extend(info_n_i.get("exemplos_repetidos", []))
                                if info_n_i.get("aviso_sem_data"):
                                    avisos_sem_dt_ent.append(info_n_i["aviso_sem_data"])

                            # Consolida todos os arquivos do lote de Entradas somando por SKU
                            novas_entradas = (
                                pd.concat(frames_ent_lote, ignore_index=True)
                                .groupby(["data", "codigo"], as_index=False)
                                .agg(
                                    descricao=("descricao", "last"),
                                    qtd_entrada=("qtd_entrada", "sum"),
                                    valor_entrada=("valor_entrada", "sum"),
                                )
                            )
                            novas_entradas = padronizar_dataframe(novas_entradas, "entradas_diarias")

                            if (
                                somar_entradas_mesmo_dia
                                and not df_entradas_bruto.empty
                                and "data" in df_entradas_bruto.columns
                            ):
                                df_ent_dia_atual = df_entradas_bruto[df_entradas_bruto["data"] == dt_ent_iso]
                                if not df_ent_dia_atual.empty:
                                    if not hashes_ent_ja_no_dia:
                                        h_ant_e = _calcular_hash_dataframe_dia(df_ent_dia_atual, "entradas_diarias")
                                        if h_ant_e:
                                            hashes_ent_ja_no_dia.append(h_ant_e)
                                        for _, r_ea in df_ent_dia_atual.iterrows():
                                            hashes_ent_ja_no_dia.append(f"sku:{r_ea['codigo']}:{float(r_ea['qtd_entrada']):.4f}")
                                    if len(arqs_entradas) == 1:
                                        ent_ja_somada_antes, _ = _verificar_sobreposicao_soma_mesmo_dia(
                                            df_existente_dia=df_ent_dia_atual,
                                            df_novo_dia=novas_entradas,
                                            col_qtd="qtd_entrada",
                                            hashes_ja_no_dia=hashes_ent_ja_no_dia,
                                            hash_efetivo=hashes_lote_ent[0],
                                            permitir_somar_codigos_repetidos_dia=permitir_somar_codigos_repetidos_dia,
                                            rotulo_aba="Entradas",
                                            data_ref_str=dt_ent_iso,
                                        )
                                    else:
                                        for idx_hn, h_sub in enumerate(hashes_lote_ent, 1):
                                            if h_sub in hashes_ent_ja_no_dia:
                                                raise ValueError(
                                                    f"[Caixa Entradas — Arquivo {idx_hn}/{len(arqs_entradas)}: '{arqs_entradas[idx_hn - 1].name}'] "
                                                    f"Este arquivo exato já havia sido somado na data {data_entrada.strftime('%d/%m/%Y')}. "
                                                    f"Nenhum arquivo do lote foi gravado."
                                                )

                            tag_arqs_ent = f" ({len(arqs_entradas)} arqs)" if len(arqs_entradas) > 1 else ""
                            modo_ent_str = (
                                f"somadas ao dia{tag_arqs_ent}"
                                if somar_entradas_mesmo_dia
                                else (f"consolidadas ({len(arqs_entradas)} arqs)" if len(arqs_entradas) > 1 else "gravadas")
                            )
                            col_val_ent_nome = cols_val_ent_lote[0] if cols_val_ent_lote else ""
                            df_ext_c = pd.DataFrame()
                            if soma_val_ent_lote > 0:
                                df_pos_c = novas_entradas[
                                    (novas_entradas["qtd_entrada"] > 0) & (novas_entradas["valor_entrada"] > 0)
                                ][["codigo", "descricao", "qtd_entrada", "valor_entrada"]].copy()
                                if not df_pos_c.empty:
                                    df_pos_c["custo_unitario"] = (df_pos_c["valor_entrada"] / df_pos_c["qtd_entrada"]).round(4)
                                    df_ext_c = df_pos_c[["codigo", "descricao", "custo_unitario"]].copy()
                            elif frames_ext_c_lote:
                                df_ext_c = pd.concat(frames_ext_c_lote, ignore_index=True).drop_duplicates(subset=["codigo"], keep="last")

                            if (
                                somar_entradas_mesmo_dia
                                and (not ent_ja_somada_antes)
                                and not df_ext_c.empty
                                and not df_entradas_bruto.empty
                                and "data" in df_entradas_bruto.columns
                                and "valor_entrada" in df_entradas_bruto.columns
                            ):
                                df_dia_ant = df_entradas_bruto[
                                    (df_entradas_bruto["data"] == dt_ent_iso)
                                    & (df_entradas_bruto["qtd_entrada"] > 0)
                                    & (df_entradas_bruto["valor_entrada"] > 0)
                                ].copy()
                                if not df_dia_ant.empty:
                                    df_soma_c = pd.concat(
                                        [
                                            df_dia_ant[["codigo", "descricao", "qtd_entrada", "valor_entrada"]],
                                            novas_entradas[
                                                (novas_entradas["qtd_entrada"] > 0) & (novas_entradas["valor_entrada"] > 0)
                                            ][["codigo", "descricao", "qtd_entrada", "valor_entrada"]],
                                        ],
                                        ignore_index=True,
                                    ).groupby("codigo", as_index=False).agg(
                                        descricao=("descricao", "last"),
                                        qtd_entrada=("qtd_entrada", "sum"),
                                        valor_entrada=("valor_entrada", "sum"),
                                    )
                                    df_soma_c["custo_unitario"] = (df_soma_c["valor_entrada"] / df_soma_c["qtd_entrada"]).round(4)
                                    df_ext_c = df_soma_c[["codigo", "descricao", "custo_unitario"]].copy()

                            if ent_ja_somada_antes:
                                teve_alerta = True
                                mensagens_auditoria_upload.append(
                                    f"🛡️ **Proteção contra Soma Duplicada (Entradas {data_entrada.strftime('%d/%m')}):** "
                                    f"Este arquivo exato (`{arqs_entradas[0].name}`) já havia sido somado nesta data e foi ignorado para não dobrar as quantidades!"
                                )
                            else:
                                if soma_val_ent_lote > 0 and not df_ext_c.empty:
                                    rot_col_e = f" (coluna '{col_val_ent_nome}')" if col_val_ent_nome else ""
                                    df_custos_sim_ent, info_upsert_custo_ent = atualizar_custos_via_entradas_df(
                                        df_custos_atual=df_custos,
                                        df_custos_novos_entrada=df_ext_c,
                                        data_entrada_iso=dt_ent_iso,
                                        df_entradas_historico=df_entradas_bruto,
                                        limite_alerta_variacao_pct=20.0,
                                        tolerancia_frete_pct=float(tolerancia_frete_nf_c1_pct),
                                    )
                                    if atualizar_custo_pela_entrada:
                                        df_custos_via_entrada = df_custos_sim_ent
                                        tot_c_aplicados = info_upsert_custo_ent["qtd_atualizados"] + info_upsert_custo_ent["qtd_inseridos"]
                                        str_val_ent = (
                                            f" | Valor Total NF{rot_col_e}: {formatar_moeda_br(soma_val_ent_lote)} "
                                            f"➔ 💰 **{formatar_num_br(tot_c_aplicados)} custo(s) unitário(s) atualizado(s)**"
                                        )
                                    else:
                                        str_val_ent = (
                                            f" | Valor Total NF{rot_col_e}: {formatar_moeda_br(soma_val_ent_lote)} "
                                            f"(Custos C1 mantidos s/ alteração — 🔎 auditoria fiscal gerada)"
                                        )
                                else:
                                    str_val_ent = ""
                                mensagens_auditoria_upload.append(
                                    f"✔️ **Entradas ({data_entrada.strftime('%d/%m')}):** {formatar_num_br(len(novas_entradas))} SKUs {modo_ent_str} "
                                    f"(Soma: {formatar_qtd_br(float(novas_entradas['qtd_entrada'].sum()))} un.{str_val_ent})."
                                )
                            if info_upsert_custo_ent.get("qtd_ignorados_data_antiga", 0) > 0:
                                teve_alerta = True
                                ex_ign_dt = ", ".join(info_upsert_custo_ent["exemplos_ignorados_data"])
                                mensagens_auditoria_upload.append(
                                    f"🛡️ **Proteção contra Custo Retroativo:** {formatar_num_br(info_upsert_custo_ent['qtd_ignorados_data_antiga'])} produto(s) "
                                    f"não tiveram o custo sobrescrito porque esta NF ({data_entrada.strftime('%d/%m/%Y')}) é mais antiga que a última entrada: {ex_ign_dt}."
                                )
                            if info_upsert_custo_ent.get("registros_auditoria"):
                                st.session_state["auditoria_custos_ultima_nf"] = info_upsert_custo_ent["registros_auditoria"]
                                st.session_state["data_auditoria_custos_nf"] = data_entrada.strftime("%d/%m/%Y")
                            if info_upsert_custo_ent.get("qtd_inalterados", 0) > 0:
                                teve_alerta = True
                                ex_inalt_c = ", ".join(info_upsert_custo_ent["exemplos_inalterados"])
                                mensagens_auditoria_upload.append(
                                    f"🔎 **Auditoria Fiscal — Custo Inalterado na NF (0,0%):** {formatar_num_br(info_upsert_custo_ent['qtd_inalterados'])} produto(s) "
                                    f"entraram com exatamente o mesmo custo anterior (conferir se o fiscal atualizou o custo): {ex_inalt_c}."
                                )
                            if info_upsert_custo_ent.get("qtd_alertas_variacao", 0) > 0:
                                teve_alerta = True
                                ex_var_c = ", ".join(info_upsert_custo_ent["exemplos_variacao"])
                                mensagens_auditoria_upload.append(
                                    f"⚠️ **Alerta de Variação de Custo (> 20%) na Entrada:** {formatar_num_br(info_upsert_custo_ent['qtd_alertas_variacao'])} produto(s) "
                                    f"tiveram alteração brusca em relação ao custo anterior: {ex_var_c}. Confira se a unidade da NF está correta!"
                                )
                            if qtd_rep_ent_lote > 0 and not ent_ja_somada_antes:
                                teve_alerta = True
                                ex_rep_ent = ", ".join(exemplos_rep_ent_lote[:5])
                                mensagens_auditoria_upload.append(
                                    f"⚠️ **Entradas (Linhas Repetidas Somadas):** {formatar_num_br(qtd_rep_ent_lote)} produto(s) "
                                    f"apareceram mais de uma vez na planilha ({formatar_num_br(qtd_extras_ent_lote)} linha(s) extra) e tiveram "
                                    f"suas quantidades somadas: {ex_rep_ent}."
                                )
                            for av_n in dict.fromkeys(avisos_sem_dt_ent):
                                teve_alerta = True
                                mensagens_auditoria_upload.append(av_n)
                            caixas_para_limpar.append("up_entradas")
                            resumo_toast_partes.append(f"Entradas: {formatar_num_br(len(novas_entradas))} SKUs")

                        # ------------------------------------------------------
                        # CAIXA 3: SAÍDAS / VENDAS (Validação Tudo ou Nada para 1..N arquivos)
                        # ------------------------------------------------------
                        hashes_lote_sai = []
                        if arqs_saidas:
                            dt_sai_iso_check = data_saida.strftime("%Y-%m-%d")
                            chave_op_sai = f"saidas_diarias::{dt_sai_iso_check}"
                            hashes_sai_ja_no_dia = list(
                                st.session_state.get("hashes_soma_por_data", {}).get(
                                    chave_op_sai, hashes_soma_meta.get(chave_op_sai, [])
                                )
                            )
                            frames_sai_lote = []
                            soma_val_sai_lote = 0.0
                            cols_val_sai_lote = []
                            qtd_rep_sai_lote = 0
                            qtd_extras_sai_lote = 0
                            exemplos_rep_sai_lote = []
                            avisos_sem_dt_sai = []

                            for idx_s, arq_s_item in enumerate(arqs_saidas, 1):
                                try:
                                    df_s_i, info_s_i = processar_planilha_movimento_diario(
                                        arquivo=arq_s_item,
                                        data_mov=data_saida,
                                        nome_aba="saidas_diarias",
                                        col_qtd="qtd_saida",
                                        rotulo_amigavel="Saídas Diárias",
                                        codigos_ref=codigos_ref_geral,
                                        ignorar_trava_catalogo=ignorar_trava_catalogo,
                                        ignorar_trava_data=ignorar_trava_data,
                                    )
                                except Exception as erro_item_s:
                                    prefixo_lote = (
                                        f"[Caixa Saídas — Arquivo {idx_s}/{len(arqs_saidas)}: '{arq_s_item.name}'] "
                                        if len(arqs_saidas) > 1
                                        else f"[Caixa Saídas: '{arq_s_item.name}'] "
                                    )
                                    raise ValueError(
                                        f"{prefixo_lote}{erro_item_s} (Nenhum arquivo do lote foi gravado — corrija e tente novamente)."
                                    ) from erro_item_s

                                h_s_i = hashlib.sha256(arq_s_item.getvalue()).hexdigest()[:16]
                                if h_s_i in hashes_lote_sai:
                                    raise ValueError(
                                        f"[Caixa Saídas — Arquivo {idx_s}/{len(arqs_saidas)}: '{arq_s_item.name}'] "
                                        f"Arquivo duplicado dentro do mesmo lote selecionado. Remova a cópia repetida e tente novamente."
                                    )
                                if somar_saidas_mesmo_dia and h_s_i in hashes_sai_ja_no_dia:
                                    raise ValueError(
                                        f"[Caixa Saídas — Arquivo {idx_s}/{len(arqs_saidas)}: '{arq_s_item.name}'] "
                                        f"Este arquivo exato já havia sido somado na data {data_saida.strftime('%d/%m/%Y')}. "
                                        f"Nenhum arquivo do lote foi gravado."
                                    )
                                hashes_lote_sai.append(h_s_i)
                                frames_sai_lote.append(df_s_i)
                                soma_val_sai_lote += float(info_s_i.get("soma_valor_venda", 0.0))
                                if info_s_i.get("coluna_valor_venda"):
                                    cols_val_sai_lote.append(info_s_i["coluna_valor_venda"])
                                qtd_rep_sai_lote += int(info_s_i.get("qtd_codigos_repetidos", 0))
                                qtd_extras_sai_lote += int(info_s_i.get("qtd_linhas_extras", 0))
                                exemplos_rep_sai_lote.extend(info_s_i.get("exemplos_repetidos", []))
                                if info_s_i.get("aviso_sem_data"):
                                    avisos_sem_dt_sai.append(info_s_i["aviso_sem_data"])

                            novas_saidas = (
                                pd.concat(frames_sai_lote, ignore_index=True)
                                .groupby(["data", "codigo"], as_index=False)
                                .agg(
                                    descricao=("descricao", "last"),
                                    qtd_saida=("qtd_saida", "sum"),
                                    valor_venda=("valor_venda", "sum"),
                                )
                            )
                            novas_saidas = padronizar_dataframe(novas_saidas, "saidas_diarias")

                            tag_arqs_sai = f" ({len(arqs_saidas)} arqs)" if len(arqs_saidas) > 1 else ""
                            modo_sai_str = (
                                f"somadas ao dia{tag_arqs_sai}"
                                if somar_saidas_mesmo_dia
                                else (f"consolidadas ({len(arqs_saidas)} arqs)" if len(arqs_saidas) > 1 else "gravadas")
                            )
                            col_val_nome = cols_val_sai_lote[0] if cols_val_sai_lote else ""
                            if soma_val_sai_lote > 0:
                                rot_col_fat = f" (coluna '{col_val_nome}')" if col_val_nome else ""
                                str_fat_sai = f" | Faturamento Bruto{rot_col_fat}: {formatar_moeda_br(soma_val_sai_lote)}"
                            else:
                                str_fat_sai = " | Sem coluna de faturamento"
                            mensagens_auditoria_upload.append(
                                f"✔️ **Saídas ({data_saida.strftime('%d/%m')}):** {formatar_num_br(len(novas_saidas))} SKUs {modo_sai_str} "
                                f"(Soma: {formatar_qtd_br(float(novas_saidas['qtd_saida'].sum()))} un.{str_fat_sai})."
                            )
                            if qtd_rep_sai_lote > 0:
                                teve_alerta = True
                                ex_rep_sai = ", ".join(exemplos_rep_sai_lote[:5])
                                mensagens_auditoria_upload.append(
                                    f"⚠️ **Saídas (Linhas Repetidas Somadas):** {formatar_num_br(qtd_rep_sai_lote)} produto(s) "
                                    f"apareceram mais de uma vez na planilha ({formatar_num_br(qtd_extras_sai_lote)} linha(s) extra) e tiveram "
                                    f"suas quantidades somadas: {ex_rep_sai}."
                                )
                            for av_s in dict.fromkeys(avisos_sem_dt_sai):
                                teve_alerta = True
                                mensagens_auditoria_upload.append(av_s)
                            caixas_para_limpar.append("up_saidas")
                            resumo_toast_partes.append(f"Saídas: {formatar_num_br(len(novas_saidas))} SKUs")

                        # ------------------------------------------------------
                        # CAIXA 4: CUSTOS C1 & TABELA T1 (Validação Tudo ou Nada para 1..N arquivos)
                        # ------------------------------------------------------
                        nova_ultima_data_custos_t1 = ultima_data_custos_t1
                        if arqs_custos:
                            dt_custos_iso = data_custos.strftime("%Y-%m-%d")
                            if ultima_data_custos_t1 and dt_custos_iso < ultima_data_custos_t1 and not ignorar_trava_data:
                                dt_ult_c_fmt = pd.to_datetime(ultima_data_custos_t1, format="%Y-%m-%d", errors="coerce")
                                str_ult_c = dt_ult_c_fmt.strftime("%d/%m/%Y") if pd.notna(dt_ult_c_fmt) else ultima_data_custos_t1
                                raise ValueError(
                                    f"Trava de Data Retroativa (Custos C1 & Tabela T1): A última carga de C1 & T1 gravada no sistema "
                                    f"é de **{str_ult_c}**, e você selecionou **{data_custos.strftime('%d/%m/%Y')}**. "
                                    f"Para evitar sobrescrever os custos e preços atuais com uma tabela antiga, o envio foi bloqueado. "
                                    f"Se realmente precisar reimportar uma data anterior, marque '📅 Ignorar trava de data no nome' nas Opções Avançadas."
                                )
                            frames_cus_lote = []
                            qtd_dup_cus_lote = 0
                            tem_col_t1_lote = False
                            avisos_sem_dt_cus = []
                            for idx_c, arq_c_item in enumerate(arqs_custos, 1):
                                try:
                                    df_c_i, info_c_i = processar_planilha_custos(
                                        arq_c_item,
                                        codigos_ref=codigos_ref_geral,
                                        ignorar_trava_catalogo=ignorar_trava_catalogo,
                                        data_custos=data_custos,
                                        ignorar_trava_data=ignorar_trava_data,
                                    )
                                except Exception as erro_item_c:
                                    prefixo_lote = (
                                        f"[Caixa Custos C1 & T1 — Arquivo {idx_c}/{len(arqs_custos)}: '{arq_c_item.name}'] "
                                        if len(arqs_custos) > 1
                                        else f"[Caixa Custos C1 & T1: '{arq_c_item.name}'] "
                                    )
                                    raise ValueError(
                                        f"{prefixo_lote}{erro_item_c} (Nenhum arquivo do lote foi gravado — corrija e tente novamente)."
                                    ) from erro_item_c
                                frames_cus_lote.append(df_c_i)
                                qtd_dup_cus_lote += int(info_c_i.get("qtd_duplicadas", 0))
                                if info_c_i.get("tem_coluna_t1", False):
                                    tem_col_t1_lote = True
                                if info_c_i.get("aviso_sem_data"):
                                    avisos_sem_dt_cus.append(info_c_i["aviso_sem_data"])

                            novos_custos = pd.concat(frames_cus_lote, ignore_index=True)
                            if len(arqs_custos) > 1:
                                qtd_dup_cus_lote += int(novos_custos.duplicated(subset=["codigo"], keep="last").sum())
                                novos_custos = novos_custos.drop_duplicates(subset=["codigo"], keep="last").reset_index(drop=True)
                            novos_custos = padronizar_dataframe(novos_custos, "custos")

                            nova_ultima_data_custos_t1 = max(ultima_data_custos_t1, dt_custos_iso) if ultima_data_custos_t1 else dt_custos_iso
                            if (not tem_col_t1_lote) and (not df_custos.empty) and ("preco_tabela" in df_custos.columns):
                                mapa_t1_prev = dict(zip(df_custos["codigo"], df_custos["preco_tabela"].fillna(0.0)))
                                novos_custos["preco_tabela"] = novos_custos["codigo"].map(mapa_t1_prev).fillna(0.0)

                            qtd_pos_c1 = int((novos_custos["custo_unitario"] > 0).sum())
                            qtd_zero_c1 = int((novos_custos["custo_unitario"] <= 0).sum())
                            qtd_pos_t1 = int((novos_custos["preco_tabela"] > 0).sum()) if "preco_tabela" in novos_custos.columns else 0
                            taxa_coinc_cus = (
                                (len(set(novos_custos["codigo"].unique()) & codigos_ref_geral) / max(len(novos_custos["codigo"].unique()), 1)) * 100.0
                                if codigos_ref_geral
                                else 100.0
                            )
                            tag_arqs_cus = f" ({len(arqs_custos)} arqs)" if len(arqs_custos) > 1 else ""
                            if qtd_dup_cus_lote > 0:
                                teve_alerta = True
                                mensagens_auditoria_upload.append(
                                    f"⚠️ **Custos & Preços{tag_arqs_cus}:** {formatar_num_br(qtd_dup_cus_lote)} código(s) repetido(s) (mantido o último valor)."
                                )
                            str_t1_info = (
                                f" | Preço Tabela T1: {formatar_num_br(qtd_pos_t1)} SKUs"
                                if tem_col_t1_lote
                                else ""
                            )
                            if qtd_zero_c1 > 0:
                                pct_zero = (qtd_zero_c1 / max(len(novos_custos), 1)) * 100.0
                                if pct_zero >= 30.0:
                                    teve_alerta = True
                                mensagens_auditoria_upload.append(
                                    f"ℹ️ **Custos C1 & T1{tag_arqs_cus}:** {formatar_num_br(qtd_pos_c1)} C1 positivos e "
                                    f"{formatar_num_br(qtd_zero_c1)} com C1 R$ 0,00 ({formatar_pct_br(pct_zero, 0)}{str_t1_info} | "
                                    f"Coincidência: {formatar_pct_br(taxa_coinc_cus)})."
                                )
                            else:
                                mensagens_auditoria_upload.append(
                                    f"✔️ **Custos C1 & T1 ({data_custos.strftime('%d/%m')}{tag_arqs_cus}):** {formatar_num_br(len(novos_custos))} itens verificados "
                                    f"(100% C1 > R$ 0{str_t1_info} | Coincidência: {formatar_pct_br(taxa_coinc_cus)})."
                                )
                            for av_c in dict.fromkeys(avisos_sem_dt_cus):
                                teve_alerta = True
                                mensagens_auditoria_upload.append(av_c)
                            caixas_para_limpar.append("up_custos")
                            resumo_toast_partes.append(f"Custos C1/T1: {formatar_num_br(len(novos_custos))} itens")

                        # Auditoria de descontos > 5% das Saídas (usando novos_custos se enviados no mesmo lote)
                        if novas_saidas is not None and not novas_saidas.empty:
                            df_custos_ref_desc = novos_custos if (novos_custos is not None and not novos_custos.empty) else df_custos
                            frames_ent_desc_up = [df_entradas_bruto] if not df_entradas_bruto.empty else []
                            if novas_entradas is not None and not novas_entradas.empty:
                                frames_ent_desc_up.append(novas_entradas)
                            df_ent_ref_desc_up = pd.concat(frames_ent_desc_up, ignore_index=True) if frames_ent_desc_up else pd.DataFrame()
                            df_aud_desc_upload = auditar_descontos_saidas_df(
                                df_saidas_ref=novas_saidas,
                                df_custos_ref=df_custos_ref_desc,
                                limite_desconto_pct=5.0,
                                df_entradas_ref=df_ent_ref_desc_up,
                            )
                            if not df_aud_desc_upload.empty:
                                teve_alerta = True
                                tot_d_rs = float(df_aud_desc_upload["desconto_total_rs"].sum())
                                ex_desc_list = [
                                    f"SKU {r['codigo']} (-{formatar_num_br(r['desconto_pct'], 1)}% | {formatar_moeda_br(r['preco_vendido_un'])} vs T1 {formatar_moeda_br(r['preco_tabela_t1'])})"
                                    for _, r in df_aud_desc_upload.head(5).iterrows()
                                ]
                                mensagens_auditoria_upload.append(
                                    f"🏷️ **Alerta de Desconto > 5% nas Saídas:** {formatar_num_br(len(df_aud_desc_upload))} produto(s) "
                                    f"vendido(s) acima de 5% de desconto sobre a Tabela T1 (Total concedido: {formatar_moeda_br(tot_d_rs)}): {', '.join(ex_desc_list)}."
                                )
                                df_tab_desc_sessao = df_aud_desc_upload[
                                    [
                                        "codigo",
                                        "descricao",
                                        "qtd_saida",
                                        "preco_tabela_t1",
                                        "preco_vendido_un",
                                        "desconto_pct",
                                        "desconto_total_rs",
                                        "custo_c1",
                                        "margem_real_pct",
                                        "status_desconto",
                                    ]
                                ].rename(
                                    columns={
                                        "codigo": "Código",
                                        "descricao": "Descrição",
                                        "qtd_saida": "Qtd. Vendida",
                                        "preco_tabela_t1": "Preço Tabela T1 (R$)",
                                        "preco_vendido_un": "Preço Vendido Balcão (R$)",
                                        "desconto_pct": "Desconto (%)",
                                        "desconto_total_rs": "Desconto Total (R$)",
                                        "custo_c1": "Custo C1 (R$)",
                                        "margem_real_pct": "Margem Real (%)",
                                        "status_desconto": "Status Desconto",
                                    }
                                )
                                st.session_state["auditoria_descontos_ultima_saida"] = df_tab_desc_sessao.to_dict("records")
                                st.session_state["data_auditoria_descontos_sai"] = data_saida.strftime("%d/%m/%Y")

                        # ------------------------------------------------------
                        # CAIXA 5: BASE INICIAL HISTÓRICA (Validação Tudo ou Nada para 1..N arquivos)
                        # ------------------------------------------------------
                        if arqs_base:
                            frames_base_lote = []
                            qtd_desc_div_base = 0
                            for idx_b, arq_b_item in enumerate(arqs_base, 1):
                                try:
                                    df_b_i, info_b_i = processar_planilha_base_vendas(
                                        arq_b_item,
                                        codigos_ref=codigos_ref_geral,
                                        ignorar_trava_catalogo=ignorar_trava_catalogo,
                                    )
                                except Exception as erro_item_b:
                                    prefixo_lote = (
                                        f"[Base Inicial — Arquivo {idx_b}/{len(arqs_base)}: '{arq_b_item.name}'] "
                                        if len(arqs_base) > 1
                                        else f"[Base Inicial: '{arq_b_item.name}'] "
                                    )
                                    raise ValueError(
                                        f"{prefixo_lote}{erro_item_b} (Nenhum arquivo do lote foi gravado — corrija e tente novamente)."
                                    ) from erro_item_b
                                frames_base_lote.append(df_b_i)
                                qtd_desc_div_base += int(info_b_i.get("qtd_desc_divergentes", 0))

                            nova_base = (
                                pd.concat(frames_base_lote, ignore_index=True)
                                .groupby("codigo", as_index=False)
                                .agg(
                                    descricao=("descricao", "last"),
                                    qtd_vendida_base=("qtd_vendida_base", "sum"),
                                )
                            )
                            nova_base = padronizar_dataframe(nova_base, "base_inicial")
                            taxa_coinc_base = (
                                (len(set(nova_base["codigo"].unique()) & codigos_ref_geral) / max(len(nova_base["codigo"].unique()), 1)) * 100.0
                                if codigos_ref_geral
                                else 100.0
                            )
                            tag_arqs_base = f" ({len(arqs_base)} arqs)" if len(arqs_base) > 1 else ""
                            msg_base = (
                                f"✔️ **Base Inicial{tag_arqs_base}:** {formatar_num_br(len(nova_base))} SKUs consolidados "
                                f"(Soma das vendas: {formatar_num_br(float(nova_base['qtd_vendida_base'].sum()))} un. | "
                                f"Coincidência: {formatar_pct_br(taxa_coinc_base)})"
                            )
                            if qtd_desc_div_base > 0:
                                msg_base += f" — {formatar_num_br(qtd_desc_div_base)} SKU(s) tinham mais de uma descrição e foram unificados pelo código."
                            mensagens_auditoria_upload.append(msg_base)
                            caixas_para_limpar.append("up_base")
                            resumo_toast_partes.append(f"Base Inicial: {formatar_num_br(len(nova_base))} SKUs")

                        # ------------------------------------------------------
                        # GRAVAÇÃO ATÔMICA NO SUPABASE (Só chega aqui se 100% dos arquivos passaram)
                        # ------------------------------------------------------
                        agora_str = agora_br().strftime("%d/%m/%Y %H:%M:%S")
                        ultimas_att_atualizadas = dict(ultimas_att_caixas)
                        if novo_estoque is not None:
                            ultimas_att_atualizadas["estoque"] = f"{agora_str} (Posição {data_posicao.strftime('%d/%m/%Y')})"
                        if novas_entradas is not None and not ent_ja_somada_antes:
                            ultimas_att_atualizadas["entradas"] = f"{agora_str} (Ref. {data_entrada.strftime('%d/%m/%Y')})"
                        if novas_saidas is not None:
                            ultimas_att_atualizadas["saidas"] = f"{agora_str} (Ref. {data_saida.strftime('%d/%m/%Y')})"
                        if novos_custos is not None:
                            ultimas_att_atualizadas["custos"] = f"{agora_str} (Tabela {data_custos.strftime('%d/%m/%Y')})"
                        if nova_base is not None:
                            ultimas_att_atualizadas["base"] = f"{agora_str} ({int(dias_base_input)} dias)"

                        try:
                            with db_supabase.transacao() as conn_tx:
                                if novo_estoque is not None:
                                    if atualizar_aba_estoque_atual:
                                        salvar_backup_automatico_sql(
                                            db_supabase, "estoque_atual", df_estoque_bruto, conn_externa=conn_tx
                                        )
                                        gravar_tabela_sql(
                                            db_supabase, "estoque_atual", novo_estoque, conn_externa=conn_tx
                                        )
                                        abas_ja_gravadas.append("estoque_atual")
                                    gravar_historico_incremental_sql(
                                        db_supabase,
                                        novo_estoque,
                                        data_str,
                                        conn_externa=conn_tx,
                                    )
                                    abas_ja_gravadas.append("historico")
                                if novas_entradas is not None:
                                    hash_lote_ent_unico = "|".join(hashes_lote_ent) if hashes_lote_ent else ""
                                    gravar_tabela_incremental_por_data_sql(
                                        db_supabase,
                                        "entradas_diarias",
                                        novas_entradas,
                                        data_entrada.strftime("%Y-%m-%d"),
                                        somar_mesma_data=somar_ent_efetivo,
                                        df_atual_memoria=df_entradas_bruto,
                                        hash_arquivo=hash_lote_ent_unico,
                                        criar_backup=True,
                                        hashes_soma_atuais=hashes_soma_meta,
                                        permitir_somar_codigos_repetidos_dia=permitir_somar_codigos_repetidos_dia,
                                        conn_externa=conn_tx,
                                    )
                                    if len(hashes_lote_ent) > 1 and somar_ent_efetivo:
                                        reg_h_e = st.session_state.setdefault("hashes_soma_por_data", {}).setdefault(
                                            f"entradas_diarias::{data_entrada.strftime('%Y-%m-%d')}", []
                                        )
                                        for h_sub_e in hashes_lote_ent:
                                            if h_sub_e not in reg_h_e:
                                                reg_h_e.append(h_sub_e)
                                    abas_ja_gravadas.append("entradas_diarias")
                                    if not df_pedidos_transito.empty:
                                        df_ent_comb_temp = pd.concat([df_entradas_bruto, novas_entradas], ignore_index=True)
                                        df_trans_pos_nf, cods_desp_sync, _ = depurar_pedidos_transito_auto_despertar(
                                            df_pedidos_transito, df_ent_comb_temp
                                        )
                                        if cods_desp_sync:
                                            salvar_backup_automatico_sql(
                                                db_supabase,
                                                "pedidos_transito",
                                                df_pedidos_transito,
                                                permitir_vazio=True,
                                                conn_externa=conn_tx,
                                            )
                                            gravar_tabela_sql(
                                                db_supabase,
                                                "pedidos_transito",
                                                df_trans_pos_nf,
                                                permitir_vazio=True,
                                                conn_externa=conn_tx,
                                            )
                                            abas_ja_gravadas.append("pedidos_transito")
                                            mensagens_auditoria_upload.append(
                                                f"🔔 **Auto-Despertar ('Já Comprei'):** {formatar_num_br(len(cods_desp_sync))} produto(s) "
                                                f"que estavam ocultos em trânsito chegaram nesta NF de Entrada e voltaram automaticamente ao painel!"
                                            )
                                if novas_saidas is not None:
                                    hash_lote_sai_unico = "|".join(hashes_lote_sai) if hashes_lote_sai else ""
                                    sai_ja_somada = gravar_tabela_incremental_por_data_sql(
                                        db_supabase,
                                        "saidas_diarias",
                                        novas_saidas,
                                        data_saida.strftime("%Y-%m-%d"),
                                        somar_mesma_data=somar_saidas_mesmo_dia,
                                        df_atual_memoria=df_saidas_bruto,
                                        hash_arquivo=hash_lote_sai_unico,
                                        criar_backup=True,
                                        hashes_soma_atuais=hashes_soma_meta,
                                        permitir_somar_codigos_repetidos_dia=permitir_somar_codigos_repetidos_dia,
                                        conn_externa=conn_tx,
                                    )
                                    if len(hashes_lote_sai) > 1 and somar_saidas_mesmo_dia:
                                        reg_h_s = st.session_state.setdefault("hashes_soma_por_data", {}).setdefault(
                                            f"saidas_diarias::{data_saida.strftime('%Y-%m-%d')}", []
                                        )
                                        for h_sub_s in hashes_lote_sai:
                                            if h_sub_s not in reg_h_s:
                                                reg_h_s.append(h_sub_s)
                                    if sai_ja_somada:
                                        teve_alerta = True
                                        mensagens_auditoria_upload.append(
                                            f"🛡️ **Proteção contra Soma Duplicada (Saídas {data_saida.strftime('%d/%m')}):** "
                                            f"Este arquivo exato (`{arqs_saidas[0].name}`) já havia sido somado nesta data e foi ignorado para não dobrar as vendas!"
                                        )
                                    abas_ja_gravadas.append("saidas_diarias")
                                if novos_custos is not None:
                                    if not df_custos_via_entrada.empty:
                                        cods_c1_pos = set(novos_custos.loc[novos_custos["custo_unitario"] > 0, "codigo"].unique())
                                        df_ent_complementar = df_custos_via_entrada[~df_custos_via_entrada["codigo"].isin(cods_c1_pos)].copy()
                                        if not df_ent_complementar.empty:
                                            novos_custos = padronizar_dataframe(
                                                pd.concat([novos_custos, df_ent_complementar], ignore_index=True), "custos"
                                            )
                                        mensagens_auditoria_upload.append(
                                            "🛡️ **Prioridade C1 & T1 Mantida:** O Custo C1 prevaleceu sobre o custo da NF (incluindo bonificações) e o Preço Tabela T1 foi atualizado."
                                        )
                                    dt_ref_cruz_nf = max(hoje_br(), data_custos)
                                    limite_nf_rec_iso = (dt_ref_cruz_nf - timedelta(days=int(janela_cruzamento_nf_c1_dias))).strftime("%Y-%m-%d")
                                    frames_ent_rec = []
                                    if not df_entradas_bruto.empty and "data" in df_entradas_bruto.columns:
                                        frames_ent_rec.append(df_entradas_bruto[df_entradas_bruto["data"] >= limite_nf_rec_iso])
                                    if novas_entradas is not None and not novas_entradas.empty:
                                        frames_ent_rec.append(novas_entradas)
                                    df_ent_rec_aud = pd.concat(frames_ent_rec, ignore_index=True) if frames_ent_rec else pd.DataFrame()
                                    regs_nf_ref = (
                                        info_upsert_custo_ent.get("registros_auditoria")
                                        or st.session_state.get("auditoria_custos_ultima_nf")
                                        or []
                                    )
                                    df_aj_c1_t1, resumo_aj_c1_t1 = auditar_ajustes_c1_t1_df(
                                        df_custos_antes=df_custos,
                                        df_custos_novos=novos_custos,
                                        df_entradas_recentes=df_ent_rec_aud,
                                        registros_auditoria_nf=regs_nf_ref,
                                        limite_alerta_c1_sem_t1_pct=2.0,
                                        tolerancia_frete_pct=float(tolerancia_frete_nf_c1_pct),
                                    )
                                    if not df_aj_c1_t1.empty:
                                        teve_alerta = True
                                        st.session_state["auditoria_ajustes_c1_t1"] = df_aj_c1_t1.to_dict("records")
                                        st.session_state["data_auditoria_ajustes_c1_t1"] = data_custos.strftime("%d/%m/%Y")
                                        st.session_state["resumo_auditoria_ajustes_c1_t1"] = resumo_aj_c1_t1
                                        partes_aj = [
                                            f"📊 **Ajustes C1 & T1 ({data_custos.strftime('%d/%m')}):** {formatar_num_br(resumo_aj_c1_t1['total_ajustes'])} item(ns) com movimentação"
                                        ]
                                        if resumo_aj_c1_t1.get("qtd_esquecimento_fiscal", 0) > 0:
                                            ex_esq_str = ", ".join(resumo_aj_c1_t1["exemplos_esquecimento_fiscal"][:4])
                                            partes_aj.append(
                                                f"🚨 **{formatar_num_br(resumo_aj_c1_t1['qtd_esquecimento_fiscal'])} item(ns) com NF acima do C1 (Conferir Fiscal)** ({ex_esq_str})"
                                            )
                                        if resumo_aj_c1_t1["qtd_defasagem_t1"] > 0:
                                            ex_def_str = ", ".join(resumo_aj_c1_t1["exemplos_defasagem_t1"][:4])
                                            partes_aj.append(
                                                f"⚠️ **{formatar_num_br(resumo_aj_c1_t1['qtd_defasagem_t1'])} item(ns) com C1 reajustado sem atualização no T1** ({ex_def_str})"
                                            )
                                        if resumo_aj_c1_t1["qtd_bonificacao_mantida"] > 0:
                                            partes_aj.append(
                                                f"🎁 **{formatar_num_br(resumo_aj_c1_t1['qtd_bonificacao_mantida'])} item(ns) de Bonificação/NF mantidos sem reajuste**"
                                            )
                                        mensagens_auditoria_upload.append(" — ".join(partes_aj) + ".")
                                    else:
                                        st.session_state.pop("auditoria_ajustes_c1_t1", None)
                                        mensagens_auditoria_upload.append(
                                            f"✔️ **Auditoria C1 & T1 ({data_custos.strftime('%d/%m')}):** Nenhuma alteração de C1 ou T1 em relação à base anterior."
                                        )
                                    salvar_backup_automatico_sql(db_supabase, "custos", df_custos, conn_externa=conn_tx)
                                    gravar_tabela_sql(db_supabase, "custos", novos_custos, conn_externa=conn_tx)
                                    abas_ja_gravadas.append("custos")
                                    if novas_saidas is None and not df_saidas_bruto.empty and "data" in df_saidas_bruto.columns:
                                        dt_sai_ref_iso = data_saida.strftime("%Y-%m-%d")
                                        df_sai_dia_t1 = df_saidas_bruto[df_saidas_bruto["data"] == dt_sai_ref_iso].copy()
                                        if not df_sai_dia_t1.empty:
                                            df_aud_desc_pos_t1 = auditar_descontos_saidas_df(
                                                df_saidas_ref=df_sai_dia_t1,
                                                df_custos_ref=novos_custos,
                                                limite_desconto_pct=5.0,
                                                df_entradas_ref=df_ent_rec_aud,
                                            )
                                            if not df_aud_desc_pos_t1.empty:
                                                teve_alerta = True
                                                tot_d_rs_t1 = float(df_aud_desc_pos_t1["desconto_total_rs"].sum())
                                                mensagens_auditoria_upload.append(
                                                    f"🏷️ **Conferência de Descontos > 5% (Saídas de {data_saida.strftime('%d/%m')}):** "
                                                    f"{formatar_num_br(len(df_aud_desc_pos_t1))} item(ns) vendido(s) acima de 5% de desconto vs. T1 "
                                                    f"(Total concedido: {formatar_moeda_br(tot_d_rs_t1)})."
                                                )
                                                df_tab_desc_sessao2 = df_aud_desc_pos_t1[
                                                    [
                                                        "codigo",
                                                        "descricao",
                                                        "qtd_saida",
                                                        "preco_tabela_t1",
                                                        "preco_vendido_un",
                                                        "desconto_pct",
                                                        "desconto_total_rs",
                                                        "custo_c1",
                                                        "margem_real_pct",
                                                        "status_desconto",
                                                    ]
                                                ].rename(
                                                    columns={
                                                        "codigo": "Código",
                                                        "descricao": "Descrição",
                                                        "qtd_saida": "Qtd. Vendida",
                                                        "preco_tabela_t1": "Preço Tabela T1 (R$)",
                                                        "preco_vendido_un": "Preço Vendido Balcão (R$)",
                                                        "desconto_pct": "Desconto (%)",
                                                        "desconto_total_rs": "Desconto Total (R$)",
                                                        "custo_c1": "Custo C1 (R$)",
                                                        "margem_real_pct": "Margem Real (%)",
                                                        "status_desconto": "Status Desconto",
                                                    }
                                                )
                                                st.session_state["auditoria_descontos_ultima_saida"] = df_tab_desc_sessao2.to_dict("records")
                                                st.session_state["data_auditoria_descontos_sai"] = data_saida.strftime("%d/%m/%Y")
                                elif not df_custos_via_entrada.empty:
                                    salvar_backup_automatico_sql(db_supabase, "custos", df_custos, conn_externa=conn_tx)
                                    gravar_tabela_sql(db_supabase, "custos", df_custos_via_entrada, conn_externa=conn_tx)
                                    abas_ja_gravadas.append("custos")
                                if nova_base is not None:
                                    salvar_backup_automatico_sql(db_supabase, "base_inicial", df_base_vendas, conn_externa=conn_tx)
                                    gravar_tabela_sql(db_supabase, "base_inicial", nova_base, conn_externa=conn_tx)
                                    abas_ja_gravadas.append("base_inicial")

                                df_meta_novo = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_input),
                                    ult_att_val=agora_str,
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=grupos_sku_custom,
                                    ultima_data_custos_t1=nova_ultima_data_custos_t1,
                                )
                                # Persiste também o timestamp individual de cada caixa importada no meta
                                linhas_caixas_meta = [
                                    {"chave": f"ult_att_{k_cx}", "valor": str(v_cx).strip()}
                                    for k_cx, v_cx in sorted(ultimas_att_atualizadas.items())
                                    if k_cx in ("estoque", "entradas", "saidas", "custos", "base") and str(v_cx).strip()
                                ]
                                if linhas_caixas_meta:
                                    df_meta_novo = (
                                        pd.concat([df_meta_novo, pd.DataFrame(linhas_caixas_meta)], ignore_index=True)
                                        .drop_duplicates(subset=["chave"], keep="last")
                                        .reset_index(drop=True)
                                    )
                                gravar_tabela_sql(db_supabase, "meta", df_meta_novo, conn_externa=conn_tx)
                                abas_ja_gravadas.append("meta")
                        except Exception:
                            st.session_state["hashes_soma_por_data"] = hashes_snapshot
                            abas_ja_gravadas.clear()
                            raise

                        # Sucesso total: limpa caches, renova chaves dinâmicas das caixas enviadas e prepara avisos persistentes
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        if caixas_para_limpar:
                            _limpar_uploaders(*caixas_para_limpar)
                        carregar_estado_completo.clear()
                        calcular_motor_giro_sazonal.clear()

                        resumo_banner = (
                            " | ".join(resumo_toast_partes)
                            if resumo_toast_partes
                            else f"Período da base atualizado para {int(dias_base_input)} dias"
                        )
                        st.session_state["msg_sucesso_sync"] = (
                            f"✅ Importação concluída e gravada com segurança no Supabase em **{agora_str}**! "
                            f"({resumo_banner})"
                        )
                        st.session_state["toast_sucesso_sync"] = f"Sincronizado com sucesso! ({resumo_banner})"
                        if mensagens_auditoria_upload:
                            st.session_state["aviso_duplicatas_sync"] = {
                                "tipo": "warning" if teve_alerta else "info",
                                "texto": " | ".join(mensagens_auditoria_upload),
                            }
                        st.rerun()
                    except Exception as erro_gravacao:
                        st.error(
                            f"❌ **Importação bloqueada antes de gravar na nuvem (transação revertida — nenhum dado anterior foi alterado e seus arquivos foram mantidos nas caixas para revisão):**\n\n"
                            f"{erro_gravacao}"
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
                    with st.spinner("Salvando configuração de grupos no Supabase..."):
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
                            gravar_tabela_sql(db_supabase, "meta", df_meta_grp)
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
                            gravar_tabela_sql(db_supabase, "meta", df_meta_grp)
                            carregar_estado_completo.clear()
                            st.session_state["msg_sucesso_sync"] = "✅ Nomes padrão dos prefixos restaurados!"
                            st.rerun()
                        except Exception as e_rst_gp:
                            st.error(f"❌ Erro ao restaurar: {e_rst_gp}")

            st.markdown("---")
            st.markdown("##### 2. Visualizar Produtos por Grupo & Mover em Lote para Outro Grupo")
            st.caption(
                "Filtre qualquer grupo atual (ex.: `Outros (90)` ou `50 - Veterinária & Reprodução`) para ver todos os produtos que estão dentro dele, "
                "marque os itens desejados na tabela e mova-os para outro grupo (ou devolva-os ao grupo original do prefixo)."
            )
            if not df_cat_grp.empty:
                linhas_grp_cat = []
                for _, r_gc in df_cat_grp.sort_values("descricao").iterrows():
                    c_gc = str(r_gc["codigo"]).strip()
                    d_gc = str(r_gc["descricao"]).strip()
                    pref_gc = c_gc[:2] if len(c_gc) >= 2 else c_gc
                    grp_padrao_gc = mapa_depto_ativo.get(pref_gc, f"Outros ({pref_gc or 'S/C'})")
                    grp_atual_gc = identificar_departamento_sku(c_gc, grupos_pref_custom, grupos_sku_custom)
                    eh_mov_manual = c_gc in grupos_sku_custom
                    linhas_grp_cat.append(
                        {
                            "codigo": c_gc,
                            "descricao": d_gc,
                            "grupo_atual": grp_atual_gc,
                            "grupo_padrao": grp_padrao_gc,
                            "movido_manual": eh_mov_manual,
                            "origem_label": "📌 Movido Manualmente" if eh_mov_manual else "🏷️ Padrão do Prefixo",
                        }
                    )
                df_grp_cat_full = pd.DataFrame(linhas_grp_cat)
                contagem_grp_atual = df_grp_cat_full.groupby("grupo_atual")["codigo"].count().to_dict()
                opcoes_grp_filtro = ["Todos os Grupos"] + sorted(df_grp_cat_full["grupo_atual"].unique())

                fg1, fg2, fg3 = st.columns([1.5, 1.3, 1.2])
                with fg1:
                    grp_atual_filtro = st.selectbox(
                        "📂 Filtrar Grupo Atual (ver itens dentro do grupo):",
                        options=opcoes_grp_filtro,
                        format_func=lambda g: (
                            f"Todos os Grupos ({formatar_num_br(len(df_grp_cat_full))} SKUs)"
                            if g == "Todos os Grupos"
                            else f"{g} ({formatar_num_br(contagem_grp_atual.get(g, 0))} SKUs)"
                        ),
                        key="sel_filtro_grp_atual_aba7",
                    )
                with fg2:
                    busca_grp_sku_txt = st.text_input(
                        "🔍 Buscar produto dentro do filtro:",
                        placeholder="Digite código ou nome...",
                        key="busca_txt_grp_sku_aba7",
                    )
                with fg3:
                    filtro_origem_grp = st.selectbox(
                        "🏷️ Filtrar Origem:",
                        options=[
                            "📋 Todos os Produtos do Filtro",
                            f"📌 Apenas Movidos Manualmente ({formatar_num_br(len(grupos_sku_custom))})",
                            "🏷️ Apenas no Grupo Padrão do Prefixo",
                        ],
                        index=0,
                        key="sel_origem_grp_aba7",
                    )

                df_grp_view = df_grp_cat_full.copy()
                if grp_atual_filtro != "Todos os Grupos":
                    df_grp_view = df_grp_view[df_grp_view["grupo_atual"] == grp_atual_filtro].copy()
                if filtro_origem_grp.startswith("📌"):
                    df_grp_view = df_grp_view[df_grp_view["movido_manual"] == True].copy()
                elif filtro_origem_grp.startswith("🏷️"):
                    df_grp_view = df_grp_view[df_grp_view["movido_manual"] == False].copy()
                if busca_grp_sku_txt and busca_grp_sku_txt.strip():
                    t_g = busca_grp_sku_txt.lower().strip()
                    df_grp_view = df_grp_view[
                        df_grp_view["codigo"].str.lower().str.contains(t_g, na=False, regex=False)
                        | df_grp_view["descricao"].str.lower().str.contains(t_g, na=False, regex=False)
                    ].copy()

                df_grp_view = df_grp_view.reset_index(drop=True)
                cg_sel1, cg_sel2 = st.columns([1.5, 2.5])
                with cg_sel1:
                    marcar_todos_grp_view = st.checkbox(
                        f"Selecionar todos os {formatar_num_br(len(df_grp_view))} produto(s) filtrados",
                        value=False,
                        key="chk_sel_todos_grp_aba7",
                    )
                with cg_sel2:
                    st.caption(
                        f"Exibindo **{formatar_num_br(len(df_grp_view))} produto(s)** | "
                        f"Total de exceções personalizadas ativas: **{formatar_num_br(len(grupos_sku_custom))}**"
                    )

                df_grp_ed_in = pd.DataFrame(
                    {
                        "selecionar": [bool(marcar_todos_grp_view)] * len(df_grp_view),
                        "Cód.": df_grp_view["codigo"].values,
                        "Descrição": df_grp_view["descricao"].values,
                        "Grupo Atual": df_grp_view["grupo_atual"].values,
                        "Grupo Original (Prefixo)": df_grp_view["grupo_padrao"].values,
                        "Origem": df_grp_view["origem_label"].values,
                    }
                )
                ed_grp_out = st.data_editor(
                    df_grp_ed_in,
                    use_container_width=True,
                    hide_index=True,
                    height=340,
                    key="editor_mover_grupos_aba7",
                    disabled=["Cód.", "Descrição", "Grupo Atual", "Grupo Original (Prefixo)", "Origem"],
                    column_config={
                        "selecionar": st.column_config.CheckboxColumn(
                            "Mover?",
                            help="Marque os produtos que deseja transferir de grupo ou devolver ao grupo original.",
                            default=False,
                            width="small",
                        ),
                        "Cód.": st.column_config.TextColumn("Cód.", width="small"),
                        "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
                        "Grupo Atual": st.column_config.TextColumn("Grupo Atual", width="medium"),
                        "Grupo Original (Prefixo)": st.column_config.TextColumn("Grupo Original (Prefixo)", width="medium"),
                        "Origem": st.column_config.TextColumn("Origem", width="small"),
                    },
                )

                sel_grp_rows = ed_grp_out[ed_grp_out["selecionar"] == True]
                cods_sel_grp = [normalizar_codigo_sku(c) for c in sel_grp_rows["Cód."].tolist() if normalizar_codigo_sku(c)]
                qtd_sel_grp = len(cods_sel_grp)
                qtd_sel_com_excecao = sum(1 for c in cods_sel_grp if c in grupos_sku_custom)

                grupos_disponiveis_destino = sorted(
                    list(
                        set(mapa_depto_ativo.values())
                        | set(grupos_sku_custom.values())
                        | {f"Outros ({p})" for p in todos_prefixos if p not in mapa_depto_ativo}
                    )
                )
                cm_sku1, cm_sku2, cm_sku3 = st.columns([1.5, 1.3, 1.2])
                with cm_sku1:
                    grupo_destino_sel = st.selectbox(
                        "Grupo de Destino para os Selecionados:",
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
                with cm_sku2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button(
                        f"📌 Mover ({formatar_num_br(qtd_sel_grp)}) para o Destino",
                        type="primary",
                        use_container_width=True,
                        disabled=(qtd_sel_grp == 0 or not grupo_destino_final),
                        key="btn_fixar_sku_grupo",
                    ):
                        with st.spinner("Movendo produtos selecionados no Supabase..."):
                            try:
                                novo_sku_custom = dict(grupos_sku_custom)
                                for cod_alvo_m in cods_sel_grp:
                                    novo_sku_custom[cod_alvo_m] = grupo_destino_final
                                df_meta_sku = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_atual),
                                    ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=novo_sku_custom,
                                )
                                gravar_tabela_sql(db_supabase, "meta", df_meta_sku)
                                carregar_estado_completo.clear()
                                calcular_motor_giro_sazonal.clear()
                                st.session_state["msg_sucesso_sync"] = (
                                    f"✅ {formatar_num_br(qtd_sel_grp)} produto(s) movido(s) para o grupo '{grupo_destino_final}'!"
                                )
                                st.rerun()
                            except Exception as e_sk_g:
                                st.error(f"❌ Erro ao mover produto de grupo: {e_sk_g}")
                with cm_sku3:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button(
                        f"↩️ Devolver ({formatar_num_br(qtd_sel_com_excecao)}) ao Original",
                        use_container_width=True,
                        disabled=(qtd_sel_com_excecao == 0),
                        key="btn_rem_excecao_sku_grp",
                    ):
                        with st.spinner("Devolvendo produtos ao grupo original no Supabase..."):
                            try:
                                set_dev_g = set(cods_sel_grp)
                                novo_sku_custom = {
                                    k: v
                                    for k, v in grupos_sku_custom.items()
                                    if k not in set_dev_g
                                }
                                df_meta_sku = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_atual),
                                    ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=novo_sku_custom,
                                )
                                gravar_tabela_sql(db_supabase, "meta", df_meta_sku)
                                carregar_estado_completo.clear()
                                calcular_motor_giro_sazonal.clear()
                                st.session_state["msg_sucesso_sync"] = (
                                    f"✅ {formatar_num_br(qtd_sel_com_excecao)} produto(s) devolvido(s) ao grupo original do prefixo!"
                                )
                                st.rerun()
                            except Exception as e_rm_sk:
                                st.error(f"❌ Erro ao devolver produtos ao grupo original: {e_rm_sk}")

            st.markdown("---")
            st.markdown("##### 3. Definir Produtos de Matéria-Prima / Produção de Ração (MP — Saída por Ordem de Produção)")
            st.caption(
                "Itens de transformação para produção de ração não aparecem no relatório de Saídas Faturadas — o sistema apura o consumo deles "
                "pela equação fechada de fábrica (**Estoque Inicial + Entrada NF − Estoque Final**). "
                "Use os filtros abaixo para localizar insumos da fábrica (inclusive os **💡 Sugeridos pela IA**, que tiveram queda de estoque sem venda faturada) "
                "e marque a caixinha **🏭 É MP / Produção?** diretamente na tabela."
            )
            if not df_cat_grp.empty:
                # Apura quedas no histórico vs. saídas faturadas para sugerir automaticamente itens de transformação/produção
                mapa_qtd_sai_mp = (
                    df_saidas_bruto.groupby("codigo")["qtd_saida"].sum().to_dict()
                    if (df_saidas_bruto is not None and not df_saidas_bruto.empty)
                    else {}
                )
                mapa_queda_hist_mp = {}
                if df_historico_bruto is not None and not df_historico_bruto.empty and "data" in df_historico_bruto.columns:
                    datas_h_mp = sorted(df_historico_bruto["data"].dropna().unique())
                    if len(datas_h_mp) >= 2:
                        piv_mp = (
                            df_historico_bruto.drop_duplicates(subset=["codigo", "data"], keep="last")
                            .pivot(index="codigo", columns="data", values="saldo_geral")
                            .reindex(columns=datas_h_mp)
                            .fillna(0.0)
                        )
                        quedas_h_mp = (-piv_mp.diff(axis=1).iloc[:, 1:]).clip(lower=0.0).sum(axis=1)
                        mapa_queda_hist_mp = quedas_h_mp.to_dict()

                linhas_mp_tabela = []
                for _, r_mp in df_cat_grp.sort_values("descricao").iterrows():
                    c_mp = str(r_mp["codigo"]).strip()
                    d_mp = str(r_mp["descricao"]).strip()
                    dep_mp = identificar_departamento_sku(c_mp, grupos_pref_custom, grupos_sku_custom)
                    eh_mp_at = identificar_produto_mp(c_mp, d_mp, grupos_sku_custom, mp_custom_map)
                    q_est_b = float(mapa_queda_hist_mp.get(c_mp, 0.0))
                    q_sai_f = float(mapa_qtd_sai_mp.get(c_mp, 0.0))
                    sug_ia_mp = (not eh_mp_at) and (q_est_b > 0.0) and (q_sai_f <= 0.0) and (c_mp not in mp_custom_map)
                    if eh_mp_at:
                        if c_mp in mp_custom_map:
                            diag_mp = "🏭 MP Ativo (Marcado Manualmente)"
                        else:
                            diag_mp = "🏭 MP Ativo (Automático por Nome MP/ME)"
                    elif sug_ia_mp:
                        diag_mp = "💡 Sugerido IA (Queda no estoque s/ saída faturada)"
                    else:
                        diag_mp = "🏪 Loja Varejo"

                    linhas_mp_tabela.append(
                        {
                            "codigo": c_mp,
                            "descricao": d_mp,
                            "departamento": dep_mp,
                            "eh_mp": bool(eh_mp_at),
                            "sugerido_ia": bool(sug_ia_mp),
                            "diagnostico_mp": diag_mp,
                            "baixa_estoque": q_est_b,
                            "saida_faturada": q_sai_f,
                        }
                    )
                df_mp_catalogo = pd.DataFrame(linhas_mp_tabela)
                qtd_mp_ativos_tot = int(df_mp_catalogo["eh_mp"].sum())
                qtd_sug_ia_mp = int(df_mp_catalogo["sugerido_ia"].sum())

                f_mp1, f_mp2, f_mp3 = st.columns([1.4, 1.3, 1.3])
                with f_mp1:
                    busca_mp_txt = st.text_input(
                        "🔍 Buscar insumo / produto (código ou nome):",
                        placeholder="Ex: milho, sorgo, bicarbonato, 2601...",
                        key="busca_txt_mp_aba7",
                    )
                with f_mp2:
                    deptos_mp_opcoes = ["Todos os Grupos"] + sorted(df_mp_catalogo["departamento"].unique())
                    depto_mp_sel = st.selectbox(
                        "📂 Filtrar por Grupo / Prefixo:",
                        options=deptos_mp_opcoes,
                        index=0,
                        key="sel_depto_mp_aba7",
                    )
                with f_mp3:
                    status_mp_filtro = st.selectbox(
                        "🏷️ Filtrar Classificação:",
                        options=[
                            f"🏭 Marcados como MP ({formatar_num_br(qtd_mp_ativos_tot)}) + 💡 Sugeridos IA ({formatar_num_br(qtd_sug_ia_mp)})",
                            f"🏭 Apenas Marcados como MP ({formatar_num_br(qtd_mp_ativos_tot)})",
                            f"💡 Apenas Sugeridos pela IA ({formatar_num_br(qtd_sug_ia_mp)})",
                            "📋 Todos os Produtos do Catálogo",
                            "🏪 Apenas Loja Varejo",
                        ],
                        index=0,
                        key="sel_status_mp_aba7",
                    )

                df_mp_view = df_mp_catalogo.copy()
                if depto_mp_sel != "Todos os Grupos":
                    df_mp_view = df_mp_view[df_mp_view["departamento"] == depto_mp_sel].copy()
                if status_mp_filtro.startswith("🏭 Marcados como MP"):
                    df_mp_view = df_mp_view[df_mp_view["eh_mp"] | df_mp_view["sugerido_ia"]].copy()
                elif status_mp_filtro.startswith("🏭 Apenas Marcados"):
                    df_mp_view = df_mp_view[df_mp_view["eh_mp"]].copy()
                elif status_mp_filtro.startswith("💡 Apenas Sugeridos"):
                    df_mp_view = df_mp_view[df_mp_view["sugerido_ia"]].copy()
                elif status_mp_filtro.startswith("🏪 Apenas Loja"):
                    df_mp_view = df_mp_view[~df_mp_view["eh_mp"]].copy()

                if busca_mp_txt and busca_mp_txt.strip():
                    t_mp = busca_mp_txt.lower().strip()
                    df_mp_view = df_mp_view[
                        df_mp_view["codigo"].str.lower().str.contains(t_mp, na=False, regex=False)
                        | df_mp_view["descricao"].str.lower().str.contains(t_mp, na=False, regex=False)
                    ].copy()

                df_mp_view = df_mp_view.sort_values(
                    ["eh_mp", "sugerido_ia", "baixa_estoque", "descricao"],
                    ascending=[False, False, False, True],
                ).reset_index(drop=True)

                st.caption(
                    f"Exibindo **{formatar_num_br(len(df_mp_view))} produto(s)** | "
                    f"Total marcado como MP na empresa: **{formatar_num_br(qtd_mp_ativos_tot)}** | "
                    f"Sugeridos pela IA: **{formatar_num_br(qtd_sug_ia_mp)}**"
                )

                df_mp_ed_in = pd.DataFrame(
                    {
                        "eh_mp": df_mp_view["eh_mp"].values,
                        "Cód.": df_mp_view["codigo"].values,
                        "Descrição": df_mp_view["descricao"].values,
                        "Grupo": df_mp_view["departamento"].values,
                        "Diagnóstico & Origem": df_mp_view["diagnostico_mp"].values,
                        "Baixa Estoque": [formatar_qtd_br(v) for v in df_mp_view["baixa_estoque"].values],
                        "Saída Faturada": [formatar_qtd_br(v) for v in df_mp_view["saida_faturada"].values],
                    }
                )
                ed_mp_out = st.data_editor(
                    df_mp_ed_in,
                    use_container_width=True,
                    hide_index=True,
                    height=340,
                    key="editor_tabela_mp_aba7",
                    disabled=["Cód.", "Descrição", "Grupo", "Diagnóstico & Origem", "Baixa Estoque", "Saída Faturada"],
                    column_config={
                        "eh_mp": st.column_config.CheckboxColumn(
                            "🏭 MP?",
                            help="Marque se este produto é Matéria-Prima / Insumo de transformação da fábrica de ração.",
                            default=False,
                            width="small",
                        ),
                        "Cód.": st.column_config.TextColumn("Cód.", width="small"),
                        "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
                        "Grupo": st.column_config.TextColumn("Grupo", width="medium"),
                        "Diagnóstico & Origem": st.column_config.TextColumn("Diagnóstico & Origem", width="medium"),
                        "Baixa Estoque": st.column_config.TextColumn("Baixa Estoque", help="Total de redução de saldo observada no histórico de estoque.", width="small"),
                        "Saída Faturada": st.column_config.TextColumn("Saída Faturada", help="Total vendido registrado nas planilhas de Saídas Faturadas.", width="small"),
                    },
                )

                cmp_b1, cmp_b2 = st.columns([1.6, 1.2])
                with cmp_b1:
                    if st.button(
                        "💾 Salvar Marcações de MP da Tabela no Supabase",
                        type="primary",
                        use_container_width=True,
                        disabled=ed_mp_out.empty,
                        key="btn_salvar_tabela_mp_aba7",
                    ):
                        with st.spinner("Salvando classificação de Matérias-Primas no Supabase..."):
                            try:
                                novo_mp_map = dict(mp_custom_map)
                                qtd_alterados_mp = 0
                                for idx_row_m, r_ed_m in ed_mp_out.iterrows():
                                    cod_m = normalizar_codigo_sku(r_ed_m["Cód."])
                                    flag_nova = bool(r_ed_m["eh_mp"])
                                    flag_antiga = bool(df_mp_view.loc[idx_row_m, "eh_mp"])
                                    if cod_m and flag_nova != flag_antiga:
                                        novo_mp_map[cod_m] = "1" if flag_nova else "0"
                                        qtd_alterados_mp += 1
                                df_meta_mp = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_atual),
                                    ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=grupos_sku_custom,
                                    mp_custom_map=novo_mp_map,
                                )
                                gravar_tabela_sql(db_supabase, "meta", df_meta_mp)
                                carregar_estado_completo.clear()
                                calcular_motor_giro_sazonal.clear()
                                st.session_state["msg_sucesso_sync"] = (
                                    f"✅ Classificação de Matéria-Prima atualizada com sucesso ({formatar_num_br(qtd_alterados_mp)} alteração(ões) salva(s))!"
                                )
                                st.rerun()
                            except Exception as e_mp_tab:
                                st.error(f"❌ Erro ao salvar classificação MP: {e_mp_tab}")
                with cmp_b2:
                    if st.button(
                        f"🏭 Marcar Todos os {formatar_num_br(len(ed_mp_out))} Filtrados como MP",
                        use_container_width=True,
                        disabled=ed_mp_out.empty,
                        key="btn_marcar_todos_filtrados_mp",
                    ):
                        with st.spinner("Marcando todos os itens filtrados como MP..."):
                            try:
                                novo_mp_map = dict(mp_custom_map)
                                for _, r_ed_m in ed_mp_out.iterrows():
                                    cod_m = normalizar_codigo_sku(r_ed_m["Cód."])
                                    if cod_m:
                                        novo_mp_map[cod_m] = "1"
                                df_meta_mp = montar_dataframe_meta_completo(
                                    dias_base_val=int(dias_base_atual),
                                    ult_att_val=str(estado.get("ultima_atualizacao", agora_br().strftime("%d/%m/%Y %H:%M:%S"))),
                                    grupos_pref_custom=grupos_pref_custom,
                                    grupos_sku_custom=grupos_sku_custom,
                                    mp_custom_map=novo_mp_map,
                                )
                                gravar_tabela_sql(db_supabase, "meta", df_meta_mp)
                                carregar_estado_completo.clear()
                                calcular_motor_giro_sazonal.clear()
                                st.session_state["msg_sucesso_sync"] = (
                                    f"✅ Todos os {formatar_num_br(len(ed_mp_out))} item(ns) filtrados foram marcados como Matéria-Prima de Fábrica!"
                                )
                                st.rerun()
                            except Exception as e_mp_all:
                                st.error(f"❌ Erro ao marcar filtrados como MP: {e_mp_all}")


        with st.expander("👥 Gerenciar Usuários de Acesso ao Aplicativo (Painel Administrador)", expanded=False):
            st.caption(
                "Cadastre novos usuários para consultar os painéis do sistema. **Apenas usuários com perfil Administrador** "
                "podem subir planilhas ou alterar dados na Aba 6."
            )
            admin_mestre_u, _, _ = obter_credencial_admin_mestre()
            if "msg_usuarios_aba7" in st.session_state:
                st.success(st.session_state.pop("msg_usuarios_aba7"))

            st.markdown("##### 1. Cadastrar Novo Usuário")
            with st.form("form_novo_usuario_v22", clear_on_submit=True):
                cu1, cu2, cu3, cu4 = st.columns([1.2, 1.5, 1.2, 1.0])
                with cu1:
                    novo_u_login = st.text_input("Usuário (Login):", placeholder="Ex: compras.esteio")
                with cu2:
                    novo_u_nome = st.text_input("Nome de Exibição:", placeholder="Ex: Compras Esteio")
                with cu3:
                    novo_u_senha = st.text_input("Senha Inicial:", type="password", placeholder="Mínimo 4 caracteres")
                with cu4:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    novo_u_admin = st.checkbox("👑 Perfil Admin?", value=False, help="Deixe desmarcado para usuário padrão (não pode subir planilhas).")
                btn_criar_u = st.form_submit_button("➕ Criar Usuário", type="primary")
                if btn_criar_u:
                    try:
                        salvar_usuario_sql(
                            db_supabase,
                            username=novo_u_login,
                            nome_exibicao=novo_u_nome,
                            senha_plana=novo_u_senha,
                            eh_admin=novo_u_admin,
                            ativo=True,
                        )
                        st.session_state["msg_usuarios_aba7"] = (
                            f"✅ Usuário `{_normalizar_username(novo_u_login)}` cadastrado com sucesso!"
                        )
                        st.rerun()
                    except Exception as e_cu:
                        st.error(f"❌ Não foi possível criar o usuário: {e_cu}")

            st.markdown("---")
            st.markdown("##### 2. Usuários Cadastrados (Ativar / Desativar / Excluir)")
            df_usuarios_db = listar_usuarios_sql(db_supabase)
            if not df_usuarios_db.empty:
                df_u_ed_in = pd.DataFrame(
                    {
                        "Usuário": df_usuarios_db["username"].values,
                        "Nome de Exibição": df_usuarios_db["nome_exibicao"].values,
                        "Perfil": ["👑 Administrador" if a else "👤 Consulta (Sem Upload)" for a in df_usuarios_db["eh_admin"].values],
                        "Ativo": df_usuarios_db["ativo"].values,
                        "Criado em": df_usuarios_db["criado_em"].values,
                        "Excluir": [False] * len(df_usuarios_db),
                    }
                )
                ed_u_out = st.data_editor(
                    df_u_ed_in,
                    use_container_width=True,
                    hide_index=True,
                    key="editor_usuarios_v22",
                    disabled=["Usuário", "Perfil", "Criado em"],
                    column_config={
                        "Usuário": st.column_config.TextColumn("Usuário", width="small"),
                        "Nome de Exibição": st.column_config.TextColumn("Nome de Exibição", width="medium"),
                        "Perfil": st.column_config.TextColumn("Perfil", width="small"),
                        "Ativo": st.column_config.CheckboxColumn("Ativo?", width="small"),
                        "Criado em": st.column_config.TextColumn("Criado em", width="small"),
                        "Excluir": st.column_config.CheckboxColumn("Excluir?", width="small"),
                    },
                )
                if st.button("💾 Salvar Alterações nos Usuários", type="primary", key="btn_salvar_ed_usuarios_v22"):
                    try:
                        lista_att_u = []
                        lista_rm_u = []
                        for _, r_u in ed_u_out.iterrows():
                            u_cod = _normalizar_username(r_u["Usuário"])
                            if bool(r_u["Excluir"]) and u_cod != admin_mestre_u:
                                lista_rm_u.append(u_cod)
                            else:
                                lista_att_u.append((u_cod, r_u["Nome de Exibição"], bool(r_u["Ativo"])))
                        atualizar_status_ou_remover_usuarios_sql(
                            db_supabase,
                            atualizacoes_status=lista_att_u,
                            usernames_remover=lista_rm_u,
                            admin_mestre_user=admin_mestre_u,
                        )
                        st.session_state["msg_usuarios_aba7"] = "✅ Lista de usuários atualizada com sucesso!"
                        st.rerun()
                    except Exception as e_sau:
                        st.error(f"❌ Erro ao atualizar usuários: {e_sau}")

                st.markdown("---")
                st.markdown("##### 3. Redefinir Senha de um Usuário")
                usuarios_redef = [u for u in df_usuarios_db["username"].tolist() if u != admin_mestre_u]
                if usuarios_redef:
                    cr_u1, cr_u2, cr_u3 = st.columns([1.4, 1.4, 1.0])
                    with cr_u1:
                        u_alvo_senha = st.selectbox("Selecione o Usuário:", options=usuarios_redef, key="sel_u_redef_senha_v22")
                    with cr_u2:
                        nova_senha_u_redef = st.text_input("Nova Senha:", type="password", key="txt_nova_senha_u_v22")
                    with cr_u3:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("🔑 Alterar Senha", use_container_width=True, key="btn_redef_senha_u_v22"):
                            try:
                                row_u_sel = df_usuarios_db[df_usuarios_db["username"] == u_alvo_senha].iloc[0]
                                salvar_usuario_sql(
                                    db_supabase,
                                    username=u_alvo_senha,
                                    nome_exibicao=str(row_u_sel["nome_exibicao"]),
                                    senha_plana=nova_senha_u_redef,
                                    eh_admin=bool(row_u_sel["eh_admin"]),
                                    ativo=bool(row_u_sel["ativo"]),
                                )
                                st.session_state["msg_usuarios_aba7"] = f"✅ Senha do usuário `{u_alvo_senha}` alterada!"
                                st.rerun()
                            except Exception as e_rsu:
                                st.error(f"❌ Erro ao alterar senha: {e_rsu}")
                else:
                    st.caption(
                        f"ℹ️ A senha do Administrador Mestre (`{admin_mestre_u}`) é protegida diretamente via `app_password` em `st.secrets`."
                    )

    r1, r2, r3, r4 = st.columns(4)
    qtd_skus_visiveis = df_estoque["codigo"].nunique() if (not df_estoque.empty and "codigo" in df_estoque.columns) else 0
    qtd_datas_hist = df_historico_bruto["data"].nunique() if (not df_historico_bruto.empty and "data" in df_historico_bruto.columns) else 0
    qtd_datas_ent = df_entradas_bruto["data"].nunique() if (not df_entradas_bruto.empty and "data" in df_entradas_bruto.columns) else 0
    qtd_datas_sai = df_saidas_bruto["data"].nunique() if (not df_saidas_bruto.empty and "data" in df_saidas_bruto.columns) else 0
    qtd_custos = len(df_custos) if not df_custos.empty else 0
    r1.metric("Produtos Ativos com Saldo/Catálogo", f"{formatar_num_br(qtd_skus_visiveis)} (Ocultos: {formatar_num_br(len(codigos_ocultos))})")
    r2.metric(
        "Histórico 2 Anos (Est. / Ent. / Saí.)",
        f"{formatar_num_br(qtd_datas_hist)}d / {formatar_num_br(qtd_datas_ent)}d / {formatar_num_br(qtd_datas_sai)}d",
    )
    r3.metric("Itens com Custo Cadastrado", f"{formatar_num_br(qtd_custos)}")
    r4.metric("Última Sincronização", estado.get("ultima_atualizacao", "-"))
