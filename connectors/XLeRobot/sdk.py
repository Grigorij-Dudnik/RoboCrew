import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Iterable

import serial
import serial.tools.list_ports

# ===== Constants (mirroring feetech.js) =====
BROADCAST_ID = 0xFE
MAX_ID = 0xFC

# Instructions
INST_PING = 1
INST_READ = 2
INST_WRITE = 3
INST_REG_WRITE = 4
INST_ACTION = 5
INST_SYNC_WRITE = 0x83
INST_SYNC_READ = 0x82
INST_STATUS = 0x55

# Comm results
COMM_SUCCESS = 0
COMM_PORT_BUSY = -1
COMM_TX_FAIL = -2
COMM_RX_FAIL = -3
COMM_TX_ERROR = -4
COMM_RX_WAITING = -5
COMM_RX_TIMEOUT = -6
COMM_RX_CORRUPT = -7
COMM_NOT_AVAILABLE = -9

TXPACKET_MAX_LEN = 250
RXPACKET_MAX_LEN = 250

# Packet positions
PKT_HEADER0 = 0
PKT_HEADER1 = 1
PKT_ID = 2
PKT_LENGTH = 3
PKT_INSTRUCTION = 4
PKT_ERROR = 4
PKT_PARAMETER0 = 5

# Error bits
ERRBIT_VOLTAGE = 1
ERRBIT_ANGLE = 2
ERRBIT_OVERHEAT = 4
ERRBIT_OVERELE = 8
ERRBIT_OVERLOAD = 32

# Control table addresses (subset)
ADDR_SCS_TORQUE_ENABLE = 40
ADDR_SCS_GOAL_ACC = 41
ADDR_SCS_GOAL_POSITION = 42
ADDR_SCS_GOAL_SPEED = 46
ADDR_SCS_PRESENT_POSITION = 56

# Additional addresses used by high level
ADDR_SCS_MODE = 33
ADDR_SCS_LOCK = 55
ADDR_SCS_ID = 5
ADDR_SCS_BAUD_RATE = 6
ADDR_POS_CORRECTION = 31
ADDR_MIN_POS_LIMIT = 9
ADDR_MAX_POS_LIMIT = 11

DEFAULT_BAUDRATE = 1_000_000
LATENCY_TIMER = 16

# Endianness flag like JS (STS/SMS=0, SCS=1). Most STS/SMS use 0.
SCS_END = 0


def SCS_LOWORD(l: int) -> int:
    return l & 0xFFFF


def SCS_HIWORD(l: int) -> int:
    return (l >> 16) & 0xFFFF


def SCS_LOBYTE(w: int) -> int:
    return (w & 0xFF) if SCS_END == 0 else ((w >> 8) & 0xFF)


def SCS_HIBYTE(w: int) -> int:
    return ((w >> 8) & 0xFF) if SCS_END == 0 else (w & 0xFF)


def SCS_MAKEWORD(a: int, b: int) -> int:
    return ((a & 0xFF) | ((b & 0xFF) << 8)) if SCS_END == 0 else ((b & 0xFF) | ((a & 0xFF) << 8))


def SCS_MAKEDWORD(a: int, b: int) -> int:
    return (a & 0xFFFF) | ((b & 0xFFFF) << 16)


def SCS_TOHOST(a: int, b: int) -> int:
    return -(a & ~(1 << b)) if (a & (1 << b)) else a


class PortHandler:
    def __init__(self, port: Optional[str] = None, baudrate: int = DEFAULT_BAUDRATE):
        self.port_name = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.is_open = False
        self.is_using = False
        self.packet_start_time = 0.0
        self.packet_timeout = 0.0
        self.tx_time_per_byte = 0.0
        self.lock = threading.Lock()

    def set_port(self, port: str):
        self.port_name = port

    def set_baudrate(self, baudrate: int):
        self.baudrate = baudrate
        self.tx_time_per_byte = (1000.0 / self.baudrate) * 10.0

    def open_port(self) -> bool:
        if not self.port_name:
            return False
        try:
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=0, write_timeout=1)
            self.is_open = True
            self.tx_time_per_byte = (1000.0 / self.baudrate) * 10.0
            return True
        except Exception:
            self.ser = None
            self.is_open = False
            return False

    def close_port(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.is_open = False
            self.ser = None

    def clear_port(self):
        if self.ser:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

    def write_port(self, data: List[int]) -> int:
        if not (self.is_open and self.ser):
            return 0
        try:
            out = bytes(byte & 0xFF for byte in data)
            return self.ser.write(out)
        except Exception:
            return 0

    def read_port(self, length: int) -> List[int]:
        if not (self.is_open and self.ser):
            return []
        result: List[int] = []
        start = time.time()
        total_timeout = 0.5  # seconds
        while len(result) < length:
            if (time.time() - start) > total_timeout:
                break
            try:
                chunk = self.ser.read(length - len(result))
                if chunk:
                    result.extend(chunk)
                else:
                    time.sleep(0.01)
            except Exception:
                break
        return list(result)

    def set_packet_timeout(self, packet_length: int):
        self.packet_start_time = time.time()
        self.packet_timeout = (self.tx_time_per_byte * packet_length + LATENCY_TIMER * 2.0 + 2.0) / 1000.0

    def set_packet_timeout_millis(self, msec: float):
        self.packet_start_time = time.time()
        self.packet_timeout = msec / 1000.0

    def is_packet_timeout(self) -> bool:
        if (time.time() - self.packet_start_time) > self.packet_timeout:
            self.packet_timeout = 0.0
            return True
        return False


class PacketHandler:
    def __init__(self, protocol_end: int = 0):
        global SCS_END
        SCS_END = protocol_end

    def get_tx_rx_result(self, result: int) -> str:
        mapping = {
            COMM_SUCCESS: "Communication success",
            COMM_PORT_BUSY: "Port in use",
            COMM_TX_FAIL: "TX failed",
            COMM_RX_FAIL: "RX failed",
            COMM_TX_ERROR: "TX packet error",
            COMM_RX_WAITING: "RX waiting",
            COMM_RX_TIMEOUT: "RX timeout",
            COMM_RX_CORRUPT: "RX corrupt",
            COMM_NOT_AVAILABLE: "Not available",
        }
        return mapping.get(result, str(result))

    def tx_packet(self, port: PortHandler, txpacket: List[int]) -> int:
        checksum = 0
        total_len = txpacket[PKT_LENGTH] + 4
        if port.is_using:
            return COMM_PORT_BUSY
        port.is_using = True

        if total_len > TXPACKET_MAX_LEN:
            port.is_using = False
            return COMM_TX_ERROR

        txpacket[PKT_HEADER0] = 0xFF
        txpacket[PKT_HEADER1] = 0xFF

        for idx in range(2, total_len - 1):
            checksum += txpacket[idx]
        txpacket[total_len - 1] = (~checksum) & 0xFF

        port.clear_port()
        written = port.write_port(txpacket)
        if written != total_len:
            port.is_using = False
            return COMM_TX_FAIL
        return COMM_SUCCESS

    def rx_packet(self, port: PortHandler) -> Tuple[List[int], int]:
        rxpacket: List[int] = []
        result = COMM_RX_FAIL
        wait_length = 6

        while True:
            data = port.read_port(wait_length - len(rxpacket))
            rxpacket.extend(data)

            if len(rxpacket) >= wait_length:
                header_index = -1
                for i in range(0, len(rxpacket) - 1):
                    if rxpacket[i] == 0xFF and rxpacket[i + 1] == 0xFF:
                        header_index = i
                        break
                if header_index == 0:
                    if rxpacket[PKT_ID] > 0xFD or rxpacket[PKT_LENGTH] > RXPACKET_MAX_LEN:
                        rxpacket.pop(0)
                        continue
                    if wait_length != (rxpacket[PKT_LENGTH] + PKT_LENGTH + 1):
                        wait_length = rxpacket[PKT_LENGTH] + PKT_LENGTH + 1
                        continue
                    if len(rxpacket) < wait_length:
                        if port.is_packet_timeout():
                            result = COMM_RX_TIMEOUT if len(rxpacket) == 0 else COMM_RX_CORRUPT
                            break
                        continue
                    checksum = 0
                    for i in range(2, wait_length - 1):
                        checksum += rxpacket[i]
                    checksum = (~checksum) & 0xFF
                    result = COMM_SUCCESS if rxpacket[wait_length - 1] == checksum else COMM_RX_CORRUPT
                    break
                elif header_index > 0:
                    rxpacket = rxpacket[header_index:]
                    continue
            if port.is_packet_timeout():
                result = COMM_RX_TIMEOUT if len(rxpacket) == 0 else COMM_RX_CORRUPT
                break
        return rxpacket, result

    def tx_rx_packet(self, port: PortHandler, txpacket: List[int]) -> Tuple[Optional[List[int]], int, int]:
        rxpacket: Optional[List[int]] = None
        error = 0
        result = self.tx_packet(port, txpacket)
        if result != COMM_SUCCESS:
            port.is_using = False
            return rxpacket, result, error

        if txpacket[PKT_ID] == BROADCAST_ID:
            port.is_using = False
            return rxpacket, result, error

        if txpacket[PKT_INSTRUCTION] == INST_READ:
            read_len = txpacket[PKT_PARAMETER0 + 1]
            port.set_packet_timeout(read_len + 10)
        else:
            port.set_packet_timeout(10)

        port.clear_port()
        rxpacket, rx_res = self.rx_packet(port)

        if rx_res != COMM_SUCCESS or not rxpacket:
            port.is_using = False
            return rxpacket, rx_res, error

        if len(rxpacket) < 6 or rxpacket[PKT_ID] != txpacket[PKT_ID]:
            port.is_using = False
            return rxpacket, COMM_RX_CORRUPT, error

        error = rxpacket[PKT_ERROR]
        port.is_using = False
        return rxpacket, rx_res, error

    # Read helpers
    def read_tx_rx(self, port: PortHandler, scs_id: int, address: int, length: int) -> Tuple[List[int], int, int]:
        if scs_id >= BROADCAST_ID:
            return [], COMM_NOT_AVAILABLE, 0
        txpacket = [0] * 8
        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = 4
        txpacket[PKT_INSTRUCTION] = INST_READ
        txpacket[PKT_PARAMETER0] = address
        txpacket[PKT_PARAMETER0 + 1] = length
        rxpacket, result, error = self.tx_rx_packet(port, txpacket)
        if result != COMM_SUCCESS or not rxpacket or len(rxpacket) < PKT_PARAMETER0 + length:
            return [], result, error
        data = [rxpacket[PKT_PARAMETER0 + i] for i in range(length)]
        return data, result, error

    def read1(self, port: PortHandler, scs_id: int, address: int) -> Tuple[int, int, int]:
        data, res, err = self.read_tx_rx(port, scs_id, address, 1)
        return (data[0] if data else 0), res, err

    def read2(self, port: PortHandler, scs_id: int, address: int) -> Tuple[int, int, int]:
        data, res, err = self.read_tx_rx(port, scs_id, address, 2)
        val = SCS_MAKEWORD(data[0], data[1]) if len(data) >= 2 else 0
        return val, res, err

    # Write helpers
    def write_tx_rx(self, port: PortHandler, scs_id: int, address: int, length: int, data: List[int]) -> Tuple[int, int]:
        if scs_id >= BROADCAST_ID:
            return COMM_NOT_AVAILABLE, 0
        txpacket = [0] * (length + 7)
        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = length + 3
        txpacket[PKT_INSTRUCTION] = INST_WRITE
        txpacket[PKT_PARAMETER0] = address
        for i in range(length):
            txpacket[PKT_PARAMETER0 + 1 + i] = data[i] & 0xFF
        rxpacket, result, error = self.tx_rx_packet(port, txpacket)
        return result, error

    def write1(self, port: PortHandler, scs_id: int, address: int, data: int) -> Tuple[int, int]:
        return self.write_tx_rx(port, scs_id, address, 1, [data & 0xFF])

    def write2(self, port: PortHandler, scs_id: int, address: int, data: int) -> Tuple[int, int]:
        arr = [SCS_LOBYTE(data), SCS_HIBYTE(data)]
        return self.write_tx_rx(port, scs_id, address, 2, arr)

    # Sync ops (TX only)
    def sync_write_tx_only(self, port: PortHandler, start_address: int, data_len: int, param: List[int]) -> int:
        txpacket = [0] * (len(param) + 8)
        txpacket[PKT_ID] = BROADCAST_ID
        txpacket[PKT_LENGTH] = len(param) + 4
        txpacket[PKT_INSTRUCTION] = INST_SYNC_WRITE
        txpacket[PKT_PARAMETER0] = start_address
        txpacket[PKT_PARAMETER0 + 1] = data_len
        for i, b in enumerate(param):
            txpacket[PKT_PARAMETER0 + 2 + i] = b & 0xFF
        # build checksum and send
        res = self.tx_packet(port, txpacket)
        port.is_using = False
        return res


class GroupSyncWrite:
    def __init__(self, port: PortHandler, ph: PacketHandler, start_address: int, data_length: int):
        self.port = port
        self.ph = ph
        self.start_address = start_address
        self.data_length = data_length
        self.ids: List[int] = []
        self.data: Dict[int, List[int]] = {}

    def add_param(self, scs_id: int, data: List[int]) -> bool:
        if scs_id in self.ids:
            return False
        if len(data) != self.data_length:
            return False
        self.ids.append(scs_id)
        self.data[scs_id] = list(data)
        return True

    def clear_param(self):
        self.ids.clear()
        self.data.clear()

    def make_param(self) -> List[int]:
        param: List[int] = []
        for sid in self.ids:
            param.append(sid)
            param.extend(self.data[sid])
        return param

    def tx_packet(self) -> int:
        if not self.ids:
            return COMM_NOT_AVAILABLE
        param = self.make_param()
        return self.ph.sync_write_tx_only(self.port, self.start_address, self.data_length, param)


class ScsServoSDK:
    def __init__(self):
        self.port = PortHandler()
        self.ph = PacketHandler(0)

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE, protocol_end: int = 0) -> bool:
        self.port.set_port(port)
        self.port.set_baudrate(baudrate)
        self.ph = PacketHandler(protocol_end)
        return self.port.open_port()

    def disconnect(self):
        self.port.close_port()

    def read_position(self, servo_id: int) -> int:
        pos, res, err = self.ph.read2(self.port, servo_id, ADDR_SCS_PRESENT_POSITION)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_position failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return pos & 0xFFFF

    def write_position(self, servo_id: int, position: int) -> str:
        if position < 0 or position > 4095:
            raise ValueError("position must be 0..4095")
        res, err = self.ph.write2(self.port, servo_id, ADDR_SCS_GOAL_POSITION, int(position))
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_position failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return "success"

    def write_torque_enable(self, servo_id: int, enable: bool) -> str:
        res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_TORQUE_ENABLE, 1 if enable else 0)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_torque_enable failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return "success"

    def write_acceleration(self, servo_id: int, acc: int) -> str:
        acc = max(0, min(254, int(acc)))
        res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_GOAL_ACC, acc)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_acceleration failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return "success"

    def read_mode(self, servo_id: int) -> int:
        val, res, err = self.ph.read1(self.port, servo_id, ADDR_SCS_MODE)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_mode failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return val

    def set_wheel_mode(self, servo_id: int) -> str:
        self._unlock(servo_id)
        try:
            res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_MODE, 1)
            if res != COMM_SUCCESS:
                raise RuntimeError(f"set_wheel_mode failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    def set_position_mode(self, servo_id: int) -> str:
        self._unlock(servo_id)
        try:
            res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_MODE, 0)
            if res != COMM_SUCCESS:
                raise RuntimeError(f"set_position_mode failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    def write_wheel_speed(self, servo_id: int, speed: int) -> str:
        speed = max(-10000, min(10000, int(speed)))
        value = abs(speed) & 0x7FFF
        if speed < 0:
            value |= 0x8000
        res, err = self.ph.write2(self.port, servo_id, ADDR_SCS_GOAL_SPEED, value)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_wheel_speed failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return "success"

    def write_goal_speed(self, servo_id: int, speed: int) -> str:
        """Set goal speed for position mode (non-negative)."""
        speed = max(0, min(10000, int(speed)))
        value = speed & 0x7FFF  # ensure positive, bit15 clear
        res, err = self.ph.write2(self.port, servo_id, ADDR_SCS_GOAL_SPEED, value)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_goal_speed failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return "success"

    def read_pos_correction(self, servo_id: int) -> int:
        raw, res, err = self.ph.read2(self.port, servo_id, ADDR_POS_CORRECTION)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_pos_correction failed: {self.ph.get_tx_rx_result(res)} err={err}")
        magnitude = raw & 0x7FF
        direction = -1 if (raw & 0x800) else 1
        return direction * magnitude

    def write_pos_correction(self, servo_id: int, correction: int) -> str:
        if correction < -2047 or correction > 2047:
            raise ValueError("correction must be -2047..2047")
        self._unlock(servo_id)
        try:
            val = abs(int(correction)) & 0x7FF
            if correction < 0:
                val |= 0x800
            res, err = self.ph.write2(self.port, servo_id, ADDR_POS_CORRECTION, val)
            if res != COMM_SUCCESS:
                raise RuntimeError(f"write_pos_correction failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    def read_baud_index(self, servo_id: int) -> int:
        idx, res, err = self.ph.read1(self.port, servo_id, ADDR_SCS_BAUD_RATE)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_baud_index failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return idx

    def set_baud_index(self, servo_id: int, idx: int) -> str:
        if idx < 0 or idx > 7:
            raise ValueError("baud index must be 0..7")
        self._unlock(servo_id)
        try:
            res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_BAUD_RATE, idx)
            if res != COMM_SUCCESS:
                raise RuntimeError(f"set_baud_index failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    def set_servo_id(self, current_id: int, new_id: int) -> str:
        if not (1 <= current_id <= 252 and 1 <= new_id <= 252):
            raise ValueError("IDs must be 1..252")
        if current_id == new_id:
            return "success"
        self._unlock(current_id)
        try:
            res, err = self.ph.write1(self.port, current_id, ADDR_SCS_ID, new_id)
            if res != COMM_SUCCESS:
                raise RuntimeError(f"set_servo_id failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            # attempt to lock with new ID
            try:
                self._lock(new_id)
            except Exception:
                self._lock(current_id)
        return "success"

    # Min/Max limits
    def read_min_pos_limit(self, servo_id: int) -> int:
        val, res, err = self.ph.read2(self.port, servo_id, ADDR_MIN_POS_LIMIT)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_min_pos_limit failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return val

    def read_max_pos_limit(self, servo_id: int) -> int:
        val, res, err = self.ph.read2(self.port, servo_id, ADDR_MAX_POS_LIMIT)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"read_max_pos_limit failed: {self.ph.get_tx_rx_result(res)} err={err}")
        return val

    def write_min_pos_limit(self, servo_id: int, limit: int) -> str:
        if limit < 0 or limit > 4095:
            raise ValueError("limit must be 0..4095")
        self._unlock(servo_id)
        try:
            res, err = self.ph.write2(self.port, servo_id, ADDR_MIN_POS_LIMIT, int(limit))
            if res != COMM_SUCCESS:
                raise RuntimeError(f"write_min_pos_limit failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    def write_max_pos_limit(self, servo_id: int, limit: int) -> str:
        if limit < 0 or limit > 4095:
            raise ValueError("limit must be 0..4095")
        self._unlock(servo_id)
        try:
            res, err = self.ph.write2(self.port, servo_id, ADDR_MAX_POS_LIMIT, int(limit))
            if res != COMM_SUCCESS:
                raise RuntimeError(f"write_max_pos_limit failed: {self.ph.get_tx_rx_result(res)} err={err}")
        finally:
            self._lock(servo_id)
        return "success"

    # Group operations (basic wrappers)
    def sync_write_positions(self, servo_positions: Dict[int, int]) -> str:
        g = GroupSyncWrite(self.port, self.ph, ADDR_SCS_GOAL_POSITION, 2)
        added = False
        for sid, pos in servo_positions.items():
            if pos < 0 or pos > 4095:
                raise ValueError(f"position for {sid} must be 0..4095")
            data = [SCS_LOBYTE(pos), SCS_HIBYTE(pos)]
            added = g.add_param(int(sid), data) or added
        if not added:
            return "success"
        res = g.tx_packet()
        if res != COMM_SUCCESS:
            raise RuntimeError(f"sync_write_positions failed: {self.ph.get_tx_rx_result(res)}")
        return "success"

    def sync_write_wheel_speeds(self, servo_speeds: Dict[int, int]) -> str:
        g = GroupSyncWrite(self.port, self.ph, ADDR_SCS_GOAL_SPEED, 2)
        added = False
        for sid, speed in servo_speeds.items():
            speed = max(-10000, min(10000, int(speed)))
            value = abs(speed) & 0x7FFF
            if speed < 0:
                value |= 0x8000
            data = [SCS_LOBYTE(value), SCS_HIBYTE(value)]
            added = g.add_param(int(sid), data) or added
        if not added:
            return "success"
        res = g.tx_packet()
        if res != COMM_SUCCESS:
            raise RuntimeError(f"sync_write_wheel_speeds failed: {self.ph.get_tx_rx_result(res)}")
        return "success"

    # Internal helpers
    def _unlock(self, servo_id: int):
        res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_LOCK, 0)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"unlock failed: {self.ph.get_tx_rx_result(res)} err={err}")

    def _lock(self, servo_id: int):
        res, err = self.ph.write1(self.port, servo_id, ADDR_SCS_LOCK, 1)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"lock failed: {self.ph.get_tx_rx_result(res)} err={err}")
