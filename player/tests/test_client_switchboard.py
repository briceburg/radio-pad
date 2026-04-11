from unittest.mock import patch

from lib.client_switchboard import next_retry_delay


def test_next_retry_delay_adds_bounded_jitter_and_grows_delay():
    with patch("lib.client_switchboard.random.random", return_value=0.5):
        sleep_seconds, next_delay = next_retry_delay(
            1,
            factor=1.5,
            jitter_seconds=1,
            max_delay_seconds=8,
        )

    assert sleep_seconds == 1.5
    assert next_delay == 1.5


def test_next_retry_delay_caps_sleep_and_next_delay():
    with patch("lib.client_switchboard.random.random", return_value=0.75):
        sleep_seconds, next_delay = next_retry_delay(
            8,
            factor=1.5,
            jitter_seconds=1,
            max_delay_seconds=8,
        )

    assert sleep_seconds == 8
    assert next_delay == 8
