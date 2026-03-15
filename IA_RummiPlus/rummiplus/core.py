"""
Modelo de datos del juego Rummikub clásico.

Define fichas (Tile), colores, melds, tablero (Board), estado de jugador (PlayerState),
estado global (GameState), tipos de jugada (MoveType, Move) y el mazo estándar.
Incluye serialización corta de fichas (Palo+Número: "B02", "K12", "J*") para integración con backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Color(str, Enum):
    """Colores de ficha en Rummikub: negro (K), azul (B), naranja (O), rojo (R)."""
    BLACK = "black"
    BLUE = "blue"
    ORANGE = "orange"
    RED = "red"


@dataclass(frozen=True)
class Tile:
    """
    Una ficha del juego: valor 1-13, color, o comodín.
    uid identifica la ficha de forma única (para validar que pertenece al rack).
    """
    value: Optional[int]
    color: Optional[Color]
    is_joker: bool = False
    uid: int = -1

    def points(self) -> int:
        """Puntos de la ficha: valor numérico, o 30 si es comodín (reglas clásicas)."""
        if self.is_joker:
            return 30
        if self.value is None:
            return 0
        return self.value

    def short(self) -> str:
        """Representación corta para JSON/logs: Palo+Número ('B02', 'K12', 'J*')."""
        if self.is_joker:
            return "J*"
        if self.value is None or self.color is None:
            return "??"
        color_map = {
            Color.BLACK: "K",
            Color.BLUE: "B",
            Color.ORANGE: "O",
            Color.RED: "R",
        }
        return f"{color_map[self.color]}{self.value:02d}"


def tile_from_short(s: str, uid: int = -1) -> "Tile":
    """
    Parsea una ficha desde el formato string Palo+Número (ej. "B02", "K12", "J*").
    Usado por backends (Spring Boot) que envían estado en JSON.
    Lanza ValueError si el string no es válido.
    """
    s = s.strip().upper()
    if s in ("J*", "J"):
        return Tile(value=None, color=None, is_joker=True, uid=uid)
    if len(s) >= 3 and s[0] in "KBOR" and s[1:3].isdigit():
        c = s[0]
        val = int(s[1:3])
        if 1 <= val <= 13:
            color_map = {"K": Color.BLACK, "B": Color.BLUE, "O": Color.ORANGE, "R": Color.RED}
            return Tile(value=val, color=color_map[c], is_joker=False, uid=uid)
    raise ValueError(f"Tile string no válido: {s!r}")


@dataclass
class Meld:
    """
    Conjunto válido de fichas: grupo (mismo valor, colores distintos) o escalera
    (mismo color, valores consecutivos). 3-4 fichas; puede incluir comodines.
    """
    tiles: list[Tile]

    def points(self) -> int:
        """Suma de puntos de las fichas del meld."""
        return sum(tile.points() for tile in self.tiles)

    def short(self) -> str:
        """Representación corta: '[B02 B03 B04]'."""
        return "[" + " ".join(tile.short() for tile in self.tiles) + "]"


@dataclass
class Board:
    """Tablero: lista ordenada de melds colocados."""
    melds: list[Meld] = field(default_factory=list)

    def clone(self) -> "Board":
        """Copia profunda del tablero (nuevos melds y listas de tiles)."""
        return Board(melds=[Meld(tiles=list(m.tiles)) for m in self.melds])

    def short(self) -> str:
        """Representación legible para logs."""
        if not self.melds:
            return "(vacío)"
        return " | ".join(f"{idx}:{meld.short()}" for idx, meld in enumerate(self.melds))


@dataclass
class PlayerState:
    """Estado de un jugador: id, fichas en mano (rack) y si ya abrió (≥30 pts)."""
    player_id: str
    rack: list[Tile]
    opened: bool = False

    def rack_points(self) -> int:
        """Suma de puntos de las fichas en la mano."""
        return sum(tile.points() for tile in self.rack)


@dataclass
class GameState:
    """
    Estado completo de la partida: tablero, jugadores, bolsa, turno actual.
    opponent_rack_counts: en modo fairplay, racks ajenos están vacíos y aquí
    se guarda el número de fichas por jugador (índice i = jugador i).
    None = modo simulación (se ven todas las fichas).
    """
    board: Board
    players: list[PlayerState]
    pool: list[Tile]
    current_player_idx: int = 0
    turn_number: int = 1
    opponent_rack_counts: list[int] | None = None

    def current_player(self) -> PlayerState:
        """Devuelve el jugador que tiene el turno."""
        return self.players[self.current_player_idx]


class MoveType(str, Enum):
    """Tipos de jugada: pasar, jugar melds nuevos, extender un meld, reorganizar tablero."""
    PASS_TURN = "pass"
    PLAY_MELDS = "play_melds"
    EXTEND_MELD = "extend_meld"
    REPLACE_BOARD = "replace_board"


@dataclass
class Move:
    """
    Una jugada: tipo más los datos según el tipo.
    REPLACE_BOARD usa new_board como tablero completo resultante.
    """
    move_type: MoveType
    new_melds: list[Meld] = field(default_factory=list)
    new_board: list[Meld] = field(default_factory=list)
    extend_index: Optional[int] = None
    extension_tiles: list[Tile] = field(default_factory=list)
    reason: str = ""

    def short(self) -> str:
        """Descripción legible de la jugada para logs y API."""
        if self.move_type == MoveType.PASS_TURN:
            return "PASAR"
        if self.move_type == MoveType.PLAY_MELDS:
            return " + ".join(m.short() for m in self.new_melds)
        if self.move_type == MoveType.EXTEND_MELD:
            tiles = " ".join(tile.short() for tile in self.extension_tiles)
            return f"extender meld #{self.extend_index} con {tiles}"
        if self.move_type == MoveType.REPLACE_BOARD:
            return "reorganizar: " + " | ".join(m.short() for m in self.new_board)
        return self.move_type.value


def build_classic_deck() -> list[Tile]:
    """
    Construye el mazo clásico: 2× (13 valores × 4 colores) + 2 comodines.
    Cada ficha tiene un uid único para identificación en validación.
    """
    deck: list[Tile] = []
    uid = 1
    colors = [Color.BLACK, Color.BLUE, Color.ORANGE, Color.RED]
    for _ in range(2):
        for color in colors:
            for value in range(1, 14):
                deck.append(Tile(value=value, color=color, is_joker=False, uid=uid))
                uid += 1
    for _ in range(2):
        deck.append(Tile(value=None, color=None, is_joker=True, uid=uid))
        uid += 1
    return deck
