# Interfaz Web RummiPlus

Visualizador web para ver jugadas de bots turno a turno.

## Ejecutar

Desde la raiz del proyecto:

```bash
python3 web_ui/server.py
```

Luego abre:

`http://127.0.0.1:8765`

Si el puerto esta ocupado:

```bash
python3 web_ui/server.py --port 8766
```

## UI incluida

- Menu intuitivo con presets (equilibrado, competitivo, caotico).
- Configuracion de 2 a 4 bots y nivel individual por bot.
- Tablero visual con melds y fichas coloreadas por palo.
- Reproduccion temporal completa (inicio, anterior, play/pause, siguiente, final, slider).
- Racks visuales por jugador (modo normal/compacto).
- Timeline clicable de turnos y resumen de puntuaciones final.

## Opciones

- Niveles de bots (`1,5,10`, por ejemplo).
- Aleatoriedad.
- Seed.
- Maximo de turnos.
- Controles de reproduccion (play/pause, slider de turnos, velocidad).
