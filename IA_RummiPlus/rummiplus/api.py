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
from .core import Board, Color, GameState, Meld, Move, MoveType, PlayerState, Tile, tile_from_short
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
    """
    d: dict = {"move_type": move.move_type.value, "reason": move.reason}
    if move.move_type == MoveType.PLAY_MELDS:
        d["new_melds"] = [[t.short() for t in m.tiles] for m in move.new_melds]
    elif move.move_type == MoveType.EXTEND_MELD:
        d["extend_index"] = move.extend_index
        d["extension_tiles"] = [t.short() for t in move.extension_tiles]
    elif move.move_type == MoveType.REPLACE_BOARD:
        d["new_board"] = [[t.short() for t in m.tiles] for m in move.new_board]
    return d


def state_from_bot_request(payload: dict) -> GameState:
    """
    Construye un GameState desde el JSON que envía el backend (Spring Boot).

    Payload esperado:
      - board: lista de melds; cada meld = lista de strings "B02", "J*", etc. (Palo+Número).
      - pool_count: número de fichas en la bolsa.
      - my_tiles: lista de strings de las fichas del bot.
      - opponent_rack_counts: (opcional) lista con el número de fichas de cada rival.
      - opened: (opcional) si el bot ya abrió; por defecto True si hay melds en el tablero.

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

    state = GameState(
        board=Board(melds=melds),
        players=players,
        pool=pool,
        current_player_idx=0,
        turn_number=int(payload.get("turn_number", 1)),
        opponent_rack_counts=counts,
    )
    return state


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
