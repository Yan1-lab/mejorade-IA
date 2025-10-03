import streamlit as st
import openai
import os
import sqlite3
import hashlib
import datetime
import requests
from PIL import Image
from pypdf import PdfReader
from docx import Document
from streamlit_lottie import st_lottie
from streamlit_cookies_manager import EncryptedCookieManager
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Asistente Médico KB", page_icon="💊", layout="wide")
openai.api_key = os.getenv("OPENAI_API_KEY") or st.secrets["OPENAI_API_KEY"]
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

def save_cookie(user_info: dict):
    cookies["user"] = user_info
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

# ---------------- GOOGLE OAUTH ----------------
def google_login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [st.secrets.get("REDIRECT_URI", "https://TU_APP.streamlit.app")],
            }
        },
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]
    )

    flow.redirect_uri = st.secrets.get("REDIRECT_URI", "https://TU_APP.streamlit.app")
    
    if "code" not in st.experimental_get_query_params():
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
        st.markdown(f"[Login con Google]({auth_url})")
        st.stop()
    else:
        code = st.experimental_get_query_params()["code"][0]
        flow.fetch_token(code=code)
        credentials = flow.credentials
        idinfo = id_token.verify_oauth2_token(credentials.id_token, google_requests.Request(), st.secrets["GOOGLE_CLIENT_ID"])
        return {"email": idinfo["email"], "name": idinfo.get("name"), "photo": idinfo.get("picture")}

# ---------------- APP ----------------
def main():
    st.title("💊 Asistente Médico KB")
    st.caption("Tu asistente médico virtual con foto de perfil y login Google OAuth.")

    user = get_logged_user()

    if not user:
        # Login Google
        user_info = google_login()
        if user_info:
            save_cookie(user_info)
            st.experimental_rerun()
    else:
        # Mostrar perfil en sidebar
        st.sidebar.image(user.get("photo"), width=50)
        st.sidebar.text(f"👋 {user.get('name', user.get('email'))}")
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
