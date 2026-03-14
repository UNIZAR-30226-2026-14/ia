from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from .core import GameState, Meld, Move, MoveType, PlayerState, Tile
from .move_logic import apply_move_inplace, clone_state, opening_points, validate_move
from .rules import (
    extend_meld_with_tile,
    find_opening_combos,
    generate_meld_candidates,
    is_valid_meld,
    rack_without_tiles,
)


@dataclass(frozen=True)
class BotConfig:
    level: int = 5
    randomness: float = 0.25
    seed: int | None = None
    max_opening_options: int = 40
    max_regular_options: int = 60
    search_time_ms: int = 80
    search_depth_cap: int = 3
    search_beam_cap: int = 14

    def skill(self) -> float:
        lvl = max(1, min(10, self.level))
        return (lvl - 1) / 9.0


@dataclass
class ScoredMove:
    move: Move
    score: float
    used_tiles: list[Tile]
    debug: str


class StrategicBot:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self._search_cache: dict[tuple[str, int, int], float] = {}

    def choose_move(self, state: GameState, player_idx: int) -> Move:
        options = self._generate_options(state, player_idx)
        if not options:
            return Move(move_type=MoveType.PASS_TURN, reason="sin opciones legales")

        if self.config.level >= 3 and len(options) > 1:
            options = self._score_with_search(state, player_idx, options)
        return self._select_option(options).move

    def _effective_limits(self) -> tuple[int, int, int]:
        """Límites de opciones según nivel: menos opciones = bots bajos más débiles."""
        skill = self.config.skill()
        max_open = max(5, min(self.config.max_opening_options, int(5 + skill * 35)))
        max_regular = max(10, min(self.config.max_regular_options, int(10 + skill * 50)))
        replace_max = max(15, min(50, int(15 + skill * 35)))
        return max_open, max_regular, replace_max

    def _generate_options(self, state: GameState, player_idx: int) -> list[ScoredMove]:
        player = state.players[player_idx]
        options: list[ScoredMove] = []
        rack = player.rack
        max_open, max_regular, replace_max = self._effective_limits()

        if not player.opened:
            opening = find_opening_combos(
                rack,
                min_points=30,
                limit=max_open,
            )
            for melds in opening:
                if opening_points(melds) < 30:
                    continue
                used = [t for meld in melds for t in meld.tiles]
                score = self._evaluate_used_tiles(rack, used, opening=True)
                options.append(
                    ScoredMove(
                        move=Move(
                            move_type=MoveType.PLAY_MELDS,
                            new_melds=melds,
                            reason="apertura 30+",
                        ),
                        score=score,
                        used_tiles=used,
                        debug=f"open points={sum(t.points() for t in used)}",
                    )
                )
            options.append(
                ScoredMove(
                    move=Move(move_type=MoveType.PASS_TURN, reason="no abrir todavía"),
                    score=-3.0,
                    used_tiles=[],
                    debug="pass",
                )
            )
            return self._filter_legal(state, player_idx, options)

        # Jugadas normales: nuevos grupos/escaleras desde rack.
        # Reducir ligeramente el score para favorecer reorganizaciones cuando hay tablero
        melds = generate_meld_candidates(rack, max_size=5)
        board_penalty = -1.0 if state.board.melds else 0.0  # Penalizar jugadas nuevas si hay tablero
        for meld in melds:
            used = list(meld.tiles)
            options.append(
                ScoredMove(
                    move=Move(
                        move_type=MoveType.PLAY_MELDS,
                        new_melds=[meld],
                        reason="nuevo meld",
                    ),
                    score=self._evaluate_used_tiles(rack, used, opening=False) + board_penalty,
                    used_tiles=used,
                    debug=f"new meld size={len(used)}",
                )
            )

        # Combinar 2 melds disjuntos para jugadas más fuertes.
        top_melds = sorted(melds, key=lambda m: m.points(), reverse=True)[:18]
        for i, left in enumerate(top_melds):
            ids_left = {t.uid for t in left.tiles}
            for right in top_melds[i + 1 :]:
                ids_right = {t.uid for t in right.tiles}
                if ids_left & ids_right:
                    continue
                used = list(left.tiles) + list(right.tiles)
                options.append(
                    ScoredMove(
                        move=Move(
                            move_type=MoveType.PLAY_MELDS,
                            new_melds=[left, right],
                            reason="doble meld",
                        ),
                        score=self._evaluate_used_tiles(rack, used, opening=False) + 2.0 + board_penalty,
                        used_tiles=used,
                        debug="double meld",
                    )
                )

        # Extensiones sencillas al tablero.
        for board_idx, board_meld in enumerate(state.board.melds):
            for tile in rack:
                extended = extend_meld_with_tile(board_meld, tile)
                if not extended:
                    continue
                # Reducir ligeramente el score de extensiones para favorecer reorganizaciones
                options.append(
                    ScoredMove(
                        move=Move(
                            move_type=MoveType.EXTEND_MELD,
                            extend_index=board_idx,
                            extension_tiles=[tile],
                            reason="extensión",
                        ),
                        score=self._evaluate_used_tiles(rack, [tile], opening=False) + 0.3,
                        used_tiles=[tile],
                        debug=f"extend #{board_idx}",
                    )
                )

        # Reorganizar tablero: coger fichas de melds y formar nuevos conjuntos con la mano.
        # Solo si el jugador ya abrió y hay melds en el tablero.
        if player.opened and state.board.melds:
            replace_count = 0
            pool_size = len(state.pool)
            # Bonus por reorganizar cuando la bolsa está vacía o casi vacía.
            pool_bonus = max(0, (100 - pool_size) * 0.25) if pool_size < 50 else 0.0
            # Caso 1: tomar una ficha de un meld y formar uno o más melds nuevos.
            for board_idx, board_meld in enumerate(state.board.melds):
                if replace_count >= replace_max:
                    break
                for tile in board_meld.tiles:
                    if replace_count >= replace_max:
                        break
                    remaining = [t for t in board_meld.tiles if t.uid != tile.uid]
                    if remaining and not is_valid_meld(remaining):
                        continue
                    freed = tile
                    other_melds = [
                        m for i, m in enumerate(state.board.melds) if i != board_idx
                    ]
                    if remaining:
                        base_melds = other_melds + [Meld(tiles=remaining)]
                    else:
                        base_melds = other_melds
                    pool = [freed] + list(rack)
                    if len(pool) < 3:
                        continue
                    # Generar múltiples melds que usen la ficha freed.
                    candidates = generate_meld_candidates(pool, max_size=5)
                    # Opción: un solo meld que usa freed.
                    for meld in candidates:
                        if replace_count >= replace_max:
                            break
                        # Verificar que el meld incluya la ficha freed
                        if not any(t.uid == freed.uid for t in meld.tiles):
                            continue
                        # Verificar que el nuevo tablero sea válido (todos los melds deben ser válidos)
                        if not all(is_valid_meld(m.tiles) for m in base_melds + [meld]):
                            continue
                        new_board = base_melds + [meld]
                        used_from_rack = [t for t in meld.tiles if t.uid != freed.uid]
                        rack_score = self._evaluate_used_tiles(rack, used_from_rack, opening=False)
                        # Bonus por reorganizar: permite usar más fichas del rack.
                        bonus = len(used_from_rack) * 1.5 if used_from_rack else 0.0
                        # Bonus adicional si usa fichas del tablero (reorganización real)
                        board_bonus = 3.0 if freed.uid in {t.uid for m in state.board.melds for t in m.tiles} else 0.0
                        options.append(
                            ScoredMove(
                                move=Move(
                                    move_type=MoveType.REPLACE_BOARD,
                                    new_board=new_board,
                                    reason="reorganizar tablero",
                                ),
                                score=rack_score + 5.0 + bonus + pool_bonus + board_bonus,
                                used_tiles=meld.tiles,
                                debug="replace_board_1",
                            )
                        )
                        replace_count += 1
                    # Opción: múltiples melds (uno usa freed, otros solo del rack).
                    melds_with_freed = [m for m in candidates if any(t.uid == freed.uid for t in m.tiles)]
                    if melds_with_freed:
                        # Generar melds adicionales solo del rack (sin freed).
                        rack_only_candidates = generate_meld_candidates(list(rack), max_size=5)
                        top_freed = sorted(melds_with_freed, key=lambda m: m.points(), reverse=True)[:8]
                        top_rack = sorted(rack_only_candidates, key=lambda m: m.points(), reverse=True)[:10]
                        for freed_meld in top_freed:
                            if replace_count >= replace_max:
                                break
                            freed_ids = {t.uid for t in freed_meld.tiles}
                            for rack_meld in top_rack:
                                if replace_count >= replace_max:
                                    break
                                rack_ids = {t.uid for t in rack_meld.tiles}
                                if freed_ids & rack_ids:
                                    continue
                                new_board = base_melds + [freed_meld, rack_meld]
                                # Verificar que todos los melds del nuevo tablero sean válidos
                                if not all(is_valid_meld(m.tiles) for m in new_board):
                                    continue
                                used_from_rack = [
                                    t for t in freed_meld.tiles + rack_meld.tiles if t.uid != freed.uid
                                ]
                                rack_score = self._evaluate_used_tiles(rack, used_from_rack, opening=False)
                                bonus = len(used_from_rack) * 2.0 if used_from_rack else 0.0
                                board_bonus = 4.0 if freed.uid in {t.uid for m in state.board.melds for t in m.tiles} else 0.0
                                options.append(
                                    ScoredMove(
                                        move=Move(
                                            move_type=MoveType.REPLACE_BOARD,
                                            new_board=new_board,
                                            reason="reorganizar tablero (múltiples)",
                                        ),
                                        score=rack_score + 8.0 + bonus + pool_bonus + board_bonus,
                                        used_tiles=freed_meld.tiles + rack_meld.tiles,
                                        debug="replace_board_2",
                                    )
                                )
                                replace_count += 1
            # Caso 2: tomar múltiples fichas de diferentes melds (más complejo pero más poderoso).
            if len(state.board.melds) >= 2 and replace_count < replace_max:
                for idx1, meld1 in enumerate(state.board.melds):
                    if replace_count >= replace_max:
                        break
                    for tile1 in meld1.tiles:
                        if replace_count >= replace_max:
                            break
                        rem1 = [t for t in meld1.tiles if t.uid != tile1.uid]
                        if rem1 and not is_valid_meld(rem1):
                            continue
                        for idx2, meld2 in enumerate(state.board.melds):
                            if idx2 <= idx1 or replace_count >= replace_max:
                                continue
                            for tile2 in meld2.tiles:
                                if replace_count >= replace_max:
                                    break
                                if tile1.uid == tile2.uid:
                                    continue
                                rem2 = [t for t in meld2.tiles if t.uid != tile2.uid]
                                if rem2 and not is_valid_meld(rem2):
                                    continue
                                freed_tiles = [tile1, tile2]
                                other_melds = [
                                    m
                                    for i, m in enumerate(state.board.melds)
                                    if i != idx1 and i != idx2
                                ]
                                if rem1:
                                    other_melds.append(Meld(tiles=rem1))
                                if rem2:
                                    other_melds.append(Meld(tiles=rem2))
                                pool = freed_tiles + list(rack)
                                if len(pool) < 3:
                                    continue
                                candidates = generate_meld_candidates(pool, max_size=5)
                                freed_uids = {t.uid for t in freed_tiles}
                                for meld in candidates:
                                    if replace_count >= replace_max:
                                        break
                                    meld_uids = {t.uid for t in meld.tiles}
                                    if not freed_uids & meld_uids:
                                        continue
                                    new_board = other_melds + [meld]
                                    # Verificar que todos los melds del nuevo tablero sean válidos
                                    if not all(is_valid_meld(m.tiles) for m in new_board):
                                        continue
                                    used_from_rack = [
                                        t for t in meld.tiles if t.uid not in freed_uids
                                    ]
                                    rack_score = self._evaluate_used_tiles(rack, used_from_rack, opening=False)
                                    bonus = len(used_from_rack) * 2.5 if used_from_rack else 0.0
                                    board_bonus = 6.0 if any(t.uid in {t2.uid for m in state.board.melds for t2 in m.tiles} for t in freed_tiles) else 0.0
                                    options.append(
                                        ScoredMove(
                                            move=Move(
                                                move_type=MoveType.REPLACE_BOARD,
                                                new_board=new_board,
                                                reason="reorganizar tablero (multi-ficha)",
                                            ),
                                            score=rack_score + 10.0 + bonus + pool_bonus + board_bonus,
                                            used_tiles=meld.tiles,
                                            debug="replace_board_multi",
                                        )
                                    )
                                    replace_count += 1

        options.append(
            ScoredMove(
                move=Move(move_type=MoveType.PASS_TURN, reason="pasar"),
                score=-2.0,
                used_tiles=[],
                debug="pass",
            )
        )
        options = sorted(options, key=lambda o: o.score, reverse=True)
        # Aumentar límite si hay reorganizaciones para no cortarlas demasiado pronto.
        has_replace = any(o.move.move_type == MoveType.REPLACE_BOARD for o in options)
        if has_replace:
            max_regular = max(max_regular, 80)
        options = options[:max_regular]
        return self._filter_legal(state, player_idx, options)

    def _filter_legal(
        self, state: GameState, player_idx: int, options: list[ScoredMove]
    ) -> list[ScoredMove]:
        legal: list[ScoredMove] = []
        for option in options:
            ok, _ = validate_move(state, player_idx, option.move)
            if ok:
                legal.append(option)
        if not legal:
            return [
                ScoredMove(
                    move=Move(move_type=MoveType.PASS_TURN, reason="fallback legal"),
                    score=-999.0,
                    used_tiles=[],
                    debug="forced pass",
                )
            ]
        return sorted(legal, key=lambda o: o.score, reverse=True)

    def _score_with_search(
        self, state: GameState, root_idx: int, options: list[ScoredMove]
    ) -> list[ScoredMove]:
        self._search_cache.clear()
        skill = self.config.skill()
        # Nivel 3 usa búsqueda mínima; niveles altos escalan depth/beam/candidatos.
        depth = min(self.config.search_depth_cap, int(skill * 4))  # 0 en nivel 3, 1-3 en 4-10
        if depth < 1 and self.config.level >= 4:
            depth = 1
        beam = min(self.config.search_beam_cap, 2 + int(skill * 12))
        candidate_count = min(len(options), 2 + int(skill * 10))

        deadline = time.perf_counter() + max(0.01, self.config.search_time_ms / 1000.0)
        rescored: list[ScoredMove] = []
        for option in options[:candidate_count]:
            if time.perf_counter() >= deadline:
                break
            simulated = clone_state(state)
            ok, _ = apply_move_inplace(
                simulated, simulated.current_player_idx, option.move, draw_on_pass=True
            )
            if not ok:
                continue
            simulated.current_player_idx = (simulated.current_player_idx + 1) % len(
                simulated.players
            )
            future = self._minimax_value(
                simulated,
                root_idx=root_idx,
                depth=max(0, depth - 1),
                beam=beam,
                deadline=deadline,
            )
            combined = option.score + 0.65 * future
            rescored.append(
                ScoredMove(
                    move=option.move,
                    score=combined,
                    used_tiles=option.used_tiles,
                    debug=f"{option.debug}; search={future:.2f}",
                )
            )

        if not rescored:
            return options

        untouched = options[candidate_count:]
        return sorted(rescored + untouched, key=lambda o: o.score, reverse=True)

    def _minimax_value(
        self,
        state: GameState,
        root_idx: int,
        depth: int,
        beam: int,
        deadline: float,
    ) -> float:
        if time.perf_counter() >= deadline:
            return self._evaluate_state(state, root_idx)
        if depth <= 0:
            return self._evaluate_state(state, root_idx)

        key = (self._state_signature(state), state.current_player_idx, depth)
        cached = self._search_cache.get(key)
        if cached is not None:
            return cached

        current_idx = state.current_player_idx
        current_options = self._generate_options(state, current_idx)[:beam]
        if not current_options:
            current_options = [
                ScoredMove(
                    move=Move(move_type=MoveType.PASS_TURN, reason="no options"),
                    score=-10.0,
                    used_tiles=[],
                    debug="auto pass",
                )
            ]

        if current_idx == root_idx:
            best = -1e18
            for option in current_options:
                if time.perf_counter() >= deadline:
                    break
                nxt = clone_state(state)
                ok, _ = apply_move_inplace(
                    nxt, nxt.current_player_idx, option.move, draw_on_pass=True
                )
                if not ok:
                    continue
                nxt.current_player_idx = (nxt.current_player_idx + 1) % len(nxt.players)
                score = self._minimax_value(
                    nxt,
                    root_idx=root_idx,
                    depth=depth - 1,
                    beam=beam,
                    deadline=deadline,
                )
                if score > best:
                    best = score
            if best == -1e18:
                best = self._evaluate_state(state, root_idx)
            self._search_cache[key] = best
            return best

        worst = 1e18
        for option in current_options:
            if time.perf_counter() >= deadline:
                break
            nxt = clone_state(state)
            ok, _ = apply_move_inplace(
                nxt, nxt.current_player_idx, option.move, draw_on_pass=True
            )
            if not ok:
                continue
            nxt.current_player_idx = (nxt.current_player_idx + 1) % len(nxt.players)
            score = self._minimax_value(
                nxt,
                root_idx=root_idx,
                depth=depth - 1,
                beam=beam,
                deadline=deadline,
            )
            if score < worst:
                worst = score
        if worst == 1e18:
            worst = self._evaluate_state(state, root_idx)
        self._search_cache[key] = worst
        return worst

    def _state_signature(self, state: GameState) -> str:
        racks = []
        for player in state.players:
            rack_ids = ",".join(str(uid) for uid in sorted(t.uid for t in player.rack))
            racks.append(f"{int(player.opened)}:{rack_ids}")
        melds = []
        for meld in state.board.melds:
            meld_ids = ",".join(str(uid) for uid in sorted(t.uid for t in meld.tiles))
            melds.append(meld_ids)
        return "|".join(
            [
                ";".join(racks),
                ";".join(melds),
                str(len(state.pool)),
            ]
        )

    def _evaluate_state(self, state: GameState, root_idx: int) -> float:
        root = state.players[root_idx]
        if not root.rack:
            return 1e6

        own_points = sum(t.points() for t in root.rack)
        own_count = len(root.rack)
        opp_points = 0.0
        opp_count = 0.0
        for i, player in enumerate(state.players):
            if i == root_idx:
                continue
            opp_points += sum(t.points() for t in player.rack)
            opp_count += len(player.rack)
        opp_n = max(1.0, float(len(state.players) - 1))
        avg_opp_points = opp_points / opp_n
        avg_opp_count = opp_count / opp_n

        opened_bonus = 6.0 if root.opened else -4.0
        board_density = len(state.board.melds) * 0.25
        return (
            -own_points * 1.25
            -own_count * 4.2
            +avg_opp_points * 0.42
            +avg_opp_count * 0.75
            +opened_bonus
            +board_density
        )

    def _evaluate_used_tiles(self, rack: list[Tile], used: list[Tile], opening: bool) -> float:
        joker_used = sum(1 for t in used if t.is_joker)
        played_points = sum(t.points() for t in used)
        used_count = len(used)
        remaining = rack_without_tiles(rack, used)
        remaining_points = sum(t.points() for t in remaining)

        score = played_points * 1.15 + used_count * 6.5 - remaining_points * 0.12
        score -= joker_used * (0.0 if opening else 1.5)
        if not remaining:
            score += 1000.0
        # Bonus por usar más fichas: ayuda a vaciar la mano más rápido.
        if used_count >= 5:
            score += 3.0
        if used_count >= 7:
            score += 5.0
        return score

    def _select_option(self, options: list[ScoredMove]) -> ScoredMove:
        if len(options) == 1:
            return options[0]

        skill = self.config.skill()
        randomness = min(1.0, max(0.0, self.config.randomness))
        effective_noise = min(1.0, randomness + (1.0 - skill) * 0.65)
        # Niveles bajos blandean más; niveles altos casi siempre eligen entre las mejores.
        blunder_base = 0.08 if skill >= 0.5 else (0.25 - skill * 0.4)
        blunder_prob = min(0.92, blunder_base + (1.0 - skill) * 0.55 + randomness * 0.15)

        sorted_opts = sorted(options, key=lambda o: o.score, reverse=True)
        if self.rng.random() < blunder_prob and len(sorted_opts) > 2:
            lower_half = sorted_opts[len(sorted_opts) // 2 :]
            return self.rng.choice(lower_half)

        temp = 0.08 + effective_noise * 1.2
        best = sorted_opts[0].score
        weights: list[float] = []
        for item in sorted_opts:
            scaled = (item.score - best) / max(temp, 1e-6)
            weights.append(math.exp(scaled))

        total = sum(weights)
        pick = self.rng.random() * total
        acc = 0.0
        for item, weight in zip(sorted_opts, weights):
            acc += weight
            if pick <= acc:
                return item
        return sorted_opts[-1]
