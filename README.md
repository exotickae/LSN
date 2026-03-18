# 🔦 Light-Speed Node

A private, encrypted, offline-first personal AI system — built for memory, autonomy, and peer-to-peer node networking. No cloud. No subscriptions. Your data stays yours.

> Built by Kaeden Taylor
> Powered by Streamlit + Python

---

## 🚀 What It Does

- 🔐 **Encrypted Chat** — All messages saved locally in an AES-encrypted `.lsn` file. Nothing leaves your device.
- 🤖 **Bring Your Own AI** — Upload any `.gguf` model (Llama, Mistral, Phi, etc.) to activate AI responses. The AI reads your full chat history for context. No model = chat saves only.
- 📡 **P2P Node Sync** — Nodes on the same WiFi or Bluetooth network auto-discover each other and stay in sync.
- 🌤 **Ambient Data** — Each node automatically shares its date/time, location, and weather with peers. Works offline using cached data.
- 🤝 **Consent-Gated Messaging** — Ambient data syncs freely, but direct message sync requires both parties to accept a chat request. Either side can revoke access at any time.
- ⚡ **Offline-First** — Everything works without internet. Weather and location fall back to cached values. Nodes sync the moment they find each other on the network.

---

## 🛠 How to Run

### 1. Install Python
https://www.python.org/downloads/ — check "Add to PATH" during install.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> `llama-cpp-python` is required only if you plan to use a local AI model. It may take a few minutes to install.

### 3. Run the app

```bash
streamlit run memory_ui.py
```

Opens at `http://localhost:8501`

---

## 🤖 Using a Local AI Model

1. Download any GGUF-format model (e.g. from [HuggingFace](https://huggingface.co/models?library=gguf))
2. Open the app → sidebar → **Upload .gguf to activate AI**
3. The AI loads and responds using your full chat history as context
4. Hit **Eject model** to go back to save-only mode

Previously uploaded models are listed in the sidebar for quick switching.

---

## 📡 Node Sync (WiFi / Bluetooth)

Run the app on multiple devices on the same network — they find each other automatically.

**What syncs automatically (no consent needed):**
- Current date & time
- Location (IP-based)
- Weather (via [wttr.in](https://wttr.in), no API key needed)

**What requires consent:**
- Chat messages — one node sends a request, the other must accept before any messages flow

Approvals are saved and persist across restarts. Either side can revoke at any time.

**Bluetooth** works the same way — Bluetooth PAN creates a local network interface, so discovery and sync work without any extra setup.

**Ports used:**
| Port | Purpose |
|------|---------|
| 8501 | Streamlit UI |
| 8502 | Node sync HTTP server |
| 8503 | UDP peer discovery (broadcast) |

---

## 🔐 Local Files

| File | Purpose |
|------|---------|
| `memory.key` | Fernet encryption key — keep this safe |
| `memory.lsn` | Encrypted chat/memory store |
| `.approved_peers.json` | Peers you've approved for messaging |
| `.ambient_cache.json` | Cached location & weather (offline fallback) |
| `.node_id` | Unique ID for this node |
| `models/` | Uploaded GGUF model files |

> `memory.key` and `memory.lsn` are excluded from git. Back them up manually if you want to preserve your history.

---

## 📁 File Structure

```
light-speed-node/
├── memory_ui.py            # Main Streamlit app
├── node_sync.py            # P2P discovery, ambient sync, consent system
├── init_memory.py          # One-time memory initialization
├── update_memory.py        # Manual memory update utility
├── requirements.txt        # Python dependencies
├── .streamlit/
│   └── config.toml         # Dark theme config
└── .claude/
    └── launch.json         # Dev server config
```

---

## 🔮 What's Coming

- Solar-powered, offline-ready USB node builds
- Multi-node mesh relay (messages hop between nodes)
- QR-code key sharing for easy device pairing
- Voice input / output
- Mobile companion app

---

## 🧠 Why It Exists

This isn't a chatbot clone. It's a personal AI infrastructure you fully own — encrypted, self-hosted, and built to run anywhere power exists. Whether you're building for privacy, permanence, or off-grid independence, Light-Speed Node keeps your data and intelligence in your hands.

---

## 💬 Questions / Contributions

Open a GitHub Issue or reach out:
📫 `kaedentaylor12345@gmail.com`
