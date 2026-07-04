import random
import time

from bridge import tap, swipe


def random_delay():
    time.sleep(random.uniform(0.2, 0.8))


if __name__ == "__main__":
    while True:
        tap(500, 800)
        random_delay()
        swipe(300, 1200, 300, 400)
        random_delay()
