import math
import random

from app_components import YesNoDialog, clear_background
from events.emote import EmoteNegativeEvent, EmotePositiveEvent
from events.input import BUTTON_TYPES, Buttons
from system.eventbus import eventbus

import app

# --- Hex grid geometry ------------------------------------------------
#
# The badge is a hexagon with a button on each of its 6 points, so the
# play field is a flat-top hex grid using axial coordinates (q, r).
# A flat-top hex's 6 neighbour directions point straight at the 6
# vertices of the badge outline, so each button maps to one direction.

HEX_SIZE = 14          # circumradius of one grid hex, in pixels
BOARD_N = 4             # board = all cells with cube-distance <= BOARD_N
STEP_MS = 400           # ms between snake moves

DIRS = {
    "N": (0, -1),
    "NE": (1, -1),
    "SE": (1, 0),
    "S": (0, 1),
    "SW": (-1, 1),
    "NW": (-1, 0),
}

OPPOSITE = {
    "N": "S", "S": "N",
    "NE": "SW", "SW": "NE",
    "SE": "NW", "NW": "SE",
}

# Buttons sit at the 6 points of the badge; map each to the hex
# direction that points at that point.
BUTTON_DIR = {
    "UP": "N",
    "RIGHT": "NE",
    "CONFIRM": "SE",
    "DOWN": "S",
    "CANCEL": "NW",
    "LEFT": "SW",
}

CANCEL_HOLD_MS = 1000   # hold CANCEL this long to quit
FLASH_MS = 150          # how long a pressed button's wedge stays lit


def axial_to_px(q, r):
    x = HEX_SIZE * 1.5 * q
    y = HEX_SIZE * math.sqrt(3) * (r + q / 2)
    return x, y


def on_board(q, r):
    return max(abs(q), abs(r), abs(q + r)) <= BOARD_N


def board_cells():
    cells = []
    for q in range(-BOARD_N, BOARD_N + 1):
        for r in range(-BOARD_N, BOARD_N + 1):
            if on_board(q, r):
                cells.append((q, r))
    return cells


# --- Precomputed static geometry ---------------------------------------
#
# All of this is fixed for the life of the program, so it's computed once
# here rather than every draw() call. draw() runs every frame and every
# millisecond it spends recomputing trig is a millisecond the input poll
# isn't running, so cheap frames mean fewer missed button presses.

# Unit-circle vertices of a flat-top hex; hex_path() just scales these.
UNIT_HEX = [
    (math.cos(math.radians(60 * i)), math.sin(math.radians(60 * i)))
    for i in range(6)
]

BOARD_CELLS = board_cells()
BOARD_PX = [axial_to_px(q, r) for (q, r) in BOARD_CELLS]

# Angle (radians, screen space) each button's direction points at, derived
# from the same DIRS/axial_to_px used for movement so the feedback wedges
# always line up with where that direction actually moves the snake.
BUTTON_ANGLE = {}
for _name, _direction in BUTTON_DIR.items():
    _dx, _dy = axial_to_px(*DIRS[_direction])
    BUTTON_ANGLE[_name] = math.atan2(_dy, _dx)
del _name, _direction, _dx, _dy

# Furthest any drawn board hex actually reaches from center: every vertex
# of every board tile, exact (not a guessed radius), so the wedge ring
# can't overlap the board no matter which axis it's measured along.
_BOARD_TILE_SIZE = HEX_SIZE - 1  # matches the tile radius used in draw()


def _hypot(x, y):
    # math.hypot() doesn't exist on MicroPython.
    return math.sqrt(x * x + y * y)


BOARD_REACH_PX = max(
    _hypot(cx + _BOARD_TILE_SIZE * ux, cy + _BOARD_TILE_SIZE * uy)
    for (cx, cy) in BOARD_PX
    for (ux, uy) in UNIT_HEX
)

WEDGE_INNER_R = BOARD_REACH_PX + 4     # just outside the board
WEDGE_OUTER_R = 118                    # inside the ~120px screen edge
WEDGE_HALF_SPAN = math.radians(25)     # wedge covers +/- this much
WEDGE_ARC_STEPS = 4                    # line segments approximating each arc


def _wedge_polygon(angle):
    # Outer arc one way, inner arc back the other way, closed into a ring
    # segment. Computed once per button at import time; draw() just walks
    # the resulting point list.
    a0, a1 = angle - WEDGE_HALF_SPAN, angle + WEDGE_HALF_SPAN
    points = []
    for i in range(WEDGE_ARC_STEPS + 1):
        t = a0 + (a1 - a0) * i / WEDGE_ARC_STEPS
        points.append((WEDGE_OUTER_R * math.cos(t), WEDGE_OUTER_R * math.sin(t)))
    for i in range(WEDGE_ARC_STEPS + 1):
        t = a1 - (a1 - a0) * i / WEDGE_ARC_STEPS
        points.append((WEDGE_INNER_R * math.cos(t), WEDGE_INNER_R * math.sin(t)))
    return points


WEDGE_POLY = {name: _wedge_polygon(angle) for name, angle in BUTTON_ANGLE.items()}


def _wrap_bounds(f):
    # Range of the position coordinate along a straight hex line whose
    # fixed cube coordinate is f, so the wrapped step re-enters on the
    # opposite edge of the *same* line rather than teleporting anywhere.
    if f >= 0:
        return -BOARD_N, BOARD_N - f
    return -BOARD_N - f, BOARD_N


def wrapped_step(q, r, direction):
    dq, dr = DIRS[direction]
    nq, nr = q + dq, r + dr
    if on_board(nq, nr):
        return nq, nr
    if direction in ("N", "S"):
        lo, hi = _wrap_bounds(q)
        nr = lo + (nr - lo) % (hi - lo + 1)
        return q, nr
    if direction in ("NE", "SW"):
        s = -(q + r)
        lo, hi = _wrap_bounds(s)
        nq = lo + (nq - lo) % (hi - lo + 1)
        return nq, -s - nq
    # SE, NW: r is the fixed coordinate.
    lo, hi = _wrap_bounds(r)
    nq = lo + (nq - lo) % (hi - lo + 1)
    return nq, r


def hex_path(ctx, cx, cy, size=HEX_SIZE):
    # Flat-top hex: vertices at 0, 60, 120, ... degrees.
    for i, (ux, uy) in enumerate(UNIT_HEX):
        x = cx + size * ux
        y = cy + size * uy
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.close_path()


def wedge_path(ctx, name):
    for i, (x, y) in enumerate(WEDGE_POLY[name]):
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.close_path()


def _lerp(a, b, t):
    return a + (b - a) * t


class SnakeApp(app.App):
    def __init__(self):
        super().__init__()
        self.button_states = Buttons(self)
        self.cancel_held_ms = 0
        self._reset()

    def _reset(self):
        self.snake = [(0, 0)]
        self.food = []
        self.direction = random.choice(list(DIRS))
        self.next_direction = ""
        self.step = 0
        self.score = 0
        self.dialog = None
        self.game = "ON"
        self.flash = {name: 0.0 for name in BUTTON_DIR}
        self._spawn_food()

    def _exit(self):
        self._reset()
        self.button_states.clear()
        self.minimise()

    def _spawn_food(self):
        occupied = set(self.snake) | set(self.food)
        candidates = [c for c in BOARD_CELLS if c not in occupied]
        if candidates:
            self.food.append(random.choice(candidates))

    def update(self, delta):
        for name in self.flash:
            if self.flash[name] > 0:
                self.flash[name] = max(0.0, self.flash[name] - delta)

        # Hold CANCEL to quit; a short tap just steers NW. This reads
        # level state (get), not the edge-triggered steer below, so a
        # held button keeps accumulating instead of getting reset.
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.flash["CANCEL"] = FLASH_MS
            self.cancel_held_ms += delta
            if self.cancel_held_ms >= CANCEL_HOLD_MS:
                self.button_states.clear()
                self.cancel_held_ms = 0
                self._exit()
                return
        else:
            self.cancel_held_ms = 0

        if self.game == "ON":
            for name, direction in BUTTON_DIR.items():
                # Edge-triggered: fires once per press, self-latches per
                # button, so handling one button doesn't wipe every other
                # button's in-flight state (that used to break the CANCEL
                # hold-to-quit timer above).
                if self.button_states.pressed(BUTTON_TYPES[name]):
                    self.flash[name] = FLASH_MS
                    if direction != OPPOSITE.get(self.direction, ""):
                        self.next_direction = direction
                    break

            self.step += delta
            if self.step >= STEP_MS:
                self.step = 0
                self._move_snake()
        elif self.game == "OVER" and self.dialog is None:
            self.dialog = YesNoDialog(
                message=["Game Over.", "Play Again?"],
                on_yes=self._reset,
                on_no=self._exit,
                app=self,
            )

    def _move_snake(self):
        if not self.next_direction and not self.direction:
            return
        self.direction = self.next_direction or self.direction

        head_q, head_r = self.snake[0]
        new_head = wrapped_step(head_q, head_r, self.direction)

        if new_head in self.snake:
            self.game = "OVER"
            eventbus.emit(EmoteNegativeEvent())
            return

        self.snake = [new_head] + self.snake

        if new_head in self.food:
            self.food.remove(new_head)
            self.score += 1
            eventbus.emit(EmotePositiveEvent())
            self._spawn_food()
        else:
            self.snake = self.snake[:-1]

    def draw(self, ctx):
        clear_background(ctx)

        ctx.save()

        # Button feedback ring: a faint wedge at each of the 6 button
        # positions, always visible as a control-layout guide, brightening
        # to an accent colour on press and fading back out over FLASH_MS.
        base = (0.15, 0.15, 0.2)
        bright = (1.0, 0.8, 0.2)
        for name in BUTTON_DIR:
            t = self.flash.get(name, 0.0) / FLASH_MS
            ctx.rgb(_lerp(base[0], bright[0], t),
                    _lerp(base[1], bright[1], t),
                    _lerp(base[2], bright[2], t))
            wedge_path(ctx, name)
            ctx.fill()

        # Board.
        for cx, cy in BOARD_PX:
            ctx.rgb(0.08, 0.08, 0.1)
            hex_path(ctx, cx, cy, HEX_SIZE - 1)
            ctx.fill()

        # Food.
        for q, r in self.food:
            cx, cy = axial_to_px(q, r)
            ctx.rgb(0, 1, 0)
            hex_path(ctx, cx, cy, HEX_SIZE - 2)
            ctx.fill()

        # Snake.
        for i, (q, r) in enumerate(self.snake):
            cx, cy = axial_to_px(q, r)
            if i == 0:
                ctx.rgb(0.4, 0.6, 1)
            else:
                ctx.rgb(0, 0, 1)
            hex_path(ctx, cx, cy, HEX_SIZE - 2)
            ctx.fill()

        ctx.restore()

        # Score.
        ctx.save()
        ctx.font_size = 14
        score_text = "Score: {}".format(self.score)
        width = ctx.text_width(score_text)
        ctx.rgb(1, 1, 1).move_to(0 - width / 2, 105).text(score_text)
        ctx.restore()

        if self.dialog:
            self.dialog.draw(ctx)


__app_export__ = SnakeApp
