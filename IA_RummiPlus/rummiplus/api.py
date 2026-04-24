"""
API pública del paquete Rummiplus: creación de bots, vista fairplay, serialización
y construcción de estado desde JSON para backends externos (Spring Boot).

Flujo para el backend (partida con jugadores reales y bots):
  - El backend gestiona la partida: estado del tablero, bolsa, jugadores y turnos.
  - Por cada bot, crea una vez BotFacade(BotConfig(...)).
  - En el turno de un bot: llama a bot.decide_turn_fairplay(state, player_idx)
    pasando el estado completo; la API solo usa tablero, número de fichas en la
    bolsa y las fichas de ese jugador (fairplay).
  - La API devuelve un Move. Para obtener un string: move.short(). Para enviar
    por red o guardar: move_to_dict(move) → dict serializable a JSON.

Decisiones de diseño relevantes antes de integrarlo en un entorno real:

1) Alcance de reglas:
   - Se implementan reglas clásicas de validación de melds (grupos y escaleras),
     apertura mínima de 30 puntos y uso de comodines.
   - El bot puede crear melds nuevos, extender melds ya presentes y reorganizar
     el tablero (coger fichas de conjuntos existentes y formar nuevos conjuntos).

2) Arquitectura "state in / move out":
   - El bot no mantiene estado oculto de partida.
   - Cada turno recibe un `GameState` (o una vista fairplay) y devuelve un `Move` legal.
   - Este patrón facilita depuración, reproducibilidad y ejecución en paralelo.

3) Modos de vista (fairplay vs simulación):
   - Fairplay (producción): el bot solo recibe tablero, bolsa (tamaño), sus fichas y
     el número de fichas de cada rival (sin verlas). Use decide_turn_fairplay() o
     pase a decide_turn() el resultado de make_fairplay_view().
   - Simulación: el bot recibe el estado completo (incluidas fichas de todos).
     Pase el GameState completo a decide_turn() para tests o análisis.

4) Niveles de dificultad (1..10) + aleatoriedad (0..1):
   - El nivel controla la calidad media de selección de jugadas.
   - Internamente el bot combina heurística + búsqueda acotada por tiempo.
   - La aleatoriedad añade ruido explícito en la elección final.

5) Determinismo opcional:
   - Se soporta `seed` para reproducir partidas y comparar configuraciones.
   - Sin seed, el bot usa variación no determinista.

6) Contrato para producción:
   - El bot asume que `GameState` representa una posición legal.
   - Se recomienda validar jugadas en el servidor (autoridad final de reglas).
   - Las jugadas deben aplicarse de forma transaccional para evitar desincronía.
   - El bot filtra internamente por legalidad antes de devolver la jugada.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ai import BotConfig as _BotConfig
from .ai import StrategicBot
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
    tile_from_short,
)
from .move_logic import clone_state


class ViewMode(str, Enum):
    """Modo de información que recibe el bot al decidir."""

    FAIRPLAY = "fairplay"
    """Solo tablero, bolsa (tamaño), sus fichas y número de fichas por rival."""

    SIMULATION = "simulation"
    """Estado completo: tablero, bolsa y fichas de todos los jugadores."""


@dataclass(frozen=True)
class BotConfig(_BotConfig):
    """Configuración de dificultad y ruido del bot."""


def make_fairplay_view(state: GameState, player_idx: int) -> GameState:
    """
    Construye una vista del estado donde el bot solo ve sus fichas y el tablero.

    Los racks de los demás jugadores se vacían en la vista; se guarda en
    state.opponent_rack_counts el número de fichas por jugador (para heurísticas
    que usen cantidad sin ver las fichas). La bolsa se mantiene (solo se usa
    len(pool) en el bot). Idóneo para partidas con al menos un jugador real.

    Uso desde un backend:
      view = make_fairplay_view(state, current_player_idx)
      move = bot.decide_turn(view, current_player_idx)
    """
    view = clone_state(state)
    counts = [len(state.players[i].rack) for i in range(len(state.players))]
    for i in range(len(view.players)):
        if i != player_idx:
            view.players[i].rack = []
    view.opponent_rack_counts = counts
    return view


def move_to_dict(move: Move) -> dict:
    """
    Serializa la jugada a un dict listo para JSON (para otro proceso/lenguaje).

    Incluye move_type y los datos necesarios para aplicar la jugada:
    - pass: solo move_type.
    - play_melds: new_melds como lista de listas de strings (ej. [["B02","B03","B04"]]).
    - extend_meld: extend_index y extension_tiles (lista de un string).
    - replace_board: new_board (lista de listas de strings de fichas).

    En modo arcade el move_type "use_item" es especial: no es una jugada del
    motor sino una petición del bot para que el backend ejecute un objeto y
    vuelva a llamar a /api/bot/move con arcade.items_used_this_turn
    actualizado. En ese caso la respuesta solo lleva "move_type", "reason" e
    "item_use"; no incluye new_melds, extension_tiles ni new_board.

    En el resto de move_types (pass, play_melds, extend_meld, replace_board):
      - Si el request incluía arcade.shop.offer, se añade "shop_choice"
        (objeto con "buy" y "reason"). buy == null si el bot no compra.
    """
    d: dict = {"move_type": move.move_type.value, "reason": move.reason}
    if move.move_type == MoveType.USE_ITEM:
        # USE_ITEM: solo item_use es relevante; no hay jugada del motor.
        if move.item_use is not None:
            d["item_use"] = item_use_to_dict(move.item_use)
        return d
    if move.move_type == MoveType.PLAY_MELDS:
        d["new_melds"] = [[t.short() for t in m.tiles] for m in move.new_melds]
    elif move.move_type == MoveType.EXTEND_MELD:
        d["extend_index"] = move.extend_index
        d["extension_tiles"] = [t.short() for t in move.extension_tiles]
    elif move.move_type == MoveType.REPLACE_BOARD:
        d["new_board"] = [[t.short() for t in m.tiles] for m in move.new_board]
    if move.shop_choice is not None:
        d["shop_choice"] = shop_choice_to_dict(move.shop_choice)
    return d


def item_use_to_dict(item_use: ItemUse) -> dict:
    """
    Serializa una sugerencia de uso de objeto (modo arcade) a dict JSON.
    Incluye el objeto, el jugador objetivo (si aplica), parámetros y razón.
    """
    d: dict = {"item": item_use.item.value, "reason": item_use.reason}
    if item_use.target_player_idx is not None:
        d["target_player_idx"] = item_use.target_player_idx
    if item_use.params:
        d["params"] = dict(item_use.params)
    return d


_COLOR_SHORT_MAP: dict[str, Color] = {
    "K": Color.BLACK,
    "B": Color.BLUE,
    "O": Color.ORANGE,
    "R": Color.RED,
}


def _parse_blocked_color(raw: object) -> Color | None:
    """
    Interpreta el color bloqueado desde el payload. Acepta letra corta
    ('K'/'B'/'O'/'R') o el valor largo del enum ('black', 'blue', ...).
    Devuelve None si el campo está ausente o es explícitamente null.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if len(s) == 1 and s.upper() in _COLOR_SHORT_MAP:
        return _COLOR_SHORT_MAP[s.upper()]
    try:
        return Color(s.lower())
    except ValueError:
        raise ValueError(f"arcade.blocked_color no válido: {raw!r}")


def _parse_shop(payload_shop: dict | None) -> tuple[list[ShopOffer], int]:
    """
    Parsea el subobjeto 'arcade.shop' del request. Devuelve (offer, balance).

    Si 'arcade.shop' está ausente o es null, devuelve ([], 0) (tienda cerrada
    este turno: el bot no emitirá shop_choice).

    Estructura esperada:
      - offer: lista de {"item": "<ItemType>", "price": int≥0}.
      - balance: int≥0. Saldo disponible del bot en la moneda de la tienda.
    """
    if not payload_shop:
        return [], 0
    if not isinstance(payload_shop, dict):
        raise ValueError("arcade.shop debe ser un objeto JSON")
    offer_raw = payload_shop.get("offer") or []
    if not isinstance(offer_raw, list):
        raise ValueError("arcade.shop.offer debe ser una lista")
    offer: list[ShopOffer] = []
    for idx, entry in enumerate(offer_raw):
        if not isinstance(entry, dict) or "item" not in entry or "price" not in entry:
            raise ValueError(f"arcade.shop.offer[{idx}] debe tener 'item' y 'price'")
        try:
            item_type = ItemType(str(entry["item"]))
        except ValueError:
            raise ValueError(
                f"arcade.shop.offer[{idx}].item desconocido: {entry['item']!r}"
            )
        try:
            price = int(entry["price"])
        except (TypeError, ValueError):
            raise ValueError(f"arcade.shop.offer[{idx}].price no es entero")
        if price < 0:
            raise ValueError(f"arcade.shop.offer[{idx}].price negativo")
        offer.append(ShopOffer(item=item_type, price=price))
    balance_raw = payload_shop.get("balance", 0)
    try:
        balance = max(0, int(balance_raw))
    except (TypeError, ValueError):
        raise ValueError("arcade.shop.balance no es entero")
    return offer, balance


def _parse_arcade(payload_arcade: dict | None) -> ArcadeState | None:
    """
    Construye un ArcadeState desde el subobjeto 'arcade' del payload. Si está
    ausente o es null, devuelve None (modo normal).

    Campos aceptados (todos opcionales):
      - enabled: bool (por defecto True si el objeto existe).
      - blocked_color: 'K'|'B'|'O'|'R' o nombre largo del enum Color.
      - min_play_points: número (techo de cristal).
      - my_items: lista de strings de ItemType (máx 3).
      - opponent_item_counts: lista de ints con objetos por rival.
      - time_limit_s: int (tiempo máximo de turno).
      - shop_discount: float (ej. 0.5 para 50%).
      - draw_at_turn_start: bool.
      - shop: objeto con "offer" (lista de {item, price}) y "balance" (int)
        representando la tienda abierta este turno. Si se envía, el bot emite
        su decisión en move.shop_choice.
      - items_used_this_turn: lista de strings de ItemType ya consumidos o
        denegados en el turno actual del bot. El backend la mantiene entre
        fases (cada USE_ITEM añade una entrada, se reinicia al terminar el
        turno). El bot no propondrá de nuevo ningún objeto que aparezca aquí.
      - guardian_angel_active: bool. True si el jugador ya tiene un escudo
        de Ángel activo (un Ángel adquirido antes, ya "convertido" por el
        backend). El bot lo usa para no comprar ni aceptar más Ángeles.
    """
    if not payload_arcade:
        return None
    if not isinstance(payload_arcade, dict):
        raise ValueError("arcade debe ser un objeto JSON")

    enabled = bool(payload_arcade.get("enabled", True))
    blocked_color = _parse_blocked_color(payload_arcade.get("blocked_color"))
    min_pts_raw = payload_arcade.get("min_play_points")
    min_play_points = int(min_pts_raw) if min_pts_raw is not None else None

    items_raw = payload_arcade.get("my_items") or []
    my_items: list[ItemType] = []
    for it in items_raw:
        try:
            my_items.append(ItemType(str(it)))
        except ValueError:
            raise ValueError(f"arcade.my_items: objeto desconocido {it!r}")
    # Límite de diseño: máximo 3 objetos por jugador.
    my_items = my_items[:3]

    opp_items_raw = payload_arcade.get("opponent_item_counts") or []
    opponent_item_counts = [int(c) for c in opp_items_raw]

    time_limit_raw = payload_arcade.get("time_limit_s")
    time_limit_s = int(time_limit_raw) if time_limit_raw is not None else None
    shop_discount_raw = payload_arcade.get("shop_discount")
    shop_discount = float(shop_discount_raw) if shop_discount_raw is not None else None
    draw_at_turn_start = bool(payload_arcade.get("draw_at_turn_start", False))
    shop_offer, shop_balance = _parse_shop(payload_arcade.get("shop"))

    used_raw = payload_arcade.get("items_used_this_turn") or []
    items_used_this_turn: list[ItemType] = []
    for it in used_raw:
        try:
            items_used_this_turn.append(ItemType(str(it)))
        except ValueError:
            raise ValueError(
                f"arcade.items_used_this_turn: objeto desconocido {it!r}"
            )

    guardian_angel_active = bool(payload_arcade.get("guardian_angel_active", False))

    return ArcadeState(
        enabled=enabled,
        blocked_color=blocked_color,
        min_play_points=min_play_points,
        my_items=my_items,
        opponent_item_counts=opponent_item_counts,
        time_limit_s=time_limit_s,
        shop_discount=shop_discount,
        draw_at_turn_start=draw_at_turn_start,
        shop_offer=shop_offer,
        shop_balance=shop_balance,
        items_used_this_turn=items_used_this_turn,
        guardian_angel_active=guardian_angel_active,
    )


def state_from_bot_request(payload: dict) -> GameState:
    """
    Construye un GameState desde el JSON que envía el backend (Spring Boot).

    Payload esperado:
      - board: lista de melds; cada meld = lista de strings "B02", "J*", etc. (Palo+Número).
      - pool_count: número de fichas en la bolsa.
      - my_tiles: lista de strings de las fichas del bot.
      - opponent_rack_counts: (opcional) lista con el número de fichas de cada rival.
      - opened: (opcional) si el bot ya abrió; por defecto True si hay melds en el tablero.
      - arcade: (opcional, modo arcade) objeto con restricciones y estado arcade
        de la ronda. Ver _parse_arcade para los campos aceptados. Si está
        ausente o es null, el bot decide en modo normal.

    Devuelve un estado listo para decide_turn (ya en forma fairplay: otros racks vacíos).
    """
    board_data = payload.get("board") or []
    pool_count = int(payload.get("pool_count", 0))
    my_tiles_data = payload.get("my_tiles") or []
    opponent_rack_counts = list(payload.get("opponent_rack_counts") or [])

    # Asignar uid único a cada ficha para validación de jugadas.
    uid = 1
    def parse_tile(s: str) -> Tile:
        nonlocal uid
        t = tile_from_short(str(s), uid=uid)
        uid += 1
        return t

    melds: list[Meld] = []
    for meld_list in board_data:
        tiles = [parse_tile(s) for s in meld_list]
        if tiles:
            melds.append(Meld(tiles=tiles))

    my_tiles = [parse_tile(s) for s in my_tiles_data]
    opened = payload.get("opened")
    if opened is None:
        opened = len(melds) > 0

    # Bolsa: el bot solo usa len(pool); usamos fichas dummy.
    dummy = Tile(value=1, color=Color.BLACK, is_joker=False, uid=0)
    pool = [dummy] * max(0, pool_count)

    players: list[PlayerState] = [
        PlayerState(player_id="Bot", rack=my_tiles, opened=opened),
    ]
    counts = [len(my_tiles)]
    for c in opponent_rack_counts:
        players.append(PlayerState(player_id=f"Opponent-{len(players)}", rack=[], opened=True))
        counts.append(int(c))

    arcade_state = _parse_arcade(payload.get("arcade"))

    state = GameState(
        board=Board(melds=melds),
        players=players,
        pool=pool,
        current_player_idx=0,
        turn_number=int(payload.get("turn_number", 1)),
        opponent_rack_counts=counts,
        arcade=arcade_state,
    )
    return state


def shop_choice_to_dict(choice: ShopChoice) -> dict:
    """
    Serializa una ShopChoice a dict JSON listo para enviar por HTTP.
    buy se emite como null cuando el bot decide no comprar.
    """
    return {
        "buy": choice.buy.value if choice.buy is not None else None,
        "reason": choice.reason,
    }


class BotFacade:
    """Fachada amigable para invocar decisiones del bot."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._bot = StrategicBot(config)

    def decide_turn(self, state: GameState, player_idx: int) -> Move:
        """
        Decide la jugada dado un estado. Acepta estado completo (simulación) o
        una vista fairplay (make_fairplay_view). En fairplay el bot no ve las
        fichas de los demás.
        """
        return self._bot.choose_move(state, player_idx)

    def decide_turn_fairplay(self, state: GameState, player_idx: int) -> Move:
        """
        Igual que decide_turn, pero enmascara las fichas de los otros jugadores
        de forma transparente. El backend puede pasar el estado completo y el
        bot solo recibe tablero, bolsa y sus fichas (más número de fichas por rival).

        Devuelve un Move. Para string legible: move.short(). Para JSON: move_to_dict(move).
        """
        view = make_fairplay_view(state, player_idx)
        return self.decide_turn(view, player_idx)

    def decide_shop(
        self,
        offer: list[ShopOffer],
        balance: int,
        current_items: list[ItemType] | None = None,
        opponent_rack_counts: list[int] | None = None,
        my_tiles_count: int = 0,
        my_opened: bool = False,
        guardian_angel_active: bool = False,
    ) -> ShopChoice:
        """
        Decide si comprar un objeto ofrecido por la tienda arcade (o ninguno).
        Wrapper de StrategicBot.choose_shop_item con argumentos por defecto
        cómodos. El backend ejecuta la compra; el bot solo recomienda.

        guardian_angel_active indica si el jugador ya tiene un escudo de
        Ángel activo (ver core.ArcadeState); cuando es True el bot nunca
        sugiere comprar otro GUARDIAN_ANGEL.
        """
        return self._bot.choose_shop_item(
            offer=list(offer),
            balance=balance,
            current_items=list(current_items or []),
            opponent_rack_counts=list(opponent_rack_counts or []),
            my_tiles_count=my_tiles_count,
            my_opened=my_opened,
            guardian_angel_active=guardian_angel_active,
        )
