
# Wheel steering helpers using the wheel section of dual_mapper_config.json.
# Now wrapped in XLeRobotWheels class for easier usage.


from typing import Dict, List
from sdk import ScsServoSDK, DEFAULT_BAUDRATE


def _role_allows(role: str, action: str) -> bool:
    role = (role or "both").lower()
    if action in ("Up", "Down"):
        return role in ("drive", "both")
    if action in ("Left", "Right"):
        return role in ("steer", "both")
    return False


def _normalize_wheel_cfg(wheel_cfg: Dict) -> Dict:
    """Fill missing pieces with safe defaults; returns the same dict for chaining."""
    if not isinstance(wheel_cfg, dict):
        raise ValueError("wheel_cfg must be a dict with keys: speed, wheels")
    wheel_cfg.setdefault("speed", 600)
    wheel_cfg.setdefault("wheels", [])
    for w in wheel_cfg["wheels"]:
        w.setdefault("id", 0)
        w.setdefault("role", "both")
        cal = w.setdefault("calibration", {})
        cal.setdefault("Up", 0)
        cal.setdefault("Down", 0)
        cal.setdefault("Left", 0)
        cal.setdefault("Right", 0)
    return wheel_cfg


def _compute_map(wheel_cfg: Dict, action: str) -> Dict[int, int]:
    cfg = _normalize_wheel_cfg(wheel_cfg)
    speed = int(cfg.get("speed", 600))
    mp: Dict[int, int] = {}
    for w in cfg.get("wheels", []):
        wid = int(w.get("id", 0))
        if wid <= 0:
            continue
        if not _role_allows(str(w.get("role", "both")), action):
            mp[wid] = 0
            continue
        cal = w.get("calibration", {})
        sign = int(cal.get(action, 0))
        mp[wid] = sign * speed
    return mp



class XLeRobotWheels:
    def __init__(self, sdk: ScsServoSDK, wheel_cfg: Dict):
        self.sdk = sdk
        self.wheel_cfg = wheel_cfg

    @staticmethod
    def _send(sdk: ScsServoSDK, mp: Dict[int, int]) -> Dict[int, int]:
        if mp:
            sdk.sync_write_wheel_speeds(mp)
        return mp

    def go_forward(self) -> Dict[int, int]:
        """Drive forward using calibration['Up'] for drive/both wheels."""
        return self._send(self.sdk, _compute_map(self.wheel_cfg, "Up"))

    def go_backward(self) -> Dict[int, int]:
        """Drive backward using calibration['Down'] for drive/both wheels."""
        return self._send(self.sdk, _compute_map(self.wheel_cfg, "Down"))

    def turn_left(self) -> Dict[int, int]:
        """Turn left using calibration['Left'] for steer/both wheels."""
        return self._send(self.sdk, _compute_map(self.wheel_cfg, "Left"))

    def turn_right(self) -> Dict[int, int]:
        """Turn right using calibration['Right'] for steer/both wheels."""
        return self._send(self.sdk, _compute_map(self.wheel_cfg, "Right"))

    def stop_wheels(self) -> Dict[int, int]:
        """Stop all wheels listed in config by writing 0 speed."""
        cfg = _normalize_wheel_cfg(self.wheel_cfg)
        mp: Dict[int, int] = {int(w.get("id", 0)): 0 for w in cfg.get("wheels", []) if int(w.get("id", 0)) > 0}
        if mp:
            self.sdk.sync_write_wheel_speeds(mp)
        return mp

    def apply_wheel_modes(self) -> List[int]:
        """Set wheel mode on all wheel IDs in config. Returns the list of IDs applied."""
        cfg = _normalize_wheel_cfg(self.wheel_cfg)
        ids: List[int] = []
        for w in cfg.get("wheels", []):
            wid = int(w.get("id", 0))
            if wid <= 0:
                continue
            self.sdk.set_wheel_mode(wid)
            ids.append(wid)
        return ids

    @staticmethod
    def connect_serial(port: str, baudrate: int = DEFAULT_BAUDRATE, protocol_end: int = 0) -> ScsServoSDK:
        """Create and connect an ScsServoSDK instance."""
        sdk = ScsServoSDK()
        if not sdk.connect(port, baudrate, protocol_end):
            raise RuntimeError(f"Failed to open serial port {port} @ {baudrate}")
        return sdk


