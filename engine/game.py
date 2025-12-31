from engine.player import Player
from .enums import Suit, CardType, RoundState


class Game:
    def __init__(self, player_names, config=None):
        """
        Inizializza una nuova partita
        :param player_names: Lista dei nomi dei giocatori
        :param config: Dizionario con la configurazione della partita
        """

        self.players = [Player(name) for name in player_names]

        for p in self.players:
            p.score = 0
        self.dealer_index = 0
        self.rounds = []
        self.round_history = []

        self.chat = []

        if config is None:
            config = {}

        self.config = config
        self.creator = player_names[0] if player_names else None

        self.selected_rounds = config.get('selected_rounds', list(range(1, 11)))
        self.current_round_index = 0

        self.first_round_open_cards = config.get('first_round_open_cards', False)
        self.max_players = config.get('max_players', len(player_names))

        print(f"[GAME] Inizializzato con {len(self.players)} giocatori: {[p.name for p in self.players]}")
        print(
            f"[GAME] Config: Round {self.selected_rounds}, Carte scoperte: {self.first_round_open_cards}, Max players: {self.max_players}")

    @property
    def round_number(self):
        if self.current_round_index < len(self.selected_rounds):
            return self.selected_rounds[self.current_round_index]
        return 0

    def _create_round_summary(self, round_obj, round_num):
        round_data = {
            "round_num": round_num,
            "players_data": []
        }
        for p in self.players:
            round_data["players_data"].append({
                "name": p.name,
                "prediction": round_obj.bids.get(p.name, 0),
                "tricks_won": round_obj.tricks_won.get(p.name, 0),
                "score": p.score,
                "points_earned": round_obj.points_earned.get(p.name, 0)
            })
        return round_data

    def start_next_round(self):
        num_players = len(self.players)
        if num_players == 0:
            print("[GAME] Nessun giocatore!")
            return False

        if self.rounds:
            last_round = self.rounds[-1]
            print(f"[GAME] Ultimo round stato: {last_round.state}")

            if last_round.state == RoundState.FINISHED:
                round_data = self._create_round_summary(last_round, self.round_number)
                self.round_history.append(round_data)
                print(f"[GAME] Storico salvato per round {self.round_number}")

                self.current_round_index += 1
                self.dealer_index = (self.dealer_index + 1) % num_players
                print(f"[GAME] Nuovo mazziere: {self.players[self.dealer_index].name}")
            else:
                print(f"[GAME] Round corrente non ancora finito (stato: {last_round.state})")
                return False

        if self.current_round_index >= len(self.selected_rounds):
            print(f"[GAME] Partita finita! Completati tutti i round: {self.selected_rounds}")
            self._print_final_scores()
            return False

        next_round_num = self.selected_rounds[self.current_round_index]
        cards_to_deal = next_round_num
        print(
            f"[GAME] Creazione round {next_round_num} ({self.current_round_index + 1}/{len(self.selected_rounds)}) con {cards_to_deal} carte")
        from engine.round import Round
        new_round = Round(self.players, cards_to_deal, self.dealer_index)
        self.rounds.append(new_round)

        new_round.setup()
        print(f"[GAME] Setup completato, stato: {new_round.state}")
        return True

    def reset_game(self):
        print(f"[GAME] Reset partita, ricomincio da round {self.selected_rounds[0] if self.selected_rounds else 1}")
        for p in self.players:
            p.score = 0
            p.hand = []
        self.dealer_index = 0
        self.rounds = []
        self.round_history = []
        self.current_round_index = 0
        self.chat = []  # Reset chat

    def get_history(self):
        history = list(self.round_history)
        if self.rounds:
            last_round = self.rounds[-1]
            if last_round.state == RoundState.FINISHED:
                current_num = self.round_number
                if not any(r['round_num'] == current_num for r in history):
                    temp_data = self._create_round_summary(last_round, current_num)
                    history.append(temp_data)

        return history

    def is_creator(self, player_name):
        return player_name == self.creator

    def _print_final_scores(self):
        print("\n" + "=" * 50)
        print("PARTITA TERMINATA - CLASSIFICA FINALE")
        print("=" * 50)
        sorted_players = sorted(self.players, key=lambda p: p.score, reverse=True)
        for i, p in enumerate(sorted_players, 1):
            print(f"{i}. {p.name}: {p.score} punti")
        print("=" * 50 + "\n")