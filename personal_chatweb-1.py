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
    except:
        return ""

# --- 3. 실시간 모델 목록 가져오기 ---
@st.cache_data(ttl=600)
def get_realtime_models(api_key: str):
    if not api_key:
        return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash"}}

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            models = res.json().get("models", [])
            dynamic_options = {}
            for m in models:
                name = m.get("name", "")
                methods = m.get("supportedGenerationMethods", [])
                if not name or "generateContent" not in methods:
                    continue
                model_id = name.replace("models/", "")
                label = model_id.replace("-", " ")
                dynamic_options[model_id] = label

            if not dynamic_options:
                return {"Default": {"gemini-1.5-flash": "Gemini 1.5 Flash"}}

            return {"Available Models": dynamic_options}

        return {"Error": {"gemini-1.5-flash": f"API Error {res.status_code}"}}
    except Exception:
        return {"Error": {"gemini-1.5-flash": "Connection Error"}}

# --- 4. 복사 스크립트 ---
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# --- 5. 히스토리 관리 ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "auth" not in st.session_state:
    st.session_state["auth"] = False

# 검색 지원 테스트 결과 저장: {model_id: {"status": "...", "detail": "..."}}
if "search_support" not in st.session_state:
    st.session_state["search_support"] = {}

def save_history():
    with open(HISTORY_FILE, "w") as f:
        f.write(encrypt_data(json.dumps(st.session_state["messages"]), ACCESS_PASSWORD))

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = decrypt_data(f.read(), ACCESS_PASSWORD)
                if data:
                    st.session_state["messages"] = json.loads(data)
        except:
            pass

# --- 안전 파서 ---
def extract_text_from_candidate(candidate: dict) -> str:
    content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    texts = []
    for p in parts:
        if isinstance(p, dict):
            t = p.get("text")
            if isinstance(t, str):
                texts.append(t)
    return "".join(texts).strip()

def extract_sources_from_candidate(candidate: dict):
    sources = []
    metadata = candidate.get("groundingMetadata", {}) if isinstance(candidate, dict) else {}
    chunks = metadata.get("groundingChunks", []) if isinstance(metadata, dict) else []
    for ch in chunks:
        if not isinstance(ch, dict):
            continue
        web = ch.get("web")
        if isinstance(web, dict):
            title = web.get("title")
            uri = web.get("uri")
            if title and uri:
                sources.append({"title": title, "uri": uri})
    return sources

# --- 모델별 search tool 선택 ---
def build_tools(selected_model: str, use_search: bool):
    if not use_search:
        return []
    if selected_model.startswith("gemini-1.5"):
        return [{
            "google_search_retrieval": {
                "dynamic_retrieval_config": {
                    "mode": "MODE_DYNAMIC",
                    "dynamic_threshold": 0.7
                }
            }
        }]
    return [{"google_search": {}}]

# --- [추가] Search 지원 테스트 ---
def test_search_support(api_token: str, selected_model: str):
    """
    현재 모델로 tools 포함 호출을 1회 수행해,
    Search/Grounding이 작동 가능한지 대략 판별.
    """
    if not api_token:
        return {"status": "NO_KEY", "detail": "API Key가 필요합니다."}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_token}

    # 검색이 동작해야 답 가능한 질문(간단)
    tools = build_tools(selected_model, use_search=True)
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": "Find one recent fact about the Eiffel Tower and cite the source."}]
        }],
        "tools": tools,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256}
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            data = res.json()
            cand0 = (data.get("candidates") or [{}])[0]
            # groundingMetadata가 있으면 거의 확실히 검색툴이 먹은 것
            meta = cand0.get("groundingMetadata")
            if meta and (meta.get("groundingChunks") or meta.get("webSearchQueries")):
                return {"status": "OK", "detail": "Search/Grounding 응답 확인됨"}
            # 200인데 groundingMetadata가 없을 수도 있음(모델이 검색이 불필요하다고 판단)
            return {"status": "MAYBE", "detail": "200 OK지만 groundingMetadata가 없을 수 있음"}
        else:
            # tool 스키마/모델 미지원 시 여기에 걸림
            txt = res.text[:4000]
            # 흔한 “툴 미지원” 문구들을 넓게 잡아 분류
            lowered = txt.lower()
            if ("unknown field" in lowered) or ("not supported" in lowered) or ("invalid argument" in lowered):
                return {"status": "NO", "detail": f"툴 미지원 가능성 높음: {txt}"}
            return {"status": "ERROR", "detail": f"{res.status_code}: {txt}"}
    except Exception as e:
        return {"status": "ERROR", "detail": str(e)}

# --- 6. 사이드바 ---
with st.sidebar:
    st.title("⚙️ Setup")

    # 로그인
    if not st.session_state["auth"]:
        pwd = st.text_input("Access Code", type="password", key="login_pwd")
        if st.button("Login", key="login_btn"):
            if pwd == ACCESS_PASSWORD:
                st.session_state["auth"] = True
                load_history()
                st.rerun()
            else:
                st.error("Wrong Code")
        st.stop()

    api_token = st.text_input("🔑 Gemini API Key", type="password", key="api_key_input")

    if st.button("🔄 Refresh Models", key="refresh_models_btn"):
        st.cache_data.clear()
        st.success("Updated")

    MODEL_DATA = get_realtime_models(api_token)
    models_group = list(MODEL_DATA.keys())[0]
    models_list = MODEL_DATA[models_group]

    selected_model = st.selectbox(
        "🤖 Model Engine",
        list(models_list.keys()),
        format_func=lambda x: models_list.get(x, x),
        key="model_select",
    )

    # 검색 토글
    use_search = st.toggle("🌐 Google Search (Grounding)", value=True, key="search_toggle")

    # --- [추가] 모델 검색 지원 상태 표시 + 테스트 버튼 ---
    s = st.session_state["search_support"].get(selected_model, {"status": "UNTESTED", "detail": ""})
    badge = {
        "UNTESTED": "⚪ 미테스트",
        "OK": "🟢 검색 가능",
        "MAYBE": "🟡 애매(200 OK)",
        "NO": "🔴 검색 불가(추정)",
        "ERROR": "🟠 에러",
        "NO_KEY": "⚫ 키 필요",
    }.get(s["status"], "⚪ 미테스트")

    st.caption(f"Search Support: **{badge}**")

    colA, colB = st.columns(2)
    with colA:
        if st.button("🔎 Test Search Support", key="test_search_btn"):
            with st.spinner("Testing..."):
                result = test_search_support(api_token, selected_model)
                st.session_state["search_support"][selected_model] = result
                st.rerun()
    with colB:
        if st.button("🧹 Clear Test", key="clear_test_btn"):
            st.session_state["search_support"].pop(selected_model, None)
            st.rerun()

    if s.get("detail"):
        with st.expander("Test detail"):
            st.write(s["detail"])

    # 히스토리 초기화
    if st.button("🗑️ Clear History", key="clear_history_btn"):
        st.session_state["messages"] = []
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        st.rerun()

# --- 7. 메인 ---
st.title("📊 AI Intelligence Center")

# --- [추가] Chat 영역 존재 여부 확인용 표시 ---
st.caption("아래는 채팅 영역입니다. (API Key가 있으면 입력창이 하단에 나타납니다.)")

# 메시지 렌더
for i, m in enumerate(st.session_state["messages"]):
    with st.chat_message(m["role"]):
        if m["role"] == "assistant":
            content_encoded = base64.b64encode(m["content"].encode("utf-8")).decode("utf-8")
            st.markdown(
                f'<button id="md_{i}" class="custom-copy-btn" onclick="copyText(\'{content_encoded}\', \'md_{i}\', \'md\')">📋 MD</button>'
                f'<button id="txt_{i}" class="custom-copy-btn" onclick="copyText(\'{content_encoded}\', \'txt_{i}\', \'txt\')">📝 TXT</button>',
                unsafe_allow_html=True,
            )
            st.markdown(m["content"])
            if m.get("sources"):
                with st.expander("📚 Sources"):
                    for s in m["sources"]:
                        st.write(f"- [{s['title']}]({s['uri']})")
        else:
            st.markdown(m["content"])

# --- Chat input: API Key 있으면 활성화, 없으면 안내만 ---
if not api_token:
    st.info("왼쪽 사이드바에 Gemini API Key를 입력하면 하단에 채팅 입력창이 활성화돼요.")
    st.stop()

prompt = st.chat_input("Ask anything...")
if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty()
        ph.markdown("📡 Processing...")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_token}

        # 최근 10개만 컨텍스트
        contents = []
        for msg in st.session_state["messages"][-10:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        tools = build_tools(selected_model, use_search)

        payload = {
            "contents": contents,
            "tools": tools,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }

        def call_gemini(p):
            return requests.post(url, headers=headers, json=p, timeout=60)

        try:
            res = call_gemini(payload)

            # --- Search tool이 문제면 tools 없이 자동 재시도 ---
            if res.status_code != 200 and use_search and tools:
                payload_no_tools = dict(payload)
                payload_no_tools["tools"] = []
                res2 = call_gemini(payload_no_tools)

                if res2.status_code == 200:
                    data = res2.json()
                    cand0 = (data.get("candidates") or [{}])[0]
                    bot_text = extract_text_from_candidate(cand0) or "(응답 텍스트를 추출하지 못했어요.)"

                    ph.markdown(
                        bot_text
                        + "\n\n⚠️ 참고: 선택한 모델/설정에서 Web Search(Grounding)가 지원되지 않아, 검색 없이 답변했어요."
                    )

                    st.session_state["messages"].append({"role": "assistant", "content": bot_text, "sources": []})
                    save_history()
                    st.stop()

            if res.status_code == 200:
                data = res.json()
                cand0 = (data.get("candidates") or [{}])[0]

                bot_text = extract_text_from_candidate(cand0) or "(응답 텍스트를 추출하지 못했어요.)"
                sources = extract_sources_from_candidate(cand0)

                ph.markdown(bot_text)
                st.session_state["messages"].append({"role": "assistant", "content": bot_text, "sources": sources})
                save_history()

                if sources:
                    st.rerun()
            else:
                ph.error(f"Error {res.status_code}: {res.text}")

        except Exception as e:
            ph.error(str(e))            key_c = key[i % len(key)]
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
