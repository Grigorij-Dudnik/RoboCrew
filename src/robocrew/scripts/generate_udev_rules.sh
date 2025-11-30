#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

MODE=${MODE:-"0660"}
GROUP=${GROUP:-"dialout"}
SYMLINK_PREFIX=${SYMLINK_PREFIX:-"robocrew"}

# Arrays to hold data
devices=()
declare -A serial_counts
declare -A camera_ids  # Used to ignore serial ports that belong to cameras

# --- FUNCTION: SCAN DEVICES ---
scan_devices() {
  local search_path="$1"
  local subsystem="$2"
  
  for device in $search_path; do
    real_device=$(readlink -f "$device") || continue
    sysfs_path=$(udevadm info -q path -n "$real_device" || true)
    [[ -z "$sysfs_path" ]] && continue

    # --- FILTER 1: Internal System Devices ---
    # Get properties early. If Vendor ID is empty, it's an internal SoC device (SKIP IT)
    props=$(udevadm info -q property -n "$real_device" || true)
    vendor_id=$(echo "$props" | awk -F= '/^ID_VENDOR_ID=/{print tolower($2); exit}')
    product_id=$(echo "$props" | awk -F= '/^ID_MODEL_ID=/{print tolower($2); exit}')
    
    if [[ -z "$vendor_id" ]]; then
        continue 
    fi

    # --- FILTER 2: Camera Index Check ---
    if [[ "$subsystem" == "video4linux" ]]; then
      # Record this ID as a camera so we can blacklist its serial port later
      camera_ids["${vendor_id}:${product_id}"]=1

      # Check index (must be 0 for video stream)
      if [[ -f "/sys/class/video4linux/$(basename "$real_device")/index" ]]; then
         idx=$(cat "/sys/class/video4linux/$(basename "$real_device")/index")
         [[ "$idx" != "0" ]] && continue
      fi
    fi

    # --- FILTER 3: Ghost Serial Ports ---
    if [[ "$subsystem" == "tty" ]]; then
        # If this serial device matches a known camera ID, skip it
        if [[ -n "${camera_ids["${vendor_id}:${product_id}"]:-}" ]]; then
            continue
        fi
    fi

    # Extract other attributes
    phys_path=$(basename "$(dirname "$(dirname "$sysfs_path")")")
    phys_path=${phys_path%%:*}
    serial_number=$(echo "$props" | awk -F= '/^ID_SERIAL_SHORT=/{print $2; exit}')
    
    # Fallback for cameras that use ID_SERIAL
    if [[ -z "$serial_number" ]]; then
        serial_number=$(echo "$props" | awk -F= '/^ID_SERIAL=/{print $2; exit}')
    fi

    # Store data
    devices+=("$(basename "$real_device")|$serial_number|$vendor_id|$product_id|$phys_path|$subsystem")

    if [[ -n "$serial_number" ]]; then
      serial_counts[$serial_number]=$((${serial_counts[$serial_number]:-0} + 1))
    fi
  done
}

# 1. SCAN CAMERAS FIRST 
# (We do this first to populate 'camera_ids' so we can block them in the serial scan)
scan_devices "/dev/v4l/by-path/*" "video4linux"

# 2. SCAN SERIAL DEVICES SECOND
scan_devices "/dev/serial/by-path/*" "tty"

# 3. GENERATE RULES
for entry in "${devices[@]}"; do
  IFS='|' read -r kernel_device serial_number vendor_id product_id phys_path subsystem <<<"$entry"

  rule="SUBSYSTEM==\"$subsystem\", ATTRS{idVendor}==\"$vendor_id\", ATTRS{idProduct}==\"$product_id\""

  # Add Index Check for Cameras
  if [[ "$subsystem" == "video4linux" ]]; then
    rule+=", ATTR{index}==\"0\""
    link_name="${SYMLINK_PREFIX}-${kernel_device}" 
  else
    link_name="${SYMLINK_PREFIX}-${kernel_device}"
  fi

  # Handle Serial Numbers and Physical Paths
  if [[ -n "$serial_number" && "$serial_number" != "00000000" ]]; then
    rule+=", ATTRS{serial}==\"$serial_number\""
    [[ ${serial_counts[$serial_number]:-0} -gt 1 ]] && rule+=", KERNELS==\"$phys_path\""
  else
    rule+=", KERNELS==\"$phys_path\""
  fi

  echo ""
  echo "$rule, MODE=\"$MODE\", GROUP=\"$GROUP\", SYMLINK+=\"${link_name}\""
  echo ""
done