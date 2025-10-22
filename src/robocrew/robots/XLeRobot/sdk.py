"""Minimal utilities for talking to SCS servos over serial."""

from __future__ import annotations

from typing import Dict, List, Optional

import serial  # type: ignore[import]
import serial.tools.list_ports  # type: ignore[import]

BROADCAST_ID = 0xFE
INST_WRITE = 0x03
INST_SYNC_WRITE = 0x83

ADDR_SCS_GOAL_SPEED = 46
ADDR_SCS_MODE = 33
ADDR_SCS_LOCK = 55

DEFAULT_BAUDRATE = 1_000_000
MAX_SPEED = 10_000


def _lo(value: int) -> int:
    return value & 0xFF


def _hi(value: int) -> int:
    return (value >> 8) & 0xFF


class ScsServoSDK:
    """Tiny protocol helper that keeps only the wheel-facing surface."""

    def __init__(self) -> None:
        self.serial: Optional[serial.Serial] = None

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE, protocol_end: int = 0) -> bool:
        try:
            self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            return True
        except Exception:
            self.serial = None
            return False

    def disconnect(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.serial = None

    def _ensure_serial(self) -> serial.Serial:
        if not self.serial or not self.serial.is_open:
            raise RuntimeError("Serial port is not open")
        return self.serial

    def _packet(self, scs_id: int, instruction: int, params: List[int]) -> List[int]:
        packet = [0xFF, 0xFF, scs_id & 0xFF, len(params) + 2, instruction & 0xFF]
        packet.extend(p & 0xFF for p in params)
        checksum = (~sum(packet[2:])) & 0xFF
        packet.append(checksum)
        return packet

    def _send(self, packet: List[int]) -> None:
        ser = self._ensure_serial()
        data = bytes(b & 0xFF for b in packet)
        written = ser.write(data)
        if written != len(data):
            raise RuntimeError("Incomplete packet write")
        ser.flush()

    def _write(self, servo_id: int, address: int, data: List[int]) -> None:
        params = [address & 0xFF, *data]
        packet = self._packet(servo_id, INST_WRITE, params)
        self._send(packet)

    def _write_byte(self, servo_id: int, address: int, value: int) -> None:
        self._write(servo_id, address, [_lo(value)])

    def _write_word(self, servo_id: int, address: int, value: int) -> None:
        self._write(servo_id, address, [_lo(value), _hi(value)])

    def set_wheel_mode(self, servo_id: int) -> str:
        self._write_byte(servo_id, ADDR_SCS_LOCK, 0)
        self._write_byte(servo_id, ADDR_SCS_MODE, 1)
        self._write_byte(servo_id, ADDR_SCS_LOCK, 1)
        return "success"

    def write_wheel_speed(self, servo_id: int, speed: int) -> str:
        clamped = max(-MAX_SPEED, min(MAX_SPEED, int(speed)))
        value = abs(clamped) & 0x7FFF
        if clamped < 0:
            value |= 0x8000
        self._write_word(servo_id, ADDR_SCS_GOAL_SPEED, value)
        return "success"

    def sync_write_wheel_speeds(self, servo_speeds: Dict[int, int]) -> str:
        payload: List[int] = []
        for sid, speed in servo_speeds.items():
            clamped = max(-MAX_SPEED, min(MAX_SPEED, int(speed)))
            value = abs(clamped) & 0x7FFF
            if clamped < 0:
                value |= 0x8000
            payload.extend([int(sid) & 0xFF, _lo(value), _hi(value)])
        if not payload:
            return "success"
        params = [ADDR_SCS_GOAL_SPEED, 2, *payload]
        packet = self._packet(BROADCAST_ID, INST_SYNC_WRITE, params)
        self._send(packet)
        return "success"

