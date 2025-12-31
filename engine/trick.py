from typing import List
from .card import Card, CardType, Suit


def winning_card(cards: List[Card], trump: Suit | None) -> int:
    """
    Ritorna l'indice della carta vincente.
    """
    # 1. Se c'è un Wizard, vince il primo Wizard giocato
    for i, card in enumerate(cards):
        if card.type == CardType.WIZARD:
            return i

    # 2. Determina il seme dominante (Lead Suit)
    # Regola Wizard: Se la prima è Jester, il seme è della prima carta successiva che ha un seme.
    lead_suit = None
    for card in cards:
        if card.type == CardType.NUMBER:
            lead_suit = card.suit
            break
        # Se troviamo un Wizard, avremmo già fatto return sopra.
        # Se troviamo Jester, continuiamo a cercare.

    best_index = 0
    best_card = cards[0]

    for i in range(1, len(cards)):
        current_card = cards[i]

        # Se la carta corrente è un Jester, perde quasi sempre contro la best_card attuale
        # (eccezione: se anche best_card è Jester, vince il primo, quindi non aggiorniamo)
        if current_card.type == CardType.JESTER:
            continue

        # Se la best_card è Jester e la corrente no, la corrente vince sicuro
        if best_card.type == CardType.JESTER:
            best_card = current_card
            best_index = i
            continue

        # A questo punto confrontiamo due carte che NON sono Jester e NON sono Wizard

        # Caso Briscola (Trump)
        if trump:
            if current_card.suit == trump and best_card.suit != trump:
                best_card = current_card
                best_index = i
                continue
            if current_card.suit == trump and best_card.suit == trump:
                if current_card.value > best_card.value:
                    best_card = current_card
                    best_index = i
                continue

        # Caso Seme Dominante (Lead Suit)
        if current_card.suit == lead_suit:
            # Se la best non è trump (se fosse trump avrebbe già vinto sopra)
            # E se la best non è dello stesso seme (o è valore inferiore)
            if best_card.suit != lead_suit and best_card.suit != trump:
                best_card = current_card
                best_index = i
            elif best_card.suit == lead_suit and current_card.value > best_card.value:
                best_card = current_card
                best_index = i

    return best_index