# tap-script

A tap/swipe automation bridge, a standalone FreeCell solver library, and a
skin-aware OCR board reader + auto-player for Solitaire Stash.

## Solitaire bot (`solitaire_auto_bot.py`, `board_reader_lib.py`, `skins/`)

`board_reader_lib.py` reads the game board from a screenshot with OpenCV
template matching. All skin-specific data lives under `skins/<name>/`:

- `layout.json` - screen geometry (column x positions, slot row, card
  stacking offsets, ...)
- `templates/` - rank-corner glyph templates for buried face-up cards
- `templates_last/` - larger templates for fully exposed cards and top slots

Pick the skin with an environment variable (default `classic`):

```
SOLITAIRE_SKIN=purple python3 solitaire_auto_bot.py            # live device
python3 solitaire_auto_bot.py --sim screenshot.png             # dry run
```

### Teaching it a new skin

1. Collect a handful of gameplay screenshots (PNG, native resolution) of the
   new skin: one right after a deal, a few mid-game with tall stacks and
   occupied top slots.
2. Calibrate the geometry:
   `python3 tools/calibrate_layout.py shots/*.png --skin myskin --write`
   (it prints anything it can't measure automatically and how to `--set` it).
3. Extract labeled-by-position card crops:
   `python3 tools/extract_templates.py shots/*.png --skin myskin`
4. Look at each crop in `template_review/` and file it under its rank:
   `python3 tools/cut_template.py --from-crop template_review/<crop>.png --label 6 --skin myskin`
   One clean example per rank per template set is enough (13 corner + 13
   exposed-card templates).
5. Verify: `SOLITAIRE_SKIN=myskin python3 solitaire_auto_bot.py --sim shot.png`
   and check the printed board against the screenshot.

The bundled `purple` skin was calibrated this way and reads at ~99%
accuracy on real captures. Its template set is verified for every rank
except 3, which never appeared face-up in the calibration recording -
when you see a 3 in play, screenshot it and file it with cut_template.py
(both a corner and an exposed-card example).

Requires `opencv-python` and `numpy`.

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
