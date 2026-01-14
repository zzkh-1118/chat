import streamlit as st
import requests
import json
import uuid
import os
import base64
import re

# ==========================================
# [사용자 설정] 
# ==========================================
ACCESS_PASSWORD = "1111" 
HISTORY_FILE = "system_log.dat"

# --- 1. 페이지 설정 ---
st.set_page_config(
    page_title="Gemini Intelligence Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded" 
)

# --- 2. 암호화/복호화 ---
def encrypt_data(data_str, key):
    enc = []
    for i, c in enumerate(data_str):
        key_c = key[i % len(key)]
        enc_c = chr(ord(c) ^ ord(key_c))
        enc.append(enc_c)
    return base64.b64encode("".join(enc).encode()).decode()

def decrypt_data(enc_str, key):
    try:
        dec = []
        enc_str = base64.b64decode(enc_str).decode()
        for i, c in enumerate(enc_str):
            key_c = key[i % len(key)]
            dec_c = chr(ord(c) ^ ord(key_c))
            dec.append(dec_c)
        return "".join(dec)
    except: return ""

# --- 3. 실시간 모델 목록 가져오기 ---
@st.cache_data(ttl=600)
def get_realtime_models(api_key):
    if not api_key:
        return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash"}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            models_data = res.json()
            dynamic_options = {}
            for m in models_data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    model_id = m["name"].replace("models/", "")
                    display_name = model_id.replace("-", " ").title()
                    dynamic_options[model_id] = display_name
            return {"Real-time Gemini Models": dynamic_options}
        else: return {"Error": {"gemini-1.5-flash": f"Err {res.status_code}"}}
    except: return {"Error": {"gemini-1.5-flash": "Connection Error"}}

# --- 4. 클립보드 복사 스크립트 ---
st.markdown("""
<script>
    function copyBase64(base64Str, btnId, type) {
        const decoded = decodeURIComponent(escape(atob(base64Str)));
        const textToCopy = type === 'md' ? decoded : decoded.replace(/[#*`]/g, '');
        navigator.clipboard.writeText(textToCopy).then(() => {
            const btn = document.getElementById(btnId);
            btn.innerText = "✅ Done";
            setTimeout(() => { btn.innerText = (type === 'md' ? "📋 MD" : "📝 TXT"); }, 2000);
        });
    }
</script>
<style>
    .custom-copy-btn { padding: 4px 8px; font-size: 11px; cursor: pointer; border-radius: 4px; border: 1px solid #444; background: #1e1e1e; color: #ccc; }
    .copy-btn-wrapper { display: flex; gap: 5px; margin-bottom: 8px; }
    .source-box { font-size: 0.85rem; color: #888; margin-top: 10px; padding: 10px; border-radius: 8px; background: #111; border-left: 3px solid #4a90e2; }
</style>
""", unsafe_allow_html=True)

# --- 5. 세션 관리 및 히스토리 ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "messages" not in st.session_state: st.session_state["messages"] = []

def save_history():
    data = json.dumps(st.session_state["messages"])
    with open(HISTORY_FILE, "w") as f:
        f.write(encrypt_data(data, ACCESS_PASSWORD))

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                dec = decrypt_data(f.read(), ACCESS_PASSWORD)
                if dec: st.session_state["messages"] = json.loads(dec)
        except: st.session_state["messages"] = []

# --- 6. 사이드바 UI ---
with st.sidebar:
    st.title("⚙️ System Setup")
    if not st.session_state["authenticated"]:
        pwd = st.text_input("Access Code", type="password")
        if st.button("Login"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                load_history()
                st.rerun()
            else: st.error("Wrong Code")
        st.stop()

    api_token = st.text_input("🔑 API Token", type="password")
    
    if st.button("🔄 Refresh Models"):
        st.cache_data.clear()
        st.success("Updated")
    
    MODEL_DATA = get_realtime_models(api_token)
    selected_model_id = st.selectbox("🤖 Engine", list(MODEL_DATA[list(MODEL_DATA.keys())[0]].keys()))
    
    # 웹 검색 기능 복구
    use_web_search = st.toggle("🌐 Google Search Grounding", value=True)
    
    st.divider()
    if st.button("🗑️ Clear History"):
        st.session_state["messages"] = []
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.rerun()

# --- 7. 메인 채팅 UI ---
st.title("📊 AI Intelligence Center")

# 히스토리 출력 (KeyError 방지 로직 포함)
for i, m in enumerate(st.session_state["messages"]):
    role = m.get("role", "assistant")
    with st.chat_message(role):
        if role == "assistant":
            content = m.get("content", "")
            b64_val = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            st.markdown(f"""<div class="copy-btn-wrapper">
                <button id="copy_{i}_md" class="custom-copy-btn" onclick="copyBase64('{b64_val}', 'copy_{i}_md', 'md')\">📋 MD</button>
                <button id="copy_{i}_txt" class="custom-copy-btn" onclick="copyBase64('{b64_val}', 'copy_{i}_txt', 'txt')\">📝 TXT</button>
            </div>""", unsafe_allow_html=True)
            st.markdown(content)
            if m.get("sources"):
                with st.expander("📚 참조 출처 확인"):
                    for s in m["sources"]:
                        st.write(f"• [{s.get('title')}]({s.get('uri')})")
        else:
            st.markdown(m.get("content", ""))
import streamlit as st
import requests
import json
import os
import base64

# ==========================================
# [사용자 설정] 
# ==========================================
ACCESS_PASSWORD = "1111" 
HISTORY_FILE = "system_log.dat"

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Gemini Intelligence", page_icon="🤖", layout="wide")

# --- 2. 암호화 함수 (파일 저장용) ---
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
    if not api_key: return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash"}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            models = res.json().get("models", [])
            dynamic_options = {m["name"].replace("models/", ""): m["name"].replace("models/", "").replace("-", " ").title() 
                               for m in models if "generateContent" in m.get("supportedGenerationMethods", [])}
            return {"Available Models": dynamic_options}
        else: return {"Error": {"gemini-1.5-flash": f"API Error {res.status_code}"}}
    except: return {"Error": {"gemini-1.5-flash": "Connection Error"}}

# --- 4. 복사 스크립트 ---
st.markdown("""
<script>
    function copyText(base64Str, btnId, type) {
        const text = decodeURIComponent(escape(atob(base64Str)));
        const final = type === 'md' ? text : text.replace(/[#*`]/g, '');
        navigator.clipboard.writeText(final).then(() => {
            const btn = document.getElementById(btnId);
            btn.innerText = "✅ Done";
            setTimeout(() => { btn.innerText = (type === 'md' ? "📋 MD" : "📝 TXT"); }, 2000);
        });
    }
</script>
<style>
    .custom-copy-btn { padding: 4px 8px; font-size: 11px; cursor: pointer; border-radius: 4px; border: 1px solid #444; background: #1e1e1e; color: #ccc; margin-right: 5px; }
    .source-box { font-size: 0.85rem; color: #888; margin-top: 10px; padding: 10px; border-radius: 8px; background: #111; border-left: 3px solid #4a90e2; }
</style>
""", unsafe_allow_html=True)

# --- 5. 히스토리 관리 ---
if "messages" not in st.session_state: st.session_state["messages"] = []
if "auth" not in st.session_state: st.session_state["auth"] = False

def save_history():
    with open(HISTORY_FILE, "w") as f:
        f.write(encrypt_data(json.dumps(st.session_state["messages"]), ACCESS_PASSWORD))

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = decrypt_data(f.read(), ACCESS_PASSWORD)
                if data: st.session_state["messages"] = json.loads(data)
        except: pass

# --- 6. 사이드바 ---
with st.sidebar:
    st.title("⚙️ Setup")
    if not st.session_state["auth"]:
        pwd = st.text_input("Access Code", type="password")
        if st.button("Login"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["auth"] = True
                load_history(); st.rerun()
            else: st.error("Wrong Code")
        st.stop()

    api_token = st.text_input("🔑 Gemini API Key", type="password")
    if st.button("🔄 Refresh Models"): st.cache_data.clear(); st.success("Updated")
    
    MODEL_DATA = get_realtime_models(api_token)
    models_list = MODEL_DATA[list(MODEL_DATA.keys())[0]]
    selected_model = st.selectbox("🤖 Model Engine", list(models_list.keys()), format_func=lambda x: models_list[x])
    
    # [수정 포인트] 최신 검색 도구 토글
    use_search = st.toggle("🌐 Google Search (Grounding)", value=True)
    
    if st.button("🗑️ Clear History"):
        st.session_state["messages"] = []; 
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.rerun()

# --- 7. 메인 채팅 ---
st.title("📊 AI Intelligence Center")

for i, m in enumerate(st.session_state["messages"]):
    with st.chat_message(m["role"]):
        if m["role"] == "assistant":
            b64 = base64.b64encode(m["content"].encode('utf-8')).decode('utf-8')
            st.markdown(f'<button id="md_{i}" class="custom-copy-btn" onclick="copyText(\'{b64}\', \'md_{i}\', \'md\')">📋 MD</button>'
                        f'<button id="txt_{i}" class="custom-copy-btn" onclick="copyText(\'{b64}\', \'txt_{i}\', \'txt\')">📝 TXT</button>', unsafe_allow_html=True)
            st.markdown(m["content"])
            if m.get("sources"):
                with st.expander("📚 Sources"):
                    for s in m["sources"]: st.write(f"- [{s['title']}]({s['uri']})")
        else: st.markdown(m["content"])

if prompt := st.chat_input("Ask anything..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty(); ph.markdown("📡 Processing...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_token}"
        
        # [수정 포인트] google_search_retrieval -> google_search 로 변경
        payload = {
            "contents": [{"role": "user" if msg["role"]=="user" else "model", "parts": [{"text": msg["content"]}]} for msg in st.session_state["messages"][-10:]],
            "tools": [{"google_search": {}}] if use_search else [],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
        }

        try:
            res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)
            if res.status_code == 200:
                data = res.json()
                bot_text = data['candidates'][0]['content']['parts'][0]['text']
                
                # 출처(Grounding) 처리
                sources = []
                try:
                    metadata = data['candidates'][0].get('groundingMetadata', {})
                    for chunk in metadata.get('groundingChunks', []):
                        if 'web' in chunk: sources.append({'title': chunk['web'].get('title'), 'uri': chunk['web'].get('uri')})
                except: pass

                ph.markdown(bot_text)
                st.session_state["messages"].append({"role": "assistant", "content": bot_text, "sources": sources})
                save_history()
                if sources: st.rerun()
            else: ph.error(f"Error {res.status_code}: {res.text}")
        except Exception as e: ph.error(str(e))
