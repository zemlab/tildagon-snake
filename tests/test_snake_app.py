def _button_for(module, direction):
    for name, d in module.BUTTON_DIR.items():
        if d == direction:
            return name
    raise AssertionError(f"no button maps to {direction}")


def test_starts_playing_immediately_no_title_screen(snake_module):
    game = snake_module.SnakeApp()
    assert game.game == "ON"
    assert game.snake == [(0, 0)]
    assert game.direction in snake_module.DIRS
    assert len(game.food) == 1


def test_move_snake_advances_head_and_keeps_length(snake_module):
    game = snake_module.SnakeApp()
    game.food = []  # no food in the way
    game.direction = "N"
    game.next_direction = ""
    game._move_snake()
    assert game.snake[0] == snake_module.DIRS["N"]
    assert len(game.snake) == 1


def test_eating_food_grows_snake_and_scores(snake_module):
    game = snake_module.SnakeApp()
    game.direction = "N"
    game.next_direction = ""
    target = snake_module.wrapped_step(0, 0, "N")
    game.food = [target]
    game._move_snake()
    assert game.snake[0] == target
    assert len(game.snake) == 2
    assert game.score == 1
    assert len(game.food) == 1
    emitted = snake_module.eventbus.emitted
    assert any(isinstance(e, snake_module.EmotePositiveEvent) for e in emitted)


def test_self_collision_ends_game(snake_module):
    game = snake_module.SnakeApp()
    # Build a snake that will run straight into its own neck.
    game.snake = [(0, 0), (0, -1), (1, -1)]
    game.food = []
    game.direction = "N"
    game.next_direction = ""
    game._move_snake()
    assert game.game == "OVER"
    assert game.snake == [(0, 0), (0, -1), (1, -1)]  # unchanged, move aborted
    emitted = snake_module.eventbus.emitted
    assert any(isinstance(e, snake_module.EmoteNegativeEvent) for e in emitted)


def test_game_over_creates_replay_dialog_once(snake_module):
    game = snake_module.SnakeApp()
    game.game = "OVER"
    game.update(delta=10)
    dialog = game.dialog
    assert dialog is not None
    assert dialog.on_yes == game._reset
    assert dialog.on_no == game._exit
    game.update(delta=10)
    assert game.dialog is dialog  # not rebuilt every frame


def test_button_steers_next_direction(snake_module):
    game = snake_module.SnakeApp()
    game.direction = "SE"  # not opposite of "N"
    button = _button_for(snake_module, "N")
    game.button_states.held.add(button)
    game.update(delta=0)
    assert game.next_direction == "N"
    # Still physically held (level state), but the steer is edge-triggered
    # so a second update while held shouldn't re-fire it.
    assert game.button_states.get(button) is True
    game.next_direction = ""
    game.update(delta=0)
    assert game.next_direction == ""


def test_cannot_reverse_directly_into_self(snake_module):
    game = snake_module.SnakeApp()
    game.direction = "N"
    game.next_direction = ""
    button = _button_for(snake_module, snake_module.OPPOSITE["N"])
    game.button_states.held.add(button)
    game.update(delta=0)
    assert game.next_direction == ""


def test_movement_only_ticks_after_step_ms(snake_module):
    game = snake_module.SnakeApp()
    game.food = []
    start_head = game.snake[0]
    game.update(delta=snake_module.STEP_MS - 1)
    assert game.snake[0] == start_head
    game.update(delta=1)
    assert game.snake[0] != start_head


def test_cancel_tap_steers_instead_of_quitting(snake_module):
    game = snake_module.SnakeApp()
    game.direction = "S"
    cancel_button = _button_for(snake_module, "NW")  # CANCEL maps to NW
    game.button_states.held.add(cancel_button)
    game.update(delta=snake_module.CANCEL_HOLD_MS - 1)
    assert game.minimised is False
    assert game.next_direction == "NW"


def test_holding_cancel_past_threshold_exits(snake_module):
    game = snake_module.SnakeApp()
    cancel_button = _button_for(snake_module, "NW")
    game.button_states.held.add(cancel_button)
    game.update(delta=snake_module.CANCEL_HOLD_MS)
    assert game.minimised is True


def test_holding_cancel_across_multiple_frames_exits(snake_module):
    # Regression: steering used to call button_states.clear() on every
    # consumed press, which wiped CANCEL's level state too (CANCEL maps to
    # NW, so it was consumed by the same steer branch) and reset the hold
    # timer every frame. Spread the hold over several small updates, the
    # way real per-tick polling would, instead of one big delta.
    game = snake_module.SnakeApp()
    cancel_button = _button_for(snake_module, "NW")
    game.button_states.held.add(cancel_button)
    per_frame = 50
    frames = snake_module.CANCEL_HOLD_MS // per_frame + 1
    for _ in range(frames):
        game.update(delta=per_frame)
    assert game.minimised is True


def test_flash_set_on_press_and_decays(snake_module):
    game = snake_module.SnakeApp()
    game.direction = "SE"  # not opposite of "N"
    button = _button_for(snake_module, "N")
    game.button_states.held.add(button)
    game.update(delta=0)
    assert game.flash["UP"] == snake_module.FLASH_MS

    game.button_states.held.discard(button)
    game.update(delta=snake_module.FLASH_MS)
    assert game.flash["UP"] == 0
