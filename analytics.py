"""
analytics.py — Módulo de Inteligência Analítica: Motor de Giro Sazonal, Radar FEFO & Promoções IA,
Curva ABC Financeira, Resolução Temporal Vetorizada (merge_asof) e Auditorias Fiscais/Descontos
(Esteio Rural — Arquitetura Modular v37).
"""
import pandas as pd
import streamlit as st

from parsers import (
    hoje_br,
    formatar_num_br,
    formatar_qtd_br,
    formatar_moeda_br,
    formatar_pct_br,
    converter_datas_deterministico,
    padronizar_dataframe,
    identificar_produto_mp,
)




# ==============================================================================
# 1. RADAR FEFO & SIMULADOR DE PROMOÇÕES ANTI-PERDA
# ==============================================================================


def calcular_plano_promocional_fefo(
    df_estoque_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    df_giro_ref: pd.DataFrame,
    aliquota_impostos_pct: float = 0.0,
    margem_referencia_pct: float = 30.0,
    df_saidas_ref: pd.DataFrame = None,
    grupos_sku_custom: dict = None,
    mp_custom_map: dict = None,
) -> pd.DataFrame:
    if df_estoque_ref is None or df_estoque_ref.empty:
        return pd.DataFrame()
    df_f = df_estoque_ref[df_estoque_ref["saldo_lote"] > 0].copy()
    if df_f.empty:
        return pd.DataFrame()

    if df_custos_ref is not None and not df_custos_ref.empty:
        cols_c_fefo = ["codigo", "custo_unitario"] + (["preco_tabela"] if "preco_tabela" in df_custos_ref.columns else [])
        df_f = df_f.merge(df_custos_ref[cols_c_fefo], on="codigo", how="left")
        df_f["custo_unitario"] = df_f["custo_unitario"].fillna(0.0)
        df_f["preco_tabela"] = df_f["preco_tabela"].fillna(0.0) if "preco_tabela" in df_f.columns else 0.0
    else:
        df_f["custo_unitario"] = 0.0
        df_f["preco_tabela"] = 0.0

    if df_giro_ref is not None and not df_giro_ref.empty and "giro_ponderado" in df_giro_ref.columns:
        mapa_giro = dict(zip(df_giro_ref["codigo"], df_giro_ref["giro_ponderado"].clip(lower=0.0)))
    else:
        mapa_giro = {}
    df_f["giro_diario"] = df_f["codigo"].map(mapa_giro).fillna(0.0)

    # Se já houver preço médio praticado nas saídas (quando coluna valor_venda estiver presente), aproveita-o
    mapa_preco_real = {}
    if (
        df_saidas_ref is not None
        and not df_saidas_ref.empty
        and "valor_venda" in df_saidas_ref.columns
        and "qtd_saida" in df_saidas_ref.columns
    ):
        df_s_val = df_saidas_ref[(df_saidas_ref["qtd_saida"] > 0) & (df_saidas_ref["valor_venda"] > 0)].copy()
        if not df_s_val.empty:
            soma_s = df_s_val.groupby("codigo", as_index=False).agg(
                tot_q=("qtd_saida", "sum"),
                tot_v=("valor_venda", "sum"),
            )
            soma_s["p_unit"] = soma_s["tot_v"] / soma_s["tot_q"]
            mapa_preco_real = dict(zip(soma_s["codigo"], soma_s["p_unit"]))

    df_f["dt_validade"] = converter_datas_deterministico(df_f["validade"])
    hoje_ts = pd.Timestamp(hoje_br())
    df_f["dias_para_vencer"] = (df_f["dt_validade"] - hoje_ts).dt.days
    df_f["valor_em_risco"] = df_f["saldo_lote"] * df_f["custo_unitario"]

    def _classificar_faixa_fefo(dias):
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
        if dias <= 120:
            return "🟣 5. Preventivo Longo (91 a 120 dias)"
        return "🟢 6. Seguro (> 120 dias)"

    df_f["status_fefo"] = df_f["dias_para_vencer"].apply(_classificar_faixa_fefo)

    # Ordena por código e data de validade crescente para simular a fila real FEFO (apenas lotes não vencidos entram na fila de venda)
    df_f["_ord_dias"] = df_f["dias_para_vencer"].fillna(999999.0)
    df_f = df_f.sort_values(["codigo", "_ord_dias", "lote"], ascending=[True, True, True]).reset_index(drop=True)
    df_f["_saldo_vendavel"] = [
        float(sl) if (pd.notna(dv) and float(dv) >= 0) else 0.0
        for sl, dv in zip(df_f["saldo_lote"], df_f["dias_para_vencer"])
    ]
    df_f["acum_lote_fefo"] = df_f.groupby("codigo")["_saldo_vendavel"].cumsum()
    df_f["saldo_lotes_anteriores"] = (df_f["acum_lote_fefo"] - df_f["_saldo_vendavel"]).clip(lower=0.0)

    fator_imposto = max(1.0 - (float(aliquota_impostos_pct) / 100.0), 0.10)
    fator_margem_ref = max(1.0 - (float(margem_referencia_pct) / 100.0), 0.15)

    sobra_proj_list = []
    cap_sobra_list = []
    preco_atual_list = []
    tem_preco_real_list = []
    origem_preco_list = []
    preco_piso_list = []
    preco_promo_list = []
    desc_sug_list = []
    margem_liq_promo_list = []
    meta_giro_promo_list = []
    diagnostico_escala_list = []
    mecanica_ia_list = []
    precisa_promo_list = []

    for _, r in df_f.iterrows():
        cod = str(r["codigo"]).strip()
        saldo_l = float(r["saldo_lote"])
        saldo_ant = float(r["saldo_lotes_anteriores"])
        custo_u = float(r["custo_unitario"])
        giro_d = float(r["giro_diario"])
        dias_v = r["dias_para_vencer"]

        preco_piso = (custo_u / fator_imposto) if custo_u > 0 else 0.0
        preco_t1_lido = float(r.get("preco_tabela", 0.0))
        preco_real_lido = float(mapa_preco_real.get(cod, 0.0))
        tem_preco_real = (preco_t1_lido > 0.0) or (preco_real_lido > 0.0)
        if preco_t1_lido > 0.0:
            preco_est = preco_t1_lido
            origem_p_txt = "🏷️ Tabela Oficial T1"
        elif preco_real_lido > 0.0:
            preco_est = preco_real_lido
            origem_p_txt = "✔️ Venda Real (Saídas)"
        elif custo_u > 0:
            preco_est = max(custo_u / fator_margem_ref, preco_piso * 1.15)
            origem_p_txt = "⚠️ Estimado (Margem)"
        else:
            preco_est = 0.0
            origem_p_txt = "⚪ Sem Custo/Preço"

        if pd.isna(dias_v):
            sobra_p = 0.0
            cap_sobra = 0.0
            precisa_p = False
            diag_txt = "⚪ Sem Validade Cadastrada"
            mec_txt = "Conferir data física no lote"
            desc_pct = 0.0
            preco_promo = preco_est
            meta_giro_p = giro_d
        elif float(dias_v) < 0:
            sobra_p = saldo_l
            cap_sobra = sobra_p * custo_u
            precisa_p = True
            diag_txt = "🔴 Vencido (Bloquear Venda)"
            mec_txt = "🚫 Segregar no depósito / Solicitar troca ou baixa"
            desc_pct = 0.0
            preco_promo = 0.0
            meta_giro_p = 0.0
        else:
            d_pos = max(float(dias_v), 0.0)
            venda_ate_venc = d_pos * giro_d
            absorcao_lote = min(saldo_l, max(0.0, venda_ate_venc - saldo_ant))
            sobra_p = max(0.0, round(saldo_l - absorcao_lote, 2))
            cap_sobra = sobra_p * custo_u
            meta_giro_p = (saldo_l + saldo_ant) / max(d_pos, 1.0)

            if sobra_p < 0.5 or d_pos > 120:
                precisa_p = False
                if d_pos <= 120:
                    diag_txt = "🟢 Escoa no Giro Normal"
                    mec_txt = "✅ Manter Preço Cheio (Giro atual absorve o lote)"
                else:
                    diag_txt = "🟢 Prazo Seguro (> 120d)"
                    mec_txt = "✅ Venda normal no balcão"
                desc_pct = 0.0
                preco_promo = preco_est
            else:
                precisa_p = True
                if d_pos <= 30:
                    diag_txt = f"🔥 Sobra {formatar_qtd_br(sobra_p)} un. (Urgente ≤30d)"
                    alvo_p = max(preco_piso * 1.02, preco_est * 0.76) if preco_est > 0 else 0.0
                    mec_txt = (
                        "🔥 Queima Balcão / Kit Lote Fechado (Piso + 2%)"
                        if saldo_l >= 6
                        else "🔥 Liquidação Imediata de Balcão (Piso + 2%)"
                    )
                elif d_pos <= 60:
                    diag_txt = f"🟠 Sobra {formatar_qtd_br(sobra_p)} un. (Atenção 31-60d)"
                    alvo_p = max(preco_piso * 1.06, preco_est * 0.82) if preco_est > 0 else 0.0
                    mec_txt = (
                        "⚡ Promoção Leve 6 Pague 5 / Atacado (-18%)"
                        if saldo_l >= 6
                        else "⚡ Desconto Progressivo no Balcão (-15% a -18%)"
                    )
                elif d_pos <= 90:
                    diag_txt = f"🟡 Sobra {formatar_qtd_br(sobra_p)} un. (Preventivo 61-90d)"
                    alvo_p = max(preco_piso * 1.10, preco_est * 0.88) if preco_est > 0 else 0.0
                    mec_txt = "🎯 Combo Fazendeiro / Campanha WhatsApp (-12%)"
                else:
                    diag_txt = f"🔵 Sobra {formatar_qtd_br(sobra_p)} un. (91-120d)"
                    alvo_p = max(preco_piso * 1.14, preco_est * 0.92) if preco_est > 0 else 0.0
                    mec_txt = "📢 Foco Equipe de Vendas (-8%)"

                preco_promo = min(alvo_p, preco_est) if preco_est > 0 else 0.0
                desc_pct = (
                    max(0.0, ((preco_est - preco_promo) / preco_est) * 100.0)
                    if preco_est > 0
                    else 0.0
                )

        if preco_promo > 0 and custo_u > 0:
            imposto_r = preco_promo * (float(aliquota_impostos_pct) / 100.0)
            lucro_liq_u = preco_promo - imposto_r - custo_u
            mg_liq_pct = (lucro_liq_u / preco_promo) * 100.0
        else:
            mg_liq_pct = 0.0

        sobra_proj_list.append(sobra_p)
        cap_sobra_list.append(cap_sobra)
        preco_atual_list.append(round(preco_est, 2))
        tem_preco_real_list.append(tem_preco_real)
        origem_preco_list.append(origem_p_txt)
        preco_piso_list.append(round(preco_piso, 2))
        preco_promo_list.append(round(preco_promo, 2))
        desc_sug_list.append(round(desc_pct, 1))
        margem_liq_promo_list.append(round(mg_liq_pct, 1))
        meta_giro_promo_list.append(round(meta_giro_p, 2))
        diagnostico_escala_list.append(diag_txt)
        mecanica_ia_list.append(mec_txt)
        precisa_promo_list.append(precisa_p)

    df_f["sobra_projetada"] = sobra_proj_list
    df_f["capital_sobra"] = cap_sobra_list
    df_f["preco_atual_est"] = preco_atual_list
    df_f["tem_preco_real"] = tem_preco_real_list
    df_f["origem_preco"] = origem_preco_list
    df_f["preco_piso_imposto"] = preco_piso_list
    df_f["preco_promo_sug"] = preco_promo_list
    df_f["desconto_sug_pct"] = desc_sug_list
    df_f["margem_liq_promo_pct"] = margem_liq_promo_list
    df_f["meta_giro_dia"] = meta_giro_promo_list
    df_f["diagnostico_giro_fefo"] = diagnostico_escala_list
    df_f["mecanica_ia"] = mecanica_ia_list
    df_f["precisa_promocao"] = precisa_promo_list
    df_f["eh_mp"] = [
        identificar_produto_mp(c, d, grupos_sku_custom, mp_custom_map)
        for c, d in zip(df_f["codigo"], df_f["descricao"])
    ]
    return df_f.drop(columns=["_ord_dias", "_saldo_vendavel"]).reset_index(drop=True)


def gerar_textos_campanha_promocional_fefo(
    codigo: str,
    descricao: str,
    lote: str,
    validade: str,
    dias_vencer: int,
    saldo_lote: float,
    sobra_proj: float,
    custo_unit: float,
    preco_de: float,
    preco_por: float,
    preco_piso: float,
    desconto_pct: float,
    aliquota_imp_pct: float,
    mecanica_sugerida: str,
    meta_giro_dia: float,
    exibir_preco_de_whatsapp: bool = True,
) -> tuple[str, str]:
    economia_un = max(0.0, preco_de - preco_por)
    economia_lote_3 = economia_un * 3.0
    receita_total_lote = saldo_lote * preco_por
    imposto_total_lote = receita_total_lote * (aliquota_imp_pct / 100.0)
    custo_total_lote = saldo_lote * custo_unit
    resultado_liq_lote = receita_total_lote - imposto_total_lote - custo_total_lote
    margem_liq_pct = ((resultado_liq_lote / receita_total_lote) * 100.0) if receita_total_lote > 0 else 0.0

    if exibir_preco_de_whatsapp and economia_un > 0.01:
        detalhe_lote_3 = (
            f" (levando 3 un., você economiza *{formatar_moeda_br(economia_lote_3)}*)"
            if saldo_lote >= 3
            else ""
        )
        bloco_preco_wpp = (
            f"💰 De: ~{formatar_moeda_br(preco_de)}~\n"
            f"🔥 *Por apenas: {formatar_moeda_br(preco_por)} à vista!* (*-{formatar_num_br(desconto_pct, 1)}%* de desconto)\n"
            f"📉 Economia imediata de *{formatar_moeda_br(economia_un)} por unidade*{detalhe_lote_3}!\n\n"
        )
    else:
        bloco_preco_wpp = (
            f"🔥 *Preço Especial de Lote: {formatar_moeda_br(preco_por)} à vista!*\n\n"
        )

    txt_whatsapp_cliente = (
        f"🌾 *OPORTUNIDADE ESPECIAL ESTEIO RURAL — LOTE PROMOCIONAL!* 🌾\n\n"
        f"📦 *{descricao}*\n"
        f"✅ Lote selecionado p/ giro rápido (Validade: *{validade or 'Consultar'}* — *{formatar_qtd_br(saldo_lote)} un.* disponíveis)\n\n"
        f"{bloco_preco_wpp}"
        f"⚡ *Condição válida exclusivamente enquanto durar este lote ({formatar_qtd_br(saldo_lote)} unidades).*\n"
        f"📲 Responda aqui no WhatsApp ou fale com nossos vendedores no balcão para reservar o seu!"
    )

    txt_briefing_equipe = (
        f"🎯 *META DE ESCOAMENTO FEFO — EQUIPE DE VENDAS ESTEIO RURAL*\n"
        f"• *Produto:* [{codigo}] {descricao}\n"
        f"• *Lote Prioritário:* {lote or 'S/L'}  |  *Validade:* {validade or '-'} ({dias_vencer} dias restantes)\n"
        f"• *Saldo no Lote:* {formatar_qtd_br(saldo_lote)} un.  |  *Sobra Projetada s/ Ação:* {formatar_qtd_br(sobra_proj)} un.\n"
        f"• *Mecânica Recomendada:* {mecanica_sugerida}\n"
        f"• *Preço Tabela:* {formatar_moeda_br(preco_de)}  ➔  *Preço Promocional:* {formatar_moeda_br(preco_por)} (-{formatar_num_br(desconto_pct, 1)}%)\n"
        f"• *Piso Mínimo (Custo C1 + {formatar_num_br(aliquota_imp_pct, 1)}% Impostos):* {formatar_moeda_br(preco_piso)} "
        f"(Margem líquida na promoção: {formatar_pct_br(margem_liq_pct, 1)})\n"
        f"• *Meta da Equipe:* Vender pelo menos *{formatar_num_br(meta_giro_dia, 1)} un./dia* para zerar o lote antes do vencimento "
        f"e recuperar *{formatar_moeda_br(receita_total_lote)}* em caixa!"
    )
    return txt_whatsapp_cliente, txt_briefing_equipe




# ==============================================================================
# 2. CURVA ABC FINANCEIRA (PARETO 80 / 15 / 5)
# ==============================================================================


def calcular_tabela_curva_abc(
    df_estoque_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    incluir_zerados: bool = False,
    df_catalogo_extra: pd.DataFrame = None,
) -> pd.DataFrame:
    if (df_estoque_ref is None or df_estoque_ref.empty) and (df_catalogo_extra is None or df_catalogo_extra.empty):
        return pd.DataFrame()
    if df_estoque_ref is not None and not df_estoque_ref.empty:
        df_est_sku = df_estoque_ref.groupby("codigo", as_index=False).agg(
            descricao=("descricao", "first"),
            saldo_geral=("saldo_geral", "first"),
        )
    else:
        df_est_sku = pd.DataFrame(columns=["codigo", "descricao", "saldo_geral"])

    if incluir_zerados and df_catalogo_extra is not None and not df_catalogo_extra.empty:
        df_cat_limpo = (
            df_catalogo_extra[["codigo", "descricao"]]
            .dropna(subset=["codigo"])
            .drop_duplicates(subset=["codigo"], keep="first")
        )
        cods_ja_no_est = set(df_est_sku["codigo"].unique())
        df_faltantes = df_cat_limpo[~df_cat_limpo["codigo"].isin(cods_ja_no_est)].copy()
        if not df_faltantes.empty:
            df_faltantes["saldo_geral"] = 0.0
            df_est_sku = pd.concat([df_est_sku, df_faltantes[["codigo", "descricao", "saldo_geral"]]], ignore_index=True)

    if df_custos_ref is not None and not df_custos_ref.empty:
        df_abc = df_est_sku.merge(df_custos_ref[["codigo", "custo_unitario"]], on="codigo", how="left")
        df_abc["custo_unitario"] = df_abc["custo_unitario"].fillna(0.0)
    else:
        df_abc = df_est_sku.copy()
        df_abc["custo_unitario"] = 0.0

    df_abc["valor_estoque"] = df_abc["saldo_geral"].clip(lower=0.0) * df_abc["custo_unitario"]
    df_pos = (
        df_abc[df_abc["valor_estoque"] > 0]
        .sort_values(["valor_estoque", "codigo"], ascending=[False, True])
        .copy()
    )
    total_fin = float(df_pos["valor_estoque"].sum()) if not df_pos.empty else 0.0
    if total_fin > 0:
        part_exata = (df_pos["valor_estoque"] / total_fin) * 100.0
        acum_exato = (df_pos["valor_estoque"].cumsum() / total_fin) * 100.0
        acum_anterior = acum_exato - part_exata
        df_pos["part_pct"] = part_exata.round(2)
        df_pos["acum_pct"] = acum_exato.round(2)
        df_pos["classe_abc_curta"] = acum_anterior.apply(
            lambda p: "Classe A" if p < 80.0 else ("Classe B" if p < 95.0 else "Classe C")
        )
        df_pos["classe_abc"] = acum_anterior.apply(
            lambda p: "Classe A (Até 80%)" if p < 80.0 else ("Classe B (80% a 95%)" if p < 95.0 else "Classe C (95% a 100%)")
        )
    elif not incluir_zerados:
        return pd.DataFrame()

    if not incluir_zerados:
        return df_pos.reset_index(drop=True)

    df_zero = (
        df_abc[df_abc["valor_estoque"] <= 0]
        .sort_values(["saldo_geral", "custo_unitario", "descricao"], ascending=[False, False, True])
        .copy()
    )
    if not df_zero.empty:
        df_zero["part_pct"] = 0.0
        df_zero["acum_pct"] = 100.0 if total_fin > 0 else 0.0
        df_zero["classe_abc_curta"] = "Sem Saldo/Custo"
        df_zero["classe_abc"] = [
            "⚪ Saldo Zerado (R$ 0,00)" if float(sg) <= 0 else "⚪ Sem Custo no ERP (R$ 0,00)"
            for sg in df_zero["saldo_geral"]
        ]
        df_final_abc = pd.concat([df_pos, df_zero], ignore_index=True)
    else:
        df_final_abc = df_pos
    return df_final_abc.reset_index(drop=True)




# ==============================================================================
# 3. AUDITORIA FISCAL (NF x C1 x T1), RESOLUÇÃO TEMPORAL VETORIZADA E DESCONTOS
# ==============================================================================


def atualizar_custos_via_entradas_df(
    df_custos_atual: pd.DataFrame,
    df_custos_novos_entrada: pd.DataFrame,
    data_entrada_iso: str = "",
    df_entradas_historico: pd.DataFrame = None,
    limite_alerta_variacao_pct: float = 20.0,
    tolerancia_frete_pct: float = 1.5,
) -> tuple[pd.DataFrame, dict]:
    """
    Faz o Upsert seletivo na tabela de custos a partir dos custos unitários apurados na Entrada:
    1) Só atualiza o custo se a data da entrada for >= à última entrada daquele SKU (proteção contra NF antiga sobrescrever custo mais novo).
    2) Detecta alertas de variação brusca de custo (>= 20%), altas acima da tolerância de frete/imposto e alertas de custo inalterado (0,0% — possível esquecimento fiscal).
    3) Retorna os registros detalhados para auditoria fiscal mesmo quando a atualização automática do C1 está desmarcada.
    """
    info_vazio = {
        "qtd_atualizados": 0,
        "qtd_inseridos": 0,
        "qtd_ignorados_data_antiga": 0,
        "exemplos_ignorados_data": [],
        "qtd_alertas_variacao": 0,
        "exemplos_variacao": [],
        "qtd_altas_acima_tolerancia": 0,
        "exemplos_altas_tolerancia": [],
        "qtd_inalterados": 0,
        "exemplos_inalterados": [],
        "registros_auditoria": [],
    }
    if df_custos_novos_entrada is None or df_custos_novos_entrada.empty:
        return padronizar_dataframe(df_custos_atual, "custos"), info_vazio
    df_novos = df_custos_novos_entrada[df_custos_novos_entrada["custo_unitario"] > 0].copy()
    if df_novos.empty:
        return padronizar_dataframe(df_custos_atual, "custos"), info_vazio
    df_base_c = (
        padronizar_dataframe(df_custos_atual, "custos")
        if (df_custos_atual is not None and not df_custos_atual.empty)
        else padronizar_dataframe(pd.DataFrame(), "custos")
    )
    mapa_custo_atual = (
        dict(zip(df_base_c["codigo"], df_base_c["custo_unitario"]))
        if not df_base_c.empty
        else {}
    )
    mapa_desc_atual = (
        dict(zip(df_base_c["codigo"], df_base_c["descricao"]))
        if not df_base_c.empty
        else {}
    )
    cods_existentes = set(df_base_c["codigo"].unique()) if not df_base_c.empty else set()

    mapa_ult_data_ent = {}
    if (
        df_entradas_historico is not None
        and not df_entradas_historico.empty
        and "codigo" in df_entradas_historico.columns
        and "data" in df_entradas_historico.columns
    ):
        df_e_hist = df_entradas_historico[df_entradas_historico["qtd_entrada"] > 0].copy()
        if not df_e_hist.empty:
            dt_e_s = converter_datas_deterministico(df_e_hist["data"])
            df_e_hist["_dt_iso"] = dt_e_s.dt.strftime("%Y-%m-%d").fillna("")
            df_e_hist = df_e_hist[df_e_hist["_dt_iso"] != ""]
            if not df_e_hist.empty:
                mapa_ult_data_ent = df_e_hist.groupby("codigo")["_dt_iso"].max().to_dict()

    dt_ent_iso_str = str(data_entrada_iso).strip()
    tol_pct = max(float(tolerancia_frete_pct), 0.0)
    linhas_validas = []
    ignorados_data = []
    alertas_var = []
    altas_tol_list = []
    inalterados_custo = []
    registros_auditoria = []

    for _, r_n in df_novos.iterrows():
        cod = str(r_n["codigo"]).strip()
        desc_item = str(r_n.get("descricao", "")).strip() or str(mapa_desc_atual.get(cod, "")).strip()
        custo_novo = float(r_n["custo_unitario"])
        custo_antigo = float(mapa_custo_atual.get(cod, 0.0))
        ult_dt_sku = mapa_ult_data_ent.get(cod, "")

        if dt_ent_iso_str and ult_dt_sku and dt_ent_iso_str < ult_dt_sku and custo_antigo > 0.0:
            dt_ult_fmt = pd.to_datetime(ult_dt_sku, format="%Y-%m-%d", errors="coerce")
            str_ult = dt_ult_fmt.strftime("%d/%m") if pd.notna(dt_ult_fmt) else ult_dt_sku
            ignorados_data.append(f"SKU {cod} (mantido {formatar_moeda_br(custo_antigo)} de {str_ult})")
            var_ign = ((custo_novo - custo_antigo) / custo_antigo) * 100.0
            registros_auditoria.append(
                {
                    "Código": cod,
                    "Descrição": desc_item,
                    "Custo Anterior (R$)": custo_antigo,
                    "Custo na NF (R$)": custo_novo,
                    "Variação (%)": round(var_ign, 2),
                    "Status Auditoria Fiscal": f"🛡️ Ignorado (NF anterior à entrada de {str_ult})",
                }
            )
            continue

        var_pct = 0.0
        if custo_antigo > 0.0:
            var_pct = ((custo_novo - custo_antigo) / custo_antigo) * 100.0
            diff_abs = abs(custo_novo - custo_antigo)
            if diff_abs < 0.005 or abs(var_pct) < 0.05:
                inalterados_custo.append(f"SKU {cod} ({formatar_moeda_br(custo_novo)})")
                status_aud = "🔎 Custo Inalterado (0,0% — Conferir Fiscal)"
            elif abs(var_pct) >= float(limite_alerta_variacao_pct):
                alertas_var.append(
                    (
                        abs(var_pct),
                        f"SKU {cod} ({formatar_moeda_br(custo_antigo)} ➔ {formatar_moeda_br(custo_novo)} | {formatar_pct_br(var_pct, 1, com_sinal=True)})",
                    )
                )
                status_aud = f"⚠️ Variação Brusca ({formatar_pct_br(var_pct, 1, com_sinal=True)})"
            elif var_pct > tol_pct and diff_abs >= 0.02:
                altas_tol_list.append(
                    (
                        var_pct,
                        f"SKU {cod} ({formatar_moeda_br(custo_antigo)} ➔ {formatar_moeda_br(custo_novo)} | {formatar_pct_br(var_pct, 1, com_sinal=True)})",
                    )
                )
                status_aud = f"📈 Alta na NF ({formatar_pct_br(var_pct, 1, com_sinal=True)} — Conferir C1)"
            elif abs(var_pct) <= tol_pct or diff_abs < 0.02:
                status_aud = f"✔️ Dentro da Tolerância ({formatar_pct_br(var_pct, 1, com_sinal=True)})"
            else:
                status_aud = f"📉 Redução na NF ({formatar_pct_br(var_pct, 1, com_sinal=True)})"
        else:
            status_aud = "🆕 Novo Custo Cadastrado"

        registros_auditoria.append(
            {
                "Código": cod,
                "Descrição": desc_item,
                "Custo Anterior (R$)": custo_antigo,
                "Custo na NF (R$)": custo_novo,
                "Variação (%)": round(var_pct, 2),
                "Status Auditoria Fiscal": status_aud,
            }
        )
        linhas_validas.append(r_n)

    if not linhas_validas:
        return df_base_c, {
            "qtd_atualizados": 0,
            "qtd_inseridos": 0,
            "qtd_ignorados_data_antiga": len(ignorados_data),
            "exemplos_ignorados_data": ignorados_data[:6],
            "qtd_alertas_variacao": 0,
            "exemplos_variacao": [],
            "qtd_altas_acima_tolerancia": 0,
            "exemplos_altas_tolerancia": [],
            "qtd_inalterados": 0,
            "exemplos_inalterados": [],
            "registros_auditoria": registros_auditoria,
        }

    mapa_t1_atual = (
        dict(zip(df_base_c["codigo"], df_base_c["preco_tabela"]))
        if (not df_base_c.empty and "preco_tabela" in df_base_c.columns)
        else {}
    )
    df_novos_validos = pd.DataFrame(linhas_validas)[["codigo", "descricao", "custo_unitario"]].copy()
    df_novos_validos["preco_tabela"] = df_novos_validos["codigo"].map(mapa_t1_atual).fillna(0.0)
    cods_aplicados = set(df_novos_validos["codigo"].unique())
    qtd_atualizados = len(cods_aplicados & cods_existentes)
    qtd_inseridos = len(cods_aplicados - cods_existentes)
    alertas_var.sort(key=lambda x: x[0], reverse=True)
    altas_tol_list.sort(key=lambda x: x[0], reverse=True)

    df_combinado = pd.concat([df_base_c, df_novos_validos], ignore_index=True)
    df_final_c = padronizar_dataframe(df_combinado, "custos")
    return df_final_c, {
        "qtd_atualizados": qtd_atualizados,
        "qtd_inseridos": qtd_inseridos,
        "qtd_ignorados_data_antiga": len(ignorados_data),
        "exemplos_ignorados_data": ignorados_data[:6],
        "qtd_alertas_variacao": len(alertas_var),
        "exemplos_variacao": [x[1] for x in alertas_var[:8]],
        "qtd_altas_acima_tolerancia": len(altas_tol_list),
        "exemplos_altas_tolerancia": [x[1] for x in altas_tol_list[:8]],
        "qtd_inalterados": len(inalterados_custo),
        "exemplos_inalterados": inalterados_custo[:10],
        "registros_auditoria": registros_auditoria,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def resolver_custo_e_t1_temporal_saidas(
    df_saidas_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    df_entradas_ref: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Resolve de forma 100% vetorizada (`pd.merge_asof` + `@st.cache_data`) o Custo Unitário (C1)
    e o Preço Tabela (T1) vigentes NA DATA DE CADA VENDA, cruzando `saidas_diarias` com o
    histórico cronológico de `entradas_diarias`:
    - Se houve NF de Entrada posterior à venda (`dt_ent > dt_venda`) com reajuste relevante (> 1,5%):
      1) Existindo NF anterior ou no dia (`dt_ent <= dt_venda`), aplica o custo histórico daquela NF
         e neutraliza o T1 novo para não gerar falso desconto.
      2) Não existindo NF anterior (lote antigo do estoque inicial vendido antes do reajuste) e
         sendo o custo da NF posterior incompatível com o preço de venda (`custo_nf_post > pv_un * 1.005`),
         marca `pre_reajuste = True` e `custo_u_efetivo = 0.0` (excluído da base de margem para
         não fabricar falso prejuízo nem inflar a margem com CMV zerado).
    """
    import numpy as np

    if df_saidas_ref is None or df_saidas_ref.empty:
        return pd.DataFrame()
    df_s = df_saidas_ref.copy()
    df_s["_orig_idx"] = np.arange(len(df_s), dtype=np.int64)

    cod_s = df_s["codigo"].fillna("").astype(str).str.strip()
    df_s["_cod_norm"] = cod_s

    if df_custos_ref is not None and not df_custos_ref.empty:
        cod_c = df_custos_ref["codigo"].fillna("").astype(str).str.strip()
        mapa_c1 = dict(zip(cod_c, pd.to_numeric(df_custos_ref["custo_unitario"], errors="coerce").fillna(0.0)))
        if "preco_tabela" in df_custos_ref.columns:
            mapa_t1 = dict(zip(cod_c, pd.to_numeric(df_custos_ref["preco_tabela"], errors="coerce").fillna(0.0)))
        else:
            mapa_t1 = {}
    else:
        mapa_c1 = {}
        mapa_t1 = {}

    c1_at_arr = cod_s.map(mapa_c1).fillna(0.0).to_numpy(dtype=float)
    t1_at_arr = cod_s.map(mapa_t1).fillna(0.0).to_numpy(dtype=float)

    tem_entradas_validas = (
        df_entradas_ref is not None
        and not df_entradas_ref.empty
        and "qtd_entrada" in df_entradas_ref.columns
        and "valor_entrada" in df_entradas_ref.columns
        and "data" in df_entradas_ref.columns
    )
    if not tem_entradas_validas:
        df_s["custo_u_efetivo"] = c1_at_arr
        df_s["t1_efetivo"] = t1_at_arr
        df_s["pre_reajuste"] = False
        df_s["tem_custo_historico"] = c1_at_arr > 0.0
        df_s["motivo_temporal"] = ""
        return df_s.drop(columns=["_orig_idx", "_cod_norm"])

    df_e_v = df_entradas_ref[
        (df_entradas_ref["qtd_entrada"] > 0) & (df_entradas_ref["valor_entrada"] > 0)
    ].copy()
    if df_e_v.empty:
        df_s["custo_u_efetivo"] = c1_at_arr
        df_s["t1_efetivo"] = t1_at_arr
        df_s["pre_reajuste"] = False
        df_s["tem_custo_historico"] = c1_at_arr > 0.0
        df_s["motivo_temporal"] = ""
        return df_s.drop(columns=["_orig_idx", "_cod_norm"])

    df_e_v["_dt_nf_ts"] = converter_datas_deterministico(df_e_v["data"])
    df_e_v["_cod_norm"] = df_e_v["codigo"].fillna("").astype(str).str.strip()
    df_e_v = df_e_v[df_e_v["_dt_nf_ts"].notna() & (df_e_v["_cod_norm"] != "")].copy()
    if df_e_v.empty:
        df_s["custo_u_efetivo"] = c1_at_arr
        df_s["t1_efetivo"] = t1_at_arr
        df_s["pre_reajuste"] = False
        df_s["tem_custo_historico"] = c1_at_arr > 0.0
        df_s["motivo_temporal"] = ""
        return df_s.drop(columns=["_orig_idx", "_cod_norm"])

    grp_nf = (
        df_e_v.groupby(["_cod_norm", "_dt_nf_ts"], as_index=False)
        .agg(qtd_entrada=("qtd_entrada", "sum"), valor_entrada=("valor_entrada", "sum"))
        .sort_values(["_dt_nf_ts", "_cod_norm"])
        .reset_index(drop=True)
    )
    grp_nf["_custo_nf"] = (grp_nf["valor_entrada"] / grp_nf["qtd_entrada"]).round(4)

    df_s["_dt_venda_ts"] = converter_datas_deterministico(df_s["data"])
    df_s["_c1_at"] = c1_at_arr
    df_s["_t1_at"] = t1_at_arr

    mask_valid_s = df_s["_dt_venda_ts"].notna() & (df_s["_cod_norm"] != "")
    df_s_valid = df_s.loc[mask_valid_s].sort_values(["_dt_venda_ts", "_cod_norm"]).reset_index(drop=True)
    df_s_invalid = df_s.loc[~mask_valid_s].copy()

    if not df_s_invalid.empty:
        df_s_invalid["custo_u_efetivo"] = df_s_invalid["_c1_at"]
        df_s_invalid["t1_efetivo"] = df_s_invalid["_t1_at"]
        df_s_invalid["pre_reajuste"] = False
        df_s_invalid["tem_custo_historico"] = df_s_invalid["_c1_at"] > 0.0
        df_s_invalid["motivo_temporal"] = ""

    if not df_s_valid.empty:
        nf_ant_ref = grp_nf[["_cod_norm", "_dt_nf_ts", "_custo_nf"]].rename(
            columns={"_dt_nf_ts": "_dt_nf_ant", "_custo_nf": "_custo_nf_ant"}
        )
        nf_post_ref = grp_nf[["_cod_norm", "_dt_nf_ts", "_custo_nf"]].rename(
            columns={"_dt_nf_ts": "_dt_nf_post", "_custo_nf": "_custo_nf_post"}
        )

        df_m = pd.merge_asof(
            df_s_valid,
            nf_ant_ref,
            left_on="_dt_venda_ts",
            right_on="_dt_nf_ant",
            by="_cod_norm",
            direction="backward",
            allow_exact_matches=True,
        )
        df_m = pd.merge_asof(
            df_m,
            nf_post_ref,
            left_on="_dt_venda_ts",
            right_on="_dt_nf_post",
            by="_cod_norm",
            direction="forward",
            allow_exact_matches=False,
        )

        c1_v = df_m["_c1_at"].to_numpy(dtype=float)
        t1_v = df_m["_t1_at"].to_numpy(dtype=float)
        qtd_v = pd.to_numeric(df_m["qtd_saida"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vlr_v = pd.to_numeric(df_m["valor_venda"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        pv_un = np.where((qtd_v > 0.0) & (vlr_v > 0.0), vlr_v / np.maximum(qtd_v, 1e-9), 0.0)

        has_post = df_m["_dt_nf_post"].notna().to_numpy(dtype=bool)
        has_ant = df_m["_dt_nf_ant"].notna().to_numpy(dtype=bool)
        c_ant = df_m["_custo_nf_ant"].fillna(0.0).to_numpy(dtype=float)
        c_post = df_m["_custo_nf_post"].fillna(0.0).to_numpy(dtype=float)

        # Caso B: tem NF anterior e NF posterior -> só troca para custo anterior se houve reajuste real (> 1,5%)
        reaj_com_ant = (
            has_post
            & has_ant
            & (c_ant > 0.0)
            & ((np.abs(c_post - c_ant) / np.maximum(c_ant, 1e-9)) > 0.015)
        )
        # Caso C: sem NF anterior, mas entrou NF posterior com custo acima do preço vendido
        reaj_sem_ant = (
            has_post
            & (~has_ant)
            & (pv_un > 0.0)
            & (c_post > (pv_un * 1.005))
        )

        custo_ef = np.where(reaj_com_ant, c_ant, np.where(reaj_sem_ant, 0.0, c1_v))
        t1_ef = np.where(reaj_com_ant | reaj_sem_ant, 0.0, t1_v)
        pre_reaj = reaj_com_ant | reaj_sem_ant
        tem_hist = np.where(reaj_com_ant, True, np.where(reaj_sem_ant, False, c1_v > 0.0))

        motivos = np.full(len(df_m), "", dtype=object)
        idx_b = np.where(reaj_com_ant)[0]
        if len(idx_b) > 0:
            dt_ant_strs = df_m.loc[idx_b, "_dt_nf_ant"].dt.strftime("%d/%m/%Y").to_numpy()
            dt_post_strs = df_m.loc[idx_b, "_dt_nf_post"].dt.strftime("%d/%m/%Y").to_numpy()
            for pos_i, d_a_s, d_p_s in zip(idx_b, dt_ant_strs, dt_post_strs):
                motivos[pos_i] = (
                    f"⏳ Custo NF {d_a_s} ({formatar_moeda_br(c_ant[pos_i])}) — anterior ao reajuste de {d_p_s}"
                )
        idx_c = np.where(reaj_sem_ant)[0]
        if len(idx_c) > 0:
            dt_post_strs_c = df_m.loc[idx_c, "_dt_nf_post"].dt.strftime("%d/%m/%Y").to_numpy()
            for pos_i, d_p_s in zip(idx_c, dt_post_strs_c):
                motivos[pos_i] = (
                    f"⏳ Venda anterior ao reajuste (NF em {d_p_s} a {formatar_moeda_br(c_post[pos_i])} | C1 atual {formatar_moeda_br(c1_v[pos_i])})"
                )

        df_m["custo_u_efetivo"] = custo_ef
        df_m["t1_efetivo"] = t1_ef
        df_m["pre_reajuste"] = pre_reaj
        df_m["tem_custo_historico"] = tem_hist
        df_m["motivo_temporal"] = motivos
        df_m = df_m.drop(columns=["_dt_nf_ant", "_custo_nf_ant", "_dt_nf_post", "_custo_nf_post"])
        df_comb = pd.concat([df_m, df_s_invalid], ignore_index=True) if not df_s_invalid.empty else df_m
    else:
        df_comb = df_s_invalid

    df_comb = df_comb.sort_values("_orig_idx").reset_index(drop=True)
    return df_comb.drop(columns=["_orig_idx", "_cod_norm", "_dt_venda_ts", "_c1_at", "_t1_at"])


def auditar_descontos_saidas_df(
    df_saidas_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    limite_desconto_pct: float = 5.0,
    df_entradas_ref: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Cruza as Saídas Reais (Valor Total da Proposta / Qtd. Saída) com o Preço Tabela Oficial T1
    vigente na data da venda (ignorando vendas anteriores a reajustes de preço) e retorna os
    produtos vendidos com desconto > limite_desconto_pct (padrão 5%).
    """
    if (
        df_saidas_ref is None
        or df_saidas_ref.empty
        or df_custos_ref is None
        or df_custos_ref.empty
        or "preco_tabela" not in df_custos_ref.columns
        or "valor_venda" not in df_saidas_ref.columns
    ):
        return pd.DataFrame()

    df_s = df_saidas_ref[(df_saidas_ref["qtd_saida"] > 0) & (df_saidas_ref["valor_venda"] > 0)].copy()
    if df_s.empty:
        return pd.DataFrame()

    df_s = resolver_custo_e_t1_temporal_saidas(
        df_saidas_ref=df_s,
        df_custos_ref=df_custos_ref,
        df_entradas_ref=df_entradas_ref,
    )
    df_s["preco_tabela_t1"] = df_s["t1_efetivo"].fillna(0.0)
    df_s["custo_c1"] = df_s["custo_u_efetivo"].fillna(0.0)
    df_s = df_s[df_s["preco_tabela_t1"] > 0.0].copy()
    if df_s.empty:
        return pd.DataFrame()

    df_s["preco_vendido_un"] = (df_s["valor_venda"] / df_s["qtd_saida"]).round(4)
    df_s["desconto_pct"] = (
        ((df_s["preco_tabela_t1"] - df_s["preco_vendido_un"]) / df_s["preco_tabela_t1"]) * 100.0
    ).round(2)
    df_s["desconto_total_rs"] = (
        (df_s["preco_tabela_t1"] - df_s["preco_vendido_un"]).clip(lower=0.0) * df_s["qtd_saida"]
    ).round(2)
    df_s["valor_cheio_t1_total"] = (df_s["preco_tabela_t1"] * df_s["qtd_saida"]).round(2)
    df_s["margem_real_pct"] = [
        round(((pv - c1) / pv) * 100.0, 2) if (pv > 0 and c1 > 0) else 0.0
        for pv, c1 in zip(df_s["preco_vendido_un"], df_s["custo_c1"])
    ]
    df_s["margem_t1_pct"] = [
        round(((t1 - c1) / t1) * 100.0, 2) if (t1 > 0 and c1 > 0) else 0.0
        for t1, c1 in zip(df_s["preco_tabela_t1"], df_s["custo_c1"])
    ]

    df_alerta = df_s[df_s["desconto_pct"] > float(limite_desconto_pct)].copy()
    if df_alerta.empty:
        return pd.DataFrame()

    df_alerta["status_desconto"] = [
        f"🚨 Desconto Alto (-{formatar_num_br(d, 1)}%)" if float(d) >= 10.0 else f"⚠️ Acima de 5% (-{formatar_num_br(d, 1)}%)"
        for d in df_alerta["desconto_pct"]
    ]
    return df_alerta.sort_values(["desconto_total_rs", "desconto_pct"], ascending=[False, False]).reset_index(drop=True)


def _classificar_divergencia_nf_vs_c1(
    custo_nf: float,
    c1_ref: float,
    t1_ref: float = 0.0,
    tolerancia_frete_pct: float = 1.5,
) -> tuple[str, int, str]:
    """
    Classifica a relação entre o Custo Unitário da NF de Entrada e o Custo C1 do ERP:
    - Retorna (categoria_curta, prioridade_ordenacao, descricao_status)
    """
    if custo_nf <= 0.0 or c1_ref <= 0.0:
        return "sem_comparacao", 9, ""
    var_pct = ((custo_nf - c1_ref) / c1_ref) * 100.0
    diff_abs = abs(custo_nf - c1_ref)
    tol = max(float(tolerancia_frete_pct), 0.0)
    if diff_abs < 0.02 or abs(var_pct) <= tol:
        return "alinhado", 5, f"✔️ Alinhado c/ NF ({formatar_pct_br(var_pct, 1, com_sinal=True)})"
    if var_pct > tol:
        alerta_t1 = ""
        if t1_ref > 0.0 and custo_nf >= t1_ref:
            alerta_t1 = " | ⚠️ Custo NF ≥ Tabela T1!"
        return (
            "esquecimento_fiscal",
            0,
            f"🚨 NF Acima do C1 ({formatar_pct_br(var_pct, 1, com_sinal=True)} | NF {formatar_moeda_br(custo_nf)} vs C1 {formatar_moeda_br(c1_ref)}) — Fiscal não atualizou C1{alerta_t1}",
        )
    if var_pct <= -30.0:
        return (
            "bonificacao",
            2,
            f"🎁 Bonificação / Desconto Promocional NF ({formatar_pct_br(var_pct, 1, com_sinal=True)} | NF {formatar_moeda_br(custo_nf)} ➔ C1 mantido)",
        )
    return (
        "reducao_nf",
        2,
        f"📉 Custo NF Menor que C1 ({formatar_pct_br(var_pct, 1, com_sinal=True)} | NF {formatar_moeda_br(custo_nf)} vs C1 {formatar_moeda_br(c1_ref)}) — Conferir Redução",
    )


def auditar_ajustes_c1_t1_df(
    df_custos_antes: pd.DataFrame,
    df_custos_novos: pd.DataFrame,
    df_entradas_recentes: pd.DataFrame = None,
    registros_auditoria_nf: list = None,
    limite_alerta_c1_sem_t1_pct: float = 2.0,
    tolerancia_frete_pct: float = 1.5,
) -> tuple[pd.DataFrame, dict]:
    """
    Audita a carga diária da planilha Custos (C1) & Tabela (T1):
    1) Detecta todo item com alteração > 0,01% em C1 ou T1, além de novos cadastros.
    2) Cruza com a última NF de Entrada (janela padrão de 3 dias) e separa:
       - 🚨 NF Acima do C1 (suspeita de esquecimento fiscal acima da tolerância de frete/imposto)
       - 🎁 Bonificação / Desconto Promocional NF (queda >= 30%)
       - 📉 Custo NF Menor que C1 (queda moderada entre tolerância e 30%)
    3) Dispara alerta de defasagem quando C1 sobe (>= 2%) mas T1 fica parado (0,0%).
    """
    resumo_vazio = {
        "total_ajustes": 0,
        "qtd_c1_alterado": 0,
        "qtd_t1_alterado": 0,
        "qtd_defasagem_t1": 0,
        "qtd_esquecimento_fiscal": 0,
        "qtd_reducao_nf": 0,
        "qtd_bonificacao_mantida": 0,
        "qtd_novos": 0,
        "exemplos_defasagem_t1": [],
        "exemplos_esquecimento_fiscal": [],
    }
    if df_custos_novos is None or df_custos_novos.empty:
        return pd.DataFrame(), resumo_vazio

    mapa_c1_db = {}
    mapa_t1_db = {}
    mapa_desc_db = {}
    if df_custos_antes is not None and not df_custos_antes.empty:
        mapa_c1_db = dict(zip(df_custos_antes["codigo"], df_custos_antes["custo_unitario"].fillna(0.0)))
        if "preco_tabela" in df_custos_antes.columns:
            mapa_t1_db = dict(zip(df_custos_antes["codigo"], df_custos_antes["preco_tabela"].fillna(0.0)))
        mapa_desc_db = dict(zip(df_custos_antes["codigo"], df_custos_antes["descricao"].fillna("")))

    mapa_custo_nf = {}
    mapa_data_nf = {}
    mapa_c1_pre_nf = {}
    if (
        df_entradas_recentes is not None
        and not df_entradas_recentes.empty
        and "qtd_entrada" in df_entradas_recentes.columns
        and "valor_entrada" in df_entradas_recentes.columns
    ):
        df_e_rec = df_entradas_recentes[
            (df_entradas_recentes["qtd_entrada"] > 0) & (df_entradas_recentes["valor_entrada"] > 0)
        ].copy()
        if not df_e_rec.empty:
            if "data" in df_e_rec.columns:
                df_e_rec = df_e_rec.sort_values("data")
                grp_e_dt = (
                    df_e_rec.groupby(["codigo", "data"], as_index=False)
                    .agg(qtd_entrada=("qtd_entrada", "sum"), valor_entrada=("valor_entrada", "sum"))
                    .sort_values("data")
                )
                for _, r_e in grp_e_dt.iterrows():
                    cod_e = str(r_e["codigo"]).strip()
                    if cod_e:
                        mapa_custo_nf[cod_e] = round(float(r_e["valor_entrada"]) / float(r_e["qtd_entrada"]), 4)
                        dt_s_e = str(r_e["data"]).strip()
                        dt_p_e = pd.to_datetime(dt_s_e, format="%Y-%m-%d", errors="coerce")
                        mapa_data_nf[cod_e] = dt_p_e.strftime("%d/%m/%Y") if pd.notna(dt_p_e) else dt_s_e
            else:
                for _, r_e in df_e_rec.iterrows():
                    cod_e = str(r_e["codigo"]).strip()
                    if cod_e:
                        mapa_custo_nf[cod_e] = round(float(r_e["valor_entrada"]) / float(r_e["qtd_entrada"]), 4)

    if registros_auditoria_nf:
        for reg_nf in registros_auditoria_nf:
            cod_nf = str(reg_nf.get("Código", "")).strip()
            if not cod_nf:
                continue
            try:
                v_nf = float(reg_nf.get("Custo na NF (R$)", 0.0) or 0.0)
                v_ant_nf = float(reg_nf.get("Custo Anterior (R$)", 0.0) or 0.0)
                if v_nf > 0.0:
                    mapa_custo_nf[cod_nf] = v_nf
                if v_ant_nf > 0.0:
                    mapa_c1_pre_nf[cod_nf] = v_ant_nf
            except (ValueError, TypeError):
                continue

    linhas_aud = []
    qtd_c1_alt = 0
    qtd_t1_alt = 0
    qtd_def_t1 = 0
    qtd_esq_fiscal = 0
    qtd_red_nf = 0
    qtd_bonif = 0
    qtd_novos = 0
    exemplos_def = []
    exemplos_esq = []

    for _, r_n in df_custos_novos.iterrows():
        cod = str(r_n["codigo"]).strip()
        if not cod:
            continue
        desc = str(r_n.get("descricao", "")).strip() or str(mapa_desc_db.get(cod, "")).strip()
        c1_novo = float(r_n.get("custo_unitario", 0.0) or 0.0)
        t1_novo = float(r_n.get("preco_tabela", 0.0) or 0.0)
        c1_db = float(mapa_c1_db.get(cod, 0.0))
        t1_ant = float(mapa_t1_db.get(cod, 0.0))
        custo_nf = float(mapa_custo_nf.get(cod, 0.0))
        dt_nf_txt = str(mapa_data_nf.get(cod, "-")).strip() or "-"
        c1_pre_nf = float(mapa_c1_pre_nf.get(cod, 0.0))

        # Se uma NF recente sobrescreveu temporariamente o C1 no banco, recupera o C1 original pré-NF como base
        if c1_pre_nf > 0.0 and custo_nf > 0.0 and abs(c1_db - custo_nf) < 0.005:
            c1_ant = c1_pre_nf
        else:
            c1_ant = c1_db

        var_c1_pct = ((c1_novo - c1_ant) / c1_ant * 100.0) if c1_ant > 0.0 else 0.0
        var_t1_pct = ((t1_novo - t1_ant) / t1_ant * 100.0) if (t1_ant > 0.0 and t1_novo > 0.0) else 0.0
        mg_t1_ant = ((t1_ant - c1_ant) / t1_ant * 100.0) if (t1_ant > 0.0 and c1_ant > 0.0) else 0.0
        mg_t1_nova = ((t1_novo - c1_novo) / t1_novo * 100.0) if (t1_novo > 0.0 and c1_novo > 0.0) else 0.0

        eh_novo = (c1_ant <= 0.0) and (c1_novo > 0.0)
        c1_mudou = (not eh_novo) and (c1_ant > 0.0) and (abs(var_c1_pct) > 0.01) and (abs(c1_novo - c1_ant) >= 0.005)
        t1_mudou = (t1_ant > 0.0) and (t1_novo > 0.0) and (abs(var_t1_pct) > 0.01) and (abs(t1_novo - t1_ant) >= 0.005)

        cat_nf, prio_nf, status_nf_detalhe = _classificar_divergencia_nf_vs_c1(
            custo_nf=custo_nf,
            c1_ref=c1_novo,
            t1_ref=t1_novo,
            tolerancia_frete_pct=tolerancia_frete_pct,
        )
        tem_divergencia_nf_c1 = (not eh_novo) and (cat_nf in ("esquecimento_fiscal", "bonificacao", "reducao_nf"))
        defasagem_t1 = (
            c1_mudou
            and (var_c1_pct >= float(limite_alerta_c1_sem_t1_pct))
            and (t1_ant > 0.0)
            and (t1_novo > 0.0)
            and (not t1_mudou)
        )
        nf_confirmada = c1_mudou and (cat_nf == "alinhado")

        if not (eh_novo or c1_mudou or t1_mudou or tem_divergencia_nf_c1):
            continue

        var_nf_abs_pct = abs(((custo_nf - c1_novo) / c1_novo * 100.0)) if (custo_nf > 0.0 and c1_novo > 0.0) else 0.0

        if eh_novo:
            qtd_novos += 1
            status_txt = "🆕 Novo Produto Cadastrado"
            prioridade = 3
        elif cat_nf == "esquecimento_fiscal":
            qtd_esq_fiscal += 1
            if c1_mudou:
                qtd_c1_alt += 1
            if t1_mudou:
                qtd_t1_alt += 1
            status_txt = status_nf_detalhe
            exemplos_esq.append(
                f"SKU {cod} (NF {formatar_moeda_br(custo_nf)} vs C1 {formatar_moeda_br(c1_novo)})"
            )
            prioridade = 0
        elif defasagem_t1:
            qtd_def_t1 += 1
            qtd_c1_alt += 1
            delta_mg = mg_t1_nova - mg_t1_ant
            status_txt = (
                f"⚠️ C1 Subiu ({formatar_pct_br(var_c1_pct, 1, com_sinal=True)}) s/ Reajuste no T1 "
                f"(Margem {formatar_pct_br(delta_mg, 1, com_sinal=True)})"
            )
            exemplos_def.append(
                f"SKU {cod} (C1 {formatar_moeda_br(c1_ant)} ➔ {formatar_moeda_br(c1_novo)} | T1 parado em {formatar_moeda_br(t1_novo)})"
            )
            prioridade = 1
        elif cat_nf == "bonificacao":
            qtd_bonif += 1
            if c1_mudou:
                qtd_c1_alt += 1
            if t1_mudou:
                qtd_t1_alt += 1
            status_txt = status_nf_detalhe
            prioridade = 2
        elif cat_nf == "reducao_nf":
            qtd_red_nf += 1
            if c1_mudou:
                qtd_c1_alt += 1
            if t1_mudou:
                qtd_t1_alt += 1
            status_txt = status_nf_detalhe
            prioridade = 2
        elif c1_mudou and t1_mudou:
            qtd_c1_alt += 1
            qtd_t1_alt += 1
            tag_nf = " | Conf. NF" if nf_confirmada else ""
            status_txt = (
                f"🔄 Ajuste C1 ({formatar_pct_br(var_c1_pct, 1, com_sinal=True)}) & "
                f"T1 ({formatar_pct_br(var_t1_pct, 1, com_sinal=True)}){tag_nf}"
            )
            prioridade = 3
        elif c1_mudou:
            qtd_c1_alt += 1
            tag_nf = " (Confirmado pela NF)" if nf_confirmada else ""
            status_txt = f"💰 Ajuste Custo C1 ({formatar_pct_br(var_c1_pct, 1, com_sinal=True)}){tag_nf}"
            prioridade = 3
        else:
            qtd_t1_alt += 1
            status_txt = f"🏷️ Ajuste Tabela T1 ({formatar_pct_br(var_t1_pct, 1, com_sinal=True)})"
            prioridade = 4

        linhas_aud.append(
            {
                "_prio": prioridade,
                "_abs_var": max(abs(var_c1_pct), abs(var_t1_pct), var_nf_abs_pct),
                "Código": cod,
                "Descrição": desc,
                "Data NF": dt_nf_txt,
                "C1 Anterior (R$)": c1_ant,
                "C1 Novo (R$)": c1_novo,
                "Var. C1 (%)": round(var_c1_pct, 2),
                "Custo NF (R$)": custo_nf,
                "T1 Anterior (R$)": t1_ant,
                "T1 Novo (R$)": t1_novo,
                "Var. T1 (%)": round(var_t1_pct, 2),
                "Nova Margem T1 (%)": round(mg_t1_nova, 1),
                "Status Auditoria C1 & T1": status_txt,
            }
        )

    if not linhas_aud:
        return pd.DataFrame(), resumo_vazio

    df_res = (
        pd.DataFrame(linhas_aud)
        .sort_values(["_prio", "_abs_var", "Código"], ascending=[True, False, True])
        .drop(columns=["_prio", "_abs_var"])
        .reset_index(drop=True)
    )
    resumo = {
        "total_ajustes": len(df_res),
        "qtd_c1_alterado": qtd_c1_alt,
        "qtd_t1_alterado": qtd_t1_alt,
        "qtd_defasagem_t1": qtd_def_t1,
        "qtd_esquecimento_fiscal": qtd_esq_fiscal,
        "qtd_reducao_nf": qtd_red_nf,
        "qtd_bonificacao_mantida": qtd_bonif,
        "qtd_novos": qtd_novos,
        "exemplos_defasagem_t1": exemplos_def[:6],
        "exemplos_esquecimento_fiscal": exemplos_esq[:6],
    }
    return df_res, resumo


def auditar_fiscal_permanente_nf_c1_t1(
    df_entradas_ref: pd.DataFrame,
    df_custos_ref: pd.DataFrame,
    df_estoque_ref: pd.DataFrame = None,
    janela_dias_nf: int = 3,
    tolerancia_frete_pct: float = 1.5,
    margem_minima_t1_pct: float = 5.0,
) -> tuple[pd.DataFrame, dict]:
    """
    Auditoria Fiscal Permanente (Aba 5 — Seção 4):
    Recalcula diretamente das tabelas `entradas_diarias` e `custos` gravadas no Supabase (nunca some ao dar F5)
    todas as entradas com valor nos últimos `janela_dias_nf` dias (padrão 3 dias), identificando:
    1) 🚨 Esquecimento Fiscal: Custo da última NF acima do C1 atual (+tolerância de frete/imposto).
    2) ⚠️ Margem Comprimida / Prejuízo na Tabela T1: Custo da NF deixa margem vs. T1 abaixo do mínimo (ou Custo NF ≥ T1).
    3) ⚪ Sem Custo C1 Cadastrado: Item entrou com valor na NF mas continua com C1 = R$ 0,00.
    4) 🎁 Bonificação / Desconto Promocional NF (queda >= 30%) e 📉 Redução na NF (queda moderada).
    5) ✔️ Itens Alinhados (NF ≈ C1 dentro da tolerância).
    """
    resumo_vazio = {
        "total_itens_nf": 0,
        "qtd_esquecimento_fiscal": 0,
        "qtd_margem_t1_baixa": 0,
        "qtd_sem_c1": 0,
        "qtd_bonificacao": 0,
        "qtd_reducao_nf": 0,
        "qtd_alinhados": 0,
        "data_corte_br": "-",
    }
    if (
        df_entradas_ref is None
        or df_entradas_ref.empty
        or "qtd_entrada" not in df_entradas_ref.columns
        or "valor_entrada" not in df_entradas_ref.columns
    ):
        return pd.DataFrame(), resumo_vazio

    df_e_val = df_entradas_ref[
        (df_entradas_ref["qtd_entrada"] > 0) & (df_entradas_ref["valor_entrada"] > 0)
    ].copy()
    if df_e_val.empty:
        return pd.DataFrame(), resumo_vazio

    dt_s = converter_datas_deterministico(df_e_val["data"])
    df_e_val["_dt_ts"] = dt_s
    df_e_val = df_e_val[df_e_val["_dt_ts"].notna()].copy()
    if df_e_val.empty:
        return pd.DataFrame(), resumo_vazio

    dt_max_base = max(pd.Timestamp(hoje_br()), df_e_val["_dt_ts"].max())
    dt_corte_ts = dt_max_base - pd.Timedelta(days=int(janela_dias_nf))
    df_e_win = df_e_val[df_e_val["_dt_ts"] >= dt_corte_ts].copy()
    if df_e_win.empty:
        resumo_vazio["data_corte_br"] = dt_corte_ts.strftime("%d/%m/%Y")
        return pd.DataFrame(), resumo_vazio

    df_e_win["_dt_iso"] = df_e_win["_dt_ts"].dt.strftime("%Y-%m-%d")
    grp_dia = (
        df_e_win.groupby(["codigo", "_dt_iso"], as_index=False)
        .agg(
            descricao=("descricao", "last"),
            qtd_entrada=("qtd_entrada", "sum"),
            valor_entrada=("valor_entrada", "sum"),
        )
        .sort_values(["codigo", "_dt_iso"])
    )
    ult_por_sku = grp_dia.drop_duplicates(subset=["codigo"], keep="last").reset_index(drop=True)

    mapa_c1 = {}
    mapa_t1 = {}
    mapa_desc_c = {}
    if df_custos_ref is not None and not df_custos_ref.empty:
        mapa_c1 = dict(zip(df_custos_ref["codigo"], df_custos_ref["custo_unitario"].fillna(0.0)))
        if "preco_tabela" in df_custos_ref.columns:
            mapa_t1 = dict(zip(df_custos_ref["codigo"], df_custos_ref["preco_tabela"].fillna(0.0)))
        mapa_desc_c = dict(zip(df_custos_ref["codigo"], df_custos_ref["descricao"].fillna("")))

    mapa_saldo = {}
    if df_estoque_ref is not None and not df_estoque_ref.empty and "saldo_geral" in df_estoque_ref.columns:
        mapa_saldo = df_estoque_ref.groupby("codigo")["saldo_geral"].first().to_dict()

    linhas = []
    q_esq = 0
    q_mg_t1 = 0
    q_sem_c1 = 0
    q_bonif = 0
    q_red = 0
    q_alin = 0

    for _, r in ult_por_sku.iterrows():
        cod = str(r["codigo"]).strip()
        if not cod:
            continue
        desc = str(r.get("descricao", "")).strip() or str(mapa_desc_c.get(cod, "")).strip()
        qtd_nf = float(r["qtd_entrada"])
        vlr_nf = float(r["valor_entrada"])
        custo_nf = round(vlr_nf / qtd_nf, 4) if qtd_nf > 0 else 0.0
        dt_iso = str(r["_dt_iso"]).strip()
        dt_fmt = pd.to_datetime(dt_iso, format="%Y-%m-%d", errors="coerce")
        dt_br = dt_fmt.strftime("%d/%m/%Y") if pd.notna(dt_fmt) else dt_iso

        c1_at = float(mapa_c1.get(cod, 0.0))
        t1_at = float(mapa_t1.get(cod, 0.0))
        saldo_at = float(mapa_saldo.get(cod, 0.0))

        var_nf_c1 = ((custo_nf - c1_at) / c1_at * 100.0) if c1_at > 0.0 else 0.0
        mg_t1_nf = ((t1_at - custo_nf) / t1_at * 100.0) if (t1_at > 0.0 and custo_nf > 0.0) else 0.0

        t1_comprimido = (t1_at > 0.0) and (custo_nf > 0.0) and (mg_t1_nf < float(margem_minima_t1_pct))
        if t1_comprimido:
            q_mg_t1 += 1

        if c1_at <= 0.0:
            q_sem_c1 += 1
            prio = 1
            cat_filtro = "sem_c1"
            status_txt = f"⚪ Sem C1 no Cadastro (NF entrou a {formatar_moeda_br(custo_nf)})"
        else:
            cat_nf, prio_nf, status_base = _classificar_divergencia_nf_vs_c1(
                custo_nf=custo_nf,
                c1_ref=c1_at,
                t1_ref=t1_at,
                tolerancia_frete_pct=tolerancia_frete_pct,
            )
            cat_filtro = cat_nf
            prio = prio_nf
            status_txt = status_base
            if cat_nf == "esquecimento_fiscal":
                q_esq += 1
            elif cat_nf == "bonificacao":
                q_bonif += 1
            elif cat_nf == "reducao_nf":
                q_red += 1
            else:
                q_alin += 1
                if t1_comprimido:
                    prio = 1
                    cat_filtro = "margem_t1"
                    status_txt = (
                        f"⚠️ C1 Alinhado, mas Tabela T1 Comprimida (Margem {formatar_pct_br(mg_t1_nf, 1)} < {formatar_num_br(margem_minima_t1_pct, 0)}%)"
                    )

        linhas.append(
            {
                "_prio": prio,
                "_abs_var": abs(var_nf_c1),
                "_cat": cat_filtro,
                "_t1_comp": t1_comprimido,
                "Código": cod,
                "Descrição": desc,
                "Última NF": dt_br,
                "Qtd. NF": qtd_nf,
                "Custo Unit. NF (R$)": custo_nf,
                "Custo C1 Atual (R$)": c1_at,
                "Var. NF vs C1 (%)": round(var_nf_c1, 2),
                "Tabela T1 Atual (R$)": t1_at,
                "Margem T1 s/ NF (%)": round(mg_t1_nf, 1),
                "Saldo Estoque": saldo_at,
                "Diagnóstico Fiscal": status_txt,
            }
        )

    df_out = (
        pd.DataFrame(linhas)
        .sort_values(["_prio", "_abs_var", "Código"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    resumo = {
        "total_itens_nf": len(df_out),
        "qtd_esquecimento_fiscal": q_esq,
        "qtd_margem_t1_baixa": q_mg_t1,
        "qtd_sem_c1": q_sem_c1,
        "qtd_bonificacao": q_bonif,
        "qtd_reducao_nf": q_red,
        "qtd_alinhados": q_alin,
        "data_corte_br": dt_corte_ts.strftime("%d/%m/%Y"),
    }
    return df_out, resumo




# ==============================================================================
# 4. MOTOR DE GIRO SAZONAL, CONSUMO MP DE FÁBRICA E DETECÇÃO DE PICOS
# ==============================================================================


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_motor_giro_sazonal(
    df_estoque: pd.DataFrame,
    df_historico: pd.DataFrame,
    df_base_vendas: pd.DataFrame,
    df_custos: pd.DataFrame,
    dias_base_atual: int,
    janela_dias: int,
    incluir_sem_estoque: bool = True,
    df_entradas: pd.DataFrame = None,
    df_saidas: pd.DataFrame = None,
    grupos_sku_custom: dict = None,
    mp_custom_map: dict = None,
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
        if df_entradas is not None and not df_entradas.empty:
            frames_cat.append(df_entradas[["codigo", "descricao"]])
        if df_saidas is not None and not df_saidas.empty:
            frames_cat.append(df_saidas[["codigo", "descricao"]])
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
    df_saidas_sku = pd.DataFrame(
        columns=[
            "codigo",
            "giro_historico",
            "giro_historico_sem_pico",
            "desvio_diario",
            "mediana_diaria",
            "mad_diario",
            "saida_ult_dia",
            "data_ult_dia",
            "queda_pico_recente",
            "data_pico_recente",
            "saldo_antes_pico",
            "alerta_nf_nao_refletida",
        ]
    )
    datas_candidatas = set()
    if df_historico is not None and not df_historico.empty and "data" in df_historico.columns:
        datas_candidatas.update(df_historico["data"].dropna().unique())
    if df_entradas is not None and not df_entradas.empty and "data" in df_entradas.columns:
        datas_candidatas.update(df_entradas["data"].dropna().unique())
    if df_saidas is not None and not df_saidas.empty and "data" in df_saidas.columns:
        datas_candidatas.update(df_saidas["data"].dropna().unique())
    datas_todas = sorted([d for d in datas_candidatas if str(d).strip() != ""])
    if datas_todas:
        dt_max = pd.to_datetime(datas_todas[-1], format="%Y-%m-%d", errors="coerce")
        dt_corte = (
            (dt_max - pd.Timedelta(days=int(janela_dias))).strftime("%Y-%m-%d")
            if pd.notna(dt_max)
            else ""
        )
        df_h_win = (
            df_historico[df_historico["data"] >= dt_corte].copy()
            if (df_historico is not None and not df_historico.empty and dt_corte)
            else (df_historico.copy() if df_historico is not None else pd.DataFrame())
        )
        df_ent_win = (
            df_entradas[df_entradas["data"] >= dt_corte].copy()
            if (df_entradas is not None and not df_entradas.empty and dt_corte)
            else (df_entradas.copy() if df_entradas is not None else pd.DataFrame())
        )
        df_sai_win = (
            df_saidas[df_saidas["data"] >= dt_corte].copy()
            if (df_saidas is not None and not df_saidas.empty and dt_corte)
            else (df_saidas.copy() if df_saidas is not None else pd.DataFrame())
        )
        datas_hist = sorted(df_h_win["data"].unique()) if not df_h_win.empty else []
        quedas_por_sku = pd.DataFrame()
        saldo_prev_sku = pd.DataFrame()
        dias_por_coluna = {}
        primeiro_saldo_sku = pd.Series(dtype=float)
        ultimo_saldo_sku = pd.Series(dtype=float)
        nf_nao_refletida_sku = pd.Series(dtype=str)

        if not df_h_win.empty:
            chaves_dedup_h = ["codigo", "lote", "data"] if "lote" in df_h_win.columns else ["codigo", "data"]
            df_h_win = df_h_win.drop_duplicates(subset=chaves_dedup_h, keep="last")
            grade_geral = (
                df_h_win.groupby(["codigo", "data"], as_index=False)["saldo_geral"]
                .first()
            )
            todos_cods_grade = df_prod["codigo"].unique() if not df_prod.empty else grade_geral["codigo"].unique()
            pivot_geral = (
                grade_geral.pivot(index="codigo", columns="data", values="saldo_geral")
                .reindex(index=todos_cods_grade, columns=datas_hist)
                .fillna(0.0)
            )
            primeiro_saldo_sku = pivot_geral[datas_hist[0]]
            ultimo_saldo_sku = pivot_geral[datas_hist[-1]]

        if len(datas_hist) >= 2:
            deltas_geral = pivot_geral.diff(axis=1)
            cols_fim_transicao = datas_hist[1:]
            cols_transicao = datas_hist[:-1]
            mapa_col_transicao = dict(zip(cols_fim_transicao, cols_transicao))
            deltas_geral = deltas_geral[cols_fim_transicao].rename(columns=mapa_col_transicao)

            for idx_t, dt_ini_t in enumerate(cols_transicao):
                dt_fim_t = datas_hist[idx_t + 1]
                t1 = pd.to_datetime(dt_ini_t, format="%Y-%m-%d", errors="coerce")
                t2 = pd.to_datetime(dt_fim_t, format="%Y-%m-%d", errors="coerce")
                dias_por_coluna[dt_ini_t] = max(int((t2 - t1).days), 1) if (pd.notna(t1) and pd.notna(t2)) else 1

            entradas_transicao = pd.DataFrame(0.0, index=pivot_geral.index, columns=cols_transicao)
            if not df_ent_win.empty:
                df_ent_grp = df_ent_win.groupby(["codigo", "data"], as_index=False)["qtd_entrada"].sum()
                for idx_t, dt_ini_t in enumerate(cols_transicao):
                    dt_fim_t = datas_hist[idx_t + 1]
                    mask_int = (df_ent_grp["data"] >= dt_ini_t) & (df_ent_grp["data"] < dt_fim_t)
                    if mask_int.any():
                        soma_ent = df_ent_grp.loc[mask_int].groupby("codigo")["qtd_entrada"].sum()
                        novos_idx = soma_ent.index.difference(entradas_transicao.index)
                        if len(novos_idx) > 0:
                            entradas_transicao = entradas_transicao.reindex(entradas_transicao.index.union(novos_idx), fill_value=0.0)
                            deltas_geral = deltas_geral.reindex(entradas_transicao.index, fill_value=0.0)
                        entradas_transicao.loc[soma_ent.index, dt_ini_t] = soma_ent.values

            saidas_transicao = pd.DataFrame(0.0, index=entradas_transicao.index, columns=cols_transicao)
            cols_com_planilha_saida = set()
            if not df_sai_win.empty:
                df_sai_grp = df_sai_win.groupby(["codigo", "data"], as_index=False)["qtd_saida"].sum()
                for idx_t, dt_ini_t in enumerate(cols_transicao):
                    dt_fim_t = datas_hist[idx_t + 1]
                    mask_sai = (df_sai_grp["data"] >= dt_ini_t) & (df_sai_grp["data"] < dt_fim_t)
                    if mask_sai.any():
                        cols_com_planilha_saida.add(dt_ini_t)
                        soma_sai = df_sai_grp.loc[mask_sai].groupby("codigo")["qtd_saida"].sum()
                        novos_idx = soma_sai.index.difference(saidas_transicao.index)
                        if len(novos_idx) > 0:
                            saidas_transicao = saidas_transicao.reindex(saidas_transicao.index.union(novos_idx), fill_value=0.0)
                            entradas_transicao = entradas_transicao.reindex(saidas_transicao.index, fill_value=0.0)
                            deltas_geral = deltas_geral.reindex(saidas_transicao.index, fill_value=0.0)
                        saidas_transicao.loc[soma_sai.index, dt_ini_t] = soma_sai.values

            # 1. Comparação direta das planilhas de Estoque Diário (captura quedas de saldo e consumo interno de fábrica)
            queda_direta = (-deltas_geral[cols_transicao]).clip(lower=0.0)

            # Identifica quais SKUs são Matéria-Prima de Fábrica (saída via Ordem de Produção)
            mapa_desc_prod = (
                dict(zip(df_prod["codigo"], df_prod["descricao"]))
                if (df_prod is not None and not df_prod.empty and "descricao" in df_prod.columns)
                else {}
            )
            eh_mp_por_idx = pd.Series(
                [
                    identificar_produto_mp(c, mapa_desc_prod.get(c, ""), grupos_sku_custom, mp_custom_map)
                    for c in entradas_transicao.index
                ],
                index=entradas_transicao.index,
            )

            # 2. Consumo em dia com NF de Entrada:
            # - Para itens de revenda (não MP) sem saída na planilha de vendas daquele dia (saidas_transicao <= 0)
            #   em que o estoque subiu menos que a NF (delta > 0 e delta < entrada): consumo = entrada - delta.
            # - Para itens de Produção / Matéria-Prima (MP), cuja saída ocorre por Ordem de Produção (fora das saídas faturadas):
            #   consumo_bruto = entrada - delta, protegido contra NF ainda não refletida no saldo físico (> 3x giro de referência).
            del_trans = deltas_geral[cols_transicao]
            sem_saida_no_sku_dia = saidas_transicao <= 0.0
            mask_alta_parcial_sku = (
                (entradas_transicao > 0.0)
                & sem_saida_no_sku_dia
                & (del_trans > 0.0)
                & (del_trans < entradas_transicao)
            )
            consumo_parcial_prelim = (entradas_transicao - del_trans).clip(lower=0.0).where(
                mask_alta_parcial_sku, 0.0
            )

            # Calcula giro médio de referência nos dias sem NF (ou fallback giro_base) para auditar consumo de MP
            quedas_prelim = queda_direta.combine(consumo_parcial_prelim, lambda s1, s2: s1.combine(s2, max))
            quedas_prelim = quedas_prelim.combine(saidas_transicao, lambda s1, s2: s1.combine(s2, max))
            dias_sem_nf_mask = entradas_transicao <= 0.0
            soma_sem_nf = quedas_prelim.where(dias_sem_nf_mask, 0.0).sum(axis=1)
            qtd_dias_sem_nf = dias_sem_nf_mask.sum(axis=1).replace(0, float("nan"))
            mapa_giro_base_idx = (
                dict(zip(df_prod["codigo"], df_prod["giro_base"]))
                if (df_prod is not None and not df_prod.empty and "giro_base" in df_prod.columns)
                else {}
            )
            giro_base_s = pd.Series(
                [float(mapa_giro_base_idx.get(c, 0.0)) for c in entradas_transicao.index],
                index=entradas_transicao.index,
            )
            giro_ref_mp = (soma_sem_nf / qtd_dias_sem_nf).fillna(0.0)
            giro_ref_mp = giro_ref_mp.where(giro_ref_mp > 0.0, giro_base_s)

            consumo_bruto_mp_mat = (entradas_transicao - del_trans).clip(lower=0.0)
            mask_mp_anomalia_nf = (
                (entradas_transicao > 0.0)
                & eh_mp_por_idx.values[:, None]
                & (
                    ((giro_ref_mp.values[:, None] > 0.0) & (consumo_bruto_mp_mat >= (giro_ref_mp.values[:, None] * 3.0)))
                    | ((giro_ref_mp.values[:, None] <= 0.0) & ((del_trans + saidas_transicao) <= 0.0))
                )
            )
            mask_mp_producao_normal = (
                (entradas_transicao > 0.0)
                & sem_saida_no_sku_dia
                & eh_mp_por_idx.values[:, None]
                & (~mask_mp_anomalia_nf)
            )
            consumo_em_alta = consumo_bruto_mp_mat.where(
                mask_alta_parcial_sku | mask_mp_producao_normal, 0.0
            )

            # Detecção de NF de Entrada sem reflexo no saldo ou consumo anormal de MP (> 3x giro médio)
            mask_nf_nao_refletida = (
                (entradas_transicao > 0.0)
                & (~eh_mp_por_idx.values[:, None])
                & ((del_trans + saidas_transicao) <= 0.0)
            )
            alertas_nf_dict = {}
            for cod_nf in entradas_transicao.index:
                if eh_mp_por_idx.loc[cod_nf] and mask_mp_anomalia_nf.loc[cod_nf].any():
                    cols_mp_a = [c for c in cols_transicao if mask_mp_anomalia_nf.loc[cod_nf, c]]
                    ult_dt_mp = cols_mp_a[-1]
                    qtd_nf_mp = float(entradas_transicao.loc[cod_nf, ult_dt_mp])
                    del_mp_v = float(del_trans.loc[cod_nf, ult_dt_mp])
                    cons_bruto_mp = max(0.0, qtd_nf_mp - del_mp_v)
                    dt_mp_fmt = pd.to_datetime(ult_dt_mp, format="%Y-%m-%d", errors="coerce")
                    str_dt_mp = dt_mp_fmt.strftime("%d/%m") if pd.notna(dt_mp_fmt) else str(ult_dt_mp)
                    alertas_nf_dict[cod_nf] = (
                        f"⚠️ MP NF +{formatar_qtd_br(qtd_nf_mp)} ({str_dt_mp}) | Apurado {formatar_qtd_br(cons_bruto_mp)} (>3x giro / conferir saldo)"
                    )
                elif (not eh_mp_por_idx.loc[cod_nf]) and mask_nf_nao_refletida.loc[cod_nf].any():
                    cols_nf = [c for c in cols_transicao if mask_nf_nao_refletida.loc[cod_nf, c]]
                    ult_dt_nf = cols_nf[-1]
                    qtd_nf = float(entradas_transicao.loc[cod_nf, ult_dt_nf])
                    dt_nf_fmt = pd.to_datetime(ult_dt_nf, format="%Y-%m-%d", errors="coerce")
                    str_dt_nf = dt_nf_fmt.strftime("%d/%m") if pd.notna(dt_nf_fmt) else str(ult_dt_nf)
                    alertas_nf_dict[cod_nf] = f"⏳ NF +{formatar_qtd_br(qtd_nf)} ({str_dt_nf}) s/ reflexo no saldo"
            if alertas_nf_dict:
                nf_nao_refletida_sku = pd.Series(alertas_nf_dict)

            # 3. Cruzamento com Saídas/Vendas Diárias via max() (nunca soma duplicado com a queda de estoque)
            quedas_por_sku = queda_direta.combine(consumo_em_alta, lambda s1, s2: s1.combine(s2, max))
            quedas_por_sku = quedas_por_sku.combine(saidas_transicao, lambda s1, s2: s1.combine(s2, max))

            saldo_prev_base = (
                pivot_geral
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            entradas_alinhadas = (
                entradas_transicao
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            deltas_alinhados = (
                deltas_geral
                .reindex(index=quedas_por_sku.index, columns=cols_transicao)
                .fillna(0.0)
            )
            entrada_nova_no_dia = entradas_alinhadas.where(
                (deltas_alinhados > 0.0) | (saldo_prev_base <= 0.0), 0.0
            )
            saldo_prev_sku = (saldo_prev_base + entrada_nova_no_dia).combine(
                quedas_por_sku, lambda s1, s2: s1.combine(s2, max)
            ).fillna(0.0)

        if not df_sai_win.empty:
            df_sai_grp_all = df_sai_win.groupby(["codigo", "data"], as_index=False)["qtd_saida"].sum()
            if len(datas_hist) >= 2:
                mask_fora = (df_sai_grp_all["data"] < datas_hist[0]) | (df_sai_grp_all["data"] >= datas_hist[-1])
                df_sai_extra = df_sai_grp_all.loc[mask_fora].copy()
            else:
                df_sai_extra = df_sai_grp_all.copy()
            if not df_sai_extra.empty:
                pivot_sai_extra = df_sai_extra.pivot(index="codigo", columns="data", values="qtd_saida").fillna(0.0)
                for col_dt_ex in pivot_sai_extra.columns:
                    dias_por_coluna[col_dt_ex] = 1
                if quedas_por_sku.empty:
                    quedas_por_sku = pivot_sai_extra.copy()
                    saldo_base_ex = primeiro_saldo_sku.reindex(pivot_sai_extra.index).fillna(0.0)
                    saldo_prev_sku = pivot_sai_extra.add(saldo_base_ex, axis=0)
                else:
                    idx_unido = quedas_por_sku.index.union(pivot_sai_extra.index)
                    quedas_por_sku = quedas_por_sku.reindex(idx_unido, fill_value=0.0)
                    saldo_prev_sku = saldo_prev_sku.reindex(idx_unido, fill_value=0.0)
                    saldo_base_ini = primeiro_saldo_sku.reindex(idx_unido).fillna(0.0)
                    saldo_base_fim = ultimo_saldo_sku.reindex(idx_unido).fillna(0.0)
                    for col_dt_ex in pivot_sai_extra.columns:
                        col_s_ex = pivot_sai_extra[col_dt_ex].reindex(idx_unido, fill_value=0.0)
                        quedas_por_sku[col_dt_ex] = col_s_ex
                        if datas_hist and col_dt_ex < datas_hist[0]:
                            saldo_prev_sku[col_dt_ex] = col_s_ex + saldo_base_ini
                        else:
                            saldo_prev_sku[col_dt_ex] = saldo_base_fim.combine(col_s_ex, max)
                    quedas_por_sku = quedas_por_sku[sorted(quedas_por_sku.columns)]
                    saldo_prev_sku = saldo_prev_sku[sorted(saldo_prev_sku.columns)]

        if not quedas_por_sku.empty:
            ts_hist = [pd.to_datetime(d, format="%Y-%m-%d", errors="coerce") for d in datas_hist]
            ts_hist = [t for t in ts_hist if pd.notna(t)]
            ts_mov = [pd.to_datetime(d, format="%Y-%m-%d", errors="coerce") for d in quedas_por_sku.columns]
            ts_mov = [t for t in ts_mov if pd.notna(t)]
            inicios_validos = ts_hist + ts_mov
            fins_validos = ts_hist + [t + pd.Timedelta(days=1) for t in ts_mov]
            if inicios_validos and fins_validos:
                d_ini = min(inicios_validos)
                d_fim = max(fins_validos)
                dias_corridos_total = int((d_fim - d_ini).days)
            else:
                dias_corridos_total = 1
            intervalo_historico_dias = max(dias_corridos_total, quedas_por_sku.shape[1], 1)
            peso_historico = min(float(intervalo_historico_dias) / float(janela_dias), 1.0)
            saida_total = quedas_por_sku.sum(axis=1)
            cols_mov = list(quedas_por_sku.columns)
            div_dias_todas = pd.Series({c: float(dias_por_coluna.get(c, 1)) for c in cols_mov})
            saldo_prev_alinhado = saldo_prev_sku.reindex(index=quedas_por_sku.index, columns=cols_mov).fillna(0.0)
            mask_com_estoque_ou_venda = (saldo_prev_alinhado > 0.0) | (quedas_por_sku > 0.0)
            dias_disponiveis_sku = mask_com_estoque_ou_venda.mul(div_dias_todas, axis=1).sum(axis=1).clip(lower=1.0)

            taxa_diaria_todas_df = quedas_por_sku.divide(div_dias_todas, axis=1)
            taxa_disp_df = taxa_diaria_todas_df.where(mask_com_estoque_ou_venda)
            media_disp_s = saida_total / dias_disponiveis_sku
            qtd_int_disp_s = mask_com_estoque_ou_venda.sum(axis=1)
            sq_diff_disp = (taxa_disp_df.sub(media_disp_s, axis=0) ** 2).fillna(0.0)
            var_diaria_s = sq_diff_disp.mul(div_dias_todas, axis=1).sum(axis=1) / (dias_disponiveis_sku - 1.0).clip(lower=1.0)
            desvio_diario_s = (var_diaria_s ** 0.5).where(qtd_int_disp_s >= 2, 0.0).fillna(0.0)
            mediana_diaria_s = taxa_disp_df.median(axis=1).fillna(0.0)
            mad_diario_s = taxa_disp_df.sub(mediana_diaria_s, axis=0).abs().median(axis=1).fillna(0.0)

            ult_col = cols_mov[-1]
            dt_ult_fmt = pd.to_datetime(ult_col, format="%Y-%m-%d", errors="coerce")
            str_ult_dia = dt_ult_fmt.strftime("%d/%m") if pd.notna(dt_ult_fmt) else str(ult_col)
            saida_ult_dia_s = quedas_por_sku[ult_col]

            cols_recentes_pico = cols_mov[-min(len(cols_mov), 5):]
            quedas_rec_df = quedas_por_sku[cols_recentes_pico]
            div_dias_rec = pd.Series({c: float(dias_por_coluna.get(c, 1)) for c in cols_recentes_pico})
            taxa_diaria_rec_df = quedas_rec_df.divide(div_dias_rec, axis=1)

            queda_pico_s = taxa_diaria_rec_df.max(axis=1)
            col_data_pico_s = taxa_diaria_rec_df.idxmax(axis=1)

            saldo_antes_pico_vals = []
            data_pico_fmt_vals = []
            queda_bruta_col_pico_vals = []
            dias_col_pico_vals = []
            for cod_idx, col_dt in col_data_pico_s.items():
                if cod_idx in saldo_prev_sku.index and col_dt in saldo_prev_sku.columns:
                    val_prev = saldo_prev_sku.loc[cod_idx, col_dt]
                    saldo_antes_pico_vals.append(0.0 if pd.isna(val_prev) else float(val_prev))
                else:
                    saldo_antes_pico_vals.append(0.0)
                queda_bruta_col_pico_vals.append(float(quedas_por_sku.loc[cod_idx, col_dt]))
                teve_disp_pico = bool(mask_com_estoque_ou_venda.loc[cod_idx, col_dt])
                dias_col_pico_vals.append(float(dias_por_coluna.get(col_dt, 1)) if teve_disp_pico else 0.0)
                dt_p = pd.to_datetime(col_dt, format="%Y-%m-%d", errors="coerce")
                data_pico_fmt_vals.append(dt_p.strftime("%d/%m") if pd.notna(dt_p) else str(col_dt))

            queda_bruta_pico_s = pd.Series(queda_bruta_col_pico_vals, index=quedas_por_sku.index)
            dias_sem_pico_s = pd.Series(
                [max(float(dias_disponiveis_sku.loc[cod_i]) - dp, 1.0) for cod_i, dp in zip(quedas_por_sku.index, dias_col_pico_vals)],
                index=quedas_por_sku.index,
            )
            saida_sem_pico = (saida_total - queda_bruta_pico_s).clip(lower=0.0)
            alerta_nf_s = nf_nao_refletida_sku.reindex(quedas_por_sku.index).fillna("")

            df_saidas_sku = pd.DataFrame(
                {
                    "codigo": quedas_por_sku.index,
                    "giro_historico": (saida_total / dias_disponiveis_sku).values,
                    "giro_historico_sem_pico": (saida_sem_pico / dias_sem_pico_s).values,
                    "desvio_diario": desvio_diario_s.values,
                    "mediana_diaria": mediana_diaria_s.values,
                    "mad_diario": mad_diario_s.values,
                    "saida_ult_dia": saida_ult_dia_s.values,
                    "data_ult_dia": str_ult_dia,
                    "queda_pico_recente": queda_pico_s.values,
                    "data_pico_recente": data_pico_fmt_vals,
                    "saldo_antes_pico": saldo_antes_pico_vals,
                    "alerta_nf_nao_refletida": alerta_nf_s.values,
                }
            )
    df_calc = df_prod.merge(df_saidas_sku, on="codigo", how="left")
    df_calc["giro_historico"] = df_calc["giro_historico"].fillna(0.0)
    df_calc["giro_historico_sem_pico"] = df_calc["giro_historico_sem_pico"].fillna(0.0)
    df_calc["desvio_diario"] = df_calc["desvio_diario"].fillna(0.0)
    df_calc["mediana_diaria"] = df_calc["mediana_diaria"].fillna(0.0)
    df_calc["mad_diario"] = df_calc["mad_diario"].fillna(0.0)
    df_calc["saida_ult_dia"] = df_calc["saida_ult_dia"].fillna(0.0)
    df_calc["data_ult_dia"] = df_calc["data_ult_dia"].fillna("-")
    df_calc["queda_pico_recente"] = df_calc["queda_pico_recente"].fillna(0.0)
    df_calc["data_pico_recente"] = df_calc["data_pico_recente"].fillna("-")
    df_calc["saldo_antes_pico"] = df_calc["saldo_antes_pico"].fillna(0.0)
    df_calc["alerta_nf_nao_refletida"] = df_calc["alerta_nf_nao_refletida"].fillna("")
    df_calc["giro_ponderado"] = (
        (df_calc["giro_historico"] * peso_historico)
        + (df_calc["giro_base"] * (1.0 - peso_historico))
    )
    df_calc["giro_ponderado_sem_pico"] = (
        (df_calc["giro_historico_sem_pico"] * peso_historico)
        + (df_calc["giro_base"] * (1.0 - peso_historico))
    )

    # Sazonalidade Automática por SKU (compara mesmo período do ano anterior com a média anual do próprio SKU)
    mapa_fator_saz_sku = {}
    if datas_todas:
        dt_max_yoy = pd.to_datetime(datas_todas[-1], format="%Y-%m-%d", errors="coerce")
        dt_min_yoy = pd.to_datetime(datas_todas[0], format="%Y-%m-%d", errors="coerce")
        if pd.notna(dt_max_yoy) and pd.notna(dt_min_yoy) and int((dt_max_yoy - dt_min_yoy).days) >= 330:
            dt_base_ini_iso = (dt_max_yoy - pd.Timedelta(days=395)).strftime("%Y-%m-%d")
            dt_base_fim_iso = (dt_max_yoy - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            dt_saz_ini_iso = (dt_max_yoy - pd.Timedelta(days=380)).strftime("%Y-%m-%d")
            dt_saz_fim_iso = (dt_max_yoy - pd.Timedelta(days=335)).strftime("%Y-%m-%d")

            df_s_yoy = (
                df_saidas[(df_saidas["data"] >= dt_base_ini_iso) & (df_saidas["data"] <= dt_base_fim_iso)].copy()
                if (df_saidas is not None and not df_saidas.empty and "data" in df_saidas.columns)
                else pd.DataFrame()
            )
            df_h_yoy = (
                df_historico[(df_historico["data"] >= dt_base_ini_iso) & (df_historico["data"] <= dt_base_fim_iso)].copy()
                if (df_historico is not None and not df_historico.empty and "data" in df_historico.columns)
                else pd.DataFrame()
            )
            if not df_s_yoy.empty:
                df_s_grp_y = df_s_yoy.groupby(["codigo", "data"], as_index=False)["qtd_saida"].sum()
                piv_s_y = df_s_grp_y.pivot(index="codigo", columns="data", values="qtd_saida").fillna(0.0)
                if not df_h_yoy.empty:
                    piv_h_y = (
                        df_h_yoy.drop_duplicates(subset=["codigo", "data"], keep="last")
                        .pivot(index="codigo", columns="data", values="saldo_geral")
                        .reindex(index=piv_s_y.index, columns=piv_s_y.columns)
                        .ffill(axis=1)
                        .fillna(0.0)
                    )
                    mask_disp_y = (piv_h_y > 0.0) | (piv_s_y > 0.0)
                else:
                    mask_disp_y = pd.DataFrame(True, index=piv_s_y.index, columns=piv_s_y.columns)

                cols_yoy_all = sorted(piv_s_y.columns)
                cols_yoy_saz = [c for c in cols_yoy_all if dt_saz_ini_iso <= c <= dt_saz_fim_iso]
                if len(cols_yoy_all) >= 60 and len(cols_yoy_saz) >= 15:
                    dias_all_y = mask_disp_y[cols_yoy_all].sum(axis=1)
                    dias_saz_y = mask_disp_y[cols_yoy_saz].sum(axis=1)
                    soma_all_y = piv_s_y[cols_yoy_all].where(mask_disp_y[cols_yoy_all], 0.0).sum(axis=1)
                    soma_saz_y = piv_s_y[cols_yoy_saz].where(mask_disp_y[cols_yoy_saz], 0.0).sum(axis=1)
                    for cod_y in piv_s_y.index:
                        d_a = float(dias_all_y.loc[cod_y])
                        d_s = float(dias_saz_y.loc[cod_y])
                        if d_a >= 60.0 and d_s >= 15.0:
                            med_a = float(soma_all_y.loc[cod_y]) / d_a
                            med_s = float(soma_saz_y.loc[cod_y]) / d_s
                            if med_a > 0.0:
                                idx_raw = med_s / med_a
                                idx_clamped = min(max(idx_raw, 0.60), 2.20)
                                mapa_fator_saz_sku[cod_y] = 1.0 if abs(idx_clamped - 1.0) < 0.05 else round(idx_clamped, 3)

    df_calc["fator_sazonal_sku"] = df_calc["codigo"].map(mapa_fator_saz_sku).fillna(1.0)
    return df_calc, intervalo_historico_dias, peso_historico
