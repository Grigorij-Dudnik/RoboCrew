---
title: May your ports be ever named the same
description: How to set up udev rules for your robot arms and cameras to ensure consistent device naming on your Raspberry Pi.
---

To ensure that your robot arms and cameras are consistently recognized on your Raspberry Pi, you need to set up udev rules. This will allow you to have fixed device names (e.g., `/dev/robot_arm` and `/dev/robot_camera`) regardless of the order in which they are connected.

## 1. Automatic Setup (Recommended)

The easiest way to configure your robot is to use the built-in interactive script. This script guides you through connecting each component one by one to identify them.

### How to run:

1. **Open a terminal** and run the setup command:

```bash
robocrew-setup-usb-modules

```

2. **Follow the prompts**:

   * Disconnect all RoboCrew USB devices when asked.
   * Connect the USB for each specific alias (e.g., `camera_center`, `arm_right`) one at a time and press Enter.
   * The script will detect the new device, capture its unique ID and serial number, and map it to the correct name.

3. **Apply Rules**: The script automatically saves the rules to `/etc/udev/rules.d/99-robocrew.rules` and reloads the system configuration.

## 2. Manual Identification

If you need to check how your devices are currently mapped, you can use standard Linux commands:

* **Check Arm/Serial Symlinks**:
```bash
ls -l /dev/arm*

```


*Example output:* `lrwxrwxrwx 1 root root 7 Dec 2 11:40 /dev/arm_right -> ttyACM2`.
* **Check Camera Symlinks**:
```bash
ls -l /dev/cam*

```


*Example output:* `lrwxrwxrwx 1 root root 6 Dec 2 11:40 /dev/camera_center -> video0`.

## 3. How the Rules Work

The system generates rules based on the device's **Vendor ID**, **Product ID**, and **Serial Number**.

* **Standard Mapping**: If a device has a unique serial number, it is used for identification.
* **Physical Path Mapping**: If multiple identical devices (same Vendor/Product ID) lack unique serial numbers, the script uses their **physical USB port path** to distinguish between them.
* **Camera Indexing**: For video devices, the rules specifically target `index 0` to ensure they capture the primary video stream rather than metadata streams.

## 4. Default Assignments

The project typically looks for the following default symlinks during setup:

* `camera_center`, `camera_right`, `camera_left`
* `arm_right`, `arm_left`

By using these persistent names in your Python scripts (e.g., `RobotCamera("/dev/camera_center")`), your robot becomes hardware-agnostic regarding which physical USB port is used.