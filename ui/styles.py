"""
ui/styles.py — Tema Obsidian Dark Neon Bento UI e helpers de tabelas/gráficos selecionáveis
(Esteio Rural — Arquitetura Modular v37).
"""
import streamlit as st


def aplicar_tema_obsidian_bento() -> None:
    """Injeta o CSS global Obsidian Dark Neon & Bento Glassmorphism."""
    st.markdown(
        """
        <style>
        /* Fundo Obsidian Dark com luzes radiais suaves estilo Bento SaaS */
        .stApp {
            background:
                radial-gradient(circle at 12% 10%, rgba(124, 58, 237, 0.16) 0%, transparent 38%),
                radial-gradient(circle at 88% 16%, rgba(16, 185, 129, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 50% 90%, rgba(59, 130, 246, 0.10) 0%, transparent 45%),
                linear-gradient(180deg, #0b0d14 0%, #0f131f 55%, #090b10 100%);
            color: #f8fafc;
        }
        /* Remove a barra preta superior do Streamlit e garante espaçamento perfeito para o cabeçalho e logo */
        header[data-testid="stHeader"] {
            background: transparent !important;
            background-color: transparent !important;
            backdrop-filter: none !important;
        }
        div[data-testid="stDecoration"] {
            display: none !important;
        }
        .block-container {
            max-width: 100% !important;
            padding-top: 3.4rem !important;
            padding-bottom: 2.2rem !important;
            padding-left: 1.15rem !important;
            padding-right: 1.15rem !important;
        }
        /* Cartões Bento Glassmorphism */
        .glass-card {
            background: linear-gradient(145deg, rgba(22, 27, 44, 0.88) 0%, rgba(15, 18, 30, 0.94) 100%);
            border: 1px solid rgba(139, 92, 246, 0.26);
            border-radius: 18px;
            padding: 18px 20px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(16px);
            margin-bottom: 14px;
            transition: transform 0.18s ease, border-color 0.18s ease;
        }
        .glass-card:hover {
            border-color: rgba(16, 185, 129, 0.45);
        }
        /* Caixa de Status Superior */
        .status-box {
            background: linear-gradient(135deg, rgba(22, 27, 44, 0.92) 0%, rgba(16, 22, 36, 0.96) 100%);
            border: 1px solid rgba(45, 212, 191, 0.40);
            border-radius: 16px;
            padding: 12px 18px;
            text-align: left;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45), 0 0 18px rgba(16, 185, 129, 0.12);
        }
        .status-label {
            font-size: 0.74rem;
            color: #94a3b8;
            margin-bottom: 3px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .status-value {
            font-size: 1.22rem;
            font-weight: 800;
            color: #f8fafc;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        /* Pílulas de Tags */
        .pill-tag {
            display: inline-block;
            background: rgba(139, 92, 246, 0.16);
            border: 1px solid rgba(167, 139, 250, 0.38);
            color: #c4b5fd;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            font-family: monospace;
            margin: 2px 4px 2px 0;
        }
        /* Barra de Abas Estilo Segmented Pill Neon (Inspirado no modelo de UI) */
        div[data-baseweb="tab-list"] {
            background: rgba(18, 22, 36, 0.90) !important;
            border: 1px solid rgba(148, 163, 184, 0.16) !important;
            border-radius: 16px !important;
            padding: 5px 6px !important;
            gap: 4px !important;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45) !important;
            margin-bottom: 16px !important;
            flex-wrap: wrap !important;
        }
        button[data-baseweb="tab"] {
            background: transparent !important;
            border-radius: 10px !important;
            padding: 8px 11px !important;
            color: #94a3b8 !important;
            font-weight: 600 !important;
            font-size: 0.83rem !important;
            border: 1px solid transparent !important;
            transition: all 0.2s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            color: #f8fafc !important;
            background: rgba(139, 92, 246, 0.12) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            border: 1px solid rgba(196, 181, 253, 0.45) !important;
            box-shadow: 0 4px 18px rgba(124, 58, 237, 0.50) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] p,
        button[data-baseweb="tab"][aria-selected="true"] span,
        button[data-baseweb="tab"][aria-selected="true"] div {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        div[data-baseweb="tab-highlight"],
        div[data-baseweb="tab-border"] {
            display: none !important;
        }
        /* Cartões de Métricas Nativos Estilizados */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, rgba(22, 27, 44, 0.90) 0%, rgba(14, 18, 30, 0.95) 100%);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 16px;
            padding: 14px 18px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.40);
        }
        /* Botões Primários com Gradiente Roxo/Indigo Neon */
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%) !important;
            border: 1px solid rgba(196, 181, 253, 0.40) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            box-shadow: 0 6px 20px rgba(124, 58, 237, 0.38) !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 8px 25px rgba(124, 58, 237, 0.58) !important;
        }
        /* Bento Hero Grid Customizada (Topo do Dashboard) */
        .bento-grid {
            display: grid;
            grid-template-columns: 1.55fr 1.15fr 0.95fr 1.15fr;
            gap: 16px;
            margin-top: 8px;
            margin-bottom: 18px;
        }
        @media (max-width: 1100px) {
            .bento-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        @media (max-width: 680px) {
            .bento-grid {
                grid-template-columns: 1fr;
            }
        }
        .bento-card {
            position: relative;
            overflow: hidden;
            border-radius: 20px;
            padding: 20px 22px;
            background: linear-gradient(155deg, rgba(23, 28, 46, 0.95) 0%, rgba(13, 16, 28, 0.98) 100%);
            border: 1px solid rgba(148, 163, 184, 0.16);
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.07);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 168px;
        }
        .bento-card-emerald {
            background:
                radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.22) 0%, transparent 55%),
                linear-gradient(155deg, rgba(20, 31, 44, 0.96) 0%, rgba(11, 18, 26, 0.98) 100%);
            border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .bento-card-purple {
            background:
                radial-gradient(circle at 85% 20%, rgba(139, 92, 246, 0.24) 0%, transparent 55%),
                linear-gradient(155deg, rgba(26, 23, 48, 0.96) 0%, rgba(14, 14, 28, 0.98) 100%);
            border: 1px solid rgba(139, 92, 246, 0.35);
        }
        .bento-card-amber {
            background:
                radial-gradient(circle at 50% 50%, rgba(249, 115, 22, 0.14) 0%, transparent 60%),
                linear-gradient(155deg, rgba(25, 24, 38, 0.96) 0%, rgba(14, 15, 25, 0.98) 100%);
            border: 1px solid rgba(249, 115, 22, 0.32);
            align-items: center;
            justify-content: center;
            text-align: center;
        }
        .bento-card-cyan {
            background:
                radial-gradient(circle at 90% 85%, rgba(6, 182, 212, 0.20) 0%, transparent 55%),
                linear-gradient(155deg, rgba(20, 27, 45, 0.96) 0%, rgba(12, 17, 29, 0.98) 100%);
            border: 1px solid rgba(6, 182, 212, 0.32);
        }
        .bento-title {
            font-size: 0.82rem;
            font-weight: 600;
            color: #94a3b8;
            letter-spacing: 0.02em;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .bento-big-val {
            font-size: 1.85rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.02em;
            line-height: 1.15;
            margin-bottom: 8px;
        }
        .bento-badge-green {
            display: inline-flex;
            align-items: center;
            background: rgba(16, 185, 129, 0.18);
            border: 1px solid rgba(16, 185, 129, 0.45);
            color: #34d399;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
            width: fit-content;
        }
        .bento-badge-purple {
            display: inline-flex;
            align-items: center;
            background: rgba(139, 92, 246, 0.20);
            border: 1px solid rgba(167, 139, 250, 0.45);
            color: #c4b5fd;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
            width: fit-content;
        }
        .bento-badge-amber {
            display: inline-flex;
            align-items: center;
            background: rgba(245, 158, 11, 0.18);
            border: 1px solid rgba(251, 191, 36, 0.45);
            color: #fbbf24;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
            width: fit-content;
        }
        .bento-sub {
            font-size: 0.77rem;
            color: #94a3b8;
            margin-top: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _renderizar_dataframe_selecionavel(
    styler_ou_df,
    key: str,
    height: int = None,
    column_config: dict = None,
) -> list:
    """Renderiza st.dataframe com seleção de linha (on_select='rerun') e retorna os índices clicados."""
    kwargs_df = {
        "use_container_width": True,
        "hide_index": True,
        "key": key,
    }
    if height is not None:
        kwargs_df["height"] = height
    if column_config is not None:
        kwargs_df["column_config"] = column_config
    try:
        evento = st.dataframe(
            styler_ou_df,
            on_select="rerun",
            selection_mode="single-row",
            **kwargs_df,
        )
        if evento is not None and hasattr(evento, "selection") and hasattr(evento.selection, "rows"):
            return list(evento.selection.rows)
        if isinstance(evento, dict):
            return list(evento.get("selection", {}).get("rows", []))
    except TypeError:
        st.dataframe(styler_ou_df, **kwargs_df)
    return []


def _extrair_selecao_altair(evento, campo_alvo: str):
    """Extrai o valor clicado em um gráfico interativo st.altair_chart(on_select='rerun')."""
    if evento is None:
        return None
    sel_dict = None
    if hasattr(evento, "selection"):
        sel_dict = evento.selection
    elif isinstance(evento, dict):
        sel_dict = evento.get("selection")
    if not sel_dict:
        return None
    try:
        itens = dict(sel_dict) if not isinstance(sel_dict, dict) else sel_dict
    except Exception:
        return None
    for _, val_sel in itens.items():
        if isinstance(val_sel, list) and len(val_sel) > 0 and isinstance(val_sel[0], dict):
            if campo_alvo in val_sel[0]:
                return val_sel[0][campo_alvo]
        elif isinstance(val_sel, dict):
            if campo_alvo in val_sel:
                v_c = val_sel[campo_alvo]
                if isinstance(v_c, list) and v_c:
                    return v_c[0]
                if isinstance(v_c, str):
                    return v_c
    return None
