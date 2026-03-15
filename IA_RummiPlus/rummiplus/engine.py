"""
Motor de simulación de partidas entre bots (sin UI).

Inicializa estado y bots a partir de SimulationConfig, ejecuta turnos en bucle:
cada turno el bot correspondiente decide (fairplay o simulación según view_mode),
se aplica la jugada y se rota el turno hasta que alguien vacíe la mano o se
alcance max_turns. Opcionalmente registra logs por turno.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .api import BotConfig, BotFacade, ViewMode
from .core import Board, GameState, Move, MoveType, PlayerState, build_classic_deck
from .move_logic import apply_move_inplace


@dataclass(frozen=True)
class SimulationConfig:
    bot_configs: list[BotConfig]
    seed: int | None = None
    max_turns: int = 120
    initial_rack_size: int = 14
    view_mode: ViewMode = ViewMode.FAIRPLAY
    """FAIRPLAY: cada bot solo ve tablero, bolsa y sus fichas. SIMULATION: estado completo."""


@dataclass
class SimulationResult:
    """Resultado de una partida: ganador (o None), turnos jugados, logs y puntos por jugador."""
    winner_id: str | None
    turns_played: int
    logs: list[str] = field(default_factory=list)
    final_rack_points: dict[str, int] = field(default_factory=dict)


def _init_state(cfg: SimulationConfig) -> tuple[GameState, list[BotFacade]]:
    """
    Crea el mazo, lo baraja, reparte initial_rack_size fichas por bot y devuelve
    el estado inicial y la lista de BotFacade (uno por bot_configs).
    """
    rng = random.Random(cfg.seed)
    deck = build_classic_deck()
    rng.shuffle(deck)

    players: list[PlayerState] = []
    bots: list[BotFacade] = []
    for idx, bot_cfg in enumerate(cfg.bot_configs):
        rack = [deck.pop() for _ in range(cfg.initial_rack_size)]
        players.append(PlayerState(player_id=f"Bot-{idx+1}", rack=rack, opened=False))
        bots.append(BotFacade(bot_cfg))

    state = GameState(board=Board(), players=players, pool=deck, current_player_idx=0, turn_number=1)
    return state, bots


def run_simulation(cfg: SimulationConfig) -> SimulationResult:
    """
    Ejecuta una partida completa: en cada turno el bot correspondiente elige
    jugada (fairplay o simulación según cfg.view_mode), se aplica y se pasa al
    siguiente. Si la jugada es ilegal se penaliza con robo. Devuelve ganador,
    número de turnos, logs y puntos finales por jugador.
    """
    state, bots = _init_state(cfg)
    logs: list[str] = []

    winner_id: str | None = None
    for turn in range(1, cfg.max_turns + 1):
        state.turn_number = turn
        bot = bots[state.current_player_idx]
        if cfg.view_mode == ViewMode.FAIRPLAY:
            move = bot.decide_turn_fairplay(state, state.current_player_idx)
        else:
            move = bot.decide_turn(state, state.current_player_idx)
        ok, detail = apply_move_inplace(
            state, state.current_player_idx, move, draw_on_pass=True
        )
        if not ok:
            # Jugada ilegal: forzar pasar y robar como penalización.
            _, penalty = apply_move_inplace(
                state,
                state.current_player_idx,
                Move(move_type=MoveType.PASS_TURN),
                draw_on_pass=True,
            )
            detail = f"{detail}; penalización -> {penalty}"

        player = state.current_player()

        logs.append(
            f"T{turn:03d} {player.player_id} (nivel={bot.config.level}, "
            f"aleatoriedad={bot.config.randomness:.2f}) => {move.short()} | {detail} | "
            f"rack={len(player.rack)}"
        )

        if len(player.rack) == 0:
            winner_id = player.player_id
            break

        state.current_player_idx = (state.current_player_idx + 1) % len(state.players)

    points = {p.player_id: p.rack_points() for p in state.players}
    return SimulationResult(
        winner_id=winner_id,
        turns_played=turn if winner_id else cfg.max_turns,
        logs=logs,
        final_rack_points=points,
    )
