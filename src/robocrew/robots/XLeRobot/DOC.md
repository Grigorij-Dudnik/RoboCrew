
# udev rules setup

Goal: expose the XLeRobot serial device to non-root users with a stable name (e.g. `/dev/robocrew`).

---

## Fast path — use the generator script

1. **Scan devices**
	```
	MODE=0660 GROUP=dialout SYMLINK_PREFIX=robocrew ./generate_udev_rules.sh
	```
	- Reads `/dev/serial/by-path/*`, prefers serial numbers, falls back to USB physical path to keep rules unique.
	- Adjust `MODE`, `GROUP`, or the symlink prefix via env vars as shown.
    ```
    # platform-xhci-hcd.0-usb-0:1.1:1.0   -> ttyACM2    (phys: 1-1.1 serial: 5A7A055068)
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d3" , ATTRS{serial}=="5A7A055068" , MODE="0660", GROUP="dialout", SYMLINK+="robocrew-ttyACM2"
    ```
    - `SYMLINK+="robocrew-ttyACM2"` creates a symlink `/dev/robocrew-ttyACM2` pointing to the actual device. **You can change `robocrew-ttyACM2` to any name you prefer.**

2. **Copy a block** into `/etc/udev/rules.d/99-robocrew.rules` (run as root). Tweak only the symlink name if desired.

    You can create or edit the file with:
    ```
    sudo nano /etc/udev/rules.d/99-robocrew.rules
    ```

3. **Reload + trigger**
	```
	sudo udevadm control --reload-rules
	sudo udevadm trigger
	```

4. **Add yourself to the device group** (skip if already a member):
	```
	sudo usermod -a -G dialout $USER
	newgrp dialout
	```

5. **Re-plug + verify**
	```
	ls -l /dev/robocrew
	udevadm info -q all -n /dev/robocrew
	```

Security tip: stay with `MODE=0660` plus the right group; only loosen to `0666` for temporary debugging.

---

## Troubleshooting & manual fallback

- **Find IDs**: `sudo lsusb` to grab vendor/product; `udevadm info -a -n /dev/ttyACM0` to inspect attributes (including serial).
- **Craft your own rule** if the script can’t see the device:
  ```
  SUBSYSTEM=="tty", ATTRS{idVendor}=="vvvv", ATTRS{idProduct}=="pppp", \
	 ATTRS{serial}=="12345678", MODE="0660", GROUP="dialout", SYMLINK+="robocrew"
  ```
  Drop `ATTRS{serial}` only if the hardware has no unique serial; in that case constrain by USB path instead.
- **Reload, re-plug, verify** as in the fast path. Use `udevadm monitor --udev` to watch matches, and remember higher-numbered rule files override lower ones (`99-robocrew.rules` wins late).
