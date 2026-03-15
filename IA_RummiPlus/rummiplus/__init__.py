"""
RummiPlus: motor y bots de Rummikub clásico.

Expone la API pública (BotConfig, BotFacade, make_fairplay_view, move_to_dict,
state_from_bot_request), tipos de datos (GameState, Move, Tile, ...) y el motor
de simulación (SimulationConfig, run_simulation). El bot es heurístico con
búsqueda minimax acotada; ver rummiplus.ai para detalles.
"""

from .api import BotConfig, BotFacade, ViewMode, make_fairplay_view, move_to_dict, state_from_bot_request
from .core import (
    Board,
    Color,
    GameState,
    Meld,
    Move,
    MoveType,
    PlayerState,
    Tile,
    build_classic_deck,
)
from .engine import SimulationConfig, run_simulation

__all__ = [
    "BotConfig",
    "BotFacade",
    "ViewMode",
    "make_fairplay_view",
    "move_to_dict",
    "state_from_bot_request",
    "Board",
    "Color",
    "GameState",
    "Meld",
    "Move",
    "MoveType",
    "PlayerState",
    "Tile",
    "build_classic_deck",
    "SimulationConfig",
    "run_simulation",
]
