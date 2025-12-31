from .card import Card, Suit, CardType

class Player:
    def __init__(self, name: str):
        self.name = name
        self.hand: list[Card] = []
        self.prediction: int | None = None
        self.tricks_won: int = 0
        self.score: int = 0

    def reset_round(self):
        self.hand.clear()
        self.prediction = None
        self.tricks_won = 0

    def sort_hand(self):
        # Ordine dei semi richiesto
        suit_priority = {
            Suit.CUORI: 0,
            Suit.QUADRI: 1,
            Suit.FIORI: 2,
            Suit.PICCHE: 3,
            None: 99  # Per sicurezza
        }

        def sort_key(card):
            # 1. TIPO DI CARTA
            # Vogliamo: Wizard (0) < Jester (1) < Number (2)
            if card.type == CardType.WIZARD:
                type_rank = 0
            elif card.type == CardType.JESTER:
                type_rank = 1
            else:
                type_rank = 2

            # 2. SEME (Importante: conta solo se type_rank è uguale, cioè per i Numeri)
            # Cuori (0) < Quadri (1) < Fiori (2) < Picche (3)
            suit_rank = suit_priority.get(card.suit, 99)

            # 3. VALORE (Decrescente: Re prima di Asso)
            # L'ordinamento standard è crescente (1, 2, 3...).
            # Usando il valore negativo, -13 (Re) è "minore" di -1 (Asso), quindi viene prima.
            if card.value is not None:
                value_rank = -card.value
            else:
                value_rank = 0

            # 4. ID (Solo per rompere la parità tra più Wizard/Jester identici)
            id_rank = card.id if card.id is not None else 0

            # Restituiamo la tupla. Python ordina confrontando il primo elemento,
            # se uguale passa al secondo, ecc.
            return (type_rank, suit_rank, value_rank, id_rank)

        self.hand.sort(key=sort_key)

    def to_dict(self):
        return {
            "name": self.name,
            "hand": [card.to_dict() for card in self.hand],
            "score": self.score,
            "tricks_won": self.tricks_won,
            "prediction": self.prediction
        }

    def __str__(self):
        return self.name
