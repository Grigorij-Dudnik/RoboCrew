#!/usr/bin/env python3

import os
import subprocess
import sys
import time
from robocrew.scripts import robocrew_generate_udev_rules as base_rules


MODE = os.environ.get("MODE", getattr(base_rules, "MODE", "0660"))
GROUP = os.environ.get("GROUP", getattr(base_rules, "GROUP", "dialout"))

default_devices = ["camera_center", "camera_left", "camera_right", "arm_right", "arm_left"]


def capture_devices():
	devices = []
	serial_counts = {}
	camera_ids = set()
	base_rules.scan("/dev/v4l/by-path/*", "video4linux", devices, serial_counts, camera_ids)
	base_rules.scan("/dev/serial/by-path/*", "tty", devices, serial_counts, camera_ids)
	return devices


def device_key(dev):
	return (dev["subsystem"], dev["kernel"], dev["phys"], dev.get("serial"))


def wait_for_device(known):
	print("Waiting for newly connected device...")
	while True:
		for dev in capture_devices():
			key = device_key(dev)
			if key not in known:
				return dev, key
		time.sleep(1)


def build_rule(dev, alias, serial_counts):
	rule = (
		f'SUBSYSTEM=="{dev["subsystem"]}", '
		f'ATTRS{{idVendor}}=="{dev["vendor"]}", '
		f'ATTRS{{idProduct}}=="{dev["product"]}"'
	)
	if dev["subsystem"] == "video4linux":
		rule += ', ATTR{index}=="0"'
	serial = dev.get("serial")
	if serial and serial != "00000000":
		rule += f', ATTRS{{serial}}=="{serial}"'
		if serial_counts.get(serial, 0) > 1:
			rule += f', KERNELS=="{dev["phys"]}"'
	else:
		rule += f', KERNELS=="{dev["phys"]}"'
	rule += f', MODE=="{MODE}", GROUP=="{GROUP}", SYMLINK+="{alias}"'
	return rule


def ensure_root():
	if os.geteuid() == 0:
		return
	print("This script needs elevated privileges for saving udev rules, requesting sudo...")
	cmd = ["sudo", "-E", sys.executable, *sys.argv]
	os.execvp("sudo", cmd)


def main():
	input("Disconnect all RoboCrew devices, then press Enter to continue.")

	known = {device_key(dev) for dev in capture_devices()}
	assignments = []

	for alias in default_devices:
		resp = input(
			f"Connect USB for '{alias}' and press Enter (or 's' to skip): "
		).strip().lower()
		if resp == "s":
			continue
		dev, key = wait_for_device(known)
		assignments.append({"alias": alias, "device": dev})
		known.add(key)


	if not assignments:
		print("No devices registered, nothing to emit.")
		return

	serial_counts = {}
	for entry in assignments:
		serial = entry["device"].get("serial")
		if serial:
			serial_counts[serial] = serial_counts.get(serial, 0) + 1
	
	rules = [build_rule(entry["device"], entry["alias"], serial_counts) for entry in assignments]
	ensure_root()
	rules_path = "/etc/udev/rules.d/99-robocrew.rules"
	with open(rules_path, "w", encoding="ascii") as fh:
		fh.write("\n\n".join(rules) + "\n")
	print(f"Saved {len(rules)} rules to {rules_path}.")
	subprocess.run(["udevadm", "control", "--reload-rules"], check=False)
	subprocess.run(["udevadm", "trigger"], check=False)


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit(130)
