# RummiPlus — Bot de Rummikub para backends

Bot de Rummikub clásico expuesto por HTTP para integrar en **Spring Boot**. El backend gestiona la partida (web, cliente de escritorio, etc.); en el turno del bot llama a esta API y recibe la jugada en JSON.

---

## Índice

1. [Uso del servicio (consumidores de la API)](#1-uso-del-servicio-consumidores-de-la-api)
2. [Qué es este código y cómo funciona el modelo](#2-qué-es-este-código-y-cómo-funciona-el-modelo)
3. [Estructura del paquete](#3-estructura-del-paquete)

---

# 1. Uso del servicio (consumidores de la API)

> **Importante:** Esta sección es la que debe seguir el consumidor de la API (Spring Boot u otro backend HTTP). Aquí se explica **qué es el bot y cómo “se crea”**, **cómo arrancar y usar el servicio**, **cómo hacer las peticiones HTTP con detalle** y **cómo aplicar la jugada** en tu motor.

---

## 1.1 Qué es el bot y cómo se usa (no hace falta “crearlo”)

El **bot** es el programa que, dado el estado actual del juego (tablero, bolsa, mano del jugador), decide la jugada (pasar, jugar melds (conjuntos de fichas en mesa), extender, reorganizar). Ese programa vive **dentro del servicio HTTP** que arrancas con `python -m rummiplus.server`.  
**No tienes que crear ni instanciar el bot en tu aplicación.** Desde Spring Boot (o cualquier cliente) solo haces lo siguiente:

1. **Arrancar el servicio** en Python (una sola vez, en la misma máquina o en un servidor accesible).
2. **Cuando sea el turno del bot:** construir un JSON con el estado (tablero, `pool_count` (fichas en bolsa), `my_tiles` (mis fichas), etc.) y hacer **POST** a `/api/bot/move`.
3. **Recibir la respuesta** en JSON (`move` (jugada) + `move_short`) y **aplicar esa jugada** en tu motor de juego (quitar fichas del rack (mano), actualizar tablero, pasar turno, etc.).

Cada petición es **independiente**: el servidor no guarda estado entre llamadas. Tu backend es el dueño de la partida; el servicio solo responde a “con este estado, ¿qué jugada hace el bot?”.

---

## 1.2 Arrancar el servicio

El servicio es un servidor HTTP en Python. Debe estar en ejecución en la misma máquina (o accesible por red) que tu backend o juego.

**Requisitos:** Python 3.10 o superior. No se necesitan dependencias externas (solo biblioteca estándar).

Desde la raíz del proyecto `IA_RummiPlus`:

```bash
python -m rummiplus.server --host 127.0.0.1 --port 8765
```

- **`--host`:** Dirección de escucha (`127.0.0.1` solo local; `0.0.0.0` para aceptar conexiones de otras máquinas).
- **`--port`:** Puerto (por defecto `8765`).

Salida esperada:

```
API bot: http://127.0.0.1:8765/api/bot/move (concurrente)
```

**Comprobar que responde:**

```bash
curl http://127.0.0.1:8765/api/health
```

Respuesta: `{"ok": true}`.

---

## 1.3 Probar la API con el script (probar_api.sh)

Para comprobar que el servicio y el bot responden bien **sin escribir código**, usa el script incluido en el proyecto. Ejecuta varias peticiones de ejemplo y muestra la respuesta formateada.

**Requisito:** El servidor debe estar levantado (ver apartado anterior).

Desde la raíz del proyecto:

```bash
cd IA_RummiPlus
bash scripts/probar_api.sh
```

Por defecto el script usa `http://127.0.0.1:8765`. Si tu servidor está en otro host o puerto, pásalo como argumento:

```bash
bash scripts/probar_api.sh http://localhost:8765
```

**Qué hace el script:**

1. **Health:** GET `/api/health` → debe devolver `{"ok": true}`.
2. **Apertura:** POST con tablero vacío y una mano de 14 fichas; comprueba que el bot devuelve una jugada (p. ej. `play_melds` (jugar conjuntos) o `pass` (pasar)).
3. **Tablero con melds (conjuntos):** POST con tablero ya con conjuntos y otra mano; comprueba que la respuesta es coherente.
4. **Niveles:** Pide una jugada con nivel 1 y otra con nivel 9; verifica que ambos responden (las jugadas pueden ser distintas).

Si todas las salidas son JSON válidos y sin errores, la API y el modelo están operativos. Es la forma recomendada de validar la instalación antes de integrar desde Spring Boot.

---

## 1.4 Endpoint de la jugada

| Método | URL | Descripción |
|--------|-----|-------------|
| **POST** | `http://<host>:<port>/api/bot/move` | Envías estado del juego; recibes la jugada del bot. |
| GET | `http://<host>:<port>/api/health` | Comprueba que el servicio está vivo. |

**Cabecera obligatoria:** `Content-Type: application/json`

---

## 1.5 Ejemplo completo de petición HTTP (curl)

Para hacer la petición con **máximo detalle** a nivel HTTP (método, URL, cabeceras, body y respuesta), puedes usar `curl` desde la terminal. Así ves exactamente qué se envía y qué se recibe.

**1. Servidor en marcha** (en otra terminal):

```bash
python -m rummiplus.server --port 8765
```

**2. Petición POST a `/api/bot/move`:**

- **Método:** `POST`
- **URL:** `http://127.0.0.1:8765/api/bot/move`
- **Cabeceras:** `Content-Type: application/json`
- **Cuerpo:** JSON con al menos `board` (tablero), `pool_count` (fichas en bolsa) y `my_tiles` (mis fichas) (ver sección siguiente para todos los campos).

Ejemplo mínimo (tablero vacío, apertura):

```bash
curl -s -X POST http://127.0.0.1:8765/api/bot/move \
  -H "Content-Type: application/json" \
  -d '{
    "board": [],
    "pool_count": 60,
    "my_tiles": ["B01","B02","B03","B04","B05","B06","B07","B08","B09","B10","B11","B12","B13","R01"]
  }'
```

**3. Respuesta esperada (ejemplo):**

- **Código HTTP:** `200 OK`
- **Cuerpo:** JSON con `move` (jugada: objeto con `move_type`, `reason` y, según el tipo, `new_melds` (nuevos conjuntos), etc.) y `move_short` (texto legible). Por ejemplo:

```json
{
  "move": {
    "move_type": "play_melds",
    "reason": "apertura 30+",
    "new_melds": [["B01","B02","B03","B04","B05","B06","B07"],["B08","B09","B10","B11","B12","B13"]]
  },
  "move_short": "[B01 B02 ... B07] + [B08 ... B13]"
}
```

**4. Códigos de estado y errores:**

| Código | Significado |
|--------|-------------|
| **200** | OK. El cuerpo es el JSON con `move` y `move_short`. |
| **400** | Petición inválida (JSON mal formado, campos obligatorios faltantes, formato de fichas incorrecto). Cuerpo: `{"error": "mensaje descriptivo"}`. |
| **404** | Ruta no encontrada (por ejemplo GET a `/api/bot/move` o URL equivocada). |
| **405** | Método no permitido (por ejemplo GET en `/api/bot/move`; allí solo se acepta POST). |
| **500** | Error interno del servidor. Cuerpo puede ser `{"error": "..."}`. |

Ejemplo de respuesta de error (body):

```json
{"error": "missing required field: my_tiles"}
```

Con esto tienes todo lo necesario para implementar el cliente HTTP en cualquier lenguaje: mismo método, URL, cabecera, cuerpo y manejo de códigos y errores.

---

## 1.6 Cuerpo de la petición (request)

El body debe ser un JSON con al menos los campos siguientes. El bot **solo usa** tablero, número de fichas en la bolsa y **sus propias fichas** (modo fairplay (juego limpio: no ve las fichas de los rivales)); el resto son opcionales para mejorar la decisión.

### Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `board` | `array` de `array` de `string` | Tablero actual. Cada elemento es un **meld** (conjunto de fichas en mesa): lista de fichas (Palo+Número). Ejemplo: `[["B02","B03","B04"], ["R01","O01","K01"]]`. |
| `pool_count` | `number` | Número de fichas que quedan en la **bolsa** (pool). |
| `my_tiles` | `array` de `string` | Fichas del jugador bot (su **mano**, rack). Mismo formato que las fichas del tablero. |

### Campos opcionales

| Campo | Tipo | Por defecto | Descripción |
|-------|------|-------------|-------------|
| `opponent_rack_counts` | `array` de `number` | `[]` | Número de fichas en la **mano** (rack) de cada rival. Ej: `[14, 12]` para dos rivales con 14 y 12 fichas. Mejora la calidad de la decisión. |
| `opened` | `boolean` | `true` si `board` tiene melds | Si el bot **ya ha abierto** (opened: ha jugado al menos 30 puntos en una jugada anterior). |
| `level` | `number` 1–10 | `5` | Dificultad del bot (1 más fácil, 10 más fuerte). |
| `randomness` | `number` 0–1 | `0.25` | Aleatoriedad en la elección (0 determinista, 1 muy variable). |
| `seed` | `number` o `null` | `null` | Si pones un número, las decisiones son reproducibles para ese seed. |
| `turn_number` | `number` | `1` | Solo informativo. |

### Formato de cada ficha (`string`)

- **Numérica:** letra de palo + dos dígitos (valor).  
  Palo: `K` = negro, `B` = azul, `O` = naranja, `R` = rojo. Valor: `01`–`13`.  
  Ejemplos: `"B01"`, `"R13"`, `"K07"`.
- **Comodín:** `"J*"` o `"J"`.

**Ejemplo mínimo de body:**

```json
{
  "board": [],
  "pool_count": 60,
  "my_tiles": ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13", "R01"]
}
```

**Ejemplo completo (con rivales y nivel):**

```json
{
  "board": [["B02", "B03", "B04"], ["R01", "O01", "K01"]],
  "pool_count": 50,
  "my_tiles": ["B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13", "K01", "K02", "K03", "K04", "K05"],
  "opponent_rack_counts": [14, 14],
  "opened": false,
  "level": 5,
  "randomness": 0.25
}
```

---

## 1.7 Respuesta (response)

El servidor devuelve **siempre** un JSON con dos claves:

| Clave | Tipo | Uso |
|-------|------|-----|
| `move` | objeto | Jugada estructurada para **aplicar en tu motor**. |
| `move_short` | string | Texto legible para logs o UI (ej. `"PASAR"`, `"[B05 B06 B07] + [B09 B10 B11]"`). |

### Estructura de `move`

Depende de `move_type`. **Siempre** viene:

- `move_type`: `"pass"` (pasar) | `"play_melds"` (jugar conjuntos) | `"extend_meld"` (extender conjunto) | `"replace_board"` (reorganizar tablero)
- `reason`: string (explicación interna).

Según el tipo, pueden venir campos adicionales:

| `move_type` | Campos adicionales | Significado |
|-------------|--------------------|-------------|
| `pass` (pasar) | (ninguno) | El bot pasa turno; en tu motor debe robar una ficha de la bolsa (si hay) y pasar al siguiente jugador. |
| `play_melds` (jugar conjuntos) | `new_melds`: `[[ficha, ...], ...]` | Jugada de **melds** (conjuntos) nuevos. Quitar esas fichas de la mano (rack) del bot y añadir cada lista como un conjunto al tablero. Marcar al jugador como “abierto” si aún no lo estaba (opened). |
| `extend_meld` (extender conjunto) | `extend_index`: número, `extension_tiles`: `[ficha]` | Extender el **meld** (conjunto) del tablero en la posición `extend_index` con la ficha indicada. Quitar esa ficha de la mano del bot y reemplazar ese conjunto por el extendido. |
| `replace_board` (reorganizar tablero) | `new_board`: `[[ficha, ...], ...]` | Reorganización: el tablero pasa a ser exactamente la lista de **melds** (conjuntos) en `new_board`. Quitar de la mano del bot las fichas que aparecen en `new_board` y no estaban en el tablero anterior; el resto del tablero se sustituye. |

**Ejemplo de respuesta — jugar melds (conjuntos):**

```json
{
  "move": {
    "move_type": "play_melds",
    "reason": "apertura 30+",
    "new_melds": [["B05", "B06", "B07"], ["B09", "B10", "B11"]]
  },
  "move_short": "[B05 B06 B07] + [B09 B10 B11]"
}
```

**Ejemplo — pasar:**

```json
{
  "move": { "move_type": "pass", "reason": "no abrir todavía" },
  "move_short": "PASAR"
}
```

**Errores:** Si el JSON es inválido o falta algo crítico, el servidor responde con código 4xx y un cuerpo como `{"error": "mensaje"}`.

---

## 1.8 Ejemplo completo: Spring Boot (Java)

El backend en Spring Boot es quien gestiona la partida (tanto si los clientes son web como escritorio). Cuando es el turno de un bot, Spring Boot construye el JSON con el estado actual, hace POST a la API de RummiPlus, recibe la jugada y la aplica en su modelo de juego. A continuación se detalla cada pieza.

### 1. Dependencia (Maven)

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

### 2. DTOs de request y response

El cuerpo del POST que envías a `/api/bot/move` se mapea a un record (o clase) con los campos del JSON. La respuesta tiene `move` (objeto con `move_type`, `reason` y, según el tipo, `new_melds`, `extend_index`, etc.) y `move_short` (string legible).

```java
import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record BotMoveRequest(
    List<List<String>> board,
    int pool_count,
    List<String> my_tiles,
    List<Integer> opponent_rack_counts,
    Boolean opened,
    Integer level,
    Double randomness,
    Integer seed
) {}

public record BotMoveResponse(
    MovePayload move,
    String move_short
) {}

public record MovePayload(
    String move_type,
    String reason,
    List<List<String>> new_melds,
    Integer extend_index,
    List<String> extension_tiles,
    List<List<String>> new_board
) {}
```

### 3. Cliente HTTP y uso en el turno del bot

Un único punto de entrada: dado el estado de la partida para el jugador bot, envías el request y recibes la jugada. No necesitas mantener estado del bot en Java; cada vez que es su turno construyes el request y llamas a la API.

```java
import org.springframework.web.client.RestTemplate;

public class RummiBotClient {

    private final String baseUrl;
    private final RestTemplate rest = new RestTemplate();

    public RummiBotClient(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    /**
     * Pide una jugada al bot. Tu motor debe haber construido el estado actual
     * (tablero, pool_count, fichas del bot, opcionalmente opponent_rack_counts y opened).
     */
    public BotMoveResponse askBot(BotMoveRequest request) {
        return rest.postForObject(
            baseUrl + "/api/bot/move",
            request,
            BotMoveResponse.class
        );
    }
}
```

### 4. Construir el request desde tu estado de partida

Desde tu modelo de juego (tablero, bolsa, manos de cada jugador) debes extraer: el tablero como lista de **melds** (conjuntos; cada meld = lista de strings en formato Palo+Número), el tamaño de la bolsa (pool), las fichas del jugador bot (rack) y, si lo tienes, el número de fichas de cada rival y si el bot ya abrió (opened). Ejemplo de construcción del request:

```java
// Ejemplo: tienes tu propio modelo (tablero, jugadores, bolsa)
BotMoveRequest request = new BotMoveRequest(
    myGame.getBoardAsListOfMelds(),   // [["B02","B03","B04"], ...]
    myGame.getPoolSize(),
    myGame.getCurrentPlayerTiles(),   // ["B05", "B06", ...]
    myGame.getOpponentRackCounts(),   // [14, 14]
    myGame.hasCurrentPlayerOpened(),
    5,                                // level
    0.25,                             // randomness
    null                              // seed
);
BotMoveResponse response = botClient.askBot(request);
```

### 5. Aplicar la jugada en tu motor

Según el `move_type` devuelto, actualizas el estado de la partida: quitar fichas del **rack** (mano) del bot, añadir o modificar **melds** (conjuntos) en el tablero, o registrar que pasó (y robar ficha si aplica). Luego pasas al siguiente jugador y, si el bot vació la mano, compruebas fin de partida.

```java
MovePayload m = response.move();
switch (m.move_type()) {
    case "pass" -> myGame.passAndDraw(currentPlayerIndex);
    case "play_melds" -> myGame.playMelds(currentPlayerIndex, m.new_melds());
    case "extend_meld" -> myGame.extendMeld(currentPlayerIndex, m.extend_index(), m.extension_tiles().get(0));
    case "replace_board" -> myGame.replaceBoard(currentPlayerIndex, m.new_board());
}
// Luego: robar ficha si aplica, comprobar si ganó, pasar al siguiente jugador.
```

---

## 1.9 Resumen para el consumidor de la API

- Arrancar el servicio: `python -m rummiplus.server --port 8765`
- Probar que responde: `bash scripts/probar_api.sh` (con el servidor levantado).
- Desde Spring Boot: **POST** a `/api/bot/move` con JSON: `board` (tablero), `pool_count` (bolsa), `my_tiles` (mis fichas) (y opcionalmente `opponent_rack_counts` (fichas por rival), `opened` (ha abierto), `level`, etc.).
- Respuesta: `move` (jugada: objeto con `move_type` y campos según tipo) y `move_short` (texto legible).
- En tu backend: según `move_type`, aplicar pass (pasar), play_melds (jugar conjuntos), extend_meld (extender conjunto) o replace_board (reorganizar tablero) y pasar al siguiente turno.

---

# 2. Qué es este código y cómo funciona el modelo

> Esta sección está orientada a **programadores** que quieran entender el paquete por dentro. No es necesaria para consumir la API correctamente.

---

## 2.1 Qué es RummiPlus

RummiPlus es un **paquete en Python** que proporciona:

- Las **reglas** de Rummikub clásico (melds (conjuntos) válidos, apertura de 30 puntos, comodines).
- Un **bot** que, dado el estado del juego (tablero, bolsa, su mano), devuelve una jugada (pasar, jugar melds (conjuntos), extender, reorganizar tablero).
- Una **API HTTP** (servidor incluido en el paquete) para que backends en otros lenguajes (Java, GDScript, etc.) envíen ese estado y reciban la jugada en JSON.

El **motor de la partida** (quién reparte, quién roba, quién gana) lo lleva siempre tu backend; RummiPlus solo responde a la pregunta: “con este estado, ¿qué jugada hace el bot?”.

---

## 2.2 Tipo de “IA”: no es aprendizaje automático

El bot **no es un modelo de aprendizaje automático** (no hay red neuronal, ni entrenamiento con datos, ni ML típico). Es un **agente basado en reglas y búsqueda**:

- **Reglas:** Genera solo jugadas que cumplen las reglas del juego (melds (conjuntos) válidos, fichas en la mano (rack), apertura ≥30 si aplica).
- **Heurísticas:** Asigna a cada jugada un “score” con fórmulas fijas (puntos jugados, fichas que quedan en mano, bonus por vaciar mano, etc.).
- **Búsqueda:** En niveles altos, simula varias jugadas hacia delante (minimax con poda) y combina ese valor con el score de la opción.
- **Selección:** No elige siempre la mejor opción; introduce ruido y temperatura para que los niveles bajos fallen más y el comportamiento sea menos perfecto.

Por tanto, es un **sistema simbólico** (reglas + puntuaciones + búsqueda acotada), no un “modelo de IA” en el sentido de ML/DL.

---

## 2.3 Cómo obtiene una respuesta el bot (paso a paso)

El flujo interno para decidir una jugada es el siguiente. Todo ocurre **en el turno actual**; el bot no guarda memoria entre turnos.

### Paso 1 — Generar opciones

A partir del **estado actual** (tablero y **su** mano):

- Si aún no ha abierto (opened): se generan **combinaciones de melds** (conjuntos) que sumen al menos 30 puntos (apertura), más la opción de pasar.
- Si ya abrió: se generan **melds** (conjuntos) nuevos desde la mano (rack), **extensiones** de conjuntos del tablero con una ficha de la mano, y **reorganizaciones** (quitar fichas de conjuntos del tablero y formar nuevos conjuntos usando también la mano). También la opción de pasar.

La cantidad de opciones generadas está **limitada** y depende del **nivel** del bot: niveles bajos ven menos opciones (se les corta la lista antes), así que tienen menos donde elegir y suelen jugar peor.

### Paso 2 — Filtrar legales

Cada opción se **valida** con las reglas del juego (fichas en la mano (rack), melds (conjuntos) válidos, apertura correcta, etc.). Las que no pasan se descartan. Si no queda ninguna legal, el bot devuelve “pasar” como única jugada permitida.

### Paso 3 — Puntuación heurística

A cada opción que quedó se le asigna un **número (score)** con una función fija que tiene en cuenta, por ejemplo:

- Puntos jugados (más es mejor).
- Número de fichas usadas (más es mejor, acerca a vaciar la mano).
- Puntos que quedan en la mano (menos es mejor).
- Bonus si la jugada deja la mano vacía (ganar).
- Pequeñas penalizaciones (p. ej. usar comodines en jugadas que no son apertura).

Esta función **no usa información de los rivales**; solo la mano del bot y lo que se juega. Es puramente “qué tan buena es esta jugada para mí”.

### Paso 4 — Búsqueda (solo nivel ≥ 3)

Para niveles 3 en adelante, y si hay más de una opción, el bot **simula** qué pasaría si juega cada una de las mejores opciones (limitado por tiempo y por número de ramas):

- Simula la jugada en una **copia** del estado.
- En esa copia, alterna turnos entre el bot y los rivales (los rivales también se simulan con el mismo bot).
- Cada “estado futuro” se **evalúa** con otra función que compara: puntos en mi mano (menos es mejor), puntos en mano (rack) de rivales (más es peor), si ya abrí, cuántos melds (conjuntos) hay en el tablero, etc.
- En **modo fairplay** (juego limpio: el bot no ve las fichas de los rivales) en esa evaluación solo se usa el **número de fichas** de cada rival (no qué fichas son). Eso se guarda en el estado como `opponent_rack_counts` (cantidad de fichas por rival).
- El resultado de esta simulación (un valor numérico por opción) se **combina** con el score heurístico del paso 3 (por ejemplo, score + 0.65 × valor_futuro). Así las opciones se **reordenan** según “jugada buena ahora y buena a futuro”.

La búsqueda está **acotada**: hay un límite de tiempo por turno, un máximo de opciones exploradas por nivel (beam) y una profundidad máxima. No es un minimax completo; es un “minimax recortado” con evaluación heurística en las hojas (no hay red neuronal que evalúe).

### Paso 5 — Selección final

El bot **no elige siempre la opción con mejor score**. Se introduce:

- **Ruido:** Con cierta probabilidad (mayor en niveles bajos) elige una jugada de la mitad peor de la lista (“blunder”).
- **Temperatura:** Entre las opciones restantes se hace un **muestreo** según los scores (temperatura alta = más aleatorio, temperatura baja = más determinista). Así el mismo estado puede dar jugadas distintas en partidas distintas, y los niveles bajos son más erráticos.

El resultado de todo esto es **una sola jugada** (move; objeto `Move`), que la API convierte a JSON y devuelve al consumidor.

---

## 2.4 Fairplay frente a simulación

- **Fairplay (producción):** El bot solo recibe tablero, tamaño de la bolsa, **sus fichas** y el **número de fichas** de cada rival. No ve las fichas concretas de los otros jugadores. Es el modo pensado para partidas con jugadores reales.
- **Simulación:** El bot recibe el estado completo (incluidas las manos de todos). Sirve para tests o para partidas solo entre bots donde quieres que el bot “vea todo” (por ejemplo en el motor de simulación incluido en el paquete).

La API HTTP que usa Spring Boot trabaja **siempre en modo fairplay** (juego limpio): tú envías solo lo que quieres que el bot use (tablero, `pool_count` (bolsa), `my_tiles` (mis fichas), opcionalmente `opponent_rack_counts` (fichas por rival)), y el servidor no tiene acceso a las manos de los rivales.

---

## 2.5 Resumen técnico del “modelo”

- **Tipo:** Agente simbólico (reglas + heurísticas + búsqueda), **no** modelo de ML.
- **Entrada:** Estado (tablero, bolsa (pool), mano del bot (rack); en fairplay (juego limpio), conteos de rivales).
- **Proceso:** Generar candidatos → filtrar legales → puntuar con heurística → (opcional) re-puntuar con minimax acotado (beam + tiempo + profundidad) → seleccionar con ruido y temperatura.
- **Salida:** Una jugada (move): `pass` (pasar), `play_melds` (jugar conjuntos), `extend_meld` (extender conjunto), `replace_board` (reorganizar tablero), lista para aplicar en el motor del consumidor.

---

# 3. Estructura del paquete

> Descripción de los ficheros del paquete `rummiplus` y del servidor, para quien quiera leer o modificar el código.

---

## 3.1 Árbol y responsabilidades

```
IA_RummiPlus/
├── rummiplus/           # Paquete principal
│   ├── core.py          # Datos: Tile (ficha), Meld (conjunto), Board (tablero), GameState, Move (jugada), mazo
│   ├── rules.py         # Reglas: validar melds (conjuntos), generar candidatos, apertura
│   ├── move_logic.py    # Validar jugada, clonar estado, aplicar jugada in-place
│   ├── ai.py            # Bot: generación, heurísticas, minimax, selección
│   ├── api.py           # API pública: BotFacade, fairplay, JSON ↔ estado
│   ├── engine.py        # Motor de simulación (partidas entre bots)
│   └── server.py        # Servidor HTTP (POST /api/bot/move, GET /api/health)
├── scripts/             # Pruebas del modelo y la APU (opcional)
└── web_ui/              # Demo con interfaz web (opcional)
```

---

## 3.2 Ficheros del paquete (detalle)

### `core.py`

**Qué hace:** Define todo el **modelo de datos** del juego.

- **Tile (ficha):** Una ficha (valor, color, si es comodín, `uid`). Métodos `points()` y `short()` para serialización.
- **tile_from_short:** Parsea strings Palo+Número (`"B02"`, `"K12"`) o `"J*"` a `Tile` (usado por la API al recibir JSON).
- **Meld (conjunto):** Lista de `Tile` que forman un conjunto válido (grupo o escalera).
- **Board (tablero):** Lista de `Meld` (el tablero).
- **PlayerState:** Identificador de jugador, lista de fichas en la mano (**rack**), si ya abrió (opened).
- **GameState:** Tablero, lista de jugadores, bolsa (**pool**), índice del jugador actual, número de turno. Opcionalmente `opponent_rack_counts` (fichas por rival) para modo fairplay (juego limpio).
- **MoveType / Move (jugada):** Tipos de jugada (pass (pasar), play_melds (jugar conjuntos), extend_meld (extender conjunto), replace_board (reorganizar tablero)) y la jugada concreta con sus datos.
- **build_classic_deck:** Construye el mazo estándar (2×52 fichas numéricas + 2 comodines) con `uid` únicos.

**Quién lo usa:** Todo el resto del paquete (rules, move_logic, ai, api, engine, server).

---

### `rules.py`

**Qué hace:** Implementa las **reglas de Rummikub** a nivel de melds (conjuntos) y generación de candidatos.

- **is_valid_meld / is_valid_set / is_valid_run:** Comprueban si una lista de fichas forma un grupo válido (mismo valor, colores distintos) o una escalera válida (mismo color, valores consecutivos; comodines cubren huecos).
- **generate_meld_candidates:** A partir de un **rack** (mano), genera todos los melds (conjuntos) válidos de tamaño 3 hasta un máximo (p. ej. 5).
- **find_opening_combos:** Dado un rack y mínimo de puntos (30), encuentra combinaciones de melds **disjuntos** que sumen al menos ese mínimo (backtracking).
- **extend_meld_with_tile:** Comprueba si un meld (conjunto) del tablero puede extenderse con una ficha (añadir al grupo o a un extremo de la escalera) y devuelve el nuevo meld o `None`.
- **rack_without_tiles:** Utilidad para restar de un rack (mano) las fichas usadas en una jugada.

**Quién lo usa:** `move_logic` (validación), `ai` (generación de opciones).

---

### `move_logic.py`

**Qué hace:** Conecta **reglas** con **estado**: valida jugadas y aplica jugadas **modificando el estado en sitio**.

- **opening_points:** Puntos que cuentan para la apertura (solo fichas no comodín).
- **clone_state:** Copia profunda de un `GameState` (para que el bot pueda simular sin alterar el estado real).
- **validate_move:** Comprueba si una `Move` (jugada) es legal (fichas en la mano (rack), melds (conjuntos) válidos, apertura ≥30 si aplica, extensión/reorganización coherente). Devuelve `(True, detalle)` o `(False, mensaje)`.
- **apply_move_inplace:** Si la jugada es legal, la ejecuta sobre el `GameState`: quita fichas del rack (mano), actualiza el tablero, y en caso de pass (pasar) puede robar de la bolsa (pool).

**Quién lo usa:** `ai` (para simular y para validar opciones), `engine` (para aplicar la jugada elegida en la partida), `api` (clone_state para fairplay y para state_from_bot_request).

---

### `ai.py`

**Qué hace:** Contiene la **lógica del bot**: generación de opciones, puntuación, búsqueda y selección.

- **BotConfig:** Parámetros (nivel, aleatoriedad, seed, límites de opciones, tiempo y profundidad de búsqueda). `skill()` devuelve un valor 0–1 según el nivel.
- **StrategicBot:** La clase principal. Recibe un `GameState` y el índice del jugador y devuelve un `Move` (jugada).
  - **choose_move:** Orquesta el flujo: generar opciones → filtrar legales → (si nivel ≥ 3) re-puntuar con búsqueda → seleccionar una opción con ruido/temperatura.
  - **_generate_options:** Genera aperturas, melds (conjuntos) nuevos, extensiones, reorganizaciones y pass (pasar); cada una con un score heurístico.
  - **_filter_legal:** Descarta opciones que no pasen `validate_move`.
  - **_score_with_search:** Para las mejores opciones, simula la jugada y llama a minimax con límite de tiempo y beam; combina score actual con valor futuro.
  - **_minimax_value:** Minimax: maximiza si es el turno del bot, minimiza si es turno de rival; usa caché por firma del estado; en hojas usa _evaluate_state.
  - **_evaluate_state:** Puntuación de un estado (menos puntos en mi mano (rack) y más en mano rival = peor; bonus por abrir y por tablero). En fairplay (juego limpio) usa solo `opponent_rack_counts` (fichas por rival).
  - **_evaluate_used_tiles:** Puntuación de una jugada concreta (puntos jugados, fichas usadas, restantes, bonus por vaciar mano).
  - **_select_option:** Introduce blunders y muestreo por temperatura sobre los scores.

**Quién lo usa:** `api` (BotFacade delega en StrategicBot), y el motor de simulación usa el bot a través de la API.

---

### `api.py`

**Qué hace:** Expone la **API pública** del paquete para quien integra el bot (en Python o vía JSON).

- **ViewMode:** Enum FAIRPLAY (juego limpio) / SIMULATION.
- **BotConfig:** Reexporta/amplía la config del bot (usada por BotFacade).
- **make_fairplay_view:** Dado un estado completo y un índice de jugador, devuelve un estado donde ese jugador ve solo su mano (rack) y el tablero; los demás racks (manos) se vacían y se rellenan `opponent_rack_counts` (fichas por rival).
- **move_to_dict:** Convierte un `Move` (jugada) a un diccionario listo para JSON (para enviar por HTTP).
- **state_from_bot_request:** Recibe el payload JSON que envía el backend (board (tablero), pool_count (bolsa), my_tiles (mis fichas), etc.) y construye un `GameState` con el que el bot puede decidir (ya en forma fairplay (juego limpio)).
- **BotFacade:** Fachada que recibe `BotConfig` y expone `decide_turn(state, player_idx)` y `decide_turn_fairplay(state, player_idx)` (este último construye la vista fairplay (juego limpio) y llama a decide_turn).

**Quién lo usa:** `engine` (simulación), `server` (state_from_bot_request, BotFacade, move_to_dict), y cualquier código que quiera usar el bot desde Python.

---

### `engine.py`

**Qué hace:** **Motor de simulación** de partidas entre bots (sin interfaz).

- **SimulationConfig:** Número y configuración de bots, seed, máximo de turnos, tamaño de mano (rack) inicial, modo (fairplay (juego limpio) o simulación).
- **_init_state:** Crea el mazo, baraja, reparte fichas a cada bot y devuelve el `GameState` inicial y la lista de `BotFacade`.
- **run_simulation:** Bucle de turnos: en cada uno el bot correspondiente elige (fairplay (juego limpio) o simulación según config), se aplica la jugada (move) con `apply_move_inplace`; si es ilegal se penaliza con pass (pasar)+robo. Al final devuelve ganador, número de turnos, logs y puntos por jugador.

**Quién lo usa:** Quien quiera ejecutar partidas automáticas (p. ej. tests o estadísticas). La API HTTP no usa el engine; el engine usa la API (BotFacade) para que cada bot decida.

---

### `server.py`

**Qué hace:** **Servidor HTTP** mínimo para exponer el bot a backends externos.

- **BotAPIHandler:** Manejador de peticiones. Atiende GET `/api/health` (responde `{"ok": true}`) y POST `/api/bot/move`: lee el body JSON, llama a `state_from_bot_request`, crea un `BotFacade` con level/randomness/seed del payload, obtiene la jugada con `decide_turn(state, 0)` y devuelve `move_to_dict(move)` y `move_short`.
- **main:** Crea un `ThreadingHTTPServer` que atiende cada petición en un hilo (varias partidas pueden pedir jugadas a la vez).

**Quién lo usa:** El backend (Spring Boot) arranca este módulo con `python -m rummiplus.server` y hace POST a `/api/bot/move` cuando es el turno de un bot.

---

## 3.3 Dónde está cada cosa

| Necesito… | Fichero |
|-----------|--------|
| Definición de Tile (ficha), GameState, Move (jugada) | `core.py` |
| Validar si un meld (conjunto) es válido, generar melds desde un rack (mano) | `rules.py` |
| Validar una jugada y aplicarla al estado | `move_logic.py` |
| Lógica del bot (generar, puntuar, buscar, elegir) | `ai.py` |
| Crear bot, vista fairplay (juego limpio), estado desde JSON, Move (jugada) a dict | `api.py` |
| Simular partidas entre bots | `engine.py` |
| Servidor HTTP para Spring Boot | `server.py` |

---

*RummiPlus — Bot de Rummikub clásico para backends Spring Boot.*
