from engine.deck import create_deck
from engine.card import Card, CardType, Suit
from engine.trick import winning_card
from .enums import RoundState
import random


class Round:
    def __init__(self, players, cards_per_player: int, dealer_index: int, open_cards_mode: bool = False):
        self.players = players
        self.cards_per_player = cards_per_player
        self.dealer_index = dealer_index
        self.open_cards_mode = open_cards_mode

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
        self.last_trick = []  # Memorizza l'ultima mano per il frontend
        self._punti_gia_fatti = False  # Flag per evitare doppi calcoli
        self.played_cards_history = []  # Memoria di tutte le carte giocate in questo round
        self.missing_suits = {p.name: set() for p in players}

    def setup(self):
        """Distribuisce carte e determina lo stato iniziale"""
        deck = create_deck()
        self._punti_gia_fatti = False

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
                # Il mazziere sceglie il seme
                self.state = RoundState.WAITING_FOR_DEALER_TRUMP
                self.current_turn_index = self.dealer_index
                return
            elif self.trump_card_object.type == CardType.JESTER:
                # Nessuna briscola
                self.trump_suit = None
            else:
                self.trump_suit = self.trump_card_object.suit
        else:
            self.trump_suit = None

        self.missing_suits = {p.name: set() for p in self.players}
        self.state = RoundState.BIDDING
        self.current_turn_index = self.first_player_index

    def get_valid_moves(self, player) -> list[Card]:
        """
        Restituisce la lista di carte giocabili da un giocatore nello stato attuale.
        Fondamentale per l'AI e per la validazione delle mosse.
        """
        # Se è il primo a giocare, tutto è valido
        if not self.current_trick:
            return list(player.hand)

        # 1. Determina il seme dominante (Lead Suit)
        lead_suit = None
        for c in self.current_trick:
            if c.type == CardType.WIZARD:
                # Se c'è un Wizard, il seme non conta (vince il primo Wizard),
                # quindi non c'è obbligo di risposta
                lead_suit = None
                break
            if c.type == CardType.NUMBER:
                lead_suit = c.suit
                break
            # Se è Jester, continuiamo a cercare il prossimo

        # Se non c'è lead suit (es. tutti Jester o primo è Wizard), tutto è valido
        if lead_suit is None:
            return list(player.hand)

        # 2. Controlla se il giocatore ha carte del seme dominante
        has_suit = any(c.suit == lead_suit and c.type == CardType.NUMBER for c in player.hand)

        if has_suit:
            # Deve rispondere a seme, OPPURE giocare Wizard o Jester (che sono sempre validi)
            return [c for c in player.hand if
                    (c.type == CardType.NUMBER and c.suit == lead_suit) or
                    c.type in [CardType.WIZARD, CardType.JESTER]]

        # Se non ha il seme, può giocare qualsiasi carta
        return list(player.hand)

    def _calculate_missing_suits(self):
        """
        Analizza la storia del round per capire quali semi mancano agli avversari.
        Ritorna: dict {player_name: set(Suit)}
        """
        if len(self.current_trick) < 2:
            return

        # 1. Determina il seme dominante (Lead Suit)
        lead_suit = None
        for c in self.current_trick:
            if c.type == CardType.WIZARD:
                lead_suit = None
                break
            if c.type == CardType.NUMBER:
                lead_suit = c.suit
                break

        # Se non c'è lead suit (es. tutti Jester o primo è Wizard), tutto è valido
        if lead_suit is None:
            return

        # 2. Controlla se il giocatore non ha carte del seme dominante
        for i in self.current_trick:
            if i.type == CardType.NUMBER and i.suit != lead_suit:
                index = self.current_trick.index(i)
                self.missing_suits[self.trick_order[index].name].add(lead_suit)

    def get_bot_prediction(self, player):
        # Import locale per evitare circular import
        from ai_engine import MonteCarloBot

        # Passiamo l'intero oggetto Round (self) al bot
        ai = MonteCarloBot(player.name, self)

        # Simulazioni rapide per la fase di scommessa
        prediction = ai.calculate_optimal_bid()

        # Regola del +/- 1 per l'ultimo giocatore (il Dealer o chi parla per ultimo)
        is_last_bidder = (self.current_turn_index == self.dealer_index)
        if is_last_bidder:
            current_sum = sum(self.bids.values())
            forbidden_bid = self.cards_per_player - current_sum

            if prediction == forbidden_bid:
                # Se la predizione cade sul numero vietato, spostiamo di 1
                if prediction > 0:
                    prediction -= 1
                else:
                    prediction += 1

        return prediction

    def get_bot_card_to_play(self, player):
        from ai_engine import MonteCarloBot

        ai = MonteCarloBot(player.name, self)

        # Usa Monte Carlo per scegliere la carta migliore
        best_card = ai.choose_best_card(simulations=100)

        return best_card.to_dict()

    def get_bot_trump_choice(self, player):
        """Sceglie il seme di briscola per il bot (se esce Wizard come briscola)."""
        counts = {s: 0 for s in Suit if s != Suit.NESSUNO}

        has_cards = False
        for card in player.hand:
            if card.type == CardType.NUMBER:
                counts[card.suit] += 1
                has_cards = True

        # Se ha carte numeriche, sceglie il seme più frequente
        if has_cards:
            best_suit = max(counts, key=counts.get)
            return best_suit

        # Se ha solo Wizard/Jester, sceglie a caso (es. Cuori)
        return Suit.CUORI

    def set_trump_suit(self, suit: Suit):
        if self.state != RoundState.WAITING_FOR_DEALER_TRUMP:
            raise Exception(f"Non è il momento di scegliere il seme")
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
                raise Exception(
                    f"Il totale delle scommesse non può essere pari al numero di carte ({self.cards_per_player})")

        self.bids[player_name] = bid
        current_player.prediction = bid
        self.current_turn_index = (self.current_turn_index + 1) % len(self.players)

        if len(self.bids) == len(self.players):
            self.state = RoundState.PLAYING
            self.current_turn_index = self.first_player_index

    def play_card(self, player_name: str, card_input: dict | Card):
        if self.state != RoundState.PLAYING:
            raise Exception("Non in fase PLAYING")

        current_player = self.players[self.current_turn_index]
        if current_player.name != player_name:
            raise Exception(f"Non è il turno di {player_name}")

        # Gestione input: se è dict (frontend) lo convertiamo/troviamo, se è Card (AI) lo usiamo
        card_obj = None
        if isinstance(card_input, dict):
            card_obj = self._find_card_in_hand(current_player, card_input)
        else:
            # Per sicurezza verifichiamo che la carta sia davvero nella mano (per evitare bug dell'AI)
            if card_input in current_player.hand:
                card_obj = card_input
            else:
                # Fallback: cerca per valore se l'istanza è diversa
                for c in current_player.hand:
                    if c == card_input:
                        card_obj = c
                        break
                if not card_obj:
                    raise Exception(f"Carta {card_input} non trovata nella mano di {player_name}")

        # Validazione
        self._validate_move(current_player, card_obj)

        # Esecuzione mossa
        current_player.hand.remove(card_obj)
        self.current_trick.append(card_obj)
        self.trick_order.append(current_player)

        # Aggiorno lista semi assenti nei giocatori
        self._calculate_missing_suits()

        if len(self.current_trick) == 1:
            self.last_trick_winner = None

        if len(self.current_trick) == len(self.players):
            self._resolve_trick()
        else:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.players)

    def _validate_move(self, player, card_to_play):
        """Valida se la mossa è legale usando get_valid_moves"""
        valid_moves = self.get_valid_moves(player)

        # Controlliamo se la carta è nella lista delle mosse valide.
        # Poiché Card è frozen=True, il confronto funziona correttamente.
        if card_to_play not in valid_moves:
            # Ricostruiamo il motivo per dare un messaggio di errore chiaro al frontend
            lead_suit = None
            for c in self.current_trick:
                if c.type == CardType.NUMBER:
                    lead_suit = c.suit
                    break
                if c.type == CardType.WIZARD:
                    break

            raise Exception(f"Mossa non valida! Devi rispondere al seme {lead_suit.name if lead_suit else 'dominante'}")

    def _resolve_trick(self):
        # Salva la mano corrente per il frontend prima di pulirla
        self.last_trick = list(self.current_trick)

        winner_idx = winning_card(self.current_trick, self.trump_suit)
        winner = self.trick_order[winner_idx]

        self.tricks_won[winner.name] += 1
        self.tricks_completed += 1
        self.last_trick_winner = winner.name

        # Aggiungiamo le carte del trick corrente alla storia
        self.played_cards_history.extend(self.current_trick)

        # Pulisci per la prossima mano
        self.current_trick = []
        self.trick_order = []

        leader_idx_global = self.players.index(winner)
        self.current_turn_index = leader_idx_global

        cards_remaining = sum(len(p.hand) for p in self.players)
        if cards_remaining == 0:
            self.state = RoundState.FINISHED

    def calculate_scores(self):
        if self._punti_gia_fatti:
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
                elif c.type in [CardType.WIZARD, CardType.JESTER]:
                    # Per Wizard e Jester controlliamo l'ID se presente, altrimenti il tipo basta
                    # (Nel tuo codice originale controllavi solo il tipo, qui affiniamo)
                    target_id = card_dict.get('id')
                    if target_id is not None:
                        if c.id == target_id:
                            return c
                    else:
                        return c
        raise Exception(f"Carta non trovata in mano a {player.name}")
