from lib import macropad_keys
from lib.macropad_keys import MacropadKeys, SKELETON_ANIMATION_TIMEOUT_MS


class FakePixels:
    def __init__(self):
        self.auto_write = True
        self.brightness = 1
        self.values = [0] * macropad_keys.MACROPAD_KEY_COUNT
        self.show_count = 0

    def __setitem__(self, index, value):
        self.values[index] = value

    def show(self):
        self.show_count += 1


class FakeMacropad:
    def __init__(self):
        self.pixels = FakePixels()


class FakeDisplay:
    def __init__(self):
        self.title = None
        self.groups = [""] * macropad_keys.MACROPAD_KEY_COUNT

    def set_title(self, title, _selected):
        self.title = title

    def set_group_text(self, index, text):
        self.groups[index] = text

    def highlight_group(self, _index):
        pass

    def unhighlight_group(self, _index):
        pass

    def refresh(self):
        pass


def test_skeleton_animation_settles_static_after_timeout(monkeypatch):
    now = 1000
    monkeypatch.setattr(macropad_keys, "ticks_ms", lambda: now)

    keys = MacropadKeys(FakeMacropad(), FakeDisplay())
    keys.set_visual_state(
        False,
        macropad_keys.VISUAL_MODE_WAITING,
        None,
        force=True,
    )
    animated_values = list(keys.macropad.pixels.values)

    now += SKELETON_ANIMATION_TIMEOUT_MS + 1
    keys.tick()
    static_values = list(keys.macropad.pixels.values)

    now += macropad_keys.SKELETON_TICK_MS * 2
    keys.tick()

    assert static_values != animated_values
    assert keys.macropad.pixels.values == static_values
