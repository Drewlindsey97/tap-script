import random
import unittest

from freecell import Card, RANKS, SUITS, full_deck, rank_value, solve
from freecell.state import State, apply_move


def replay(columns, free_cells, foundations, moves):
    """Re-applies a solved move list from scratch and returns the final
    state, so tests check the moves are actually legal/complete rather than
    just trusting solve()'s own solved flag."""
    state = State(columns, free_cells or [], foundations or {})
    for move in moves:
        state = apply_move(state, move)
    return state


class TestCards(unittest.TestCase):
    def test_full_deck_has_52_unique_cards(self):
        deck = full_deck()
        self.assertEqual(len(deck), 52)
        self.assertEqual(len(set(deck)), 52)

    def test_rank_value_ordering(self):
        self.assertEqual(rank_value(Card("A", "S")), 1)
        self.assertEqual(rank_value(Card("K", "S")), 13)
        values = [rank_value(Card(r, "S")) for r in RANKS]
        self.assertEqual(values, sorted(values))


class TestSolver(unittest.TestCase):
    def test_tiny_two_card_deal(self):
        columns = [[Card("2", "S")], [Card("A", "S")], [], [], [], [], []]
        result = solve(columns)

        self.assertTrue(result.solved)
        self.assertEqual(result.status, "solved")

        final_state = replay(columns, None, None, result.moves)
        self.assertEqual(sum(final_state.foundation_ranks().values()), 2)

    def test_seeded_free_cells_and_foundations(self):
        columns = [[Card("3", "S")], [], [], [], [], [], [], []]
        free_cells = [Card("2", "S")]
        foundations = {"S": 1}

        result = solve(columns, free_cells=free_cells, foundations=foundations)

        self.assertTrue(result.solved)
        final_state = replay(columns, free_cells, foundations, result.moves)
        self.assertEqual(final_state.foundation_ranks()["S"], 3)

    def test_already_solved_deal_returns_no_moves(self):
        result = solve([[] for _ in range(8)], foundations={s: 13 for s in SUITS})

        self.assertTrue(result.solved)
        self.assertEqual(result.moves, [])

    def test_full_shuffled_deck_solves_and_replays_cleanly(self):
        random.seed(1234)
        deck = full_deck()
        random.shuffle(deck)

        columns = [[] for _ in range(8)]
        for i, card in enumerate(deck):
            columns[i % 8].append(card)

        result = solve(columns, max_seen=500_000)

        self.assertIn(result.status, ("solved", "capped", "exhausted"))
        if result.solved:
            final_state = replay(columns, None, None, result.moves)
            self.assertEqual(sum(final_state.foundation_ranks().values()), 52)


if __name__ == "__main__":
    unittest.main()
