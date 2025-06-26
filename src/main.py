import os
import time
import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label
from adafruit_macropad import MacroPad
from adafruit_hid.keycode import Keycode
import time

MACRO_FOLDER = "/macros"


class App:
    """Class representing a host-side application, for which we have a set
    of macro sequences. Project code was originally more complex and
    this was helpful, but maybe it's excessive now?"""

    def __init__(self, appdata):
        self.name = appdata["name"]
        self.macros = appdata["macros"]

    def switch(self):
        """Activate application settings; update OLED labels and LED
        colors."""
        group[13].text = self.name  # Application name
        if self.name:
            rect.fill = 0xFFFFFF
        else:  # empty app name indicates blank screen for which we dimm header
            rect.fill = 0x000000
        for i in range(12):
            if i < len(self.macros):  # Key in use, set label + LED color
                macropad.pixels[i] = self.macros[i][0]
                group[i].text = self.macros[i][1]
            else:  # Key not in use, no label or LED
                macropad.pixels[i] = 0
                group[i].text = ""
        macropad.keyboard.release_all()
        macropad.consumer_control.release()
        macropad.mouse.release_all()
        macropad.stop_tone()
        macropad.pixels.show()
        macropad.display.refresh()


# INITIALIZATION -----------------------

macropad = MacroPad()
macropad.display.auto_refresh = False
macropad.pixels.auto_write = False
macropad.pixels.brightness = 0.10  # Dim the LEDs

# Set up displayio group with all the labels
group = displayio.Group()
for key_index in range(12):
    x = key_index % 3
    y = key_index // 3
    group.append(
        label.Label(
            terminalio.FONT,
            text="",
            color=0xFFFFFF,
            anchored_position=(
                (macropad.display.width - 1) * x / 2,
                macropad.display.height - 1 - (3 - y) * 12,
            ),
            anchor_point=(x / 2, 1.0),
        )
    )
rect = Rect(0, 0, macropad.display.width, 13, fill=0xFFFFFF)
group.append(rect)
group.append(
    label.Label(
        terminalio.FONT,
        text="",
        color=0x000000,
        anchored_position=(macropad.display.width // 2, 0),
        anchor_point=(0.5, 0.0),
    )
)
macropad.display.root_group = group

# Load all the macro key setups from .py files in MACRO_FOLDER
apps = []
files = os.listdir(MACRO_FOLDER)
files.sort()
for filename in files:
    if filename.endswith(".py") and not filename.startswith("._"):
        try:
            module = __import__(MACRO_FOLDER + "/" + filename[:-3])
            apps.append(App(module.app))
        except (
            SyntaxError,
            ImportError,
            AttributeError,
            KeyError,
            NameError,
            IndexError,
            TypeError,
        ) as err:
            print("ERROR in", filename)
            import traceback

            traceback.print_exception(err, err, err.__traceback__)

if not apps:
    group[13].text = "NO MACRO FILES FOUND"
    macropad.display.refresh()
    while True:
        pass

pressed_color = 0x015C01
last_position = None
last_pressed = None
last_encoder_switch = macropad.encoder_switch_debounced.pressed
app_index = 0
apps[app_index].switch()

def radio_control(key):
    """Send a control command follwed by key to the radio-pad application."""
    macropad.keyboard.press(Keycode.CONTROL)
    macropad.keyboard.press(Keycode.SIX)
    macropad.keyboard.release(Keycode.CONTROL)
    macropad.keyboard.release(Keycode.SIX)
    macropad.keyboard.press(key)
    macropad.keyboard.release(key)

# MAIN LOOP ----------------------------

while True:
    # Read encoder position. If it's changed, adjust volume.
    position = macropad.encoder
    if last_position is not None and position != last_position:
        radio_control(
            Keycode.UP_ARROW if position > last_position else Keycode.DOWN_ARROW
        )
    last_position = position

    # Handle encoder button. If it's pressed, stop radio. 
    macropad.encoder_switch_debounced.update()
    encoder_switch = macropad.encoder_switch_debounced.pressed
    if encoder_switch != last_encoder_switch:
        last_encoder_switch = encoder_switch
        if last_pressed is not None:
            # stop radio
            radio_control(Keycode.LEFT_ARROW)

            # reset radio display and highlighted key to its original
            group[last_pressed].color = 0xFFFFFF
            group[last_pressed].background_color = 0x000000
            group[13].text = apps[app_index].name
            macropad.display.refresh()
            last_pressed = None

            # flash the pixels
            for i in range(12):
                macropad.pixels[i] = 0x990909
            macropad.pixels.show()
            time.sleep(0.66)

            # restore the pixels
            for i in range(12):
                try:
                    macropad.pixels[i] = apps[app_index].macros[i][0]
                except IndexError:
                    macropad.pixels[i] = 0
            macropad.pixels.show()
            
        continue
    else:
        event = macropad.keys.events.get()
        if not event or event.key_number >= len(apps[app_index].macros):
            continue  # No key events, or no corresponding macro, resume loop
        key_number = event.key_number
        pressed = event.pressed

    # If code reaches here, a key WAS pressed/released and there's a corresponding macro.
    sequence = apps[app_index].macros[key_number][2]
    if pressed:
        # 'sequence' is an arbitrary-length list, each item is one of:
        # Positive integer (e.g. Keycode.KEYPAD_MINUS): key pressed
        # Negative integer: (absolute value) key released
        # Float (e.g. 0.25): delay in seconds
        # String (e.g. "Foo"): corresponding keys pressed & released
        # List []: one or more Consumer Control codes (can also do float delay)
        # Dict {}: mouse buttons/motion (might extend in future)
        if key_number < 12:  # No pixel for encoder button
            macropad.pixels[key_number] = pressed_color
            macropad.pixels.show()

            # highlight the station pressed on the OLED display
            if last_pressed != key_number:
                group[key_number].color = 0x000000
                group[key_number].background_color = 0xFFFFFF
                group[13].text = apps[app_index].macros[key_number][1]

                # reset highlight on the previously selected station
                if last_pressed is not None:
                    group[last_pressed].color = 0xFFFFFF
                    group[last_pressed].background_color = 0x000000

                macropad.display.refresh()
        for item in sequence:
            if isinstance(item, int):
                if item >= 0:
                    macropad.keyboard.press(item)
                else:
                    macropad.keyboard.release(-item)
            elif isinstance(item, float):
                time.sleep(item)
            elif isinstance(item, str):
                macropad.keyboard_layout.write(item)
            elif isinstance(item, list):
                for code in item:
                    if isinstance(code, int):
                        macropad.consumer_control.release()
                        macropad.consumer_control.press(code)
                    if isinstance(code, float):
                        time.sleep(code)
            elif isinstance(item, dict):
                if "buttons" in item:
                    if item["buttons"] >= 0:
                        macropad.mouse.press(item["buttons"])
                    else:
                        macropad.mouse.release(-item["buttons"])
                macropad.mouse.move(
                    item["x"] if "x" in item else 0,
                    item["y"] if "y" in item else 0,
                    item["wheel"] if "wheel" in item else 0,
                )
                if "tone" in item:
                    if item["tone"] > 0:
                        macropad.stop_tone()
                        macropad.start_tone(item["tone"])
                    else:
                        macropad.stop_tone()
                elif "play" in item:
                    macropad.play_file(item["play"])
    else:
        # Release any still-pressed keys, consumer codes, mouse buttons
        # Keys and mouse buttons are individually released this way (rather
        # than release_all()) because pad supports multi-key rollover, e.g.
        # could have a meta key or right-mouse held down by one macro and
        # press/release keys/buttons with others. Navigate popups, etc.
        for item in sequence:
            if isinstance(item, int):
                if item >= 0:
                    macropad.keyboard.release(item)
            elif isinstance(item, dict):
                if "buttons" in item:
                    if item["buttons"] >= 0:
                        macropad.mouse.release(item["buttons"])
                elif "tone" in item:
                    macropad.stop_tone()
        macropad.consumer_control.release()

        if key_number < 12:  # No pixel for encoder button
            # reset previously highlighted key to its original color
            if last_pressed is not None and last_pressed != key_number:
                macropad.pixels[last_pressed] = apps[app_index].macros[last_pressed][0]
                macropad.pixels.show()
            last_pressed = key_number
