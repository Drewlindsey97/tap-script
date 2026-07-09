#!/usr/bin/env python3
"""Measure a skin's layout constants from real gameplay screenshots.

Detects the white card faces on the felt, splits them into the top slot row
and the tableau, and proposes a layout.json for the skin. The more
screenshots you feed it (early deal, mid-game with tall stacks, slots
occupied), the more constants it can pin down.

Usage:
    python3 tools/calibrate_layout.py shot1.png shot2.png ... --skin purple
    python3 tools/calibrate_layout.py shots/*.png --skin purple --write
    python3 tools/calibrate_layout.py shots/*.png --skin purple \
        --set hidden_card_h=23 --set foundation_x=[505] --write

What it can and can't measure:
- slot_y, slot_w, slot_h, free_cell_x, foundation_x: from white boxes in the
  top row (needs at least one shot with occupied slots to see them all).
- tableau_x, col_width, tableau_y_top, card_h: from tableau white boxes.
  tableau_y_top needs at least one column with no face-down cards on top
  (always true right after a deal).
- step: from the spacing of rank-glyph bands inside a stacked column (needs
  a shot with 3+ face-up cards piled in one column).
- hidden_card_h: NOT auto-measurable (face-down cards aren't white). It
  prints the measured face-down band height per column; divide by the count
  you can see in the screenshot and pass --set hidden_card_h=N.

Without --write it only prints the proposal. With --write it merges the
measured values over the skin's existing layout.json (or the classic
defaults) and saves.
"""

import argparse
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np

SKINS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skins")

WHITE_LO = np.array([0, 0, 180])
WHITE_HI = np.array([180, 60, 255])


def white_boxes(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, WHITE_LO, WHITE_HI)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 40 and h > 40:
            boxes.append((x, y, w, h))
    return boxes


def cluster(values, gap):
    """Group sorted 1-D values into clusters separated by more than `gap`."""
    out = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= gap:
            out[-1].append(v)
        else:
            out.append([v])
    return [int(round(sum(c) / len(c))) for c in out]


def estimate_step(img, box):
    """Spacing of rank-glyph rows inside a tall stacked column."""
    x, y, w, h = box
    if h < 200:
        return None
    strip = img[y:y + h, x:x + w]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    dark_rows = (gray < 140).sum(axis=1)
    # y positions where a new glyph band starts
    active = dark_rows > max(3, int(w * 0.03))
    starts = [i for i in range(1, len(active)) if active[i] and not active[i - 1]]
    diffs = [b - a for a, b in zip(starts, starts[1:]) if 15 <= b - a <= 100]
    if not diffs:
        return None
    return Counter(diffs).most_common(1)[0][0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="+", help="gameplay screenshot PNGs of the skin")
    ap.add_argument("--skin", required=True, help="skin name (directory under skins/)")
    ap.add_argument("--write", action="store_true", help="write the merged skins/<skin>/layout.json")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="manual override, e.g. --set hidden_card_h=23 (VALUE is parsed as JSON)")
    args = ap.parse_args()

    all_slot_boxes = []
    tableau_lefts = []
    tableau_tops = []
    card_heights = []
    card_widths = []
    step_votes = []
    facedown_notes = []

    for shot in args.shots:
        img = cv2.imread(shot)
        if img is None:
            print(f"[skip] cannot read {shot}")
            continue
        H, W = img.shape[:2]
        boxes = white_boxes(img)
        if not boxes:
            print(f"[skip] no card faces found in {shot}")
            continue

        # split slot row vs tableau at the biggest vertical gap between boxes
        tops = sorted(b[1] for b in boxes)
        split = None
        if len(tops) > 1:
            gaps = [(tops[i + 1] - tops[i], tops[i + 1]) for i in range(len(tops) - 1)]
            gap, at = max(gaps)
            if gap > 60:
                split = at
        slot_boxes = [b for b in boxes if split and b[1] < split]
        tab_boxes = [b for b in boxes if not split or b[1] >= split]

        all_slot_boxes.extend(slot_boxes)
        for x, y, w, h in tab_boxes:
            tableau_lefts.append(x)
            tableau_tops.append(y)
            card_widths.append(w)
            if h < 250:
                card_heights.append(h)
            s = estimate_step(img, (x, y, w, h))
            if s:
                step_votes.append(s)
        print(f"[ok] {shot}: {len(slot_boxes)} slot box(es), {len(tab_boxes)} tableau box(es)")

    if not tableau_lefts:
        print("No usable data found.", file=sys.stderr)
        sys.exit(1)

    proposal = {}

    col_x = cluster(tableau_lefts, gap=30)
    proposal["tableau_x"] = col_x
    if len(col_x) > 1:
        proposal["col_width"] = int(round((col_x[-1] - col_x[0]) / (len(col_x) - 1)))
    proposal["tableau_y_top"] = min(tableau_tops)
    if card_heights:
        proposal["card_h"] = int(np.median(card_heights))
    if card_widths:
        pass  # informational only; crops use col_width / slot_w

    if all_slot_boxes:
        proposal["slot_y"] = int(np.median([b[1] for b in all_slot_boxes]))
        proposal["slot_w"] = int(np.median([b[2] for b in all_slot_boxes]))
        slot_x = cluster([b[0] for b in all_slot_boxes], gap=30)
        print(f"\nSlot-row x positions seen: {slot_x}")
        print("  -> assign these to free_cell_x / foundation_x yourself (the")
        print("     script cannot know which slots are foundations vs waste/stock).")

    if step_votes:
        proposal["step"] = Counter(step_votes).most_common(1)[0][0]

    # face-down band: gap between the column origin and each white box top
    y_top = proposal["tableau_y_top"]
    bands = sorted({t - y_top for t in tableau_tops if t - y_top > 5})
    if bands:
        print(f"\nFace-down band heights seen above revealed cards: {bands}")
        print("  -> divide by the face-down card count visible in the screenshot")
        print("     and pass --set hidden_card_h=<result>")

    print("\nProposed measurements:")
    print(json.dumps(proposal, indent=4))

    for kv in args.set:
        key, _, val = kv.partition("=")
        proposal[key] = json.loads(val)

    if args.write:
        skin_dir = os.path.join(SKINS_ROOT, args.skin)
        layout_path = os.path.join(skin_dir, "layout.json")
        base_path = layout_path if os.path.exists(layout_path) else os.path.join(SKINS_ROOT, "classic", "layout.json")
        with open(base_path) as f:
            layout = json.load(f)
        layout.update(proposal)
        os.makedirs(skin_dir, exist_ok=True)
        with open(layout_path, "w") as f:
            json.dump(layout, f, indent=4)
            f.write("\n")
        print(f"\nWrote {layout_path} (merged over {base_path})")
    else:
        print("\n(dry run - pass --write to save into the skin's layout.json)")


if __name__ == "__main__":
    main()
