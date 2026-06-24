from lib.macropad_keys import DEFAULT_COLOR, VISUAL_MODE_LOADING, VISUAL_MODE_WAITING
from lib.macropad_state import MacropadState


class FakeKeys:
    def __init__(self):
        self.visual_states = []
        self.station_lists = []
        self.playing_stations = []

    def set_visual_state(
        self,
        degraded=False,
        visual_mode=None,
        title_override=None,
        force=False,
    ):
        self.visual_states.append(
            {
                "degraded": degraded,
                "visual_mode": visual_mode,
                "title_override": title_override,
                "force": force,
            }
        )

    def set_stations(self, stations, refresh=True):
        self.station_lists.append((stations, refresh))

    def set_playing_station(self, station):
        self.playing_stations.append(station)


def test_state_flows_from_waiting_to_loading_to_ready():
    state = MacropadState()
    keys = FakeKeys()

    state.apply(keys, force=True)
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": VISUAL_MODE_WAITING,
        "title_override": "Waiting for Player",
        "force": True,
    }

    assert state.mark_player_available()
    state.apply(keys, force=True)
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": VISUAL_MODE_LOADING,
        "title_override": "Loading stations",
        "force": True,
    }

    state.handle_event({"event": "station_list", "data": ["KEXP"]}, keys)
    assert state.has_stations
    assert keys.station_lists[-1] == (
        [{"name": "KEXP", "color": DEFAULT_COLOR}],
        False,
    )
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": None,
        "title_override": None,
        "force": True,
    }


def test_upstream_warning_degrades_ready_stations_without_taking_title_line():
    state = MacropadState()
    keys = FakeKeys()

    state.mark_player_available()
    state.handle_event(
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "warning",
                "summary": "Switchboard down",
            },
        },
        keys,
    )
    assert keys.visual_states[-1] == {
        "degraded": True,
        "visual_mode": VISUAL_MODE_LOADING,
        "title_override": "Switchboard down",
        "force": False,
    }

    state.handle_event({"event": "station_list", "data": ["KEXP"]}, keys)
    assert keys.visual_states[-1] == {
        "degraded": True,
        "visual_mode": None,
        "title_override": None,
        "force": True,
    }


def test_ok_status_clears_degraded_state():
    state = MacropadState()
    keys = FakeKeys()

    state.mark_player_available()
    state.handle_event(
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "warning",
                "summary": "Switchboard down",
            },
        },
        keys,
    )
    state.handle_event(
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "ok",
                "summary": None,
            },
        },
        keys,
    )

    assert not state.has_status
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": VISUAL_MODE_LOADING,
        "title_override": "Loading stations",
        "force": False,
    }


def test_empty_station_list_keeps_loading_state():
    state = MacropadState()
    keys = FakeKeys()

    state.mark_player_available()
    state.handle_event({"event": "station_list", "data": []}, keys)

    assert not state.has_stations
    assert keys.station_lists[-1] == ([], False)
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": VISUAL_MODE_LOADING,
        "title_override": "Loading stations",
        "force": True,
    }


def test_unavailable_player_clears_session_state_and_station_keys():
    state = MacropadState()
    keys = FakeKeys()

    state.mark_player_available()
    state.handle_event(
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "warning",
                "summary": "Switchboard down",
            },
        },
        keys,
    )
    state.handle_event({"event": "station_list", "data": ["KEXP"]}, keys)

    assert state.mark_player_unavailable(keys)
    assert not state.player_available
    assert not state.has_stations
    assert not state.has_status
    assert keys.station_lists[-1] == ([], False)

    state.apply(keys, force=True)
    assert keys.visual_states[-1] == {
        "degraded": False,
        "visual_mode": VISUAL_MODE_WAITING,
        "title_override": "Waiting for Player",
        "force": True,
    }
