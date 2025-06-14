from cryptography.fernet import Fernet
import json
import os

# File paths
KEY_FILE = "memory.key"
MEMORY_FILE = "memory.lsn"

# Generate key and save
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
else:
    with open(KEY_FILE, "rb") as f:
        key = f.read()

fernet = Fernet(key)

# Setup basic memory
memory = {
    "user": "Kaeden",
    "notes": [],
    "history": []
}

# Encrypt and save memory
encrypted = fernet.encrypt(json.dumps(memory).encode())
with open(MEMORY_FILE, "wb") as f:
    f.write(encrypted)

print("✅ Encrypted memory file created.")
