"""
Reglas de Rummikub clásico: validación de melds y generación de candidatos.

Un meld es válido si es grupo (mismo valor, colores distintos, 3-4 fichas) o
escalera (mismo color, valores consecutivos, 3+ fichas). Los comodines pueden
sustituir cualquier ficha. Proporciona generación de melds desde un rack,
combinaciones de apertura (≥30 puntos) y extensión de melds existentes.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

from .core import Color, Meld, Tile


def is_valid_meld(tiles: list[Tile]) -> bool:
    """Indica si la lista de fichas forma un meld válido (grupo o escalera)."""
    return is_valid_set(tiles) or is_valid_run(tiles)


def is_valid_set(tiles: list[Tile]) -> bool:
    """
    Comprueba si las fichas forman un grupo válido: mismo valor numérico,
    colores distintos entre las naturales, 3 o 4 fichas (comodines permitidos).
    """
    n = len(tiles)
    if n < 3 or n > 4:
        return False

    jokers = [t for t in tiles if t.is_joker]
    naturals = [t for t in tiles if not t.is_joker]
    if not naturals:
        return False

    # Grupo: un solo valor entre las naturales
    values = {t.value for t in naturals}
    if len(values) != 1:
        return False

    # Colores distintos (sin repetir color en naturales)
    colors = [t.color for t in naturals]
    if len(set(colors)) != len(colors):
        return False

    return len(naturals) + len(jokers) == n


def is_valid_run(tiles: list[Tile]) -> bool:
    """
    Comprueba si las fichas forman una escalera válida: mismo color en naturales,
    valores consecutivos (los huecos pueden ser comodines), mínimo 3 fichas.
    Recorre los posibles intervalos [start, start+n) en 1..13 y comprueba si
    los valores naturales caben y los huecos se cubren con comodines.
    """
    n = len(tiles)
    if n < 3:
        return False

    jokers = [t for t in tiles if t.is_joker]
    naturals = [t for t in tiles if not t.is_joker]
    if not naturals:
        return False

    # Una sola color en naturales
    colors = {t.color for t in naturals}
    if len(colors) != 1 or None in colors:
        return False

    values = [t.value for t in naturals if t.value is not None]
    if len(values) != len(set(values)):
        return False

    # Rango de inicios posibles para una ventana de longitud n
    min_start = max(1, max(values) - n + 1)
    max_start = min(min(values), 13 - n + 1)
    joker_count = len(jokers)
    value_set = set(values)

    for start in range(min_start, max_start + 1):
        target = set(range(start, start + n))
        if value_set.issubset(target):
            missing = len(target - value_set)
            if missing <= joker_count:
                return True
    return False


def generate_meld_candidates(rack: list[Tile], max_size: int = 5) -> list[Meld]:
    """
    Genera todos los melds válidos que se pueden formar con subconjuntos del rack
    (tamaño 3 hasta max_size). Evita duplicados por uid de fichas.
    """
    seen: set[tuple[int, ...]] = set()
    melds: list[Meld] = []
    upper = min(max_size, len(rack))
    for size in range(3, upper + 1):
        for combo in combinations(rack, size):
            tiles = list(combo)
            if not is_valid_meld(tiles):
                continue
            key = tuple(sorted(t.uid for t in tiles))
            if key in seen:
                continue
            seen.add(key)
            melds.append(Meld(tiles=tiles))
    return melds


def find_opening_combos(
    rack: list[Tile], min_points: int = 30, limit: int = 50
) -> list[list[Meld]]:
    """
    Encuentra combinaciones de melds disjuntos que sumen al menos min_points
    (apertura clásica 30). Backtracking: se eligen melds sin compartir fichas
    hasta alcanzar el mínimo; se limita el número de resultados.
    """
    candidates = generate_meld_candidates(rack, max_size=5)
    results: list[list[Meld]] = []

    def backtrack(
        start: int, used: set[int], chosen: list[Meld], points: int
    ) -> None:
        if len(results) >= limit:
            return
        if points >= min_points and chosen:
            results.append(list(chosen))
        for idx in range(start, len(candidates)):
            meld = candidates[idx]
            ids = {t.uid for t in meld.tiles}
            if ids & used:
                continue
            chosen.append(meld)
            backtrack(idx + 1, used | ids, chosen, points + meld.points())
            chosen.pop()

    backtrack(0, set(), [], 0)
    return results


def extend_meld_with_tile(meld: Meld, tile: Tile) -> Meld | None:
    """
    Si se puede extender el meld con la ficha (añadir al grupo o a un extremo
    de la escalera), devuelve el nuevo Meld; si no, None. Grupos máx 4 fichas.
    """
    if is_valid_set(meld.tiles):
        if len(meld.tiles) >= 4:
            return None
        extended = list(meld.tiles) + [tile]
        if is_valid_set(extended):
            return Meld(tiles=extended)
        return None

    if not is_valid_run(meld.tiles):
        return None

    # Escalera: probar añadir al inicio o al final
    prepend = [tile] + list(meld.tiles)
    if is_valid_run(prepend):
        return Meld(tiles=prepend)
    append = list(meld.tiles) + [tile]
    if is_valid_run(append):
        return Meld(tiles=append)
    return None


def rack_without_tiles(rack: list[Tile], used_tiles: Iterable[Tile]) -> list[Tile]:
    """Devuelve el rack quitando las fichas indicadas (por uid)."""
    used_ids = {t.uid for t in used_tiles}
    return [tile for tile in rack if tile.uid not in used_ids]


def tile_contribution(tile: Tile) -> int:
    """Puntos que aporta la ficha (para heurísticas)."""
    return tile.points()


def color_value_signature(tiles: list[Tile]) -> tuple[Color | None, tuple[int | None, ...]]:
    """Extrae color (de la primera natural) y tupla de valores para comparar melds."""
    color = None
    vals: list[int | None] = []
    for tile in tiles:
        if tile.color is not None:
            color = tile.color
        vals.append(tile.value)
    return color, tuple(vals)
