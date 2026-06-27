"""List endpoints return full resources only when no smaller projection exists."""

from models import AccountSpec, PlayerSpec, RadioDialSpec
from tests.api._helpers import assert_exact_fields, find_item
from tests.api.client.accounts import AccountApi
from tests.api.client.players import PlayerApi
from tests.api.client.radio_dials import RadioDialApi


def test_account_list_returns_complete_small_resource(account_api: AccountApi) -> None:
    account_api.put("list-shape", AccountSpec(name="List Shape"))

    account = find_item(account_api.list()["items"], "list-shape")

    assert_exact_fields(account, "id", "name")


def test_player_list_returns_summary(player_api: PlayerApi) -> None:
    player_api.put(
        "list-shape",
        "summary-player",
        PlayerSpec(
            name="Summary Player",
            radio_dial="community/briceburg",
            switchboard_url="wss://example.com/switchboard",
        ),
    )

    player = find_item(player_api.list("list-shape")["items"], "summary-player")

    assert_exact_fields(player, "id", "account_id", "name")


def test_radio_dial_list_returns_summary(radio_dial_api: RadioDialApi) -> None:
    radio_dial_api.put(
        "list-shape",
        "summary-dial",
        RadioDialSpec(
            name="Summary Dial",
            description="Visible summary metadata",
            discoverable=True,
            stations=["community/WWOZ"],
        ),
    )

    [summary] = radio_dial_api.list("list-shape")["items"]

    assert_exact_fields(summary, "key", "name", "description", "discoverable")
