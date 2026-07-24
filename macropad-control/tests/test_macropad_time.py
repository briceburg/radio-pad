from lib import macropad_time


def test_fallback_ticks_ms_wraps_at_circuitpython_period(monkeypatch):
    elapsed_ms = macropad_time.TICKS_PERIOD + 123
    monkeypatch.setattr(macropad_time.time, "monotonic", lambda: elapsed_ms / 1000)

    assert macropad_time.ticks_ms() == 123


def test_fallback_ticks_diff_handles_forward_wrap():
    before_wrap = macropad_time.TICKS_PERIOD - 1000
    after_wrap = 1000

    assert macropad_time.ticks_diff(after_wrap, before_wrap) == 2000
