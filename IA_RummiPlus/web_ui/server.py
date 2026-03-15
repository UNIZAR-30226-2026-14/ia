from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rummiplus import BotConfig, BotFacade, Board, GameState, Move, MoveType, PlayerState, build_classic_deck
from rummiplus import move_to_dict, state_from_bot_request, ViewMode
from rummiplus.move_logic import apply_move_inplace

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class TurnSnapshot:
    turn: int
    player_id: str
    level: int
    randomness: float
    move: str
    detail: str
    rack_count: int
    pool_remaining: int
    board: list[str]
    racks: dict[str, list[str]]
    board_melds: list[list[str]]
    pool_counts: dict[str, int]
    rack_points: dict[str, int]


def _init_state(levels: list[int], randomness: float, seed: int) -> tuple[GameState, list[BotFacade]]:
    rng = random.Random(seed)
    deck = build_classic_deck()
    rng.shuffle(deck)

    players: list[PlayerState] = []
    bots: list[BotFacade] = []
    for idx, level in enumerate(levels):
        rack = [deck.pop() for _ in range(14)]
        config = BotConfig(
            level=max(1, min(10, level)),
            randomness=max(0.0, min(1.0, randomness)),
            seed=seed + idx * 17,
        )
        players.append(PlayerState(player_id=f"Bot-{idx + 1}", rack=rack, opened=False))
        bots.append(BotFacade(config))

    state = GameState(
        board=Board(),
        players=players,
        pool=deck,
        current_player_idx=0,
        turn_number=1,
    )
    return state, bots


def _snapshot(state: GameState, turn: int, player_idx: int, move: Move, detail: str, bots: list[BotFacade]) -> TurnSnapshot:
    player = state.players[player_idx]
    board = [meld.short() for meld in state.board.melds]
    racks = {
        p.player_id: [tile.short() for tile in sorted(p.rack, key=lambda t: (t.is_joker, t.value or 0, str(t.color)))]
        for p in state.players
    }
    board_melds = [[tile.short() for tile in meld.tiles] for meld in state.board.melds]
    pool_counts: dict[str, int] = {}
    for tile in state.pool:
        key = tile.short()
        pool_counts[key] = pool_counts.get(key, 0) + 1

    pool_counts = dict(
        sorted(
            pool_counts.items(),
            key=lambda kv: (
                kv[0] == "J*",
                kv[0][0] if kv[0] != "J*" else "Z",
                int(kv[0][1:3]) if kv[0] != "J*" else 99,
            ),
        )
    )
    rack_points = {p.player_id: p.rack_points() for p in state.players}

    return TurnSnapshot(
        turn=turn,
        player_id=player.player_id,
        level=bots[player_idx].config.level,
        randomness=bots[player_idx].config.randomness,
        move=move.short(),
        detail=detail,
        rack_count=len(player.rack),
        pool_remaining=len(state.pool),
        board=board,
        racks=racks,
        board_melds=board_melds,
        pool_counts=pool_counts,
        rack_points=rack_points,
    )


def run_visual_simulation(
    levels: list[int],
    randomness: float,
    seed: int,
    max_turns: int,
    view_mode: ViewMode = ViewMode.FAIRPLAY,
) -> dict[str, Any]:
    state, bots = _init_state(levels, randomness, seed)
    timeline: list[dict[str, Any]] = []

    winner_id: str | None = None
    end_reason = "max_turns"
    blocked_passes = 0
    for turn in range(1, max_turns + 1):
        state.turn_number = turn
        player_idx = state.current_player_idx
        player = state.players[player_idx]
        bot = bots[player_idx]
        if view_mode == ViewMode.FAIRPLAY:
            move = bot.decide_turn_fairplay(state, player_idx)
        else:
            move = bot.decide_turn(state, player_idx)
        ok, detail = apply_move_inplace(state, player_idx, move, draw_on_pass=True)
        if not ok:
            _, penalty_detail = apply_move_inplace(
                state,
                player_idx,
                Move(move_type=MoveType.PASS_TURN),
                draw_on_pass=True,
            )
            detail = f"{detail}; penalizacion -> {penalty_detail}"

        if move.move_type == MoveType.PASS_TURN and detail.strip().lower() == "sin fichas para robar":
            blocked_passes += 1
        else:
            blocked_passes = 0

        timeline.append(asdict(_snapshot(state, turn, player_idx, move, detail, bots)))

        if len(player.rack) == 0:
            winner_id = player.player_id
            end_reason = "winner"
            break

        if blocked_passes >= len(state.players):
            end_reason = "blocked_no_moves_no_draw"
            break

        state.current_player_idx = (state.current_player_idx + 1) % len(state.players)

    final_points = {p.player_id: p.rack_points() for p in state.players}
    return {
        "seed": seed,
        "levels": levels,
        "randomness": randomness,
        "max_turns": max_turns,
        "winner_id": winner_id,
        "end_reason": end_reason,
        "turns_played": len(timeline),
        "timeline": timeline,
        "final_points": final_points,
    }


class AppHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._json_response({"ok": True})
            return
        return super().do_GET()

    def _handle_bot_move(self) -> None:
        """POST /api/bot/move: estado en JSON → jugada en JSON. Para Spring Boot."""
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response({"error": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            state = state_from_bot_request(payload)
            level = max(1, min(10, int(payload.get("level", 5))))
            randomness = max(0.0, min(1.0, float(payload.get("randomness", 0.25))))
            seed = payload.get("seed")
            if seed is not None:
                seed = int(seed)
            bot = BotFacade(BotConfig(level=level, randomness=randomness, seed=seed))
            move = bot.decide_turn(state, 0)
            self._json_response({
                "move": move_to_dict(move),
                "move_short": move.short(),
            })
        except ValueError as e:
            self._json_response({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json_response({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        if self.path == "/api/bot/move":
            self._handle_bot_move()
            return
        if self.path not in ["/api/run", "/api/run_simulation"]:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response({"error": "JSON invalido"}, status=HTTPStatus.BAD_REQUEST)
            return

        levels = payload.get("levels", [1, 5, 10])
        randomness = float(payload.get("randomness", 0.25))
        seed = int(payload.get("seed", 1234))
        max_turns = int(payload.get("max_turns", 300))
        view_mode_str = (payload.get("view_mode") or "fairplay").lower()
        view_mode = ViewMode.SIMULATION if view_mode_str == "simulation" else ViewMode.FAIRPLAY
        if not isinstance(levels, list) or not levels:
            self._json_response({"error": "levels debe ser una lista"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            norm_levels = [int(x) for x in levels]
        except ValueError:
            self._json_response({"error": "levels contiene valores no numericos"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            data = run_visual_simulation(
                levels=norm_levels,
                randomness=max(0.0, min(1.0, randomness)),
                seed=seed,
                max_turns=max(1, max_turns),
                view_mode=view_mode,
            )
            self._json_response(data)
        except Exception as e:
            import traceback
            error_msg = str(e)
            traceback.print_exc()
            self._json_response({"error": f"Error ejecutando simulacion: {error_msg}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor web para visualizar bots de Rummikub.")
    parser.add_argument("--host", default="127.0.0.1", help="Host de escucha")
    parser.add_argument("--port", type=int, default=8765, help="Puerto de escucha")
    args = parser.parse_args()

    handler_cls = partial(AppHandler, directory=str(BASE_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)
    print(f"UI lista en http://{args.host}:{args.port}")
    print("Pulsa Ctrl+C para salir.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
