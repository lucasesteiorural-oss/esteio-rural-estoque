"""
ui/tab_auditoria.py — Aba 5: Auditoria de Lotes, Saldos Negativos, Sem Custo
e Auditoria Fiscal Permanente.
"""
import pandas as pd
import streamlit as st

from parsers import (
    hoje_br,
    formatar_num_br,
    formatar_qtd_br,
    formatar_moeda_br,
    formatar_pct_br,
    estilizar_tabela_br,
    converter_datas_deterministico,
    gerar_excel_relatorio,
    identificar_departamento_sku,
)
from analytics import (
    auditar_descontos_saidas_df,
    auditar_fiscal_permanente_nf_c1_t1,
)


def render_tab_auditoria(ctx: dict) -> None:
    """Renderiza a Aba 5 — Auditoria de ERP."""
    df_estoque = ctx["df_estoque"]
    df_entradas = ctx["df_entradas"]
    df_saidas = ctx["df_saidas"]
    df_custos = ctx["df_custos"]
    df_custos_rel = ctx["df_custos_rel"]
    grupos_pref_custom = ctx["grupos_pref_custom"]
    grupos_sku_custom = ctx["grupos_sku_custom"]

    st.markdown("### 🔍 Auditoria e Classificação de Divergências de ERP")
    st.caption(
        "Os valores originais do ERP nunca são alterados automaticamente. "
        "Abaixo, cada divergência é classificada por natureza operacional para facilitar a conferência no Siagri."
    )
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 6 (Importação & Backup) para auditar divergências de lote e saldos.")
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

    st.markdown("---")
    st.markdown("#### 4. Auditoria Fiscal Permanente — Compras & Custos (Última NF × C1 × Tabela T1)")
    st.caption(
        "Recalculada diretamente a partir das tabelas gravadas no Supabase (não some ao atualizar a página). "
        "Compara o custo unitário da última NF de Entrada (`Fatu416`) com o **C1 Atual** e a **Tabela T1** para apontar "
        "esquecimentos fiscais de atualização de custo, margens comprimidas e bonificações."
    )
    if df_entradas.empty:
        st.info("Importe planilhas de Entradas (NF) na Aba 6 para ativar a auditoria fiscal permanente.")
    else:
        af1, af2, af3, af4 = st.columns([1.0, 1.0, 1.0, 1.6])
        with af1:
            janela_aud5_dias = st.number_input(
                "📅 Janela NFs (dias):",
                min_value=1,
                max_value=120,
                value=3,
                step=1,
                key="aud5_janela_nf_dias",
                help="Padrão de 3 dias: analisa a entrada mais recente de cada SKU nos últimos 3 dias.",
            )
        with af2:
            tol_aud5_pct = st.number_input(
                "⚖️ Tolerância Frete/Imp. (%):",
                min_value=0.0,
                max_value=10.0,
                value=1.5,
                step=0.5,
                key="aud5_tol_frete_pct",
                help="Padrão de 1,5%: variações dentro dessa margem entre NF líquida e C1 são consideradas alinhadas.",
            )
        with af3:
            margem_min_aud5 = st.number_input(
                "🏷️ Margem T1 Mínima (%):",
                min_value=0.0,
                max_value=40.0,
                value=5.0,
                step=1.0,
                key="aud5_margem_min_t1",
                help="Alerta quando o custo da NF deixa a margem da Tabela T1 abaixo deste percentual.",
            )
        with af4:
            busca_aud5_txt = st.text_input(
                "🔍 Buscar produto na auditoria fiscal:",
                placeholder="Digite código ou nome...",
                key="aud5_busca_fiscal_txt",
            )

        df_aud5_full, res_aud5 = auditar_fiscal_permanente_nf_c1_t1(
            df_entradas_ref=df_entradas,
            df_custos_ref=df_custos_rel,
            df_estoque_ref=df_estoque,
            janela_dias_nf=int(janela_aud5_dias),
            tolerancia_frete_pct=float(tol_aud5_pct),
            margem_minima_t1_pct=float(margem_min_aud5),
        )
        if df_aud5_full.empty:
            st.info(
                f"Nenhuma entrada com valor financeiro (> R$ 0,00) encontrada nos últimos {int(janela_aud5_dias)} dia(s) "
                f"(a partir de {res_aud5.get('data_corte_br', '-')})."
            )
        else:
            q5_esq = int(res_aud5["qtd_esquecimento_fiscal"])
            q5_mgt1 = int(res_aud5["qtd_margem_t1_baixa"])
            q5_semc1 = int(res_aud5["qtd_sem_c1"])
            q5_bonif = int(res_aud5["qtd_bonificacao"])
            q5_red = int(res_aud5["qtd_reducao_nf"])
            q5_alin = int(res_aud5["qtd_alinhados"])
            qtd_pend_fiscal = len(df_aud5_full[df_aud5_full["_cat"] != "alinhado"])

            fm1, fm2, fm3, fm4 = st.columns(4)
            fm1.metric(
                "🚨 NF Acima do C1 (Fiscal)",
                formatar_num_br(q5_esq),
                "Possível C1 desatualizado" if q5_esq > 0 else "Tudo atualizado",
                delta_color="inverse" if q5_esq > 0 else "normal",
            )
            fm2.metric(
                "⚠️ T1 Comprimido / Sem C1",
                f"{formatar_num_br(q5_mgt1)} / {formatar_num_br(q5_semc1)}",
                f"Margem < {formatar_num_br(margem_min_aud5, 0)}% / C1=0",
            )
            fm3.metric(
                "📉 NF < C1 / 🎁 Bonificação",
                f"{formatar_num_br(q5_red)} / {formatar_num_br(q5_bonif)}",
                "Queda <30% / Queda ≥30%",
            )
            fm4.metric(
                "✔️ Alinhados (NF ≈ C1)",
                formatar_num_br(q5_alin),
                f"De {formatar_num_br(res_aud5['total_itens_nf'])} SKUs (desde {res_aud5['data_corte_br']})",
            )

            fa5_1, fa5_2 = st.columns([2.2, 1.0])
            with fa5_1:
                filtro_cat_aud5 = st.selectbox(
                    "Filtrar diagnóstico fiscal:",
                    options=[
                        f"🔎 Todas as Divergências & Alertas ({qtd_pend_fiscal})",
                        f"🚨 Apenas NF Acima do C1 — Esquecimento Fiscal ({q5_esq})",
                        f"⚠️ Apenas Tabela T1 Comprimida (< {formatar_num_br(margem_min_aud5, 0)}%) ({q5_mgt1})",
                        f"⚪ Apenas Sem C1 Cadastrado ({q5_semc1})",
                        f"📉 Apenas Custo NF Menor que C1 ({q5_red})",
                        f"🎁 Apenas Bonificação / Queda ≥ 30% ({q5_bonif})",
                        f"📋 Todos os Itens com NF no Período ({res_aud5['total_itens_nf']})",
                    ],
                    index=0 if qtd_pend_fiscal > 0 else 6,
                    key="sel_filtro_cat_aud5",
                )
            df_aud5_view = df_aud5_full.copy()
            if filtro_cat_aud5.startswith("🔎 Todas as Divergências"):
                df_aud5_view = df_aud5_view[df_aud5_view["_cat"] != "alinhado"].copy()
            elif filtro_cat_aud5.startswith("🚨 Apenas NF Acima"):
                df_aud5_view = df_aud5_view[df_aud5_view["_cat"] == "esquecimento_fiscal"].copy()
            elif filtro_cat_aud5.startswith("⚠️ Apenas Tabela T1"):
                df_aud5_view = df_aud5_view[df_aud5_view["_t1_comp"] == True].copy()
            elif filtro_cat_aud5.startswith("⚪ Apenas Sem C1"):
                df_aud5_view = df_aud5_view[df_aud5_view["_cat"] == "sem_c1"].copy()
            elif filtro_cat_aud5.startswith("📉 Apenas Custo NF"):
                df_aud5_view = df_aud5_view[df_aud5_view["_cat"] == "reducao_nf"].copy()
            elif filtro_cat_aud5.startswith("🎁 Apenas Bonificação"):
                df_aud5_view = df_aud5_view[df_aud5_view["_cat"] == "bonificacao"].copy()

            if busca_aud5_txt and busca_aud5_txt.strip():
                t_a5 = busca_aud5_txt.lower().strip()
                df_aud5_view = df_aud5_view[
                    df_aud5_view["Código"].str.lower().str.contains(t_a5, na=False, regex=False)
                    | df_aud5_view["Descrição"].str.lower().str.contains(t_a5, na=False, regex=False)
                ].copy()

            df_aud5_exib = df_aud5_view.drop(columns=["_prio", "_abs_var", "_cat", "_t1_comp"]).reset_index(drop=True)
            with fa5_2:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.download_button(
                    label="📥 Baixar Auditoria Fiscal (.xlsx)",
                    data=gerar_excel_relatorio(df_aud5_exib, "Auditoria_Fiscal_NF_C1_T1"),
                    file_name=f"Auditoria_Fiscal_NF_C1_T1_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_auditoria_fiscal_perm_aba5",
                )
            if df_aud5_exib.empty:
                st.success("✅ Nenhuma inconsistência fiscal encontrada para o filtro selecionado!")
            else:
                st.dataframe(
                    estilizar_tabela_br(
                        df_aud5_exib,
                        formatadores={
                            "Qtd. NF": formatar_qtd_br,
                            "Custo Unit. NF (R$)": formatar_moeda_br,
                            "Custo C1 Atual (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Var. NF vs C1 (%)": lambda x: "0,0%" if (pd.isna(x) or abs(float(x)) < 0.05) else formatar_pct_br(x, 1, com_sinal=True),
                            "Tabela T1 Atual (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Margem T1 s/ NF (%)": lambda x: "-" if (pd.isna(x) or float(x) == 0.0) else formatar_pct_br(x, 1),
                            "Saldo Estoque": formatar_qtd_br,
                        },
                        colunas_esquerda=["Descrição", "Diagnóstico Fiscal"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=340,
                )

    st.markdown("---")
    st.markdown("#### 5. Auditoria Permanente de Descontos nas Vendas (Saídas × Tabela T1)")
    st.caption(
        "Recalculada diretamente das tabelas `saidas_diarias` e `custos` gravadas no Supabase (não some ao atualizar a página) "
        "e protegida contra vendas anteriores a reajustes de preço. O padrão normal do balcão é até **2,1%**."
    )
    if df_saidas.empty:
        st.info("Importe planilhas de Saídas / Vendas na Aba 6 para ativar a auditoria permanente de descontos.")
    elif df_custos_rel.empty or "preco_tabela" not in df_custos_rel.columns or float(df_custos_rel["preco_tabela"].fillna(0.0).sum()) <= 0.0:
        st.info("Suba a planilha **Custos & Preços (`C1 + T1`)** na Aba 6 para comparar o Preço Tabela T1 com o Preço Vendido no Balcão.")
    else:
        ad1, ad2, ad3, ad4 = st.columns([1.0, 1.0, 1.3, 1.5])
        with ad1:
            janela_desc_aud5 = st.number_input(
                "📅 Janela Vendas (dias):",
                min_value=1,
                max_value=120,
                value=3,
                step=1,
                key="aud5_desc_janela_dias",
                help="Padrão de 3 dias: analisa as saídas registradas nos últimos 3 dias.",
            )
        with ad2:
            limite_desc_aud5 = st.number_input(
                "🎯 Desconto Mínimo (%):",
                min_value=0.5,
                max_value=50.0,
                value=5.0,
                step=0.5,
                key="aud5_desc_limite_pct",
                help="O padrão do sistema é até 2,1%. Acima de 5,0%, o item aparece na lista de auditoria.",
            )
        dt_sai_s5 = converter_datas_deterministico(df_saidas["data"])
        df_sai_v5 = df_saidas[dt_sai_s5.notna()].copy()
        df_sai_v5["_dt_ts"] = dt_sai_s5[dt_sai_s5.notna()]
        dt_max_sai5 = max(pd.Timestamp(hoje_br()), df_sai_v5["_dt_ts"].max()) if not df_sai_v5.empty else pd.Timestamp(hoje_br())
        dt_corte_sai5 = dt_max_sai5 - pd.Timedelta(days=int(janela_desc_aud5))
        df_sai_win5 = df_sai_v5[df_sai_v5["_dt_ts"] >= dt_corte_sai5].drop(columns=["_dt_ts"]).copy()

        df_desc_perm5 = auditar_descontos_saidas_df(
            df_saidas_ref=df_sai_win5,
            df_custos_ref=df_custos_rel,
            limite_desconto_pct=float(limite_desc_aud5),
            df_entradas_ref=df_entradas,
        )
        if not df_desc_perm5.empty:
            df_desc_perm5["departamento"] = df_desc_perm5["codigo"].map(
                lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
            )
            deptos_desc5 = ["Todos os Grupos"] + sorted(df_desc_perm5["departamento"].unique())
        else:
            deptos_desc5 = ["Todos os Grupos"]

        with ad3:
            depto_desc5_sel = st.selectbox(
                "📂 Filtrar Grupo / Departamento:",
                options=deptos_desc5,
                index=0,
                key="aud5_desc_depto_sel",
            )
        with ad4:
            busca_desc5_txt = st.text_input(
                "🔍 Buscar produto com desconto:",
                placeholder="Digite código ou nome...",
                key="aud5_desc_busca_txt",
            )

        if df_desc_perm5.empty:
            st.success(
                f"✅ Nenhuma venda com desconto acima de **{formatar_num_br(limite_desc_aud5, 1)}%** encontrada nos últimos "
                f"**{int(janela_desc_aud5)} dia(s)** (desde {dt_corte_sai5.strftime('%d/%m/%Y')})."
            )
        else:
            df_desc5_view = df_desc_perm5.copy()
            if depto_desc5_sel != "Todos os Grupos":
                df_desc5_view = df_desc5_view[df_desc5_view["departamento"] == depto_desc5_sel].copy()
            if busca_desc5_txt and busca_desc5_txt.strip():
                td5 = busca_desc5_txt.lower().strip()
                df_desc5_view = df_desc5_view[
                    df_desc5_view["codigo"].str.lower().str.contains(td5, na=False, regex=False)
                    | df_desc5_view["descricao"].str.lower().str.contains(td5, na=False, regex=False)
                ].copy()

            qtd_vendas_desc5 = len(df_desc5_view)
            qtd_skus_desc5 = int(df_desc5_view["codigo"].nunique()) if not df_desc5_view.empty else 0
            tot_desc_rs5 = float(df_desc5_view["desconto_total_rs"].sum()) if not df_desc5_view.empty else 0.0
            tot_cheio_rs5 = float(df_desc5_view["valor_cheio_t1_total"].sum()) if not df_desc5_view.empty else 0.0
            tot_vendido_rs5 = float(df_desc5_view["valor_venda"].sum()) if not df_desc5_view.empty else 0.0
            qtd_mg_baixa5 = (
                int(((df_desc5_view["custo_c1"] > 0.0) & (df_desc5_view["margem_real_pct"] < 10.0)).sum())
                if not df_desc5_view.empty
                else 0
            )

            dm1, dm2, dm3, dm4 = st.columns(4)
            dm1.metric(
                f"🏷️ Vendas > {formatar_num_br(limite_desc_aud5, 1)}% Desc.",
                f"{formatar_num_br(qtd_vendas_desc5)} ({formatar_num_br(qtd_skus_desc5)} SKUs)",
                f"Desde {dt_corte_sai5.strftime('%d/%m/%Y')}",
            )
            dm2.metric(
                "💸 Desconto Total Concedido",
                formatar_moeda_br(tot_desc_rs5),
                f"-{formatar_pct_br((tot_desc_rs5 / max(tot_cheio_rs5, 1.0)) * 100.0, 1)} s/ Tabela T1" if tot_cheio_rs5 > 0 else "-",
                delta_color="inverse" if tot_desc_rs5 > 0 else "normal",
            )
            dm3.metric(
                "💵 Tabela T1 vs. Vendido",
                formatar_moeda_br(tot_vendido_rs5),
                f"Valor Cheio T1: {formatar_moeda_br(tot_cheio_rs5)}",
            )
            dm4.metric(
                "⚠️ Vendas c/ Margem < 10%",
                formatar_num_br(qtd_mg_baixa5),
                "Abaixo de 10% s/ C1" if qtd_mg_baixa5 > 0 else "Margem preservada",
                delta_color="inverse" if qtd_mg_baixa5 > 0 else "normal",
            )

            df_desc5_exib = df_desc5_view[
                [
                    "data",
                    "codigo",
                    "descricao",
                    "departamento",
                    "qtd_saida",
                    "preco_tabela_t1",
                    "preco_vendido_un",
                    "desconto_pct",
                    "desconto_total_rs",
                    "custo_c1",
                    "margem_t1_pct",
                    "margem_real_pct",
                    "status_desconto",
                ]
            ].rename(
                columns={
                    "data": "Data",
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "departamento": "Grupo",
                    "qtd_saida": "Qtd.",
                    "preco_tabela_t1": "Preço Tabela T1 (R$)",
                    "preco_vendido_un": "Preço Vendido Balcão (R$)",
                    "desconto_pct": "Desconto (%)",
                    "desconto_total_rs": "Desconto Total (R$)",
                    "custo_c1": "Custo C1 (R$)",
                    "margem_t1_pct": "Margem T1 (%)",
                    "margem_real_pct": "Margem Real (%)",
                    "status_desconto": "Status Desconto",
                }
            )
            st.download_button(
                label="📥 Baixar Auditoria Permanente de Descontos (.xlsx)",
                data=gerar_excel_relatorio(df_desc5_exib, "Descontos_Vendas_T1"),
                file_name=f"Auditoria_Descontos_Vendas_T1_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_auditoria_desc_perm_aba5",
            )
            if df_desc5_exib.empty:
                st.info("Nenhum item corresponde aos filtros de grupo/busca selecionados.")
            else:
                st.dataframe(
                    estilizar_tabela_br(
                        df_desc5_exib,
                        formatadores={
                            "Qtd.": formatar_qtd_br,
                            "Preço Tabela T1 (R$)": formatar_moeda_br,
                            "Preço Vendido Balcão (R$)": formatar_moeda_br,
                            "Desconto (%)": lambda x: f"-{formatar_pct_br(x, 1)}",
                            "Desconto Total (R$)": formatar_moeda_br,
                            "Custo C1 (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                            "Margem T1 (%)": lambda x: formatar_pct_br(x, 1),
                            "Margem Real (%)": lambda x: formatar_pct_br(x, 1),
                        },
                        colunas_esquerda=["Descrição", "Grupo", "Status Desconto"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )
