from lib.macropad_keys import VISUAL_MODE_LOADING, VISUAL_MODE_WAITING
from lib.macropad_state import MacropadState


class FakeKeys:
    def __init__(self):
        self.station_lists = []
        self.playing_stations = []

    def set_visual_state(self, degraded, visual_mode, title_override, force=False):
        pass

    def set_stations(self, stations, refresh=True):
        self.station_lists.append((stations, refresh))

    def set_playing_station(self, station):
        self.playing_stations.append(station)


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


def station_list(*stations):
    return {"event": "station_list", "data": list(stations)}


def test_state_flows_from_waiting_to_loading_to_ready():
    state, keys = state_keys()

    assert_view(state, False, VISUAL_MODE_WAITING, "Waiting for Player")

    assert state.mark_player_available()
    assert_view(state, False, VISUAL_MODE_LOADING, "Loading stations")

    state.handle_event(station_list("KEXP"), keys)
    assert state.has_stations
    assert keys.station_lists[-1] == ([{"name": "KEXP"}], False)
    assert_view(state, False, None, None)


def test_upstream_warning_degrades_ready_stations_without_taking_title_line():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("upstream", "warning", "Switchboard down"), keys)
    assert_view(state, True, VISUAL_MODE_LOADING, "Switchboard down")

    state.handle_event(station_list("KEXP"), keys)
    assert_view(state, True, None, None)


def test_upstream_warning_without_summary_still_degrades_keys():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("upstream", "warning"), keys)

    assert_view(state, True, VISUAL_MODE_LOADING, "Loading stations")


def test_ok_status_clears_degraded_state():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("upstream", "warning", "Switchboard down"), keys)
    state.handle_event(player_status("upstream", "ok"), keys)

    assert not state.has_status
    assert_view(state, False, VISUAL_MODE_LOADING, "Loading stations")


def test_empty_station_list_keeps_loading_state():
    state, keys = state_keys(available=True)

    state.handle_event(station_list(), keys)

    assert not state.has_stations
    assert keys.station_lists[-1] == ([], False)
    assert_view(state, False, VISUAL_MODE_LOADING, "Loading stations")


def test_station_playing_event_updates_keys():
    state, keys = state_keys()

    state.handle_event({"event": "station_playing", "data": "KEXP"}, keys)

    assert keys.playing_stations == ["KEXP"]


def test_unavailable_player_clears_session_state():
    state, keys = state_keys(available=True)

    state.handle_event(player_status("upstream", "warning", "Switchboard down"), keys)
    state.handle_event(station_list("KEXP"), keys)

    assert state.mark_player_unavailable()
    assert not state.player_available
    assert not state.has_stations
    assert not state.has_status

    assert_view(state, False, VISUAL_MODE_WAITING, "Waiting for Player")
