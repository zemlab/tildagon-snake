def test_board_cell_count_matches_hexagonal_number(snake_module):
    n = snake_module.BOARD_N
    assert len(snake_module.board_cells()) == 3 * n * (n + 1) + 1


def test_on_board_accepts_boundary_rejects_beyond(snake_module):
    n = snake_module.BOARD_N
    assert snake_module.on_board(n, 0)
    assert snake_module.on_board(0, -n)
    assert snake_module.on_board(-n, n)
    assert not snake_module.on_board(n + 1, 0)
    assert not snake_module.on_board(0, -n - 1)


def test_wrapped_step_always_lands_on_board(snake_module):
    for q, r in snake_module.board_cells():
        for direction in snake_module.DIRS:
            nq, nr = snake_module.wrapped_step(q, r, direction)
            assert snake_module.on_board(nq, nr), (q, r, direction, nq, nr)


def test_wrapped_step_cycles_back_to_start_on_same_line(snake_module):
    # Repeatedly stepping in one direction should return to the origin
    # cell having visited every cell on that line exactly once - i.e.
    # wrap re-enters the *same* line, not an arbitrary board cell.
    for q, r in snake_module.board_cells():
        for direction in snake_module.DIRS:
            cq, cr = q, r
            seen = set()
            for _ in range(2 * snake_module.BOARD_N + 2):
                seen.add((cq, cr))
                cq, cr = snake_module.wrapped_step(cq, cr, direction)
                if (cq, cr) == (q, r):
                    break
            else:
                raise AssertionError(f"no cycle back to start from {(q, r)} going {direction}")
            assert (cq, cr) == (q, r)


def test_button_direction_mapping_covers_all_six_directions_bijectively(snake_module):
    assert set(snake_module.BUTTON_DIR.values()) == set(snake_module.DIRS.keys())
    assert len(snake_module.BUTTON_DIR) == 6
    assert len(set(snake_module.BUTTON_DIR.values())) == 6


def test_opposite_is_a_fixed_point_free_involution(snake_module):
    for direction in snake_module.DIRS:
        opposite = snake_module.OPPOSITE[direction]
        assert opposite != direction
        assert snake_module.OPPOSITE[opposite] == direction
