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

# Only create memory file if it doesn't already exist or is empty
if not os.path.exists(MEMORY_FILE) or os.path.getsize(MEMORY_FILE) == 0:
    memory = {
        "user": "Kaeden",
        "notes": [],
        "history": []
    }
    encrypted = fernet.encrypt(json.dumps(memory).encode())
    with open(MEMORY_FILE, "wb") as f:
        f.write(encrypted)
    print("✅ Encrypted memory file created.")
else:
    print("ℹ️ Memory file already exists, skipping initialization.")
