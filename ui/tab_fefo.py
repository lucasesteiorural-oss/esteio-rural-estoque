"""
ui/tab_fefo.py — Aba 3: Radar FEFO, cálculo de sobra projetada e
simulador/gerador de campanhas WhatsApp.
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
    gerar_excel_relatorio,
)
from analytics import (
    calcular_motor_giro_sazonal,
    calcular_plano_promocional_fefo,
    gerar_textos_campanha_promocional_fefo,
)


def render_tab_fefo(ctx: dict) -> None:
    """Renderiza a Aba 3 — Radar FEFO & Promoções IA."""
    df_estoque = ctx["df_estoque"]
    df_historico = ctx["df_historico"]
    df_entradas = ctx["df_entradas"]
    df_saidas = ctx["df_saidas"]
    df_custos_rel = ctx["df_custos_rel"]
    df_base_vendas_rel = ctx["df_base_vendas_rel"]
    dias_base_atual = ctx["dias_base_atual"]
    grupos_sku_custom = ctx["grupos_sku_custom"]
    mp_custom_map = ctx["mp_custom_map"]

    st.markdown("### ⏳ Radar de Validades (FEFO) & Consultor Inteligente de Promoções")
    st.caption(
        "Cruza a validade de cada lote com o **Giro Diário Real** do produto para descobrir quais lotes vão escoar sozinhos "
        "e quais deixarão **sobra no vencimento**, sugerindo descontos progressivos protegidos contra impostos (ICMS, PIS/COFINS, ST) "
        "e gerando o texto comercial pronto para WhatsApp e para a equipe de vendas."
    )
    if df_estoque.empty:
        st.info("Importe a Planilha de Estoque na Aba 6 (Importação & Backup) para monitorar os lotes e validades.")
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
                options=[30, 60, 90, 120, 180, 365],
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
            grupos_sku_custom=grupos_sku_custom,
            mp_custom_map=mp_custom_map,
        )

        df_fefo = calcular_plano_promocional_fefo(
            df_estoque_ref=df_estoque,
            df_custos_ref=df_custos_rel,
            df_giro_ref=df_giro_fefo_base,
            aliquota_impostos_pct=float(aliquota_imp_fefo),
            margem_referencia_pct=float(margem_ref_fefo),
            df_saidas_ref=df_saidas,
            grupos_sku_custom=grupos_sku_custom,
            mp_custom_map=mp_custom_map,
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
