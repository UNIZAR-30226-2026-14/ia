"""
Modelo de datos del juego Rummikub clásico (modo normal) y de sus ampliaciones
para el modo arcade.

Define fichas (Tile), colores, melds, tablero (Board), estado de jugador
(PlayerState), estado global (GameState), tipos de jugada (MoveType, Move) y el
mazo estándar. Incluye serialización corta de fichas (Palo+Número: "B02",
"K12", "J*") para integración con backends.

El modo arcade añade, de forma opcional y retrocompatible, tres habilidades
especiales sobre fichas normales (todas se representan como sufijos al string
corto Palo+Número):

- Arcoíris (sufijo 'A'): la ficha actúa como comodín de color manteniendo su
  valor numérico. Su color base es solo cosmético.
- Dorada (sufijo 'D'): los puntos de la ficha se duplican al puntuar.
- Negativa (sufijo 'N'): los puntos se toman con signo opuesto.

Además se añaden:
- ItemType / ItemUse: catálogo de objetos del modo arcade y descriptor de "uso
  de objeto" que el bot puede sugerir junto a la jugada.
- ArcadeState: efectos activos en la ronda (color bloqueado, techo de cristal,
  inventario de objetos del bot, etc.).

El motor real de eventos y objetos lo gestiona el backend; el bot solo
**respeta restricciones** y **sugiere** usos de objetos a partir del estado
arcade que recibe en la petición.
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


# Colores disponibles para formar grupos (4 slots de color). En Rummikub
# clásico son los 4 palos; el modo arcade no añade nuevos colores: las
# habilidades especiales (dorada, negativa, arcoíris) son modificadores sobre
# fichas ya coloreadas.
NATURAL_COLORS: tuple[Color, ...] = (Color.BLACK, Color.BLUE, Color.ORANGE, Color.RED)


@dataclass(frozen=True)
class Tile:
    """
    Una ficha del juego: valor 1-13, color, o comodín.
    uid identifica la ficha de forma única (para validar que pertenece al rack).

    Habilidades especiales arcade (opcionales, sin efecto en modo normal):
    - gold: ficha dorada, los puntos se duplican al puntuar.
    - negative: ficha negativa, los puntos se toman con signo opuesto.
    - rainbow: ficha arcoíris, su color base es solo cosmético; en melds
      actúa como comodín de color (valor fijo) y, a efectos de restricciones
      por color bloqueado, no se considera ligada a su color base.
    Si varias habilidades están activas, se combinan: primero se niega
    (negative), luego se duplica (gold). La de rainbow no afecta a puntos.
    """
    value: Optional[int]
    color: Optional[Color]
    is_joker: bool = False
    uid: int = -1
    gold: bool = False
    negative: bool = False
    rainbow: bool = False

    def points(self) -> int:
        """
        Puntos de la ficha:
        - Comodín: 30 (reglas clásicas).
        - Numérica normal: valor.
        - Numérica con modificadores arcade: valor con signo (negative) y/o
          duplicado (gold). Rainbow no altera los puntos.
        """
        if self.is_joker:
            return 30
        if self.value is None:
            return 0
        base = self.value
        if self.negative:
            base = -base
        if self.gold:
            base = base * 2
        return base

    def short(self) -> str:
        """
        Representación corta para JSON/logs.
        - Comodín: 'J*'.
        - Numérica: Palo+Número ('B02', 'K12').
        - Con habilidades arcade se añaden sufijos: 'A' (arcoíris),
          'D' (dorada), 'N' (negativa). Orden fijo al serializar: A, D, N
          (ej. 'B07AD', 'R10N', 'O03D'). Al parsear se acepta cualquier orden.
        """
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
        s = f"{color_map[self.color]}{self.value:02d}"
        if self.rainbow:
            s += "A"
        if self.gold:
            s += "D"
        if self.negative:
            s += "N"
        return s


def tile_from_short(s: str, uid: int = -1) -> "Tile":
    """
    Parsea una ficha desde el formato string Palo+Número (ej. "B02", "K12",
    "J*", "B07A", "O03D", "R10N", "B05AD").
    Usado por backends (Spring Boot) que envían estado en JSON.

    Palos admitidos: K (negro), B (azul), O (naranja), R (rojo).
    Valor 01-13. Habilidades especiales opcionales (modo arcade) como sufijos
    en cualquier orden: 'A' (arcoíris), 'D' (dorada), 'N' (negativa).
    Comodín: 'J*' o 'J' (no sigue la regla Palo+Número).

    Lanza ValueError si el string no es válido.
    """
    s = s.strip().upper()
    if s in ("J*", "J"):
        return Tile(value=None, color=None, is_joker=True, uid=uid)
    if len(s) >= 3 and s[0] in "KBOR" and s[1:3].isdigit():
        c = s[0]
        val = int(s[1:3])
        suffix = s[3:]
        # Solo se aceptan letras 'A', 'D', 'N' como habilidades; cada una a lo sumo una vez.
        if any(ch not in "ADN" for ch in suffix):
            raise ValueError(f"Tile string no válido (habilidad): {s!r}")
        if len(set(suffix)) != len(suffix):
            raise ValueError(f"Tile string no válido (habilidad repetida): {s!r}")
        rainbow = "A" in suffix
        gold = "D" in suffix
        negative = "N" in suffix
        if 1 <= val <= 13:
            color_map = {
                "K": Color.BLACK,
                "B": Color.BLUE,
                "O": Color.ORANGE,
                "R": Color.RED,
            }
            return Tile(
                value=val,
                color=color_map[c],
                is_joker=False,
                uid=uid,
                gold=gold,
                negative=negative,
                rainbow=rainbow,
            )
    raise ValueError(f"Tile string no válido: {s!r}")


@dataclass
class Meld:
    """
    Conjunto válido de fichas: grupo (mismo valor, colores distintos) o escalera
    (mismo color, valores consecutivos). 3-4 fichas; puede incluir comodines.
    En modo arcade admite fichas con habilidad arcoíris, que actúan como color
    flexible en grupos y como color dominante en escaleras.
    """
    tiles: list[Tile]

    def points(self) -> int:
        """Suma de puntos de las fichas del meld (modificadores arcade incluidos)."""
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


# --- Modo arcade: catálogo de objetos y descriptores --------------------------


class ItemType(str, Enum):
    """
    Catálogo de objetos del modo arcade. El bot los recibe en su inventario y
    puede sugerir uno junto a la jugada; el backend es quien aplica el efecto.
    """
    GUARDIAN_ANGEL = "GUARDIAN_ANGEL"           # Ángel de la guarda (pasivo)
    CRYSTAL_BALL = "CRYSTAL_BALL"               # Bola de cristal
    TRUTH_MAGNIFIER = "TRUTH_MAGNIFIER"         # Lupa de la verdad
    MIDAS_TOUCH = "MIDAS_TOUCH"                 # Toque de Midas
    MINUS_POWER = "MINUS_POWER"                 # Poder del -
    RAINBOW_REFRACTION = "RAINBOW_REFRACTION"   # Refracción multicolor
    PLUS_FOUR = "PLUS_FOUR"                     # +4
    SWAP_ON_FAIL = "SWAP_ON_FAIL"               # Trueque al fallo
    WHITE_GLOVE = "WHITE_GLOVE"                 # Guante blanco
    SMOKE_BOMB = "SMOKE_BOMB"                   # Bomba de humo
    CHILI_PEPPER = "CHILI_PEPPER"               # Guindilla en el culo
    RUM_ROCKS = "RUM_ROCKS"                     # Ron con hielo / Dos copas de más
    GLASS_CEILING = "GLASS_CEILING"             # Techo de cristal


@dataclass
class ItemUse:
    """
    Sugerencia del bot para usar un objeto. El backend es quien ejecuta el
    efecto real y, si procede, vuelve a pedir jugada al bot con el estado ya
    modificado.

    Campos:
    - item: objeto a usar (de ItemType).
    - target_player_idx: índice del jugador objetivo (None si el objeto es
      autoaplicado o no requiere objetivo).
    - reason: texto informativo para logs/UI.
    - params: parámetros adicionales que pide el objeto (p. ej. color o
      rango numérico para Bola de cristal). Opcional y abierto.
    """
    item: ItemType
    target_player_idx: Optional[int] = None
    reason: str = ""
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ShopOffer:
    """
    Una oferta concreta del stock de tienda al empezar el turno del bot.
    El backend compone el surtido (2–3 ofertas) y lo envía al bot para que
    elija comprar una o ninguna. El bot no almacena catálogos ni precios: se
    limita a elegir dentro de lo que el backend le muestre.
    """
    item: ItemType
    price: int


@dataclass
class ShopChoice:
    """
    Decisión de compra del bot ante una oferta de tienda.
    - buy: objeto elegido (uno de los ofrecidos) o None si decide no comprar.
    - reason: motivo legible para logs/UI.
    """
    buy: Optional[ItemType] = None
    reason: str = ""


@dataclass
class ArcadeState:
    """
    Estado arcade que acompaña al GameState cuando el backend está jugando en
    modo arcade. Todos los campos son opcionales y, si no se pasan, el bot se
    comporta en modo normal.

    Campos:
    - enabled: indicador explícito de modo arcade activo.
    - blocked_color: color que NO se puede jugar este turno (evento de ronda).
    - min_play_points: puntos mínimos que debe sumar la próxima jugada del bot
      (techo de cristal; se aplica aparte del mínimo de apertura).
    - my_items: inventario de objetos del bot (máximo 3 por diseño).
    - opponent_item_counts: número de objetos que tiene cada rival (por índice).
    - time_limit_s: tiempo máximo del turno en segundos (informativo; el bot lo
      usa para acotar su búsqueda).
    - shop_discount: factor de descuento de la tienda (informativo, 0.5 = 50%).
    - draw_at_turn_start: si el evento "cada jugador roba una ficha al empezar
      su turno" está activo (informativo; el backend ya lo aplica).
    - shop_offer: oferta actual de la tienda para este turno (lista de ShopOffer,
      0–N entradas). Lista vacía ⇒ la tienda no está abierta este turno. Si hay
      ofertas, el bot emite su decisión en Move.shop_choice.
    - shop_balance: saldo disponible del bot en la moneda de la tienda. Solo se
      usa junto a shop_offer para filtrar ofertas asequibles.
    - items_used_this_turn: objetos ya consumidos o denegados durante el turno
      actual del bot. El backend los añade tras ejecutar (o rechazar) un
      USE_ITEM y los reinicia al empezar cada turno. El bot NUNCA vuelve a
      sugerir un objeto que aparezca aquí, aunque siga figurando en my_items.
      Garantiza la terminación del bucle de fases del turno arcade.
    - guardian_angel_active: protección pasiva de un Ángel ya "convertido".
      Es un escudo único (no acumulable). True ⇒ el próximo objeto ofensivo
      que afecte al portador se bloqueará automáticamente y el escudo se
      gastará (backend pone el flag a False). El Ángel recién adquirido
      entra en my_items y el backend lo convierte a escudo al inicio del
      siguiente turno del portador (si ya había escudo activo, el Ángel
      sigue en my_items hasta que el escudo anterior se gaste). El bot
      usa este flag para no comprar ni aceptar más Ángeles redundantes.
    """
    enabled: bool = False
    blocked_color: Optional[Color] = None
    min_play_points: Optional[int] = None
    my_items: list[ItemType] = field(default_factory=list)
    opponent_item_counts: list[int] = field(default_factory=list)
    time_limit_s: Optional[int] = None
    shop_discount: Optional[float] = None
    draw_at_turn_start: bool = False
    shop_offer: list["ShopOffer"] = field(default_factory=list)
    shop_balance: int = 0
    items_used_this_turn: list[ItemType] = field(default_factory=list)
    guardian_angel_active: bool = False


@dataclass
class GameState:
    """
    Estado completo de la partida: tablero, jugadores, bolsa, turno actual.
    opponent_rack_counts: en modo fairplay, racks ajenos están vacíos y aquí
    se guarda el número de fichas por jugador (índice i = jugador i).
    None = modo simulación (se ven todas las fichas).

    arcade: (opcional) efectos/inventario del modo arcade. None en modo normal.
    """
    board: Board
    players: list[PlayerState]
    pool: list[Tile]
    current_player_idx: int = 0
    turn_number: int = 1
    opponent_rack_counts: list[int] | None = None
    arcade: Optional[ArcadeState] = None

    def current_player(self) -> PlayerState:
        """Devuelve el jugador que tiene el turno."""
        return self.players[self.current_player_idx]


class MoveType(str, Enum):
    """
    Tipos de jugada.

    Tipos "clásicos" (cierran el turno):
    - PASS_TURN: el bot roba ficha y pasa.
    - PLAY_MELDS: juega nuevos melds desde la mano.
    - EXTEND_MELD: extiende un meld del tablero con una ficha de la mano.
    - REPLACE_BOARD: reorganiza el tablero (resultado final completo).

    Tipo "arcade" (NO cierra el turno):
    - USE_ITEM: el bot pide al backend usar un objeto y que le devuelva el
      control en una nueva llamada a /api/bot/move con el estado actualizado
      y ese objeto marcado en arcade.items_used_this_turn. En ese caso
      Move.item_use es obligatorio y Move no contiene new_melds/extension.
    """
    PASS_TURN = "pass"
    PLAY_MELDS = "play_melds"
    EXTEND_MELD = "extend_meld"
    REPLACE_BOARD = "replace_board"
    USE_ITEM = "use_item"


@dataclass
class Move:
    """
    Una jugada: tipo más los datos según el tipo.
    REPLACE_BOARD usa new_board como tablero completo resultante.

    item_use: (obligatorio si move_type == USE_ITEM; opcional en otros casos)
    en modo arcade, sugerencia de uso de objeto. Con USE_ITEM es lo único
    relevante del Move: el backend ejecuta el efecto y vuelve a llamar al bot
    con arcade.items_used_this_turn actualizado para que decida la siguiente
    fase del turno (otro objeto o la jugada final). Con cualquier otro
    move_type, item_use es siempre None (ese tipo de Move cierra el turno).

    shop_choice: (opcional, modo arcade) decisión del bot ante la oferta de
    tienda de este turno. Solo se emite si el request incluyó arcade.shop_offer.
    buy == None ⇒ el bot pasa de comprar. El backend ejecuta la compra (cobra
    saldo, añade el objeto al inventario) y la jugada devuelta en el mismo
    Move asume el estado PREVIO a esa compra: el objeto comprado no podrá
    usarse hasta el siguiente turno.
    """
    move_type: MoveType
    new_melds: list[Meld] = field(default_factory=list)
    new_board: list[Meld] = field(default_factory=list)
    extend_index: Optional[int] = None
    extension_tiles: list[Tile] = field(default_factory=list)
    reason: str = ""
    item_use: Optional[ItemUse] = None
    shop_choice: Optional["ShopChoice"] = None

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
        if self.move_type == MoveType.USE_ITEM and self.item_use is not None:
            tgt = (
                f" → jugador {self.item_use.target_player_idx}"
                if self.item_use.target_player_idx is not None
                else ""
            )
            return f"usar {self.item_use.item.value}{tgt}"
        return self.move_type.value


def build_classic_deck() -> list[Tile]:
    """
    Construye el mazo clásico: 2× (13 valores × 4 colores) + 2 comodines.
    Cada ficha tiene un uid único para identificación en validación.

    En modo arcade las fichas especiales (dorada, negativa, arcoíris) no
    aparecen aquí: el backend las introduce mediante objetos durante la partida.
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
