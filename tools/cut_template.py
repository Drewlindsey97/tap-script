#!/usr/bin/env python3
"""Save a labeled rank template into a skin's template set.

Two ways to use it:

1. From a crop produced by tools/extract_templates.py (kind inferred from
   the *_rank / *_last / *_slot filename suffix):

       python3 tools/cut_template.py --from-crop template_review/f1_col3_last.png \
           --label 6 --skin purple

2. Straight from a full screenshot, naming the position (replaces the old
   one-off add_template_*.py scripts):

       python3 tools/cut_template.py --frame shot.png --col 3 --row last \
           --label 6 --skin purple
       python3 tools/cut_template.py --frame shot.png --col 2 --row 0 \
           --label 9 --skin purple
       python3 tools/cut_template.py --frame shot.png --slot free1 \
           --label A --skin purple

Corner-rank crops go to skins/<skin>/templates/<LABEL>.png, exposed-card
crops to skins/<skin>/templates_last/<LABEL>.png.
"""

import argparse
import os
import shutil
import sys

import cv2

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, REPO_ROOT)

VALID_LABELS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def dest_path(skin, kind, label):
    sub = "templates" if kind == "corner" else "templates_last"
    d = os.path.join(REPO_ROOT, "skins", skin, sub)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{label}.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skin", required=True)
    ap.add_argument("--label", required=True, choices=VALID_LABELS)
    ap.add_argument("--from-crop", help="crop file from tools/extract_templates.py")
    ap.add_argument("--kind", choices=["corner", "last"],
                    help="template set to write (only needed if not inferrable)")
    ap.add_argument("--frame", help="full screenshot to crop from")
    ap.add_argument("--col", type=int, help="tableau column index (with --frame)")
    ap.add_argument("--row", help="face-up row index from the top, or 'last' (with --frame)")
    ap.add_argument("--slot", help="'free0'..'free3' or 'found0' (with --frame)")
    args = ap.parse_args()

    if args.from_crop:
        kind = args.kind
        if kind is None:
            if args.from_crop.endswith("_rank.png"):
                kind = "corner"
            elif args.from_crop.endswith(("_last.png", "_slot.png")):
                kind = "last"
            else:
                ap.error("cannot infer --kind from filename; pass --kind corner|last")
        out = dest_path(args.skin, kind, args.label)
        shutil.copyfile(args.from_crop, out)
        print(f"Saved {out}")
        return

    if not args.frame:
        ap.error("pass either --from-crop or --frame")

    os.environ["SOLITAIRE_SKIN"] = args.skin
    import board_reader_lib as brl

    img = cv2.imread(args.frame)
    if img is None:
        ap.error(f"cannot read {args.frame}")

    if args.slot:
        xs = {"free": brl.FREE_CELL_X, "found": brl.FOUNDATION_X}[args.slot[:-1].rstrip("0123456789") or "free"]
        prefix = "free" if args.slot.startswith("free") else "found"
        idx = int(args.slot[len(prefix):])
        x = (brl.FREE_CELL_X if prefix == "free" else brl.FOUNDATION_X)[idx]
        patch = img[brl.SLOT_Y:brl.SLOT_Y + brl.SLOT_H, x:x + brl.SLOT_W]
        kind = "last"
    elif args.col is not None and args.row is not None:
        x = brl.TABLEAU_X[args.col]
        height, hidden_count, reliable = brl.detect_column_height(img, x)
        if height < brl.MIN_STACK_H:
            ap.error(f"col{args.col} looks empty in {args.frame}")
        revealed_span = height - hidden_count * brl.HIDDEN_CARD_H
        num_rows = max(1, round((revealed_span - brl.CARD_H) / brl.STEP) + 1)
        y_start = brl.TABLEAU_Y_TOP + hidden_count * brl.HIDDEN_CARD_H
        if args.row == "last":
            y = y_start + (num_rows - 1) * brl.STEP
            patch = img[y:y + brl.SLOT_H, x:x + brl.SLOT_W]
            kind = "last"
        else:
            row = int(args.row)
            if row >= num_rows - 1:
                ap.error(f"row {row} is the exposed card; use --row last")
            y = y_start + row * brl.STEP
            patch = img[y:y + brl.RANK_H, x:x + brl.RANK_W]
            kind = "corner"
    else:
        ap.error("with --frame, pass --col N --row K|last, or --slot freeN|foundN")

    out = dest_path(args.skin, args.kind or kind, args.label)
    cv2.imwrite(out, patch)
    print(f"Saved {out} ({patch.shape[1]}x{patch.shape[0]})")


if __name__ == "__main__":
    main()
