import streamlit as st
import requests
import json
import os
import base64

# ==========================================
# [사용자 설정]
# ==========================================
ACCESS_PASSWORD = "1111"
HISTORY_FILE = "system_log_v2.dat"

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Gemini Intelligence Center", page_icon="🤖", layout="wide")

# --- 2. 암호화 함수 ---
def encrypt_data(data_str, key):
    enc = [chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data_str)]
    return base64.b64encode("".join(enc).encode()).decode()

def decrypt_data(enc_str, key):
    try:
        dec_bytes = base64.b64decode(enc_str).decode()
        dec = [chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(dec_bytes)]
        return "".join(dec)
    except: return ""

# --- 3. 실시간 모델 목록 가져오기 ---
@st.cache_data(ttl=600)
def get_realtime_models(api_key):
    if not api_key: return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash (Enter API Key)"}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            models = res.json().get("models", [])
            dynamic_options = {m["name"].replace("models/", ""): m["name"].replace("models/", "").replace("-", " ").title() 
                               for m in models if "generateContent" in m.get("supportedGenerationMethods", [])}
            return {"Available Models": dynamic_options} if dynamic_options else {"Default": {"gemini-1.5-flash": "No Models Found"}}
        return {"Error": {"gemini-1.5-flash": f"API Error {res.status_code}"}}
    except: return {"Error": {"gemini-1.5-flash": "Connection Error"}}

# --- 4. 복사 스크립트 (안정화 버전) ---
st.markdown("""
<script>
    function copyText(base64Str, btnId, type) {
        try {
            const text = decodeURIComponent(escape(atob(base64Str)));
            const final = type === 'md' ? text : text.replace(/[#*`]/g, '');
            navigator.clipboard.writeText(final).then(() => {
                const btn = document.getElementById(btnId);
                btn.innerText = "✅ Done";
                setTimeout(() => { btn.innerText = (type === 'md' ? "📋 MD" : "📝 TXT"); }, 2000);
            });
        } catch(e) { console.error("Copy failed", e); }
    }
</script>
<style>
    .custom-copy-btn { padding: 4px 8px; font-size: 11px; cursor: pointer; border-radius: 4px; border: 1px solid #444; background: #1e1e1e; color: #ccc; margin-right: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 5. 히스토리 관리 ---
if "projects" not in st.session_state: st.session_state["projects"] = {"Default Project": []}
if "current_project" not in st.session_state: st.session_state["current_project"] = "Default Project"
if "auth" not in st.session_state: st.session_state["auth"] = False

def save_local_data():
    data_str = json.dumps({"projects": st.session_state["projects"], "current_project": st.session_state["current_project"]})
    with open(HISTORY_FILE, "w") as f:
        f.write(encrypt_data(data_str, ACCESS_PASSWORD))

def load_local_data():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                dec = decrypt_data(f.read(), ACCESS_PASSWORD)
                if dec:
                    loaded = json.loads(dec)
                    st.session_state["projects"] = loaded.get("projects", {"Default Project": []})
                    st.session_state["current_project"] = loaded.get("current_project", "Default Project")
        except: pass

# --- 6. 사이드바 UI ---
with st.sidebar:
    st.title("⚙️ System Control")
    if not st.session_state["auth"]:
        pwd = st.text_input("Access Code", type="password", key="login_pwd")
        if st.button("Login
