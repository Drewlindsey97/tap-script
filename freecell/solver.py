import heapq
import itertools
import time
from collections import namedtuple

from .cards import rank_value
from .state import State, auto_play_safe, generate_moves, apply_move

SolveResult = namedtuple("SolveResult", ["moves", "explored", "solved", "status"])


def is_solved(state, total_cards):
    return sum(state.foundation_ranks().values()) == total_cards


def heuristic(state, total_cards):
    """Estimated work remaining: cards not yet on foundation, penalized for
    columns that bury a currently-playable card under others, and rewarded
    for empty columns / open free cells (both give the search room to
    maneuver)."""
    foundation_ranks = state.foundation_ranks()
    base = total_cards - sum(foundation_ranks.values())

    penalty = 0
    for col in state.columns:
        for i, card in enumerate(col):
            needed = foundation_ranks.get(card.suit, 0) + 1
            if rank_value(card) == needed and i != len(col) - 1:
                penalty += (len(col) - 1 - i) * 2

    empty_bonus = sum(1 for c in state.columns if not c) * 3
    free_bonus = 4 - len(state.free_cells)

    return max(0, base + penalty - empty_bonus - free_bonus)


def solve(columns, free_cells=None, foundations=None,
          weight=5, max_seen=3_000_000, progress_every=100_000):
    """
    Weighted best-first search (f = g + weight*h) over single-card FreeCell
    moves: free cell <-> foundation/column, column top <-> foundation/free
    cell/column. Runs until the game is won or every reachable state has
    been explored with no solution found (proven stuck) - the `seen` dedup
    guarantees this terminates, since the state space for a fixed deck is
    finite. Safe foundation plays (see state.auto_play_safe) are collapsed
    into a single forced step instead of being separate branch choices.

    weight > 1 biases the search to favor heuristic progress over path
    length - plain A* (weight=1) treats every state tied on heuristic value
    as equally worth exploring, which blows up into a breadth-first-like
    search across huge plateaus. We only need *a* solution, not the
    shortest one, so trading path optimality for a search that actually
    converges is the right tradeoff.

    max_seen is a memory safety valve, not a search-quality cap: if state
    tracking grows past it the run stops and says so explicitly, rather
    than growing until the OS kills the process with no explanation.

    columns: list of lists of Card, one list per tableau column.
    free_cells: list of Card currently held in free cells (default: none).
    foundations: dict of suit -> count of cards already played for that
        suit, e.g. {"H": 4} means A-4 of hearts are already on foundation
        (default: empty).

    Returns SolveResult(moves, explored, solved, status), where status is
    "solved", "exhausted" (proven unsolvable), or "capped" (memory limit
    hit before either could be determined - moves is the best partial line
    seen).
    """
    free_cells = free_cells or []
    foundations = foundations or {}
    raw_start = State(columns, free_cells, foundations)
    start, start_moves = auto_play_safe(raw_start)

    total_cards = raw_start.total_cards()

    counter = itertools.count()
    open_set = [(weight * heuristic(start, total_cards), next(counter), start, start_moves, None)]
    seen = {start.key(): 0}

    best_path = start_moves
    best_h = heuristic(start, total_cards)

    explored = 0
    start_time = time.time()

    while open_set:
        _, _, state, path, last_move = heapq.heappop(open_set)
        explored += 1

        if progress_every and explored % progress_every == 0:
            elapsed = time.time() - start_time
            print(f"  ...explored {explored} states, {len(open_set)} queued, "
                  f"best remaining={best_h}, {elapsed:.0f}s elapsed")

        h = heuristic(state, total_cards)
        if h < best_h:
            best_h = h
            best_path = path

        if is_solved(state, total_cards):
            return SolveResult(path, explored, True, "solved")

        if len(seen) >= max_seen:
            print(f"  ...memory cap reached ({max_seen} states tracked), stopping")
            return SolveResult(best_path, explored, False, "capped")

        for move in generate_moves(state, last_move):
            moved_state = apply_move(state, move)
            new_state, auto_moves = auto_play_safe(moved_state)
            full_moves = [move] + auto_moves
            g = len(path) + len(full_moves)
            hh = heuristic(new_state, total_cards)
            f = g + weight * hh
            k = new_state.key()
            if k not in seen or seen[k] > g:
                seen[k] = g
                heapq.heappush(open_set, (f, next(counter), new_state, path + full_moves, move))

    return SolveResult(best_path, explored, False, "exhausted")
