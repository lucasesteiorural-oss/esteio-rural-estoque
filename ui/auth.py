"""
ui/auth.py — Tela de login fail-closed por usuário/senha e controle de sessão
(Esteio Rural — Arquitetura Modular v37).
"""
import hmac
from datetime import timedelta
import streamlit as st

from parsers import agora_br
from database import (
    _normalizar_username,
    obter_credencial_admin_mestre,
    _autenticar_usuario_no_banco,
)


def verificar_autenticacao() -> bool:
    admin_user, admin_nome, senha_correta = obter_credencial_admin_mestre()
    if not senha_correta:
        st.error(
            "🔒 **Acesso Bloqueado por Segurança:** A credencial `app_password` não foi configurada "
            "em `st.secrets`. Adicione `app_password = \"SuaSenhaForte\"` nas configurações de Secrets "
            "do Streamlit Cloud (ou em `.streamlit/secrets.toml`) para liberar o acesso ao sistema."
        )
        return False
    if st.session_state.get("autenticado_esteio", False):
        if "usuario_logado" not in st.session_state:
            st.session_state["usuario_logado"] = admin_user
            st.session_state["nome_usuario_logado"] = admin_nome
            st.session_state["eh_admin_esteio"] = True
        return True
    col_v1, col_login, col_v2 = st.columns([1, 1.4, 1])
    with col_login:
        st.markdown(
            """
            <div class="glass-card" style="margin-top: 40px; text-align: center;">
                <h3>🔒 Esteio Rural — Acesso Restrito</h3>
                <p style="color: #94a3b8; font-size: 0.9rem;">
                    Insira seu <strong>Usuário</strong> e <strong>Senha</strong> para acessar o painel de estoque e custos.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_login_esteio"):
            usuario_digitado = st.text_input("Usuário:", placeholder=f"Ex: {admin_user}")
            senha_digitada = st.text_input("Senha de acesso:", type="password")
            btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
            if btn_entrar:
                agora_login = agora_br()
                bloq_ate = st.session_state.get("login_bloqueado_ate")
                if bloq_ate is not None and agora_login < bloq_ate:
                    seg_rest = max(1, int((bloq_ate - agora_login).total_seconds()))
                    st.error(f"⏳ Muitas tentativas incorretas. Aguarde {seg_rest}s para tentar novamente.")
                else:
                    user_norm = _normalizar_username(usuario_digitado)
                    if not user_norm or not senha_digitada:
                        st.error("⚠️ Preencha o usuário e a senha para entrar.")
                    elif user_norm == admin_user and hmac.compare_digest(
                        senha_digitada.encode("utf-8"), senha_correta.encode("utf-8")
                    ):
                        st.session_state["login_tentativas_falhas"] = 0
                        st.session_state.pop("login_bloqueado_ate", None)
                        st.session_state["autenticado_esteio"] = True
                        st.session_state["usuario_logado"] = admin_user
                        st.session_state["nome_usuario_logado"] = admin_nome
                        st.session_state["eh_admin_esteio"] = True
                        st.rerun()
                    else:
                        ok_db, nome_db, eh_adm_db, msg_err = _autenticar_usuario_no_banco(user_norm, senha_digitada)
                        if ok_db:
                            st.session_state["login_tentativas_falhas"] = 0
                            st.session_state.pop("login_bloqueado_ate", None)
                            st.session_state["autenticado_esteio"] = True
                            st.session_state["usuario_logado"] = user_norm
                            st.session_state["nome_usuario_logado"] = nome_db
                            st.session_state["eh_admin_esteio"] = eh_adm_db
                            st.rerun()
                        else:
                            falhas_at = int(st.session_state.get("login_tentativas_falhas", 0)) + 1
                            st.session_state["login_tentativas_falhas"] = falhas_at
                            if falhas_at >= 5:
                                st.session_state["login_bloqueado_ate"] = agora_login + timedelta(seconds=30)
                                st.session_state["login_tentativas_falhas"] = 0
                            st.error(msg_err or "❌ Usuário ou senha incorretos. Tente novamente.")
    return False
