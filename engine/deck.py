import random
from .card import Card, Suit, CardType


def create_deck() -> list[Card]:
    deck = []

    for suit in Suit:
        for value in range(1, 14):
            deck.append(Card(CardType.NUMBER, suit, value))

    for i in range(4):
        deck.append(Card(CardType.WIZARD, id=i))
        deck.append(Card(CardType.JESTER, id=i))

    random.shuffle(deck)
    return deck
