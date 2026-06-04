"""
client.py — RemotePolicyClient: talks to the MolmoAct2 serve.py over a raw TCP
socket (4-byte big-endian length header + pickle).

Duck-typed stand-in for the model: exposes the same predict_chunk signature the
AsyncPolicyRunner expects, so the runtime is unchanged. The robot box never
imports torch — the GPU model lives in serve.py.
"""
import pickle
import socket

import cv2
import numpy as np


def recv_msg(conn):
    try:
        hdr = b""
        while len(hdr) < 4:
            chunk = conn.recv(4 - len(hdr))
            if not chunk:
                return None
            hdr += chunk
        data = b""
        size = int.from_bytes(hdr, "big")
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return pickle.loads(data)
    except ConnectionResetError:
        return None


def send_msg(conn, msg):
    try:
        data = pickle.dumps(msg)
        conn.sendall(len(data).to_bytes(4, "big") + data)
        return True
    except (BrokenPipeError, ConnectionResetError):
        return False


class RemotePolicyClient:
    """Runs predict_chunk on a remote MolmoAct2 serve.py.

    Same signature as the local MolmoActPolicy.predict_chunk, so the producer is
    unchanged. num_steps / cuda_graph are owned by the server and ignored here.
    """

    def __init__(self, server: str, port: int, jpeg_quality: int = 85):
        self.server = server
        self.port = int(port)
        self.jpeg_quality = jpeg_quality
        self.sock = None
        self._connect()

    def _connect(self):
        s = socket.socket()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[RemotePolicy] Connecting to {self.server}:{self.port} ...")
        s.connect((self.server, self.port))
        if recv_msg(s) != "ready":
            raise RuntimeError("Server did not send 'ready' handshake.")
        self.sock = s
        print("[RemotePolicy] Connected.")

    def _encode(self, pil_img):
        bgr = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)
        _, jpg = cv2.imencode(".jpg", bgr,
                              [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        return jpg.tobytes()

    def predict_chunk(self, images, state, prompt, *,
                      num_steps=10, cuda_graph=False):
        scene, wrist = images  # [scene, wrist] PIL images
        req = {
            "scene_jpg": self._encode(scene),
            "wrist_jpg": self._encode(wrist),
            "state": np.asarray(state, dtype=np.float32),
            "prompt": prompt,
        }
        if not send_msg(self.sock, req):
            self._connect()
            send_msg(self.sock, req)
        resp = recv_msg(self.sock)
        if resp is None:
            self._connect()
            recv_msg(self.sock)  # consume the post-reconnect 'ready'
            send_msg(self.sock, req)
            resp = recv_msg(self.sock)
        if isinstance(resp, dict) and "error" in resp:
            raise RuntimeError(f"Server error: {resp['error']}")
        return np.asarray(resp, dtype=np.float32)

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
