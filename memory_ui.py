import streamlit as st
import json
import os
import time
import uuid
from cryptography.fernet import Fernet

KEY_FILE = "memory.key"
MEMORY_FILE = "memory.lsn"
MODELS_DIR = "models"

os.makedirs(MODELS_DIR, exist_ok=True)


# --- Memory ---

def load_memory():
    if not os.path.exists(KEY_FILE) or os.path.getsize(KEY_FILE) == 0:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()

    fernet = Fernet(key)

    if not os.path.exists(MEMORY_FILE) or os.path.getsize(MEMORY_FILE) == 0:
        memory = {"user": "Kaeden", "messages": []}
        _write_memory(fernet, memory)
    else:
        with open(MEMORY_FILE, "rb") as f:
            memory = json.loads(fernet.decrypt(f.read()).decode())

    return fernet, memory


def _write_memory(fernet, memory):
    with open(MEMORY_FILE, "wb") as f:
        f.write(fernet.encrypt(json.dumps(memory).encode()))


def stamp(msg: dict, node_id: str) -> dict:
    if "id" not in msg:
        msg["id"] = f"{node_id}_{uuid.uuid4().hex[:8]}"
    if "ts" not in msg:
        msg["ts"] = time.time()
    if "node" not in msg:
        msg["node"] = node_id
    return msg


def merge_messages(local: list, remote: list) -> int:
    seen = {m["id"] for m in local if "id" in m}
    added = 0
    for msg in remote:
        if "id" in msg and msg["id"] not in seen:
            local.append(msg)
            seen.add(msg["id"])
            added += 1
    if added:
        local.sort(key=lambda m: m.get("ts", 0))
    return added


# --- AI (optional) ---

@st.cache_resource
def load_llm(model_path: str):
    try:
        from llama_cpp import Llama
        return Llama(model_path=model_path, n_ctx=2048, n_threads=4)
    except Exception:
        return None


def ai_response(llm, history: list) -> str:
    prompt = "<|system|>\nYou are a helpful personal AI assistant with access to the user's full chat history.\n</s>\n"
    for msg in history:
        tag = "<|user|>" if msg["role"] == "user" else "<|assistant|>"
        prompt += f"{tag}\n{msg['content']}</s>\n"
    prompt += "<|assistant|>\n"
    output = llm(prompt, max_tokens=256, stop=["</s>", "<|user|>"])
    return output["choices"][0]["text"].strip()


# --- Node sync ---

@st.cache_resource
def start_sync_node(_get_fn, _merge_fn):
    from node_sync import NodeSync
    node = NodeSync(_get_fn, _merge_fn)
    node.start()
    return node


# --- App ---

st.set_page_config(page_title="Light-Speed Node", layout="centered")
st.title("💡 Light-Speed Node")

# Init session state
if "fernet" not in st.session_state:
    fernet, memory = load_memory()
    st.session_state.fernet = fernet
    st.session_state.memory = memory
    st.session_state.messages = memory.get("messages", [])
    st.session_state.model_path = None
    st.session_state.model_name = None

from node_sync import get_node_id, get_local_ip
NODE_ID = get_node_id()


def get_messages():
    return st.session_state.get("messages", [])


def merge_and_save(remote: list) -> int:
    msgs = st.session_state.get("messages", [])
    added = merge_messages(msgs, remote)
    if added:
        st.session_state.messages = msgs
        st.session_state.memory["messages"] = msgs
        _write_memory(st.session_state.fernet, st.session_state.memory)
    return added


sync = start_sync_node(get_messages, merge_and_save)


# --- Sidebar ---
with st.sidebar:

    # -- This node info --
    st.header("🌐 This Node")
    st.caption(f"ID: `{NODE_ID}`")
    st.caption(f"IP: `{get_local_ip()}:8502`")

    my_ambient = sync.get_ambient()
    st.caption(f"🕐 {my_ambient['datetime']}")
    if my_ambient["location"]:
        st.caption(f"📍 {my_ambient['location']}")
    if my_ambient["weather"]:
        st.caption(f"🌤 {my_ambient['weather']}")

    st.divider()

    # -- Incoming chat requests --
    pending = list(sync.pending_requests)
    if pending:
        st.subheader("📩 Chat Requests")
        for req in pending:
            peer_id = req["node_id"]
            st.warning(f"Node `{peer_id}` wants to chat")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Accept", key=f"accept_{peer_id}"):
                    sync.respond_to_request(peer_id, accept=True)
                    st.rerun()
            with col2:
                if st.button("❌ Decline", key=f"decline_{peer_id}"):
                    sync.respond_to_request(peer_id, accept=False)
                    st.rerun()
        st.divider()

    # -- Peers --
    peers = sync.active_peers()
    if peers:
        st.subheader(f"📡 Peers ({len(peers)})")
        for peer in peers:
            pid = peer["node_id"]
            ambient = peer.get("ambient", {})
            approved = pid in sync.approved_peers
            pending_out = pid in sync.pending_outbound

            with st.expander(f"{'🔓' if approved else '🔒'} `{pid}`"):
                if ambient.get("datetime"):
                    st.caption(f"🕐 {ambient['datetime']}")
                if ambient.get("location"):
                    st.caption(f"📍 {ambient['location']}")
                if ambient.get("weather"):
                    st.caption(f"🌤 {ambient['weather']}")

                if approved:
                    if st.button("Revoke chat", key=f"revoke_{pid}"):
                        sync.revoke_chat(pid)
                        st.rerun()
                elif pending_out:
                    st.info("Request sent — waiting...")
                else:
                    if st.button("Request chat", key=f"req_{pid}"):
                        sync.request_chat(pid)
                        st.rerun()
    else:
        st.info("No peers detected — broadcasting...")

    if sync.sync_log:
        with st.expander("Sync log"):
            for line in reversed(sync.sync_log[-10:]):
                st.caption(line)

    st.divider()

    # -- AI model --
    st.header("🤖 AI Model")
    if st.session_state.model_name:
        st.success(f"**{st.session_state.model_name}**")
        if st.button("Eject model"):
            st.session_state.model_path = None
            st.session_state.model_name = None
            st.rerun()
    else:
        st.info("No model — chat saves only.")

    uploaded_file = st.file_uploader("Upload .gguf to activate AI", type=["gguf"])
    if uploaded_file:
        save_path = os.path.join(MODELS_DIR, uploaded_file.name)
        if not os.path.exists(save_path):
            with open(save_path, "wb") as f:
                f.write(uploaded_file.read())
        st.session_state.model_path = save_path
        st.session_state.model_name = uploaded_file.name
        st.rerun()

    saved_models = [f for f in os.listdir(MODELS_DIR) if f.endswith(".gguf")]
    if saved_models:
        for name in saved_models:
            if st.button(name, key=f"m_{name}"):
                st.session_state.model_path = os.path.join(MODELS_DIR, name)
                st.session_state.model_name = name
                st.rerun()

    st.divider()
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.session_state.memory["messages"] = []
        _write_memory(st.session_state.fernet, st.session_state.memory)
        st.rerun()


# --- Chat ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Type a message..."):
    user_msg = stamp({"role": "user", "content": prompt}, NODE_ID)
    st.session_state.messages.append(user_msg)
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.model_path:
        llm = load_llm(st.session_state.model_path)
        if llm:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = ai_response(llm, st.session_state.messages)
                st.markdown(reply)
            ai_msg = stamp({"role": "assistant", "content": reply}, NODE_ID)
            st.session_state.messages.append(ai_msg)
        else:
            st.error("⚠️ Failed to load model.")

    st.session_state.memory["messages"] = st.session_state.messages
    _write_memory(st.session_state.fernet, st.session_state.memory)
