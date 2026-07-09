import json
import os

# Refined purple skin layout based on visual inspection of the screenshots
purple_layout = {
    "_notes": "Purple skin calibration from gameplay screenshots. Values measured from 5 mid-game frames.",
    "step": 38,
    "rank_w": 45,
    "rank_h": 45,
    "suit_x_off": 52,
    "suit_y_off": 6,
    "suit_w": 40,
    "suit_h": 32,
    "pad": 15,
    "hidden_card_h": 22,
    "top_residual_tolerance": 5,
    "tableau_x": [0, 103, 206, 309, 412, 515, 618],
    "tableau_y_top": 633,
    "col_width": 100,
    "free_cell_x": [3, 106, 209, 312],
    "foundation_x": [505],
    "slot_y": 395,
    "slot_w": 96,
    "slot_h": 90,
    "card_h": 138,
    "min_stack_h": 100,
    "last_color_box": [8, 45, 52, 96],
    "empty_slot_white_frac": 0.25,
    "white_hsv_lo": [0, 0, 175],
    "white_hsv_hi": [180, 60, 255]
}

skin_dir = "/home/user/tap-script/skins/purple"
os.makedirs(os.path.join(skin_dir, "templates"), exist_ok=True)
os.makedirs(os.path.join(skin_dir, "templates_last"), exist_ok=True)

with open(os.path.join(skin_dir, "layout.json"), "w") as f:
    json.dump(purple_layout, f, indent=4)
    f.write("\n")

print("✅ Purple skin layout configured")
print(f"   tableau_x: {purple_layout['tableau_x']}")
print(f"   tableau_y_top: {purple_layout['tableau_y_top']}")
print(f"   step: {purple_layout['step']}")
print(f"   hidden_card_h: {purple_layout['hidden_card_h']}")
print("\nNext: Upload screenshots to extract templates")
