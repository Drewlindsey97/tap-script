import random
import time

from freecell import Card, full_deck, solve

random.seed(42)
deck = full_deck()
random.shuffle(deck)

columns = [[] for _ in range(8)]
for i, card in enumerate(deck):
    columns[i % 8].append(card)

print("Dealt columns:")
for i, col in enumerate(columns):
    print(f"  col{i}: {[f'{c.rank}{c.suit}' for c in col]}")

start = time.time()
result = solve(columns)
elapsed = time.time() - start

if result.solved:
    print(f"\nSOLVED in {len(result.moves)} moves (explored {result.explored} states, {elapsed:.1f}s)")
    for move in result.moves[:15]:
        print(" ", move)
else:
    label = "PROVEN UNSOLVABLE" if result.status == "exhausted" else "MEMORY CAP HIT (not proven either way)"
    print(f"\n{label} (explored {result.explored} states, {elapsed:.1f}s)")
    print("Best partial line found:")
    for move in result.moves[:15]:
        print(" ", move)
