# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exceptions for the radio-pad application."""


class RadioPadError(Exception):
    """Base exception for radio-pad errors."""


class ConfigError(RadioPadError):
    """Raised for configuration-related errors."""

    def __init__(self, message, *, status_summary="Registry unavailable"):
        super().__init__(message)
        self.status_summary = status_summary
