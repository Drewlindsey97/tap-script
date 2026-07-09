#!/usr/bin/env python3
"""Crop template-ready card patches from gameplay screenshots.

For every screenshot given, uses the skin's layout.json to crop exactly the
patches the board reader will later match against:

- each buried face-up tableau card's rank corner  (rank_w x rank_h)
- each column's fully exposed bottom card         (slot_w x slot_h)
- each occupied top slot                          (slot_w x slot_h)

Crops land in a review directory named by position, e.g.
    review/frame01_col3_row0_rank.png
    review/frame01_col3_last.png
    review/frame01_free2_slot.png

Workflow for a new skin:
 1. python3 tools/extract_templates.py shots/*.png --skin purple
 2. Look at each crop, note its rank.
 3. python3 tools/cut_template.py --from-crop review/frame01_col3_last.png \
        --label 6 --skin purple
    (kind is inferred from the filename: *_rank.png -> templates/,
     *_last.png / *_slot.png -> templates_last/)

You only need ONE clean example per rank per template set (13 corner crops
+ 13 exposed-card crops covers the whole skin).
"""

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="+", help="gameplay screenshot PNGs")
    ap.add_argument("--skin", required=True, help="skin name (directory under skins/)")
    ap.add_argument("--out", default="template_review", help="output directory (default: template_review)")
    args = ap.parse_args()

    os.environ["SOLITAIRE_SKIN"] = args.skin
    import board_reader_lib as brl  # picks up the skin via the env var

    os.makedirs(args.out, exist_ok=True)
    saved = 0

    for shot in args.shots:
        img = cv2.imread(shot)
        if img is None:
            print(f"[skip] cannot read {shot}")
            continue
        stem = os.path.splitext(os.path.basename(shot))[0]

        for col_idx, x in enumerate(brl.TABLEAU_X):
            height, hidden_count, reliable = brl.detect_column_height(img, x)
            if height < brl.MIN_STACK_H:
                continue
            if not reliable:
                print(f"[warn] {shot} col{col_idx}: mid-animation frame, skipping column")
                continue
            revealed_span = height - hidden_count * brl.HIDDEN_CARD_H
            num_rows = max(1, round((revealed_span - brl.CARD_H) / brl.STEP) + 1)
            y_start = brl.TABLEAU_Y_TOP + hidden_count * brl.HIDDEN_CARD_H

            for row in range(num_rows):
                y = y_start + row * brl.STEP
                if row == num_rows - 1:
                    patch = img[y:y + brl.SLOT_H, x:x + brl.SLOT_W]
                    name = f"{stem}_col{col_idx}_last.png"
                else:
                    patch = img[y:y + brl.RANK_H, x:x + brl.RANK_W]
                    name = f"{stem}_col{col_idx}_row{row}_rank.png"
                cv2.imwrite(os.path.join(args.out, name), patch)
                saved += 1

        for kind, xs in (("free", brl.FREE_CELL_X), ("found", brl.FOUNDATION_X)):
            for i, x in enumerate(xs):
                patch = img[brl.SLOT_Y:brl.SLOT_Y + brl.SLOT_H, x:x + brl.SLOT_W]
                frac_white = (brl.white_mask(patch) > 0).mean()
                if frac_white < brl.EMPTY_SLOT_WHITE_FRAC:
                    continue
                name = f"{stem}_{kind}{i}_slot.png"
                cv2.imwrite(os.path.join(args.out, name), patch)
                saved += 1

    print(f"Saved {saved} crops to {args.out}/")


if __name__ == "__main__":
    main()
