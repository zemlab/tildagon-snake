class _EventBus:
    def __init__(self):
        self.emitted = []

    def emit(self, event):
        self.emitted.append(event)


eventbus = _EventBus()
