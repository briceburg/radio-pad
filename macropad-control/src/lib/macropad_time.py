# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

import time

TICKS_PERIOD = 1 << 29
TICKS_HALF_PERIOD = TICKS_PERIOD // 2

try:
    from adafruit_ticks import ticks_diff, ticks_ms
except ImportError:

    def ticks_ms():
        return int(time.monotonic() * 1000) % TICKS_PERIOD

    def ticks_diff(new, old):
        return ((new - old + TICKS_HALF_PERIOD) % TICKS_PERIOD) - TICKS_HALF_PERIOD
