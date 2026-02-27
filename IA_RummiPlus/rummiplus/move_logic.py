from __future__ import annotations

from .core import GameState, Meld, Move, MoveType, PlayerState
from .rules import extend_meld_with_tile, is_valid_meld

OPENING_MIN_POINTS = 30


def opening_points(melds: list[Meld]) -> int:
    # Regla clásica: para apertura contamos solo fichas no comodín.
    return sum(t.points() for meld in melds for t in meld.tiles if not t.is_joker)


def clone_state(state: GameState) -> GameState:
    return GameState(
        board=state.board.clone(),
        players=[
            PlayerState(player_id=p.player_id, rack=list(p.rack), opened=p.opened)
            for p in state.players
        ],
        pool=list(state.pool),
        current_player_idx=state.current_player_idx,
        turn_number=state.turn_number,
    )


def validate_move(state: GameState, player_idx: int, move: Move) -> tuple[bool, str]:
    player = state.players[player_idx]

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
        return True, "replace_board legal"

    return False, "tipo de jugada no reconocido"


def _draw_tile(state: GameState, player: PlayerState) -> str:
    if not state.pool:
        return "sin fichas para robar"
    tile = state.pool.pop()
    player.rack.append(tile)
    return f"roba {tile.short()}"


def apply_move_inplace(
    state: GameState, player_idx: int, move: Move, draw_on_pass: bool = True
) -> tuple[bool, str]:
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
