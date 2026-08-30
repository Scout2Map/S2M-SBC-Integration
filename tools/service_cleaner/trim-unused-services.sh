#!/usr/bin/env bash
# Trim OS-level systemd services on the onboard Pi 5 (Ubuntu Server 24.04)
# that are unrelated to the ROS2 stack, so more CPU/RAM/IO headroom stays
# with SLAM/Nav2/event-engine/comm_relay.
#
# Safe by default: dry-run unless --apply is passed. Nothing is masked or
# removed, only `systemctl disable --now` (still installed, still startable
# by hand with `systemctl start <name>`).
#
# Usage:
#   ./trim-unused-services.sh                 # show what WOULD change, do nothing
#   ./trim-unused-services.sh --apply         # actually disable the SAFE tier + set s2m.local
#   ./trim-unused-services.sh --apply --with-conditional   # SAFE + CONDITIONAL tiers
#   ./trim-unused-services.sh --apply --with-gui           # + kill any desktop/display-manager
#   ./trim-unused-services.sh --restore       # re-enable everything this script has touched
#   ./trim-unused-services.sh --apply --no-hostname   # skip the s2m.local rename
#
# --with-gui is its own opt-in tier, separate from SAFE/CONDITIONAL: it also
# flips the default boot target (graphical.target -> multi-user.target), so
# next reboot the Pi comes up straight to a text console instead of a login
# screen. `s2m_slam_real.launch.py`'s `use_rviz` defaults to false and
# `ros-onboard.txt` never installs a desktop, so ROS itself never needed a
# GUI here - if a display manager IS present it's almost certainly baked
# into whichever OS image was flashed onto the SD card (e.g. "Ubuntu
# Desktop" instead of "Ubuntu Server"), not something the ROS stack asked
# for. Nothing happens if no display manager is installed - each unit below
# is skipped automatically when absent, same as every other tier.
#
# State is recorded in /var/lib/scout2map/trimmed-services.log so --restore
# can undo exactly what was disabled, not guess.
#
# avahi-daemon is kept ON on purpose (not in the SAFE tier below) so the
# robot stays reachable as s2m.local over mDNS - useful precisely because
# this is a field robot that hops between networks/DHCP leases rather than
# sitting on one fixed IP. --apply also renames the host to "s2m" so that
# advertised name is actually s2m.local, and makes sure avahi-daemon itself
# is enabled in case the base image shipped it off.

set -euo pipefail

STATE_DIR="/var/lib/scout2map"
STATE_FILE="${STATE_DIR}/trimmed-services.log"
TARGET_HOSTNAME="s2m"

APPLY=false
WITH_CONDITIONAL=false
WITH_GUI=false
RESTORE=false
SET_HOSTNAME=true

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --with-conditional) WITH_CONDITIONAL=true ;;
    --with-gui) WITH_GUI=true ;;
    --restore) RESTORE=true ;;
    --no-hostname) SET_HOSTNAME=false ;;
    -h|--help)
      sed -n '2,32p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 1
      ;;
  esac
done

# SAFE tier: no plausible use on a headless robot SBC with no display,
# no printer, no modem, no snap packages, and no onboard Bluetooth radio
# in use (BT chip is unused here - MCUs talk over USB CDC, not UART/BT).
# avahi-daemon is deliberately NOT here - see the note above, it's what
# makes s2m.local work.
SAFE_SERVICES=(
  cups.service
  cups-browsed.service
  ModemManager.service
  bluetooth.service
  hciuart.service
  triggerhappy.service
  snapd.service
  snapd.socket
  snapd.seeded.service
  packagekit.service
  switcheroo-control.service
  accounts-daemon.service
  multipathd.service
  multipathd.socket
)

# CONDITIONAL tier: turn these off only after you've confirmed the robot
# doesn't need them. Disabled separately because getting these wrong has
# real consequences (auto-reboot mid-mission, or losing the fallback path
# to fix a broken update over SSH).
CONDITIONAL_SERVICES=(
  # Stops apt from silently installing + rebooting while a mission is
  # running. Keep `apt-daily.timer` (index refresh) if you still want
  # manual `apt upgrade` to see current versions; this only kills the
  # unattended auto-apply + reboot path.
  unattended-upgrades.service
  apt-daily-upgrade.timer
  # Slows boot waiting for a network that comes up anyway; systemd-networkd
  # itself is untouched, only the "block boot until online" unit.
  NetworkManager-wait-online.service
  systemd-networkd-wait-online.service
)

# DESKTOP tier: display managers / desktop session brokers. Only relevant
# if the SD card image included a desktop (e.g. "Ubuntu Desktop" rather
# than "Ubuntu Server"). Covers the common ones across Ubuntu/Raspberry Pi
# OS images; whichever aren't installed are silently skipped.
DESKTOP_SERVICES=(
  gdm3.service
  gdm.service
  lightdm.service
  sddm.service
  lxdm.service
  xdm.service
  wdm.service
)

# NEVER touch these - required for ROS2/DDS, SSH access, serial/USB (MCU
# bridges + LiDAR), WiFi itself, or the s2m.local mDNS name:
#   ssh.service, systemd-networkd.service, wpa_supplicant.service,
#   systemd-udevd.service, polkit.service, systemd-timesyncd.service,
#   avahi-daemon.service, avahi-daemon.socket,
#   NetworkManager.service (if that's what actually brings up WiFi here)

log() { echo "[trim-services] $*"; }

do_set_hostname() {
  local current
  current=$(hostnamectl hostname 2>/dev/null || hostname)

  log "making sure avahi-daemon is enabled (needed for ${TARGET_HOSTNAME}.local)"
  sudo systemctl enable --now avahi-daemon.service avahi-daemon.socket 2>/dev/null \
    || log "  (avahi-daemon not installed - install it first: sudo apt install avahi-daemon)"

  if [[ "$current" == "$TARGET_HOSTNAME" ]]; then
    log "hostname already ${TARGET_HOSTNAME}, ${TARGET_HOSTNAME}.local should already resolve"
    return
  fi

  log "renaming host ${current} -> ${TARGET_HOSTNAME} (so it advertises as ${TARGET_HOSTNAME}.local)"
  sudo hostnamectl set-hostname "$TARGET_HOSTNAME"

  # keep /etc/hosts' 127.0.1.1 line (Debian/Ubuntu convention) in sync so
  # anything reading it locally sees the new name too
  if grep -q '^127\.0\.1\.1[[:space:]]' /etc/hosts 2>/dev/null; then
    sudo sed -i "s/^127\.0\.1\.1[[:space:]].*/127.0.1.1\t${TARGET_HOSTNAME}/" /etc/hosts
  else
    echo -e "127.0.1.1\t${TARGET_HOSTNAME}" | sudo tee -a /etc/hosts >/dev/null
  fi

  log "old hostname was '${current}' - if that's what you SSH in with from other scripts/bookmarks, update those too"
}

is_active_unit() {
  systemctl list-unit-files "$1" --no-legend 2>/dev/null | grep -q "$1"
}

do_set_boot_target() {
  local current
  current=$(systemctl get-default 2>/dev/null || echo "unknown")
  if [[ "$current" != "graphical.target" ]]; then
    log "[GUI] boot target is already '${current}', not graphical - leaving as is"
    return
  fi
  log "[GUI] switching default boot target: graphical.target -> multi-user.target"
  log "[GUI]   (next reboot comes up to a text console, no login screen)"
  sudo systemctl set-default multi-user.target
  sudo mkdir -p "$STATE_DIR"
  echo "graphical.target" | sudo tee "${STATE_DIR}/previous-boot-target" >/dev/null
}

do_restore() {
  local boot_target_file="${STATE_DIR}/previous-boot-target"
  if [[ -f "$boot_target_file" ]]; then
    local prev
    prev=$(cat "$boot_target_file")
    log "restoring boot target: $(systemctl get-default) -> ${prev}"
    sudo systemctl set-default "$prev"
    sudo rm -f "$boot_target_file"
  fi
  if [[ ! -f "$STATE_FILE" ]]; then
    log "no service state file at $STATE_FILE - nothing else to restore"
    exit 0
  fi
  while read -r unit; do
    [[ -z "$unit" ]] && continue
    log "re-enabling $unit"
    sudo systemctl enable --now "$unit" || log "  (failed, check manually: $unit)"
  done < "$STATE_FILE"
  log "restore attempted for all units in $STATE_FILE. Leaving the log in place;"
  log "delete it yourself once you've confirmed the restore looks right."
}

do_pass() {
  local label="$1"; shift
  local units=("$@")
  local touched=0
  for unit in "${units[@]}"; do
    if ! is_active_unit "$unit"; then
      continue # not installed on this system, skip silently
    fi
    local state
    state=$(systemctl is-enabled "$unit" 2>/dev/null || echo "unknown")
    if [[ "$state" == "disabled" || "$state" == "masked" || "$state" == "not-found" ]]; then
      continue # already off
    fi
    touched=$((touched + 1))
    if $APPLY; then
      log "[$label] disabling $unit (was: $state)"
      sudo systemctl disable --now "$unit"
      mkdir -p "$STATE_DIR" 2>/dev/null || sudo mkdir -p "$STATE_DIR"
      echo "$unit" | sudo tee -a "$STATE_FILE" >/dev/null
    else
      log "[$label] WOULD disable $unit (currently: $state)"
    fi
  done
  if [[ $touched -eq 0 ]]; then
    log "[$label] nothing to do (already trimmed, or not installed)"
  fi
}

if $RESTORE; then
  do_restore
  exit 0
fi

if ! $APPLY; then
  log "DRY RUN - nothing will change. Re-run with --apply to actually disable."
fi

do_pass "SAFE" "${SAFE_SERVICES[@]}"

if $WITH_CONDITIONAL; then
  do_pass "CONDITIONAL" "${CONDITIONAL_SERVICES[@]}"
else
  log "skipping CONDITIONAL tier (pass --with-conditional to include it after you've read the script comments)"
fi

if $WITH_GUI; then
  do_pass "GUI" "${DESKTOP_SERVICES[@]}"
  if $APPLY; then
    do_set_boot_target
  else
    log "[GUI] (dry run - boot target switch to multi-user.target not shown here, only on --apply)"
  fi
else
  log "skipping GUI tier (pass --with-gui to also stop any display manager / desktop session, if one is installed)"
fi

if $APPLY && $SET_HOSTNAME; then
  do_set_hostname
elif ! $SET_HOSTNAME; then
  log "skipping hostname rename (--no-hostname passed)"
fi

if $APPLY; then
  log "done. Check headroom with: free -h && systemctl list-units --state=running | wc -l"
  $SET_HOSTNAME && log "try from another machine on the same network: ssh <user>@${TARGET_HOSTNAME}.local"
  log "undo service changes anytime with: $0 --restore (hostname rename is not tracked by --restore)"
fi
