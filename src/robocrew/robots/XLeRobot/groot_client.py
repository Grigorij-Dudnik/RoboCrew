# robocrew/groot_client.py
# Self-contained GR00T PolicyClient — no gr00t package required.
# Dependencies: pip install pyzmq msgpack numpy

from __future__ import annotations

import io
from typing import Any

#import msgpack
import numpy as np
#import zmq


class _MsgSerializer:
    """Mirrors the serialization format used by the GR00T policy server."""

    @staticmethod
    def to_bytes(data: Any) -> bytes:
        return msgpack.packb(data, default=_MsgSerializer._encode)

    @staticmethod
    def from_bytes(data: bytes) -> Any:
        return msgpack.unpackb(data, object_hook=_MsgSerializer._decode)

    @staticmethod
    def _decode(obj: dict):
        if not isinstance(obj, dict):
            return obj
        if "__ndarray_class__" in obj:
            return np.load(io.BytesIO(obj["as_npy"]), allow_pickle=False)
        # ModalityConfig objects arrive as plain dicts on the client side — keep them as dicts.
        if "__ModalityConfig_class__" in obj:
            return obj["as_json"]
        return obj

    @staticmethod
    def _encode(obj):
        if isinstance(obj, np.ndarray):
            buf = io.BytesIO()
            np.save(buf, obj, allow_pickle=False)
            return {"__ndarray_class__": True, "as_npy": buf.getvalue()}
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        raise TypeError(f"Cannot serialize type {type(obj)}")


class PolicyClient:
    """Lightweight ZMQ client for the GR00T inference server.

    Mirrors the interface of gr00t.policy.server_client.PolicyClient
    without requiring the gr00t package to be installed.

    Dependencies: pyzmq, msgpack, numpy
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5555,
        timeout_ms: int = 15000,
        api_token: str | None = None,
    ):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.api_token = api_token
        self._context = zmq.Context()
        self._init_socket()

    def _init_socket(self) -> None:
        self._socket = self._context.socket(zmq.REQ)
        if self.timeout_ms:
            self._socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            self._socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self._socket.connect(f"tcp://{self.host}:{self.port}")

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    def call_endpoint(
        self,
        endpoint: str,
        data: dict | None = None,
        requires_input: bool = True,
    ) -> Any:
        request: dict = {"endpoint": endpoint}
        if requires_input:
            request["data"] = data or {}
        if self.api_token:
            request["api_token"] = self.api_token

        self._socket.send(_MsgSerializer.to_bytes(request))
        raw = self._socket.recv()

        if raw == b"ERROR":
            raise RuntimeError("GR00T server returned a generic ERROR.")

        response = _MsgSerializer.from_bytes(raw)

        if isinstance(response, dict) and "error" in response:
            raise RuntimeError(f"GR00T server error: {response['error']}")

        return response

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if the server is reachable."""
        try:
            self.call_endpoint("ping", requires_input=False)
            return True
        except zmq.error.ZMQError:
            self._init_socket()  # recreate socket for next attempt
            return False

    def reset(self, options: dict | None = None) -> dict:
        """Reset the policy episode state."""
        return self.call_endpoint("reset", {"options": options})

    def get_action(
        self,
        observation: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send an observation and receive (action_chunk, info).

        action_chunk keys match the modality config used during training,
        e.g. {"single_arm": np.ndarray(B, T, 5), "gripper": np.ndarray(B, T, 1)}.
        """
        response = self.call_endpoint(
            "get_action",
            {"observation": observation, "options": options},
        )
        return tuple(response)  # list -> (action, info)

    def get_modality_config(self) -> dict:
        """Retrieve the server's modality config (returned as plain dicts)."""
        return self.call_endpoint("get_modality_config", requires_input=False)

    def kill_server(self) -> None:
        """Ask the server to shut down."""
        self.call_endpoint("kill", requires_input=False)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._socket.close()
        self._context.term()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
