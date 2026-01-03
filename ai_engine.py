# ai_engine.py
import random
import copy
from engine.card import Card, Suit, CardType
from engine.enums import RoundState
from engine.deck import create_deck
from engine.trick import winning_card


class MonteCarloBot:
    def __init__(self, bot_name, real_round):
        """
        bot_name: Il nome del giocatore controllato dall'AI
        real_round: L'istanza reale dell'oggetto Round corrente
        """
        self.bot_name = bot_name
        self.real_round = real_round
        self.my_player = next(p for p in real_round.players if p.name == bot_name)

    def _determinize_round(self):
        """
        Crea un mondo possibile coerente con le informazioni note
        """
        # 1. Identifica carte NOTE (Mie + Tavolo attuale + Storia passata)
        known_cards_ids = set()
        for c in self.my_player.hand: known_cards_ids.add(str(c))
        for c in self.real_round.current_trick: known_cards_ids.add(str(c))

        # Recupera la memoria storica dal round (se implementata come suggerito)
        if hasattr(self.real_round, 'played_cards_history'):
            # Se played_cards_history contiene oggetti Card
            for item in self.real_round.played_cards_history:
                # Gestisce sia se è una lista di Card, sia se è una lista di tuple (Card, Player)
                card_obj = item[0] if isinstance(item, (list, tuple)) else item
                known_cards_ids.add(str(card_obj))

        # 2. Genera il pool di carte IGNOTE
        full_deck = create_deck()
        base_unknown_cards = [c for c in full_deck if str(c) not in known_cards_ids]

        # Lista degli avversari da riempire
        opponents = [p for p in self.real_round.players if p.name != self.bot_name]

        # --- STRATEGIA: MOST CONSTRAINED FIRST ---
        # Ordiniamo gli avversari: chi ha PIÙ semi vietati viene servito per PRIMO.
        # Chi ha meno vincoli è più flessibile e può prendere quello che avanza.
        opponents_sorted = sorted(
            opponents,
            key=lambda p: len(self.real_round.missing_suits.get(p.name, set())),
            reverse=True
        )

        # Tentiamo di distribuire fino a 10 volte
        max_retries = 10

        for attempt in range(max_retries):
            # Clona il round per questo tentativo
            sim_round = copy.deepcopy(self.real_round)

            # Mescola le carte ignote per questo tentativo
            current_unknown = list(base_unknown_cards)
            random.shuffle(current_unknown)

            distribution_success = True

            for real_p in opponents_sorted:
                p_name = real_p.name

                # Trova il giocatore corrispondente nell'oggetto sim_round
                sim_p = next(sp for sp in sim_round.players if sp.name == p_name)

                # Quante carte servono
                cards_needed = len(real_p.hand)
                sim_p.hand = []  # Svuota mano simulata

                forbidden_suits = self.real_round.missing_suits.get(p_name, set())

                for _ in range(cards_needed):
                    if not current_unknown:
                        distribution_success = False
                        break

                    found_card = None
                    found_index = -1

                    # Cerca la prima carta valida nel mazzo mescolato
                    for i, card in enumerate(current_unknown):
                        is_valid = True

                        if card.type == CardType.NUMBER:
                            if card.suit in forbidden_suits:
                                is_valid = False

                        if is_valid:
                            found_card = card
                            found_index = i
                            break

                    if found_card:
                        sim_p.hand.append(found_card)
                        current_unknown.pop(found_index)
                    else:
                        # Vicolo cieco: questo giocatore non può prendere nessuna delle carte rimaste
                        distribution_success = False
                        break

                if not distribution_success:
                    break

            if distribution_success:
                # ABBIAMO TROVATO UNA CONFIGURAZIONE VALIDA!
                return sim_round

        # --- FALLBACK ---
        print(f"[AI WARNING] Fallback distribution triggered for {self.bot_name}")

        fallback_round = copy.deepcopy(self.real_round)
        random.shuffle(base_unknown_cards)
        for p in fallback_round.players:
            if p.name == self.bot_name: continue
            real_p = next(op for op in self.real_round.players if op.name == p.name)
            p.hand = base_unknown_cards[:len(real_p.hand)]
            base_unknown_cards = base_unknown_cards[len(real_p.hand):]

        return fallback_round

    def _play_randomout(self, sim_round):
        """Simula la partita fino alla fine usando mosse casuali ma VALIDE"""
        while sim_round.state == RoundState.PLAYING:
            current_p = sim_round.players[sim_round.current_turn_index]

            # Usa il metodo del Round per ottenere mosse legali (senza eccezioni)
            valid_moves = sim_round.get_valid_moves(current_p)

            # Valutare se aggiungere regole aggiuntive
            card_to_play = random.choice(valid_moves)

            # Gioca la carta usando il motore reale
            sim_round.play_card(current_p.name, card_to_play)
        return {p.name: sim_round.tricks_won[p.name] for p in sim_round.players}

    def calculate_optimal_bid(self):
        """
        Calcola la scommessa basandosi sulla forza statistica della mano.
        """
        # --- CASO SPECIALE: 1 Carta + Modalità Carte Scoperte ---
        if self.real_round.cards_per_player == 1 and self.real_round.open_cards_mode:
            # 1. Identifichiamo le carte visibili (Trump + Avversari)
            visible_cards_ids = set()

            # Briscola
            if self.real_round.trump_card_object:
                visible_cards_ids.add(str(self.real_round.trump_card_object))

            # Carte che vedo sulla fronte degli avversari
            opponents_cards_map = {}
            for p in self.real_round.players:
                if p.name != self.bot_name and p.hand:
                    card = p.hand[0]
                    visible_cards_ids.add(str(card))
                    opponents_cards_map[p.name] = card

            # 2. Generiamo tutte le carte che POTREI avere io
            # (Tutto il mazzo meno quelle che vedo già in gioco)
            full_deck = create_deck()
            possible_my_cards = [c for c in full_deck if str(c) not in visible_cards_ids]
            print(visible_cards_ids)
            wins = 0
            total_scenarios = len(possible_my_cards)

            # 3. Simuliamo la mano per OGNI carta che potrei avere
            start_idx = self.real_round.first_player_index
            num_players = len(self.real_round.players)
            trump_suit = self.real_round.trump_suit

            for my_card in possible_my_cards:
                # Costruiamo il trick ipotetico nell'ordine corretto di gioco
                trick_cards = []

                for i in range(num_players):
                    current_player_idx = (start_idx + i) % num_players
                    player = self.real_round.players[current_player_idx]

                    if player.name == self.bot_name:
                        # In questa simulazione, ipotizzo di avere 'my_card'
                        trick_cards.append(my_card)
                    else:
                        # Per gli altri, uso la carta che vedo realmente
                        trick_cards.append(opponents_cards_map[player.name])

                # Chi vince questa simulazione?
                winner_rel_idx = winning_card(trick_cards, trump_suit)
                winner_abs_idx = (start_idx + winner_rel_idx) % num_players
                winner_name = self.real_round.players[winner_abs_idx].name

                if winner_name == self.bot_name:
                    wins += 1

            # 4. Calcolo Probabilità
            win_probability = wins / total_scenarios if total_scenarios > 0 else 0

            print(f"[AI {self.bot_name}] Probabilità vittoria: {win_probability:.2%}")

            # 5. Decisione: Se ho più del 50% di chance, scommetto 1.
            if win_probability > 0.5:
                return 1
            else:
                return 0

        trump = self.real_round.trump_suit
        total_strength = 0.0

        num_players = len(self.real_round.players)

        # Fattore di affollamento: più giocatori ci sono, meno valgono le carte alte non-briscola
        crowd_factor = 1.0 if num_players <= 4 else 0.8

        for card in self.my_player.hand:
            strength = 0.0

            if card.type == CardType.WIZARD:
                strength = 1.0

            elif card.type == CardType.JESTER:
                strength = 0.0

            elif card.type == CardType.NUMBER:
                val = card.value

                # Se è briscola
                if trump and card.suit == trump:
                    if val >= 11:
                        strength = 0.95  # J, Q, K
                    elif val >= 8:
                        strength = 0.7
                    elif val >= 5:
                        strength = 0.4
                    else:
                        strength = 0.1

                # Se non è briscola (e non c'è "Nessuna briscola")
                elif trump is not None:
                    if val == 13:
                        strength = 0.7 * crowd_factor
                    elif val == 12:
                        strength = 0.5 * crowd_factor
                    elif val == 11:
                        strength = 0.2 * crowd_factor
                    else:
                        strength = 0.0

                # Se non c'è briscola (Round Jester o ultima carta mazzo finita)
                else:
                    if val >= 12:
                        strength = 0.85
                    elif val >= 10:
                        strength = 0.6
                    elif val >= 8:
                        strength = 0.3
                    else:
                        strength = 0.0

            total_strength += strength

        # Arrotondamento statistico
        predicted_tricks = round(total_strength)
        # Correzione logica: Non scommettere mai più del numero di carte in mano
        return min(predicted_tricks, len(self.my_player.hand))

    def choose_best_card(self, simulations):
        """
        Per ogni carta valida nella mia mano:
        1. Giocala in un round clonato.
        2. Simula il resto della partita N volte a caso.
        3. Conta quante volte raggiungo la mia prediction.
        """
        # Ottieni mosse valide dal round reale
        valid_moves = self.real_round.get_valid_moves(self.my_player)

        if not valid_moves: return self.my_player.hand[0]  # Fallback
        if len(valid_moves) == 1: return valid_moves[0]  # Scelta obbligata

        scores = {str(card): 0 for card in valid_moves}
        target_prediction = self.real_round.bids.get(self.bot_name, 0)

        for card in valid_moves:
            for _ in range(simulations):
                # 1. Crea situazione ipotetica
                sim_round = self._determinize_round()

                # 2. Io gioco QUESTA carta specifica
                try:
                    sim_round.play_card(self.bot_name, card)
                except Exception as e:
                    # Se per qualche motivo la generazione random crea uno stato impossibile
                    continue

                    # 3. Gli altri giocano a caso fino alla fine
                results = self._play_randomout(sim_round)

                # 4. Punteggio
                tricks_won = results.get(self.bot_name, 0)

                # Semplice funzione di reward:
                if tricks_won == target_prediction:
                    scores[str(card)] += 10  # Grande bonus se faccio la mia bid
                else:
                    diff = abs(tricks_won - target_prediction)
                    scores[str(card)] -= (diff * 5)  # Penalità per la distanza

        # Trova la carta col punteggio migliore
        best_card_str = max(scores, key=scores.get)

        # Ritorna l'oggetto carta corrispondente
        for c in valid_moves:
            if str(c) == best_card_str:
                return c

        return valid_moves[0]