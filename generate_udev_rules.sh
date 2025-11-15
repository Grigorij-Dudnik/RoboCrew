#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

MODE=${MODE:-"0660"}
GROUP=${GROUP:-"dialout"}
SYMLINK_PREFIX=${SYMLINK_PREFIX:-"robocrew"}

if ! command -v udevadm >/dev/null 2>&1; then
  echo "udevadm command not found; please install udev utilities." >&2
  exit 1
fi

serial_devices=()
declare -A serial_counts

dev_paths=(/dev/serial/by-path/*)
if [[ ${#dev_paths[@]} -eq 1 && ! -e ${dev_paths[0]} ]]; then
  dev_paths=()
fi

for device in "${dev_paths[@]}"; do
  real_device=$(readlink -f "$device") || continue
  sysfs_path=$(udevadm info -q path -n "$real_device" || true)
  [[ -z "$sysfs_path" ]] && continue

  phys_path=$(basename "$(dirname "$(dirname "$sysfs_path")")")
  phys_path=${phys_path%%:*}

  props=$(udevadm info -q property -n "$real_device" || true)

  vendor_id=$(echo "$props" | awk -F= '/^ID_VENDOR_ID=/{print tolower($2); exit}')
  product_id=$(echo "$props" | awk -F= '/^ID_MODEL_ID=/{print tolower($2); exit}')
  serial_number=$(echo "$props" | awk -F= '/^ID_SERIAL_SHORT=/{print $2; exit}')

  vendor_id=${vendor_id:-????}
  product_id=${product_id:-????}
  serial_number=${serial_number:-}

  device_id=$(basename "$device")
  kernel_device=$(basename "$real_device")

  serial_devices+=("$device_id|$kernel_device|$serial_number|$vendor_id|$product_id|$phys_path")

  if [[ -n "$serial_number" ]]; then
    current_count=${serial_counts[$serial_number]:-0}
    serial_counts[$serial_number]=$((current_count + 1))
  fi
done

if [[ ${#serial_devices[@]} -eq 0 ]]; then
  echo "# No /dev/serial/by-path devices detected on this system." >&2
  exit 0
fi

cat <<'HEADER'
# -------------------------------------------------------------
# Auto-generated udev rules (copy into /etc/udev/rules.d/*.rules)
# Matching priority: serial number, then physical USB path
# Customize MODE, GROUP, SYMLINK prefix via env vars before running:
#   MODE=0660 GROUP=dialout SYMLINK_PREFIX=robocrew ./generate_udev_rules.sh
# -------------------------------------------------------------
HEADER
echo

for entry in "${serial_devices[@]}"; do
  IFS='|' read -r device_id kernel_device serial_number vendor_id product_id phys_path <<<"$entry"

  comment="# $(printf '%-35s' "$device_id") -> $(printf '%-10s' "$kernel_device") (phys: $phys_path"
  if [[ -n "$serial_number" ]]; then
    comment+=" serial: $serial_number"
  else
    comment+=" serial: N/A"
  fi
  comment+=")"
  echo "$comment"

  rule="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$vendor_id\", ATTRS{idProduct}==\"$product_id\""

  if [[ -n "$serial_number" ]]; then
    rule+=" , ATTRS{serial}==\"$serial_number\""
    if [[ ${serial_counts[$serial_number]:-0} -gt 1 ]]; then
      rule+=" , KERNELS==\"$phys_path\""
    fi
  else
    rule+=" , KERNELS==\"$phys_path\""
  fi

  rule+=" , MODE=\"$MODE\", GROUP=\"$GROUP\", SYMLINK+=\"${SYMLINK_PREFIX}-${kernel_device}\""
  echo "$rule" | sed 's/,[[:space:]]*/, /g'
  echo
done
