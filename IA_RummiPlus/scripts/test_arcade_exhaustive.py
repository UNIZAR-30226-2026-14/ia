#!/usr/bin/env python3
"""
Suite de comprobaciones para modo arcade: API, motor, serialización y bot.

Ejecutar desde el directorio IA_RummiPlus:
  py -3 scripts/test_arcade_exhaustive.py
  # o: python scripts/test_arcade_exhaustive.py

Código de salida: 0 si todas las pruebas pasan, 1 si alguna falla.

Requisito: el directorio padre (IA_RummiPlus) esté en PYTHONPATH; el bloque
sys.path bajo asegura importación al ejecutar el script en local.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# IA_RummiPlus/ es el raíz del paquete
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rummiplus import (  # noqa: E402
    BotConfig,
    BotFacade,
    Color,
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
    item_use_to_dict,
    move_to_dict,
    shop_choice_to_dict,
    state_from_bot_request,
)
from rummiplus.core import Board, GameState, ArcadeState, tile_from_short  # noqa: E402
from rummiplus.move_logic import (  # noqa: E402
    apply_move_inplace,
    clone_state,
    opening_points,
    validate_move,
)
from rummiplus.rules import is_valid_meld  # noqa: E402
from rummiplus.ai import StrategicBot  # noqa: E402


# --- helpers -----------------------------------------------------------------

def _fail(msg: str) -> None:
    raise AssertionError(msg)


def _tile(short: str, uid: int) -> Tile:
    return tile_from_short(short, uid=uid)


# --- pruebas: core (fichas) --------------------------------------------------

def test_tile_serialization_roundtrip() -> None:
    assert _tile("B05D", 1).short() == "B05D"
    assert tile_from_short("B05AD", uid=0).short() in ("B05AD",)  # orden A,D,N
    t = _tile("R07D", 1)
    assert t.gold and t.points() == 14, "oro duplica"
    t2 = _tile("R10N", 2)
    assert t2.negative and t2.points() == -10, "negativa invierte"
    t3 = _tile("O08A", 3)
    assert t3.rainbow
    t4 = tile_from_short("O08A", uid=4)
    assert t4.short() == "O08A"


def test_opening_points_arcade() -> None:
    m = Meld(tiles=[_tile("B05D", 1), _tile("O05D", 2), _tile("K05D", 3)])
    pts = opening_points([m])
    assert pts == 30, f"3×5 duplicado = 30, got {pts}"


# --- pruebas: reglas (arcoíris) ----------------------------------------------

def test_rainbow_in_group() -> None:
    tiles = [
        _tile("B05A", 1),
        _tile("O05", 2),
        _tile("R05", 3),
        _tile("K05", 4),
    ]
    assert is_valid_meld(tiles), "grupo con arcoíris"


# --- pruebas: move_logic -----------------------------------------------------

def test_use_item_rejected_by_engine() -> None:
    dummy = _tile("B01", 1)
    p = PlayerState("b", [dummy])
    st = GameState(
        board=Board(melds=[]),
        players=[p],
        pool=[],
        arcade=ArcadeState(enabled=True, my_items=[ItemType.PLUS_FOUR]),
    )
    m = Move(
        move_type=MoveType.USE_ITEM,
        item_use=ItemUse(item=ItemType.PLUS_FOUR, reason="x"),
    )
    ok, reason = validate_move(st, 0, m)
    assert not ok and "use_item" in reason
    ok_apply, _ = apply_move_inplace(st, 0, m, draw_on_pass=True)
    assert not ok_apply, "USE_ITEM no debe aplicarse al motor"


def test_my_items_truncated_to_three_in_request() -> None:
    g = state_from_bot_request(
        {
            "board": [],
            "pool_count": 0,
            "my_tiles": [],
            "arcade": {
                "my_items": [
                    "PLUS_FOUR",
                    "MIDAS_TOUCH",
                    "CHILI_PEPPER",
                    "RUM_ROCKS",
                ],
            },
        }
    )
    assert g.arcade and len(g.arcade.my_items) == 3


def test_blocked_color() -> None:
    t1, t2, t3 = _tile("R05", 1), _tile("R06", 2), _tile("R07", 3)
    p = PlayerState("b", [t1, t2, t3], opened=True)
    st = GameState(
        board=Board(melds=[]),
        players=[p, PlayerState("o1", [], opened=True)],
        pool=[],
        opponent_rack_counts=[3, 10],
        arcade=ArcadeState(enabled=True, blocked_color=Color.RED),
    )
    play = Move(
        move_type=MoveType.PLAY_MELDS,
        new_melds=[Meld(tiles=[t1, t2, t3])],
    )
    ok, reason = validate_move(st, 0, play)
    assert not ok and "bloqueado" in reason, reason

    st2 = GameState(
        board=Board(melds=[]),
        players=[
            PlayerState(
                "b",
                [_tile("B05A", 1), _tile("B06A", 2), _tile("B07A", 3)],
                opened=True,
            ),
            PlayerState("o1", [], opened=True),
        ],
        pool=[],
        opponent_rack_counts=[3, 10],
        arcade=ArcadeState(enabled=True, blocked_color=Color.BLUE),
    )
    a1, a2, a3 = st2.players[0].rack
    play2 = Move(
        move_type=MoveType.PLAY_MELDS,
        new_melds=[Meld(tiles=[a1, a2, a3])],
    )
    v2, _ = validate_move(st2, 0, play2)
    assert v2, "arcoíris no bloqueada por color base"


def test_glass_ceiling_min_play() -> None:
    p = PlayerState("b", [_tile("B02", 1), _tile("B03", 2), _tile("B04", 3)], opened=True)
    st = GameState(
        board=Board(melds=[]),
        players=[p],
        pool=[],
        opponent_rack_counts=[3, 10],
        arcade=ArcadeState(enabled=True, min_play_points=30),
    )
    t1, t2, t3 = p.rack
    play = Move(
        move_type=MoveType.PLAY_MELDS,
        new_melds=[Meld(tiles=[t1, t2, t3])],
    )
    ok, reason = validate_move(st, 0, play)
    assert not ok and "techo" in reason, reason


def test_clone_state_arcade_lists() -> None:
    st = GameState(
        board=Board(melds=[]),
        players=[PlayerState("b", [], opened=True)],
        pool=[],
        arcade=ArcadeState(
            enabled=True,
            my_items=[ItemType.PLUS_FOUR],
            items_used_this_turn=[ItemType.MIDAS_TOUCH],
            shop_offer=[ShopOffer(item=ItemType.RUM_ROCKS, price=10)],
            guardian_angel_active=True,
        ),
    )
    c = clone_state(st)
    assert c.arcade is not None
    assert c.arcade.items_used_this_turn == [ItemType.MIDAS_TOUCH]
    assert c.arcade.shop_offer[0].price == 10
    assert c.arcade.guardian_angel_active is True
    c.arcade.items_used_this_turn.append(ItemType.PLUS_FOUR)
    assert len(st.arcade.items_used_this_turn) == 1, "clon profundo de listas"


# --- pruebas: API JSON -------------------------------------------------------

def test_state_from_bot_request_arcade() -> None:
    payload = {
        "board": [["B10", "B11", "B12"]],
        "pool_count": 5,
        "my_tiles": ["R01", "O02D", "B03A"],
        "opponent_rack_counts": [7, 2],
        "opened": True,
        "level": 5,
        "arcade": {
            "enabled": True,
            "blocked_color": "R",
            "min_play_points": 20,
            "my_items": ["PLUS_FOUR", "GUARDIAN_ANGEL"],
            "opponent_item_counts": [0, 1, 0],
            "time_limit_s": 45,
            "draw_at_turn_start": True,
            "items_used_this_turn": ["MIDAS_TOUCH"],
            "guardian_angel_active": False,
            "shop": {
                "offer": [
                    {"item": "CHILI_PEPPER", "price": 50},
                    {"item": "GUARDIAN_ANGEL", "price": 10},
                ],
                "balance": 100,
            },
        },
    }
    g = state_from_bot_request(payload)
    assert g.arcade is not None
    a = g.arcade
    assert a.blocked_color == Color.RED
    assert a.min_play_points == 20
    assert a.my_items == [ItemType.PLUS_FOUR, ItemType.GUARDIAN_ANGEL]
    assert a.items_used_this_turn == [ItemType.MIDAS_TOUCH]
    assert a.shop_balance == 100
    assert len(a.shop_offer) == 2
    assert a.guardian_angel_active is False
    # fichas
    assert g.players[0].rack[1].gold
    assert g.players[0].rack[2].rainbow


def test_state_from_bot_request_rejects_bad_item() -> None:
    try:
        state_from_bot_request(
            {
                "board": [],
                "pool_count": 0,
                "my_tiles": [],
                "arcade": {"my_items": ["NO_EXISTE"]},
            }
        )
        _fail("debía lanzar")
    except ValueError as e:
        assert "desconocido" in str(e).lower() or "NO_EXISTE" in str(e)


def test_state_from_bot_request_rejects_negative_shop_price() -> None:
    try:
        state_from_bot_request(
            {
                "board": [],
                "pool_count": 0,
                "my_tiles": [],
                "arcade": {
                    "shop": {
                        "offer": [{"item": "PLUS_FOUR", "price": -5}],
                        "balance": 0,
                    }
                },
            }
        )
        _fail("precio negativo")
    except ValueError as e:
        assert "negativo" in str(e).lower() or "price" in str(e).lower()


def test_move_to_dict_variants() -> None:
    t = _tile("B01", 1)
    m_pass = move_to_dict(Move(move_type=MoveType.PASS_TURN))
    assert m_pass["move_type"] == "pass"
    assert "shop_choice" not in m_pass

    iu = ItemUse(
        item=ItemType.CRYSTAL_BALL,
        target_player_idx=None,
        reason="r",
        params={"color": "B", "value_range": [1, 7]},
    )
    m_ui = move_to_dict(
        Move(
            move_type=MoveType.USE_ITEM,
            item_use=iu,
            reason="u",
        )
    )
    assert m_ui["move_type"] == "use_item"
    assert m_ui["item_use"]["item"] == "CRYSTAL_BALL"
    assert m_ui["item_use"]["params"]["color"] == "B"
    assert "new_melds" not in m_ui
    assert "shop_choice" not in m_ui

    m_play = move_to_dict(
        Move(
            move_type=MoveType.PLAY_MELDS,
            new_melds=[Meld(tiles=[t])],
            shop_choice=ShopChoice(buy=ItemType.MIDAS_TOUCH, reason="c"),
        )
    )
    assert m_play["new_melds"] == [["B01"]]
    assert m_play["shop_choice"]["buy"] == "MIDAS_TOUCH"

    d_item = item_use_to_dict(
        ItemUse(
            item=ItemType.TRUTH_MAGNIFIER,
            target_player_idx=1,
            reason="x",
        )
    )
    assert d_item["target_player_idx"] == 1
    sc = shop_choice_to_dict(ShopChoice(buy=None, reason="no"))
    assert sc["buy"] is None


def test_move_to_dict_orders_output_meld_tiles() -> None:
    """La serialización ordena fichas en melds de salida (new_melds/new_board)."""
    t1 = _tile("R03", 1)
    t2 = _tile("B03", 2)
    t3 = _tile("K03", 3)
    t4 = _tile("O03", 4)

    m_play = move_to_dict(
        Move(
            move_type=MoveType.PLAY_MELDS,
            new_melds=[Meld(tiles=[t1, t2, t3, t4])],
        )
    )
    assert m_play["new_melds"] == [["B03", "K03", "O03", "R03"]]

    m_replace = move_to_dict(
        Move(
            move_type=MoveType.REPLACE_BOARD,
            new_board=[Meld(tiles=[t1, t3, t2])],
        )
    )
    assert m_replace["new_board"] == [["B03", "K03", "R03"]]


def test_json_roundtrip_use_item() -> None:
    m = move_to_dict(
        Move(
            move_type=MoveType.USE_ITEM,
            item_use=ItemUse(
                item=ItemType.SWAP_ON_FAIL,
                target_player_idx=2,
                reason="t",
            ),
        )
    )
    s = json.dumps(m, ensure_ascii=False)
    back = json.loads(s)
    assert back["move_type"] == "use_item"
    assert back["item_use"]["item"] == "SWAP_ON_FAIL"


# --- pruebas: bot arcade (heurísticas) ---------------------------------------

def test_bot_use_item_plus_four_when_rival_low() -> None:
    """Rival con ≤3 fichas y PLUS_FOUR en mano => use_item antes que jugada."""
    cfg = BotConfig(level=5, randomness=0.0, seed=42)
    bot = StrategicBot(cfg)
    # mano mínima legal para no quedarse sin opciones
    tiles = [
        _tile("B02", 1),
        _tile("B03", 2),
        _tile("B04", 3),
        _tile("B05", 4),
        _tile("B06", 5),
    ]
    st = GameState(
        board=Board(melds=[]),
        players=[
            PlayerState("b", tiles, opened=True),
            PlayerState("o1", [], opened=True),
            PlayerState("o2", [], opened=True),
        ],
        pool=[_tile("K01", 99)] * 20,
        opponent_rack_counts=[5, 5, 2],
        arcade=ArcadeState(
            enabled=True,
            my_items=[ItemType.PLUS_FOUR, ItemType.MIDAS_TOUCH],
        ),
    )
    move = bot.choose_move(st, 0)
    assert move.move_type == MoveType.USE_ITEM, move
    assert move.item_use is not None
    assert move.item_use.item == ItemType.PLUS_FOUR
    # o2 tiene el mínimo (2) entre rivales
    assert move.item_use.target_player_idx == 2


def test_bot_item_not_repeated_if_in_items_used() -> None:
    """Con PLUS_FOUR ya en items_used_this_turn, el filtro vacía y no hay use_item
    (my_items solo contenía PLUS_FOUR, queda sin sugerir objetos)."""
    cfg = BotConfig(level=5, randomness=0.0, seed=1)
    bot = StrategicBot(cfg)
    tiles = [
        _tile("B02", 1),
        _tile("B03", 2),
        _tile("B04", 3),
    ]
    st = GameState(
        board=Board(melds=[]),
        players=[
            PlayerState("b", tiles, opened=True),
            PlayerState("o1", [], opened=True),
        ],
        pool=[_tile("K01", 99)] * 20,
        opponent_rack_counts=[3, 2],
        arcade=ArcadeState(
            enabled=True,
            my_items=[ItemType.PLUS_FOUR],
            items_used_this_turn=[ItemType.PLUS_FOUR],
        ),
    )
    move = bot.choose_move(st, 0)
    assert move.move_type != MoveType.USE_ITEM, (
        "no debería proponer use_item sin objetos 'disponibles' tras el filtro"
    )


def test_bot_truth_magnifier_high_level_rival_not_priority() -> None:
    """Un solo oponente con >3 fichas: no salta el bloque 'casi gana';
    nivel 8+ con solo lupa en inventario sugiere TRUTH_MAGNIFIER."""
    cfg = BotConfig(level=8, randomness=0.0, seed=1)
    bot = StrategicBot(cfg)
    st = GameState(
        board=Board(melds=[Meld(tiles=[_tile("O01", 1), _tile("O02", 2), _tile("O03", 3)])]),
        players=[
            PlayerState("b", [_tile("B05", 10), _tile("B06", 11), _tile("B07", 12)], opened=True),
            PlayerState("o1", [], opened=True),
        ],
        pool=[_tile("K01", 99)] * 5,
        # [bot(3), rival(10)]: el rival no está a punto de ganar (>3)
        opponent_rack_counts=[3, 10],
        arcade=ArcadeState(
            enabled=True,
            my_items=[ItemType.TRUTH_MAGNIFIER],
        ),
    )
    move = bot.choose_move(st, 0)
    assert move.move_type == MoveType.USE_ITEM
    assert move.item_use and move.item_use.item == ItemType.TRUTH_MAGNIFIER


def test_shop_guards_angel_not_bought_if_active() -> None:
    bot = StrategicBot(BotConfig(level=7, randomness=0.0, seed=1))
    ch = bot.choose_shop_item(
        offer=[ShopOffer(item=ItemType.GUARDIAN_ANGEL, price=1)],
        balance=100,
        current_items=[],
        opponent_rack_counts=[5],
        my_tiles_count=10,
        my_opened=True,
        guardian_angel_active=True,
    )
    assert ch.buy is None, ch


def test_shop_guards_angel_not_bought_if_pending_in_inventory() -> None:
    bot = StrategicBot(BotConfig(level=7, randomness=0.0, seed=1))
    ch = bot.choose_shop_item(
        offer=[ShopOffer(item=ItemType.GUARDIAN_ANGEL, price=1)],
        balance=100,
        current_items=[ItemType.GUARDIAN_ANGEL],
        opponent_rack_counts=[5],
        my_tiles_count=10,
        my_opened=True,
        guardian_angel_active=False,
    )
    assert ch.buy is None


def test_shop_midas_when_angel_offered_with_guard() -> None:
    bot = StrategicBot(BotConfig(level=7, randomness=0.0, seed=1))
    ch = bot.choose_shop_item(
        offer=[
            ShopOffer(item=ItemType.GUARDIAN_ANGEL, price=1),
            ShopOffer(item=ItemType.MIDAS_TOUCH, price=2),
        ],
        balance=100,
        current_items=[],
        opponent_rack_counts=[5],
        my_tiles_count=10,
        my_opened=True,
        guardian_angel_active=True,
    )
    assert ch.buy == ItemType.MIDAS_TOUCH, ch


def test_facade_decide_shop_passes_flag() -> None:
    f = BotFacade(BotConfig(level=7, randomness=0.0, seed=1))
    c = f.decide_shop(
        [ShopOffer(item=ItemType.GUARDIAN_ANGEL, price=1)],
        balance=50,
        current_items=[],
        opponent_rack_counts=[6],
        my_tiles_count=7,
        my_opened=True,
        guardian_angel_active=True,
    )
    assert c.buy is None


# --- pruebas: modo normal vs arcade (regresión) -----------------------------

def test_classic_legal_pass_and_no_arcade() -> None:
    deck = build_classic_deck()
    t = deck[0:5]
    st = GameState(
        board=Board(melds=[]),
        players=[PlayerState("b", t, opened=False)],
        pool=deck[5:20],
    )
    m = Move(move_type=MoveType.PASS_TURN)
    assert validate_move(st, 0, m)[0]
    b = clone_state(st)
    ok, _ = apply_move_inplace(b, 0, m, draw_on_pass=True)
    assert ok and len(b.players[0].rack) == 6, "pasa y roba"


# --- listado y main ----------------------------------------------------------

ALL_TESTS = [
    test_tile_serialization_roundtrip,
    test_opening_points_arcade,
    test_rainbow_in_group,
    test_use_item_rejected_by_engine,
    test_my_items_truncated_to_three_in_request,
    test_blocked_color,
    test_glass_ceiling_min_play,
    test_clone_state_arcade_lists,
    test_state_from_bot_request_arcade,
    test_state_from_bot_request_rejects_bad_item,
    test_state_from_bot_request_rejects_negative_shop_price,
    test_move_to_dict_variants,
    test_move_to_dict_orders_output_meld_tiles,
    test_json_roundtrip_use_item,
    test_bot_use_item_plus_four_when_rival_low,
    test_bot_item_not_repeated_if_in_items_used,
    test_bot_truth_magnifier_high_level_rival_not_priority,
    test_shop_guards_angel_not_bought_if_active,
    test_shop_guards_angel_not_bought_if_pending_in_inventory,
    test_shop_midas_when_angel_offered_with_guard,
    test_facade_decide_shop_passes_flag,
    test_classic_legal_pass_and_no_arcade,
]


def main() -> int:
    failed = 0
    for fn in ALL_TESTS:
        name = fn.__name__
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FALLA  {name}: {e}")
            traceback.print_exc()
        else:
            print(f"OK     {name}")
    print("-" * 60)
    if failed:
        print(f"Resumen: {failed} fallo(s) de {len(ALL_TESTS)} pruebas.")
        return 1
    print(f"Resumen: {len(ALL_TESTS)} pruebas superadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
