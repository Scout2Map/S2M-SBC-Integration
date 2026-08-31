"""Pure safety policy used by the return-home ROS node."""

from dataclasses import dataclass
from enum import Enum


class Decision(Enum):
    NONE = 'none'
    RETURN_HOME = 'return_home'
    SAFE_STOP = 'safe_stop'


@dataclass(frozen=True)
class Health:
    heartbeat_seen: bool
    heartbeat_fresh: bool
    drive_seen: bool
    drive_healthy: bool
    tf_healthy: bool
    # True while the drive bridge reports DriveStatus.batt_critical (pack at
    # or below BATT_CRITICAL_MV, but not yet batt_dead). Reported separately
    # from drive_healthy/drive_seen because a critical-but-not-dead pack must
    # NOT be treated as a drive-link fault - drive_link_adapter deliberately
    # leaves batt_critical_blocks_link false so a low pack can still drive
    # itself home instead of being safe-stopped in place.
    battery_critical: bool


def decide(state, armed, start_captured, health):
    """Return the only automatic action allowed by the current health state."""
    if not armed or state in {'ARRIVED', 'SAFE_STOP'}:
        return Decision.NONE

    if health.drive_seen and not health.drive_healthy:
        return Decision.SAFE_STOP

    if (
        state in {'NORMAL', 'RETURN_REQUESTED', 'RETURNING'}
        and not health.tf_healthy
    ):
        return Decision.SAFE_STOP

    # Two independent conditions request the same automatic return: control
    # heartbeat loss (the original trigger) and a critical battery pack (the
    # robot should drive itself home while it still can, rather than wait
    # for someone to notice or for the pack to reach batt_dead and lose
    # drive entirely). Both go through the identical precondition guard -
    # only RETURN_HOME if drive and localization are themselves healthy,
    # otherwise SAFE_STOP rather than attempt a return on a system that
    # cannot safely execute one.
    if state == 'NORMAL' and (
        health.battery_critical
        or (health.heartbeat_seen and not health.heartbeat_fresh)
    ):
        if start_captured and health.drive_healthy and health.tf_healthy:
            return Decision.RETURN_HOME
        return Decision.SAFE_STOP

    return Decision.NONE
