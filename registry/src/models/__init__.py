"""Registry domain model naming.

Specs are writable resource specifications without path-derived identity. Unsuffixed models are complete returned
resources. Summaries are reduced representations used only by list and discovery endpoints.
"""

from .account import Account, AccountSpec
from .player import Player, PlayerSpec, PlayerSummary
from .radio_dial import RadioDial, RadioDialSpec, RadioDialSummary
from .station import Station, StationSpec

__all__ = [
    "Account",
    "AccountSpec",
    "Player",
    "PlayerSpec",
    "PlayerSummary",
    "RadioDial",
    "RadioDialSpec",
    "RadioDialSummary",
    "Station",
    "StationSpec",
]
