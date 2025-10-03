import streamlit as st
import openai
import os
import sqlite3
import hashlib
import datetime
from streamlit_cookies_manager import EncryptedCookieManager
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Asistente Médico KB", page_icon="💊", layout="wide")

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("⚠️ Configura tu OpenAI API Key en las variables de entorno.")
    st.stop()

# ---------------- BASE DE DATOS ----------------
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password TEXT
                )''')
    conn.commit()
    conn.close()

def register_user(email, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(email, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hashed))
    user = c.fetchone()
    conn.close()
    return user

# ---------------- COOKIES ----------------
cookies = EncryptedCookieManager(
    prefix="asistente_medico",
    password="clave_super_secreta_123"
)
if not cookies.ready():
    st.stop()

def save_cookie(email):
    cookies["user"] = email
    cookies.set("expiry", str(datetime.datetime.now() + datetime.timedelta(days=365)))
    cookies.save()

def clear_cookie():
    cookies["user"] = ""
    cookies.save()

def get_logged_user():
    return cookies.get("user")

# ---------------- INTERFAZ ----------------
def main():
    st.title("💊 Asistente Médico KB")
    st.caption("Tu asistente médico virtual, seguro y confiable.")

    user = get_logged_user()

    if not user:  
        st.subheader("🔑 Inicia sesión o regístrate")
        option = st.radio("Elige una opción", ["Login", "Registro"])

        email = st.text_input("📧 Correo electrónico")
        password = st.text_input("🔒 Contraseña", type="password")

        if option == "Registro":
            if st.button("Registrarse"):
                if register_user(email, password):
                    st.success("✅ Registro exitoso. Ya puedes usar el asistente.")
                    save_cookie(email)
                    st.experimental_rerun()
                else:
                    st.error("⚠️ El correo ya está registrado.")

        elif option == "Login":
            if st.button("Iniciar sesión"):
                if login_user(email, password):
                    st.success("✅ Bienvenido de nuevo")
                    save_cookie(email)
                    st.experimental_rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")
    else:
        st.sidebar.success(f"👋 Bienvenido, {user}")
        if st.sidebar.button("🚪 Cerrar sesión"):
            clear_cookie()
            st.experimental_rerun()

        # ---------------- CHAT ----------------
        st.subheader("🤖 Chat Médico")
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "👋 Hola, soy tu asistente médico KB. ¿Qué síntomas tienes hoy?"}
            ]

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.chat_message("user").markdown(msg["content"])
            else:
                st.chat_message("assistant").markdown(msg["content"])

        if prompt := st.chat_input("Describe tus síntomas..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("💭 Analizando..."):
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
    init_db()
    main()
