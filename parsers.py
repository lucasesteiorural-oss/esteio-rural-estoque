"""
parsers.py — Módulo de Formatação BR, Esquemas Siagri, Leitura/Travas de Planilhas,
Departamentos/MP e Exportação Excel/ZIP (Esteio Rural — Arquitetura Modular v37).
"""
import io
import re
import math
import zipfile
import unicodedata
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st




# ==============================================================================
# 1. FUSO HORÁRIO E DATAS BRASIL
# ==============================================================================


FUSO_BR = ZoneInfo("America/Sao_Paulo")


def hoje_br() -> date:
    return datetime.now(FUSO_BR).date()


def agora_br() -> datetime:
    return datetime.now(FUSO_BR)




# ==============================================================================
# 2. CONSTANTES, ESQUEMAS E SINÔNIMOS SIAGRI
# ==============================================================================


DIAS_MAX_HISTORICO = 730


DIAS_PADRAO_SONECA_COMPRA = 15


LIMITE_COINCIDENCIA_CATALOGO = 80.0


COLUNAS_NUMERICAS = {
    "saldo_geral",
    "saldo_lote",
    "custo_unitario",
    "preco_tabela",
    "qtd_vendida",
    "qtd_entrada",
    "valor_entrada",
    "qtd_saida",
    "valor_venda",
    "qtd_comprada",
}


ESQUEMA_ABAS = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada", "valor_entrada", "data"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida", "valor_venda", "data"],
    "custos": ["codigo", "descricao", "custo_unitario", "preco_tabela"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "pedidos_transito": ["codigo", "descricao", "qtd_comprada", "data_compra", "silenciar_ate"],
    "meta": ["chave", "valor"],
}


COLUNAS_OBRIGATORIAS_UPLOAD = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida"],
    "custos": ["codigo", "descricao", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao"],
    "pedidos_transito": ["codigo", "descricao"],
    "meta": ["chave", "valor"],
}


ORDEM_POSICIONAL_PADRAO = {
    "estoque_atual": ["codigo", "saldo_geral", "descricao", "lote", "saldo_lote", "validade", "data"],
    "historico": ["codigo", "saldo_geral", "data"],
    "entradas_diarias": ["codigo", "descricao", "qtd_entrada", "valor_entrada", "data"],
    "saidas_diarias": ["codigo", "descricao", "qtd_saida", "valor_venda", "data"],
    "custos": ["codigo", "descricao", "preco_tabela", "custo_unitario"],
    "base_inicial": ["codigo", "descricao", "qtd_vendida"],
    "ocultos": ["codigo", "descricao", "data_ocultado"],
    "pedidos_transito": ["codigo", "descricao", "qtd_comprada", "data_compra", "silenciar_ate"],
    "meta": ["chave", "valor"],
}


MAPA_SINONIMOS = {
    "codigo": [
        "codigo",
        "cod",
        "cod_produto",
        "codigo_produto",
        "codigo_do_produto",
        "codigo_produto_acabado",
        "cod_produto_acabado",
        "codigo_do_produto_acabado",
        "sku",
        "id",
        "item",
    ],
    "saldo_geral": [
        "saldo_geral",
        "saldogeral",
        "quantidade_do_saldo_inicial_dos_produtos_no_controle_de_saldo",
        "quantidade_do_saldo_inicial",
        "saldo_inicial",
        "estoque_geral",
        "saldo_total",
        "saldo_atual",
        "estoque_atual",
        "saldo_fisico",
        "saldo",
    ],
    "descricao": [
        "descricao",
        "descricao_do_produto_servico",
        "descricao_produto_servico",
        "descricao_do_produto_predominante",
        "descricao_produto_predominante",
        "produto_predominante",
        "descricao_do_produto_acabado",
        "descricao_produto_acabado",
        "desc",
        "descricao_produto",
        "descricao_do_produto",
        "produto",
        "nome",
        "mercadoria",
    ],
    "lote": [
        "lote",
        "codigo_do_lote",
        "cod_lote",
        "codigo_lote",
        "num_lote",
        "numero_lote",
        "lotes",
    ],
    "saldo_lote": [
        "saldo_lote",
        "sald_lot",
        "saldo_lot",
        "saldolote",
        "saldo_do_lote",
        "qtd_lote",
        "estoque_lote",
        "quant_lote",
    ],
    "validade": [
        "validade",
        "validade_tempo_germinacao",
        "data_de_validade_germinacao_do_lote",
        "data_validade_germinacao_do_lote",
        "validade_germinacao_do_lote",
        "validade_germinacao",
        "data_validade",
        "dt_validade",
        "data_de_validade",
        "vencimento",
        "data_vencimento",
        "validade_lote",
        "val",
    ],
    "data": [
        "data",
        "data_posicao",
        "data_ref",
        "data_importacao",
        "dt",
        "dia",
    ],
    "custo_unitario": [
        "custo_unitario",
        "custo_unitario_c1",
        "custo_c1",
        "c1",
        "custo",
        "custo_medio",
        "custo_medio_unitario",
        "preco_custo",
        "valor_unitario",
        "cmv",
    ],
    "preco_tabela": [
        "preco_tabela",
        "t1",
        "tabela_1",
        "tabela1",
        "preco_venda",
        "preco_de_venda",
        "preco_cheio",
        "preco_normal",
        "vlr_venda",
        "valor_tabela",
        "preco",
    ],
    "qtd_vendida": [
        "qtd_vendida",
        "quantidade_vendida",
        "vend_pro",
        "venda_pro",
        "venda_produto",
        "vendas_produto",
        "qtd_venda",
        "quantidade",
        "qtd",
        "vendas",
        "saida",
        "total_vendido",
    ],
    "qtd_entrada": [
        "qtd_entrada",
        "quantidade_entrada",
        "ent_pro",
        "compra_pro",
        "qtd_compra",
        "entrada",
        "entradas",
        "qtd_comprada",
        "quantidade",
        "qtd",
    ],
    "valor_entrada": [
        "valor_entrada",
        "valor",
        "vlr",
        "valor_total",
        "vlr_total",
        "valor_total_entrada",
        "total_entrada",
        "valor_nf",
        "vlr_nf",
        "valor_liquido",
        "valor_bruto",
        "custo_total",
        "custo_unitario",
        "custo_c1",
        "valor_unitario",
    ],
    "qtd_saida": [
        "qtd_saida",
        "quantidade_saida",
        "vend_pro",
        "venda_pro",
        "venda_produto",
        "vendas_produto",
        "qtd_venda",
        "qtd_vendida",
        "quantidade_vendida",
        "saida",
        "saidas",
        "vendas",
        "quantidade",
        "qtd",
        "total_vendido",
    ],
    "valor_venda": [
        "valor_venda",
        "valor_total_da_proposta",
        "valor_total_proposta",
        "vlr_total_da_proposta",
        "vlr_total_proposta",
        "valor_da_proposta",
        "valor_proposta",
        "valor_total_venda",
        "valor_total",
        "faturamento",
        "receita",
        "valor_liquido",
        "total_venda",
        "vlr_venda",
    ],
    "data_ocultado": ["data_ocultado", "data", "ocultado_em"],
    "qtd_comprada": ["qtd_comprada", "quantidade_comprada", "qtd_pedido", "sugestao_compra", "qtd"],
    "data_compra": ["data_compra", "comprado_em", "data_pedido", "data"],
    "silenciar_ate": ["silenciar_ate", "ocultar_ate", "expira_em", "valido_ate"],
    "chave": ["chave", "key", "parametro", "config"],
    "valor": ["valor", "value", "conteudo"],
}




# ==============================================================================
# 3. FORMATAÇÃO BRASILEIRA (1.000,00) E ESTILIZAÇÃO DE TABELAS
# ==============================================================================


def formatar_num_br(valor, casas: int = 0) -> str:
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return str(valor)
    if casas <= 0:
        return f"{v:,.0f}".replace(",", ".")
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_qtd_br(valor) -> str:
    if pd.isna(valor) or valor is None:
        return "0"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return str(valor)
    if abs(v - round(v)) < 0.005:
        return formatar_num_br(round(v), 0)
    return formatar_num_br(v, 2)


def formatar_moeda_br(valor) -> str:
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return "R$ 0,00"
    if 0 < abs(v) < 1.0 and abs(v * 100 - round(v * 100)) > 0.01:
        return f"R$ {formatar_num_br(v, 3)}"
    return f"R$ {formatar_num_br(v, 2)}"


def formatar_pct_br(valor, casas: int = 1, com_sinal: bool = False) -> str:
    if pd.isna(valor) or valor is None:
        return "0,0%"
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return "0,0%"
    prefixo = "+" if (com_sinal and v > 0) else ""
    return f"{prefixo}{formatar_num_br(v, casas)}%"


def estilizar_tabela_br(
    df: pd.DataFrame,
    formatadores: dict = None,
    colunas_esquerda: list = None,
):
    if df is None or df.empty:
        return df
    cols_esq = set(colunas_esquerda or ["Descrição"])
    cols_centro = [c for c in df.columns if c not in cols_esq]
    styler = df.style
    if formatadores:
        fmt_validos = {k: v for k, v in formatadores.items() if k in df.columns}
        if fmt_validos:
            styler = styler.format(fmt_validos, na_rep="-")
    if cols_centro:
        styler = styler.set_properties(subset=cols_centro, **{"text-align": "center"})
    cols_esq_presentes = [c for c in df.columns if c in cols_esq]
    if cols_esq_presentes:
        styler = styler.set_properties(subset=cols_esq_presentes, **{"text-align": "left"})
    styler = styler.set_table_styles(
        [{"selector": "th", "props": [("text-align", "center")]}]
    )
    return styler




# ==============================================================================
# 4. NORMALIZAÇÃO DE TEXTO, NÚMEROS, DATAS E DATAFRAMES
# ==============================================================================


def normalizar_chave_coluna(nome: str) -> str:
    s = unicodedata.normalize("NFKD", str(nome)).encode("ASCII", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.lower()).strip("_")
    return s


def limpar_serie_texto(serie: pd.Series) -> pd.Series:
    def _limpar_val(v):
        if pd.isna(v) or v is None:
            return ""
        if isinstance(v, (datetime, date, pd.Timestamp)):
            return v.strftime("%d/%m/%Y")
        if isinstance(v, float):
            if v.is_integer():
                return str(int(v))
            return str(v)
        s = str(v).strip()
        if s.lower() in ("nan", "none", "nat", "<na>"):
            return ""
        return re.sub(r"^(\d+)\.0$", r"\1", s)
    return serie.map(_limpar_val)


def normalizar_codigo_sku(val) -> str:
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat", "<na>"):
        return ""
    s = re.sub(r"^(\d+)\.0$", r"\1", s)
    s = re.sub(r"^0+(?=\d)", "", s)
    return s


def limpar_serie_codigo(serie: pd.Series) -> pd.Series:
    return limpar_serie_texto(serie).map(normalizar_codigo_sku)


def converter_numero_br(
    serie: pd.Series,
    nome_coluna: str = "",
    origem_banco: bool = False,
    bloquear_invalidos: bool = False,
    codigos_ref: pd.Series = None,
) -> pd.Series:
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0.0).astype(float)
    mask_nativo_num = serie.map(
        lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and pd.notna(x)
    )
    if mask_nativo_num.all():
        return serie.astype(float)
    s_str = (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.replace("R$", "", regex=False)
        .str.replace("r$", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    s_apenas_str = s_str[~mask_nativo_num]
    tem_virgula_decimal_na_coluna = s_apenas_str.str.contains(r",\d+$", regex=True).any()
    tem_ponto_nao_3_digitos = s_apenas_str.str.match(
        r"^[+-]?\d+\.\d{1,2}$|^[+-]?\d+\.\d{4,}$|^[+-]?0\.\d+$"
    ).any()
    if origem_banco:
        tratar_1ponto_3dig_como_milhar = False
    elif nome_coluna in ("saldo_geral", "saldo_lote", "qtd_vendida", "qtd_entrada", "qtd_saida"):
        tratar_1ponto_3dig_como_milhar = (not tem_ponto_nao_3_digitos) or tem_virgula_decimal_na_coluna
    else:
        tratar_1ponto_3dig_como_milhar = (not tem_ponto_nao_3_digitos) and tem_virgula_decimal_na_coluna
    erros_encontrados = []
    valores_convertidos = []
    for idx, val in serie.items():
        if pd.isna(val) or val is None:
            valores_convertidos.append(0.0)
            continue
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            v_flt = float(val)
            if math.isnan(v_flt) or math.isinf(v_flt):
                valores_convertidos.append(0.0)
            else:
                valores_convertidos.append(v_flt)
            continue
        txt_bruto = str(val).strip()
        txt = (
            txt_bruto.replace("R$", "")
            .replace("r$", "")
            .replace("\u00a0", "")
            .replace(" ", "")
        )
        if not txt or txt.lower() in ("-", "--", "nan", "none", "nat", "<na>"):
            valores_convertidos.append(0.0)
            continue
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            if txt.count(",") == 1:
                txt = txt.replace(",", ".")
            elif re.match(r"^[+-]?[1-9]\d{0,2}(,\d{3})+$", txt):
                txt = txt.replace(",", "")
        elif "." in txt:
            if txt.count(".") >= 2 and re.match(r"^[+-]?[1-9]\d{0,2}(\.\d{3}){2,}$", txt):
                txt = txt.replace(".", "")
            elif tratar_1ponto_3dig_como_milhar and re.match(r"^[+-]?[1-9]\d{0,2}\.\d{3}$", txt):
                txt = txt.replace(".", "")
        try:
            num = float(txt)
            if math.isnan(num) or math.isinf(num):
                raise ValueError("NaN/Inf")
            valores_convertidos.append(num)
        except ValueError:
            if bloquear_invalidos:
                cod_id = ""
                if codigos_ref is not None and idx in codigos_ref.index:
                    cod_id = str(codigos_ref.loc[idx]).strip()
                identificador = f"SKU '{cod_id}'" if cod_id else f"Linha {idx + 2}"
                erros_encontrados.append(f"{identificador} (valor lido: '{txt_bruto}')")
            valores_convertidos.append(0.0)
    if bloquear_invalidos and erros_encontrados:
        amostra = ", ".join(erros_encontrados[:8])
        raise ValueError(
            f"Trava de Segurança (Valor Numérico Inválido na coluna '{nome_coluna}'): "
            f"Foram encontrados {len(erros_encontrados)} registro(s) com texto inválido ou erro de fórmula "
            f"que seriam zerados indevidamente. Exemplos: {amostra}. "
            f"Corrija esses itens na planilha antes de importar."
        )
    return pd.Series(valores_convertidos, index=serie.index, dtype=float)


FORMATOS_DATA_ACEITOS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%y")


def _parse_data_segura_py(valor, ano_min: int = 2000, ano_max: int = None):
    if ano_max is None:
        ano_max = hoje_br().year + 15
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return datetime(valor.year, valor.month, valor.day) if (ano_min <= valor.year <= ano_max) else None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if 36526 <= float(valor) <= 60000:
            dt_xl = datetime(1899, 12, 30) + timedelta(days=int(float(valor)))
            return dt_xl if (ano_min <= dt_xl.year <= ano_max) else None
        return None
    s = str(valor).strip()
    if not s or s.lower() in {"nan", "none", "nat", "<na>", "0", "0.0", "-", "--", "sem validade", "s/v"}:
        return None
    if re.fullmatch(r"\d{5}(?:\.0+)?", s):
        serial_int = int(float(s))
        if 36526 <= serial_int <= 60000:
            dt_xl = datetime(1899, 12, 30) + timedelta(days=serial_int)
            return dt_xl if (ano_min <= dt_xl.year <= ano_max) else None
        return None
    s_data = re.sub(r"[\sT]+\d{1,2}:\d{2}(:\d{2})?.*$", "", s).strip()
    m_ano = re.search(r"\b(\d{4})\b", s_data)
    if m_ano:
        ano_int = int(m_ano.group(1))
        if ano_int < ano_min or ano_int > ano_max:
            return None
    for fmt in FORMATOS_DATA_ACEITOS:
        try:
            dt = datetime.strptime(s_data, fmt)
            if ano_min <= dt.year <= ano_max:
                return dt
            return None
        except ValueError:
            continue
    return None


def formatar_validade_padrao(valor) -> str:
    dt = _parse_data_segura_py(valor, ano_min=2000, ano_max=hoje_br().year + 15)
    return dt.strftime("%d/%m/%Y") if dt is not None else ""


def converter_datas_deterministico(serie: pd.Series) -> pd.Series:
    if serie is None or serie.empty:
        return pd.Series(dtype="datetime64[ns]")
    ano_teto = hoje_br().year + 15
    unicos = serie.dropna().unique()
    mapa = {val: _parse_data_segura_py(val, ano_min=2000, ano_max=ano_teto) for val in unicos}
    lista_dt = [mapa.get(v, None) if pd.notna(v) else None for v in serie]
    return pd.to_datetime(pd.Series(lista_dt, index=serie.index, dtype="object"), errors="coerce").astype("datetime64[ns]")


def restaurar_tipos(
    df: pd.DataFrame,
    origem_banco: bool = False,
    bloquear_invalidos: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        if col not in COLUNAS_NUMERICAS:
            if col == "codigo":
                df[col] = limpar_serie_codigo(df[col])
            elif col == "validade":
                df[col] = df[col].map(formatar_validade_padrao)
            else:
                df[col] = limpar_serie_texto(df[col])
    codigos_ref = df["codigo"] if "codigo" in df.columns else None
    for col in df.columns:
        if col in COLUNAS_NUMERICAS:
            df[col] = converter_numero_br(
                df[col],
                nome_coluna=col,
                origem_banco=origem_banco,
                bloquear_invalidos=bloquear_invalidos,
                codigos_ref=codigos_ref,
            )
    return df


def estruturar_dataframe_bruto(
    df: pd.DataFrame,
    nome_aba: str,
    exigir_colunas_obrigatorias: bool = False,
    origem_banco: bool = False,
) -> pd.DataFrame:
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    colunas_esperadas = ESQUEMA_ABAS.get(aba_esquema, [])
    if df is None or df.empty:
        return restaurar_tipos(pd.DataFrame(columns=colunas_esperadas), origem_banco=origem_banco)
    df_orig = df.loc[:, ~df.columns.duplicated()].copy()
    cols_norm = {col: normalizar_chave_coluna(col) for col in df_orig.columns}
    renomear = {}
    colunas_orig_usadas = set()
    alvos_encontrados = set()
    for col_alvo in colunas_esperadas:
        sinonimos = MAPA_SINONIMOS.get(col_alvo, [col_alvo])
        for sin in sinonimos:
            encontrada = None
            for col_orig, norm in cols_norm.items():
                if col_orig not in colunas_orig_usadas and norm == sin:
                    encontrada = col_orig
                    break
            if encontrada is not None:
                renomear[encontrada] = col_alvo
                colunas_orig_usadas.add(encontrada)
                alvos_encontrados.add(col_alvo)
                break
    if aba_esquema in ("saidas_diarias", "entradas_diarias") and df_orig.shape[1] >= 4:
        col_fin_alvo = "valor_venda" if aba_esquema == "saidas_diarias" else "valor_entrada"
        if col_fin_alvo not in alvos_encontrados:
            termos_fin_validos = (
                ("valor", "vlr", "proposta", "faturamento", "receita", "preco", "liquido", "bruto", "total_venda")
                if aba_esquema == "saidas_diarias"
                else ("valor", "vlr", "custo", "c1", "nf", "nota", "liquido", "bruto", "total")
            )
            termos_nao_fin = (
                ("saldo", "estoque", "lote", "validade", "custo", "cmv", "cod", "qtd", "quant", "data")
                if aba_esquema == "saidas_diarias"
                else ("saldo", "estoque", "lote", "validade", "cod", "qtd", "quant", "data", "preco", "venda", "proposta", "faturamento", "receita")
            )
            for col_cand in list(df_orig.columns)[3:]:
                norm_cand = cols_norm.get(col_cand, "")
                if (
                    col_cand not in colunas_orig_usadas
                    and any(t in norm_cand for t in termos_fin_validos)
                    and not any(b in norm_cand for b in termos_nao_fin)
                ):
                    renomear[col_cand] = col_fin_alvo
                    colunas_orig_usadas.add(col_cand)
                    alvos_encontrados.add(col_fin_alvo)
                    break
    if not exigir_colunas_obrigatorias:
        if aba_esquema == "saidas_diarias" and df_orig.shape[1] == 4 and "valor_venda" not in alvos_encontrados:
            ordem_padrao = ["codigo", "descricao", "qtd_saida", "data"]
        elif aba_esquema == "entradas_diarias" and df_orig.shape[1] == 4 and "valor_entrada" not in alvos_encontrados:
            ordem_padrao = ["codigo", "descricao", "qtd_entrada", "data"]
        elif aba_esquema == "custos" and df_orig.shape[1] == 3 and "preco_tabela" not in alvos_encontrados:
            ordem_padrao = ["codigo", "descricao", "custo_unitario"]
        else:
            ordem_padrao = ORDEM_POSICIONAL_PADRAO.get(aba_esquema, colunas_esperadas)
        cols_orig_lista = list(df_orig.columns)
        for idx_pos, col_alvo in enumerate(ordem_padrao):
            if col_alvo not in alvos_encontrados and idx_pos < len(cols_orig_lista):
                col_candidata = cols_orig_lista[idx_pos]
                if col_candidata not in colunas_orig_usadas:
                    renomear[col_candidata] = col_alvo
                    colunas_orig_usadas.add(col_candidata)
                    alvos_encontrados.add(col_alvo)
    df = df_orig.rename(columns=renomear)
    if exigir_colunas_obrigatorias:
        obrigatorias = COLUNAS_OBRIGATORIAS_UPLOAD.get(aba_esquema, [])
        ausentes = [c for c in obrigatorias if c not in df.columns]
        if ausentes:
            cols_lidas = ", ".join(f"'{c}'" for c in df_orig.columns[:10])
            raise ValueError(
                f"Trava contra Coluna Desconhecida ou Trocada ('{aba_esquema}'): "
                f"Não foi possível localizar a(s) coluna(s) obrigatória(s) **{', '.join(ausentes)}** pelo cabeçalho. "
                f"Cabeçalhos encontrados na planilha enviada: [{cols_lidas}]. "
                f"Verifique se a planilha está correta e com os títulos de coluna esperados."
            )
    for col_alvo in colunas_esperadas:
        if col_alvo not in df.columns:
            if col_alvo in COLUNAS_NUMERICAS:
                df[col_alvo] = 0.0
            elif col_alvo in ("data", "data_ocultado", "data_compra"):
                df[col_alvo] = hoje_br().strftime("%Y-%m-%d")
            elif col_alvo == "silenciar_ate":
                df[col_alvo] = (hoje_br() + timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
            else:
                df[col_alvo] = ""
    df = df[colunas_esperadas].copy()
    if "codigo" in df.columns:
        df["codigo"] = limpar_serie_codigo(df["codigo"])
        df = df[df["codigo"] != ""].copy()
        df = df[
            ~df["codigo"].str.lower().isin(
                ["codigo", "código", "cod", "sku", "id", "item", "total", "total geral", "subtotal"]
            )
        ].copy()
    df = restaurar_tipos(
        df,
        origem_banco=origem_banco,
        bloquear_invalidos=exigir_colunas_obrigatorias and (not origem_banco),
    )
    return df.reset_index(drop=True)


def compactar_estoque_para_historico(df_est: pd.DataFrame) -> pd.DataFrame:
    """Compacta o estoque para 1 linha por SKU (apenas saldo_geral != 0) e 3 colunas (codigo, saldo_geral, data)."""
    if df_est is None or df_est.empty:
        return pd.DataFrame(columns=ESQUEMA_ABAS["historico"])
    df_h = estruturar_dataframe_bruto(df_est, "historico")
    if df_h.empty:
        return df_h
    df_h = df_h.drop_duplicates(subset=["codigo", "data"], keep="last")
    df_h = df_h[df_h["saldo_geral"].abs() > 1e-9].copy()
    return df_h.reset_index(drop=True)


def padronizar_dataframe(
    df: pd.DataFrame,
    nome_aba: str,
    origem_banco: bool = False,
) -> pd.DataFrame:
    aba_esquema = nome_aba[5:] if nome_aba.startswith("_bkp_") else nome_aba
    df = estruturar_dataframe_bruto(df, aba_esquema, origem_banco=origem_banco)
    if df.empty:
        return df
    if aba_esquema == "estoque_atual":
        df = df.drop_duplicates(subset=["codigo", "lote", "data"], keep="last")
    elif aba_esquema == "historico":
        df = df.drop_duplicates(subset=["codigo", "data"], keep="last")
        df = df[df["saldo_geral"].abs() > 1e-9].copy()
    elif aba_esquema in ("entradas_diarias", "saidas_diarias"):
        df = df.drop_duplicates(subset=["codigo", "data"], keep="last")
    elif aba_esquema in ("custos", "ocultos", "pedidos_transito"):
        df = df.drop_duplicates(subset=["codigo"], keep="last")
    return df.reset_index(drop=True)


def depurar_pedidos_transito_auto_despertar(
    df_transito: pd.DataFrame,
    df_entradas: pd.DataFrame,
) -> tuple[pd.DataFrame, list, list]:
    """
    Mantém apenas os itens em 'pedidos_transito' dentro do prazo de 15 dias e que ainda NÃO
    tiveram entrada na planilha de Entradas (NF) em data >= data_compra (Auto-Despertar).
    """
    if df_transito is None or df_transito.empty:
        return padronizar_dataframe(pd.DataFrame(), "pedidos_transito"), [], []
    df_t = padronizar_dataframe(df_transito, "pedidos_transito")
    if df_t.empty:
        return df_t, [], []

    hoje_iso = hoje_br().strftime("%Y-%m-%d")
    dt_comp_s = converter_datas_deterministico(df_t["data_compra"])
    dt_sil_s = converter_datas_deterministico(df_t["silenciar_ate"])

    datas_compra_iso = []
    datas_sil_iso = []
    for idx_r, r_t in df_t.iterrows():
        dc = dt_comp_s.loc[idx_r]
        ds = dt_sil_s.loc[idx_r]
        dc_iso = dc.strftime("%Y-%m-%d") if pd.notna(dc) else hoje_iso
        if pd.notna(ds):
            ds_iso = ds.strftime("%Y-%m-%d")
        else:
            dt_base_c = dc if pd.notna(dc) else pd.Timestamp(hoje_br())
            ds_iso = (dt_base_c + pd.Timedelta(days=DIAS_PADRAO_SONECA_COMPRA)).strftime("%Y-%m-%d")
        datas_compra_iso.append(dc_iso)
        datas_sil_iso.append(ds_iso)

    df_t["data_compra"] = datas_compra_iso
    df_t["silenciar_ate"] = datas_sil_iso

    mapa_ult_ent = {}
    if df_entradas is not None and not df_entradas.empty and "codigo" in df_entradas.columns and "data" in df_entradas.columns:
        df_e_pos = df_entradas[df_entradas["qtd_entrada"] > 0].copy()
        if not df_e_pos.empty:
            dt_e = converter_datas_deterministico(df_e_pos["data"])
            df_e_pos["_dt_iso"] = dt_e.dt.strftime("%Y-%m-%d").fillna("")
            df_e_pos = df_e_pos[df_e_pos["_dt_iso"] != ""]
            if not df_e_pos.empty:
                mapa_ult_ent = df_e_pos.groupby("codigo")["_dt_iso"].max().to_dict()

    cods_despertados_nf = []
    cods_expirados_15d = []
    indices_manter = []

    for idx_r, r_t in df_t.iterrows():
        cod = str(r_t["codigo"]).strip()
        dc_iso = str(r_t["data_compra"]).strip()
        ds_iso = str(r_t["silenciar_ate"]).strip()
        ult_ent_iso = mapa_ult_ent.get(cod, "")
        if ult_ent_iso and ult_ent_iso >= dc_iso:
            cods_despertados_nf.append(cod)
            continue
        if ds_iso < hoje_iso:
            cods_expirados_15d.append(cod)
            continue
        indices_manter.append(idx_r)

    df_ativos = df_t.loc[indices_manter].reset_index(drop=True)
    return df_ativos, cods_despertados_nf, cods_expirados_15d


def podar_historico_max_dias(df_hist: pd.DataFrame, nome_aba: str = "historico") -> pd.DataFrame:
    if df_hist is None or df_hist.empty or "data" not in df_hist.columns:
        return padronizar_dataframe(pd.DataFrame(), nome_aba)
    df_h = df_hist.copy()
    if "codigo" in df_h.columns:
        df_h["codigo"] = limpar_serie_codigo(df_h["codigo"])
    dt_parsed = converter_datas_deterministico(df_h["data"])
    mask_valida = dt_parsed.notna()
    df_h = df_h.loc[mask_valida].copy()
    if df_h.empty:
        return padronizar_dataframe(pd.DataFrame(), nome_aba)
    dt_validas = dt_parsed.loc[mask_valida]
    df_h["data"] = dt_validas.dt.strftime("%Y-%m-%d")
    limite_ts = pd.Timestamp(hoje_br() - timedelta(days=DIAS_MAX_HISTORICO))
    df_filtrado = df_h[dt_validas >= limite_ts].copy()
    chaves_dedup = ["codigo", "lote", "data"] if "lote" in df_filtrado.columns else ["codigo", "data"]
    df_filtrado = df_filtrado.drop_duplicates(subset=chaves_dedup, keep="last")
    if nome_aba == "historico" and "saldo_geral" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["saldo_geral"].abs() > 1e-9].copy()
    return df_filtrado.reset_index(drop=True)


podar_historico_180_dias = podar_historico_max_dias




# ==============================================================================
# 5. EXPORTAÇÃO E BACKUP EM MEMÓRIA (.XLSX, .ZIP E COTAÇÃO C/ FÓRMULAS)
# ==============================================================================


def _formatar_e_centralizar_aba_openpyxl(ws):
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter
    alin_centro = Alignment(horizontal="center", vertical="center")
    alin_esq = Alignment(horizontal="left", vertical="center")
    fonte_cab = Font(bold=True)
    max_row = ws.max_row
    max_col = ws.max_column
    for col_idx in range(1, max_col + 1):
        letra = get_column_letter(col_idx)
        titulo = str(ws.cell(row=1, column=col_idx).value or "").strip()
        titulo_norm = normalizar_chave_coluna(titulo)
        ws.cell(row=1, column=col_idx).alignment = alin_centro
        ws.cell(row=1, column=col_idx).font = fonte_cab
        eh_esquerda = any(p in titulo_norm for p in ["descricao", "diagnostico", "acao_ia", "mecanica", "status_margem", "departamento"])
        eh_moeda = any(p in titulo_norm for p in ["custo", "valor", "capital", "preco", "recuperavel", "faturamento", "cmv", "imposto", "lucro", "compras_nf", "total_compra", "total_do_item", "total_estimado"]) and "pct" not in titulo_norm and "variacao" not in titulo_norm and "cresc" not in titulo_norm
        eh_pct = "%" in titulo or "pct" in titulo_norm or "variacao" in titulo_norm
        maior_tam = max(len(titulo), 12)
        for row_idx in range(2, max_row + 1):
            cel = ws.cell(row=row_idx, column=col_idx)
            cel.alignment = alin_esq if eh_esquerda else alin_centro
            val = cel.value
            if isinstance(val, (int, float)):
                if eh_moeda:
                    cel.number_format = "R$ #,##0.00"
                elif eh_pct:
                    cel.number_format = '0.00"%"'
                elif isinstance(val, float) and not val.is_integer():
                    cel.number_format = "#,##0.00"
                else:
                    cel.number_format = "#,##0"
            if val is not None:
                maior_tam = max(maior_tam, min(len(str(val)) + 4, 46))
        ws.column_dimensions[letra].width = max(maior_tam + 3, 14)


def gerar_excel_banco_dados(estado: dict) -> bytes:
    from openpyxl import load_workbook
    buffer_xlsx = io.BytesIO()
    linhas_meta_bkp = [
        {"chave": "dias_base", "valor": str(estado.get("dias_base", 87))},
        {"chave": "ultima_atualizacao", "valor": str(estado.get("ultima_atualizacao", "-"))},
        {"chave": "data_exportacao_backup", "valor": agora_br().strftime("%d/%m/%Y %H:%M:%S")},
    ]
    if str(estado.get("ultima_data_custos_t1", "")).strip():
        linhas_meta_bkp.append({"chave": "ultima_data_custos_t1", "valor": str(estado.get("ultima_data_custos_t1", "")).strip()})
    if str(estado.get("ultimo_backup_semanal", "")).strip():
        linhas_meta_bkp.append({"chave": "ultimo_backup_semanal", "valor": str(estado.get("ultimo_backup_semanal", "")).strip()})
    for pref_k, nome_g in sorted((estado.get("grupos_pref_custom") or {}).items()):
        linhas_meta_bkp.append({"chave": f"grp_pref_{pref_k}", "valor": str(nome_g)})
    for sku_k, nome_g in sorted((estado.get("grupos_sku_custom") or {}).items()):
        linhas_meta_bkp.append({"chave": f"grp_sku_{sku_k}", "valor": str(nome_g)})
    for sku_m, flag_m in sorted((estado.get("mp_custom_map") or {}).items()):
        sku_m_norm = normalizar_codigo_sku(sku_m)
        if sku_m_norm and str(flag_m).strip() in ("0", "1"):
            linhas_meta_bkp.append({"chave": f"mp_flag_{sku_m_norm}", "valor": str(flag_m).strip()})
    df_meta_bkp = pd.DataFrame(linhas_meta_bkp)
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        estado.get("estoque_atual", pd.DataFrame()).to_excel(writer, sheet_name="estoque_atual", index=False)
        estado.get("entradas_diarias", pd.DataFrame()).to_excel(writer, sheet_name="entradas_diarias", index=False)
        estado.get("saidas_diarias", pd.DataFrame()).to_excel(writer, sheet_name="saidas_diarias", index=False)
        estado.get("custos", pd.DataFrame()).to_excel(writer, sheet_name="custos", index=False)
        estado.get("base_inicial", pd.DataFrame()).to_excel(writer, sheet_name="base_inicial", index=False)
        estado.get("ocultos", pd.DataFrame()).to_excel(writer, sheet_name="ocultos", index=False)
        estado.get("pedidos_transito", pd.DataFrame()).to_excel(writer, sheet_name="pedidos_transito", index=False)
        df_meta_bkp.to_excel(writer, sheet_name="meta", index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    for nome_aba in wb.sheetnames:
        _formatar_e_centralizar_aba_openpyxl(wb[nome_aba])
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


def gerar_pacote_backup_leve(estado: dict) -> bytes:
    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        xlsx_bytes = gerar_excel_banco_dados(estado)
        zf.writestr("Banco_Dados_Esteio_Rural.xlsx", xlsx_bytes)
        df_hist = estado.get("historico", pd.DataFrame())
        csv_bytes = df_hist.to_csv(index=False, sep=";").encode("utf-8-sig")
        zf.writestr("historico_2anos.csv", csv_bytes)
    return buffer_zip.getvalue()


@st.cache_data(ttl=3600, max_entries=20, show_spinner=False)
def gerar_excel_relatorio(df: pd.DataFrame, nome_aba: str = "Relatorio") -> bytes:
    from openpyxl import load_workbook
    buffer_xlsx = io.BytesIO()
    aba_limpa = nome_aba[:31]
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=aba_limpa, index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    _formatar_e_centralizar_aba_openpyxl(wb[aba_limpa])
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


@st.cache_data(ttl=3600, max_entries=20, show_spinner=False)
def gerar_excel_com_formulas_cotacao(df_cotacao: pd.DataFrame) -> bytes:
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    buffer_xlsx = io.BytesIO()
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df_cotacao.to_excel(writer, sheet_name="Cotacao_Compras", index=False)
    buffer_xlsx.seek(0)
    wb = load_workbook(buffer_xlsx)
    ws = wb["Cotacao_Compras"]
    max_row = ws.max_row
    max_col = ws.max_column
    fonte_negrito = Font(bold=True)
    alin_centro = Alignment(horizontal="center", vertical="center")
    alin_esq = Alignment(horizontal="left", vertical="center")
    preenchimento_editavel = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")

    mapa_letras = {}
    for c_idx in range(1, max_col + 1):
        ws.cell(row=1, column=c_idx).alignment = alin_centro
        ws.cell(row=1, column=c_idx).font = fonte_negrito
        tit_norm = normalizar_chave_coluna(ws.cell(row=1, column=c_idx).value or "")
        if tit_norm:
            mapa_letras[tit_norm] = get_column_letter(c_idx)

    def _col(chave_norm: str, fallback_letra: str) -> str:
        return mapa_letras.get(chave_norm, fallback_letra)

    col_desc = _col("descricao", "B")
    col_saldo = _col("saldo_atual", "D")
    col_venc = _col("vencido_ou_vencendo_60d", "E")
    col_giro = _col("giro_medio_dia", "F")
    col_auton = _col("autonomia_dias", "G")
    col_pped = mapa_letras.get("ponto_de_pedido_c_seg", "")
    col_sug = _col("sugestao_sistema", "H")
    col_qtd = _col("qtd_a_comprar", "I")
    col_custo_erp = _col("ultimo_custo_erp_r", "J")
    col_custo_cot = _col("custo_atual_cotado_r", "K")
    col_var = _col("variacao_custo", "L")
    col_total = _col("total_do_item_r", "M")

    for r in range(2, max_row + 1):
        for c_idx in range(1, max_col + 1):
            letra_c = get_column_letter(c_idx)
            ws.cell(row=r, column=c_idx).alignment = alin_esq if letra_c == col_desc else alin_centro
        ws[f"{col_saldo}{r}"].number_format = "#,##0"
        ws[f"{col_venc}{r}"].number_format = "#,##0"
        ws[f"{col_giro}{r}"].number_format = "#,##0.00"
        ws[f"{col_auton}{r}"].number_format = "#,##0.0"
        if col_pped:
            ws[f"{col_pped}{r}"].number_format = "#,##0"
        ws[f"{col_sug}{r}"].number_format = "#,##0"
        ws[f"{col_qtd}{r}"].number_format = "#,##0"
        ws[f"{col_qtd}{r}"].fill = preenchimento_editavel
        ws[f"{col_custo_cot}{r}"].fill = preenchimento_editavel
        val_k = ws[f"{col_custo_cot}{r}"].value
        if val_k is not None and float(val_k) == 0.0:
            ws[f"{col_custo_cot}{r}"].value = None
        ws[f"{col_custo_erp}{r}"].number_format = "R$ #,##0.00"
        ws[f"{col_custo_cot}{r}"].number_format = "R$ #,##0.00"
        ws[f"{col_var}{r}"] = (
            f"=IF(AND({col_custo_cot}{r}>0,{col_custo_erp}{r}>0),"
            f"({col_custo_cot}{r}-{col_custo_erp}{r})/{col_custo_erp}{r},0)"
        )
        ws[f"{col_var}{r}"].number_format = "+0.0%;-0.0%;0.0%"
        ws[f"{col_total}{r}"] = f"={col_qtd}{r}*IF({col_custo_cot}{r}>0,{col_custo_cot}{r},{col_custo_erp}{r})"
        ws[f"{col_total}{r}"].number_format = "R$ #,##0.00"

    linha_total = max_row + 2
    ws[f"{col_sug}{linha_total}"] = "TOTAL DO PEDIDO:"
    ws[f"{col_sug}{linha_total}"].font = fonte_negrito
    ws[f"{col_sug}{linha_total}"].alignment = Alignment(horizontal="right", vertical="center")
    ws[f"{col_qtd}{linha_total}"] = f"=SUM({col_qtd}2:{col_qtd}{max_row})"
    ws[f"{col_qtd}{linha_total}"].font = fonte_negrito
    ws[f"{col_qtd}{linha_total}"].alignment = alin_centro
    ws[f"{col_qtd}{linha_total}"].number_format = "#,##0"
    ws[f"{col_total}{linha_total}"] = f"=SUM({col_total}2:{col_total}{max_row})"
    ws[f"{col_total}{linha_total}"].font = fonte_negrito
    ws[f"{col_total}{linha_total}"].alignment = alin_centro
    ws[f"{col_total}{linha_total}"].number_format = "R$ #,##0.00"

    larguras_por_chave = {
        "codigo": 14,
        "descricao": 38,
        "saida_recente_alerta": 26,
        "saldo_atual": 15,
        "vencido_ou_vencendo_60d": 26,
        "giro_medio_dia": 16,
        "autonomia_dias": 16,
        "ponto_de_pedido_c_seg": 19,
        "sugestao_sistema": 17,
        "qtd_a_comprar": 18,
        "ultimo_custo_erp_r": 20,
        "custo_atual_cotado_r": 22,
        "variacao_custo": 18,
        "total_do_item_r": 20,
    }
    for c_idx in range(1, max_col + 1):
        letra_c = get_column_letter(c_idx)
        tit_norm = normalizar_chave_coluna(ws.cell(row=1, column=c_idx).value or "")
        ws.column_dimensions[letra_c].width = larguras_por_chave.get(tit_norm, 16)
    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()




# ==============================================================================
# 6. LEITURA DE UPLOADS, TRAVAS DE DATA/CATÁLOGO E PROCESSADORES SIAGRI
# ==============================================================================


def _preservar_celula_excel(val):
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.strftime("%d/%m/%Y")
    return str(val).strip()


def extrair_data_nome_arquivo(nome_arquivo: str):
    """Extrai a data contida no nome do arquivo (ex: 'Entrada 30-10-2026.xlsx' -> date(2026, 10, 30))."""
    if not nome_arquivo:
        return None
    base = re.sub(r"\.[a-zA-Z0-9]+$", "", str(nome_arquivo))
    m_dmy = re.search(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)", base)
    if m_dmy:
        try:
            return date(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
        except ValueError:
            pass
    m_ymd = re.search(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)", base)
    if m_ymd:
        try:
            return date(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
        except ValueError:
            pass
    return None


def validar_coerencia_data_upload(
    arquivo,
    data_selecionada: date,
    rotulo: str,
    ignorar_trava: bool = False,
) -> str:
    """Impede que uma planilha com data no nome (ex: 30-10-2026) seja importada com data diferente no seletor."""
    if arquivo is None:
        return ""
    nome_arq = getattr(arquivo, "name", "")
    dt_nome = extrair_data_nome_arquivo(nome_arq)
    if dt_nome is not None:
        if dt_nome != data_selecionada and not ignorar_trava:
            raise ValueError(
                f"Trava de Coerência de Data ({rotulo}): O arquivo enviado chama-se **'{nome_arq}'** "
                f"(indicando a data **{dt_nome.strftime('%d/%m/%Y')}**), mas o seletor de data na tela está marcado em "
                f"**{data_selecionada.strftime('%d/%m/%Y')}**. Ajuste a data no seletor para **{dt_nome.strftime('%d/%m/%Y')}** "
                f"antes de sincronizar para evitar gravar o movimento no dia errado!"
            )
        return ""
    return (
        f"ℹ️ **{rotulo}:** O arquivo `'{nome_arq}'` não traz data no nome; "
        f"foi gravado na data selecionada (**{data_selecionada.strftime('%d/%m/%Y')}**)."
    )


def ler_arquivo_upload(arquivo, exigir_multiplas_colunas: bool = False) -> pd.DataFrame:
    nome = arquivo.name.lower()
    conteudo = arquivo.getvalue()
    if nome.endswith(".csv"):
        candidato_1_col = None
        for enc in ["utf-8-sig", "cp1252", "latin1"]:
            for sep in [";", ",", "\t"]:
                try:
                    df = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=enc, dtype=str)
                    if df.shape[1] >= 2:
                        return df
                    if df.shape[1] == 1 and candidato_1_col is None:
                        candidato_1_col = df
                except Exception:
                    continue
        if candidato_1_col is not None and not exigir_multiplas_colunas:
            return candidato_1_col
        raise ValueError("Não foi possível ler o arquivo CSV. Verifique o separador.")
    else:
        df_preview = pd.read_excel(io.BytesIO(conteudo), nrows=0)
        conversores = {col: _preservar_celula_excel for col in df_preview.columns}
        return pd.read_excel(io.BytesIO(conteudo), converters=conversores)


def ler_lista_produtos_cotacao(arquivo) -> pd.DataFrame:
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=False)
    if df_raw is None or df_raw.empty:
        raise ValueError("A planilha enviada para cotação está vazia.")
    cols_norm = {col: normalizar_chave_coluna(col) for col in df_raw.columns}
    col_cod = None
    col_desc = None
    for orig, norm in cols_norm.items():
        if col_cod is None and norm in MAPA_SINONIMOS["codigo"]:
            col_cod = orig
        elif col_desc is None and norm in MAPA_SINONIMOS["descricao"]:
            col_desc = orig
    if col_cod is None:
        col_cod = df_raw.columns[0]
    if col_desc is None and df_raw.shape[1] >= 2:
        for c in df_raw.columns:
            if c != col_cod:
                col_desc = c
                break
    df = pd.DataFrame()
    df["codigo_lista"] = limpar_serie_codigo(df_raw[col_cod])
    if col_desc is not None:
        df["descricao_lista"] = limpar_serie_texto(df_raw[col_desc])
    else:
        df["descricao_lista"] = ""
    df = df[df["codigo_lista"] != ""].copy()
    df = df[~df["codigo_lista"].str.lower().isin(["codigo", "código", "cod", "sku", "id", "item", "total"])].copy()
    df = df.drop_duplicates(subset=["codigo_lista"], keep="first").reset_index(drop=True)
    return df


def validar_estrutura_e_coincidencia_codigos(
    df_novo: pd.DataFrame,
    codigos_referencia: set,
    nome_planilha: str,
    ignorar_trava_catalogo: bool = False,
    exigir_cobertura_total: bool = True,
) -> float:
    if df_novo.empty or "codigo" not in df_novo.columns:
        return 100.0
    if "descricao" in df_novo.columns:
        df_desc_validas = df_novo[df_novo["descricao"] != ""]
        if not df_desc_validas.empty:
            desc_por_cod = df_desc_validas.groupby("codigo")["descricao"].nunique()
            codigos_ambiguos = desc_por_cod[desc_por_cod > 1]
            if len(codigos_ambiguos) > max(int(len(desc_por_cod) * 0.05), 10) and not ignorar_trava_catalogo:
                ex_amb = ", ".join(f"'{c}'" for c in codigos_ambiguos.index[:6])
                raise ValueError(
                    f"Trava contra Colunas Trocadas ({nome_planilha}): A coluna lida como 'Código' possui "
                    f"{len(codigos_ambiguos)} valores que se repetem em produtos com descrições diferentes "
                    f"(ex: {ex_amb}). Isso indica que uma coluna de Saldo ou Quantidade foi colocada no lugar do Código!"
                )
    if not codigos_referencia:
        return 100.0
    cods_novos = {normalizar_codigo_sku(c) for c in df_novo["codigo"].unique() if normalizar_codigo_sku(c)}
    cods_ref_norm = {normalizar_codigo_sku(c) for c in codigos_referencia if normalizar_codigo_sku(c)}
    if not cods_ref_norm:
        return 100.0
    intersecao = cods_novos & cods_ref_norm
    taxa_sobre_novo = (len(intersecao) / max(len(cods_novos), 1)) * 100.0
    taxa_sobre_anterior = (len(intersecao) / max(len(cods_ref_norm), 1)) * 100.0
    taxa_avaliada = min(taxa_sobre_novo, taxa_sobre_anterior) if exigir_cobertura_total else taxa_sobre_novo
    if taxa_avaliada < LIMITE_COINCIDENCIA_CATALOGO and not ignorar_trava_catalogo:
        estranhos = sorted(list(cods_novos - cods_ref_norm))[:8]
        amostra_estranhos = ", ".join(f"'{c}'" for c in estranhos) if estranhos else "N/A"
        raise ValueError(
            f"Trava contra Colunas Trocadas ({nome_planilha}): Apenas **{taxa_avaliada:.1f}%** dos códigos "
            f"coincidem com a base anterior ({len(intersecao)} coincidentes entre {len(cods_novos)} enviados "
            f"e {len(cods_ref_norm)} cadastrados; mínimo exigido: {LIMITE_COINCIDENCIA_CATALOGO:.0f}%). "
            f"Exemplos de códigos lidos na 1ª coluna: {amostra_estranhos}. "
            f"Verifique se a ordem das colunas da planilha não foi trocada!"
        )
    return taxa_avaliada


def processar_planilha_estoque(
    arquivo,
    data_pos: date,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
    ignorar_trava_data: bool = False,
) -> tuple[pd.DataFrame, dict]:
    aviso_sem_data = validar_coerencia_data_upload(
        arquivo, data_pos, "Posição de Estoque", ignorar_trava=ignorar_trava_data
    )
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 6:
        raise ValueError(
            f"A planilha de estoque precisa ter pelo menos 6 colunas (encontradas: {df_raw.shape[1]})."
        )
    df = estruturar_dataframe_bruto(df_raw, "estoque_atual", exigir_colunas_obrigatorias=True)
    df["data"] = data_pos.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Estoque): Nenhuma linha válida de produto foi encontrada na planilha."
        )
    soma_saldo_geral = float(df["saldo_geral"].abs().sum())
    if soma_saldo_geral <= 0:
        raise ValueError(
            "Trava de Segurança (Estoque): Todos os saldos gerais vieram ZERADOS (0). "
            "Verifique se a coluna 'Saldo Geral' está na posição correta (2ª coluna) ou se o arquivo está correto."
        )
    tem_lotes_informados = (df["lote"] != "").any()
    soma_saldo_lote = float(df["saldo_lote"].abs().sum())
    if tem_lotes_informados and soma_saldo_lote <= 0:
        raise ValueError(
            "Trava de Segurança (Estoque): Há lotes informados na planilha, mas todos os 'Saldos do Lote' "
            "vieram ZERADOS (0). Verifique a 5ª coluna do arquivo antes de importar."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Estoque",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=True,
    )
    linhas_antes = len(df)
    mask_dup = df.duplicated(subset=["codigo", "lote"], keep="last")
    qtd_duplicadas = int(mask_dup.sum())
    exemplos_dup = []
    if qtd_duplicadas > 0:
        df_ex = df.loc[mask_dup, ["codigo", "descricao", "lote"]].head(8)
        exemplos_dup = [
            f"{r['codigo']} ({r['descricao'][:25]} - Lote: {r['lote'] or 'S/L'})"
            for _, r in df_ex.iterrows()
        ]
    df_final = padronizar_dataframe(df, "estoque_atual")
    info_dup = {
        "linhas_lidas": linhas_antes,
        "linhas_finais": len(df_final),
        "qtd_duplicadas": qtd_duplicadas,
        "exemplos": exemplos_dup,
        "taxa_coincidencia": taxa_coincidencia,
        "aviso_sem_data": aviso_sem_data,
    }
    return df_final, info_dup


def processar_planilha_custos(
    arquivo,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
    data_custos: date = None,
    ignorar_trava_data: bool = False,
) -> tuple[pd.DataFrame, dict]:
    aviso_sem_data = (
        validar_coerencia_data_upload(
            arquivo, data_custos, "Custos C1 & Preços T1", ignorar_trava=ignorar_trava_data
        )
        if data_custos is not None
        else ""
    )
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError("A planilha de Custos & Preços precisa ter pelo menos 3 colunas (Código, Descrição, T1/C1).")
    cols_norm_raw = {normalizar_chave_coluna(c) for c in df_raw.columns}
    tem_coluna_t1 = (df_raw.shape[1] >= 4) or any(
        n in MAPA_SINONIMOS["preco_tabela"] for n in cols_norm_raw
    )
    df = estruturar_dataframe_bruto(df_raw, "custos", exigir_colunas_obrigatorias=True)
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Custos & Preços): Nenhum produto válido encontrado na planilha."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Custos & Preços (C1/T1)",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=False,
    )
    qtd_dup_custos = int(df.duplicated(subset=["codigo"], keep="last").sum())
    df_final = padronizar_dataframe(df, "custos")
    qtd_positivos = int((df_final["custo_unitario"] > 0).sum())
    if qtd_positivos == 0:
        raise ValueError(
            "Trava de Segurança (Custos C1): Todos os custos unitários vieram ZERADOS (R$ 0,00). "
            "A importação foi bloqueada para proteger a Curva ABC e o FEFO. Verifique a coluna C1 da planilha."
        )
    qtd_zerados = int((df_final["custo_unitario"] <= 0).sum())
    qtd_t1_positivos = int((df_final["preco_tabela"] > 0).sum()) if "preco_tabela" in df_final.columns else 0
    info_custos = {
        "total_itens": len(df_final),
        "qtd_positivos": qtd_positivos,
        "qtd_zerados": qtd_zerados,
        "qtd_t1_positivos": qtd_t1_positivos,
        "tem_coluna_t1": tem_coluna_t1,
        "qtd_duplicadas": qtd_dup_custos,
        "taxa_coincidencia": taxa_coincidencia,
        "aviso_sem_data": aviso_sem_data,
    }
    return df_final, info_custos


def processar_planilha_base_vendas(
    arquivo,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
) -> tuple[pd.DataFrame, dict]:
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError("A Base Inicial de Vendas precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade).")
    df = estruturar_dataframe_bruto(df_raw, "base_inicial", exigir_colunas_obrigatorias=True)
    if df.empty:
        raise ValueError(
            "Trava de Segurança (Base de Vendas): Nenhum registro válido encontrado na planilha."
        )
    taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
        df_novo=df,
        codigos_referencia=codigos_ref,
        nome_planilha="Base Inicial de Vendas",
        ignorar_trava_catalogo=ignorar_trava_catalogo,
        exigir_cobertura_total=False,
    )
    desc_por_sku = df[df["descricao"] != ""].groupby("codigo")["descricao"].nunique()
    qtd_desc_divergentes = int((desc_por_sku > 1).sum())
    df_agrupado = df.groupby("codigo", as_index=False).agg(
        descricao=("descricao", "last"),
        qtd_vendida=("qtd_vendida", "sum"),
    )
    df_final = padronizar_dataframe(df_agrupado, "base_inicial")
    soma_vendas = float(df_final["qtd_vendida"].sum())
    if soma_vendas <= 0:
        raise ValueError(
            "Trava de Segurança (Base de Vendas): A soma das quantidades vendidas veio ZERADA (0). "
            "A importação foi bloqueada para não zerar o cálculo de giro. Verifique a 3ª coluna da planilha."
        )
    info_base = {
        "total_itens": len(df_final),
        "soma_vendas": soma_vendas,
        "qtd_zerados": int((df_final["qtd_vendida"] <= 0).sum()),
        "qtd_desc_divergentes": qtd_desc_divergentes,
        "taxa_coincidencia": taxa_coincidencia,
    }
    return df_final, info_base


def processar_planilha_movimento_diario(
    arquivo,
    data_mov: date,
    nome_aba: str,
    col_qtd: str,
    rotulo_amigavel: str,
    codigos_ref: set,
    ignorar_trava_catalogo: bool = False,
    ignorar_trava_data: bool = False,
) -> tuple[pd.DataFrame, dict]:
    aviso_sem_data = validar_coerencia_data_upload(
        arquivo, data_mov, rotulo_amigavel, ignorar_trava=ignorar_trava_data
    )
    df_raw = ler_arquivo_upload(arquivo, exigir_multiplas_colunas=True)
    if df_raw.shape[1] < 3:
        raise ValueError(
            f"A planilha de {rotulo_amigavel} precisa ter pelo menos 3 colunas (Código, Descrição, Quantidade)."
        )
    coluna_valor_lida = ""
    eh_custo_unitario_direto = False
    if nome_aba == "saidas_diarias":
        termos_fin_v = ("valor", "vlr", "proposta", "faturamento", "receita", "preco", "liquido", "bruto", "total_venda")
        termos_nao_fin_v = ("saldo", "estoque", "lote", "validade", "custo", "cmv", "cod", "qtd", "quant", "data")
        for c_orig in df_raw.columns:
            n_c = normalizar_chave_coluna(c_orig)
            if n_c in MAPA_SINONIMOS["valor_venda"] or (
                any(t in n_c for t in termos_fin_v) and not any(b in n_c for b in termos_nao_fin_v)
            ):
                coluna_valor_lida = str(c_orig).strip()
                break
    elif nome_aba == "entradas_diarias":
        termos_fin_e = ("valor", "vlr", "custo", "c1", "nf", "nota", "liquido", "bruto", "total")
        termos_nao_fin_e = ("saldo", "estoque", "lote", "validade", "cod", "qtd", "quant", "data", "preco", "venda", "proposta", "faturamento", "receita")
        cols_norm_e = {c_orig: normalizar_chave_coluna(c_orig) for c_orig in df_raw.columns}
        col_escolhida_ent = None
        for sin_e in MAPA_SINONIMOS["valor_entrada"]:
            for c_orig, n_c in cols_norm_e.items():
                if n_c == sin_e and not any(b in n_c for b in termos_nao_fin_e):
                    col_escolhida_ent = c_orig
                    break
            if col_escolhida_ent is not None:
                break
        if col_escolhida_ent is None:
            for c_orig, n_c in cols_norm_e.items():
                if any(t in n_c for t in termos_fin_e) and not any(b in n_c for b in termos_nao_fin_e):
                    col_escolhida_ent = c_orig
                    break
        if col_escolhida_ent is not None:
            coluna_valor_lida = str(col_escolhida_ent).strip()
            n_c_esc = cols_norm_e[col_escolhida_ent]
            if any(u in n_c_esc for u in ("unitario", "unit", "c1", "medio")):
                eh_custo_unitario_direto = True
            if n_c_esc not in MAPA_SINONIMOS["valor_entrada"]:
                df_raw = df_raw.rename(columns={col_escolhida_ent: "valor_entrada"})
    df = estruturar_dataframe_bruto(df_raw, nome_aba, exigir_colunas_obrigatorias=True)
    if nome_aba == "entradas_diarias" and eh_custo_unitario_direto and "valor_entrada" in df.columns:
        df["valor_entrada"] = df["qtd_entrada"] * df["valor_entrada"]
    data_iso = data_mov.strftime("%Y-%m-%d")
    df["data"] = data_iso
    if df.empty:
        raise ValueError(
            f"Trava de Segurança ({rotulo_amigavel}): Nenhum registro válido encontrado na planilha."
        )
    taxa_coincidencia = 100.0
    if len(df) >= 5 and codigos_ref:
        taxa_coincidencia = validar_estrutura_e_coincidencia_codigos(
            df_novo=df,
            codigos_referencia=codigos_ref,
            nome_planilha=rotulo_amigavel,
            ignorar_trava_catalogo=ignorar_trava_catalogo,
            exigir_cobertura_total=False,
        )
    contagem_por_sku = df.groupby("codigo")[col_qtd].count()
    cods_repetidos = contagem_por_sku[contagem_por_sku > 1].index.tolist()
    qtd_codigos_repetidos = len(cods_repetidos)
    qtd_linhas_extras = int(df.duplicated(subset=["codigo"], keep="first").sum())
    exemplos_repetidos = []
    if qtd_codigos_repetidos > 0:
        for cod_r in cods_repetidos[:6]:
            sub_r = df[df["codigo"] == cod_r]
            parcelas_str = "+".join(formatar_qtd_br(v) for v in sub_r[col_qtd].tolist()[:4])
            if len(sub_r) > 4:
                parcelas_str += "+..."
            soma_r = float(sub_r[col_qtd].sum())
            exemplos_repetidos.append(f"SKU {cod_r} ({parcelas_str} = {formatar_qtd_br(soma_r)})")
    agg_mov = {
        "descricao": ("descricao", "last"),
        col_qtd: (col_qtd, "sum"),
    }
    if "valor_entrada" in df.columns:
        agg_mov["valor_entrada"] = ("valor_entrada", "sum")
    if "valor_venda" in df.columns:
        agg_mov["valor_venda"] = ("valor_venda", "sum")
    agg_mov["data"] = ("data", "last")
    df_agrupado = df.groupby("codigo", as_index=False).agg(**agg_mov)
    df_agrupado = df_agrupado[df_agrupado[col_qtd] > 0].copy()
    if df_agrupado.empty:
        raise ValueError(
            f"Trava de Segurança ({rotulo_amigavel}): Todas as quantidades vieram ZERADAS (0). "
            "Verifique a 3ª coluna da planilha antes de importar."
        )
    df_final = padronizar_dataframe(df_agrupado, nome_aba)
    soma_qtd = float(df_final[col_qtd].sum())
    soma_valor_venda = float(df_final["valor_venda"].sum()) if "valor_venda" in df_final.columns else 0.0
    soma_valor_entrada = float(df_final["valor_entrada"].sum()) if "valor_entrada" in df_final.columns else 0.0
    df_custos_extraidos = pd.DataFrame(columns=["codigo", "descricao", "custo_unitario"])
    if nome_aba == "entradas_diarias" and "valor_entrada" in df_final.columns:
        df_c_val = df_final[(df_final["qtd_entrada"] > 0) & (df_final["valor_entrada"] > 0)].copy()
        if not df_c_val.empty:
            df_c_val["custo_unitario"] = (df_c_val["valor_entrada"] / df_c_val["qtd_entrada"]).round(4)
            df_custos_extraidos = df_c_val[["codigo", "descricao", "custo_unitario"]].copy()
    return df_final, {
        "total_itens": len(df_final),
        "soma_qtd": soma_qtd,
        "soma_valor_venda": soma_valor_venda,
        "soma_valor_entrada": soma_valor_entrada,
        "coluna_valor_venda": coluna_valor_lida if nome_aba == "saidas_diarias" else "",
        "coluna_valor_entrada": coluna_valor_lida if nome_aba == "entradas_diarias" else "",
        "df_custos_extraidos": df_custos_extraidos,
        "data_iso": data_iso,
        "taxa_coincidencia": taxa_coincidencia,
        "qtd_codigos_repetidos": qtd_codigos_repetidos,
        "qtd_linhas_extras": qtd_linhas_extras,
        "exemplos_repetidos": exemplos_repetidos,
        "aviso_sem_data": aviso_sem_data,
    }




# ==============================================================================
# 7. DEPARTAMENTOS SIAGRI, MATÉRIA-PRIMA (MP), BACKUP SEMANAL E METADADOS
# ==============================================================================


MAPA_DEPARTAMENTOS_SIAGRI = {
    "50": "50 - Veterinária & Reprodução",
    "70": "70 - Ferragens, Lonas & Selaria",
    "26": "26 - Nutrição & Matéria-Prima (MP)",
    "90": "90 - Rações, Milho & Grãos",
    "60": "60 - Máquinas, Pulv. & EPIs",
    "20": "20 - Domissanitários & Defensivos",
    "11": "11 - Hidráulica, Tubos & Parafusos",
    "12": "12 - Bombas, Boias & Conexões",
    "13": "13 - Botinas, Calçados & Vestuário",
    "15": "15 - Óleos, Graxas & Lubrificantes",
    "80": "80 - Arames, Cordoalhas & Cercas",
    "30": "30 - Adubos, Sementes & Agrícola",
    "10": "10 - Inseticidas & Desinfetantes",
    "16": "16 - Linha Pet & Aves",
}


def construir_mapa_departamentos(mapa_pref_custom: dict = None) -> dict:
    mapa = dict(MAPA_DEPARTAMENTOS_SIAGRI)
    if mapa_pref_custom:
        for k, v in mapa_pref_custom.items():
            ks = str(k).strip()
            vs = str(v).strip()
            if ks and vs:
                mapa[ks] = vs
    return mapa


def identificar_departamento_sku(
    codigo: str,
    mapa_pref_custom: dict = None,
    mapa_sku_custom: dict = None,
) -> str:
    cod_s = normalizar_codigo_sku(codigo)
    if not cod_s:
        cod_s = str(codigo).strip()
    if mapa_sku_custom and cod_s in mapa_sku_custom and str(mapa_sku_custom[cod_s]).strip():
        return str(mapa_sku_custom[cod_s]).strip()
    pref = cod_s[:2] if len(cod_s) >= 2 else cod_s
    mapa_base = construir_mapa_departamentos(mapa_pref_custom)
    return mapa_base.get(pref, f"Outros ({pref or 'S/C'})")


def identificar_produto_mp(
    codigo: str,
    descricao: str,
    grupos_sku_custom: dict = None,
    mp_custom_map: dict = None,
) -> bool:
    """
    Identifica se um produto é Matéria-Prima de Fábrica (saída via Ordem de Produção):
    1) Respeita marcação explícita em mp_custom_map ('1' = MP, '0' = Revenda Loja).
    2) Respeita se o SKU foi fixado manualmente em grupo de Matéria-Prima (MP).
    3) Regra padrão limpa: descrição iniciada em 'MP ' ou 'ME ' (microelementos de fábrica),
       sem marcar automaticamente todo o prefixo '26' (que contém itens de varejo como laços e medicamentos).
    """
    cod_s = normalizar_codigo_sku(codigo)
    if not cod_s:
        cod_s = str(codigo).strip()
    if mp_custom_map and cod_s in mp_custom_map:
        return str(mp_custom_map[cod_s]).strip() == "1"
    if grupos_sku_custom and cod_s in grupos_sku_custom:
        grp_s = str(grupos_sku_custom[cod_s]).strip().lower()
        if "matéria-prima" in grp_s or "materia-prima" in grp_s or "(mp)" in grp_s:
            return True
    desc_up = str(descricao).strip().upper()
    return desc_up.startswith("MP ") or desc_up.startswith("ME ")


def avaliar_alerta_backup_semanal(ultimo_backup_iso: str, hoje_ref: date = None) -> tuple[bool, int | None, str]:
    """
    Avalia se o alerta semanal de backup deve ser exibido (7 dias ou mais sem download).
    Retorna (deve_alertar, dias_decorridos, data_formatada_br).
    """
    ref = hoje_ref or hoje_br()
    s_bkp = str(ultimo_backup_iso or "").strip()
    if not s_bkp:
        return True, None, ""
    dt_parsed = _parse_data_segura_py(s_bkp, ano_min=2020, ano_max=ref.year + 2)
    if dt_parsed is None:
        return True, None, ""
    dias_diff = max(0, int((ref - dt_parsed.date()).days))
    return (dias_diff >= 7), dias_diff, dt_parsed.strftime("%d/%m/%Y")


def montar_dataframe_meta_completo(
    dias_base_val: int,
    ult_att_val: str,
    grupos_pref_custom: dict = None,
    grupos_sku_custom: dict = None,
    hashes_soma_por_data: dict = None,
    mp_custom_map: dict = None,
    ultima_data_custos_t1: str = None,
    ultimo_backup_semanal: str = None,
) -> pd.DataFrame:
    linhas = [
        {"chave": "dias_base", "valor": str(int(dias_base_val))},
        {"chave": "ultima_atualizacao", "valor": str(ult_att_val)},
    ]
    dt_c1_t1_ref = (
        str(ultima_data_custos_t1).strip()
        if ultima_data_custos_t1 is not None
        else str(st.session_state.get("ultima_data_custos_t1_sessao", "")).strip()
    )
    if dt_c1_t1_ref:
        linhas.append({"chave": "ultima_data_custos_t1", "valor": dt_c1_t1_ref})
    dt_bkp_ref = (
        str(ultimo_backup_semanal).strip()
        if ultimo_backup_semanal is not None
        else str(st.session_state.get("ultimo_backup_semanal_sessao", "")).strip()
    )
    if dt_bkp_ref:
        linhas.append({"chave": "ultimo_backup_semanal", "valor": dt_bkp_ref})
    if grupos_pref_custom:
        for pk, pv in sorted(grupos_pref_custom.items()):
            if str(pk).strip() and str(pv).strip():
                linhas.append({"chave": f"grp_pref_{str(pk).strip()}", "valor": str(pv).strip()})
    if grupos_sku_custom:
        for sk, sv in sorted(grupos_sku_custom.items()):
            sk_norm = normalizar_codigo_sku(sk)
            if sk_norm and str(sv).strip():
                linhas.append({"chave": f"grp_sku_{sk_norm}", "valor": str(sv).strip()})
    mp_ref = mp_custom_map if mp_custom_map is not None else st.session_state.get("mp_custom_map_sessao", {})
    if mp_ref:
        for sk_m, flag_m in sorted(mp_ref.items()):
            sk_norm = normalizar_codigo_sku(sk_m)
            if sk_norm and str(flag_m).strip() in ("0", "1"):
                linhas.append({"chave": f"mp_flag_{sk_norm}", "valor": str(flag_m).strip()})
    hashes_ref = hashes_soma_por_data if hashes_soma_por_data is not None else st.session_state.get("hashes_soma_por_data", {})
    if hashes_ref:
        limite_iso_m = (hoje_br() - timedelta(days=DIAS_MAX_HISTORICO)).strftime("%Y-%m-%d")
        for ch_op, lista_h in sorted(hashes_ref.items()):
            partes_op = str(ch_op).split("::")
            if len(partes_op) == 2 and partes_op[1] >= limite_iso_m and lista_h:
                hashes_unicos = []
                for h_item in lista_h:
                    hs = str(h_item).strip()
                    if hs and hs not in hashes_unicos:
                        hashes_unicos.append(hs)
                if hashes_unicos:
                    linhas.append({"chave": f"soma_hashes_{ch_op}", "valor": ",".join(hashes_unicos)})
    return pd.DataFrame(linhas)
