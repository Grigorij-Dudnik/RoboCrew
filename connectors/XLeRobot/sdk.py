import time
from typing import Dict, List, Optional

import serial  # type: ignore[import]
import serial.tools.list_ports  # type: ignore[import]

# Servo protocol constants ----------------------------------------------------

BROADCAST_ID = 0xFE

INST_WRITE = 3
INST_SYNC_WRITE = 0x83

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

# Control table addresses
ADDR_SCS_GOAL_SPEED = 46
ADDR_SCS_MODE = 33
ADDR_SCS_LOCK = 55

DEFAULT_BAUDRATE = 1_000_000
LATENCY_TIMER = 16

# Endianness flag like JS (STS/SMS=0, SCS=1). Most STS/SMS use 0.
SCS_END = 0

def SCS_LOBYTE(w: int) -> int:
    return (w & 0xFF) if SCS_END == 0 else ((w >> 8) & 0xFF)


def SCS_HIBYTE(w: int) -> int:
    return ((w >> 8) & 0xFF) if SCS_END == 0 else (w & 0xFF)


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

    def rx_packet(self, port: PortHandler):
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

    def tx_rx_packet(self, port: PortHandler, txpacket: List[int]):
        rxpacket: Optional[List[int]] = None
        error = 0
        result = self.tx_packet(port, txpacket)
        if result != COMM_SUCCESS:
            port.is_using = False
            return rxpacket, result, error

        if txpacket[PKT_ID] == BROADCAST_ID:
            port.is_using = False
            return rxpacket, result, error

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

    # Write helpers
    def write_tx_rx(self, port: PortHandler, scs_id: int, address: int, data: List[int]):
        if scs_id >= BROADCAST_ID:
            return COMM_NOT_AVAILABLE, 0
        txpacket = [0] * (len(data) + 7)
        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = len(data) + 3
        txpacket[PKT_INSTRUCTION] = INST_WRITE
        txpacket[PKT_PARAMETER0] = address
        for i, value in enumerate(data):
            txpacket[PKT_PARAMETER0 + 1 + i] = value & 0xFF
        rxpacket, result, error = self.tx_rx_packet(port, txpacket)
        return result, error

    def write1(self, port: PortHandler, scs_id: int, address: int, data: int):
        return self.write_tx_rx(port, scs_id, address, [data & 0xFF])

    def write2(self, port: PortHandler, scs_id: int, address: int, data: int):
        arr = [SCS_LOBYTE(data), SCS_HIBYTE(data)]
        return self.write_tx_rx(port, scs_id, address, arr)

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
    """Thin convenience wrapper for the handful of operations we need."""

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

    # ------------------------------------------------------------------
    # Basic write helpers
    # ------------------------------------------------------------------

    def _write_byte(self, servo_id: int, address: int, value: int):
        res, err = self.ph.write1(self.port, servo_id, address, value)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_byte failed: {self.ph.get_tx_rx_result(res)} err={err}")

    def _write_word(self, servo_id: int, address: int, value: int):
        res, err = self.ph.write2(self.port, servo_id, address, value)
        if res != COMM_SUCCESS:
            raise RuntimeError(f"write_word failed: {self.ph.get_tx_rx_result(res)} err={err}")

    # ------------------------------------------------------------------
    # Wheel helpers
    # ------------------------------------------------------------------

    def set_wheel_mode(self, servo_id: int) -> str:
        self._unlock(servo_id)
        try:
            self._write_byte(servo_id, ADDR_SCS_MODE, 1)
        finally:
            self._lock(servo_id)
        return "success"

    def write_wheel_speed(self, servo_id: int, speed: int) -> str:
        speed = max(-10000, min(10000, int(speed)))
        value = abs(speed) & 0x7FFF
        if speed < 0:
            value |= 0x8000
        self._write_word(servo_id, ADDR_SCS_GOAL_SPEED, value)
        return "success"

    def sync_write_wheel_speeds(self, servo_speeds: Dict[int, int]) -> str:
        if not servo_speeds:
            return "success"
        group = GroupSyncWrite(self.port, self.ph, ADDR_SCS_GOAL_SPEED, 2)
        added = False
        for sid, speed in servo_speeds.items():
            speed = max(-10000, min(10000, int(speed)))
            value = abs(speed) & 0x7FFF
            if speed < 0:
                value |= 0x8000
            added = group.add_param(int(sid), [SCS_LOBYTE(value), SCS_HIBYTE(value)]) or added
        if not added:
            return "success"
        result = group.tx_packet()
        if result != COMM_SUCCESS:
            raise RuntimeError(f"sync_write_wheel_speeds failed: {self.ph.get_tx_rx_result(result)}")
        return "success"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unlock(self, servo_id: int):
        self._write_byte(servo_id, ADDR_SCS_LOCK, 0)

    def _lock(self, servo_id: int):
        self._write_byte(servo_id, ADDR_SCS_LOCK, 1)
