from engine.deck import create_deck
from engine.card import Card, CardType, Suit
from engine.trick import winning_card
from .enums import RoundState
import random


class Round:
    def __init__(self, players, cards_per_player: int, dealer_index: int):
        self.players = players
        self.cards_per_player = cards_per_player
        self.dealer_index = dealer_index

        # Stato del gioco
        self.state = RoundState.BIDDING
        self.trump_suit: Suit | None = None
        self.trump_card_object: Card | None = None

        # Gestione turni
        self.first_player_index = (dealer_index + 1) % len(players)
        self.current_turn_index = self.first_player_index

        # Dati della partita
        self.bids = {}
        self.current_trick = []
        self.trick_order = []
        self.tricks_won = {p.name: 0 for p in players}
        self.tricks_completed = 0
        self.points_earned = {}
        self.last_trick_winner = None
        self.last_trick = []  # NUOVO: Memorizza l'ultima mano per il frontend

    def setup(self):
        """Distribuisce carte e determina lo stato iniziale"""
        deck = create_deck()
        for p in self.players:
            p.reset_round()

        # Distribuzione
        for _ in range(self.cards_per_player):
            for p in self.players:
                if deck:
                    card = deck.pop()
                    p.hand.append(card)

        for p in self.players:
            p.sort_hand()

        # Determinazione Briscola
        if deck:
            self.trump_card_object = deck.pop()
            if self.trump_card_object.type == CardType.WIZARD:
                self.state = RoundState.WAITING_FOR_DEALER_TRUMP
                self.current_turn_index = self.dealer_index
                return
            elif self.trump_card_object.type == CardType.JESTER:
                self.trump_suit = None
            else:
                self.trump_suit = self.trump_card_object.suit
        else:
            self.trump_suit = None

        self.state = RoundState.BIDDING
        self.current_turn_index = self.first_player_index

    def get_bot_trump_choice(self, player):
        #Sceglie il seme di briscola per il bot.
        counts = {s: 0 for s in Suit}

        has_cards = False
        for card in player.hand:
            if card.type == CardType.NUMBER:
                counts[card.suit] += 1
                has_cards = True
        print(counts)
        # Se ha carte numeriche, sceglie il seme più frequente
        if has_cards:
            best_suit = max(counts, key=counts.get)
            return best_suit

        # Se ha solo Wizard/Jester, sceglie a caso (es. Cuori)
        return Suit.CUORI

    def get_bot_prediction(self, player):
        # Calcola la scommessa per il bot basandosi sulla sua mano.
        prediction = 0
        for card in player.hand:
            if card.type == CardType.WIZARD or (card.type == CardType.NUMBER and card.value > 11):
                prediction += 1

        # Verifichiamo se questo bot è l'ultimo a giocare
        is_last_bidder = (self.current_turn_index == self.dealer_index)
        if is_last_bidder:
            current_sum = sum(self.bids.values())
            forbidden_bid = self.cards_per_player - current_sum

            # Se la nostra previsione è proprio il numero vietato, dobbiamo cambiarla
            if prediction == forbidden_bid:
                prediction += 1

        return prediction

    def get_bot_card_to_play(self, player):
        valid_cards = [i for i in player.hand if i.type == CardType.WIZARD or i.type == CardType.JESTER]
        #Sceglie quale carta giocare.
        # 1. Otteniamo le carte che PUÒ giocare secondo le regole
        lead_suit = None
        for c in self.current_trick:
            if c.type == CardType.WIZARD:
                lead_suit = None
                break
            if c.type == CardType.NUMBER:
                lead_suit = c.suit
                break

        has_suit = any(c.suit == lead_suit and c.type == CardType.NUMBER for c in player.hand)
        if lead_suit and has_suit:
            valid_cards.extend(
                i for i in player.hand
                if i.type == CardType.NUMBER and i.suit == lead_suit
            )
        else:
            valid_cards = player.hand
        chosen_card = random.choice(valid_cards)
        chosen_card_dict = chosen_card.to_dict()

        return chosen_card_dict

    def set_trump_suit(self, suit: Suit):
        if self.state != RoundState.WAITING_FOR_DEALER_TRUMP:
            raise Exception(f"Non è il momento di scegliere")
        self.trump_suit = suit
        self.state = RoundState.BIDDING
        self.current_turn_index = self.first_player_index

    def make_bid(self, player_name: str, bid: int):
        if self.state != RoundState.BIDDING:
            raise Exception("Non è la fase delle scommesse")

        current_player = self.players[self.current_turn_index]
        if current_player.name != player_name:
            raise Exception(f"Non è il turno di {player_name}")

        # Controllo dealer (regola +/- 1)
        is_last_bidder = (self.current_turn_index == self.dealer_index)
        if is_last_bidder:
            current_sum = sum(self.bids.values())
            if current_sum + bid == self.cards_per_player:
                raise Exception(f"Il totale delle scommesse non può essere pari al numero di carte ({self.cards_per_player})")

        self.bids[player_name] = bid
        current_player.prediction = bid
        self.current_turn_index = (self.current_turn_index + 1) % len(self.players)

        if len(self.bids) == len(self.players):
            self.state = RoundState.PLAYING
            self.current_turn_index = self.first_player_index

    def play_card(self, player_name: str, card_dict: dict):
        if self.state != RoundState.PLAYING:
            raise Exception("Non in fase PLAYING")

        current_player = self.players[self.current_turn_index]
        if current_player.name != player_name:
            raise Exception(f"Non è il turno di {player_name}")

        card_obj = self._find_card_in_hand(current_player, card_dict)
        self._validate_move(current_player, card_obj)

        current_player.hand.remove(card_obj)
        self.current_trick.append(card_obj)
        self.trick_order.append(current_player)

        if len(self.current_trick) == 1:
            self.last_trick_winner = None

        if len(self.current_trick) == len(self.players):
            self._resolve_trick()
        else:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.players)

    def _validate_move(self, player, card_to_play):
        if not self.current_trick:
            return

        lead_suit = None
        for c in self.current_trick:
            if c.type == CardType.WIZARD:
                lead_suit = None
                break
            if c.type == CardType.NUMBER:
                lead_suit = c.suit
                break

        if card_to_play.type in [CardType.WIZARD, CardType.JESTER]:
            return

        if lead_suit:
            has_suit = any(c.suit == lead_suit and c.type == CardType.NUMBER for c in player.hand)
            if has_suit and card_to_play.suit != lead_suit:
                raise Exception(f"Devi rispondere al seme {lead_suit.name}")

    def _resolve_trick(self):
        # Salva la mano corrente per il frontend prima di pulirla
        self.last_trick = list(self.current_trick)

        winner_idx = winning_card(self.current_trick, self.trump_suit)
        winner = self.trick_order[winner_idx]

        self.tricks_won[winner.name] += 1
        self.tricks_completed += 1
        self.last_trick_winner = winner.name

        # Pulisci per la prossima mano
        self.current_trick = []
        self.trick_order = []

        leader_idx_global = self.players.index(winner)
        self.current_turn_index = leader_idx_global

        cards_remaining = sum(len(p.hand) for p in self.players)
        if cards_remaining == 0:
            self.state = RoundState.FINISHED

    def calculate_scores(self):
        if getattr(self, "_punti_gia_fatti", False):
            return

        for player in self.players:
            actual = self.tricks_won.get(player.name, 0)
            predicted = self.bids.get(player.name, 0)

            if actual == predicted:
                points = 20 + (actual * 10)
            else:
                diff = abs(actual - predicted)
                points = -(diff * 10)

            player.score += points
            self.points_earned[player.name] = points

        self._punti_gia_fatti = True

    def _find_card_in_hand(self, player, card_dict):
        for c in player.hand:
            if c.type.name == card_dict['type']:
                if c.type == CardType.NUMBER:
                    if c.value == card_dict['value'] and c.suit.name == card_dict['suit']:
                        return c
                else:
                    return c
        raise Exception(f"Carta non trovata in mano a {player.name}")