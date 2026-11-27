"""
ui/tab_compras.py — Aba 2: Sugestão de Compras, Ponto de Pedido, Pico Sazonal,
Cotação .xlsx e gestão de 'Já Comprei'.
"""
import re
import math
import unicodedata
from datetime import timedelta
import pandas as pd
import streamlit as st

from parsers import (
    DIAS_PADRAO_SONECA_COMPRA,
    hoje_br,
    formatar_num_br,
    formatar_qtd_br,
    formatar_moeda_br,
    formatar_pct_br,
    normalizar_codigo_sku,
    converter_datas_deterministico,
    padronizar_dataframe,
    gerar_excel_com_formulas_cotacao,
    ler_lista_produtos_cotacao,
)
from database import (
    gravar_tabela_sql,
    salvar_backup_automatico_sql,
    carregar_estado_completo,
)
from analytics import (
    calcular_motor_giro_sazonal,
)


def render_tab_compras(ctx: dict) -> None:
    """Renderiza a Aba 2 — Sugestão de Compras & Cotação."""
    db_supabase = ctx["db_supabase"]
    eh_usuario_admin = ctx["eh_usuario_admin"]
    nome_atual_logado = ctx["nome_atual_logado"]
    estado = ctx["estado"]
    df_estoque = ctx["df_estoque"]
    df_estoque_bruto = ctx["df_estoque_bruto"]
    df_historico = ctx["df_historico"]
    df_historico_bruto = ctx["df_historico_bruto"]
    df_entradas = ctx["df_entradas"]
    df_entradas_bruto = ctx["df_entradas_bruto"]
    df_saidas = ctx["df_saidas"]
    df_saidas_bruto = ctx["df_saidas_bruto"]
    df_custos = ctx["df_custos"]
    df_custos_rel = ctx["df_custos_rel"]
    df_base_vendas = ctx["df_base_vendas"]
    df_base_vendas_rel = ctx["df_base_vendas_rel"]
    df_pedidos_transito = ctx["df_pedidos_transito"]
    dias_base_atual = ctx["dias_base_atual"]
    grupos_sku_custom = ctx["grupos_sku_custom"]
    mp_custom_map = ctx["mp_custom_map"]
    codigos_em_transito = ctx["codigos_em_transito"]

    st.markdown("### 🛒 Sugestão de Compras, Radar de Ruptura, Pico Sazonal & Cotação")
    st.caption(
        "Cruza automaticamente Estoque + Entradas (NF) + Saídas/Vendas por data, destaca Ruptura Iminente e Pico Sazonal, "
        "permite marcar produtos como **'Já Comprei'** (ocultando-os por 15 dias com **Auto-Despertar** assim que entrarem na NF) "
        "e exporta a planilha de cotação com fórmulas vivas."
    )
    if "msg_transito_aba2" in st.session_state:
        st.success(st.session_state.pop("msg_transito_aba2"))
    desp_rec = estado.get("despertados_nf_recente", [])
    if desp_rec:
        st.info(
            f"🔔 **Auto-Despertar Automático:** **{formatar_num_br(len(desp_rec))} produto(s)** que estavam ocultos em "
            f"*'Já Comprei'* apareceram em planilha recente de **Entradas (NF)** e voltaram automaticamente ao monitoramento!"
        )

    with st.expander("📋 Importar Planilha de Produtos para Cotação Direcionada (Opcional)", expanded=False):
        arq_lista_cotacao = st.file_uploader(
            "Subir planilha com Código e Nome dos produtos (.xlsx, .xls ou .csv)",
            type=["xlsx", "xls", "csv"],
            key="up_lista_cotacao",
        )
        if arq_lista_cotacao is not None:
            st.success(
                "✅ Planilha de cotação ativa! Todos os produtos enviados abaixo serão mantidos na tabela e no Excel gerado (inclusive itens com sugestão 0)."
            )
    p1, p2, p3, p4 = st.columns([1.0, 1.0, 1.0, 2.5])
    janela_dias = p1.selectbox(
        "Janela de Giro (dias):",
        options=[15, 30, 45, 60, 90, 120, 180, 365],
        index=5,
        help="Escolha 120, 180 ou 365 dias para negociações de longo prazo e análise anual com fornecedores.",
    )
    cobertura_desejada = p2.number_input("Cobertura Alvo (dias):", min_value=5, max_value=180, value=120)
    lead_time = p3.number_input("Entrega / Lead (dias):", min_value=0, max_value=90, value=10)
    filtro_busca = p4.text_input(
        "🔍 Fornecedor / Linha / Produto (use vírgula p/ vários):",
        placeholder="Ex: tigre  |  roda d'água, gaxeta  |  joelho 25",
        help="Busca inteligente: ignora acentos/apóstrofos (encontra RODA D'AGUA, RODA DAGUA e RODA D AGUA), aceita palavras fora de ordem e múltiplos termos separados por vírgula.",
    )
    c_op1, c_op2, c_op3, c_op4, c_op5 = st.columns(5)
    with c_op1:
        incluir_zerados_com_giro = st.checkbox(
            "Incluir Saldo = 0 c/ giro",
            value=False,
        )
    with c_op2:
        usar_sugestao_reforcada_pico = st.checkbox(
            "⚡ Sugestão Reforçada (Pico)",
            value=True,
            help="Quando um produto sofre uma queda brusca em 1 dia (ex: D KELLBYOL caindo de 41 para 11), sugere recompor o lote consumido + cobertura regular.",
        )
    with c_op3:
        filtrar_apenas_ruptura = st.checkbox(
            "🔥 Apenas Ruptura Iminente",
            value=False,
            help="Mostra somente produtos com giro ativo cujo estoque atual acaba antes ou durante o prazo de entrega do fornecedor (Autonomia ≤ Entrega).",
        )
    with c_op4:
        filtrar_apenas_picos = st.checkbox(
            "🚨 Apenas Saídas de Pico",
            value=False,
            help="Filtra somente os produtos que tiveram queda brusca recente para você conferir se foi venda real ou ajuste no Siagri.",
        )
    with c_op5:
        mostrar_comprados_transito = st.checkbox(
            f"🚚 Mostrar 'Já Comprei' ({formatar_num_br(len(codigos_em_transito))})",
            value=False,
            help="Por padrão, produtos marcados como 'Já Comprei' ficam ocultos por 15 dias (ou até aparecerem na planilha de Entradas NF). Marque para exibi-los na tabela.",
        )

    mapa_silenciar_ate = (
        dict(zip(df_pedidos_transito["codigo"], df_pedidos_transito["silenciar_ate"]))
        if not df_pedidos_transito.empty
        else {}
    )

    df_est_fonte = df_estoque_bruto if arq_lista_cotacao is not None else df_estoque
    df_hist_fonte = df_historico_bruto if arq_lista_cotacao is not None else df_historico
    df_ent_fonte = df_entradas_bruto if arq_lista_cotacao is not None else df_entradas
    df_sai_fonte = df_saidas_bruto if arq_lista_cotacao is not None else df_saidas
    df_base_fonte = df_base_vendas if arq_lista_cotacao is not None else df_base_vendas_rel
    df_custos_fonte = df_custos if arq_lista_cotacao is not None else df_custos_rel
    if df_est_fonte.empty and df_base_fonte.empty and arq_lista_cotacao is None:
        st.info("Importe a Planilha de Estoque na Aba 6 (Importação & Backup) para calcular o giro e as sugestões de compra.")
    else:
        df_base_giro, dias_hist_janela, peso_hist = calcular_motor_giro_sazonal(
            df_estoque=df_est_fonte,
            df_historico=df_hist_fonte,
            df_base_vendas=df_base_fonte,
            df_custos=df_custos_fonte,
            dias_base_atual=dias_base_atual,
            janela_dias=int(janela_dias),
            incluir_sem_estoque=True if arq_lista_cotacao is not None else incluir_zerados_com_giro,
            df_entradas=df_ent_fonte,
            df_saidas=df_sai_fonte,
            grupos_sku_custom=grupos_sku_custom,
            mp_custom_map=mp_custom_map,
        )
        df_calc = df_base_giro.copy()
        codigos_nao_encontrados_lista = []
        cods_conhecidos_erp = (
            set(df_estoque_bruto["codigo"].unique())
            | set(df_entradas_bruto["codigo"].unique())
            | set(df_saidas_bruto["codigo"].unique())
            | set(df_custos["codigo"].unique())
            | set(df_base_vendas["codigo"].unique())
            | set(df_historico_bruto["codigo"].unique())
        )
        if arq_lista_cotacao is not None:
            try:
                df_lista = ler_lista_produtos_cotacao(arq_lista_cotacao)
                mapa_sem_zero = {}
                for c_erp in cods_conhecidos_erp:
                    chave_sz = normalizar_codigo_sku(c_erp)
                    if chave_sz not in mapa_sem_zero:
                        mapa_sem_zero[chave_sz] = c_erp
                df_lista["codigo"] = df_lista["codigo_lista"].apply(
                    lambda c: c if c in cods_conhecidos_erp else mapa_sem_zero.get(normalizar_codigo_sku(c), c)
                )
                df_lista = df_lista.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
                mask_inexistente = ~df_lista["codigo"].isin(cods_conhecidos_erp)
                if mask_inexistente.any():
                    codigos_nao_encontrados_lista = df_lista.loc[mask_inexistente, "codigo_lista"].tolist()
                df_merged = df_lista.merge(df_calc, on="codigo", how="left")
                df_merged["descricao"] = df_merged["descricao"].fillna("")
                df_merged["descricao"] = df_merged["descricao"].where(
                    df_merged["descricao"] != "", df_merged["descricao_lista"]
                )
                for col_num_fill in [
                    "saldo_atual", "giro_base", "giro_historico", "giro_historico_sem_pico",
                    "giro_ponderado", "giro_ponderado_sem_pico", "desvio_diario",
                    "mediana_diaria", "mad_diario", "saida_ult_dia",
                    "queda_pico_recente", "saldo_antes_pico"
                ]:
                    if col_num_fill in df_merged.columns:
                        df_merged[col_num_fill] = df_merged[col_num_fill].fillna(0.0)
                if "fator_sazonal" in df_merged.columns:
                    df_merged["fator_sazonal"] = df_merged["fator_sazonal"].fillna(1.0)
                df_merged["data_ult_dia"] = df_merged["data_ult_dia"].fillna("-")
                df_merged["data_pico_recente"] = df_merged["data_pico_recente"].fillna("-")
                df_merged["alerta_nf_nao_refletida"] = df_merged["alerta_nf_nao_refletida"].fillna("")
                df_calc = df_merged.drop(columns=["codigo_lista", "descricao_lista"])
            except Exception as e:
                st.error(f"❌ Erro ao processar a lista de produtos para cotação: {e}")
        if codigos_nao_encontrados_lista:
            lista_str = ", ".join(f"`{c}`" for c in codigos_nao_encontrados_lista[:20])
            sufixo = " ..." if len(codigos_nao_encontrados_lista) > 20 else ""
            st.warning(
                f"⚠️ **Atenção:** **{formatar_num_br(len(codigos_nao_encontrados_lista))} código(s)** da planilha enviada "
                f"**não foram encontrados** em nenhuma base do ERP (Estoque, Custos ou Vendas) e aparecem "
                f"com saldo 0: {lista_str}{sufixo}. Verifique se os códigos estão corretos antes de fechar o pedido."
            )

        # Oculta produtos marcados como 'Já Comprei / Em Trânsito' (15 dias ou até NF de Entrada)
        if codigos_em_transito and (not mostrar_comprados_transito) and (arq_lista_cotacao is None):
            df_calc = df_calc[~df_calc["codigo"].isin(codigos_em_transito)].copy()

        fator_saz_sku_s = (
            pd.to_numeric(df_calc["fator_sazonal"], errors="coerce").fillna(1.0)
            if "fator_sazonal" in df_calc.columns
            else pd.Series(1.0, index=df_calc.index)
        )
        df_calc["giro_diario"] = (df_calc["giro_ponderado"] * fator_saz_sku_s).clip(lower=0.0)
        df_calc["giro_diario_sem_pico"] = (df_calc["giro_ponderado_sem_pico"] * fator_saz_sku_s).clip(lower=0.0)
        if not df_custos.empty:
            df_calc = df_calc.merge(
                df_custos[["codigo", "custo_unitario"]], on="codigo", how="left"
            )
            df_calc["custo_unitario"] = df_calc["custo_unitario"].fillna(0.0)
        else:
            df_calc["custo_unitario"] = 0.0
        mapa_venc_60d = {}
        if not df_est_fonte.empty:
            df_lotes_pos = df_est_fonte[df_est_fonte["saldo_lote"] > 0].copy()
            if not df_lotes_pos.empty:
                df_lotes_pos["dt_val"] = converter_datas_deterministico(df_lotes_pos["validade"])
                dias_venc = (df_lotes_pos["dt_val"] - pd.Timestamp(hoje_br())).dt.days
                df_curto = df_lotes_pos[dias_venc.notna() & (dias_venc <= 60)]
                if not df_curto.empty:
                    mapa_venc_60d = df_curto.groupby("codigo")["saldo_lote"].sum().to_dict()
        df_calc["vencendo_60d"] = df_calc["codigo"].map(mapa_venc_60d).fillna(0.0)

        # Estoque de Segurança (ES) e Ponto de Pedido (PP) por variabilidade da demanda (Z=1.65 Curva A, Z=1.28 B/C)
        cmv_diario_sku = df_calc["giro_diario"] * df_calc["custo_unitario"]
        tot_cmv_dia_ab2 = float(cmv_diario_sku.sum())
        if tot_cmv_dia_ab2 > 0.0 and not df_calc.empty:
            ordem_cmv = cmv_diario_sku.sort_values(ascending=False)
            acum_cmv_ant = (ordem_cmv.cumsum() - ordem_cmv) / tot_cmv_dia_ab2
            z_series = pd.Series(
                [1.65 if float(a) < 0.80 else 1.28 for a in acum_cmv_ant],
                index=ordem_cmv.index,
            ).reindex(df_calc.index).fillna(1.28)
        else:
            z_series = pd.Series(1.28, index=df_calc.index)

        if int(lead_time) > 0 and not df_calc.empty:
            desvio_saz_s = df_calc.get("desvio_diario", pd.Series(0.0, index=df_calc.index)).fillna(0.0) * fator_saz_sku_s
            es_bruto_s = z_series * desvio_saz_s * math.sqrt(float(lead_time))
            teto_es_s = df_calc["giro_diario"] * max(float(lead_time) * 1.5, 15.0)
            es_final_s = es_bruto_s.clip(lower=0.0).where(df_calc["giro_diario"] > 0.0, 0.0)
            es_final_s = es_final_s.combine(teto_es_s, min)
            df_calc["estoque_seguranca"] = es_final_s.apply(
                lambda x: float(math.ceil(x - 1e-9)) if x > 0.05 else 0.0
            )
        else:
            df_calc["estoque_seguranca"] = 0.0

        df_calc["ponto_pedido"] = (
            (df_calc["giro_diario"] * float(lead_time)) + df_calc["estoque_seguranca"]
        ).apply(lambda x: float(math.ceil(x - 1e-9)) if x > 0.05 else 0.0)

        dias_totais_nec = float(cobertura_desejada + lead_time)
        df_calc["estoque_ideal"] = (df_calc["giro_diario"] * dias_totais_nec) + df_calc["estoque_seguranca"]
        df_calc["estoque_ideal_sem_pico"] = (df_calc["giro_diario_sem_pico"] * dias_totais_nec) + df_calc["estoque_seguranca"]
        necessidade_padrao = (df_calc["estoque_ideal"] - df_calc["saldo_atual"]).clip(lower=0.0)
        df_calc["sugestao_padrao"] = necessidade_padrao.apply(
            lambda x: float(math.ceil(x - 1e-9)) if x > 0 else 0.0
        )
        df_calc["autonomia_dias"] = (
            (df_calc["saldo_atual"].clip(lower=0.0) / df_calc["giro_diario"].replace(0.0, float("nan")))
            .fillna(999.0)
            .round(1)
        )

        def _avaliar_ruptura_pico_e_sugestao(r):
            cod = str(r["codigo"])
            prefixo_tr = ""
            if cod in mapa_silenciar_ate:
                dt_s_fmt = pd.to_datetime(mapa_silenciar_ate[cod], format="%Y-%m-%d", errors="coerce")
                str_ate = dt_s_fmt.strftime("%d/%m") if pd.notna(dt_s_fmt) else str(mapa_silenciar_ate[cod])
                prefixo_tr = f"🚚 JÁ COMPRADO (Até {str_ate}) | "
            if cod not in cods_conhecidos_erp:
                return False, False, prefixo_tr + "⚠️ Não Cadastrado no ERP", 0.0
            queda_pico = float(r.get("queda_pico_recente", 0.0))
            saldo_antes = float(r.get("saldo_antes_pico", 0.0))
            saldo_at = float(r.get("saldo_atual", 0.0))
            giro_d = float(r.get("giro_diario", 0.0))
            giro_sem_p = float(r.get("giro_diario_sem_pico", 0.0))
            mediana_d = float(r.get("mediana_diaria", 0.0))
            mad_d = float(r.get("mad_diario", 0.0))
            fator_saz_i = float(r.get("fator_sazonal", 1.0))
            ponto_ped = float(r.get("ponto_pedido", 0.0))
            est_ideal = float(r.get("estoque_ideal", 0.0))
            est_ideal_sem_p = float(r.get("estoque_ideal_sem_pico", 0.0))
            sug_padrao = float(r.get("sugestao_padrao", 0.0))
            autonomia = float(r.get("autonomia_dias", 999.0))
            saida_ult = float(r.get("saida_ult_dia", 0.0))
            dt_ult = str(r.get("data_ult_dia", "-"))
            dt_pico = str(r.get("data_pico_recente", "-"))
            alerta_nf = str(r.get("alerta_nf_nao_refletida", "")).strip()

            sufixo_saz = (
                f" | 📅 Saz. {formatar_pct_br((fator_saz_i - 1.0) * 100.0, 0, com_sinal=True)}"
                if abs(fator_saz_i - 1.0) >= 0.05
                else ""
            )
            eh_ruptura = (giro_d > 0.0) and ((autonomia <= float(lead_time)) or (saldo_at <= ponto_ped))
            nao_reposto = (saldo_antes <= 0.0) or (saldo_at < (saldo_antes * 0.85))
            proporcao_estoque = (queda_pico / saldo_antes) if saldo_antes > 0 else 1.0

            # Detecção relativa de pico por SKU via Mediana + MAD (sem limiares fixos 3 e 5)
            sigma_robusto = 1.4826 * mad_d
            limiar_pico_sku = max(mediana_d + (3.5 * sigma_robusto), giro_sem_p * 2.5, giro_d * 2.5, 2.0)
            eh_pico = (
                (queda_pico >= limiar_pico_sku)
                and (queda_pico > 0.0)
                and nao_reposto
                and ((proporcao_estoque >= 0.30) or (queda_pico > sug_padrao and queda_pico > saldo_at))
            )
            sug_ref = sug_padrao
            if eh_pico:
                reserva_min = max(est_ideal_sem_p, ponto_ped)
                teto_recompor_anterior = (
                    min(saldo_antes, queda_pico + est_ideal)
                    if saldo_antes > 0
                    else (queda_pico + reserva_min)
                )
                alvo_reforcado = max(est_ideal, queda_pico + reserva_min, teto_recompor_anterior)
                nec_ref = max(0.0, alvo_reforcado - saldo_at)
                sug_ref = float(math.ceil(nec_ref - 1e-9)) if nec_ref > 0 else 0.0
                sug_ref = max(sug_ref, sug_padrao)
            if eh_pico and eh_ruptura:
                aut_str = "0d" if saldo_at <= 0 else f"{formatar_num_br(autonomia, 1)}d"
                txt_alerta = (
                    prefixo_tr + f"🔥 Rupt. ({aut_str}) + 🚨 Pico -{formatar_qtd_br(queda_pico)} ({dt_pico}){sufixo_saz}"
                )
                return True, True, txt_alerta, sug_ref
            if eh_pico:
                txt_alerta = (
                    prefixo_tr + f"🚨 Pico -{formatar_qtd_br(queda_pico)} ({dt_pico}) | "
                    f"Pad.: {formatar_qtd_br(sug_padrao)}{sufixo_saz}"
                )
                return True, False, txt_alerta, sug_ref
            if eh_ruptura:
                if saldo_at <= 0:
                    txt_alerta = prefixo_tr + f"🔥 Zerado c/ Giro{sufixo_saz}"
                elif autonomia <= float(lead_time):
                    txt_alerta = prefixo_tr + f"🔥 Dura {formatar_num_br(autonomia, 1)}d (≤{lead_time}d){sufixo_saz}"
                else:
                    txt_alerta = prefixo_tr + f"🔥 Ponto Pedido (≤{formatar_qtd_br(ponto_ped)} un.){sufixo_saz}"
                return False, True, txt_alerta, sug_ref
            if alerta_nf:
                return False, False, prefixo_tr + alerta_nf + sufixo_saz, sug_padrao
            if saida_ult > 0:
                return False, False, prefixo_tr + f"✔️ -{formatar_qtd_br(saida_ult)} un. ({dt_ult}){sufixo_saz}", sug_padrao
            return False, False, prefixo_tr + f"➖ Sem saída{sufixo_saz}", sug_padrao

        if not df_calc.empty:
            res_analise = df_calc.apply(_avaliar_ruptura_pico_e_sugestao, axis=1)
            df_calc["tem_pico"] = [x[0] for x in res_analise]
            df_calc["tem_ruptura"] = [x[1] for x in res_analise]
            df_calc["alerta_saida_recente"] = [x[2] for x in res_analise]
            df_calc["sugestao_reforcada"] = [x[3] for x in res_analise]
        else:
            df_calc["tem_pico"] = pd.Series(dtype=bool)
            df_calc["tem_ruptura"] = pd.Series(dtype=bool)
            df_calc["alerta_saida_recente"] = pd.Series(dtype=str)
            df_calc["sugestao_reforcada"] = pd.Series(dtype=float)

        if usar_sugestao_reforcada_pico:
            df_calc["sugestao_compra"] = df_calc["sugestao_reforcada"]
        else:
            df_calc["sugestao_compra"] = df_calc["sugestao_padrao"]

        def _canonizar_texto_busca(txt: str) -> str:
            s = unicodedata.normalize("NFKD", str(txt)).encode("ASCII", "ignore").decode("utf-8").lower()
            s = re.sub(r"\bd[\s'\-]*agua\b", "dagua", s)
            s = re.sub(r"[^a-z0-9]+", " ", s).strip()
            return s

        if filtro_busca and filtro_busca.strip() and not df_calc.empty:
            grupos_busca = [
                _canonizar_texto_busca(g)
                for g in re.split(r"[;,]+", filtro_busca)
                if _canonizar_texto_busca(g)
            ]
            if grupos_busca:
                serie_alvo = (df_calc["codigo"].astype(str) + " " + df_calc["descricao"].astype(str)).map(
                    _canonizar_texto_busca
                )
                mask_total = pd.Series(False, index=df_calc.index)
                for grp in grupos_busca:
                    palavras = grp.split()
                    mask_grp = pd.Series(True, index=df_calc.index)
                    for pal in palavras:
                        mask_grp = mask_grp & serie_alvo.str.contains(re.escape(pal), na=False)
                    mask_total = mask_total | mask_grp
                df_calc = df_calc[mask_total].copy()
        qtd_total_ruptura = int(df_calc["tem_ruptura"].sum()) if not df_calc.empty else 0
        qtd_total_picos = int(df_calc["tem_pico"].sum()) if not df_calc.empty else 0
        qtd_nf_pendente = int((df_calc["alerta_nf_nao_refletida"] != "").sum()) if not df_calc.empty else 0
        if qtd_total_ruptura > 0 or qtd_total_picos > 0 or qtd_nf_pendente > 0 or len(codigos_em_transito) > 0:
            partes_aviso = []
            if qtd_total_ruptura > 0:
                partes_aviso.append(
                    f"🔥 **{formatar_num_br(qtd_total_ruptura)} produto(s) em Ruptura Iminente** (estoque acaba antes dos {lead_time} dias de entrega)"
                )
            if qtd_total_picos > 0:
                partes_aviso.append(
                    f"🚨 **{formatar_num_br(qtd_total_picos)} produto(s) com Saída Fora do Padrão (Pico)**"
                )
            if len(codigos_em_transito) > 0:
                partes_aviso.append(
                    f"🚚 **{formatar_num_br(len(codigos_em_transito))} produto(s) oculto(s) em 'Já Comprei'** (15d ou até NF)"
                )
            if qtd_nf_pendente > 0:
                partes_aviso.append(
                    f"⏳ **{formatar_num_br(qtd_nf_pendente)} produto(s) com NF de Entrada sem reflexo no saldo seguinte**"
                )
            st.info(" | ".join(partes_aviso))
        if filtrar_apenas_ruptura:
            df_calc = df_calc[df_calc["tem_ruptura"] == True].copy()
        if filtrar_apenas_picos:
            df_calc = df_calc[df_calc["tem_pico"] == True].copy()
        if arq_lista_cotacao is None and not df_calc.empty:
            df_calc["_inv_ord"] = df_calc["sugestao_compra"] * df_calc["custo_unitario"]
            df_compras = df_calc.sort_values(
                ["tem_ruptura", "tem_pico", "_inv_ord", "descricao"],
                ascending=[False, False, False, True],
            ).drop(columns=["_inv_ord"])
        else:
            df_compras = df_calc.copy()
        df_compras = df_compras.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
        total_item_s = (df_compras["sugestao_compra"] * df_compras["custo_unitario"]).round(2)
        df_completo_13_cols = pd.DataFrame(
            {
                "Código": df_compras["codigo"].values,
                "Descrição": df_compras["descricao"].values,
                "Saída Recente & Alerta": df_compras["alerta_saida_recente"].values,
                "Saldo Atual": df_compras["saldo_atual"].values,
                "Vencido ou vencendo (≤60d)": df_compras["vencendo_60d"].values,
                "Giro Médio/Dia": df_compras["giro_diario"].values,
                "Autonomia (Dias)": df_compras["autonomia_dias"].values,
                "Ponto de Pedido (c/ Seg.)": df_compras["ponto_pedido"].values,
                "Sugestão Sistema": df_compras["sugestao_compra"].values,
                "Qtd. a Comprar": df_compras["sugestao_compra"].values,
                "Último Custo ERP (R$)": df_compras["custo_unitario"].values,
                "Custo Atual / Cotado (R$)": 0.0,
                "Variação Custo (%)": 0.0,
                "Total do Item (R$)": total_item_s.values,
            }
        )
        m1, m2, m3, m4 = st.columns(4)
        itens_com_pedido = int((df_compras["sugestao_compra"] > 0).sum())
        orcamento_total = float(total_item_s.sum())
        m1.metric(
            "Produtos Listados",
            f"{formatar_num_br(len(df_completo_13_cols))} SKUs (Sugeridos: {formatar_num_br(itens_com_pedido)})",
        )
        m2.metric("Orçamento Estimado (Último Custo)", formatar_moeda_br(orcamento_total))
        m3.metric(
            "🔥 Ruptura / 🚨 Pico",
            f"{formatar_num_br(qtd_total_ruptura)} / {formatar_num_br(qtd_total_picos)}",
            help="Quantidade de itens listados em Ruptura Iminente e Saída de Pico.",
        )
        m4.metric(
            "🚚 Em Trânsito ('Já Comprei')",
            f"{formatar_num_br(len(codigos_em_transito))} SKUs (15d / Auto-NF)",
            help=f"Produtos ocultos temporariamente por {DIAS_PADRAO_SONECA_COMPRA} dias ou até entrarem na NF.",
        )

        col_sel_tudo_c, col_dica_c = st.columns([1.4, 2.6])
        with col_sel_tudo_c:
            marcar_todos_compra_aba2 = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_compras))} itens listados abaixo como 'Já Comprei'",
                value=False,
                key="chk_todos_ja_comprei_aba2",
            )
        with col_dica_c:
            st.caption(
                "💡 **Dica rápida:** Clique na caixinha **'🛒 Já Comprei?'** (1ª coluna da tabela) nos produtos que você acabou de pedir ao fornecedor "
                "e confirme no botão abaixo da tabela para ocultá-los por **15 dias** (eles voltam sozinhos assim que entrarem na NF)."
            )

        df_editor_aba2 = pd.DataFrame(
            {
                "ja_comprei": [bool(marcar_todos_compra_aba2)] * len(df_compras),
                "Cód.": df_compras["codigo"].values,
                "Descrição": df_compras["descricao"].values,
                "Alerta & Saída": df_compras["alerta_saida_recente"].values,
                "Saldo": [formatar_qtd_br(v) for v in df_compras["saldo_atual"].values],
                "Venc. ≤60d": [formatar_qtd_br(v) for v in df_compras["vencendo_60d"].values],
                "Giro/Dia": [
                    formatar_num_br(v, 3) if (pd.notna(v) and 0 < float(v) < 0.05) else formatar_num_br(v, 2)
                    for v in df_compras["giro_diario"].values
                ],
                "Auton.": [
                    "S/ Giro" if (pd.notna(v) and float(v) >= 999.0) else f"{formatar_num_br(v, 1)}d"
                    for v in df_compras["autonomia_dias"].values
                ],
                "P. Pedido": [formatar_qtd_br(v) for v in df_compras["ponto_pedido"].values],
                "Sugestão": [formatar_qtd_br(v) for v in df_compras["sugestao_compra"].values],
                "Custo Un.": [formatar_moeda_br(v) for v in df_compras["custo_unitario"].values],
                "Total (R$)": [formatar_moeda_br(v) for v in total_item_s.values],
            }
        )

        ed_compras_aba2 = st.data_editor(
            df_editor_aba2,
            use_container_width=True,
            hide_index=True,
            height=450,
            key="editor_ja_comprei_aba2",
            disabled=[
                "Cód.",
                "Descrição",
                "Alerta & Saída",
                "Saldo",
                "Venc. ≤60d",
                "Giro/Dia",
                "Auton.",
                "P. Pedido",
                "Sugestão",
                "Custo Un.",
                "Total (R$)",
            ],
            column_config={
                "ja_comprei": st.column_config.CheckboxColumn(
                    "🛒",
                    help="Já Comprei? — Marque este produto para ocultá-lo da lista e dos alertas por 15 dias (ou até a NF de Entrada chegar).",
                    default=False,
                    width="small",
                ),
                "Cód.": st.column_config.TextColumn(
                    "Cód.",
                    help="Código do Produto (SKU no ERP Siagri).",
                    width="small",
                ),
                "Descrição": st.column_config.TextColumn(
                    "Descrição",
                    help="Descrição Completa do Produto no ERP.",
                    width="medium",
                ),
                "Alerta & Saída": st.column_config.TextColumn(
                    "Alerta & Saída",
                    help="Diagnóstico de Ruptura Iminente (estoque acaba antes do prazo de entrega), Pico Sazonal de Saída ou última venda registrada.",
                    width="medium",
                ),
                "Saldo": st.column_config.TextColumn(
                    "Saldo",
                    help="Saldo Geral Atual em Estoque Físico.",
                    width="small",
                ),
                "Venc. ≤60d": st.column_config.TextColumn(
                    "Venc. ≤60d",
                    help="Quantidade vencida ou vencendo nos próximos 60 dias (Radar FEFO).",
                    width="small",
                ),
                "Giro/Dia": st.column_config.TextColumn(
                    "Giro/Dia",
                    help="Giro Médio Diário Ponderado (unidades vendidas ou consumidas por dia).",
                    width="small",
                ),
                "Auton.": st.column_config.TextColumn(
                    "Auton.",
                    help="Autonomia Estimada do Estoque Atual em Dias (Saldo Atual ÷ Giro Médio/Dia).",
                    width="small",
                ),
                "P. Pedido": st.column_config.TextColumn(
                    "P. Pedido",
                    help="Ponto de Pedido = Demanda no Prazo de Entrega + Estoque de Segurança (calculado pela oscilação diária de vendas). Quando o Saldo atinge ou fica abaixo deste valor, é hora de comprar!",
                    width="small",
                ),
                "Sugestão": st.column_config.TextColumn(
                    "Sugestão",
                    help="Sugestão Inteligente de Compra em unidades para cobrir (Cobertura Alvo + Prazo de Entrega + Estoque de Segurança).",
                    width="small",
                ),
                "Custo Un.": st.column_config.TextColumn(
                    "Custo Un.",
                    help="Último Custo Unitário C1 (R$) cadastrado ou atualizado automaticamente via NF de Entrada (Fatu416).",
                    width="small",
                ),
                "Total (R$)": st.column_config.TextColumn(
                    "Total (R$)",
                    help="Orçamento Total Estimado para o Item (Sugestão de Compra × Último Custo Unitário).",
                    width="small",
                ),
            },
        )

        indices_marcados_compra = ed_compras_aba2.index[ed_compras_aba2["ja_comprei"] == True].tolist()
        qtd_marcados_compra = len(indices_marcados_compra)

        if not eh_usuario_admin:
            st.caption(
                f"🔒 **Modo Consulta ({nome_atual_logado}):** Apenas o **Administrador** pode registrar ou devolver itens em 'Já Comprei / Em Trânsito'."
            )
        b_act_col1, b_act_col2 = st.columns([1.3, 1.3])
        with b_act_col1:
            if st.button(
                f"🚚 Ocultar Marcados como 'Já Comprei' por 15 dias ({formatar_num_br(qtd_marcados_compra)} selecionado(s))",
                type="primary",
                use_container_width=True,
                disabled=(qtd_marcados_compra == 0 or not eh_usuario_admin),
            ) and eh_usuario_admin:
                with st.spinner("Registrando pedido em trânsito no Supabase..."):
                    try:
                        hoje_str_c = hoje_br().strftime("%Y-%m-%d")
                        sil_ate_str_c = (hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
                        df_sel_c = df_compras.iloc[indices_marcados_compra].copy()
                        novos_transito = pd.DataFrame(
                            {
                                "codigo": df_sel_c["codigo"].values,
                                "descricao": df_sel_c["descricao"].values,
                                "qtd_comprada": df_sel_c["sugestao_compra"].values,
                                "data_compra": hoje_str_c,
                                "silenciar_ate": sil_ate_str_c,
                            }
                        )
                        df_trans_atualizado = (
                            pd.concat([df_pedidos_transito, novos_transito], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
                        )
                        salvar_backup_automatico_sql(
                            db_supabase, "pedidos_transito", df_pedidos_transito, permitir_vazio=True
                        )
                        gravar_tabela_sql(
                            db_supabase, "pedidos_transito", df_trans_atualizado, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.session_state["msg_transito_aba2"] = (
                            f"✅ {formatar_num_br(qtd_marcados_compra)} produto(s) marcado(s) como 'Já Comprei'! "
                            f"Eles ficarão ocultos por {DIAS_PADRAO_SONECA_COMPRA} dias (até {(hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime('%d/%m/%Y')}) "
                            f"ou despertarão automaticamente assim que aparecerem na planilha de Entradas (NF)."
                        )
                        st.rerun()
                    except Exception as e_tr:
                        st.error(f"❌ Erro ao salvar produtos em trânsito: {e_tr}")

        with b_act_col2:
            if not df_completo_13_cols.empty:
                st.download_button(
                    label="📥 Baixar Planilha de Sugestão & Cotação (.xlsx com 14 Colunas e Fórmulas Vivas)",
                    data=gerar_excel_com_formulas_cotacao(df_completo_13_cols),
                    file_name=f"Cotacao_Compras_Esteio_{janela_dias}d_{hoje_br().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

    with st.expander(
        f"🚚 Gerenciar Produtos Marcados como 'Já Comprei / Em Trânsito' ({formatar_num_br(len(df_pedidos_transito))} ativo(s) — 15 dias ou até NF)",
        expanded=False,
    ):
        if df_pedidos_transito.empty:
            st.success("Nenhum produto está silenciado como 'Já Comprei' no momento.")
        else:
            st.caption(
                "Estes produtos foram marcados como comprados e estão temporariamente silenciados na Aba 2. "
                "Eles voltam sozinhos após 15 dias ou assim que o código entrar numa planilha de Entradas (NF) na Aba 6. "
                "Se marcou algum por engano, selecione abaixo para devolvê-lo imediatamente:"
            )
            df_tr_view = df_pedidos_transito.copy()
            hoje_ts_tr = pd.Timestamp(hoje_br())
            dt_sil_tr = converter_datas_deterministico(df_tr_view["silenciar_ate"])
            dt_comp_tr = converter_datas_deterministico(df_tr_view["data_compra"])
            dias_rest_tr = (dt_sil_tr - hoje_ts_tr).dt.days.fillna(0).astype(int)
            df_tr_view["data_compra_fmt"] = dt_comp_tr.dt.strftime("%d/%m/%Y").fillna(df_tr_view["data_compra"])
            df_tr_view["silenciar_ate_fmt"] = dt_sil_tr.dt.strftime("%d/%m/%Y").fillna(df_tr_view["silenciar_ate"])
            df_tr_view["dias_restantes"] = [f"{max(int(d), 0)} dia(s)" for d in dias_rest_tr]

            df_tr_ed_input = pd.DataFrame(
                {
                    "devolver": [False] * len(df_tr_view),
                    "Código": df_tr_view["codigo"].values,
                    "Descrição": df_tr_view["descricao"].values,
                    "Qtd. Sugerida na Compra": [formatar_qtd_br(v) for v in df_tr_view["qtd_comprada"].values],
                    "Marcado em": df_tr_view["data_compra_fmt"].values,
                    "Oculto até (15d)": df_tr_view["silenciar_ate_fmt"].values,
                    "Prazo Restante": df_tr_view["dias_restantes"].values,
                }
            )
            ed_transito_gestao = st.data_editor(
                df_tr_ed_input,
                hide_index=True,
                use_container_width=True,
                key="editor_gestao_transito_aba2",
                disabled=[
                    "Código",
                    "Descrição",
                    "Qtd. Sugerida na Compra",
                    "Marcado em",
                    "Oculto até (15d)",
                    "Prazo Restante",
                ],
                column_config={
                    "devolver": st.column_config.CheckboxColumn(
                        "Devolver?",
                        help="Marque para remover do modo 'Já Comprei' e voltar a exibir na lista de compras",
                        default=False,
                    )
                },
            )
            sel_devolver_tr = ed_transito_gestao[ed_transito_gestao["devolver"] == True]
            bt_tr1, bt_tr2 = st.columns(2)
            with bt_tr1:
                btn_dev_marcados = st.button(
                    f"↩️ Devolver Marcados para Lista de Compras ({formatar_num_br(len(sel_devolver_tr))})",
                    type="primary",
                    use_container_width=True,
                    disabled=(sel_devolver_tr.empty or not eh_usuario_admin),
                )
            with bt_tr2:
                btn_dev_todos = st.button(
                    "🔄 Devolver Todos os Itens em Trânsito",
                    use_container_width=True,
                    disabled=(not eh_usuario_admin),
                )
            if (btn_dev_marcados or btn_dev_todos) and eh_usuario_admin:
                with st.spinner("Atualizando lista de trânsito no Supabase..."):
                    try:
                        if btn_dev_todos:
                            df_tr_restante = padronizar_dataframe(pd.DataFrame(), "pedidos_transito")
                        else:
                            cods_dev = set(sel_devolver_tr["Código"].unique())
                            df_tr_restante = df_pedidos_transito[~df_pedidos_transito["codigo"].isin(cods_dev)].copy()
                        salvar_backup_automatico_sql(
                            db_supabase, "pedidos_transito", df_pedidos_transito, permitir_vazio=True
                        )
                        gravar_tabela_sql(
                            db_supabase, "pedidos_transito", df_tr_restante, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.session_state["msg_transito_aba2"] = "✅ Produto(s) devolvido(s) para a lista ativa de compras!"
                        st.rerun()
                    except Exception as e_dev:
                        st.error(f"❌ Erro ao devolver produtos: {e_dev}")
