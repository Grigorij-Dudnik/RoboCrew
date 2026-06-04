"""
serve.py — Remote MolmoAct2 inference server for the SO-101.

Runs on the GPU box. Loads MolmoAct2-SO100_101 once and serves predict_chunk
over a raw TCP socket (4-byte big-endian length header + pickle). The robot box
(RoboCrew's create_molmoact2_single_arm_manipulation tool) connects, streams two
JPEG camera frames + the model-frame joint state + the task prompt, and gets
back a (T, 6) float32 action chunk in model frame.

Start it on the GPU box with:
    python -m robocrew.robots.XLeRobot.molmoact.serve
"""
import pickle
import socket
import time

import cv2
import numpy as np
from PIL import Image

from .policy import MolmoActPolicy
from .client import recv_msg, send_msg

POLICY = "allenai/MolmoAct2-SO100_101"
DEVICE = "cuda"
DTYPE = "bfloat16"
NUM_STEPS = 10
PORT = 5005


def _decode(jpg_bytes):
    arr = np.frombuffer(jpg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def main():
    policy = MolmoActPolicy.from_pretrained(POLICY, dtype=DTYPE, device=DEVICE)

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(1)
    print(f"[serve] Listening on 0.0.0.0:{PORT}")

    conn, addr = s.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"[serve] Client connected: {addr}")

    while True:
        if not send_msg(conn, "ready"):
            conn.close()
            conn, addr = s.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[serve] Client connected: {addr}")
            continue
        while True:
            req = recv_msg(conn)
            if req is None:
                break
            try:
                scene = _decode(req["scene_jpg"])
                wrist = _decode(req["wrist_jpg"])
                t0 = time.perf_counter()
                chunk = policy.predict_chunk(
                    images=[scene, wrist],
                    state=req["state"],
                    prompt=req["prompt"],
                    num_steps=NUM_STEPS,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                print(f"[serve] predict_chunk {dt_ms:.0f} ms  shape={chunk.shape}")
            except Exception as e:
                print(f"[serve] {type(e).__name__}: {e}")
                if not send_msg(conn, {"error": f"{type(e).__name__}: {e}"}):
                    break
                continue
            if not send_msg(conn, chunk):
                break
        conn.close()
        print("[serve] Client disconnected; waiting for a new connection.")
        conn, addr = s.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[serve] Client connected: {addr}")


if __name__ == "__main__":
    main()
