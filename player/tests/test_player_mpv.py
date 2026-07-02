import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lib.interfaces import RadioPadStation
from lib.player_mpv import MpvPlayer


def fake_process():
    process = Mock(pid=123)
    process.poll.return_value = None
    process.wait.return_value = 0
    return process


def fake_socket(**state):
    return SimpleNamespace(**{"idle_active": False, "audio_params": None, "volume": 75, "stop": Mock(), **state})


async def directly(function, *args, **kwargs):
    return function(*args, **kwargs)


def test_play_confirms_only_after_ipc_reports_audio_ready(tmp_path):
    process = fake_process()
    sock = fake_socket(audio_params={"samplerate": 48000})
    player = MpvPlayer(
        audio_device="alsa/default:CARD=Generic",
        audio_output="alsa",
        socket_path=str(tmp_path / "mpv.sock"),
        playback_timeout_seconds=0.1,
    )
    station = RadioPadStation("KEXP", "https://example.test/kexp")

    with (
        patch("lib.player_mpv.subprocess.Popen", return_value=process) as popen,
        patch("lib.player_mpv.MPV", return_value=sock),
        patch("lib.player_mpv.asyncio.to_thread", side_effect=directly),
    ):
        assert asyncio.run(player.play(station)) is True

    assert player.station == station
    assert player.mpv_sock is sock
    command = popen.call_args.args[0]
    assert "--audio-device=alsa/default:CARD=Generic" in command
    assert "--ao=alsa" in command


def test_live_process_without_ready_audio_times_out_and_clears_state(tmp_path):
    process = fake_process()
    sock = fake_socket(idle_active=True)
    player = MpvPlayer(socket_path=str(tmp_path / "mpv.sock"), playback_timeout_seconds=0.01)
    station = RadioPadStation("GMCR", "http://stream.gmcr.org:8000/gmcr")
    statuses = []

    async def report(level, summary):
        statuses.append((level, summary))

    player.status_reporter = report
    with (
        patch("lib.player_mpv.subprocess.Popen", return_value=process),
        patch("lib.player_mpv.MPV", return_value=sock),
        patch("lib.player_mpv.asyncio.to_thread", side_effect=directly),
        patch("lib.player_mpv.READINESS_POLL_SECONDS", 0.001),
    ):
        assert asyncio.run(player.play(station)) is False

    assert player.station is None
    process.terminate.assert_called_once()
    assert statuses == [("error", "Playback timed out")]


def test_process_exit_for_unreachable_stream_reports_failure(tmp_path):
    process = fake_process()
    process.poll.return_value = 2
    player = MpvPlayer(socket_path=str(tmp_path / "mpv.sock"))
    station = RadioPadStation("STALE", "https://stale.example.invalid/stream")
    statuses = []

    async def report(level, summary):
        statuses.append((level, summary))

    player.status_reporter = report
    with (
        patch("lib.player_mpv.subprocess.Popen", return_value=process),
        patch("lib.player_mpv.asyncio.to_thread", side_effect=directly),
    ):
        assert asyncio.run(player.play(station)) is False

    assert player.station is None
    assert statuses == [("error", "Playback failed")]
