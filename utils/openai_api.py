# utils/openai_api.py
import os
import openai

def get_openai_key():
    try:
        import streamlit as st
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", None)

def call_openai_chat(prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.3, max_tokens: int = 600):
    key = get_openai_key()
    if not key:
        return "⚠️ OpenAI API key no configurada."
    openai.api_key = key
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role":"system","content":"Eres un asistente médico responsable y prudente. Provee posibles causas, pruebas recomendadas y señales de alarma. Mantén tono claro y prudente."},
                      {"role":"user","content":prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error OpenAI: {e}"
