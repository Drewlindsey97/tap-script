"""Skin-aware solitaire board reader.

Ported from the original Solitaire_Bot board_reader_lib.py, with every
layout constant and template image moved into a per-skin directory so the
same reading logic can serve multiple card skins:

    skins/<name>/layout.json       - geometry constants (see below)
    skins/<name>/templates/        - rank glyph templates for buried
                                     (partially covered) face-up cards
    skins/<name>/templates_last/   - larger templates for the fully
                                     exposed bottom card of a column and
                                     for cards sitting in the top slots

Select the skin with the SOLITAIRE_SKIN environment variable (default:
"classic"), e.g.:

    SOLITAIRE_SKIN=purple python3 solitaire_auto_bot.py

The public module-level names (read_board, TABLEAU_X, SLOT_Y, ...) are
kept identical to the original so existing callers work unchanged.
"""

import glob
import json
import os

import cv2
import numpy as np

SKIN = os.environ.get("SOLITAIRE_SKIN", "classic")
SKIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", SKIN)

with open(os.path.join(SKIN_DIR, "layout.json")) as f:
    LAYOUT = json.load(f)

STEP = LAYOUT["step"]
RANK_W, RANK_H = LAYOUT["rank_w"], LAYOUT["rank_h"]
SUIT_X_OFF, SUIT_Y_OFF = LAYOUT["suit_x_off"], LAYOUT["suit_y_off"]
SUIT_W, SUIT_H = LAYOUT["suit_w"], LAYOUT["suit_h"]
PAD = LAYOUT["pad"]
HIDDEN_CARD_H = LAYOUT["hidden_card_h"]
TOP_RESIDUAL_TOLERANCE = LAYOUT["top_residual_tolerance"]

# fixed x-start positions for each tableau column (UI layout doesn't move)
TABLEAU_X = LAYOUT["tableau_x"]
TABLEAU_Y_TOP = LAYOUT["tableau_y_top"]
COL_WIDTH = LAYOUT["col_width"]

FREE_CELL_X = LAYOUT["free_cell_x"]
FOUNDATION_X = LAYOUT["foundation_x"]
SLOT_Y = LAYOUT["slot_y"]
SLOT_W, SLOT_H = LAYOUT["slot_w"], LAYOUT["slot_h"]

# full on-screen height of one card, used to derive how many stacked rows a
# column's revealed span holds
CARD_H = LAYOUT["card_h"]
# revealed spans shorter than this are treated as an empty column / noise
MIN_STACK_H = LAYOUT["min_stack_h"]
# (dy1, dy2, dx1, dx2) box within a fully exposed card where the suit pip
# sits, sampled for red/black classification
LAST_COLOR_BOX = LAYOUT["last_color_box"]
# a top slot counts as occupied only if at least this fraction of its pixels
# are card-face white (empty slots show felt / a ghost outline, not white)
EMPTY_SLOT_WHITE_FRAC = LAYOUT["empty_slot_white_frac"]

WHITE_HSV_LO = np.array(LAYOUT["white_hsv_lo"])
WHITE_HSV_HI = np.array(LAYOUT["white_hsv_hi"])

# bottom edge of the tableau scan region; excludes UI chrome (e.g. white
# footer buttons) that would otherwise read as huge card stacks. None means
# scan to the bottom of the screenshot (classic-skin behavior).
TABLEAU_Y_BOTTOM = LAYOUT.get("tableau_y_bottom")

# Skins whose face-down cards are white-faced with a colored stripe (instead
# of a fully colored back) can't use the white-mask top-offset trick to count
# hidden cards - the white mask sees the face-down cards too. For those skins
# set facedown_hsv_lo/hi to the stripe color and hidden cards are counted by
# detecting the stripes directly.
FACEDOWN_HSV_LO = np.array(LAYOUT["facedown_hsv_lo"]) if "facedown_hsv_lo" in LAYOUT else None
FACEDOWN_HSV_HI = np.array(LAYOUT["facedown_hsv_hi"]) if "facedown_hsv_hi" in LAYOUT else None

# a revealed span shorter than this holds no readable face-up card (the
# column is empty or all face-down)
MIN_REVEALED_H = LAYOUT.get("min_revealed_h", 60)


def load_templates(folder):
    t = {}
    for path in glob.glob(f"{folder}/*.png"):
        name = os.path.splitext(os.path.basename(path))[0]
        gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        t[name] = binary
    return t


TEMPLATES = load_templates(os.path.join(SKIN_DIR, "templates"))
TEMPLATES_LAST = load_templates(os.path.join(SKIN_DIR, "templates_last"))


def white_mask(patch):
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, WHITE_HSV_LO, WHITE_HSV_HI)


def classify_suit_color(patch):
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    mask = gray < 200
    if mask.sum() < 5:
        return "?"
    b, g, r = patch[mask].mean(axis=0)
    if r > g + 15 and r > b:
        return "RED"
    return "BLACK"


def match_rank(patch, template_set):
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    padded = cv2.copyMakeBorder(binary, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=0)

    best_name, best_score = "?", -1
    for name, tmpl in template_set.items():
        if tmpl.shape[0] > padded.shape[0] or tmpl.shape[1] > padded.shape[1]:
            continue
        result = cv2.matchTemplate(padded, tmpl, cv2.TM_CCOEFF_NORMED)
        score = result.max()
        if score > best_score:
            best_score = score
            best_name = name
    return best_name, best_score


def detect_column_height(img, x):
    """Detect how tall the card stack in this column currently is, using
    white-region contour detection.

    The white mask only picks up face-up (revealed) cards; face-down cards at
    the top of a column render as a uniform sliver per card that the mask
    doesn't see, so the revealed region's top edge sits that much lower than
    the column origin. Returns (height, hidden_count, reliable):
    - height: pixel bottom of the revealed region
    - hidden_count: how many face-down cards sit above the revealed region,
      inferred from that top offset
    - reliable: False when the top offset doesn't cleanly fit a whole number
      of hidden cards - a sign of a mid-animation render rather than a real,
      stable hidden-card count
    """
    col_slice = img[TABLEAU_Y_TOP:TABLEAU_Y_BOTTOM, x:x + COL_WIDTH]
    mask = white_mask(col_slice)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0, 0, True

    max_y, min_y = 0, None
    for c in contours:
        cx, cy, cw, ch = cv2.boundingRect(c)
        if cw > 30 and ch > 20:
            max_y = max(max_y, cy + ch)
            min_y = cy if min_y is None else min(min_y, cy)

    if min_y is None:
        return 0, 0, True

    if FACEDOWN_HSV_LO is not None:
        # count face-down cards by their colored stripes: one stripe band per
        # face-down card, stacked at HIDDEN_CARD_H pitch from the column top
        hsv = cv2.cvtColor(col_slice, cv2.COLOR_BGR2HSV)
        fd = cv2.inRange(hsv, FACEDOWN_HSV_LO, FACEDOWN_HSV_HI)
        rows = np.where(fd.sum(axis=1) > COL_WIDTH * 0.3 * 255)[0]
        bands = []
        prev = None
        for r in rows:
            if prev is None or r - prev > 3:
                bands.append([r, r])
            else:
                bands[-1][1] = r
            prev = r
        bands = [b for b in bands if b[1] - b[0] >= 4]
        hidden_count = len(bands)
        # a stable stack has its stripes at a regular pitch starting at the
        # column top; anything else is a mid-animation frame
        reliable = all(
            abs(b[0] - i * HIDDEN_CARD_H) <= TOP_RESIDUAL_TOLERANCE + 8
            for i, b in enumerate(bands)
        )
        return max_y, hidden_count, reliable

    hidden_count = round(min_y / HIDDEN_CARD_H)
    residual = abs(min_y - hidden_count * HIDDEN_CARD_H)
    reliable = residual <= TOP_RESIDUAL_TOLERANCE
    return max_y, hidden_count, reliable  # bottom pixel of the revealed region


def read_board(frame_path):
    img = cv2.imread(frame_path)
    if img is None:
        raise FileNotFoundError(frame_path)

    board = {}
    for col_idx, x in enumerate(TABLEAU_X):
        height, hidden_count, reliable = detect_column_height(img, x)
        col_cards = []

        if height < MIN_STACK_H:  # empty or noise, treat as empty column
            board[f"col{col_idx}"] = col_cards
            continue

        revealed_span = height - hidden_count * HIDDEN_CARD_H
        if hidden_count and revealed_span < MIN_REVEALED_H:
            # only face-down cards in this column, nothing readable
            col_cards.extend({"rank": "?", "color": "?", "score": 0.0} for _ in range(hidden_count))
            board[f"col{col_idx}"] = col_cards
            continue
        num_rows = round((revealed_span - CARD_H) / STEP) + 1
        num_rows = max(1, num_rows)

        # face-down cards have no readable rank; represent them as unknown
        # rather than feeding their pixels into the rank matcher
        col_cards.extend({"rank": "?", "color": "?", "score": 0.0} for _ in range(hidden_count))

        y_start = TABLEAU_Y_TOP + hidden_count * HIDDEN_CARD_H
        for row in range(num_rows):
            y = y_start + row * STEP
            is_last = (row == num_rows - 1)

            if is_last:
                rank_patch = img[y:y + SLOT_H, x:x + SLOT_W]
                name, score = match_rank(rank_patch, TEMPLATES_LAST)
                dy1, dy2, dx1, dx2 = LAST_COLOR_BOX
                color = classify_suit_color(img[y + dy1:y + dy2, x + dx1:x + dx2])
            else:
                rank_patch = img[y:y + RANK_H, x:x + RANK_W]
                name, score = match_rank(rank_patch, TEMPLATES)
                suit_patch = img[y + SUIT_Y_OFF:y + SUIT_Y_OFF + SUIT_H,
                                 x + SUIT_X_OFF:x + SUIT_X_OFF + SUIT_W]
                color = classify_suit_color(suit_patch)

            # a top offset that doesn't cleanly fit a whole number of hidden
            # cards means this frame is mid-animation, not a stable state -
            # every row crop here is misaligned regardless of match_rank's score
            if not reliable:
                score = 0.0

            col_cards.append({"rank": name, "color": color, "score": round(float(score), 2)})

        board[f"col{col_idx}"] = col_cards

    def read_slot(x):
        patch = img[SLOT_Y:SLOT_Y + SLOT_H, x:x + SLOT_W]
        # occupied slots hold a white card face; empty ones show felt or a
        # ghost outline, so almost none of their pixels pass the white mask
        frac_white = (white_mask(patch) > 0).mean()
        if frac_white < EMPTY_SLOT_WHITE_FRAC:
            return None
        name, score = match_rank(patch, TEMPLATES_LAST)
        dy1, dy2, dx1, dx2 = LAST_COLOR_BOX
        color = classify_suit_color(img[SLOT_Y + dy1:SLOT_Y + dy2, x + dx1:x + dx2])
        return {"rank": name, "color": color, "score": round(float(score), 2)}

    board["free_cells"] = [read_slot(x) for x in FREE_CELL_X]
    board["foundation"] = [read_slot(x) for x in FOUNDATION_X]

    return board
