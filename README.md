# IA_RummiPlus

Entorno **Vibecodeado** para creación de IA para **Rummikub** (clásico) y su **modo arcade**. Implementación desde cero de bots con validación de reglas, niveles configurables y API lista para integrar.

## Contenido del proyecto

- Validación de reglas base (grupos, escaleras, comodín, apertura de 30 puntos).
- Bots con `nivel` (1-10) y `aleatoriedad` configurable (0-1).
- Selección híbrida: heurística rápida + búsqueda con poda por tiempo.
- API simple `state -> move` para integración.
- Simulador por turnos para comparar calidad entre bots.
- Interfaz web para visualizar partidas turno a turno.

---

## Cómo encender la web

Desde la **raíz del proyecto** (`IA_RummiPlus/`):

```bash
python3 web_ui/server.py
```

Por defecto el servidor escucha en el puerto **8765**. Si ese puerto está ocupado:

```bash
python3 web_ui/server.py --port 8766
```

Para escuchar en otra interfaz (por ejemplo todas las interfaces):

```bash
python3 web_ui/server.py --host 0.0.0.0 --port 8765
```

---

## Cómo entrar a la interfaz web

Con el servidor en marcha, abre en el navegador:

- **http://127.0.0.1:8765** (o **http://localhost:8765**)

Si usaste otro puerto (por ejemplo `8766`), cambia el número en la URL.

La UI permite configurar partidas (2–4 bots, niveles, aleatoriedad, seed), ver el tablero con melds y fichas, y reproducir la partida (play/pause, slider de turnos, timeline). Más detalles en `web_ui/README.md`.

---

## Demo por línea de comandos

Sin abrir la web puedes ejecutar simulaciones de bots:

```bash
python3 demo_bots.py --levels 1,5,10 --randomness 0.25 --games 80
```

---

## API principal

Importa desde `rummiplus`:

- `BotConfig`
- `BotFacade`
- `GameState`, `Move`, etc.
- `run_simulation`

La cabecera detallada de decisiones de diseño está en `rummiplus/api.py`.

## Ajustes avanzados del bot

En `BotConfig`:

- `search_time_ms`: presupuesto de tiempo para búsqueda por turno.
- `search_depth_cap`: profundidad máxima de lookahead.
- `search_beam_cap`: ancho máximo de beam en la exploración.
