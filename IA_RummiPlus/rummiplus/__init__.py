"""
RummiPlus: motor y bots de Rummikub clásico (modo normal) con soporte opcional
para modo arcade (objetos, fichas especiales y eventos de ronda).

Expone la API pública (BotConfig, BotFacade, make_fairplay_view, move_to_dict,
state_from_bot_request), tipos de datos (GameState, Move, Tile, ...), tipos de
modo arcade (ArcadeState, ItemType, ItemUse) y el motor de simulación
(SimulationConfig, run_simulation). El bot es heurístico con búsqueda minimax
acotada; ver rummiplus.ai para detalles.
"""

from .api import (
    BotConfig,
    BotFacade,
    ViewMode,
    item_use_to_dict,
    make_fairplay_view,
    move_to_dict,
    shop_choice_to_dict,
    state_from_bot_request,
)
from .core import (
    ArcadeState,
    Board,
    Color,
    GameState,
    ItemType,
    ItemUse,
    Meld,
    Move,
    MoveType,
    PlayerState,
    ShopChoice,
    ShopOffer,
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
    "item_use_to_dict",
    "shop_choice_to_dict",
    "state_from_bot_request",
    "ArcadeState",
    "Board",
    "Color",
    "GameState",
    "ItemType",
    "ItemUse",
    "Meld",
    "Move",
    "MoveType",
    "PlayerState",
    "ShopChoice",
    "ShopOffer",
    "Tile",
    "build_classic_deck",
    "SimulationConfig",
    "run_simulation",
]
