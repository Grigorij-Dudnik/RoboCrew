#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

MODE=${MODE:-"0660"}
GROUP=${GROUP:-"dialout"}
SYMLINK_PREFIX=${SYMLINK_PREFIX:-"robocrew"}

serial_devices=()
declare -A serial_counts

# 1. Scan devices
for device in /dev/serial/by-path/*; do
  real_device=$(readlink -f "$device") || continue
  sysfs_path=$(udevadm info -q path -n "$real_device" || true)
  [[ -z "$sysfs_path" ]] && continue

  phys_path=$(basename "$(dirname "$(dirname "$sysfs_path")")")
  phys_path=${phys_path%%:*}

  props=$(udevadm info -q property -n "$real_device" || true)
  vendor_id=$(echo "$props" | awk -F= '/^ID_VENDOR_ID=/{print tolower($2); exit}')
  product_id=$(echo "$props" | awk -F= '/^ID_MODEL_ID=/{print tolower($2); exit}')
  serial_number=$(echo "$props" | awk -F= '/^ID_SERIAL_SHORT=/{print $2; exit}')

  # Store only essential data (kernel name, serial, vendor, product, phys path)
  serial_devices+=("$(basename "$real_device")|$serial_number|$vendor_id|$product_id|$phys_path")

  if [[ -n "$serial_number" ]]; then
    serial_counts[$serial_number]=$((${serial_counts[$serial_number]:-0} + 1))
  fi
done

# 2. Generate Rules
for entry in "${serial_devices[@]}"; do
  IFS='|' read -r kernel_device serial_number vendor_id product_id phys_path <<<"$entry"

  rule="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$vendor_id\", ATTRS{idProduct}==\"$product_id\""

  if [[ -n "$serial_number" ]]; then
    rule+=", ATTRS{serial}==\"$serial_number\""
    # Only add physical path if this serial number is a duplicate
    [[ ${serial_counts[$serial_number]:-0} -gt 1 ]] && rule+=", KERNELS==\"$phys_path\""
  else
    rule+=", KERNELS==\"$phys_path\""
  fi

  echo ""
  echo "$rule, MODE=\"$MODE\", GROUP=\"$GROUP\", SYMLINK+=\"${SYMLINK_PREFIX}-${kernel_device}\""
  echo ""
done