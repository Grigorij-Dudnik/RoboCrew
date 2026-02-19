---
title: Flashing Raspberry and plugin
description: How to flash your Raspberry Pi and plug-in robot arms and cameras.
---

##

### 1. Flashing Raspberry Pi OS

1. **Download Tools**: Visit the [official Raspberry Pi website](https://www.raspberrypi.org/software/) to download the **Raspberry Pi Imager**.
2. **Select OS**: Open the Imager and choose **Raspberry Pi OS with desktop**.
3. **Configure Settings**: Click the settings icon to pre-configure your **hostname** (e.g., `XLerobot.local`), **username/password**, and **WiFi credentials**.
4. **Write to SD**: Insert a microSD card (32GB+ recommended) into your computer and click **"Write"** to flash the image.

### 2. Connecting Robot Arms and Cameras

After flashing and booting your Raspberry Pi, you can connect your robot arms and cameras:

It is important to connect the robot arms and cameras to the **correct USB** ports. Often it happens that USB Hub will **bottleneck** the bandwidth of the cameras, so it is recommended to connect the **cameras directly** to the Raspberry Pi's USB ports and use a powered USB hub for the robot arms, and another sensors if you have them.

### 3. Remote Access Setup (Optional but Recommended)

To control the robot without a dedicated monitor:

1. **Enable VNC**: Run `sudo raspi-config` in the terminal, go to **Interface Options**, and enable **VNC**.
2. **Connect from PC**: Install **RealVNC Viewer** on your laptop and connect using your pre-configured hostname (e.g., `XLerobot.local`).
3. **SSH Access**: You can also SSH into your Pi using `ssh pi@XLerobot.local` (replace `pi` with your configured username if you have changed it).
4. **SSHFS Access**: For file transfers, use `sshfs pi@XLerobot.local: /mnt/robocrew` (you can replace `/mnt/robocrew` with any **empty directory** on your local machine).
   * Linux (Debian/Ubuntu): Install `sshfs` via `sudo apt install sshfs`.
   * MacOS: Install `sshfs` via Homebrew with `brew install sshfs`.
   * Windows: in PowerShell run `winget install SSHFS-Win.SSHFS-Win`.

### 4. Software Preparation

Once hardware is connected, ensure your Pi is updated and has essential tools:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip git curl wget

```
