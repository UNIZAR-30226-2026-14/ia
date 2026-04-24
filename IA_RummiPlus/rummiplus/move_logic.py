"""
Lógica de jugadas: validación, clonado de estado y aplicación en sitio.

Valida que una Move sea legal (fichas del rack, melds válidos, apertura ≥30),
clona GameState para búsqueda y aplica la jugada modificando el estado in-place
(quitar fichas del rack, añadir al tablero, robar de la bolsa al pasar).

En modo arcade, validate_move respeta también dos restricciones opcionales del
ArcadeState acompañante: color bloqueado (no se pueden jugar fichas de ese
color) y techo de cristal (la jugada debe sumar al menos min_play_points).
"""

from __future__ import annotations

from dataclasses import replace

from .core import ArcadeState, GameState, Meld, Move, MoveType, PlayerState, Tile
from .rules import extend_meld_with_tile, is_valid_meld

OPENING_MIN_POINTS = 30


def opening_points(melds: list[Meld]) -> int:
    """
    Puntos que cuentan para la apertura: solo fichas no comodín (regla clásica).
    En modo arcade, las fichas doradas/negativas aportan sus puntos con
    modificador (t.points() ya incorpora el signo y la duplicación).
    """
    return sum(t.points() for meld in melds for t in meld.tiles if not t.is_joker)


def _played_tiles(move: Move, state: GameState, player_idx: int) -> list[Tile]:
    """
    Lista de fichas que el jugador añade al tablero en esta jugada (no incluye
    fichas que ya estaban en el tablero y solo se reorganizan).
    Usado para aplicar restricciones arcade (color bloqueado, techo de cristal).
    """
    if move.move_type == MoveType.PLAY_MELDS:
        return [t for meld in move.new_melds for t in meld.tiles]
    if move.move_type == MoveType.EXTEND_MELD:
        return list(move.extension_tiles)
    if move.move_type == MoveType.REPLACE_BOARD:
        board_uids = {t.uid for m in state.board.melds for t in m.tiles}
        rack_uids = {t.uid for t in state.players[player_idx].rack}
        rack_by_uid = {t.uid: t for t in state.players[player_idx].rack}
        played: list[Tile] = []
        for meld in move.new_board:
            for t in meld.tiles:
                if t.uid in rack_uids and t.uid not in board_uids:
                    played.append(rack_by_uid[t.uid])
        return played
    return []


def clone_state(state: GameState) -> GameState:
    """
    Copia profunda del estado (tablero, jugadores, bolsa, turno).
    Necesario para simular jugadas en la búsqueda sin alterar el estado real.
    En modo arcade se copia también el ArcadeState (inventarios y restricciones).
    """
    arcade_copy: ArcadeState | None = None
    if state.arcade is not None:
        arcade_copy = replace(
            state.arcade,
            my_items=list(state.arcade.my_items),
            opponent_item_counts=list(state.arcade.opponent_item_counts),
            shop_offer=list(state.arcade.shop_offer),
            items_used_this_turn=list(state.arcade.items_used_this_turn),
        )
    return GameState(
        board=state.board.clone(),
        players=[
            PlayerState(player_id=p.player_id, rack=list(p.rack), opened=p.opened)
            for p in state.players
        ],
        pool=list(state.pool),
        current_player_idx=state.current_player_idx,
        turn_number=state.turn_number,
        opponent_rack_counts=list(state.opponent_rack_counts) if state.opponent_rack_counts is not None else None,
        arcade=arcade_copy,
    )


def _validate_arcade_constraints(
    state: GameState, player_idx: int, move: Move
) -> tuple[bool, str]:
    """
    Valida las restricciones del modo arcade sobre una jugada ya legal en el
    sentido clásico: color bloqueado y techo de cristal (min_play_points).
    Devuelve (True, '') si no hay violación o no hay ArcadeState activo.
    PASS_TURN nunca viola estas restricciones.
    """
    arcade = state.arcade
    if arcade is None or not arcade.enabled:
        return True, ""
    if move.move_type == MoveType.PASS_TURN:
        return True, ""

    played = _played_tiles(move, state, player_idx)

    if arcade.blocked_color is not None:
        for t in played:
            # Las fichas arcoíris (habilidad 'A') no están ligadas a su color
            # base: actúan como color flexible y no las afecta el bloqueo.
            if t.rainbow:
                continue
            if t.color == arcade.blocked_color:
                return False, f"arcade: color bloqueado {arcade.blocked_color.value}"

    if arcade.min_play_points is not None:
        played_points = sum(t.points() for t in played)
        if played_points < arcade.min_play_points:
            return (
                False,
                f"arcade: techo de cristal {played_points} < {arcade.min_play_points}",
            )
    return True, ""


def validate_move(state: GameState, player_idx: int, move: Move) -> tuple[bool, str]:
    """
    Comprueba si la jugada es legal: fichas en el rack, melds válidos, apertura
    ≥30 si aplica, extensión/reorganización coherente. Devuelve (True, detalle)
    o (False, mensaje de error).

    En modo arcade también se comprueban restricciones del ArcadeState
    acompañante: color bloqueado y techo de cristal (min_play_points).

    El tipo USE_ITEM no es una jugada del motor clásico (solo una señal a
    nivel de API para que el backend ejecute un objeto y vuelva a preguntar);
    no se valida ni aplica aquí: validate_move y apply_move_inplace lo
    rechazan explícitamente. Se emite únicamente como respuesta en
    choose_move y se serializa en move_to_dict.
    """
    player = state.players[player_idx]

    if move.move_type == MoveType.USE_ITEM:
        return False, "use_item no es una jugada del motor (solo respuesta de API)"

    if move.move_type == MoveType.PASS_TURN:
        return True, "pass legal"

    if move.move_type == MoveType.PLAY_MELDS:
        if not move.new_melds:
            return False, "jugada inválida: sin melds"
        used_ids: list[int] = []
        for meld in move.new_melds:
            if not is_valid_meld(meld.tiles):
                return False, f"meld inválido {meld.short()}"
            used_ids.extend(t.uid for t in meld.tiles)

        if len(set(used_ids)) != len(used_ids):
            return False, "jugada inválida: fichas repetidas"

        rack_ids = {t.uid for t in player.rack}
        if any(uid not in rack_ids for uid in used_ids):
            return False, "jugada inválida: ficha fuera del rack"

        if not player.opened:
            points = opening_points(move.new_melds)
            if points < OPENING_MIN_POINTS:
                return False, f"apertura inválida: {points} < {OPENING_MIN_POINTS}"
        ok_arcade, reason_arcade = _validate_arcade_constraints(state, player_idx, move)
        if not ok_arcade:
            return False, reason_arcade
        return True, "play legal"

    if move.move_type == MoveType.EXTEND_MELD:
        if move.extend_index is None or len(move.extension_tiles) != 1:
            return False, "extensión inválida"
        if not player.opened:
            return False, "no puede extender antes de abrir"
        if move.extend_index < 0 or move.extend_index >= len(state.board.melds):
            return False, "índice de meld inválido"

        tile = move.extension_tiles[0]
        rack_tile = next((t for t in player.rack if t.uid == tile.uid), None)
        if rack_tile is None:
            return False, "ficha de extensión no está en rack"

        target = state.board.melds[move.extend_index]
        if extend_meld_with_tile(target, rack_tile) is None:
            return False, "extensión no legal"
        ok_arcade, reason_arcade = _validate_arcade_constraints(state, player_idx, move)
        if not ok_arcade:
            return False, reason_arcade
        return True, "extend legal"

    if move.move_type == MoveType.REPLACE_BOARD:
        if not move.new_board:
            return False, "reorganización sin melds"
        board_uids = {t.uid for m in state.board.melds for t in m.tiles}
        rack_uids = {t.uid for t in player.rack}
        new_uids: list[int] = []
        for meld in move.new_board:
            if not is_valid_meld(meld.tiles):
                return False, f"meld inválido en reorganización: {meld.short()}"
            for t in meld.tiles:
                new_uids.append(t.uid)
        if len(new_uids) != len(set(new_uids)):
            return False, "reorganización: fichas repetidas"
        new_uid_set = set(new_uids)
        if not new_uid_set <= (board_uids | rack_uids):
            return False, "reorganización: ficha no está en tablero ni en mano"
        from_board = new_uid_set & board_uids
        from_rack = new_uid_set - board_uids
        if not player.opened and from_rack:
            points_from_hand = sum(
                t.points() for meld in move.new_board for t in meld.tiles
                if t.uid in from_rack and not t.is_joker
            )
            if points_from_hand < OPENING_MIN_POINTS:
                return False, f"apertura en reorganización: {points_from_hand} < {OPENING_MIN_POINTS}"
        ok_arcade, reason_arcade = _validate_arcade_constraints(state, player_idx, move)
        if not ok_arcade:
            return False, reason_arcade
        return True, "replace_board legal"

    return False, "tipo de jugada no reconocido"


def _draw_tile(state: GameState, player: PlayerState) -> str:
    """Roba una ficha de la bolsa y la añade al rack del jugador. Devuelve mensaje."""
    if not state.pool:
        return "sin fichas para robar"
    tile = state.pool.pop()
    player.rack.append(tile)
    return f"roba {tile.short()}"


def apply_move_inplace(
    state: GameState, player_idx: int, move: Move, draw_on_pass: bool = True
) -> tuple[bool, str]:
    """
    Valida la jugada y, si es legal, la aplica modificando state in-place:
    quitar fichas del rack, actualizar tablero, opcionalmente robar al pasar.
    Devuelve (True, detalle) o (False, motivo).
    """
    ok, reason = validate_move(state, player_idx, move)
    if not ok:
        return False, reason

    player = state.players[player_idx]

    if move.move_type == MoveType.PASS_TURN:
        if draw_on_pass:
            return True, _draw_tile(state, player)
        return True, "pass sin robo"

    if move.move_type == MoveType.PLAY_MELDS:
        used_set = {t.uid for meld in move.new_melds for t in meld.tiles}
        player.rack = [tile for tile in player.rack if tile.uid not in used_set]
        state.board.melds.extend(move.new_melds)
        player.opened = True
        return True, f"juega {move.short()}"

    if move.move_type == MoveType.EXTEND_MELD:
        target = state.board.melds[move.extend_index]  # type: ignore[index]
        rack_tile = next(t for t in player.rack if t.uid == move.extension_tiles[0].uid)
        extended = extend_meld_with_tile(target, rack_tile)
        if extended is None:
            return False, "extensión no legal"
        state.board.melds[move.extend_index] = extended  # type: ignore[index]
        player.rack = [t for t in player.rack if t.uid != rack_tile.uid]
        return True, f"extiende {move.short()}"

    if move.move_type == MoveType.REPLACE_BOARD:
        board_uids = {t.uid for m in state.board.melds for t in m.tiles}
        new_uid_set = {t.uid for m in move.new_board for t in m.tiles}
        from_rack_uids = new_uid_set - board_uids
        state.board.melds = list(move.new_board)
        player.rack = [t for t in player.rack if t.uid not in from_rack_uids]
        player.opened = True
        return True, f"reorganiza tablero ({len(move.new_board)} melds)"

    return False, reason
