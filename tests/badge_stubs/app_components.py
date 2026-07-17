def clear_background(ctx):
    pass


class YesNoDialog:
    def __init__(self, message=None, on_yes=None, on_no=None, app=None):
        self.message = message
        self.on_yes = on_yes
        self.on_no = on_no
        self.app = app

    def draw(self, ctx):
        pass
