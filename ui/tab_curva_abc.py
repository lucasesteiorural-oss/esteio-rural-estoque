"""
ui/tab_curva_abc.py — Aba 4: Curva ABC Financeira, Elefantes Brancos,
Vitrine Multi-Produto e simulador de giro.
"""
import re
import unicodedata
import pandas as pd
import streamlit as st

from parsers import (
    hoje_br,
    formatar_num_br,
    formatar_qtd_br,
    formatar_moeda_br,
    formatar_pct_br,
    gerar_excel_relatorio,
    identificar_produto_mp,
)
from analytics import (
    calcular_motor_giro_sazonal,
    calcular_tabela_curva_abc,
    enriquecer_curva_abc_giro_t1,
    calcular_simulacao_giro_abc,
    gerar_textos_campanha_curva_abc,
    gerar_textos_vitrine_multi_abc,
)


def render_tab_curva_abc(ctx: dict) -> None:
    """Renderiza a Aba 4 — Curva ABC Financeira."""
    df_estoque = ctx["df_estoque"]
    df_historico = ctx["df_historico"]
    df_entradas = ctx["df_entradas"]
    df_saidas = ctx["df_saidas"]
    df_custos_rel = ctx["df_custos_rel"]
    df_base_vendas_rel = ctx["df_base_vendas_rel"]
    dias_base_atual = ctx["dias_base_atual"]
    grupos_sku_custom = ctx["grupos_sku_custom"]
    mp_custom_map = ctx["mp_custom_map"]

    st.markdown("### 📈 Curva ABC Financeira & Central de Aceleração de Giro")
    st.caption(
        "Cruza o capital imobilizado na prateleira (**80% Classe A, 15% Classe B e 5% Classe C**) com o **Giro Diário** e a **Tabela T1** "
        "para identificar **Elefantes Brancos (180+ dias parados)** e itens de alta margem. "
        "Marque **1 produto** (Oferta Individual / Atacado) ou **2 a 8+ produtos** (Vitrine da Semana) na tabela para simular descontos protegidos e gerar o texto pronto para WhatsApp."
    )
    if df_estoque.empty and df_custos_rel.empty:
        st.info("Importe a Planilha de Estoque e a Planilha de Custos na Aba 6 (Importação & Backup) para gerar a Curva ABC Financeira.")
    else:
        col_f_abc1, col_f_abc2, col_f_abc3 = st.columns([1.8, 1.3, 1.1])
        with col_f_abc1:
            busca_abc = st.text_input(
                "🔍 Pesquisar Fornecedor / Linha / Produto (vírgula p/ vários):",
                placeholder="Ex: matsuda  |  ouro fino, ceva  |  505084",
                key="busca_curva_abc",
            )
        with col_f_abc2:
            filtro_alvo_abc = st.selectbox(
                "🎯 Filtro de Alvos & Oportunidades:",
                options=[
                    "📋 Todos os Itens da Curva",
                    "🐘 Elefantes Brancos (Classe A/B com 180+ dias)",
                    "⚠️ Giro Lento + Elefantes Brancos (Classe A/B 90d+)",
                    "💎 Alta Margem Atual (Margem ≥ 35%)",
                    "🏆 Apenas Classe A (80% do Capital)",
                ],
                index=0,
                key="filtro_alvo_curva_abc",
            )
        with col_f_abc3:
            escopo_abc = st.selectbox(
                "🏢 Escopo de Produtos:",
                options=[
                    "🏢 Todos (Loja + Fábrica MP)",
                    "🏪 Apenas Loja Varejo",
                    "🏭 Apenas Fábrica / MP",
                ],
                index=0,
                key="escopo_curva_abc",
            )

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
            df_giro_abc_base, _, _ = calcular_motor_giro_sazonal(
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

            df_abc = enriquecer_curva_abc_giro_t1(
                df_abc_base=df_abc,
                df_custos_ref=df_custos_rel,
                df_giro_ref=df_giro_abc_base,
                df_saidas_ref=df_saidas,
                margem_referencia_pct=28.0,
            )

            df_abc["eh_mp"] = [
                identificar_produto_mp(c, d, grupos_sku_custom, mp_custom_map)
                for c, d in zip(df_abc["codigo"], df_abc["descricao"])
            ]
            if escopo_abc.startswith("🏪"):
                df_abc = df_abc[~df_abc["eh_mp"]].copy()
            elif escopo_abc.startswith("🏭"):
                df_abc = df_abc[df_abc["eh_mp"]].copy()

            total_fin = float(df_abc["valor_estoque"].sum())
            qtd_classe_a = int((df_abc["classe_abc_curta"] == "Classe A").sum())
            mask_elefantes = df_abc["diagnostico_alvo"].str.startswith("🐘", na=False)
            qtd_elefantes = int(mask_elefantes.sum())
            cap_elefantes = float(df_abc.loc[mask_elefantes, "valor_estoque"].sum())
            qtd_sem_saldo_custo = int((df_abc["classe_abc_curta"] == "Sem Saldo/Custo").sum())

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Capital Total Imobilizado", formatar_moeda_br(total_fin))
            a2.metric("Itens Classe A (80% do Valor)", f"{formatar_num_br(qtd_classe_a)} SKUs")
            a3.metric(
                "Elefantes Brancos (A/B 180d+)",
                f"{formatar_num_br(qtd_elefantes)} SKUs",
                f"{formatar_moeda_br(cap_elefantes)} parados",
                delta_color="off",
            )
            a4.metric(
                "Itens Zerados / Sem Custo",
                f"{formatar_num_br(qtd_sem_saldo_custo)} SKUs" if incluir_zerados_abc else "Ocultos (Marque acima)",
            )

            df_abc_filtrado = df_abc.copy()

            if filtro_alvo_abc.startswith("🐘"):
                df_abc_filtrado = df_abc_filtrado[df_abc_filtrado["diagnostico_alvo"].str.startswith("🐘", na=False)].copy()
            elif filtro_alvo_abc.startswith("⚠️"):
                df_abc_filtrado = df_abc_filtrado[
                    df_abc_filtrado["diagnostico_alvo"].str.startswith("🐘", na=False)
                    | df_abc_filtrado["diagnostico_alvo"].str.startswith("⚠️", na=False)
                ].copy()
            elif filtro_alvo_abc.startswith("💎"):
                df_abc_filtrado = df_abc_filtrado[
                    (df_abc_filtrado["saldo_geral"] > 0) & (df_abc_filtrado["margem_atual_pct"] >= 35.0)
                ].copy()
            elif filtro_alvo_abc.startswith("🏆"):
                df_abc_filtrado = df_abc_filtrado[df_abc_filtrado["classe_abc_curta"] == "Classe A"].copy()

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
                                f"acima para visualizar todos os {formatar_num_br(len(df_abc_com_z[m_z_tot]))} itens!"
                            )

            df_abc_filtrado = df_abc_filtrado.reset_index(drop=True)

            df_abc_editor = pd.DataFrame(
                {
                    "🎯": [False] * len(df_abc_filtrado),
                    "Classe ABC": df_abc_filtrado["classe_abc_curta"].values,
                    "Diagnóstico Alvo": df_abc_filtrado["diagnostico_alvo"].values,
                    "Código": df_abc_filtrado["codigo"].values,
                    "Descrição": df_abc_filtrado["descricao"].values,
                    "Saldo": [formatar_qtd_br(v) for v in df_abc_filtrado["saldo_geral"].values],
                    "Giro/Dia": [
                        formatar_num_br(v, 3) if (pd.notna(v) and 0 < float(v) < 0.05) else formatar_num_br(v, 2)
                        for v in df_abc_filtrado["giro_diario"].values
                    ],
                    "Autonomia": [
                        "-" if s <= 0 else ("999+ d" if a >= 999.0 else f"{formatar_num_br(a, 0)}d")
                        for s, a in zip(df_abc_filtrado["saldo_geral"].values, df_abc_filtrado["autonomia_dias"].values)
                    ],
                    "Custo C1 (R$)": [formatar_moeda_br(v) for v in df_abc_filtrado["custo_unitario"].values],
                    "Tabela T1 (R$)": [
                        f"{formatar_moeda_br(p)} ({o})" if p > 0 else "-"
                        for p, o in zip(df_abc_filtrado["preco_base"].values, df_abc_filtrado["origem_preco"].values)
                    ],
                    "Margem Atual": [
                        formatar_pct_br(m, 1) if p > 0 else "-"
                        for m, p in zip(df_abc_filtrado["margem_atual_pct"].values, df_abc_filtrado["preco_base"].values)
                    ],
                    "Valor Total (R$)": [formatar_moeda_br(v) for v in df_abc_filtrado["valor_estoque"].values],
                    "% Indiv.": [formatar_pct_br(v, 2) for v in df_abc_filtrado["part_pct"].values],
                    "% Acum.": [formatar_pct_br(v, 2) for v in df_abc_filtrado["acum_pct"].values],
                }
            )

            ed_abc_giro = st.data_editor(
                df_abc_editor,
                use_container_width=True,
                hide_index=True,
                height=420,
                key="editor_curva_abc_giro",
                disabled=[
                    "Classe ABC",
                    "Diagnóstico Alvo",
                    "Código",
                    "Descrição",
                    "Saldo",
                    "Giro/Dia",
                    "Autonomia",
                    "Custo C1 (R$)",
                    "Tabela T1 (R$)",
                    "Margem Atual",
                    "Valor Total (R$)",
                    "% Indiv.",
                    "% Acum.",
                ],
                column_config={
                    "🎯": st.column_config.CheckboxColumn(
                        "🎯",
                        help="Marque 1 produto (Oferta Individual / Atacado) ou 2 a 8+ produtos (Vitrine da Semana) para gerar a campanha abaixo!",
                        default=False,
                        width="small",
                    ),
                    "Classe ABC": st.column_config.TextColumn("Classe", width="small"),
                    "Diagnóstico Alvo": st.column_config.TextColumn("Diagnóstico Alvo", width="medium"),
                    "Código": st.column_config.TextColumn("Código", width="small"),
                    "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
                    "Saldo": st.column_config.TextColumn("Saldo", width="small"),
                    "Giro/Dia": st.column_config.TextColumn("Giro/Dia", width="small"),
                    "Autonomia": st.column_config.TextColumn("Auton.", width="small"),
                    "Custo C1 (R$)": st.column_config.TextColumn("Custo C1", width="small"),
                    "Tabela T1 (R$)": st.column_config.TextColumn("Preço T1 / Base", width="medium"),
                    "Margem Atual": st.column_config.TextColumn("Margem %", width="small"),
                    "Valor Total (R$)": st.column_config.TextColumn("Capital (R$)", width="small"),
                    "% Indiv.": st.column_config.TextColumn("% Indiv.", width="small"),
                    "% Acum.": st.column_config.TextColumn("% Acum.", width="small"),
                },
            )

            if not df_abc_filtrado.empty:
                df_abc_export_xlsx = df_abc_filtrado[
                    [
                        "classe_abc",
                        "diagnostico_alvo",
                        "codigo",
                        "descricao",
                        "saldo_geral",
                        "giro_diario",
                        "autonomia_dias",
                        "custo_unitario",
                        "preco_base",
                        "origem_preco",
                        "margem_atual_pct",
                        "valor_estoque",
                        "part_pct",
                        "acum_pct",
                    ]
                ].rename(
                    columns={
                        "classe_abc": "Classe ABC",
                        "diagnostico_alvo": "Diagnóstico Alvo",
                        "codigo": "Código",
                        "descricao": "Descrição",
                        "saldo_geral": "Saldo Geral",
                        "giro_diario": "Giro/Dia",
                        "autonomia_dias": "Autonomia (Dias)",
                        "custo_unitario": "Custo Unit. (R$)",
                        "preco_base": "Preço Base T1 (R$)",
                        "origem_preco": "Origem Preço",
                        "margem_atual_pct": "Margem Atual (%)",
                        "valor_estoque": "Valor Total (R$)",
                        "part_pct": "% Individual",
                        "acum_pct": "% Acumulado",
                    }
                )
                st.download_button(
                    label="📥 Baixar Curva ABC & Giro (.xlsx)",
                    data=gerar_excel_relatorio(df_abc_export_xlsx, "Curva_ABC_Giro"),
                    file_name=f"Curva_ABC_Giro_Esteio_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # ------------------------------------------------------------------
            # PILARES 2, 3 e 4: SIMULADOR DE GIRO & GERADOR DE OFERTAS WHATSAPP
            # ------------------------------------------------------------------
            st.markdown("---")
            st.markdown("#### 🚀 Simulador de Desconto Inteligente & Gerador de Ofertas (WhatsApp / Equipe)")
            st.caption(
                "Diferente da Aba 3 (queima de validade), aqui o foco é **acelerar o giro aumentando o lucro total em reais**: "
                "o simulador calcula o **Ponto de Equilíbrio de Volume** (quantos % a mais você precisa vender para empatar o lucro R$) "
                "e gera copy comercial de oportunidade para os grupos de produtores."
            )

            p_abc1, p_abc2, p_abc3 = st.columns([1.0, 1.0, 1.6])
            with p_abc1:
                aliq_imp_abc = st.number_input(
                    "🏛️ Impostos s/ Venda (%):",
                    min_value=0.0,
                    max_value=35.0,
                    value=0.0,
                    step=0.5,
                    key="abc_sim_aliq_imp",
                    help="Padrão 0% (medicamentos isentos). Ajuste se quiser embutir ICMS/PIS/COFINS/ST no piso.",
                )
            with p_abc2:
                margem_alvo_abc = st.number_input(
                    "🎯 Margem Líquida Mínima Alvo (%):",
                    min_value=0.0,
                    max_value=50.0,
                    value=12.0,
                    step=1.0,
                    key="abc_sim_margem_alvo",
                    help="Define o Preço Mínimo Autorizado no Siagri (Custo C1 + Impostos + Margem Alvo).",
                )
            with p_abc3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                exibir_de_abc = st.checkbox(
                    "🏷️ Exibir preço antigo ('De: ~R$ X~') e economia na mensagem do WhatsApp",
                    value=True,
                    key="abc_sim_exibir_de",
                )

            indices_marcados_abc = ed_abc_giro.index[ed_abc_giro["🎯"] == True].tolist()
            df_selecionados_abc = df_abc_filtrado.iloc[indices_marcados_abc].copy() if indices_marcados_abc else pd.DataFrame()

            # Personalização Rápida (Pilar 4)
            st.markdown("##### ✍️ Personalização Rápida da Campanha")
            pers1, pers2, pers3 = st.columns([1.3, 1.2, 1.3])
            with pers1:
                chamada_beneficio_abc = st.text_input(
                    "✨ Chamada / Benefício (opcional):",
                    placeholder="Ex: Ideal para protocolo sanitário / reforma de pasto",
                    key="abc_pers_chamada",
                )
            with pers2:
                prazo_campanha_abc = st.text_input(
                    "⏳ Prazo ou Limite da Campanha:",
                    value="Válido somente até sábado ou enquanto durar o estoque promocional",
                    key="abc_pers_prazo",
                )
            with pers3:
                rodape_comercial_abc = st.text_input(
                    "🚚 Condição Comercial / Entrega (rodapé):",
                    value="Condição à vista (Pix/Dinheiro). Consulte entrega na fazenda!",
                    key="abc_pers_rodape",
                )

            # MODO MULTI-PRODUTO (2 ou mais itens marcados -> Modelo 3 Vitrine / Combo)
            if len(df_selecionados_abc) >= 2:
                st.info(
                    f"🔥 **Modo Vitrine / Combo da Semana Ativo ({len(df_selecionados_abc)} produtos marcados):** "
                    f"ajuste abaixo o preço normal e o desconto de cada item para gerar a lista única de disparo no WhatsApp."
                )
                df_vitrine_edit = pd.DataFrame(
                    {
                        "Código": df_selecionados_abc["codigo"].astype(str).values,
                        "Descrição": df_selecionados_abc["descricao"].astype(str).values,
                        "Saldo": [float(v) for v in df_selecionados_abc["saldo_geral"].values],
                        "Custo C1 (R$)": [round(float(v), 2) for v in df_selecionados_abc["custo_unitario"].values],
                        "Preço De (R$)": [
                            round(max(float(p), float(c) * 1.20, 1.0), 2)
                            for p, c in zip(df_selecionados_abc["preco_base"].values, df_selecionados_abc["custo_unitario"].values)
                        ],
                        "Desconto (%)": [10.0] * len(df_selecionados_abc),
                    }
                )
                ed_vitrine = st.data_editor(
                    df_vitrine_edit,
                    use_container_width=True,
                    hide_index=True,
                    key="editor_vitrine_multi_abc",
                    disabled=["Código", "Descrição", "Saldo", "Custo C1 (R$)"],
                    column_config={
                        "Código": st.column_config.TextColumn("Código", width="small"),
                        "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
                        "Saldo": st.column_config.NumberColumn("Saldo", format="%.0f", width="small"),
                        "Custo C1 (R$)": st.column_config.NumberColumn("Custo C1", format="R$ %.2f", width="small"),
                        "Preço De (R$)": st.column_config.NumberColumn("Preço De (R$)", min_value=0.01, step=1.0, format="R$ %.2f", width="small"),
                        "Desconto (%)": st.column_config.NumberColumn("Desconto (%)", min_value=0.0, max_value=60.0, step=1.0, format="%.1f%%", width="small"),
                    },
                )

                itens_vitrine_calc = []
                alertas_piso_vitrine = []
                for _, r_vit in ed_vitrine.iterrows():
                    c_u = float(r_vit["Custo C1 (R$)"])
                    p_de_v = float(r_vit["Preço De (R$)"])
                    d_pct_v = float(r_vit["Desconto (%)"])
                    p_por_v = round(p_de_v * (1.0 - (d_pct_v / 100.0)), 2)
                    sim_v = calcular_simulacao_giro_abc(
                        custo_unit=c_u,
                        preco_de=p_de_v,
                        preco_por=p_por_v,
                        aliquota_imp_pct=float(aliq_imp_abc),
                        margem_alvo_pct=float(margem_alvo_abc),
                        saldo_atual=float(r_vit["Saldo"]),
                    )
                    if p_por_v < sim_v["preco_min_autorizado"] and c_u > 0:
                        alertas_piso_vitrine.append(
                            f"**[{r_vit['Código']}] {r_vit['Descrição']}** (Promo {formatar_moeda_br(p_por_v)} < Mín. Autorizado {formatar_moeda_br(sim_v['preco_min_autorizado'])})"
                        )
                    itens_vitrine_calc.append(
                        {
                            "codigo": str(r_vit["Código"]),
                            "descricao": str(r_vit["Descrição"]),
                            "preco_de": p_de_v,
                            "preco_por": p_por_v,
                            "desconto_pct": sim_v["desconto_efetivo_pct"],
                            "preco_min_autorizado": sim_v["preco_min_autorizado"],
                            "margem_liq_promo_pct": sim_v["margem_liq_promo_pct"],
                            "break_even_vol_pct": sim_v["break_even_vol_pct"],
                        }
                    )

                if alertas_piso_vitrine:
                    st.warning(
                        "⚠️ **Atenção à Margem Alvo na Vitrine:** Os seguintes itens ficaram abaixo do Preço Mínimo Autorizado: "
                        + " | ".join(alertas_piso_vitrine)
                    )

                txt_wpp_abc, txt_brief_abc = gerar_textos_vitrine_multi_abc(
                    itens_vitrine=itens_vitrine_calc,
                    chamada_beneficio=chamada_beneficio_abc,
                    prazo_campanha=prazo_campanha_abc,
                    rodape_comercial=rodape_comercial_abc,
                    exibir_preco_de=exibir_de_abc,
                )

                col_w_abc1, col_w_abc2 = st.columns(2)
                with col_w_abc1:
                    st.markdown("##### 📲 1. Modelo 3 — Vitrine da Semana (WhatsApp Grupos)")
                    st.code(txt_wpp_abc, language="markdown")
                with col_w_abc2:
                    st.markdown("##### 🎯 2. Briefing Interno da Vitrine (Equipe de Vendas)")
                    st.code(txt_brief_abc, language="markdown")

            # MODO INDIVIDUAL (1 produto marcado OU seleção rápida via dropdown)
            else:
                if len(df_selecionados_abc) == 1:
                    item_abc_sel = df_selecionados_abc.iloc[0]
                    st.caption(
                        f"✔️ Produto selecionado na tabela: **[{item_abc_sel['codigo']}] {item_abc_sel['descricao']}** "
                        f"(Marque 2 ou mais caixinhas 🎯 na tabela acima se quiser montar uma Vitrine Multi-Produto)."
                    )
                else:
                    df_cand_abc = df_abc_filtrado[df_abc_filtrado["saldo_geral"] > 0].copy()
                    if df_cand_abc.empty:
                        df_cand_abc = df_abc_filtrado.copy()
                    df_cand_abc["_prio_elef"] = df_cand_abc["diagnostico_alvo"].str.startswith("🐘", na=False).astype(int)
                    df_cand_abc = df_cand_abc.sort_values(
                        ["_prio_elef", "valor_estoque"], ascending=[False, False]
                    ).reset_index(drop=True)
                    opcoes_abc_sim = [
                        f"[{r['codigo']}] {r['descricao']} — {r['classe_abc_curta']} | {r['diagnostico_alvo']} | "
                        f"Saldo: {formatar_qtd_br(r['saldo_geral'])} un. | T1: {formatar_moeda_br(r['preco_base'])}"
                        for _, r in df_cand_abc.iterrows()
                    ]
                    idx_abc_drop = st.selectbox(
                        "🎯 Marque caixinhas 🎯 na tabela acima ou escolha aqui um produto para simular a oferta:",
                        options=range(len(opcoes_abc_sim)),
                        format_func=lambda i: opcoes_abc_sim[i],
                        key="sel_item_sim_abc_single",
                    )
                    item_abc_sel = df_cand_abc.iloc[int(idx_abc_drop)]

                cod_a_sim = str(item_abc_sel["codigo"])
                desc_a_sim = str(item_abc_sel["descricao"])
                cls_a_sim = str(item_abc_sel["classe_abc_curta"])
                saldo_a_sim = float(item_abc_sel["saldo_geral"])
                giro_a_sim = float(item_abc_sel["giro_diario"])
                auton_a_sim = float(item_abc_sel["autonomia_dias"])
                custo_a_sim = float(item_abc_sel["custo_unitario"])
                orig_p_a_sim = str(item_abc_sel["origem_preco"])
                p_base_a_padrao = max(float(item_abc_sel["preco_base"]), custo_a_sim * 1.25, 1.0)

                sa1, sa2, sa3 = st.columns(3)
                with sa1:
                    rotulo_t1_abc = (
                        f"💵 Preço Normal ({orig_p_a_sim}):"
                        if orig_p_a_sim in ("Tabela T1", "Média Saídas")
                        else "💵 Preço Normal (⚠️ Estimado — Confira):"
                    )
                    p_de_abc_in = st.number_input(
                        rotulo_t1_abc,
                        min_value=0.01,
                        max_value=100000.0,
                        value=float(round(p_base_a_padrao, 2)),
                        step=1.0,
                        key=f"abc_p_de_{cod_a_sim}",
                    )
                with sa2:
                    desc_abc_slider = st.slider(
                        "🏷️ Desconto à Vista (%):",
                        min_value=0.0,
                        max_value=50.0,
                        value=10.0,
                        step=1.0,
                        key=f"abc_desc_sl_{cod_a_sim}",
                    )
                p_por_abc_calc = round(p_de_abc_in * (1.0 - (desc_abc_slider / 100.0)), 2)
                with sa3:
                    p_por_abc_in = st.number_input(
                        "🔥 Preço Promo à Vista ('Por R$'):",
                        min_value=0.01,
                        max_value=100000.0,
                        value=float(max(p_por_abc_calc, 0.01)),
                        step=0.50,
                        key=f"abc_p_por_{cod_a_sim}_{desc_abc_slider}",
                    )

                sim_res_avista = calcular_simulacao_giro_abc(
                    custo_unit=custo_a_sim,
                    preco_de=p_de_abc_in,
                    preco_por=p_por_abc_in,
                    aliquota_imp_pct=float(aliq_imp_abc),
                    margem_alvo_pct=float(margem_alvo_abc),
                    saldo_atual=saldo_a_sim,
                    giro_diario=giro_a_sim,
                )

                ma1, ma2, ma3, ma4 = st.columns(4)
                ma1.metric(
                    "Preço Mínimo Autorizado",
                    formatar_moeda_br(sim_res_avista["preco_min_autorizado"]),
                    f"Piso Empate Zero: {formatar_moeda_br(sim_res_avista['preco_piso'])}",
                )
                ma2.metric(
                    "Preço Promo à Vista",
                    formatar_moeda_br(p_por_abc_in),
                    f"-{formatar_num_br(sim_res_avista['desconto_efetivo_pct'], 1)}% (Econ. {formatar_moeda_br(sim_res_avista['economia_un'])}/un.)",
                )
                ma3.metric(
                    "Margem Líq. Pós-Desconto",
                    formatar_pct_br(sim_res_avista["margem_liq_promo_pct"], 1),
                    f"{formatar_moeda_br(sim_res_avista['lucro_liq_promo_un'])} livres/un.",
                    delta_color="normal" if sim_res_avista["lucro_liq_promo_un"] >= 0 else "inverse",
                )
                be_val = sim_res_avista["break_even_vol_pct"]
                ma4.metric(
                    "Ponto de Equilíbrio Volume",
                    f"+{formatar_num_br(be_val, 1)}% un." if be_val is not None else "Inviável (< Piso)",
                    f"Meta: {formatar_num_br(sim_res_avista['meta_giro_dia'], 1)} un./dia",
                )

                if p_por_abc_in < sim_res_avista["preco_piso"] and custo_a_sim > 0:
                    st.error(
                        f"🚨 **Bloqueio de Margem:** O preço promocional (**{formatar_moeda_br(p_por_abc_in)}**) está abaixo do "
                        f"**Piso Tributário ({formatar_moeda_br(sim_res_avista['preco_piso'])})**, gerando prejuízo líquido de "
                        f"**{formatar_moeda_br(abs(sim_res_avista['lucro_liq_promo_un']))}/un.**"
                    )
                elif p_por_abc_in < sim_res_avista["preco_min_autorizado"] and custo_a_sim > 0:
                    st.warning(
                        f"⚠️ **Abaixo da Margem Alvo ({formatar_num_br(margem_alvo_abc, 0)}%):** O preço escolhido ficou abaixo do "
                        f"**Mínimo Autorizado ({formatar_moeda_br(sim_res_avista['preco_min_autorizado'])})**."
                    )
                elif be_val is not None and be_val > 0:
                    st.success(
                        f"📊 **Ponto de Equilíbrio de Volume:** Com **{formatar_num_br(sim_res_avista['desconto_efetivo_pct'], 1)}%** de desconto, "
                        f"você precisa vender **+{formatar_num_br(be_val, 1)}%** de unidades para empatar o lucro total em R$; "
                        f"qualquer venda acima disso é **lucro líquido extra** no caixa!"
                    )

                # Mecânica de Atacado / Volume (Condição Fazendeiro)
                usar_atac_abc = st.checkbox(
                    "🚜 Ativar Condição Fazendeiro / Preço de Atacado por Volume (desconto progressivo para compra fechada)",
                    value=False,
                    key=f"abc_chk_atac_{cod_a_sim}",
                )
                qtd_atac_in = 5
                p_atac_in = p_por_abc_in
                sim_res_atac = None
                if usar_atac_abc:
                    at1, at2, at3 = st.columns(3)
                    with at1:
                        qtd_atac_in = st.number_input(
                            "📦 Qtd. Mínima Atacado (un./sacos):",
                            min_value=2,
                            max_value=500,
                            value=5,
                            step=1,
                            key=f"abc_qtd_atac_{cod_a_sim}",
                        )
                    with at2:
                        desc_extra_atac = st.slider(
                            "📉 Desconto Extra Atacado (% s/ à vista):",
                            min_value=1.0,
                            max_value=25.0,
                            value=5.0,
                            step=0.5,
                            key=f"abc_desc_atac_{cod_a_sim}",
                        )
                    p_atac_calc = round(p_por_abc_in * (1.0 - (desc_extra_atac / 100.0)), 2)
                    with at3:
                        p_atac_in = st.number_input(
                            "🚜 Preço Unitário Atacado (R$):",
                            min_value=0.01,
                            max_value=100000.0,
                            value=float(max(p_atac_calc, 0.01)),
                            step=0.50,
                            key=f"abc_p_atac_{cod_a_sim}_{desc_extra_atac}",
                        )
                    sim_res_atac = calcular_simulacao_giro_abc(
                        custo_unit=custo_a_sim,
                        preco_de=p_de_abc_in,
                        preco_por=p_atac_in,
                        aliquota_imp_pct=float(aliq_imp_abc),
                        margem_alvo_pct=float(margem_alvo_abc),
                        saldo_atual=saldo_a_sim,
                        giro_diario=giro_a_sim,
                    )
                    econ_pacote_at = max(0.0, (p_de_abc_in - p_atac_in) * int(qtd_atac_in))
                    be_at = sim_res_atac["break_even_vol_pct"]
                    be_at_str = f"+{formatar_num_br(be_at, 1)}%" if be_at is not None else "Abaixo do piso"
                    st.caption(
                        f"🚜 **Resumo Atacado (≥ {int(qtd_atac_in)} un.):** Ticket do pacote = **{formatar_moeda_br(p_atac_in * int(qtd_atac_in))}** | "
                        f"Economia total do produtor = **{formatar_moeda_br(econ_pacote_at)}** | "
                        f"Margem Líq. Atacado = **{formatar_pct_br(sim_res_atac['margem_liq_promo_pct'], 1)}** | "
                        f"Break-Even Volume = **{be_at_str}**"
                    )

                modelo_wpp_abc = st.radio(
                    "📝 Estilo da Mensagem WhatsApp:",
                    options=[
                        "Modelo 1 — Oferta Relâmpago (Curto, visual e com gatilho de escassez)",
                        "Modelo 2 — Condição Fazendeiro / Volume (Foco em compra fechada para a fazenda)",
                    ],
                    index=1 if usar_atac_abc else 0,
                    horizontal=True,
                    key=f"abc_modelo_wpp_{cod_a_sim}",
                )

                txt_wpp_abc, txt_brief_abc = gerar_textos_campanha_curva_abc(
                    codigo=cod_a_sim,
                    descricao=desc_a_sim,
                    classe_abc=cls_a_sim,
                    saldo_atual=saldo_a_sim,
                    autonomia_dias=auton_a_sim,
                    custo_unit=custo_a_sim,
                    preco_de=p_de_abc_in,
                    preco_por=p_por_abc_in,
                    sim_avista=sim_res_avista,
                    modelo_escolhido=modelo_wpp_abc,
                    chamada_beneficio=chamada_beneficio_abc,
                    prazo_campanha=prazo_campanha_abc,
                    rodape_comercial=rodape_comercial_abc,
                    usar_atacado=usar_atac_abc,
                    qtd_atacado=int(qtd_atac_in),
                    preco_atacado=p_atac_in,
                    sim_atacado=sim_res_atac,
                    exibir_preco_de=exibir_de_abc,
                )

                col_w_abc1, col_w_abc2 = st.columns(2)
                with col_w_abc1:
                    st.markdown("##### 📲 1. Mensagem Pronta para WhatsApp (Grupos / Clientes)")
                    st.code(txt_wpp_abc, language="markdown")
                with col_w_abc2:
                    st.markdown("##### 🎯 2. Briefing Interno da Campanha (Equipe de Vendas)")
                    st.code(txt_brief_abc, language="markdown")
        else:
            st.warning("Nenhum produto com saldo e custo positivos encontrado para calcular a Curva ABC.")
