from lib.macropad_keys import VISUAL_MODE_LOADING, VISUAL_MODE_WAITING
from lib.macropad_state import MacropadState


class FakeKeys:
    def __init__(self):
        self.station_updates = []
        self.playback_states = []

    def set_visual_state(self, degraded, visual_mode, title_override, force=False):
        pass

    def set_stations(self, stations, refresh=True):
        self.station_updates.append((stations, refresh))

    def set_playback_state(self, call_sign, requested_call_sign):
        self.playback_states.append((call_sign, requested_call_sign))


def assert_view(state, degraded, visual_mode, title_override):
    assert state.view() == (degraded, visual_mode, title_override)


def state_keys(available=False):
    state = MacropadState()
    keys = FakeKeys()
    if available:
        state.mark_player_available()
    return state, keys


def player_status(scope, level, summary=None):
    return {
        "event": "player_status",
        "data": {"scope": scope, "level": level, "summary": summary},
    }


def station_menu(*call_signs):
    return {"event": "station_menu", "data": list(call_signs)}


def test_state_flows_from_waiting_to_loading_to_ready():
    state, keys = state_keys()

    assert_view(state, False, VISUAL_MODE_WAITING, "Waiting for Player")

    assert state.mark_player_available()
    assert_view(state, False, VISUAL_MODE_LOADING, "Loading RadioDial")

    state.handle_event(station_menu("KEXP"), keys)
    assert state.station_menu_loaded
    assert keys.station_updates[-1] == (["KEXP"], False)
    assert_view(state, False, None, None)


def test_switchboard_warning_degrades_ready_stations_without_taking_title_line():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("switchboard", "warning", "Switchboard down"), keys)
    assert_view(state, True, VISUAL_MODE_LOADING, "Switchboard down")

    state.handle_event(station_menu("KEXP"), keys)
    assert_view(state, True, None, None)


def test_switchboard_warning_without_summary_still_degrades_keys():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("switchboard", "warning"), keys)

    assert_view(state, True, VISUAL_MODE_LOADING, "Loading RadioDial")


def test_ok_status_clears_degraded_state():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("switchboard", "warning", "Switchboard down"), keys)
    state.handle_event(player_status("switchboard", "ok"), keys)

    assert not state.has_status
    assert_view(state, False, VISUAL_MODE_LOADING, "Loading RadioDial")


def test_empty_station_menu_is_loaded():
    state, keys = state_keys(available=True)

    state.handle_event(station_menu(), keys)

    assert state.station_menu_loaded
    assert keys.station_updates[-1] == ([], False)
    assert_view(state, False, None, None)


def test_invalid_station_menu_is_ignored():
    state, keys = state_keys(available=True)

    state.handle_event({"event": "station_menu", "data": ["KEXP", None]}, keys)

    assert not state.station_menu_loaded
    assert keys.station_updates == []


def test_playback_state_event_updates_keys():
    state, keys = state_keys()

    state.handle_event(
        {
            "event": "playback_state",
            "data": {"call_sign": None, "requested_call_sign": "KEXP"},
        },
        keys,
    )

    assert keys.playback_states == [(None, "KEXP")]


def test_unavailable_player_clears_session_state():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("switchboard", "warning", "Switchboard down"), keys)
    state.handle_event(station_menu("KEXP"), keys)

    assert state.mark_player_unavailable()
    assert not state.player_available
    assert not state.station_menu_loaded
    assert not state.has_status

    assert_view(state, False, VISUAL_MODE_WAITING, "Waiting for Player")
