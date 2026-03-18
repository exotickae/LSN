"""
Light-Speed Node - P2P sync over LAN.

Nodes auto-share ambient data (datetime, weather, location).
Direct messaging requires explicit consent from both parties.
"""

import json
import os
import socket
import threading
import time
import uuid
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

SYNC_PORT = 8502
DISCOVERY_PORT = 8503
BROADCAST_INTERVAL = 15
RESYNC_INTERVAL = 60
AMBIENT_REFRESH = 600   # refresh weather/location every 10 min

NODE_ID_FILE = ".node_id"
APPROVED_PEERS_FILE = ".approved_peers.json"
AMBIENT_CACHE_FILE = ".ambient_cache.json"


def get_node_id() -> str:
    if os.path.exists(NODE_ID_FILE):
        with open(NODE_ID_FILE) as f:
            return f.read().strip()
    node_id = str(uuid.uuid4())[:8]
    with open(NODE_ID_FILE, "w") as f:
        f.write(node_id)
    return node_id


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_approved_peers() -> set:
    if os.path.exists(APPROVED_PEERS_FILE):
        try:
            with open(APPROVED_PEERS_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_approved_peers(peers: set):
    with open(APPROVED_PEERS_FILE, "w") as f:
        json.dump(list(peers), f)


def _load_ambient_cache() -> dict:
    if os.path.exists(AMBIENT_CACHE_FILE):
        try:
            with open(AMBIENT_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"location": "", "weather": "", "last_updated": 0}


def _save_ambient_cache(data: dict):
    with open(AMBIENT_CACHE_FILE, "w") as f:
        json.dump(data, f)


def _fetch_location() -> str:
    try:
        req = urllib.request.Request(
            "https://ipinfo.io/json",
            headers={"User-Agent": "LightSpeedNode/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        parts = [data.get("city", ""), data.get("region", ""), data.get("country", "")]
        return ", ".join(p for p in parts if p)
    except Exception:
        return ""


def _fetch_weather(location: str) -> str:
    try:
        loc = urllib.parse.quote(location) if location else ""
        url = f"https://wttr.in/{loc}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return ""


class NodeSync:
    def __init__(self, get_messages_fn, merge_fn):
        self.node_id = get_node_id()
        self.local_ip = get_local_ip()
        self.get_messages = get_messages_fn
        self.merge = merge_fn

        self._lock = threading.Lock()
        self.approved_peers: set = load_approved_peers()
        self.peers: dict = {}           # node_id -> {"ip", "port", "ambient", "last_seen"}
        self.pending_requests: list = []  # incoming: [{"node_id", "ip", "port"}]
        self.pending_outbound: set = set()  # node_ids we've sent a request to

        self.ambient: dict = _load_ambient_cache()
        self.sync_log: list = []
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._http_server, daemon=True).start()
        threading.Thread(target=self._broadcaster, daemon=True).start()
        threading.Thread(target=self._listener, daemon=True).start()
        threading.Thread(target=self._ambient_updater, daemon=True).start()

    def stop(self):
        self.running = False

    # --- Ambient data ---

    def _ambient_updater(self):
        """Refresh location and weather in background, cache results."""
        while self.running:
            age = time.time() - self.ambient.get("last_updated", 0)
            if age > AMBIENT_REFRESH:
                location = _fetch_location()
                weather = _fetch_weather(location)
                with self._lock:
                    self.ambient = {
                        "location": location or self.ambient.get("location", ""),
                        "weather": weather or self.ambient.get("weather", ""),
                        "last_updated": time.time(),
                    }
                _save_ambient_cache(self.ambient)
                if location or weather:
                    self._log(f"Ambient updated: {location} / {weather}")
            time.sleep(60)

    def get_ambient(self) -> dict:
        with self._lock:
            return {
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "location": self.ambient.get("location", ""),
                "weather": self.ambient.get("weather", ""),
                "last_updated": self.ambient.get("last_updated", 0),
            }

    # --- Consent ---

    def request_chat(self, peer_id: str) -> bool:
        """Send a chat request to a peer. Returns True if request was sent."""
        with self._lock:
            peer = self.peers.get(peer_id)
        if not peer:
            return False
        payload = json.dumps({
            "node_id": self.node_id,
            "ip": self.local_ip,
            "port": SYNC_PORT,
        }).encode()
        try:
            req = urllib.request.Request(
                f"http://{peer['ip']}:{peer['port']}/chat_request",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=5)
            with self._lock:
                self.pending_outbound.add(peer_id)
            self._log(f"Chat request sent to {peer_id}")
            return True
        except Exception as e:
            self._log(f"Failed to send request to {peer_id}: {e}")
            return False

    def respond_to_request(self, peer_id: str, accept: bool):
        """Accept or decline an incoming chat request."""
        with self._lock:
            req_entry = next((r for r in self.pending_requests if r["node_id"] == peer_id), None)
            if req_entry:
                self.pending_requests = [r for r in self.pending_requests if r["node_id"] != peer_id]

        if not req_entry:
            return

        if accept:
            with self._lock:
                self.approved_peers.add(peer_id)
            _save_approved_peers(self.approved_peers)
            self._log(f"Approved chat with {peer_id}")

        # Notify peer of decision
        payload = json.dumps({
            "node_id": self.node_id,
            "accepted": accept,
        }).encode()
        try:
            req = urllib.request.Request(
                f"http://{req_entry['ip']}:{req_entry['port']}/chat_response",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def revoke_chat(self, peer_id: str):
        """Remove a peer from approved list."""
        with self._lock:
            self.approved_peers.discard(peer_id)
        _save_approved_peers(self.approved_peers)
        self._log(f"Revoked chat access for {peer_id}")

    def active_peers(self) -> list:
        cutoff = time.time() - 120
        with self._lock:
            return [
                {"node_id": nid, **info}
                for nid, info in self.peers.items()
                if info.get("last_seen", 0) > cutoff
            ]

    # --- HTTP server ---

    def _http_server(self):
        sync = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _read_json(self):
                length = int(self.headers.get("Content-Length", 0))
                return json.loads(self.rfile.read(length).decode())

            def _send_json(self, data, status=200):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/ping":
                    self._send_json({"node_id": sync.node_id, "ip": sync.local_ip})

                elif self.path == "/ambient":
                    self._send_json(sync.get_ambient())

                elif self.path == "/messages":
                    peer_id = self.headers.get("X-Node-ID", "")
                    with sync._lock:
                        approved = peer_id in sync.approved_peers
                    if not approved:
                        self._send_json({"error": "not approved"}, 403)
                        return
                    self._send_json(sync.get_messages())

                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path == "/messages":
                    peer_id = self.headers.get("X-Node-ID", "")
                    with sync._lock:
                        approved = peer_id in sync.approved_peers
                    if not approved:
                        self._send_json({"error": "not approved"}, 403)
                        return
                    remote = self._read_json()
                    added = sync.merge(remote)
                    if added:
                        sync._log(f"Received {added} message(s) from {peer_id}")
                    self.send_response(200)
                    self.end_headers()

                elif self.path == "/chat_request":
                    data = self._read_json()
                    peer_id = data.get("node_id", "")
                    with sync._lock:
                        already_approved = peer_id in sync.approved_peers
                        already_pending = any(r["node_id"] == peer_id for r in sync.pending_requests)
                    if not already_approved and not already_pending:
                        with sync._lock:
                            sync.pending_requests.append({
                                "node_id": peer_id,
                                "ip": data.get("ip", self.client_address[0]),
                                "port": data.get("port", SYNC_PORT),
                            })
                        sync._log(f"Chat request received from {peer_id}")
                    self.send_response(200)
                    self.end_headers()

                elif self.path == "/chat_response":
                    data = self._read_json()
                    peer_id = data.get("node_id", "")
                    accepted = data.get("accepted", False)
                    with sync._lock:
                        sync.pending_outbound.discard(peer_id)
                        if accepted:
                            sync.approved_peers.add(peer_id)
                    if accepted:
                        _save_approved_peers(sync.approved_peers)
                        sync._log(f"{peer_id} accepted your chat request")
                    else:
                        sync._log(f"{peer_id} declined your chat request")
                    self.send_response(200)
                    self.end_headers()

                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            server = HTTPServer(("0.0.0.0", SYNC_PORT), Handler)
            server.serve_forever()
        except OSError as e:
            self._log(f"Sync server error: {e}")

    # --- Discovery ---

    def _broadcaster(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            payload = json.dumps({
                "type": "LSN_NODE",
                "node_id": self.node_id,
                "ip": self.local_ip,
                "port": SYNC_PORT,
            }).encode()
            try:
                sock.sendto(payload, ("<broadcast>", DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(BROADCAST_INTERVAL)

    def _listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
        except OSError:
            self._log(f"Discovery port {DISCOVERY_PORT} busy")
            return
        sock.settimeout(1.0)

        while self.running:
            try:
                data, _ = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("type") != "LSN_NODE" or msg["node_id"] == self.node_id:
                    continue

                peer_id = msg["node_id"]
                now = time.time()

                with self._lock:
                    existing = self.peers.get(peer_id, {})
                    last_seen = existing.get("last_seen", 0)
                    self.peers[peer_id] = {
                        **existing,
                        "ip": msg["ip"],
                        "port": msg["port"],
                        "last_seen": now,
                    }

                # Fetch ambient data and do message sync if approved
                if now - last_seen > RESYNC_INTERVAL:
                    threading.Thread(
                        target=self._update_peer,
                        args=(peer_id, msg["ip"], msg["port"]),
                        daemon=True,
                    ).start()

            except socket.timeout:
                pass
            except Exception:
                pass

    def _update_peer(self, peer_id: str, ip: str, port: int):
        """Pull ambient data from peer. Sync messages only if approved."""
        base = f"http://{ip}:{port}"
        try:
            with urllib.request.urlopen(f"{base}/ambient", timeout=5) as r:
                ambient = json.loads(r.read().decode())
            with self._lock:
                if peer_id in self.peers:
                    self.peers[peer_id]["ambient"] = ambient
        except Exception:
            pass

        with self._lock:
            approved = peer_id in self.approved_peers
        if not approved:
            return

        # Sync messages
        try:
            req = urllib.request.Request(f"{base}/messages")
            req.add_header("X-Node-ID", self.node_id)
            with urllib.request.urlopen(req, timeout=5) as r:
                remote = json.loads(r.read().decode())
            added = self.merge(remote)
            if added:
                self._log(f"Synced {added} message(s) with {peer_id}")

            our_data = json.dumps(self.get_messages()).encode()
            push_req = urllib.request.Request(f"{base}/messages", data=our_data, method="POST")
            push_req.add_header("Content-Type", "application/json")
            push_req.add_header("X-Node-ID", self.node_id)
            urllib.request.urlopen(push_req, timeout=5)
        except Exception:
            pass

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        with self._lock:
            self.sync_log.append(f"[{ts}] {msg}")
            if len(self.sync_log) > 50:
                self.sync_log.pop(0)
