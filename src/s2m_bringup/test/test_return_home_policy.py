"""Host-only tests for return-home safety decisions."""

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from return_home_policy import Decision, Health, decide  # noqa: E402


def healthy(heartbeat_fresh=True, drive_healthy=True, tf_healthy=True):
    return Health(
        heartbeat_seen=True,
        heartbeat_fresh=heartbeat_fresh,
        drive_seen=True,
        drive_healthy=drive_healthy,
        tf_healthy=tf_healthy,
    )


def test_network_loss_requests_return_when_all_local_systems_are_healthy():
    result = decide('NORMAL', True, True, healthy(heartbeat_fresh=False))
    assert result is Decision.RETURN_HOME


def test_drive_link_loss_selects_safe_stop_instead_of_return():
    result = decide(
        'NORMAL',
        True,
        True,
        healthy(heartbeat_fresh=False, drive_healthy=False),
    )
    assert result is Decision.SAFE_STOP


def test_tf_loss_selects_safe_stop_instead_of_return():
    result = decide(
        'NORMAL',
        True,
        True,
        healthy(heartbeat_fresh=False, tf_healthy=False),
    )
    assert result is Decision.SAFE_STOP


def test_drive_loss_cancels_an_active_return():
    result = decide('RETURNING', True, True, healthy(drive_healthy=False))
    assert result is Decision.SAFE_STOP


def test_disarmed_monitor_never_starts_an_automatic_return():
    result = decide('NORMAL', False, True, healthy(heartbeat_fresh=False))
    assert result is Decision.NONE
