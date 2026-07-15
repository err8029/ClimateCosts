"""Autenticación mínima de la app: usuario/contraseña contra un hash guardado en
st.secrets (.streamlit/secrets.toml, no versionado - ver .streamlit/secrets.toml.example
y generar_credenciales.py). La contraseña nunca se guarda en texto plano, solo un hash
PBKDF2-SHA256 salteado."""
import hashlib
import hmac

import streamlit as st

from common import load_header_title, load_logo

ITERACIONES_PBKDF2 = 200_000


def _hash_contraseña(contraseña, salt_hex):
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac('sha256', contraseña.encode('utf-8'), salt, ITERACIONES_PBKDF2).hex()


def _credenciales_correctas(usuario, contraseña):
    auth = st.secrets.get('auth', {})
    usuario_ok = hmac.compare_digest(usuario, auth.get('username', ''))
    hash_calculado = _hash_contraseña(contraseña, auth.get('password_salt', ''))
    contraseña_ok = hmac.compare_digest(hash_calculado, auth.get('password_hash', ''))
    return usuario_ok and contraseña_ok


def requerir_login():
    """Bloquea el resto de la app (st.stop()) hasta que se introduzcan credenciales
    correctas. Debe llamarse justo después de st.set_page_config(), antes de construir
    la navegación."""
    if st.session_state.get('autenticado'):
        return

    load_header_title()
    load_logo()

    st.title("🌍 Apollo")
    st.caption("Inicia sesión para continuar.")

    with st.form("login"):
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        enviado = st.form_submit_button("Entrar")

    if enviado:
        if _credenciales_correctas(usuario, contraseña):
            st.session_state['autenticado'] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.stop()
