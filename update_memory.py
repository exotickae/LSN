from cryptography.fernet import Fernet
import json

# File paths
KEY_FILE = "memory.key"
MEMORY_FILE = "memory.lsn"

# Load key + decrypt memory
with open(KEY_FILE, "rb") as f:
    key = f.read()
fernet = Fernet(key)

with open(MEMORY_FILE, "rb") as f:
    decrypted = fernet.decrypt(f.read())
memory = json.loads(decrypted.decode())

# ✅ Add something
memory["notes"].append("Kaeden's solar-powered AI plan logged.")
memory["history"].append("User launched encrypted memory update test.")

# 🔐 Re-encrypt and save
with open(MEMORY_FILE, "wb") as f:
    f.write(fernet.encrypt(json.dumps(memory).encode()))

# 🧠 Show last 3 thoughts
print("Latest notes:", memory["notes"][-3:])
print("Latest history:", memory["history"][-3:])
