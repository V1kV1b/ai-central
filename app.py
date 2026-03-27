import streamlit as st
import requests
import json
import uuid
import base64

# --- 🛑 SECURE API KEY HANDLING 🛑 ---
# The web server will secretly inject your key here
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("🚨 API Key missing! Add it to the Streamlit Cloud Secrets.")
    st.stop()

HISTORY_FILE = "advanced_history.json"

# --- DYNAMIC PRO ICONS ---
USER_ICON = "https://api.iconify.design/material-symbols/person-outline.svg?color=%23aaaaaa"
EMPTY_STATE_LOGO = "https://api.iconify.design/lucide/bot.svg?color=%23ffffff&width=64&height=64"

def get_ai_icon(model_name):
    if "GPT" in model_name: return "https://api.iconify.design/simple-icons/openai.svg?color=%23ffffff"
    if "Llama" in model_name: return "https://api.iconify.design/simple-icons/meta.svg?color=%23ffffff"
    if "Qwen" in model_name: return "https://api.iconify.design/simple-icons/alibabacloud.svg?color=%23ffffff"
    return "https://api.iconify.design/lucide/sparkles.svg?color=%23ffffff"

st.set_page_config(page_title="AI Workspace", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# --- OLLAMA ULTRA-DARK CSS ---
st.markdown("""
<style>
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #111111; color: #ececec; }
    [data-testid="stSidebar"] { background-color: #171717; border-right: 1px solid #222; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 850px; }
    .stChatMessage { background-color: transparent; border-radius: 8px; padding: 15px; }
    div.stButton > button { text-align: left; border: 1px solid #333; background: #1a1a1a; color: #ececec; border-radius: 8px; }
    div.stButton > button:hover { border: 1px solid #555; background-color: #222; color: white; }
    .empty-state { display: flex; justify-content: center; margin-top: 25vh; margin-bottom: 2rem; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

# --- MEMORY HANDLING ---
# (Note: On the free cloud, file-based memory wipes when the server sleeps. 
# We use session_state so it remembers during your active session!)
if "sessions" not in st.session_state: 
    st.session_state.sessions = {}
if "current_session" not in st.session_state:
    new_id = str(uuid.uuid4())
    st.session_state.sessions[new_id] = {"title": "New Chat", "messages": []}
    st.session_state.current_session = new_id

active_chat = st.session_state.sessions[st.session_state.current_session]["messages"]

# --- DATA: MODELS & PERSONAS ---
models = {
    "Llama 4 Scout 17B (Vision)": "meta-llama/llama-4-scout-17b-16e-instruct",
    "Qwen 3 32B": "qwen/qwen3-32b",
    "Llama 3.3 70B": "llama-3.3-70b-versatile",
    "Llama 3.1 8B": "llama-3.1-8b-instant",
    "GPT OSS 120B": "openai/gpt-oss-120b",
}

roles = {
    "Standard Assistant": "You are a highly intelligent, objective, and clear AI assistant.",
    "Software Engineer": "You are an expert Software Engineer. Provide robust code.",
    "Systems Architect": "You are a Systems Architect. Focus on system design and security.",
}

# --- SIDEBAR ---
with st.sidebar:
    if st.button("New Chat", icon=":material/edit_square:", use_container_width=True):
        new_id = str(uuid.uuid4())
        st.session_state.sessions[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.current_session = new_id
        st.rerun()
        
    st.markdown("<br><p style='color:#777; font-size:0.85rem; font-weight:600;'>Recent (This Session)</p>", unsafe_allow_html=True)
    for session_id, session_data in reversed(st.session_state.sessions.items()):
        if st.button(f"{session_data['title']}", key=session_id, use_container_width=True):
            st.session_state.current_session = session_id
            st.rerun()
            
    st.markdown("---")
    st.markdown("<p style='color:#777; font-size:0.85rem; font-weight:600;'>Workspace Controls</p>", unsafe_allow_html=True)
    system_prompt = roles[st.selectbox("Persona", list(roles.keys()), label_visibility="collapsed")]
    uploaded_file = st.file_uploader("Attach Context or Image", type=["txt", "md", "py", "csv", "png", "jpg", "jpeg"])

# --- MAIN UI: TOP CENTER MODEL SELECTOR ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    selected_model_name = st.selectbox("Engine", list(models.keys()), label_visibility="collapsed")
    model_choice = models[selected_model_name]

current_ai_icon = get_ai_icon(selected_model_name)

# --- MAIN UI: CHAT DISPLAY ---
if len(active_chat) == 0:
    st.markdown(f"<div class='empty-state'><img src='{EMPTY_STATE_LOGO}'></div>", unsafe_allow_html=True)
else:
    for message in active_chat:
        avatar_img = message.get("avatar", USER_ICON if message["role"] == "user" else EMPTY_STATE_LOGO)
        with st.chat_message(message["role"], avatar=avatar_img):
            st.markdown(message["content"])

def stream_generator(response):
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith("data: ") and decoded[6:] != "[DONE]":
                try:
                    content = json.loads(decoded[6:])["choices"][0]["delta"].get("content", "")
                    if content: yield content
                except: pass

# --- CHAT INPUT & LOGIC ---
if prompt := st.chat_input("Send a message..."):
    if len(active_chat) == 0:
        st.session_state.sessions[st.session_state.current_session]["title"] = prompt[:20] + "..." if len(prompt) > 20 else prompt

    if uploaded_file is not None:
        if uploaded_file.type.startswith("image/"):
            st.toast("📷 Image detected. Auto-switching to Vision Model...", icon="👀")
            base64_img = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
            model_choice = "meta-llama/llama-4-scout-17b-16e-instruct"
            current_ai_icon = get_ai_icon("Llama")
            final_prompt = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{uploaded_file.type};base64,{base64_img}"}}
            ]
            ui_prompt = f"{prompt}\n\n*[📷 Attached Image: {uploaded_file.name}]*"
        else:
            file_text = uploaded_file.getvalue().decode("utf-8")
            final_prompt = f"{prompt}\n\n--- [DOCUMENT CONTEXT] ---\n{file_text}"
            ui_prompt = prompt
    else:
        final_prompt = prompt
        ui_prompt = prompt

    active_chat.append({"role": "user", "content": ui_prompt, "avatar": USER_ICON})
    with st.chat_message("user", avatar=USER_ICON):
        st.markdown(ui_prompt)

    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in active_chat:
        clean_msg = {"role": msg["role"], "content": msg["content"]}
        if msg == active_chat[-1]: clean_msg["content"] = final_prompt 
        api_messages.append(clean_msg)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model_choice, "messages": api_messages, "stream": True}

    try:
        with st.chat_message("assistant", avatar=current_ai_icon):
            with st.spinner(""):
                response = requests.post(url, headers=headers, json=payload, stream=True)
            if response.status_code != 200:
                st.error(f"API Error: {response.text}")
                st.stop()
            full_response = st.write_stream(stream_generator(response))
            
        active_chat.append({"role": "assistant", "content": full_response, "avatar": current_ai_icon})
        st.rerun() 
    except Exception as e:
        st.error(f"Connection failed: {e}")