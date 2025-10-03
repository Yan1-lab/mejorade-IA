# app.py
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

# utils
from utils.db import init_db, create_chat_session, get_sessions_by_user, get_session, delete_session, delete_all_sessions_for_user, save_file_record, get_files_for_session
from utils.auth import create_user, authenticate_user, get_user_by_token, rotate_user_token
from utils.parser import save_uploaded_file, UPLOADS
from utils.openai_api import call_openai_chat, get_openai_key

# cookie manager
from streamlit_cookies_manager import EncryptedCookieManager

# Setup
st.set_page_config(page_title="KB Asistente Médico - Yan el Panda 🐼", page_icon="💊", layout="wide")
APP_ROOT = Path.cwd()
UPLOADS.mkdir(exist_ok=True)

# inject css if available
if (APP_ROOT / "assets" / "style.css").exists():
    with open(APP_ROOT / "assets" / "style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# DATABASE init (use Streamlit secrets or env)
DATABASE_URL = None
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass
if not DATABASE_URL:
    DATABASE_URL = os.environ.get("DATABASE_URL", None)
# fallback to local sqlite
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{APP_ROOT / 'data.db'}"

# init DB
init_db(DATABASE_URL)

# COOKIE secret (must be set in Streamlit Secrets for production)
COOKIE_SECRET = None
try:
    if "COOKIE_SECRET" in st.secrets:
        COOKIE_SECRET = st.secrets["COOKIE_SECRET"]
except Exception:
    pass
if not COOKIE_SECRET:
    COOKIE_SECRET = os.environ.get("COOKIE_SECRET", None)

cookies = EncryptedCookieManager(prefix="kb_asst", password=COOKIE_SECRET)
cookies.load()

# Try restore user by cookie token
current_user = None
token_val = None
try:
    token_val = cookies.get("kb_token")
except Exception:
    token_val = None

if token_val:
    current_user = get_user_by_token(token_val)

# Session state user
if "user" not in st.session_state:
    if current_user:
        st.session_state["user"] = {"id": current_user.id, "username": current_user.username}
    else:
        st.session_state["user"] = None

# If not authenticated -> show auth UI
if not st.session_state["user"]:
    st.markdown("<div class='card'><h2>KB — Registro / Iniciar sesión</h2></div>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Iniciar sesión")
        login_id = st.text_input("Usuario o email", key="login_id")
        login_pass = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar"):
            user, err = authenticate_user(login_id.strip(), login_pass.strip())
            if err:
                st.error(err)
            else:
                st.session_state["user"] = {"id": user.id, "username": user.username}
                # set cookie with expiry 1 year
                try:
                    try:
                        cookies.set("kb_token", user.token, expires=(datetime.utcnow()+timedelta(days=365)))
                    except Exception:
                        cookies["kb_token"] = user.token
                    cookies.save()
                except Exception:
                    pass
                st.success(f"Bienvenido {user.username} 👋")
                st.experimental_rerun()
    with col_r:
        st.subheader("Registrarse")
        reg_user = st.text_input("Usuario", key="reg_user")
        reg_email = st.text_input("Email (recomendado)", key="reg_email")
        reg_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        reg_pass2 = st.text_input("Confirmar contraseña", type="password", key="reg_pass2")
        if st.button("Crear cuenta"):
            if not reg_user or not reg_pass:
                st.error("Usuario y contraseña requeridos")
            elif reg_pass != reg_pass2:
                st.error("Las contraseñas no coinciden")
            else:
                user, err = create_user(reg_user.strip(), reg_pass.strip(), reg_email.strip() or None)
                if err:
                    st.error(err)
                else:
                    # auto-login + cookie
                    st.session_state["user"] = {"id": user.id, "username": user.username}
                    try:
                        try:
                            cookies.set("kb_token", user.token, expires=(datetime.utcnow()+timedelta(days=365)))
                        except Exception:
                            cookies["kb_token"] = user.token
                        cookies.save()
                    except Exception:
                        pass
                    st.success("Registrado y logueado. ¡Bienvenido!")
                    st.experimental_rerun()
    st.stop()

# Authenticated
user_id = st.session_state["user"]["id"]
username = st.session_state["user"]["username"]

# Sidebar: user info, logout, history
with st.sidebar:
    st.markdown(f"### 👤 {username}")
    if st.button("Cerrar sesión"):
        # rotate token server-side so cookie invalid
        rotate_user_token(user_id)
        try:
            cookies.delete("kb_token")
        except Exception:
            try:
                cookies["kb_token"] = ""
                cookies.save()
            except Exception:
                pass
        st.session_state.clear()
        st.experimental_rerun()

    st.markdown("---")
    st.markdown("#### Historial")
    sessions = get_sessions_by_user(user_id)
    for s in sessions:
        cols = st.columns([6,1])
        with cols[0]:
            if st.button(s.title or f"Sesión {s.id} - {s.created_at.date()}", key=f"load_{s.id}"):
                st.session_state["loaded_session"] = s.id
                st.experimental_rerun()
        with cols[1]:
            if st.button("🗑", key=f"del_{s.id}"):
                # Confirm deletion modal (simple)
                if st.confirm(f"¿Eliminar la sesión {s.id}? Esta acción no se puede deshacer."):
                    delete_session(s.id)
                    st.experimental_rerun()
    st.markdown("---")
    st.markdown("#### Acciones")
    if st.button("🧹 Borrar TODO el historial (peligro)", key="del_all"):
        confirm = st.checkbox("✅ Sí, borrar TODO (irreversible)", key="confirm_del_all")
        if confirm:
            delete_all_sessions_for_user(user_id)
            # remove uploads folder for user
            user_dir = UPLOADS / str(user_id)
            try:
                if user_dir.exists():
                    import shutil
                    shutil.rmtree(user_dir)
            except Exception:
                pass
            st.success("Historial eliminado")
            st.experimental_rerun()

# Main area
st.markdown("<div class='card'><h2>KB — Yan el Panda 🐼 — Asistente Médico</h2></div>", unsafe_allow_html=True)
col_main, col_side = st.columns([3,1])

with col_main:
    st.subheader("Describe tus síntomas o pega texto")
    user_text = st.text_area("Escribe aquí...", height=140, key="user_text")
    st.markdown("**Adjunta archivos (opcional)**: PDF, imagen, docx, xlsx, pptx, txt, código.")
    uploaded = st.file_uploader("Sube archivos", accept_multiple_files=True, key="files")

    # create empty session to attach files; will update assistant_response later
    session_obj = create_chat_session(user_id, title=None, user_input=user_text or "", assistant_response=None)
    session_id = session_obj.id

    files_meta = []
    if uploaded:
        for uf in uploaded:
            meta = save_uploaded_file(uf, user_id, session_id)
            save_file_record(session_id, meta["filename"], meta["filepath"], meta["filetype"], meta["extracted_text"])
            files_meta.append(meta)
        st.success(f"{len(uploaded)} archivo(s) subido(s) y procesado(s).")

    if st.button("🔍 Analizar con IA"):
        prompt = f"Usuario: {username}\nDescripción: {user_text}\n\nArchivos:\n"
        for f in files_meta:
            preview = (f["extracted_text"][:1200] + "...") if f["extracted_text"] else "[sin texto extraído]"
            prompt += f"- {f['filename']}: {preview}\n"
        prompt += "\nPor favor entrega un análisis preliminar: posibles causas, pruebas recomendadas, señales de alarma y recomendaciones iniciales. Indica claramente que no reemplaza a un profesional médico."

        if not get_openai_key():
            st.error("OpenAI API key no configurada. Añádela en Streamlit Secrets.")
        else:
            with st.spinner("Analizando con IA..."):
                answer = call_openai_chat(prompt)
            # update session
            # (update existing session object in DB)
            # we use simple DB access via helper above
            # update assistant_response and title
            try:
                from utils.db import get_db, ChatSession
                db = get_db()
                s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if s:
                    s.assistant_response = answer
                    s.title = (user_text[:80] + "...") if user_text else f"Sesión {s.id}"
                    db.add(s)
                    db.commit()
                db.close()
            except Exception:
                pass
            st.markdown("### Resultado IA")
            st.write(answer)

with col_side:
    st.subheader("Sesión cargada")
    loaded_id = st.session_state.get("loaded_session", None)
    if loaded_id:
        s = get_session(user_id, int(loaded_id))
        if s:
            st.markdown(f"**Título:** {s.title or ''}")
            st.markdown(f"**Fecha:** {s.created_at}")
            st.markdown("**Entrada:**")
            st.info(s.user_input or "(sin texto)")
            st.markdown("**Respuesta IA:**")
            st.write(s.assistant_response or "(sin respuesta)")
            st.markdown("**Archivos asociados:**")
            files = get_files_for_session(s.id)
            for f in files:
                st.write(f"- {f.filename} ({f.filetype})")
                if f.extracted_text:
                    st.markdown(f"```{f.extracted_text[:800]}```")
    else:
        st.info("Carga una sesión desde el historial en la barra lateral.")

# Footer
st.markdown("---")
st.markdown("<div class='small-muted'>KB Asistente Médico — Yan el Panda 🐼 — Información orientativa, no sustituye a profesional médico.</div>", unsafe_allow_html=True)
