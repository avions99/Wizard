from enum import Enum, auto

class Suit(Enum):
    CUORI = auto()
    QUADRI = auto()
    FIORI = auto()
    PICCHE = auto()
    NESSUNO = auto() # Usato per i Jolly o quando non c'è briscola

class CardType(Enum):
    NUMBER = auto()
    WIZARD = auto()
    JESTER = auto()

class RoundState(Enum):
    LOBBY = auto()
    BIDDING = auto()
    PLAYING = auto()
    FINISHED = auto()
    WAITING_FOR_DEALER_TRUMP = auto()