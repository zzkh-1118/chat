import streamlit as st
import requests
import json
import os
import base64

# ==========================================
# [사용자 설정]
# ==========================================
ACCESS_PASSWORD = "1111"
HISTORY_FILE = "system_log_v2.dat" # 프로젝트 구조를 위해 파일명 변경

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

# --- 5. 히스토리 및 프로젝트 관리 ---
if "projects" not in st.session_state: st.session_state["projects"] = {"Default Project": []}
if "current_project" not in st.session_state: st.session_state["current_project"] = "Default Project"
if "auth" not in st.session_state: st.session_state["auth"] = False

def save_all_data():
    data = {
        "projects": st.session_state["projects"],
        "current_project": st.session_state["current_project"]
    }
    with open(HISTORY_FILE, "w") as f:
        f.write(encrypt_data(json.dumps(data), ACCESS_PASSWORD))

def load_all_data():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                dec = decrypt_data(f.read(), ACCESS_PASSWORD)
                if dec:
                    loaded = json.loads(dec)
                    st.session_state["projects"] = loaded.get("projects", {"Default Project": []})
                    st.session_state["current_project"] = loaded.get("current_project", "Default Project")
        except: pass

# --- 6. 사이드바 (프로젝트 기능 포함) ---
with st.sidebar:
    st.title("⚙️ System Control")
    if not st.session_state["auth"]:
        pwd = st.text_input("Access Code", type="password", key="login_pwd")
        if st.button("Login", key="login_btn"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["auth"] = True
                load_all_data(); st.rerun()
            else: st.error("Wrong Code")
        st.stop()

    # [추가] 프로젝트 관리 영역
    st.subheader("📁 Projects")
    new_proj_name = st.text_input("New Project Name", placeholder="Enter name...", key="new_proj_input")
    if st.button("➕ Create Project", use_container_width=True):
        if new_proj_name and new_proj_name not in st.session_state["projects"]:
            st.session_state["projects"][new_proj_name] = []
            st.session_state["current_project"] = new_proj_name
            save_all_data(); st.rerun()

    proj_list = list(st.session_state["projects"].keys())
    selected_proj = st.selectbox("Select Project", proj_list, index=proj_list.index(st.session_state["current_project"]))
    if selected_proj != st.session_state["current_project"]:
        st.session_state["current_project"] = selected_proj
        st.rerun()

    api_token = st.text_input("🔑 Gemini API Key", type="password", key="api_key_input")
    
    # 파라미터 설정 (기존 기능 유지)
    st.divider()
    sys_prompt = st.text_area("📜 System Instruction", value="You are a helpful AI assistant.", height=80)
    
    col1, col2 = st.columns(2)
    with col1:
        entropy = st.slider("✨ Entropy (Temp)", 0.0, 2.0, 0.7, 0.1)
        top_p = st.slider("🎯 Top-P", 0.0, 1.0, 0.95, 0.05)
    with col2:
        max_tokens = st.number_input("📏 Max Tokens", 100, 8192, 4096)
        top_k = st.number_input("🎲 Top-K", 1, 100, 40)

    with st.expander("🛡️ Safety Settings"):
        safety_level = st.select_slider("Filter Level", 
            options=["BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"], value="BLOCK_ONLY_HIGH")
        safety_settings = [{"category": c, "threshold": safety_level} for c in 
                           ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]

    st.divider()
    if st.button("🔄 Refresh Models", key="refresh_models_btn"): st.cache_data.clear(); st.success("Updated")
    
    MODEL_DATA = get_realtime_models(api_token)
    models_list = MODEL_DATA[list(MODEL_DATA.keys())[0]]
    selected_model = st.selectbox("🤖 Model Engine", list(models_list.keys()), format_func=lambda x: models_list[x], key="model_select")
    
    use_search = st.toggle("🌐 Google Search (Grounding)", value=True, key="search_toggle")
    
    if st.button("🗑️ Delete Current Project", key="del_proj_btn"):
        if len(st.session_state["projects"]) > 1:
            del st.session_state["projects"][st.session_state["current_project"]]
            st.session_state["current_project"] = list(st.session_state["projects"].keys())[0]
            save_all_data(); st.rerun()
        else: st.warning("At least one project must exist.")

# --- 7. 메인 채팅 UI ---
st.title(f"📊 {st.session_state['current_project']}")

current_msgs = st.session_state["projects"][st.session_state["current_project"]]

for i, m in enumerate(current_msgs):
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
    current_msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty(); ph.markdown("📡 Processing...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_token}"
        
        history_payload = [{"role": "user", "parts": [{"text": f"System Instruction: {sys_prompt}"}]},
                           {"role": "model", "parts": [{"text": "Understood."}]}]
        
        for msg in current_msgs[-10:]:
            history_payload.append({"role": "user" if msg["role"]=="user" else "model", "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": history_payload, "tools": [{"google_search": {}}] if use_search else [],
            "safetySettings": safety_settings,
            "generationConfig": {"temperature": entropy, "topP": top_p, "topK": top_k, "maxOutputTokens": max_tokens}
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
                current_msgs.append({"role": "assistant", "content": bot_text, "sources": sources})
                save_all_data()
                if sources: st.rerun()
            else: ph.error(f"Error {res.status_code}: {res.text}")
        except Exception as e: ph.error(str(e))
