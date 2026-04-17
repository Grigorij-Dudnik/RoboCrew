"""Interactive hardware script to test saving and recalling XLeRobot arm positions.

Usage examples:
  python examples/5_xlerobot_test_save_recall_positions.py \
      --arms both

  python examples/5_xlerobot_test_save_recall_positions.py \
      --arms right \
      --position-name my_right_arm_pose
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Dict

from robocrew.robots.XLeRobot.servo_controls import ServoControler


RIGHT_ARM_USB = "/dev/arm_right"
LEFT_ARM_USB = "/dev/arm_left"


def _assert_close(actual: Dict[str, float], expected: Dict[str, float], label: str) -> None:
    for name, exp_value in expected.items():
        act_value = float(actual.get(name, 0.0))
        if abs(act_value - float(exp_value)) > 1e-6:
            raise AssertionError(
                f"{label} mismatch for '{name}': expected {exp_value}, got {act_value}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test save/read arm position functionality on XLeRobot hardware."
    )
    parser.add_argument(
        "--arms",
        choices=["left", "right", "both"],
        default="both",
        help="Which arm(s) to test.",
    )
    parser.add_argument(
        "--position-name",
        default="position_save_recall_test",
        help="Position file name (stored under ~/.cache/robocrew/positions).",
    )
    parser.add_argument("--pause", type=float, default=1.0, help="Pause after recall in seconds.")
    args = parser.parse_args()

    right_usb = RIGHT_ARM_USB if args.arms in ("right", "both") else None
    left_usb = LEFT_ARM_USB if args.arms in ("left", "both") else None

    servo = ServoControler(
        right_arm_wheel_usb=right_usb,
        left_arm_head_usb=left_usb,
    )

    try:
        if args.arms == "right":
            joints = list(servo._arm_positions_right.keys())
        elif args.arms == "left":
            joints = list(servo._arm_positions_left.keys())
        else:
            # Use the common key set for both sides.
            joints = sorted(set(servo._arm_positions_left.keys()) | set(servo._arm_positions_right.keys()))

        if not joints:
            raise RuntimeError("No arm joints discovered from controller maps.")

        print("[1/4] Releasing arm torque for manual positioning...")
        servo.disable_torque("arms")
        input("Manually set the arm(s) to a target pose, then press Enter to save... ")
        # servo.enable_torque("arms")
        servo.read_arm_present_position(arm_side=args.arms)

        print("[2/4] Saving pose...")
        save_path = servo.save_arm_position(args.position_name, arm_side=args.arms)
        print(f"Saved file: {save_path}")

        input("[3/4] Move the arm(s) away from that pose, then press Enter to recall the saved pose... ")

        print("[4/4] Recalling saved pose...")
        servo.set_saved_position(args.position_name, arm_side=args.arms)
        time.sleep(args.pause)

        print("Validating recalled pose...")
        saved_json = json.loads(open(save_path, "r", encoding="utf-8").read())
        saved_positions = saved_json["positions"] if "positions" in saved_json else saved_json

        if args.arms == "right":
            _assert_close(servo._arm_positions_right, saved_positions, "right arm")
        elif args.arms == "left":
            _assert_close(servo._arm_positions_left, saved_positions, "left arm")
        else:
            _assert_close(servo._arm_positions_right, saved_positions["right"], "right arm")
            _assert_close(servo._arm_positions_left, saved_positions["left"], "left arm")

        print("PASS: save + recall behavior looks correct.")

    finally:
        servo.disconnect()


if __name__ == "__main__":
    main()
