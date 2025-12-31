import random
import copy
from collections import Counter
from engine.card import Card, Suit, CardType
from engine.round import Round
from server import *

class MonteCarloBot:
    def __init__(self, player_id, hand, num_players):
        self.my_id = player_id
        self.hand = hand  # Lista di oggetti Card
        self.num_players = num_players
        self.seen_cards = set()  # Qui memorizziamo TUTTE le carte viste (mie + tavolo)

    def update_seen_cards(self, cards_list):
        """Chiama questo metodo ogni volta che finisce una mano o vedi carte"""
        for c in cards_list:
            self.seen_cards.add(c)

    def generate_hypothetical_game(self, current_round_state):
        """
        Crea un oggetto Round completo riempiendo i buchi di informazione.
        current_round_state: Un dizionario o oggetto con info parziali (chi ha giocato, scommesse, ecc)
        """

        # 1. Crea un mazzo completo
        full_deck = self._create_full_deck()

        # 2. Rimuovi le carte che sappiamo essere impossibili
        # (Le mie, quelle in tavola ora, e quelle uscite nei turni passati)
        unknown_cards = [
            c for c in full_deck
            if c not in self.hand
               and c not in current_round_state['table_cards']
               and c not in self.seen_cards
        ]

        # 3. Mischia ciò che resta
        random.shuffle(unknown_cards)

        # 4. Distribuisci le carte agli avversari
        # Qui serve sapere quante carte hanno in mano gli avversari.
        # Assumiamo di essere nel round N, ogni giocatore deve avere X carte.
        hypothetical_hands = {}

        for pid in range(self.num_players):
            if pid == self.my_id:
                # Per me, uso la mia mano vera
                hypothetical_hands[pid] = self.hand[:]
            else:
                # Per gli altri, pesco dal mazzo ignoto
                # Nota: Devi calcolare quante carte hanno ancora in mano
                cards_needed = current_round_state['players_card_counts'][pid]
                hypothetical_hands[pid] = []
                for _ in range(cards_needed):
                    if unknown_cards:
                        hypothetical_hands[pid].append(unknown_cards.pop())

        # 5. Clona l'oggetto Round attuale (o creane uno nuovo)
        # È vitale che 'sim_round' abbia le stesse regole del gioco vero
        sim_round = Round(
            round_num=current_round_state['round_num'],
            players=hypothetical_hands,  # Passiamo le mani inventate
            trump=current_round_state['trump']
        )

        # Ripristina lo stato del tavolo attuale nel round simulato
        sim_round.table = current_round_state['table_cards'][:]
        sim_round.turn_order = current_round_state['turn_order'][:]

        return sim_round

    def play_randomout(self, sim_round):
        """
        Gioca a caso fino alla fine del round e ritorna il risultato.
        """
        while not sim_round.is_finished():
            # Chi tocca?
            current_player = sim_round.get_current_player()

            # Quali mosse sono legali?
            # (Qui usi la tua logica esistente in round.py!)
            valid_moves = sim_round.get_valid_moves(current_player)

            # Scelta casuale (Bot stupido veloce)
            chosen_card = random.choice(valid_moves)

            # Esegui la mossa
            sim_round.play_card(current_player, chosen_card)

        # Alla fine, calcola le prese
        return sim_round.calculate_results()

    def choose_best_card(self, current_state, my_bid, current_tricks_won):
        """
        Ritorna l'indice della carta migliore da giocare.
        """
        valid_moves = self._get_my_valid_moves(current_state)

        # Se ho una sola mossa, non penso nemmeno
        if len(valid_moves) == 1:
            return valid_moves[0]

        scores = {card: 0 for card in valid_moves}
        NUM_SIMULATIONS = 100  # Aumenta se il PC è veloce, diminuisci se lagga

        # ANALISI PER OGNI CARTA POSSIBILE
        for card in valid_moves:

            # Esegui N simulazioni
            for _ in range(NUM_SIMULATIONS):

                # 1. Crea un mondo parallelo
                sim_round = self.generate_hypothetical_game(current_state)

                # 2. FORZA la prima mossa (quella che stiamo valutando)
                sim_round.play_card(self.my_id, card)

                # 3. Lascia che il resto della partita si svolga a caso
                final_results = self.play_randomout(sim_round)

                # 4. Ho raggiunto il mio obiettivo?
                my_final_tricks = current_tricks_won + final_results[self.my_id]['tricks']

                # La logica di Wizard: Vincere ESATTAMENTE la scommessa
                if my_final_tricks == my_bid:
                    scores[card] += 1
                else:
                    # Penalità leggera: meglio sbagliare di poco che di tanto?
                    # Per ora semplice: 0 punti.
                    pass

        # Scegli la carta con il punteggio più alto
        best_card = max(scores, key=scores.get)
        print(f"Monte Carlo Analysis: {scores}")
        return best_card

