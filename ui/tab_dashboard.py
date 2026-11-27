"""
ui/tab_dashboard.py — Aba 1: Dashboard Executivo (Power BI)
(Bento KPIs, Saúde do Capital, Matriz 2D, Fluxo Diário e Resultado Comercial/Impostos).
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
    identificar_departamento_sku,
    identificar_produto_mp,
)
from analytics import (
    calcular_motor_giro_sazonal,
    calcular_plano_promocional_fefo,
    resolver_custo_e_t1_temporal_saidas,
    auditar_descontos_saidas_df,
)
from ui.styles import (
    _renderizar_dataframe_selecionavel,
    _extrair_selecao_altair,
)


def render_tab_dashboard(ctx: dict) -> None:
    """Renderiza a Aba 1 — Dashboard Executivo (Power BI)."""
    df_estoque = ctx["df_estoque"]
    df_historico = ctx["df_historico"]
    df_entradas = ctx["df_entradas"]
    df_saidas = ctx["df_saidas"]
    df_custos_rel = ctx["df_custos_rel"]
    df_base_vendas_rel = ctx["df_base_vendas_rel"]
    dias_base_atual = ctx["dias_base_atual"]
    grupos_pref_custom = ctx["grupos_pref_custom"]
    grupos_sku_custom = ctx["grupos_sku_custom"]
    mp_custom_map = ctx["mp_custom_map"]
    codigos_em_transito = ctx["codigos_em_transito"]

    st.markdown("### 📊 Torre de Controle Executiva — Inteligência de Estoque & Capital (Power BI)")
    st.caption(
        "Visão gerencial consolidada para tomada de decisão: Saúde do Capital Imobilizado, Matriz Cruzada 2D (Estoque × Giro), "
        "Nível de Serviço dos Campeões de Venda, Risco FEFO Dinâmico e Fluxo Diário de Compras vs. Saídas."
    )
    if df_estoque.empty and df_base_vendas_rel.empty:
        st.info("Importe as planilhas de Estoque e Custos na Aba 6 (Importação & Backup) para ativar o Dashboard Executivo.")
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
        incluir_zerados_inativados_bi = st.checkbox(
            "⚪ Incluir Saldo = 0 c/ giro e produtos inativados no Siagri",
            value=False,
            key="chk_incluir_zerados_inativados_bi",
            help="Desmarcado por padrão (igual à Aba 2): exibe apenas produtos ativos com saldo positivo na prateleira, evitando que itens inativados ou zerados poluam o Top Ruptura e a Disponibilidade Líderes.",
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
            grupos_sku_custom=grupos_sku_custom,
            mp_custom_map=mp_custom_map,
        )
        df_bi = df_bi_base.copy()
        if not df_custos_rel.empty:
            df_bi = df_bi.merge(df_custos_rel[["codigo", "custo_unitario"]], on="codigo", how="left")
            df_bi["custo_unitario"] = df_bi["custo_unitario"].fillna(0.0)
        else:
            df_bi["custo_unitario"] = 0.0

        cods_ativos_no_estoque = (
            set(df_estoque["codigo"].unique())
            if (df_estoque is not None and not df_estoque.empty and "codigo" in df_estoque.columns)
            else set()
        )
        df_bi["ativo_no_erp"] = df_bi["codigo"].isin(cods_ativos_no_estoque)
        df_bi["departamento"] = df_bi["codigo"].map(
            lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
        )
        df_bi["eh_mp"] = [
            identificar_produto_mp(cod, desc, grupos_sku_custom, mp_custom_map)
            for cod, desc in zip(df_bi["codigo"], df_bi["descricao"])
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

        # Preserva todos os códigos do escopo para auditoria financeira histórica (Seção 5)
        cods_escopo_fin_bi = set(df_bi["codigo"].unique())

        # Para os indicadores de ruptura e estoque ativo (Seções 1 a 4), respeita o filtro de Saldo = 0 / Inativados
        if not incluir_zerados_inativados_bi:
            df_bi = df_bi[df_bi["ativo_no_erp"] & (df_bi["saldo_atual"] > 0)].copy()

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
        fator_saz_bi = (
            pd.to_numeric(df_bi["fator_sazonal"], errors="coerce").fillna(1.0)
            if "fator_sazonal" in df_bi.columns
            else 1.0
        )
        df_bi["giro_dia"] = (df_bi["giro_ponderado"] * fator_saz_bi).clip(lower=0.0)
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

        meta_ref_longa_bi = max(int(meta_cobertura_bi), int(lead_bi))
        teto_cobertura_longa_bi = max(180, meta_ref_longa_bi + 60)

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
            if int(meta_cobertura_bi) > int(lead_bi) and aut <= float(meta_cobertura_bi):
                return f"2. Saudável ({int(lead_bi)+1} a {int(meta_cobertura_bi)}d)"
            if aut <= float(teto_cobertura_longa_bi):
                return f"3. Cobertura Longa ({meta_ref_longa_bi+1} a {teto_cobertura_longa_bi}d)"
            return f"4. Excesso (> {teto_cobertura_longa_bi}d)"

        df_bi["faixa_saude"] = df_bi.apply(_classificar_faixa_saude_bi, axis=1)
        df_bi["estoque_alvo_val"] = df_bi["cmv_diario"] * float(meta_cobertura_bi)
        df_bi["capital_liberavel"] = [
            max(0.0, float(v) - float(alv)) if float(g) > 0 else float(v)
            for v, alv, g in zip(df_bi["valor_estoque"], df_bi["estoque_alvo_val"], df_bi["giro_dia"])
        ]

        # Cálculo de Risco FEFO Dinâmico (reutilizando o motor oficial `calcular_plano_promocional_fefo`)
        cods_escopo_bi = set(df_bi["codigo"].unique())
        df_estoque_escopo_bi = df_estoque[df_estoque["codigo"].isin(cods_escopo_bi)].copy()
        df_fefo_bi = calcular_plano_promocional_fefo(
            df_estoque_ref=df_estoque_escopo_bi,
            df_custos_ref=df_custos_rel,
            df_giro_ref=df_bi_base,
            df_saidas_ref=df_saidas,
            grupos_sku_custom=grupos_sku_custom,
            mp_custom_map=mp_custom_map,
        )
        vlr_fefo_90d = 0.0
        vlr_sobra_fefo_90d = 0.0
        if not df_fefo_bi.empty:
            lotes_ate_90 = df_fefo_bi[
                df_fefo_bi["dias_para_vencer"].notna() & (df_fefo_bi["dias_para_vencer"] <= 90)
            ]
            if not lotes_ate_90.empty:
                vlr_fefo_90d = float(lotes_ate_90["valor_em_risco"].sum())
                vlr_sobra_fefo_90d = float(lotes_ate_90["capital_sobra"].sum())

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
                    altura_saude = max(310, len(res_saude_bi) * 52)
                    chart_saude = (
                        alt.Chart(res_saude_bi)
                        .mark_bar(cornerRadiusEnd=6, height=22)
                        .encode(
                            x=alt.X("Capital:Q", title="Capital Imobilizado (R$)", axis=alt.Axis(format="~s")),
                            y=alt.Y(
                                "faixa_saude:N",
                                sort=list(res_saude_bi["faixa_saude"]),
                                title=None,
                                axis=alt.Axis(labelLimit=280, labelOverlap=False, labelPadding=8),
                            ),
                            color=alt.Color(
                                "faixa_saude:N",
                                legend=None,
                                scale=alt.Scale(range=["#ef4444", "#10b981", "#38bdf8", "#f59e0b", "#8b5cf6", "#64748b"]),
                            ),
                            opacity=alt.condition(sel_bar_saude, alt.value(1.0), alt.value(0.55)),
                            tooltip=[
                                alt.Tooltip("faixa_saude:N", title="Faixa de Saúde"),
                                alt.Tooltip("SKUs:Q", title="SKUs", format=",d"),
                                alt.Tooltip("Capital:Q", title="Capital (R$)", format=",.2f"),
                                alt.Tooltip("CMV_Mensal:Q", title="CMV Mensal (R$)", format=",.2f"),
                                alt.Tooltip("% Capital:Q", title="% do Capital", format=".1f"),
                            ],
                        )
                        .add_params(sel_bar_saude)
                        .properties(height=altura_saude)
                    )
                    ev_chart_s = st.altair_chart(chart_saude, use_container_width=True, on_select="rerun", key="alt_chart_saude_bi")
                    faixa_saude_clicada = _extrair_selecao_altair(ev_chart_s, "faixa_saude")
                except Exception:
                    st.bar_chart(
                        res_saude_bi.set_index("faixa_saude")[["Capital"]],
                        use_container_width=True,
                        height=310,
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
            st.caption("👆 **Top 8 Departamentos** (clique na barra ou na tabela abaixo para abrir os produtos do grupo)")
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
                    df_dep_top8 = res_depto_bi.head(8).copy()
                    ordem_deptos = list(df_dep_top8["departamento"])
                    linhas_dep_melt = []
                    for _, r_dp in df_dep_top8.iterrows():
                        linhas_dep_melt.append(
                            {
                                "departamento": r_dp["departamento"],
                                "Indicador": "Capital Atual (R$)",
                                "Valor": float(r_dp["Capital"]),
                                "SKUs": int(r_dp["SKUs"]),
                                "Capital_Ref": float(r_dp["Capital"]),
                                "CMV_Ref": float(r_dp["CMV_Mensal"]),
                            }
                        )
                        linhas_dep_melt.append(
                            {
                                "departamento": r_dp["departamento"],
                                "Indicador": "Giro CMV/Mês (R$)",
                                "Valor": float(r_dp["CMV_Mensal"]),
                                "SKUs": int(r_dp["SKUs"]),
                                "Capital_Ref": float(r_dp["Capital"]),
                                "CMV_Ref": float(r_dp["CMV_Mensal"]),
                            }
                        )
                    df_dep_chart = pd.DataFrame(linhas_dep_melt)
                    altura_dep = max(350, len(ordem_deptos) * 44)
                    sel_bar_dep = alt.selection_point(fields=["departamento"], name="sel_depto")
                    chart_dep = (
                        alt.Chart(df_dep_chart)
                        .mark_bar(cornerRadiusEnd=5, height=13)
                        .encode(
                            x=alt.X("Valor:Q", title="Valor (R$)", axis=alt.Axis(format="~s")),
                            y=alt.Y(
                                "departamento:N",
                                sort=ordem_deptos,
                                title=None,
                                axis=alt.Axis(labelLimit=260, labelOverlap=False, labelPadding=8),
                            ),
                            yOffset=alt.YOffset(
                                "Indicador:N",
                                sort=["Capital Atual (R$)", "Giro CMV/Mês (R$)"],
                            ),
                            color=alt.Color(
                                "Indicador:N",
                                scale=alt.Scale(
                                    domain=["Capital Atual (R$)", "Giro CMV/Mês (R$)"],
                                    range=["#38bdf8", "#10b981"],
                                ),
                                legend=alt.Legend(orient="top", title=None, labelFontSize=12),
                            ),
                            opacity=alt.condition(sel_bar_dep, alt.value(1.0), alt.value(0.55)),
                            tooltip=[
                                alt.Tooltip("departamento:N", title="Grupo / Departamento"),
                                alt.Tooltip("SKUs:Q", title="SKUs c/ Saldo", format=",d"),
                                alt.Tooltip("Capital_Ref:Q", title="Capital Atual (R$)", format=",.2f"),
                                alt.Tooltip("CMV_Ref:Q", title="Giro CMV/Mês (R$)", format=",.2f"),
                            ],
                        )
                        .add_params(sel_bar_dep)
                        .properties(height=altura_dep)
                    )
                    ev_chart_d = st.altair_chart(chart_dep, use_container_width=True, on_select="rerun", key="alt_chart_depto_bi")
                    depto_clicado = _extrair_selecao_altair(ev_chart_d, "departamento")
                except Exception:
                    st.bar_chart(
                        res_depto_bi.head(8).set_index("departamento")[["Capital", "CMV_Mensal"]],
                        use_container_width=True,
                        height=350,
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
        mapa_t1_bi = (
            dict(zip(df_custos_rel["codigo"], df_custos_rel["preco_tabela"].fillna(0.0)))
            if (not df_custos_rel.empty and "preco_tabela" in df_custos_rel.columns)
            else {}
        )
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
                st.info("Importe planilhas de Entradas e Saídas na Aba 6 para visualizar o fluxo financeiro diário.")

        st.markdown("---")
        st.markdown("#### 5. Resultado Comercial Real: Margem Média por Grupo, Visão Mensal / Anual & Impostos")
        st.caption(
            "Cruza o **Valor Total da Proposta** (4ª coluna da planilha de Saídas/Vendas) com o **Custo Unitário C1** para calcular a "
            "**Margem Média e o Markup** por **Grupo/Departamento**, **Mês a Mês** ou **Consolidado Anual**, com opção de ligar ou desligar impostos."
        )

        df_sai_escopo = (
            df_saidas[df_saidas["codigo"].isin(cods_escopo_fin_bi)].copy()
            if (df_saidas is not None and not df_saidas.empty)
            else pd.DataFrame()
        )
        df_ent_escopo = (
            df_entradas[df_entradas["codigo"].isin(cods_escopo_fin_bi)].copy()
            if (df_entradas is not None and not df_entradas.empty)
            else pd.DataFrame()
        )

        if df_sai_escopo.empty and df_ent_escopo.empty:
            st.info(
                "💡 Importe suas planilhas de **Saídas / Vendas Diárias** (com a 4ª coluna `Valor Total da Proposta`) na Aba 6 "
                "para destravar a auditoria de Faturamento Bruto, Margem Média por Grupo e o Comparativo Mensal / Anual!"
            )
        else:
            if not df_sai_escopo.empty:
                if "valor_venda" not in df_sai_escopo.columns:
                    df_sai_escopo["valor_venda"] = 0.0
                df_sai_escopo["departamento"] = df_sai_escopo["codigo"].map(
                    lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
                )
                df_sai_escopo = resolver_custo_e_t1_temporal_saidas(
                    df_saidas_ref=df_sai_escopo,
                    df_custos_ref=df_custos_rel,
                    df_entradas_ref=df_entradas,
                )
                df_sai_escopo["custo_u"] = df_sai_escopo["custo_u_efetivo"].fillna(0.0)
                df_sai_escopo["preco_t1_u"] = df_sai_escopo["t1_efetivo"].fillna(0.0)
                df_sai_escopo["cmv_total"] = df_sai_escopo["qtd_saida"] * df_sai_escopo["custo_u"]
                df_sai_escopo["fat_bruto"] = df_sai_escopo["valor_venda"].fillna(0.0)
                df_sai_escopo["fat_cheio_t1"] = [
                    (float(q) * float(t1)) if float(t1) > 0.0 else float(fb)
                    for q, t1, fb in zip(df_sai_escopo["qtd_saida"], df_sai_escopo["preco_t1_u"], df_sai_escopo["fat_bruto"])
                ]
                df_sai_escopo["mes_ano"] = df_sai_escopo["data"].astype(str).str.slice(0, 7)
                df_sai_escopo["ano"] = df_sai_escopo["data"].astype(str).str.slice(0, 4)
            else:
                df_sai_escopo = pd.DataFrame(
                    columns=[
                        "codigo", "descricao", "departamento", "qtd_saida", "valor_venda", "data",
                        "custo_u", "preco_t1_u", "pre_reajuste", "tem_custo_historico", "motivo_temporal",
                        "cmv_total", "fat_bruto", "mes_ano", "ano"
                    ]
                )

            if not df_ent_escopo.empty:
                df_ent_escopo["departamento"] = df_ent_escopo["codigo"].map(
                    lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
                )
                df_ent_escopo["custo_u"] = df_ent_escopo["codigo"].map(mapa_custo_bi).fillna(0.0)
                custo_est_nf = df_ent_escopo["qtd_entrada"] * df_ent_escopo["custo_u"]
                if "valor_entrada" in df_ent_escopo.columns:
                    val_nf_s = df_ent_escopo["valor_entrada"].fillna(0.0)
                    df_ent_escopo["compras_nf_custo"] = val_nf_s.where(val_nf_s > 0.0, custo_est_nf)
                else:
                    df_ent_escopo["compras_nf_custo"] = custo_est_nf
                df_ent_escopo["mes_ano"] = df_ent_escopo["data"].astype(str).str.slice(0, 7)
                df_ent_escopo["ano"] = df_ent_escopo["data"].astype(str).str.slice(0, 4)
            else:
                df_ent_escopo = pd.DataFrame(columns=["codigo", "descricao", "departamento", "qtd_entrada", "data", "custo_u", "compras_nf_custo", "mes_ano", "ano"])

            deptos_disponiveis_margem = sorted(
                list(
                    (set(df_sai_escopo["departamento"].unique()) if not df_sai_escopo.empty else set())
                    | (set(df_ent_escopo["departamento"].unique()) if not df_ent_escopo.empty else set())
                )
            )
            meses_disponiveis_margem = sorted(
                [
                    m for m in (
                        (set(df_sai_escopo["mes_ano"].unique()) if not df_sai_escopo.empty else set())
                        | (set(df_ent_escopo["mes_ano"].unique()) if not df_ent_escopo.empty else set())
                    )
                    if str(m).strip() and len(str(m).strip()) >= 7
                ],
                reverse=True,
            )
            anos_disponiveis_margem = sorted(
                [
                    a for a in (
                        (set(df_sai_escopo["ano"].unique()) if not df_sai_escopo.empty else set())
                        | (set(df_ent_escopo["ano"].unique()) if not df_ent_escopo.empty else set())
                    )
                    if str(a).strip() and len(str(a).strip()) == 4
                ],
                reverse=True,
            )

            mg_f1, mg_f2, mg_f3, mg_f4 = st.columns([1.8, 1.2, 1.0, 1.0])
            with mg_f1:
                deptos_sel_margem = st.multiselect(
                    "📂 Filtrar Grupo / Departamento (ex: Medicamentos):",
                    options=deptos_disponiveis_margem,
                    default=[],
                    key="bi_deptos_margem_sec5",
                    help="Selecione um ou mais grupos (ex: 50 - Veterinária & Reprodução) para apurar a margem média exclusiva daquele grupo. Deixe vazio para ver todos.",
                )
            with mg_f2:
                visao_tempo_margem = st.selectbox(
                    "📅 Período de Apuração:",
                    options=[
                        "📅 Todos os Meses (Evolução Mensal)",
                        "🗓️ Mês Específico",
                        "📆 Consolidado Anual",
                    ],
                    index=0,
                    key="bi_visao_tempo_margem",
                )
            with mg_f3:
                if visao_tempo_margem == "🗓️ Mês Específico":
                    mes_escolhido_margem = st.selectbox(
                        "Selecione o Mês:",
                        options=meses_disponiveis_margem if meses_disponiveis_margem else ["-"],
                        key="bi_mes_especifico_margem",
                    )
                    ano_escolhido_margem = None
                elif visao_tempo_margem == "📆 Consolidado Anual":
                    ano_escolhido_margem = st.selectbox(
                        "Selecione o Ano:",
                        options=["Todos os Anos"] + anos_disponiveis_margem,
                        key="bi_ano_especifico_margem",
                    )
                    mes_escolhido_margem = None
                else:
                    mes_escolhido_margem = None
                    ano_escolhido_margem = None
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.caption(f"🗓️ {len(meses_disponiveis_margem)} mês(es) na base")
            with mg_f4:
                aplicar_imposto_margem = st.checkbox(
                    "🏛️ Descontar Impostos",
                    value=False,
                    key="bi_chk_aplicar_imposto",
                    help="Desmarcado: calcula a margem comercial pura (Faturamento - CMV). Marcado: desconta a alíquota % informada abaixo.",
                )
                aliq_imp_dash = st.number_input(
                    "Alíquota (%):",
                    min_value=0.0,
                    max_value=35.0,
                    value=6.0,
                    step=0.5,
                    disabled=not aplicar_imposto_margem,
                    key="bi_aliq_imposto_vendas",
                )

            aliq_imp_efetiva = float(aliq_imp_dash) if aplicar_imposto_margem else 0.0

            # Aplica os filtros da Seção 5 (Grupo + Período)
            df_sai_sec5 = df_sai_escopo.copy()
            df_ent_sec5 = df_ent_escopo.copy()
            if deptos_sel_margem:
                if not df_sai_sec5.empty:
                    df_sai_sec5 = df_sai_sec5[df_sai_sec5["departamento"].isin(deptos_sel_margem)].copy()
                if not df_ent_sec5.empty:
                    df_ent_sec5 = df_ent_sec5[df_ent_sec5["departamento"].isin(deptos_sel_margem)].copy()

            if visao_tempo_margem == "🗓️ Mês Específico" and mes_escolhido_margem and mes_escolhido_margem != "-":
                if not df_sai_sec5.empty:
                    df_sai_sec5 = df_sai_sec5[df_sai_sec5["mes_ano"] == mes_escolhido_margem].copy()
                if not df_ent_sec5.empty:
                    df_ent_sec5 = df_ent_sec5[df_ent_sec5["mes_ano"] == mes_escolhido_margem].copy()
            elif visao_tempo_margem == "📆 Consolidado Anual" and ano_escolhido_margem and ano_escolhido_margem != "Todos os Anos":
                if not df_sai_sec5.empty:
                    df_sai_sec5 = df_sai_sec5[df_sai_sec5["ano"] == ano_escolhido_margem].copy()
                if not df_ent_sec5.empty:
                    df_ent_sec5 = df_ent_sec5[df_ent_sec5["ano"] == ano_escolhido_margem].copy()

            if not df_sai_sec5.empty:
                tem_c_mask = df_sai_sec5["custo_u"] > 0.0
                df_sai_sec5["imposto_est"] = df_sai_sec5["fat_bruto"] * (aliq_imp_efetiva / 100.0)
                df_sai_sec5["fat_com_custo"] = df_sai_sec5["fat_bruto"].where(tem_c_mask, 0.0)
                df_sai_sec5["imposto_com_custo"] = df_sai_sec5["imposto_est"].where(tem_c_mask, 0.0)
                df_sai_sec5["lucro_bruto"] = (df_sai_sec5["fat_bruto"] - df_sai_sec5["cmv_total"]).where(tem_c_mask, 0.0)
                df_sai_sec5["lucro_liquido"] = (
                    df_sai_sec5["fat_bruto"] - df_sai_sec5["imposto_est"] - df_sai_sec5["cmv_total"]
                ).where(tem_c_mask, 0.0)
            else:
                df_sai_sec5["imposto_est"] = pd.Series(dtype=float)
                df_sai_sec5["fat_com_custo"] = pd.Series(dtype=float)
                df_sai_sec5["imposto_com_custo"] = pd.Series(dtype=float)
                df_sai_sec5["lucro_bruto"] = pd.Series(dtype=float)
                df_sai_sec5["lucro_liquido"] = pd.Series(dtype=float)

            df_sai_com_fat = df_sai_sec5[df_sai_sec5["fat_bruto"] > 0].copy() if not df_sai_sec5.empty else pd.DataFrame()
            df_sai_base_margem = (
                df_sai_com_fat[df_sai_com_fat["custo_u"] > 0].copy()
                if not df_sai_com_fat.empty
                else pd.DataFrame()
            )
            fat_total_periodo = float(df_sai_com_fat["fat_bruto"].sum()) if not df_sai_com_fat.empty else 0.0
            fat_base_margem = float(df_sai_base_margem["fat_bruto"].sum()) if not df_sai_base_margem.empty else 0.0
            fat_sem_custo_excl = max(0.0, fat_total_periodo - fat_base_margem)
            cmv_das_vendas_fat = float(df_sai_base_margem["cmv_total"].sum()) if not df_sai_base_margem.empty else 0.0
            imp_total_periodo = float(df_sai_com_fat["imposto_est"].sum()) if not df_sai_com_fat.empty else 0.0
            imp_base_margem = float(df_sai_base_margem["imposto_est"].sum()) if not df_sai_base_margem.empty else 0.0
            lucro_bruto_periodo = fat_base_margem - cmv_das_vendas_fat
            lucro_liq_periodo = fat_base_margem - imp_base_margem - cmv_das_vendas_fat
            margem_bruta_pct = ((lucro_bruto_periodo / fat_base_margem) * 100.0) if fat_base_margem > 0 else 0.0
            margem_liq_pct = ((lucro_liq_periodo / fat_base_margem) * 100.0) if fat_base_margem > 0 else 0.0
            markup_medio_pct = (((fat_base_margem / cmv_das_vendas_fat) - 1.0) * 100.0) if cmv_das_vendas_fat > 0 else 0.0

            rotulo_escopo_mg = ", ".join(deptos_sel_margem) if deptos_sel_margem else "Todos os Grupos"
            rotulo_tempo_mg = (
                f"Mês {mes_escolhido_margem}"
                if (visao_tempo_margem == "🗓️ Mês Específico" and mes_escolhido_margem)
                else (
                    f"Ano {ano_escolhido_margem}"
                    if (visao_tempo_margem == "📆 Consolidado Anual" and ano_escolhido_margem)
                    else "Período Completo"
                )
            )
            if fat_total_periodo > 0:
                txt_imp_res = (
                    f"Impostos ({formatar_num_br(aliq_imp_efetiva, 1)}%): **{formatar_moeda_br(imp_total_periodo)}**"
                    if aplicar_imposto_margem
                    else "Impostos: **Desativado (0%)**"
                )
                nota_sem_custo_banner = (
                    f"  |  ℹ️ Base c/ custo: **{formatar_moeda_br(fat_base_margem)}** "
                    f"({formatar_moeda_br(fat_sem_custo_excl)} s/ custo excluído da margem)"
                    if fat_sem_custo_excl > 0.01
                    else ""
                )
                st.info(
                    f"📈 **Margem Média ({rotulo_escopo_mg} | {rotulo_tempo_mg}):** "
                    f"Faturamento: **{formatar_moeda_br(fat_total_periodo)}**  |  "
                    f"CMV (C1): **{formatar_moeda_br(cmv_das_vendas_fat)}**  |  "
                    f"{txt_imp_res}  |  "
                    f"Margem Média: **{formatar_pct_br(margem_liq_pct, 1)}** (Markup: +{formatar_num_br(markup_medio_pct, 1)}%)"
                    f"{nota_sem_custo_banner}"
                )
            else:
                st.warning(
                    "ℹ️ As saídas registradas neste filtro ainda não possuem a 4ª coluna (`Valor Total da Proposta` > R$ 0,00). "
                    "Ao subir planilhas como `Saida venda 12-11-2026.xlsx` na Aba 6, o faturamento e as margens aparecerão aqui automaticamente!"
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
                f"🏛️ Impostos ({formatar_num_br(aliq_imp_efetiva, 1)}%)",
                formatar_moeda_br(imp_total_periodo),
                "Ativado" if aplicar_imposto_margem else "Desativado (0%)",
            )
            rm5.metric(
                "💎 Lucro Líquido Real",
                formatar_moeda_br(lucro_liq_periodo),
                f"Margem Média: {formatar_pct_br(margem_liq_pct, 1)}",
                delta_color="normal" if lucro_liq_periodo >= 0 else "inverse",
            )

            tab_mom, tab_grp_mg, tab_sku_lucro, tab_desc_t1, tab_sku_alerta = st.tabs(
                [
                    "📆 Consolidado Anual (Compras × CMV × Faturamento × Lucro)" if visao_tempo_margem == "📆 Consolidado Anual" else "📅 Comparativo Mês a Mês (Compras NF × CMV × Faturamento × Lucro)",
                    "📊 Margem Média por Grupo / Departamento",
                    "🏆 Top Produtos Campeões de Lucro Líquido",
                    "🏷️ Descontos > 5% vs. Tabela T1",
                    "⚠️ Auditoria de Margem Baixa ou Negativa",
                ]
            )

            with tab_mom:
                col_chave_tempo = "ano" if visao_tempo_margem == "📆 Consolidado Anual" else "mes_ano"
                rotulo_col_tempo = "Ano" if visao_tempo_margem == "📆 Consolidado Anual" else "Mês/Ano"
                tam_min_chave = 4 if visao_tempo_margem == "📆 Consolidado Anual" else 7

                periodos_todos = sorted(
                    list(
                        (set(df_sai_sec5[col_chave_tempo].unique()) if not df_sai_sec5.empty else set())
                        | (set(df_ent_sec5[col_chave_tempo].unique()) if not df_ent_sec5.empty else set())
                    )
                )
                periodos_todos = [p for p in periodos_todos if str(p).strip() and len(str(p).strip()) >= tam_min_chave]
                if not periodos_todos:
                    st.info("Ainda não há períodos registrados para o filtro selecionado.")
                else:
                    df_mom = pd.DataFrame({col_chave_tempo: periodos_todos})
                    if not df_ent_sec5.empty:
                        grp_e_m = df_ent_sec5.groupby(col_chave_tempo, as_index=False).agg(
                            compras_nf=("compras_nf_custo", "sum"),
                            qtd_ent=("qtd_entrada", "sum"),
                        )
                        df_mom = df_mom.merge(grp_e_m, on=col_chave_tempo, how="left")
                    else:
                        df_mom["compras_nf"] = 0.0
                        df_mom["qtd_ent"] = 0.0

                    if not df_sai_sec5.empty:
                        grp_s_m = df_sai_sec5.groupby(col_chave_tempo, as_index=False).agg(
                            dias_mov=("data", "nunique"),
                            qtd_sai=("qtd_saida", "sum"),
                            cmv_sai=("cmv_total", "sum"),
                            faturamento=("fat_bruto", "sum"),
                            fat_base_mg=("fat_com_custo", "sum"),
                            impostos=("imposto_est", "sum"),
                            lucro_bruto=("lucro_bruto", "sum"),
                            lucro_liq=("lucro_liquido", "sum"),
                        )
                        df_mom = df_mom.merge(grp_s_m, on=col_chave_tempo, how="left")
                    else:
                        for c_z in ["dias_mov", "qtd_sai", "cmv_sai", "faturamento", "fat_base_mg", "impostos", "lucro_bruto", "lucro_liq"]:
                            df_mom[c_z] = 0.0

                    df_mom = df_mom.fillna(0.0).sort_values(col_chave_tempo).reset_index(drop=True)
                    df_mom["margem_bruta_pct"] = [
                        ((lb / fb) * 100.0) if fb > 0 else 0.0
                        for lb, fb in zip(df_mom["lucro_bruto"], df_mom["fat_base_mg"])
                    ]
                    df_mom["margem_liq_pct"] = [
                        ((ll / fb) * 100.0) if fb > 0 else 0.0
                        for ll, fb in zip(df_mom["lucro_liq"], df_mom["fat_base_mg"])
                    ]
                    df_mom["markup_pct"] = [
                        (((fb / cmv) - 1.0) * 100.0) if (fb > 0 and cmv > 0) else 0.0
                        for fb, cmv in zip(df_mom["fat_base_mg"], df_mom["cmv_sai"])
                    ]
                    base_cresc = df_mom["faturamento"] if float(df_mom["faturamento"].sum()) > 0 else df_mom["cmv_sai"]
                    cresc_vals = [0.0]
                    for idx_m in range(1, len(df_mom)):
                        ant_v = float(base_cresc.iloc[idx_m - 1])
                        at_v = float(base_cresc.iloc[idx_m])
                        cresc_vals.append((((at_v - ant_v) / ant_v) * 100.0) if ant_v > 0 else 0.0)
                    df_mom["cresc_mom_pct"] = cresc_vals

                    mapa_base_periodo = dict(zip(df_mom[col_chave_tempo].astype(str), base_cresc.astype(float)))
                    yoy_vals = []
                    for idx_m, r_m in df_mom.iterrows():
                        ch_p = str(r_m[col_chave_tempo]).strip()
                        at_v = float(base_cresc.iloc[idx_m])
                        if len(ch_p) >= 7 and ch_p[:4].isdigit():
                            ch_ano_ant = f"{int(ch_p[:4]) - 1}{ch_p[4:]}"
                            ant_yoy = float(mapa_base_periodo.get(ch_ano_ant, 0.0))
                            yoy_vals.append((((at_v - ant_yoy) / ant_yoy) * 100.0) if ant_yoy > 0 else 0.0)
                        else:
                            yoy_vals.append(0.0)
                    df_mom["cresc_yoy_pct"] = yoy_vals

                    cols_mom_final = [
                        rotulo_col_tempo,
                        "Dias c/ Saída",
                        "Compras NF a Custo (R$)",
                        "CMV das Saídas (R$)",
                        "Faturamento Bruto (R$)",
                        "Impostos Est. (R$)",
                        "Lucro Bruto (R$)",
                        "Lucro Líquido Real (R$)",
                        "Margem Bruta (%)",
                        "Margem Líquida (%)",
                        "Markup Médio (%)",
                        "Evolução (%)",
                    ]
                    if visao_tempo_margem != "📆 Consolidado Anual":
                        cols_mom_final.append("Vs. Ano Ant. (%)")

                    df_mom_exib = df_mom.rename(
                        columns={
                            col_chave_tempo: rotulo_col_tempo,
                            "dias_mov": "Dias c/ Saída",
                            "compras_nf": "Compras NF a Custo (R$)",
                            "cmv_sai": "CMV das Saídas (R$)",
                            "faturamento": "Faturamento Bruto (R$)",
                            "impostos": "Impostos Est. (R$)",
                            "lucro_bruto": "Lucro Bruto (R$)",
                            "lucro_liq": "Lucro Líquido Real (R$)",
                            "margem_bruta_pct": "Margem Bruta (%)",
                            "margem_liq_pct": "Margem Líquida (%)",
                            "markup_pct": "Markup Médio (%)",
                            "cresc_mom_pct": "Evolução (%)",
                            "cresc_yoy_pct": "Vs. Ano Ant. (%)",
                        }
                    )[cols_mom_final]
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
                                "Markup Médio (%)": lambda x: formatar_pct_br(x, 1, com_sinal=True),
                                "Evolução (%)": lambda x: "-" if (pd.isna(x) or float(x) == 0.0) else formatar_pct_br(x, 1, com_sinal=True),
                                "Vs. Ano Ant. (%)": lambda x: "-" if (pd.isna(x) or float(x) == 0.0) else formatar_pct_br(x, 1, com_sinal=True),
                            },
                            colunas_esquerda=[],
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            with tab_grp_mg:
                if df_sai_com_fat.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) para visualizar a margem média por grupo.")
                else:
                    grp_dep_mg = (
                        df_sai_com_fat.groupby("departamento", as_index=False)
                        .agg(
                            skus_vend=("codigo", "nunique"),
                            qtd_vend=("qtd_saida", "sum"),
                            faturamento=("fat_bruto", "sum"),
                            fat_base_mg=("fat_com_custo", "sum"),
                            cmv_total=("cmv_total", "sum"),
                            impostos=("imposto_est", "sum"),
                            lucro_bruto=("lucro_bruto", "sum"),
                            lucro_liq=("lucro_liquido", "sum"),
                        )
                        .sort_values("faturamento", ascending=False)
                        .reset_index(drop=True)
                    )
                    tot_fat_grp = float(grp_dep_mg["faturamento"].sum())
                    grp_dep_mg["part_fat_pct"] = (grp_dep_mg["faturamento"] / max(tot_fat_grp, 1.0)) * 100.0
                    grp_dep_mg["margem_bruta_pct"] = [
                        ((lb / fb) * 100.0) if fb > 0 else 0.0
                        for lb, fb in zip(grp_dep_mg["lucro_bruto"], grp_dep_mg["fat_base_mg"])
                    ]
                    grp_dep_mg["margem_liq_pct"] = [
                        ((ll / fb) * 100.0) if fb > 0 else 0.0
                        for ll, fb in zip(grp_dep_mg["lucro_liq"], grp_dep_mg["fat_base_mg"])
                    ]
                    grp_dep_mg["markup_pct"] = [
                        (((fb / cmv) - 1.0) * 100.0) if (fb > 0 and cmv > 0) else 0.0
                        for fb, cmv in zip(grp_dep_mg["fat_base_mg"], grp_dep_mg["cmv_total"])
                    ]
                    df_grp_mg_exib = grp_dep_mg.rename(
                        columns={
                            "departamento": "Grupo / Departamento",
                            "skus_vend": "SKUs",
                            "qtd_vend": "Qtd. Vendida",
                            "faturamento": "Faturamento (R$)",
                            "part_fat_pct": "% Fat.",
                            "cmv_total": "CMV Total (R$)",
                            "impostos": "Impostos Est. (R$)",
                            "lucro_bruto": "Lucro Bruto (R$)",
                            "lucro_liq": "Lucro Líquido Real (R$)",
                            "margem_bruta_pct": "Margem Bruta (%)",
                            "margem_liq_pct": "Margem Líquida (%)",
                            "markup_pct": "Markup Médio (%)",
                        }
                    )[
                        [
                            "Grupo / Departamento",
                            "SKUs",
                            "Qtd. Vendida",
                            "Faturamento (R$)",
                            "% Fat.",
                            "CMV Total (R$)",
                            "Impostos Est. (R$)",
                            "Lucro Bruto (R$)",
                            "Lucro Líquido Real (R$)",
                            "Margem Bruta (%)",
                            "Margem Líquida (%)",
                            "Markup Médio (%)",
                        ]
                    ]
                    st.dataframe(
                        estilizar_tabela_br(
                            df_grp_mg_exib,
                            formatadores={
                                "SKUs": formatar_num_br,
                                "Qtd. Vendida": formatar_qtd_br,
                                "Faturamento (R$)": formatar_moeda_br,
                                "% Fat.": lambda x: formatar_pct_br(x, 1),
                                "CMV Total (R$)": formatar_moeda_br,
                                "Impostos Est. (R$)": formatar_moeda_br,
                                "Lucro Bruto (R$)": formatar_moeda_br,
                                "Lucro Líquido Real (R$)": formatar_moeda_br,
                                "Margem Bruta (%)": lambda x: formatar_pct_br(x, 1),
                                "Margem Líquida (%)": lambda x: formatar_pct_br(x, 1),
                                "Markup Médio (%)": lambda x: formatar_pct_br(x, 1, com_sinal=True),
                            },
                            colunas_esquerda=["Grupo / Departamento"],
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.download_button(
                        label="📥 Baixar Margem Média por Grupo / Departamento (.xlsx)",
                        data=gerar_excel_relatorio(df_grp_mg_exib, "Margem_Por_Grupo"),
                        file_name=f"Margem_Media_Grupos_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_margem_grupos_bi",
                    )

            with tab_sku_lucro:
                if df_sai_base_margem.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) e custo cadastrado para ver o ranking de lucro por produto.")
                else:
                    grp_sku_fat = (
                        df_sai_base_margem.groupby("codigo", as_index=False)
                        .agg(
                            descricao=("descricao", "last"),
                            departamento=("departamento", "last"),
                            qtd_vendida=("qtd_saida", "sum"),
                            preco_t1_u=("preco_t1_u", "last"),
                            cmv_total=("cmv_total", "sum"),
                            faturamento=("fat_bruto", "sum"),
                            impostos=("imposto_est", "sum"),
                            lucro_bruto=("lucro_bruto", "sum"),
                            lucro_liq=("lucro_liquido", "sum"),
                        )
                    )
                    grp_sku_fat["custo_u"] = (grp_sku_fat["cmv_total"] / grp_sku_fat["qtd_vendida"].replace(0.0, float("nan"))).fillna(0.0)
                    grp_sku_fat["preco_medio_venda"] = grp_sku_fat["faturamento"] / grp_sku_fat["qtd_vendida"].replace(0.0, float("nan"))
                    grp_sku_fat["desconto_vs_t1_pct"] = [
                        round(((t1 - pv) / t1) * 100.0, 2) if (t1 > 0 and pv > 0) else 0.0
                        for t1, pv in zip(grp_sku_fat["preco_t1_u"], grp_sku_fat["preco_medio_venda"])
                    ]
                    grp_sku_fat["margem_bruta_pct"] = (grp_sku_fat["lucro_bruto"] / grp_sku_fat["faturamento"]) * 100.0
                    grp_sku_fat["margem_liq_pct"] = (grp_sku_fat["lucro_liq"] / grp_sku_fat["faturamento"]) * 100.0
                    top_lucro_df = grp_sku_fat.sort_values("lucro_liq", ascending=False).head(50).reset_index(drop=True)
                    top_lucro_exib = top_lucro_df.rename(
                        columns={
                            "codigo": "Código",
                            "descricao": "Descrição",
                            "departamento": "Grupo",
                            "qtd_vendida": "Qtd. Vendida",
                            "custo_u": "Custo C1 (R$)",
                            "preco_t1_u": "Preço Tabela T1 (R$)",
                            "preco_medio_venda": "Preço Vendido Balcão (R$)",
                            "desconto_vs_t1_pct": "Desc. vs T1 (%)",
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
                            "Grupo",
                            "Qtd. Vendida",
                            "Custo C1 (R$)",
                            "Preço Tabela T1 (R$)",
                            "Preço Vendido Balcão (R$)",
                            "Desc. vs T1 (%)",
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
                                "Custo C1 (R$)": formatar_moeda_br,
                                "Preço Tabela T1 (R$)": lambda x: "-" if (pd.isna(x) or float(x) <= 0.0) else formatar_moeda_br(x),
                                "Preço Vendido Balcão (R$)": formatar_moeda_br,
                                "Desc. vs T1 (%)": lambda x: "-" if (pd.isna(x) or abs(float(x)) < 0.05) else formatar_pct_br(x, 1, com_sinal=True),
                                "Faturamento (R$)": formatar_moeda_br,
                                "CMV Total (R$)": formatar_moeda_br,
                                "Impostos Est. (R$)": formatar_moeda_br,
                                "Lucro Líquido Real (R$)": formatar_moeda_br,
                                "Margem Bruta (%)": lambda x: formatar_pct_br(x, 1),
                                "Margem Líquida (%)": lambda x: formatar_pct_br(x, 1),
                            },
                            colunas_esquerda=["Descrição", "Grupo"],
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

            with tab_desc_t1:
                if df_sai_com_fat.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) para auditar os descontos concedidos.")
                elif not mapa_t1_bi or sum(1 for v in mapa_t1_bi.values() if float(v) > 0) == 0:
                    st.info("Suba a planilha **Custos & Preços (`C1 + T1`)** na Aba 6 para comparar o Preço Tabela T1 com o Preço Vendido no Balcão.")
                else:
                    cd_lim1, cd_lim2 = st.columns([1.2, 2.8])
                    with cd_lim1:
                        limite_desc_bi = st.number_input(
                            "🎯 Alertar descontos acima de (%):",
                            min_value=1.0,
                            max_value=50.0,
                            value=5.0,
                            step=0.5,
                            key="bi_limite_desc_t1",
                            help="O padrão do sistema é até 2,1%. Acima de 5,0%, o item aparece na lista de auditoria.",
                        )
                    df_desc_aud_bi = auditar_descontos_saidas_df(
                        df_saidas_ref=df_sai_com_fat,
                        df_custos_ref=df_custos_rel,
                        limite_desconto_pct=float(limite_desc_bi),
                        df_entradas_ref=df_entradas,
                    )
                    if df_desc_aud_bi.empty:
                        st.success(f"✅ Nenhum produto vendido no período selecionado teve desconto acima de {formatar_num_br(limite_desc_bi, 1)}% em relação à Tabela T1!")
                    else:
                        df_desc_aud_bi["departamento"] = df_desc_aud_bi["codigo"].map(
                            lambda c: identificar_departamento_sku(c, grupos_pref_custom, grupos_sku_custom)
                        )
                        tot_desc_concedido_rs = float(df_desc_aud_bi["desconto_total_rs"].sum())
                        tot_cheio_t1_rs = float(df_desc_aud_bi["valor_cheio_t1_total"].sum())
                        tot_vendido_balcao_rs = float(df_desc_aud_bi["valor_venda"].sum())
                        with cd_lim2:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            st.warning(
                                f"🏷️ **{formatar_num_br(len(df_desc_aud_bi))} venda(s)** com desconto > {formatar_num_br(limite_desc_bi, 1)}%  |  "
                                f"Valor Cheio T1: **{formatar_moeda_br(tot_cheio_t1_rs)}** ➔ Vendido: **{formatar_moeda_br(tot_vendido_balcao_rs)}**  |  "
                                f"Desconto Concedido: **{formatar_moeda_br(tot_desc_concedido_rs)}**"
                            )
                        df_desc_bi_exib = df_desc_aud_bi[
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
                            }
                        )
                        st.dataframe(
                            estilizar_tabela_br(
                                df_desc_bi_exib,
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
                                colunas_esquerda=["Descrição", "Grupo"],
                            ),
                            use_container_width=True,
                            hide_index=True,
                            height=300,
                        )
                        st.download_button(
                            label="📥 Baixar Auditoria de Descontos vs. Tabela T1 (.xlsx)",
                            data=gerar_excel_relatorio(df_desc_bi_exib, "Descontos_Acima_5pct"),
                            file_name=f"Auditoria_Descontos_T1_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_auditoria_descontos_bi",
                        )

            with tab_sku_alerta:
                if df_sai_com_fat.empty:
                    st.info("Importe uma planilha de Saídas com a 4ª coluna (`Valor Total da Proposta`) para auditar margens comprimidas.")
                else:
                    df_sai_pre_reaj_sem_hist = df_sai_com_fat[
                        (df_sai_com_fat["pre_reajuste"] == True) & (df_sai_com_fat["custo_u"] <= 0)
                    ].copy()

                    if not df_sai_base_margem.empty:
                        grp_alerta_sku = (
                            df_sai_base_margem.groupby("codigo", as_index=False)
                            .agg(
                                descricao=("descricao", "last"),
                                departamento=("departamento", "last"),
                                qtd_vendida=("qtd_saida", "sum"),
                                cmv_total=("cmv_total", "sum"),
                                faturamento=("fat_bruto", "sum"),
                                lucro_liq=("lucro_liquido", "sum"),
                            )
                        )
                        grp_alerta_sku["custo_u"] = (grp_alerta_sku["cmv_total"] / grp_alerta_sku["qtd_vendida"].replace(0.0, float("nan"))).fillna(0.0)
                        grp_alerta_sku["preco_medio_venda"] = (grp_alerta_sku["faturamento"] / grp_alerta_sku["qtd_vendida"].replace(0.0, float("nan"))).fillna(0.0)
                        grp_alerta_sku["margem_liq_pct"] = (grp_alerta_sku["lucro_liq"] / grp_alerta_sku["faturamento"]) * 100.0
                        df_alerta_mg = grp_alerta_sku[grp_alerta_sku["margem_liq_pct"] < 10.0].sort_values(
                            "lucro_liq", ascending=True
                        ).reset_index(drop=True)
                    else:
                        df_alerta_mg = pd.DataFrame()

                    if df_alerta_mg.empty:
                        st.success(f"✅ Excelente! Nenhum produto vendido com custo vigente na data teve margem líquida inferior a 10% (impostos: {formatar_num_br(aliq_imp_efetiva, 1)}%).")
                    else:
                        df_alerta_mg["status_margem"] = [
                            "🔴 Prejuízo Líquido (Abaixo de Custo + Impostos)" if float(m) < 0.0 else "🟠 Margem Comprimida (< 10% Líq.)"
                            for m in df_alerta_mg["margem_liq_pct"]
                        ]
                        df_alerta_exib = df_alerta_mg.rename(
                            columns={
                                "codigo": "Código",
                                "descricao": "Descrição",
                                "departamento": "Grupo",
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
                                "Grupo",
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
                                colunas_esquerda=["Descrição", "Grupo", "Status de Margem"],
                            ),
                            use_container_width=True,
                            hide_index=True,
                            height=280,
                        )

                    if not df_sai_pre_reaj_sem_hist.empty:
                        with st.expander(
                            f"⏳ Vendas Anteriores ao Reajuste de Custo ({formatar_num_br(df_sai_pre_reaj_sem_hist['codigo'].nunique())} SKU(s) — Excluídas do alerta de prejuízo e da base de margem)",
                            expanded=False,
                        ):
                            st.caption(
                                "Estes itens foram vendidos antes da entrada da NF reajustada e ainda não possuíam custo anterior gravado; "
                                "por isso o sistema os exclui da base de margem e não aplica o custo novo retroativamente."
                            )
                            df_pr_exib = df_sai_pre_reaj_sem_hist.copy()
                            df_pr_exib["preco_praticado"] = (df_pr_exib["fat_bruto"] / df_pr_exib["qtd_saida"].replace(0.0, float("nan"))).fillna(0.0)
                            df_pr_exib["custo_atual_ref"] = df_pr_exib["codigo"].map(mapa_custo_bi).fillna(0.0)
                            df_pr_tab = df_pr_exib[
                                ["data", "codigo", "descricao", "qtd_saida", "preco_praticado", "fat_bruto", "custo_atual_ref", "motivo_temporal"]
                            ].rename(
                                columns={
                                    "data": "Data Venda",
                                    "codigo": "Código",
                                    "descricao": "Descrição",
                                    "qtd_saida": "Qtd. Vendida",
                                    "preco_praticado": "Preço Vendido (R$)",
                                    "fat_bruto": "Faturamento (R$)",
                                    "custo_atual_ref": "Custo C1 Atual (R$)",
                                    "motivo_temporal": "Diagnóstico Temporal",
                                }
                            )
                            st.dataframe(
                                estilizar_tabela_br(
                                    df_pr_tab,
                                    formatadores={
                                        "Qtd. Vendida": formatar_qtd_br,
                                        "Preço Vendido (R$)": formatar_moeda_br,
                                        "Faturamento (R$)": formatar_moeda_br,
                                        "Custo C1 Atual (R$)": formatar_moeda_br,
                                    },
                                    colunas_esquerda=["Descrição", "Diagnóstico Temporal"],
                                ),
                                use_container_width=True,
                                hide_index=True,
                            )
