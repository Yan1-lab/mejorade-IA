import streamlit as st
import openai
import os
import time
from streamlit_cookies_manager import EncryptedCookieManager
from utils import db, auth

# ==============================
# CONFIGURACIÓN DE LA APP
# ==============================
st.set_page_config(
    page_title="Asistente Médico KB",
    page_icon="💊",
    layout="wide"
)

# Estilos
with open("assets/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ==============================
# CONFIGURACIÓN DE COOKIES
# ==============================
cookies = EncryptedCookieManager(
    prefix="med_assistant",
    password=os.getenv("COOKIE_SECRET", "clave-secreta-demo")
)

if not cookies.ready():
    st.stop()

# ==============================
# OPENAI API
# ==============================
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.warning("⚠️ Configura tu OPENAI_API_KEY en secrets.")
    st.stop()

# ==============================
# LOGIN / REGISTRO
# ==============================
user = auth.check_cookie(cookies)

if not user:
    st.title("👤 Bienvenido a KB")
    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])

    with tab1:
        email = st.text_input("Correo", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_password")
        if st.button("Iniciar Sesión"):
            success, user = auth.login_user(email, password)
            if success:
                cookies["user"] = str(user["id"])
                cookies.save()
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")

    with tab2:
        name = st.text_input("Nombre completo", key="register_name")
        email = st.text_input("Correo", key="register_email")
        password = st.text_input("Contraseña", type="password", key="register_password")
        if st.button("Registrarse"):
            success, msg = auth.register_user(name, email, password)
            if success:
                st.success("✅ Registro exitoso, ahora inicia sesión")
            else:
                st.error(f"❌ {msg}")

    st.stop()

# ==============================
# APP PRINCIPAL (CHAT + ARCHIVOS)
# ==============================
st.sidebar.success(f"✅ Sesión iniciada: {user['name']}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    cookies["user"] = ""
    cookies.save()
    st.rerun()

st.title("💊 Asistente Médico Inteligente KB")
st.write("👋 Hola, soy tu asistente virtual Yan el Panda 🐼. ¿En qué te puedo ayudar hoy?")

# ==============================
# HISTORIAL DE CHAT
# ==============================
messages = db.get_messages(user["id"])

for msg in messages:
    role = msg["role"]
    content = msg["content"]
    if role == "user":
        st.chat_message("user").markdown(content)
    else:
        st.chat_message("assistant").markdown(content)

# ==============================
# SUBIDA DE ARCHIVOS
# ==============================
st.sidebar.header("📂 Archivos")
uploaded_file = st.sidebar.file_uploader(
    "Sube un archivo (PDF, Word, Excel, PPT, Imagen)",
    type=["pdf", "docx", "xlsx", "pptx", "png", "jpg", "jpeg"]
)

if uploaded_file:
    db.save_file(user["id"], uploaded_file)
    st.sidebar.success(f"✅ Archivo {uploaded_file.name} guardado")

files = db.get_files(user["id"])
if files:
    st.sidebar.write("Tus archivos subidos:")
    for f in files:
        st.sidebar.write(f"- {f['filename']}")

# ==============================
# INPUT DEL CHAT
# ==============================
if prompt := st.chat_input("Describe tus síntomas..."):
    db.save_message(user["id"], "user", prompt)
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("💭 Analizando..."):
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": 
                         "Eres un asistente médico virtual. Analiza síntomas y da posibles causas. Siempre aclara que no reemplazas a un médico real."},
                        *[{"role": m["role"], "content": m["content"]} for m in db.get_messages(user["id"])]
                    ],
                    max_tokens=400,
                    temperature=0.5
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = f"⚠️ Error al conectar con OpenAI: {e}"

        st.markdown(reply)
        db.save_message(user["id"], "assistant", reply)

# ==============================
# OPCIONES DE BORRADO DE CHAT
# ==============================
st.sidebar.header("🗑️ Historial")
if st.sidebar.button("❌ Borrar TODO el historial", type="primary"):
    st.sidebar.warning("⚠️ Esto eliminará TODOS tus chats")
    if st.sidebar.button("Confirmar borrado", type="secondary"):
        db.delete_all_messages(user["id"])
        st.sidebar.success("✅ Historial eliminado")
        st.rerun()
