---
title: Installing RoboCrew
description: How to install and set up RoboCrew on your Raspberry Pi.
---

To install RoboCrew on your Raspberry Pi, follow these steps:

1. **Update System Packages** (if you haven't already):

   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Python** (if not already installed):

    ```bash
    sudo apt install -y python3-pip
    ```

3. **Set Up Python Environment** (optional but **HIGHLY** recommended):

   ```bash
   python3 -m venv robocrew-env
   source robocrew-env/bin/activate
   ```

4. **Install RoboCrew**:

   ```bash
   pip install robocrew
   ```

5. **Install Additional Dependencies**:
    For audio support (if using voice commands):

    ```bash
    sudo apt install portaudio19-dev
    ```
