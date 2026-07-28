import json
from pathlib import Path

import pytest

from lib import macropad_keys
from lib.macropad_keys import SKELETON_ANIMATION_TIMEOUT_MS, MacropadKeys
from lib.macropad_state import MacropadState

CONTROLLER_TITLE_CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "controller-title-cases.json").read_text()
)


class FakePixels:
    def __init__(self):
        self.auto_write = True
        self.brightness = 1
        self.values = [0] * macropad_keys.MACROPAD_KEY_COUNT
        self.show_count = 0

    def __setitem__(self, index, value):
        self.values[index] = value

    def show(self):
        self.show_count += 1


class FakeMacropad:
    def __init__(self):
        self.pixels = FakePixels()


class FakeDisplay:
    def __init__(self):
        self.title = None
        self.groups = [""] * macropad_keys.MACROPAD_KEY_COUNT

    def set_title(self, title, _selected):
        self.title = title

    def set_group_text(self, index, text):
        self.groups[index] = text

    def highlight_group(self, _index):
        pass

    def unhighlight_group(self, _index):
        pass

    def refresh(self):
        pass


@pytest.mark.parametrize(
    "title_case",
    CONTROLLER_TITLE_CASES,
    ids=[title_case["name"] for title_case in CONTROLLER_TITLE_CASES],
)
def test_shared_controller_title_contract(title_case):
    state = MacropadState()
    keys = MacropadKeys(FakeMacropad(), FakeDisplay())

    if title_case["player_available"]:
        state.mark_player_available()
    state.apply(keys, force=True)

    if title_case["player_available"]:
        station_menu = title_case["station_menu"]
        if station_menu is not None:
            state.handle_event({"event": "station_menu", "data": station_menu}, keys)

        state.handle_event(
            {
                "event": "playback_state",
                "data": title_case["playback_state"],
            },
            keys,
        )
        for status in title_case["player_statuses"]:
            state.handle_event({"event": "player_status", "data": status}, keys)

    assert keys.display.title == title_case["expected_title"]


def test_skeleton_animation_settles_static_after_timeout(monkeypatch):
    now = 1000
    monkeypatch.setattr(macropad_keys, "ticks_ms", lambda: now)

    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_visual_state(
        False,
        macropad_keys.VISUAL_MODE_WAITING,
        None,
        force=True,
    )
    animated_values = list(keys.macropad.pixels.values)

    now += SKELETON_ANIMATION_TIMEOUT_MS + 1
    keys.tick()
    static_values = list(keys.macropad.pixels.values)

    now += macropad_keys.SKELETON_TICK_MS * 2
    keys.tick()

    assert static_values != animated_values
    assert keys.macropad.pixels.values == static_values


def test_pending_station_is_distinct_and_recovers_to_confirmed_or_idle():
    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_stations(["KEXP"])

    keys.set_playback_state(None, "KEXP", None)
    assert keys.macropad.pixels.values[0] == macropad_keys.PENDING_COLOR
    assert keys.display.title == "Starting KEXP"
    assert keys.can_stop

    keys.set_playback_state("KEXP", None, None)
    assert keys.macropad.pixels.values[0] == macropad_keys.PLAYING_COLOR
    assert keys.display.title == "KEXP"

    keys.set_playback_state(None, None, None)
    assert keys.macropad.pixels.values[0] == macropad_keys.DEFAULT_COLOR
    assert not keys.can_stop


def test_local_request_immediately_replaces_pending_station():
    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_stations(["KEXP", "KGUT"])
    keys.set_visual_state(False, None, "Playback failed")

    keys.set_pending_station("KEXP")
    keys.set_pending_station("KGUT")

    assert keys.macropad.pixels.values[:2] == [
        macropad_keys.DEFAULT_COLOR,
        macropad_keys.PENDING_COLOR,
    ]
    assert keys.display.title == "Starting KGUT"


def test_local_request_for_playing_station_stays_confirmed():
    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_stations(["KEXP"])
    keys.set_playback_state("KEXP", None, None)

    keys.set_pending_station("KEXP")

    assert keys.macropad.pixels.values[0] == macropad_keys.PLAYING_COLOR
    assert keys.display.title == "KEXP"
    assert keys.pending_station_index is None


def test_failed_station_turns_red_and_retry_turns_amber():
    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_stations(["LOFI"])
    keys.set_visual_state(False, None, "Playback failed")

    keys.set_playback_state(None, None, "LOFI")
    assert keys.macropad.pixels.values[0] == macropad_keys.FAILED_COLOR
    assert keys.display.title == "Failed LOFI"

    keys.set_pending_station("LOFI")
    assert keys.macropad.pixels.values[0] == macropad_keys.PENDING_COLOR
    assert keys.display.title == "Starting LOFI"
