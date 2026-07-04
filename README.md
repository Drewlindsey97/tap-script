# tap-script

A tap/swipe automation bridge, plus a standalone FreeCell solver library.

## Bridge (`bridge.py`, `tap_script.py`)

`bridge.py` is a thin HTTP client for a local automation service listening on
`http://localhost:8080`:

- `tap(x, y)` - `POST /tap` with `{"x": x, "y": y}`
- `swipe(x1, y1, x2, y2)` - `POST /swipe` with `{"x1", "y1", "x2", "y2"}`
- `screenshot()` - `GET /screenshot`, returns a PIL Image

`tap_script.py` is a small demo loop built on top of it. Requires the
`requests` package, and Pillow if you use `screenshot()`.

## FreeCell solver (`freecell/`)

A self-contained FreeCell solver: state model, legal-move generation, and a
weighted best-first search. No dependency on screen-reading, OCR, or the
bridge above - just feed it a board and get back a move list.

```python
from freecell import Card, full_deck, solve
import random

deck = full_deck()
random.shuffle(deck)

columns = [[] for _ in range(8)]
for i, card in enumerate(deck):
    columns[i % 8].append(card)

result = solve(columns)
print(result.solved, len(result.moves))
```

`solve()` also accepts `free_cells` (list of `Card`) and `foundations` (dict
of suit -> count of cards already played) to start from a mid-game position.

See `example_solve.py` for a full runnable example.

## Tests

```
python3 -m unittest test_freecell -v
```

Stdlib `unittest` only, no extra dependencies. Takes ~20s (mostly the
full-shuffled-deck search).
