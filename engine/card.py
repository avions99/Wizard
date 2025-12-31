from enum import Enum, auto
from dataclasses import dataclass


class Suit(Enum):
    CUORI = 1
    QUADRI = 2
    FIORI = 3
    PICCHE = 4

class CardType(Enum):
    NUMBER = auto()
    WIZARD = auto()
    JESTER = auto()

@dataclass(frozen=True)
class Card:
    type: CardType
    suit: Suit | None = None
    value: int | None = None
    id: int | None = None

    def __str__(self):
        if self.type == CardType.WIZARD:
            return f"WIZARD-{self.id}"
        if self.type == CardType.JESTER:
            return f"JESTER-{self.id}"
        return f"{self.suit.name}-{self.value}"

    def to_dict(self):
        return {
            "type": self.type.name,
            "suit": self.suit.name if self.suit else None,
            "value": self.value,
            "id": self.id,
            "display": str(self)  # Utile per debug o display rapido
        }
