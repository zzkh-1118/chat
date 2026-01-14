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
    if not api_key: return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash"}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=15)
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

# --- 6. 사이드바 (모든 세부 기능 복원) ---
with st.sidebar:
    st.title("⚙️ System Control")
    if not st.session_state["auth"]:
        pwd = st.text_input("Access Code", type="password", key="login_pwd")
        if st.button("Login", key="login_btn"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["auth"] = True
                load_history(); st.rerun()
            else: st.error("Wrong Code")
        st.stop()

    api_token = st.text_input("🔑 Gemini API Key", type="password", key="api_key_input")
    
    # [복원 1] 기본 파라미터 설정
    st.divider()
    sys_prompt = st.text_area("📜 System Instruction", value="You are a helpful AI assistant.", height=80)
    
    col1, col2 = st.columns(2)
    with col1:
        entropy = st.slider("✨ Entropy (Temp)", 0.0, 2.0, 0.7, 0.1)
        top_p = st.slider("🎯 Top-P", 0.0, 1.0, 0.95, 0.05)
    with col2:
        max_tokens = st.number_input("📏 Max Tokens", 100, 8192, 4096)
        top_k = st.number_input("🎲 Top-K", 1, 100, 40)

    # [복원 2] 안전 설정 (Safety Settings)
    with st.expander("🛡️ Safety Settings"):
        safety_level = st.select_slider(
            "Filter Level",
            options=["BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"],
            value="BLOCK_ONLY_HIGH"
        )
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
        ]

    # 모델 설정
    st.divider()
    if st.button("🔄 Refresh Models", key="refresh_models_btn"): st.cache_data.clear(); st.success("Updated")
    
    MODEL_DATA = get_realtime_models(api_token)
    models_list = MODEL_DATA[list(MODEL_DATA.keys())[0]]
    selected_model = st.selectbox("🤖 Model Engine", list(models_list.keys()), format_func=lambda x: models_list[x], key="model_select")
    
    use_search = st.toggle("🌐 Google Search (Grounding)", value=True, key="search_toggle")
    
    if st.button("🗑️ Clear History", key="clear_history_btn"):
        st.session_state["messages"] = []; 
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.rerun()

# --- 7. 메인 채팅 UI ---
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
        
        # 시스템 프롬프트 구성
        history_payload = [{"role": "user", "parts": [{"text": f"System Instruction: {sys_prompt}"}]},
                           {"role": "model", "parts": [{"text": "Understood. I will act according to these instructions."}]}]
        
        for msg in st.session_state["messages"][-10:]:
            history_payload.append({"role": "user" if msg["role"]=="user" else "model", "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": history_payload,
            "tools": [{"google_search": {}}] if use_search else [],
            "safetySettings": safety_settings,
            "generationConfig": {
                "temperature": entropy, 
                "topP": top_p,
                "topK": top_k,
                "maxOutputTokens": max_tokens
            }
        }

        try:
            res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)
            if res.status_code == 200:
                data = res.json()
                bot_text = data['candidates'][0]['content']['parts'][0]['text']
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
