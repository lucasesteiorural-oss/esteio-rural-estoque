"""
ui/tab_ocultos.py — Aba 7: Gerenciamento de produtos ocultos.
"""
import pandas as pd
import streamlit as st

from parsers import (
    hoje_br,
    formatar_num_br,
    padronizar_dataframe,
)
from database import (
    gravar_tabela_sql,
    salvar_backup_automatico_sql,
    carregar_estado_completo,
)


def render_tab_ocultos(ctx: dict) -> None:
    """Renderiza a Aba 7 — Gerenciamento de Produtos Ocultos."""
    db_supabase = ctx["db_supabase"]
    eh_usuario_admin = ctx["eh_usuario_admin"]
    nome_atual_logado = ctx["nome_atual_logado"]
    df_estoque_bruto = ctx["df_estoque_bruto"]
    df_entradas_bruto = ctx["df_entradas_bruto"]
    df_saidas_bruto = ctx["df_saidas_bruto"]
    df_custos = ctx["df_custos"]
    df_base_vendas = ctx["df_base_vendas"]
    df_ocultos = ctx["df_ocultos"]
    codigos_ocultos = ctx["codigos_ocultos"]

    st.markdown("### 👁️‍🗨️ Ocultar ou Restaurar Produtos dos Relatórios")
    st.caption(
        "Marque as caixas de seleção para ocultar vários produtos de uma só vez (ex: brindes, uso interno ou itens fora de linha). "
        "A lista fica salva diretamente no Supabase (PostgreSQL) e pode ser restaurada a qualquer momento."
    )
    if not eh_usuario_admin:
        st.warning(
            f"🔒 **Acesso Somente Leitura ({nome_atual_logado}):** Apenas o usuário **Administrador** pode ocultar ou restaurar produtos."
        )
    frames_catalogo = []
    if not df_estoque_bruto.empty:
        frames_catalogo.append(df_estoque_bruto[["codigo", "descricao"]])
    if not df_entradas_bruto.empty:
        frames_catalogo.append(df_entradas_bruto[["codigo", "descricao"]])
    if not df_saidas_bruto.empty:
        frames_catalogo.append(df_saidas_bruto[["codigo", "descricao"]])
    if not df_custos.empty:
        frames_catalogo.append(df_custos[["codigo", "descricao"]])
    if not df_base_vendas.empty:
        frames_catalogo.append(df_base_vendas[["codigo", "descricao"]])
    if frames_catalogo:
        df_catalogo = (
            pd.concat(frames_catalogo, ignore_index=True)
            .drop_duplicates(subset=["codigo"], keep="first")
            .sort_values("descricao")
            .reset_index(drop=True)
        )
    else:
        df_catalogo = pd.DataFrame(columns=["codigo", "descricao"])
    col_esq, col_dir = st.columns(2)
    with col_esq:
        st.markdown("#### ✅ Produtos Visíveis nos Relatórios")
        if df_catalogo.empty:
            st.info("Importe suas planilhas na Aba 6 para listar os produtos aqui.")
        else:
            df_visiveis = df_catalogo[~df_catalogo["codigo"].isin(codigos_ocultos)].copy()
            busca_visiveis = st.text_input(
                "🔍 Pesquisar produto visível (Código ou Nome):",
                key="busca_visiveis_oc",
            )
            if busca_visiveis:
                termo_v = busca_visiveis.lower().strip()
                df_visiveis = df_visiveis[
                    df_visiveis["codigo"].str.lower().str.contains(termo_v, na=False, regex=False)
                    | df_visiveis["descricao"].str.lower().str.contains(termo_v, na=False, regex=False)
                ].copy()
            marcar_todos_visiveis = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_visiveis))} produtos listados abaixo",
                value=False,
                key="chk_todos_visiveis",
            )
            df_visiveis.insert(0, "selecionar", marcar_todos_visiveis)
            ed_visiveis = st.data_editor(
                df_visiveis,
                hide_index=True,
                use_container_width=True,
                height=380,
                key="editor_ocultar",
                disabled=["codigo", "descricao"],
                column_config={
                    "selecionar": st.column_config.CheckboxColumn(
                        "Ocultar?",
                        help="Marque para ocultar este produto dos relatórios",
                        default=False,
                    ),
                    "codigo": st.column_config.TextColumn("Código"),
                    "descricao": st.column_config.TextColumn("Descrição"),
                },
            )
            selecionados_para_ocultar = ed_visiveis[ed_visiveis["selecionar"] == True]
            if st.button(
                f"🙈 Ocultar Selecionados ({formatar_num_br(len(selecionados_para_ocultar))})",
                type="primary",
                use_container_width=True,
                disabled=(selecionados_para_ocultar.empty or not eh_usuario_admin),
            ) and eh_usuario_admin:
                with st.spinner("Salvando produtos ocultos no Supabase..."):
                    try:
                        novos_ocultos = selecionados_para_ocultar[["codigo", "descricao"]].copy()
                        novos_ocultos["data_ocultado"] = hoje_br().strftime("%Y-%m-%d")
                        df_ocultos_atualizado = (
                            pd.concat([df_ocultos, novos_ocultos], ignore_index=True)
                            .drop_duplicates(subset=["codigo"], keep="last")
                            .reset_index(drop=True)
                        )
                        salvar_backup_automatico_sql(
                            db_supabase, "ocultos", df_ocultos, permitir_vazio=True
                        )
                        gravar_tabela_sql(
                            db_supabase, "ocultos", df_ocultos_atualizado, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success(f"✅ {formatar_num_br(len(selecionados_para_ocultar))} produto(s) ocultado(s) com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao ocultar produtos: {e}")
    with col_dir:
        st.markdown(f"#### 🙈 Produtos Ocultos ({formatar_num_br(len(df_ocultos))})")
        if df_ocultos.empty:
            st.success("Nenhum produto está oculto no momento. Todos os itens estão visíveis nos relatórios!")
        else:
            busca_ocultos = st.text_input(
                "🔍 Pesquisar entre os ocultos:",
                key="busca_ocultos_oc",
            )
            df_oc_view = df_ocultos.copy()
            if busca_ocultos:
                termo_o = busca_ocultos.lower().strip()
                df_oc_view = df_oc_view[
                    df_oc_view["codigo"].str.lower().str.contains(termo_o, na=False, regex=False)
                    | df_oc_view["descricao"].str.lower().str.contains(termo_o, na=False, regex=False)
                ].copy()
            marcar_todos_ocultos = st.checkbox(
                f"Selecionar todos os {formatar_num_br(len(df_oc_view))} ocultos listados abaixo",
                value=False,
                key="chk_todos_ocultos",
            )
            df_oc_view.insert(0, "restaurar", marcar_todos_ocultos)
            ed_ocultos = st.data_editor(
                df_oc_view,
                hide_index=True,
                use_container_width=True,
                height=380,
                key="editor_restaurar",
                disabled=["codigo", "descricao", "data_ocultado"],
                column_config={
                    "restaurar": st.column_config.CheckboxColumn(
                        "Voltar?",
                        help="Marque para voltar a exibir este produto nos relatórios",
                        default=False,
                    ),
                    "codigo": st.column_config.TextColumn("Código"),
                    "descricao": st.column_config.TextColumn("Descrição"),
                    "data_ocultado": st.column_config.TextColumn("Ocultado em"),
                },
            )
            selecionados_para_restaurar = ed_ocultos[ed_ocultos["restaurar"] == True]
            b_rest_1, b_rest_2 = st.columns(2)
            with b_rest_1:
                btn_restaurar_sel = st.button(
                    f"👁️ Restaurar Marcados ({formatar_num_br(len(selecionados_para_restaurar))})",
                    type="primary",
                    use_container_width=True,
                    disabled=(selecionados_para_restaurar.empty or not eh_usuario_admin),
                )
            with b_rest_2:
                btn_restaurar_todos = st.button(
                    "🔄 Restaurar Todos",
                    use_container_width=True,
                    disabled=(not eh_usuario_admin),
                )
            if (btn_restaurar_sel or btn_restaurar_todos) and eh_usuario_admin:
                with st.spinner("Restaurando produtos no Supabase..."):
                    try:
                        if btn_restaurar_todos:
                            df_ocultos_restante = padronizar_dataframe(pd.DataFrame(), "ocultos")
                        else:
                            cods_remover = set(selecionados_para_restaurar["codigo"].unique())
                            df_ocultos_restante = df_ocultos[~df_ocultos["codigo"].isin(cods_remover)].copy()
                        salvar_backup_automatico_sql(
                            db_supabase, "ocultos", df_ocultos, permitir_vazio=True
                        )
                        gravar_tabela_sql(
                            db_supabase, "ocultos", df_ocultos_restante, permitir_vazio=True
                        )
                        st.session_state.pop("bkp_db_xlsx_bytes", None)
                        st.session_state.pop("backup_zip_bytes", None)
                        carregar_estado_completo.clear()
                        st.success("✅ Produto(s) restaurado(s) para os relatórios com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao restaurar produtos: {e}")
