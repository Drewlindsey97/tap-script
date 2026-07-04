from collections import namedtuple

from .cards import RED_SUITS, rank_value

Move = namedtuple("Move", ["kind", "src", "dst", "card"])


class State:
    """A FreeCell board position: tableau columns, free cells, and foundations.

    Immutable - every function below returns a new State rather than mutating
    one. key() gives a hashable signature so a search can dedupe positions it
    has already visited. foundations maps suit -> count of cards already
    played for that suit (0 if none, 13 once the King is down).
    """

    __slots__ = ("columns", "free_cells", "foundations")

    def __init__(self, columns, free_cells, foundations):
        self.columns = tuple(tuple(c) for c in columns)
        self.free_cells = tuple(sorted(free_cells))
        self.foundations = tuple(sorted(foundations.items()))

    def key(self):
        return (self.columns, self.free_cells, self.foundations)

    def foundation_ranks(self):
        return dict(self.foundations)

    def total_cards(self):
        return (
            sum(len(c) for c in self.columns)
            + len(self.free_cells)
            + sum(self.foundation_ranks().values())
        )


def opposite_color_suits(suit):
    return ("S", "C") if suit in RED_SUITS else ("H", "D")


def can_stack(card, on_top_of):
    same_color = (card.suit in RED_SUITS) == (on_top_of.suit in RED_SUITS)
    return not same_color and rank_value(card) == rank_value(on_top_of) - 1


def can_send_to_foundation(card, foundation_ranks):
    return rank_value(card) == foundation_ranks.get(card.suit, 0) + 1


def is_safe_autoplay(card, foundation_ranks):
    """A card is safe to send to foundation immediately - no future move
    could ever need it back in play - once both opposite-color foundations
    are already at least at its rank - 1. Standard FreeCell auto-play rule;
    collapses long forced sequences into one step instead of branching on
    them, which is what keeps the search tree tractable."""
    if not can_send_to_foundation(card, foundation_ranks):
        return False
    rv = rank_value(card)
    if rv <= 2:  # A, 2 are always safe once legal
        return True
    o1, o2 = opposite_color_suits(card.suit)
    return min(foundation_ranks.get(o1, 0), foundation_ranks.get(o2, 0)) >= rv - 1


def auto_play_safe(state):
    """Repeatedly applies safe foundation moves until none remain.

    Returns (new_state, moves_applied) - moves_applied is empty if nothing
    changed.
    """
    columns = [list(c) for c in state.columns]
    free_cells = list(state.free_cells)
    foundation_ranks = state.foundation_ranks()
    moves = []

    changed = True
    while changed:
        changed = False
        for ci, col in enumerate(columns):
            if col and is_safe_autoplay(col[-1], foundation_ranks):
                card = col.pop()
                foundation_ranks[card.suit] = rank_value(card)
                moves.append(Move("col_to_found", ci, None, card))
                changed = True
        for card in list(free_cells):
            if is_safe_autoplay(card, foundation_ranks):
                free_cells.remove(card)
                foundation_ranks[card.suit] = rank_value(card)
                moves.append(Move("free_to_found", None, None, card))
                changed = True

    return State(columns, free_cells, foundation_ranks), moves


def generate_moves(state, last_move=None):
    moves = []
    foundation_ranks = state.foundation_ranks()

    for ci, col in enumerate(state.columns):
        if col and can_send_to_foundation(col[-1], foundation_ranks):
            moves.append(Move("col_to_found", ci, None, col[-1]))

    for card in state.free_cells:
        if can_send_to_foundation(card, foundation_ranks):
            moves.append(Move("free_to_found", None, None, card))

    for ci, col in enumerate(state.columns):
        if not col:
            continue
        card = col[-1]
        placed_on_empty = False
        for cj, col2 in enumerate(state.columns):
            if ci == cj:
                continue
            if not col2:
                if not placed_on_empty:
                    moves.append(Move("col_to_col", ci, cj, card))
                    placed_on_empty = True
            elif can_stack(card, col2[-1]):
                moves.append(Move("col_to_col", ci, cj, card))

    for card in state.free_cells:
        placed_on_empty = False
        for cj, col2 in enumerate(state.columns):
            if not col2:
                if not placed_on_empty:
                    moves.append(Move("free_to_col", None, cj, card))
                    placed_on_empty = True
            elif can_stack(card, col2[-1]):
                moves.append(Move("free_to_col", None, cj, card))

    if len(state.free_cells) < 4:
        for ci, col in enumerate(state.columns):
            if col:
                move = Move("col_to_free", ci, None, col[-1])
                if last_move and last_move.kind == "free_to_col" and last_move.card == col[-1]:
                    continue
                moves.append(move)

    return moves


def apply_move(state, move):
    columns = [list(c) for c in state.columns]
    free_cells = list(state.free_cells)
    foundation_ranks = state.foundation_ranks()

    if move.kind == "col_to_found":
        columns[move.src].pop()
        foundation_ranks[move.card.suit] = rank_value(move.card)
    elif move.kind == "free_to_found":
        free_cells.remove(move.card)
        foundation_ranks[move.card.suit] = rank_value(move.card)
    elif move.kind == "col_to_col":
        columns[move.src].pop()
        columns[move.dst].append(move.card)
    elif move.kind == "col_to_free":
        columns[move.src].pop()
        free_cells.append(move.card)
    elif move.kind == "free_to_col":
        free_cells.remove(move.card)
        columns[move.dst].append(move.card)

    return State(columns, free_cells, foundation_ranks)
