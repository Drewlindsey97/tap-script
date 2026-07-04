from collections import namedtuple

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUE = {r: i + 1 for i, r in enumerate(RANKS)}
SUITS = ["S", "H", "D", "C"]  # Spades, Hearts, Diamonds, Clubs
RED_SUITS = {"H", "D"}
BLACK_SUITS = {"S", "C"}

Card = namedtuple("Card", ["rank", "suit"])


def card_color(card):
    return "red" if card.suit in RED_SUITS else "black"


def card_name(card):
    return f"{card.rank}{card.suit}"


def full_deck():
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def rank_value(card):
    return RANK_VALUE[card.rank]
