BUTTON_TYPES = {
    "UP": "UP",
    "DOWN": "DOWN",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
    "CONFIRM": "CONFIRM",
    "CANCEL": "CANCEL",
}


class Buttons:
    """Test double: tests drive input by mutating `.held` directly to
    simulate a button being physically down. `get()` mirrors the real
    firmware's level state; `pressed()` mirrors its edge-triggered,
    latch-until-release state.
    """

    def __init__(self, app):
        self.held = set()
        self._already_pressed = set()

    def get(self, name):
        return name in self.held

    def pressed(self, name):
        is_down = self.get(name)
        if is_down and name not in self._already_pressed:
            self._already_pressed.add(name)
            return True
        if not is_down:
            self._already_pressed.discard(name)
        return False

    def clear(self):
        self.held = set()
        self._already_pressed = set()
