#!/usr/bin/env python3
import subprocess
import sys
import argparse

def set_priority(wifi_name=None, priority=50):
    priority = int(sys.argv[1]) if len(sys.argv) > 1 else priority

    if wifi_name is None:
        active = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
            text=True,
        )

        wifi_name = next(
            (
                line.split(":", 1)[0]
                for line in active.splitlines()
                if line.endswith(":802-11-wireless")
            ),
            None,
        )
        if not wifi_name:
            raise SystemExit("No active WiFi connection found")

    subprocess.run(
        [
            "nmcli",
            "connection",
            "modify",
            wifi_name,
            "connection.autoconnect-priority",
            str(priority),
        ],
        check=True,
    )
    print(f"Set {wifi_name} autoconnect priority to {priority}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Set WiFi autoconnect priority for RoboCrew.")
    parser.add_argument('--priority', type=int, default=50, help="Priority value (default: 50)")
    parser.add_argument('--wifi-name', type=str, default=None, help="Name of the WiFi connection to modify (optional)")
    args = parser.parse_args()
    set_priority(wifi_name=args.wifi_name, priority=args.priority)
