import io

import requests

BASE_URL = "http://localhost:8080"


def tap(x, y):
    print(f"Tap at ({x}, {y})")
    try:
        requests.post(f"{BASE_URL}/tap", json={"x": x, "y": y}, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"Tap request failed: {e}")


def swipe(x1, y1, x2, y2):
    print(f"Swipe from ({x1}, {y1}) to ({x2}, {y2})")
    try:
        requests.post(
            f"{BASE_URL}/swipe",
            json={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            timeout=5,
        )
    except requests.exceptions.RequestException as e:
        print(f"Swipe request failed: {e}")


def screenshot():
    """Fetch a screenshot from the bridge and return it as a PIL Image."""
    from PIL import Image

    resp = requests.get(f"{BASE_URL}/screenshot", timeout=10)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")
