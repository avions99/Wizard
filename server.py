import uvicorn, json, asyncio, random, string, importlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import engine.game

importlib.reload(engine.game)
from engine.game import Game
from engine.enums import RoundState
from engine.card import Suit

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/google82983cca318f8a41.html")
async def google_verification():
    return FileResponse("google82983cca318f8a41.html")

class GameManager:
    def __init__(self):
        self.rooms = {}
        self.active_games = {}
        self.lobby_players = {}
        self.lobby_configs = {}

    def get_game_state(self, room_id, player_id):
        # --- STATO LOBBY ---
        if room_id not in self.active_games:
            players = self.lobby_players.get(room_id, [])
            config = self.lobby_configs.get(room_id, {})
            creator = players[0] if players else None
            max_players = config.get('max_players', 6)

            return {
                "state": "LOBBY",
                "room_id": room_id,
                "players": [{"name": n, "score": 0, "tricks_won": 0, "prediction": None} for n in players],
                "can_start": len(players) >= max_players and config.get('configured', False),
                "table_cards": [],
                "round_num": 0,
                "current_turn": None,
                "trump_card": None,
                "trump_suit": None,
                "cards_to_deal": 0,
                "dealer": None,
                "round_history": [],
                "is_creator": player_id == creator,
                "creator": creator,
                "config": config,
                "lobby_ready": config.get('configured', False),
                "chat": []  # Niente chat in lobby
            }

        # --- STATO PARTITA ---
        game = self.active_games[room_id]

        # Assicura che la chat esista anche se il game è vecchio
        if not hasattr(game, 'chat'):
            game.chat = []

        if not game.rounds:
            return {
                "state": "LOBBY",
                "room_id": room_id,
                "players": [{"name": p.name, "score": p.score, "tricks_won": 0, "prediction": None} for p in
                            game.players],
                "can_start": False,
                "table_cards": [],
                "round_num": 0,
                "current_turn": None,
                "trump_card": None,
                "trump_suit": None,
                "cards_to_deal": 0,
                "dealer": None,
                "round_history": game.get_history(),
                "chat": game.chat
            }

        curr = game.rounds[-1]

        current_turn_name = None
        if curr.state == RoundState.BIDDING:
            if hasattr(curr, 'current_turn_index') and curr.current_turn_index is not None:
                current_turn_name = game.players[curr.current_turn_index].name
        elif curr.state == RoundState.PLAYING:
            if hasattr(curr, 'current_turn_index') and curr.current_turn_index is not None:
                current_turn_name = game.players[curr.current_turn_index].name
        elif curr.state == RoundState.WAITING_FOR_DEALER_TRUMP:
            current_turn_name = game.players[curr.dealer_index].name
        elif curr.state == RoundState.FINISHED:
            current_turn_name = "---"

        last_round_num = game.selected_rounds[-1]
        is_last_round = (game.round_number == last_round_num)
        game_finished = is_last_round and curr.state == RoundState.FINISHED

        state = {
            "state": curr.state.name,
            "room_id": room_id,
            "round_num": game.round_number,
            "current_turn": current_turn_name,
            "trump_card": curr.trump_card_object.to_dict() if hasattr(curr,
                                                                      'trump_card_object') and curr.trump_card_object else None,
            "trump_suit": curr.trump_suit.name if curr.trump_suit else None,
            "table_cards": [{**c.to_dict(), "played_by": p.name} for c, p in
                            zip(curr.current_trick, curr.trick_order)] if hasattr(curr, 'current_trick') else [],
            "last_trick_cards": [c.to_dict() for c in curr.last_trick] if hasattr(curr, 'last_trick') else [],
            "tricks_completed": curr.tricks_completed if hasattr(curr, 'tricks_completed') else 0,
            "players": [],
            "cards_to_deal": curr.cards_per_player,
            "dealer": game.players[curr.dealer_index].name,
            "round_history": game.get_history(),
            "is_creator": game.is_creator(player_id),
            "creator": game.creator,
            "config": game.config,
            "selected_rounds": game.selected_rounds,
            "current_round_index": game.current_round_index,
            "total_rounds": len(game.selected_rounds),
            "last_trick_winner": curr.last_trick_winner if hasattr(curr, 'last_trick_winner') else None,
            "game_finished": game_finished,
            "is_last_trick": hasattr(curr, 'tricks_completed') and curr.tricks_completed == curr.cards_per_player,
            "chat": game.chat
        }

        is_first_round_of_game = (game.current_round_index == 0)

        for p in game.players:
            p_info = {
                "name": p.name,
                "score": p.score,
                "tricks_won": curr.tricks_won.get(p.name, 0) if hasattr(curr, 'tricks_won') else 0,
                "prediction": curr.bids.get(p.name, None) if hasattr(curr, 'bids') else None,
                "hand": []
            }

            # --- LOGICA VISIBILITÀ CARTE ---
            # Caso speciale: 1° round con carte scoperte DURANTE le scommesse
            is_special_first_round_bidding = (
                    game.first_round_open_cards and
                    is_first_round_of_game and
                    (curr.state == RoundState.BIDDING or curr.state == RoundState.WAITING_FOR_DEALER_TRUMP)
            )

            if p.name == player_id:
                # Se sono io
                if is_special_first_round_bidding:
                    # DEVO COPRIRE LE MIE CARTE (mostro il dorso)
                    p_info['hand'] = [{"type": "BACK", "suit": None, "value": None, "id": None} for _ in p.hand]
                else:
                    # Normalmente vedo le mie carte
                    p_info['hand'] = [c.to_dict() for c in p.hand] if hasattr(p, 'hand') and p.hand else []
            else:
                # Se sono gli altri
                if is_special_first_round_bidding:
                    # VEDO le carte degli altri
                    p_info['hand'] = [c.to_dict() for c in p.hand] if hasattr(p, 'hand') and p.hand else []
                else:
                    # Normalmente non vedo le carte degli altri
                    p_info['hand'] = []

            state["players"].append(p_info)
        return state

    async def broadcast(self, room_id):
        if room_id not in self.rooms: return
        for ws in self.rooms[room_id][:]:
            try:
                state = self.get_game_state(room_id, ws.player_id)
                await ws.send_text(json.dumps(state))
            except Exception:
                if ws in self.rooms[room_id]:
                    self.rooms[room_id].remove(ws)


manager = GameManager()


@app.get("/")
async def get_index(): return FileResponse('index.html')


@app.get("/favicon.ico")
async def get_favicon(): return JSONResponse(content={}, status_code=204)


@app.get("/create_room")
async def create_room():
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    manager.rooms[code] = []
    manager.lobby_players[code] = []
    return {"room_id": code}


@app.post("/{room_id}/add_bot")
async def add_bot_endpoint(room_id, response: Response):
    bot = 'bot_1'
    config = manager.lobby_configs.get(room_id, {})
    max_players = config.get('max_players', 6)
    if bot in manager.lobby_players[room_id]:
        lista_bot = [int(i[-1]) for i in manager.lobby_players[room_id] if i.startswith('bot')]
        max_bot = max(lista_bot)
        bot = f'bot_{max_bot + 1}'
    if len(manager.lobby_players[room_id]) >= max_players:
        response.status_code = 400
        return {"error": "Lobby piena"}
    manager.lobby_players[room_id].append(bot)
    print(f"[SERVER] Bot aggiunto! Totale giocatori: {len(manager.lobby_players[room_id])}")
    await manager.broadcast(room_id)

async def gestisci_turno_bot(manager, room_id):
    await manager.broadcast(room_id)

    # Controlla di chi è il turno. Se è di un Bot, esegue la mossa.
    game = manager.active_games.get(room_id)
    if not game:
        return

    # Recuperiamo il round corrente e il giocatore di turno
    current_round = game.rounds[-1]

    # Giocatore mazziere
    idx = current_round.dealer_index
    player_mazziere = game.players[idx]

    # Se il mazziere è un bot e lo stato è la scelta della briscola
    if player_mazziere.name.lower().startswith('bot_') and current_round.state == RoundState.WAITING_FOR_DEALER_TRUMP:
        print(f"[AI] Il dealer {player_mazziere.name} deve scegliere la briscola...")
        await asyncio.sleep(1.0)  # Piccola pausa per realismo

        # Calcola la scelta
        chosen_suit = current_round.get_bot_trump_choice(player_mazziere)
        # Applica la scelta
        current_round.set_trump_suit(chosen_suit)
        print(f"[AI] {player_mazziere.name} ha scelto: {chosen_suit.name}")
        # Aggiorna grafica (mostra il seme scelto)
        await manager.broadcast(room_id)
        # Recursione: Ora lo stato è passato a BIDDING, quindi qualcuno deve scommettere
        await gestisci_turno_bot(manager, room_id)
        return

    # Indice del giocatore corrente
    idx = current_round.current_turn_index
    player = game.players[idx]

    # SE NON È UN BOT, ci fermiamo subito. Tocca a un umano.
    if not player.name.lower().startswith('bot_'):
        return

    # --- È IL TURNO DI UN BOT! ---
    print(f"[AI] Tocca al bot {player.name}...")

    # Simula un tempo di "pensiero"
    await asyncio.sleep(1.5)

    if current_round.state == RoundState.BIDDING:
        # Calcola il numero
        prediction_val = current_round.get_bot_prediction(player)
        try:
            current_round.make_bid(player.name, prediction_val)
        except Exception as e:
            print(f"ERRORE GRAVE BOT: {e}")
            return
        print(f"[AI] {player.name} ha scommesso: {prediction_val}")

        # NOTIFICA TUTTI
        await manager.broadcast(room_id)
        # RECURSIONE
        await gestisci_turno_bot(manager, room_id)

    elif current_round.state == RoundState.PLAYING:
        # --- FASE DI GIOCO CARTE
        # Calcola il numero
        card_played = current_round.get_bot_card_to_play(player)
        try:
            current_round.play_card(player.name, card_played)
            if current_round.state == RoundState.FINISHED:
                current_round.calculate_scores()
        except Exception as e:
            print(f"ERRORE GRAVE BOT: {e}")
            return
        print(f"[AI] {player.name} ha giocato: {card_played}")

        # NOTIFICA TUTTI
        await manager.broadcast(room_id)
        # RECURSIONE
        await gestisci_turno_bot(manager, room_id)

@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    if room_id not in manager.rooms:
        manager.rooms[room_id] = []
        manager.lobby_players[room_id] = []

    config = manager.lobby_configs.get(room_id, {})
    max_players = config.get('max_players', 6)

    # Se un umano prova a usare un nome riservato, lo cacciamo subito
    if player_id.lower().startswith("bot_"):
        await websocket.close(code=1008, reason="Nome non permesso (riservato ai Bot)")
        return

    if player_id not in manager.lobby_players[room_id] and len(manager.lobby_players[room_id]) >= max_players:
        await websocket.close(code=1008, reason="Lobby piena")
        return

    await websocket.accept()
    websocket.player_id = player_id
    manager.rooms[room_id].append(websocket)
    if player_id not in manager.lobby_players[room_id]:
        manager.lobby_players[room_id].append(player_id)

    print(f"[WS] {player_id} connesso a stanza {room_id}")
    await manager.broadcast(room_id)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get('action') == 'ping':
                continue

            game = manager.active_games.get(room_id)

            if msg['action'] == 'configure_lobby':
                if manager.lobby_players[room_id][0] == player_id:
                    selected_rounds = msg.get('selected_rounds', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
                    first_round_open_cards = bool(msg.get('first_round_open_cards', False))
                    if 1 not in selected_rounds:
                        first_round_open_cards = False

                    config = {
                        'max_players': int(msg['max_players']),
                        'selected_rounds': selected_rounds,
                        'first_round_open_cards': first_round_open_cards,
                        'configured': True
                    }
                    manager.lobby_configs[room_id] = config
                    print(f"[LOBBY] Config salvata: {config}")

            elif msg['action'] == 'kick_player':
                # Verifica: Solo il creatore può cacciare (il creatore è il primo della lista)
                if manager.lobby_players[room_id][0] == player_id:
                    target = msg['target']

                    # Non puoi cacciare te stesso
                    if target == player_id:
                        continue

                    print(f"[KICK] {player_id} sta cacciando {target}")

                    # CASO 1: È un BOT
                    if target.lower().startswith('bot_'):
                        if target in manager.lobby_players[room_id]:
                            manager.lobby_players[room_id].remove(target)
                            await manager.broadcast(room_id)

                    # CASO 2: È un UMANO
                    else:
                        # Rimuoviamo dalla lista dei nomi
                        if target in manager.lobby_players[room_id]:
                            manager.lobby_players[room_id].remove(target)

                        # Troviamo il suo WebSocket e lo chiudiamo
                        target_ws = None
                        for ws_client in manager.rooms[room_id]:
                            if getattr(ws_client, 'player_id', None) == target:
                                target_ws = ws_client
                                break

                        if target_ws:
                            # Chiudiamo la connessione con un codice specifico
                            await target_ws.close(code=1008, reason="Sei stato rimosso dalla stanza.")
                            if target_ws in manager.rooms[room_id]:
                                manager.rooms[room_id].remove(target_ws)

                        # Aggiorniamo tutti gli altri rimasti
                        await manager.broadcast(room_id)

            elif msg['action'] == 'start_game':
                config = manager.lobby_configs.get(room_id, {})
                max_players = config.get('max_players', 6)
                current_players_count = len(manager.lobby_players[room_id])

                if current_players_count > max_players:
                    # Invia un errore al client che ha provato ad avviare
                    await websocket.send_text(json.dumps({
                        "error": f"Troppi giocatori! Il limite è impostato a {max_players}, ma siete in {current_players_count}. Rimuovi qualcuno per iniziare.",
                        "action": "error_notify"
                    }))
                    continue  # Blocca l'esecuzione, non avvia il gioco
                if room_id not in manager.active_games:
                    new_game = Game(manager.lobby_players[room_id], config)
                    # Inizializza esplicitamente la chat
                    new_game.chat = []
                    manager.active_games[room_id] = new_game
                    manager.active_games[room_id].start_next_round()
                    # Aggiorna il frontend
                    await manager.broadcast(room_id)
                    # Controllo se BOT
                    await gestisci_turno_bot(manager, room_id)

            elif msg['action'] == 'start_next_round' and game:
                if game.is_creator(player_id) and game.rounds[-1].state == RoundState.FINISHED:
                    game.start_next_round()
                    # Controllo se BOT
                    await gestisci_turno_bot(manager, room_id)

            elif msg['action'] == 'select_trump' and game:
                game.rounds[-1].set_trump_suit(Suit[msg['suit']])
                # Controllo se BOT
                await gestisci_turno_bot(manager, room_id)

            elif msg['action'] == 'play_card' and game:
                try:
                    card_to_play = msg['card']
                    game.rounds[-1].play_card(player_id, card_to_play)
                    if game.rounds[-1].state == RoundState.FINISHED:
                        game.rounds[-1].calculate_scores()

                    # Controllo se BOT
                    await gestisci_turno_bot(manager, room_id)

                except Exception as e:
                    await websocket.send_text(json.dumps({"error": str(e), "action": "error_notify"}))

            elif msg['action'] == 'make_bid' and game:
                try:
                    game.rounds[-1].make_bid(player_id, int(msg['bid']))
                except Exception as e:
                    await websocket.send_text(json.dumps({"error": str(e), "action": "error_notify"}))
                await gestisci_turno_bot(manager, room_id)

            elif msg['action'] == 'new_game' and game:
                if game.is_creator(player_id):
                    game.reset_game()
                    game.start_next_round()

            # --- AGGIUNGERE QUESTO BLOCCO ---
            elif msg['action'] == 'cancel_lobby':
                # Verifica: Solo il creatore (primo della lista) può cancellare
                if manager.lobby_players[room_id] and manager.lobby_players[room_id][0] == player_id:
                    print(f"[SERVER] Il creatore {player_id} sta chiudendo la stanza {room_id}")

                    # 1. Avvisa tutti i client
                    for ws_client in manager.rooms[room_id]:
                        try:
                            # Inviamo un messaggio speciale che il frontend riconoscerà
                            await ws_client.send_text(json.dumps({"action": "lobby_destroyed"}))
                        except:
                            pass

                    # 2. Pulisci la memoria del server
                    if room_id in manager.rooms: del manager.rooms[room_id]
                    if room_id in manager.lobby_players: del manager.lobby_players[room_id]
                    if room_id in manager.active_games: del manager.active_games[room_id]
                    if room_id in manager.lobby_configs: del manager.lobby_configs[room_id]

                    # Interrompiamo il ciclo per questo socket poiché la stanza non esiste più
                    break

            # --- DEBUGGING CHAT ---
            elif msg['action'] == 'chat_message':
                print(f"[DEBUG CHAT] Ricevuto da {player_id}: {msg.get('message')}")

                if game:
                    if not hasattr(game, 'chat'):
                        print("[DEBUG CHAT] Inizializzazione lazy della chat")
                        game.chat = []

                    game.chat.append({
                        "sender": player_id,
                        "text": msg['message'],
                        "type": "user"
                    })
                    game.chat = game.chat[-50:]
                    print(f"[DEBUG CHAT] Messaggio aggiunto. Totale: {len(game.chat)}")
                else:
                    print("[DEBUG CHAT] Messaggio ignorato: PARTITA NON INIZIATA")

            elif msg['action'] == 'leave_game':
                pass

            await manager.broadcast(room_id)
    except WebSocketDisconnect:
        if websocket in manager.rooms.get(room_id, []):
            manager.rooms[room_id].remove(websocket)
        await manager.broadcast(room_id)
    except Exception as e:
        print(f"[ERROR] WS Disconnessione imprevista: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)