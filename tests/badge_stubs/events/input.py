BUTTON_TYPES = {
    "UP": "UP",
    "DOWN": "DOWN",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
    "CONFIRM": "CONFIRM",
    "CANCEL": "CANCEL",
}


class Buttons:
    """Test double: tests drive input by mutating `.pressed` directly."""

    def __init__(self, app):
        self.pressed = set()

    def get(self, name):
        return name in self.pressed

    def clear(self):
        self.pressed = set()
