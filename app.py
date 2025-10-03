import streamlit as st
import openai
import os
import datetime
import bcrypt
from PIL import Image
from pypdf import PdfReader
from docx import Document
from streamlit_lottie import st_lottie
from streamlit_cookies_manager import EncryptedCookieManager
import requests

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Asistente Médico KB", page_icon="💊", layout="wide")

openai.api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
if not openai.api_key:
    st.error("⚠️ Configura tu OpenAI API Key en secrets.")
    st.stop()

# ---------------- COOKIES ----------------
cookies = EncryptedCookieManager(
    prefix="asistente_medico",
    password=st.secrets.get("COOKIE_SECRET", "clave_super_secreta_aleatoria_y_larga")
)
if not cookies.ready():
    st.stop()

def save_cookie(user_email: str):
    cookies["user"] = user_email
    cookies["expiry"] = str(datetime.datetime.now() + datetime.timedelta(days=365))
    cookies.save()

def clear_cookie():
    cookies["user"] = ""
    cookies.save()

def get_logged_user():
    return cookies.get("user")

# ---------------- LOTTIE ----------------
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# ---------------- USUARIOS ----------------
if "users" not in st.session_state:
    st.session_state.users = {}  # email: hashed_password

def register_user(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    st.session_state.users[email] = hashed
    save_cookie(email)

def login_user(email, password):
    hashed = st.session_state.users.get(email)
    if hashed and bcrypt.checkpw(password.encode(), hashed):
        save_cookie(email)
        return True
    return False

# ---------------- APP ----------------
def main():
    st.title("💊 Asistente Médico KB")
    
    user_email = get_logged_user()

    if not user_email:
        st.subheader("🔑 Registro / Login")
        mode = st.radio("Elige acción:", ["Login", "Registro"])
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")

        if st.button("Continuar"):
            if mode == "Registro":
                if email in st.session_state.users:
                    st.warning("⚠️ Usuario ya registrado.")
                else:
                    register_user(email, password)
                    st.success("✅ Registro exitoso. Ya puedes usar el asistente.")
                    st.experimental_rerun()
            else:  # Login
                if login_user(email, password):
                    st.success("✅ Login exitoso.")
                    st.experimental_rerun()
                else:
                    st.error("❌ Email o contraseña incorrectos.")
        return

    # ---------------- SIDEBAR ----------------
    st.sidebar.text(f"👋 {user_email}")
    if st.sidebar.button("🚪 Cerrar sesión / Cambiar usuario"):
        clear_cookie()
        st.experimental_rerun()

    # ---------------- CHAT ----------------
    st.subheader("🤖 Chat Médico")
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 Hola, soy tu asistente médico KB. ¿Qué síntomas tienes hoy?"}
        ]

    # Mostrar historial
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["content"])
        else:
            st.chat_message("assistant").markdown(msg["content"])

    # Input de chat
    if prompt := st.chat_input("Describe tus síntomas..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            # Animación Lottie
            lottie_url = "https://assets10.lottiefiles.com/packages/lf20_usmfx6bp.json"
            lottie_animation = load_lottieurl(lottie_url)
            if lottie_animation:
                st_lottie(lottie_animation, speed=1, width=150, height=150, key="loading")

            with st.spinner("💭 Analizando con IA..."):
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content":
                             "Eres un asistente médico. Da posibles causas de síntomas, pero aclara que no reemplazas a un médico real."},
                            *st.session_state.messages
                        ],
                        max_tokens=400,
                        temperature=0.5
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"⚠️ Error al conectar con OpenAI: {e}"

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

    # ---------------- SUBIDA DE ARCHIVOS ----------------
    st.subheader("📂 Subir Archivos Médicos")
    uploaded = st.file_uploader("Sube un archivo (PDF, Word, Imagen)", type=["pdf", "docx", "png", "jpg", "jpeg"])

    if uploaded:
        text = ""
        if uploaded.type == "application/pdf":
            pdf = PdfReader(uploaded)
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        elif uploaded.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = Document(uploaded)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif "image" in uploaded.type:
            image = Image.open(uploaded)
            st.image(image, caption="Imagen subida")
            text = "[Imagen cargada - análisis futuro con OCR]"

        if text:
            st.text_area("Contenido extraído", text, height=200)

# ---------------- EJECUCIÓN ----------------
if __name__ == "__main__":
    main()
