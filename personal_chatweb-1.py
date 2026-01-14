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
    page_title="Gemini Real-time Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded" 
)

# --- 2. 암호화/복호화 (파일 저장용) ---
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
    except:
        return ""

# --- 3. 실시간 모델 목록 가져오기 함수 ---
@st.cache_data(ttl=600) # 10분간 결과 캐싱
def get_realtime_models(api_key):
    if not api_key:
        return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash (Enter API Key)"}}
    
    # Google AI Studio 모델 리스트 엔드포인트
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            models_data = res.json()
            dynamic_options = {}
            for m in models_data.get("models", []):
                # 콘텐츠 생성이 가능한 모델만 필터링
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    model_id = m["name"].replace("models/", "")
                    # 가독성을 위해 이름 정리 (예: gemini-2.0-flash-exp -> Gemini 2.0 Flash Exp)
                    display_name = model_id.replace("-", " ").title()
                    dynamic_options[model_id] = display_name
            
            if not dynamic_options:
                return {"Error": {"gemini-1.5-flash": "No available models found"}}
            return {"Real-time Gemini Models": dynamic_options}
        else:
            return {"Error": {"gemini-1.5-flash": f"Err {res.status_code}: Check API Key"}}
    except Exception as e:
        return {"Error": {"gemini-1.5-flash": f"Connection Error: {str(e)}"}}

# --- 4. 핵심: 클립보드 복사 스크립트 ---
st.markdown("""
<script>
    function copyBase64(base64Str, btnId, type) {
        const decoded = atob(base64Str);
        const textToCopy = type === 'md' ? decoded : decoded.replace(/[#*`]/g, '');
        navigator.clipboard.writeText(textToCopy).then(() => {
            const btn = document.getElementById(btnId);
            const originalText = btn.innerText;
            btn.innerText = "✅ Done";
            btn.style.backgroundColor = "#22c55e";
            setTimeout(() => {
                btn.innerText = originalText;
                btn.style.backgroundColor = "";
            }, 2000);
        });
    }
</script>
<style>
    .custom-copy-btn {
        padding: 4px 8px; font-size: 11px; cursor: pointer; border-radius: 4px;
        border: 1px solid #444; background: #1e1e1e; color: #ccc; transition: 0.3s;
    }
    .custom-copy-btn:hover { background: #333; color: white; }
    .copy-btn-wrapper { display: flex; gap: 5px; margin-bottom: 8px; }
    .source-box { font-size: 0.85rem; color: #888; margin-top: 10px; padding: 10px; border-radius: 8px; background: #111; }
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
        with open(HISTORY_FILE, "r") as f:
            dec = decrypt_data(f.read(), ACCESS_PASSWORD)
            if dec: st.session_state["messages"] = json.loads(dec)

# --- 6. 사이드바 UI ---
with st.sidebar:
    st.title("⚙️ System Setup")
    
    # 6-1. 인증
    if not st.session_state["authenticated"]:
        pwd = st.text_input("Access Code", type="password")
        if st.button("Login"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                load_history()
                st.rerun()
            else: st.error("Wrong Code")
        st.stop()

    # 6-2. API & 모델 설정
    api_token = st.text_input("🔑 API Token", type="password", help="Enter Google AI Studio Key")
    
    col1, col2 = st.columns([2,1])
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear() # 캐시 강제 삭제
            st.success("Updated")
    
    # 실시간 모델 목록 가져오기
    MODEL_DATA = get_realtime_models(api_token)
    groups = list(MODEL_DATA.keys())
    selected_group = st.selectbox("📁 Series", groups)
    
    engines = MODEL_DATA[selected_group]
    selected_model_id = st.selectbox("🤖 Engine", list(engines.keys()), format_func=lambda x: engines[x])

    st.divider()
    chat_height = st.slider("Chat Window Height", 300, 1200, 600)
    if st.button("🗑️ Clear History"):
        st.session_state["messages"] = []
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.rerun()

# --- 7. 메인 채팅 UI ---
st.title("📊 AI Intelligence Center")

# 채팅창 출력
chat_container = st.container()
with chat_container:
    for i, m in enumerate(st.session_state["messages"]):
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                # 복사 버튼 생성
                b64_val = base64.b64encode(m["content"].encode()).decode()
                btn_id = f"copy_{i}"
                st.markdown(f"""
                <div class="copy-btn-wrapper">
                    <button id="{btn_id}_md" class="custom-copy-btn" onclick="copyBase64('{b64_val}', '{btn_id}_md', 'md')\">📋 MD</button>
                    <button id="{btn_id}_txt" class="custom-copy-btn" onclick="copyBase64('{b64_val}', '{btn_id}_txt', 'txt')\">📝 TXT</button>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(m["content"])

# 메시지 입력
if prompt := st.chat_input("Enter your command..."):
    if not api_token:
        st.error("Please enter API Token in sidebar.")
    else:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            ph = st.empty()
            ph.markdown("📡 Processing...")
            
            # Google API 호출
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model_id}:generateContent?key={api_token}"
            headers = {'Content-Type': 'application/json'}
            
            # 대화 기록 포함 (최근 10개)
            history_payload = []
            for msg in st.session_state["messages"][-10:]:
                role = "user" if msg["role"] == "user" else "model"
                history_payload.append({"role": role, "parts": [{"text": msg["content"]}]})

            payload = {
                "contents": history_payload,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
            }

            try:
                res = requests.post(url, headers=headers, data=json.dumps(payload))
                if res.status_code == 200:
                    result = res.json()
                    bot_text = result['candidates'][0]['content']['parts'][0]['text']
                    ph.markdown(bot_text)
                    st.session_state["messages"].append({"role": "assistant", "content": bot_text})
                    save_history()
                else:
                    ph.error(f"Err {res.status_code}: {res.text}")
            except Exception as e:
                ph.error(f"Error: {str(e)}")
