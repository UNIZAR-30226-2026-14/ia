from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Color(str, Enum):
    BLACK = "black"
    BLUE = "blue"
    ORANGE = "orange"
    RED = "red"


@dataclass(frozen=True)
class Tile:
    value: Optional[int]
    color: Optional[Color]
    is_joker: bool = False
    uid: int = -1

    def points(self) -> int:
        if self.is_joker:
            return 30
        if self.value is None:
            return 0
        return self.value

    def short(self) -> str:
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
        return f"{self.value:02d}{color_map[self.color]}"


@dataclass
class Meld:
    tiles: list[Tile]

    def points(self) -> int:
        return sum(tile.points() for tile in self.tiles)

    def short(self) -> str:
        return "[" + " ".join(tile.short() for tile in self.tiles) + "]"


@dataclass
class Board:
    melds: list[Meld] = field(default_factory=list)

    def clone(self) -> "Board":
        return Board(melds=[Meld(tiles=list(m.tiles)) for m in self.melds])

    def short(self) -> str:
        if not self.melds:
            return "(vacío)"
        return " | ".join(f"{idx}:{meld.short()}" for idx, meld in enumerate(self.melds))


@dataclass
class PlayerState:
    player_id: str
    rack: list[Tile]
    opened: bool = False

    def rack_points(self) -> int:
        return sum(tile.points() for tile in self.rack)


@dataclass
class GameState:
    board: Board
    players: list[PlayerState]
    pool: list[Tile]
    current_player_idx: int = 0
    turn_number: int = 1

    def current_player(self) -> PlayerState:
        return self.players[self.current_player_idx]


class MoveType(str, Enum):
    PASS_TURN = "pass"
    PLAY_MELDS = "play_melds"
    EXTEND_MELD = "extend_meld"
    REPLACE_BOARD = "replace_board"


@dataclass
class Move:
    move_type: MoveType
    new_melds: list[Meld] = field(default_factory=list)
    new_board: list[Meld] = field(default_factory=list)  # para REPLACE_BOARD: tablero completo resultante
    extend_index: Optional[int] = None
    extension_tiles: list[Tile] = field(default_factory=list)
    reason: str = ""

    def short(self) -> str:
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
