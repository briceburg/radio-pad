# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

import time

from adafruit_macropad import MacroPad

from lib.macropad_display import MacropadDisplay
from lib.macropad_keys import MacropadKeys
from lib.macropad_player import MacropadPlayer
from lib.macropad_state import MacropadState

macropad = MacroPad()
display = MacropadDisplay(macropad)
keys = MacropadKeys(macropad, display)
player = MacropadPlayer()
state = MacropadState()

last_position = macropad.encoder
last_encoder_switch = macropad.encoder_switch_debounced.pressed
state.apply(keys, force=True)

while True:
    event = player.read_event() if player.connected else None
    if event:
        state.handle_event(event, keys)

    # --- Player Connection ---
    connected = player.connected
    if not connected or player.session_stale:
        state_changed = state.mark_player_unavailable()
        if not connected and state_changed:
            player.flush_buffer()
        if state_changed:
            keys.set_stations([], refresh=False)
        state.apply(keys, force=state_changed)
        keys.tick()
        time.sleep(0.01)
        continue

    if state.mark_player_available():
        state.apply(keys, force=True)

    if state.needs_station_menu:
        player.request_station_menu()
        state.apply(keys)

    # --- Encoder Rotation ---
    position = macropad.encoder
    if position != last_position:
        if keys.playing_station_index is not None:
            if position > last_position:
                player.volume_up()
            else:
                player.volume_down()
        else:
            num_pages = keys.page_count
            if position > last_position:
                keys.switch_page((keys.current_page_index + 1) % num_pages)
            else:
                keys.switch_page((keys.current_page_index - 1 + num_pages) % num_pages)
        last_position = position

    # --- Encoder Press ---
    macropad.encoder_switch_debounced.update()
    pressed = macropad.encoder_switch_debounced.pressed
    if pressed and not last_encoder_switch:
        if keys.can_stop:
            player.stop_playback()
            keys.flash_keys()
    last_encoder_switch = pressed

    # --- Key Events ---
    last_pressed_call_sign = None
    while True:
        # Drain keypad event queue so simultaneous presses resolve to the "last" press.
        key_event = macropad.keys.events.get()
        if not key_event:
            break
        if not key_event.pressed:
            continue

        key_number = key_event.key_number
        call_sign = keys.get_call_sign(key_number)
        if call_sign:
            last_pressed_call_sign = call_sign

    if last_pressed_call_sign:
        keys.set_pending_station(last_pressed_call_sign)
        player.start_playback(last_pressed_call_sign)

    keys.tick()
    time.sleep(0.01)
