#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from robocrew.scripts import robocrew_generate_udev_rules as base_rules
from robocrew.scripts.robocrew_set_wifi_priority import set_priority as set_wifi_priority
import argparse


MODE = os.environ.get("MODE", getattr(base_rules, "MODE", "0660"))
GROUP = os.environ.get("GROUP", getattr(base_rules, "GROUP", "dialout"))

default_devices = ["camera_center", "camera_right", "camera_left", "arm_right", "arm_left", "mic_main"]

def capture_devices():
	devices = []
	serial_counts = {}
	camera_ids = set()
	base_rules.scan("/dev/v4l/by-path/*", "video4linux", devices, serial_counts, camera_ids)
	base_rules.scan("/dev/serial/by-path/*", "tty", devices, serial_counts, camera_ids)
	base_rules.scan("/dev/snd/controlC*", "sound", devices, serial_counts, camera_ids)
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


def build_rule(dev, alias):
	rule = f'SUBSYSTEM=="{dev["subsystem"]}"'
	if dev["subsystem"] == "video4linux":
		rule += ', ATTR{index}=="0"'
	id_path = dev.get("id_path") or dev["phys"]
	rule += f', ENV{{ID_PATH}}=="{id_path}"'
	serial = dev.get("serial")
	if serial and serial != "00000000":
		if dev.get("serial_is_short"):
			rule += f', ATTRS{{serial}}=="{serial}"'
		else:
			rule += f', ENV{{ID_SERIAL}}=="{serial}"'
	rule += f', MODE="{MODE}", GROUP="{GROUP}", SYMLINK+="{alias}"'
	return rule


def ensure_root():
	if os.geteuid() == 0:
		return
	print("This script needs elevated privileges for saving udev rules, requesting sudo...")
	cmd = ["sudo", "-E", sys.executable, *sys.argv]
	os.execvp("sudo", cmd)


def main():
	parser = argparse.ArgumentParser(description="Setup udev rules for RoboCrew devices.")
	parser.add_argument('--no-wifi-priority', action='store_true', help="Do not set WiFi priority for RoboCrew.")
	args = parser.parse_args()


	ensure_root()
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

	while True:
		resp = input("All default devices assigned. Type 'a' to add more, or press Enter to finish: ").strip().lower()
		if resp != "a":
			break
		else:
			alias = input("Enter alias for the new device: ").strip()
			if not alias:
				print("Alias cannot be empty. Skipping.")
				continue
			dev, key = wait_for_device(known)
			assignments.append({"alias": alias, "device": dev})
			known.add(key)

	if not assignments:
		print("No devices registered, nothing to emit.")
		return

	rules = [build_rule(entry["device"], entry["alias"]) for entry in assignments]
	rules_path = "/etc/udev/rules.d/99-robocrew.rules"
	with open(rules_path, "w", encoding="ascii") as fh:
		fh.write("\n\n".join(rules) + "\n")
	print(f"Saved {len(rules)} rules to {rules_path}.")
	subprocess.run(["udevadm", "control", "--reload-rules"], check=False)
	subprocess.run(["udevadm", "trigger"], check=False)
	if args.no_wifi_priority:
		print("Skipping WiFi priority setup.")
	else:
		try:
			set_wifi_priority()
		except Exception as e:
			print(f"(Warning) Failed to set WiFi priority. Please run 'robocrew_set_wifi_priority.py' manually to set it. \
			It will fix wifi auto-connect issues.\n Error: {e}")

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit(130)
