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

    if state == 'NORMAL' and health.heartbeat_seen and not health.heartbeat_fresh:
        if start_captured and health.drive_healthy and health.tf_healthy:
            return Decision.RETURN_HOME
        return Decision.SAFE_STOP

    return Decision.NONE
