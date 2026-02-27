"""
API pública para integrar un jugador automático de Rummikub clásico.

Decisiones de diseño relevantes antes de integrarlo en un entorno real:

1) Alcance de reglas:
   - Se implementan reglas clásicas de validación de melds (grupos y escaleras),
     apertura mínima de 30 puntos y uso de comodines.
   - El bot puede crear melds nuevos, extender melds ya presentes y reorganizar
     el tablero (coger fichas de conjuntos existentes y formar nuevos conjuntos).

2) Arquitectura "state in / move out":
   - El bot no mantiene estado oculto de partida.
   - Cada turno recibe un `GameState` y devuelve un `Move` legal.
   - Este patrón facilita depuración, reproducibilidad y ejecución en paralelo.

3) Niveles de dificultad (1..10) + aleatoriedad (0..1):
   - El nivel controla la calidad media de selección de jugadas.
   - Internamente el bot combina heurística + búsqueda acotada por tiempo.
   - La aleatoriedad añade ruido explícito en la elección final.
   - Incluso niveles altos pueden cometer errores con baja probabilidad.
   - Incluso niveles bajos pueden acertar con baja probabilidad.
   - Resultado: comportamiento más humano y configurable.

4) Determinismo opcional:
   - Se soporta `seed` para reproducir partidas y comparar configuraciones.
   - Sin seed, el bot usa variación no determinista.

5) Contrato para producción:
   - El bot asume que `GameState` representa una posición legal.
   - Se recomienda validar jugadas en el servidor (autoridad final de reglas).
   - Las jugadas deben aplicarse de forma transaccional para evitar desincronía.
   - El bot filtra internamente por legalidad antes de devolver la jugada.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ai import BotConfig as _BotConfig
from .ai import StrategicBot
from .core import GameState, Move


@dataclass(frozen=True)
class BotConfig(_BotConfig):
    """Configuración de dificultad y ruido del bot."""


class BotFacade:
    """Fachada amigable para invocar decisiones del bot."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._bot = StrategicBot(config)

    def decide_turn(self, state: GameState, player_idx: int) -> Move:
        return self._bot.choose_move(state, player_idx)
