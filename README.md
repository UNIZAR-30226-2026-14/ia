# RummiPlus — Bot de Rummikub para backends

Bot de Rummikub clásico expuesto por HTTP para integrar en **Spring Boot**. El backend gestiona la partida (web, cliente de escritorio, etc.); en el turno del bot llama a esta API y recibe la jugada en JSON.

**Atención: El presente README y la mayoría de documentación de este repositorio ha sido creado mediante uso de LLM.**

---

## <a id="sec-indice"></a>Índice
### Parte 1 — Uso del servicio (consumidores de la API)
1. [1. Uso del servicio (consumidores de la API)](#sec-1)
   - [1.1 Qué es el bot y cómo se usa](#sec-1-1)
   - [1.2 Arrancar el servicio](#sec-1-2)
   - [1.3 Probar la API con el script (probar_api.sh)](#sec-1-3)
   - [1.4 Endpoint de la jugada](#sec-1-4)
   - [1.5 Ejemplo completo de petición HTTP (curl)](#sec-1-5)
   - [1.6 Cuerpo de la petición (request)](#sec-1-6)
     - [Campos obligatorios](#sec-1-6-campos-obligatorios)
     - [Campos opcionales](#sec-1-6-campos-opcionales)
     - [Formato de cada ficha (`string`)](#sec-1-6-formato-ficha)
   - [1.7 Respuesta (response)](#sec-1-7)
     - [Estructura de `move`](#sec-1-7-estructura-move)
   - [1.8 Ejemplo completo: Spring Boot (Java)](#sec-1-8)
     - [1. Dependencia (Maven)](#sec-1-8-maven)
     - [2. DTOs de request y response](#sec-1-8-dtos)
     - [3. Cliente HTTP y uso en el turno del bot](#sec-1-8-cliente-http)
     - [4. Construir el request desde tu estado de partida](#sec-1-8-construir-request)
     - [5. Aplicar la jugada en tu motor](#sec-1-8-aplicar-jugada)
   - [1.9 Resumen para el consumidor de la API](#sec-1-9)
   - [1.10 Modo arcade (opcional)](#sec-1-10)
     - [1.10.1 Formato de fichas arcade](#sec-1-10-1)
     - [1.10.2 Campos arcade en el request (opcionales)](#sec-1-10-2)
     - [1.10.3 `move_type: "use_item"` y campo `item_use`](#sec-1-10-3)
     - [1.10.4 Catálogo de objetos (códigos `ItemType`)](#sec-1-10-4)
     - [1.10.5 Restricciones que aplica el propio bot](#sec-1-10-5)
     - [1.10.6 Compatibilidad con Spring Boot](#sec-1-10-6)
     - [1.10.7 Tienda arcade (integrada en `arcade`)](#sec-1-10-7)
     - [1.10.8 Flujo del turno arcade (fases `use_item` + jugada final)](#sec-1-10-8)
     - [1.10.9 Responsabilidades en modo arcade (bot vs backend)](#sec-1-10-9)
       - [1.10.9.1 Tienda](#sec-1-10-9-1)
       - [1.10.9.2 Eventos especiales del turno](#sec-1-10-9-2)
       - [1.10.9.3 Objetos: reglas generales y flujo del turno](#sec-1-10-9-3)
       - [1.10.9.4 Objetos: tipo por tipo](#sec-1-10-9-4)
       - [1.10.9.5 Fichas especiales (habilidades `A`, `D`, `N`)](#sec-1-10-9-5)
       - [1.10.9.6 Resumen operativo](#sec-1-10-9-6)
### Parte 2 — Qué es este código y cómo funciona el modelo
2. [2. Qué es este código y cómo funciona el modelo](#sec-2)
   - [2.1 Qué es RummiPlus](#sec-2-1)
   - [2.2 Tipo de “IA”: no es aprendizaje automático](#sec-2-2)
   - [2.3 Cómo obtiene una respuesta el bot (paso a paso)](#sec-2-3)
     - [Paso 1 — Generar opciones](#sec-2-3-paso-1)
     - [Paso 2 — Filtrar legales](#sec-2-3-paso-2)
     - [Paso 3 — Puntuación heurística](#sec-2-3-paso-3)
     - [Paso 4 — Búsqueda (solo nivel ≥ 3)](#sec-2-3-paso-4)
     - [Paso 5 — Selección final](#sec-2-3-paso-5)
   - [2.4 Fairplay frente a simulación](#sec-2-4)
   - [2.5 Resumen técnico del “modelo”](#sec-2-5)
   - [2.6 Soporte de modo arcade](#sec-2-6)
     - [2.6.1 Qué hace el bot cuando recibe un `ArcadeState`](#sec-2-6-1)
     - [2.6.2 Qué sigue sin hacer el bot](#sec-2-6-2)
     - [2.6.3 Impacto en la búsqueda (minimax)](#sec-2-6-3)
     - [2.6.4 Decisión de compra en tienda (`arcade.shop` + `move.shop_choice`)](#sec-2-6-4)
### Parte 3 — Estructura del paquete
3. [3. Estructura del paquete](#sec-3)
   - [3.1 Árbol y responsabilidades](#sec-3-1)
   - [3.2 Ficheros del paquete (detalle)](#sec-3-2)
     - [`core.py`](#sec-3-2-core)
     - [`rules.py`](#sec-3-2-rules)
     - [`move_logic.py`](#sec-3-2-move-logic)
     - [`ai.py`](#sec-3-2-ai)
     - [`api.py`](#sec-3-2-api)
     - [`engine.py`](#sec-3-2-engine)
     - [`server.py`](#sec-3-2-server)
   - [3.3 Dónde está cada cosa](#sec-3-3)
   - [3.4 Cambios para modo arcade](#sec-3-4)

---

# <a id="sec-1"></a>1. Uso del servicio (consumidores de la API)

> **Importante:** Esta sección es la que debe seguir el consumidor de la API (Spring Boot u otro backend HTTP). Aquí se explica **qué es el bot y cómo “se crea”**, **cómo arrancar y usar el servicio**, **cómo hacer las peticiones HTTP con detalle** y **cómo aplicar la jugada** en tu motor.

---

## <a id="sec-1-1"></a>1.1 Qué es el bot y cómo se usa (no hace falta “crearlo”)

El **bot** es el programa que, dado el estado actual del juego (tablero, bolsa, mano del jugador), decide la jugada (pasar, jugar melds (conjuntos de fichas en mesa), extender, reorganizar). Ese programa vive **dentro del servicio HTTP** que arrancas con `python -m rummiplus.server`.  
**No tienes que crear ni instanciar el bot en tu aplicación.** Desde Spring Boot (o cualquier cliente) solo haces lo siguiente:

1. **Arrancar el servicio** en Python (una sola vez, en la misma máquina o en un servidor accesible).
2. **Cuando sea el turno del bot:** construir un JSON con el estado (tablero, `pool_count` (fichas en bolsa), `my_tiles` (mis fichas), etc.) y hacer **POST** a `/api/bot/move`.
3. **Recibir la respuesta** en JSON (`move` (jugada) + `move_short`) y **aplicar esa jugada** en tu motor de juego (quitar fichas del rack (mano), actualizar tablero, pasar turno, etc.).

Cada petición es **independiente**: el servidor no guarda estado entre llamadas. Tu backend es el dueño de la partida; el servicio solo responde a “con este estado, ¿qué jugada hace el bot?”.

---

## <a id="sec-1-2"></a>1.2 Arrancar el servicio

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

## <a id="sec-1-3"></a>1.3 Probar la API con el script (probar_api.sh)

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

## <a id="sec-1-4"></a>1.4 Endpoint de la jugada

| Método | URL | Descripción |
|--------|-----|-------------|
| **POST** | `http://<host>:<port>/api/bot/move` | Envías estado del juego; recibes la jugada del bot. |
| GET | `http://<host>:<port>/api/health` | Comprueba que el servicio está vivo. |

**Cabecera obligatoria:** `Content-Type: application/json`

---

## <a id="sec-1-5"></a>1.5 Ejemplo completo de petición HTTP (curl)

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

## <a id="sec-1-6"></a>1.6 Cuerpo de la petición (request)

El body debe ser un JSON con al menos los campos siguientes. El bot **solo usa** tablero, número de fichas en la bolsa y **sus propias fichas** (modo fairplay (juego limpio: no ve las fichas de los rivales)); el resto son opcionales para mejorar la decisión.

### <a id="sec-1-6-campos-obligatorios"></a>Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `board` | `array` de `array` de `string` | Tablero actual. Cada elemento es un **meld** (conjunto de fichas en mesa): lista de fichas (Palo+Número). Ejemplo: `[["B02","B03","B04"], ["R01","O01","K01"]]`. |
| `pool_count` | `number` | Número de fichas que quedan en la **bolsa** (pool). |
| `my_tiles` | `array` de `string` | Fichas del jugador bot (su **mano**, rack). Mismo formato que las fichas del tablero. |

### <a id="sec-1-6-campos-opcionales"></a>Campos opcionales

| Campo | Tipo | Por defecto | Descripción |
|-------|------|-------------|-------------|
| `opponent_rack_counts` | `array` de `number` | `[]` | Número de fichas en la **mano** (rack) de cada rival. Ej: `[14, 12]` para dos rivales con 14 y 12 fichas. Mejora la calidad de la decisión. |
| `opened` | `boolean` | `true` si `board` tiene melds | Si el bot **ya ha abierto** (opened: ha jugado al menos 30 puntos en una jugada anterior). |
| `level` | `number` 1–10 | `5` | Dificultad del bot (1 más fácil, 10 más fuerte). |
| `randomness` | `number` 0–1 | `0.25` | Aleatoriedad en la elección (0 determinista, 1 muy variable). |
| `seed` | `number` o `null` | `null` | Si pones un número, las decisiones son reproducibles para ese seed. |
| `turn_number` | `number` | `1` | Solo informativo. |

### <a id="sec-1-6-formato-ficha"></a>Formato de cada ficha (`string`)

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

## <a id="sec-1-7"></a>1.7 Respuesta (response)

El servidor devuelve **siempre** un JSON con dos claves:

| Clave | Tipo | Uso |
|-------|------|-----|
| `move` | objeto | Jugada estructurada para **aplicar en tu motor**. |
| `move_short` | string | Texto legible para logs o UI (ej. `"PASAR"`, `"[B05 B06 B07] + [B09 B10 B11]"`). |

### <a id="sec-1-7-estructura-move"></a>Estructura de `move`

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

## <a id="sec-1-8"></a>1.8 Ejemplo completo: Spring Boot (Java)

El backend en Spring Boot es quien gestiona la partida (tanto si los clientes son web como escritorio). Cuando es el turno de un bot, Spring Boot construye el JSON con el estado actual, hace POST a la API de RummiPlus, recibe la jugada y la aplica en su modelo de juego. A continuación se detalla cada pieza.

### <a id="sec-1-8-maven"></a>1. Dependencia (Maven)

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

### <a id="sec-1-8-dtos"></a>2. DTOs de request y response

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

### <a id="sec-1-8-cliente-http"></a>3. Cliente HTTP y uso en el turno del bot

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

### <a id="sec-1-8-construir-request"></a>4. Construir el request desde tu estado de partida

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

### <a id="sec-1-8-aplicar-jugada"></a>5. Aplicar la jugada en tu motor

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

## <a id="sec-1-9"></a>1.9 Resumen para el consumidor de la API

- Arrancar el servicio: `python -m rummiplus.server --port 8765`
- Probar que responde: `bash scripts/probar_api.sh` (con el servidor levantado).
- Desde Spring Boot: **POST** a `/api/bot/move` con JSON: `board` (tablero), `pool_count` (bolsa), `my_tiles` (mis fichas) (y opcionalmente `opponent_rack_counts` (fichas por rival), `opened` (ha abierto), `level`, etc.).
- Respuesta: `move` (jugada: objeto con `move_type` y campos según tipo) y `move_short` (texto legible).
- En tu backend: según `move_type`, aplicar pass (pasar), play_melds (jugar conjuntos), extend_meld (extender conjunto) o replace_board (reorganizar tablero) y pasar al siguiente turno.

---

## <a id="sec-1-10"></a>1.10 Modo arcade (opcional)

> Esta sub-sección describe **únicamente el modo arcade**. Las secciones 1.1–1.9 siguen siendo válidas para el modo normal; el modo arcade añade campos **opcionales** al request y un campo opcional al response. Si no envías el bloque `arcade`, el servicio se comporta exactamente como en modo normal.

El modo arcade amplía el juego con:

- **Eventos de ronda** que imponen restricciones al turno (color bloqueado, techo de cristal, tiempo reducido/ampliado, etc.). El backend decide y aplica los eventos; el bot solo **respeta** las restricciones que le pases.
- **Objetos** (hasta 3 por jugador) que producen buffs/debuffs. El backend es el autoritario en su ejecución; el bot puede **sugerir** qué objeto usar cuando le paséis su inventario.
- **Fichas especiales**: doradas (×2 puntos), negativas (puntos con signo opuesto) y arcoíris (comodín de color con valor fijo). Se envían como strings con sufijos.

### <a id="sec-1-10-1"></a>1.10.1 Formato de fichas arcade

Las fichas arcade mantienen el formato Palo+Número y añaden **habilidades como sufijos** (una letra por habilidad). Palos normales (`K`, `B`, `O`, `R`) y comodín (`J*`) no cambian.

| Componente | Tipo | Código interno | Ejemplo |
|------------|------|----------------|---------|
| Negro | Palo / Color | `K` | `K12` → ficha negra 12 |
| Azul | Palo / Color | `B` | `B07` → ficha azul 7 |
| Naranja | Palo / Color | `O` | `O03` → ficha naranja 3 |
| Rojo | Palo / Color | `R` | `R01` → ficha roja 1 |
| Número | Valor (2 dígitos) | `01`–`13` | `K12`, `O03`, `B07` |
| Dorado | Habilidad (sufijo) | `D` | `O03D` = naranja 3 dorado |
| Arcoíris | Habilidad (sufijo) | `A` | `B07A` = azul 7 arcoíris |
| Negativo | Habilidad (sufijo) | `N` | `R10N` = rojo 10 negativo |
| Comodín | Ficha especial | `J*` | `J*` = comodín (no sigue Palo+Número) |

**Efecto de cada habilidad:**

- `D` **Dorado**: los puntos se **duplican** al puntuar (5 → 10). Validación de meld sin cambios.
- `N` **Negativo**: los puntos se **niegan** (9 → -9). Afecta apertura, puntuación de rack y techo de cristal.
- `A` **Arcoíris**: el color base es solo cosmético. En un grupo ocupa un slot de color libre; en una escalera toma el color dominante del resto de naturales no arcoíris. El valor numérico se mantiene. **No le afecta el color bloqueado** (ver 1.10.5).

**Combinación de habilidades:** se pueden combinar en la misma ficha. Al **serializar**, el bot usa orden alfabético `A, D, N` (ej. `"B07AD"`, `"R05AN"`, `"K12DN"`, `"B05ADN"`). Al **parsear**, el bot acepta cualquier orden (`"B07DA"` y `"B07AD"` son equivalentes). Combinación de puntos: primero se niega (`N`), luego se duplica (`D`); ej. `R09DN` → (9 → -9 → -18).

### <a id="sec-1-10-2"></a>1.10.2 Campos arcade en el request (opcionales)

Añade al JSON de POST `/api/bot/move` un objeto `arcade` con los campos que apliquen en ese turno. **Todos los campos son opcionales**; si no pasas `arcade` el bot decide en modo normal.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `enabled` | `boolean` | `true` si el modo arcade está activo (por defecto `true` si existe el bloque). |
| `blocked_color` | `string` | Color bloqueado este turno por evento: `"K"`, `"B"`, `"O"` o `"R"` (también acepta `"black"`, `"blue"`, `"orange"`, `"red"`). El bot nunca jugará fichas de ese color. |
| `min_play_points` | `number` | Techo de cristal aplicado al bot: la próxima jugada debe sumar al menos este valor en puntos (se aplica aparte del mínimo de apertura). |
| `my_items` | `array` de `string` | Inventario de objetos del bot (códigos de `ItemType`, ver tabla 1.10.4). Máx 3. |
| `opponent_item_counts` | `array` de `number` | Número de objetos por jugador (mismo orden que `opponent_rack_counts`: posición `i` = jugador `i`). La posición del propio bot se ignora. |
| `time_limit_s` | `number` | Tiempo máximo de turno en segundos (informativo; el bot lo tendrá en cuenta para acotar su búsqueda). |
| `shop_discount` | `number` | Descuento de tienda (0.5 = 50%). Informativo para el bot. |
| `draw_at_turn_start` | `boolean` | Indica si este turno el jugador ha robado una ficha al empezar (informativo; el backend ya la ha repartido). |
| `items_used_this_turn` | `array` de `string` | Objetos (códigos `ItemType`) ya **usados o denegados** por el bot en este turno a través de fases previas de `use_item`. El backend añade una entrada tras ejecutar o rechazar cada `use_item` y reinicia la lista al comenzar un nuevo turno. El bot no propondrá de nuevo ninguno de estos. |
| `guardian_angel_active` | `boolean` | `true` si el jugador tiene un escudo de Ángel activo (un Ángel adquirido antes, ya "convertido" por el backend). Ver 1.10.4 y 1.10.9.4. Se usa junto a `my_items` para decidir compras e ignorar Ángeles redundantes. Por defecto `false`. |

**Ejemplo de request en modo arcade:**

```json
{
  "board": [["B02","B03","B04"]],
  "pool_count": 50,
  "my_tiles": ["R05","R06","R07","K10","K10D","B09A","B11N","J*","O05","O07","O08","O09","R13","R13D"],
  "opponent_rack_counts": [14, 12],
  "opened": true,
  "level": 7,
  "arcade": {
    "enabled": true,
    "blocked_color": "B",
    "min_play_points": 30,
    "my_items": ["PLUS_FOUR","MIDAS_TOUCH","GUARDIAN_ANGEL"],
    "opponent_item_counts": [0, 2, 1],
    "time_limit_s": 60
  }
}
```

### <a id="sec-1-10-3"></a>1.10.3 `move_type: "use_item"` y campo `item_use`

Cuando el bot decide usar un objeto, **no devuelve una jugada**. En su lugar responde con un move de tipo `use_item` cuyo único contenido relevante es `item_use`:

```json
{
  "move": {
    "move_type": "use_item",
    "reason": "usar MIDAS_TOUCH antes de jugar",
    "item_use": {
      "item": "MIDAS_TOUCH",
      "reason": "mano grande: subir puntuación con fichas doradas"
    }
  },
  "move_short": "usar MIDAS_TOUCH"
}
```

Semántica:

- `move_type: "use_item"` **no cierra el turno**. Es una señal al backend: *"ejecuta este objeto y vuelve a llamarme"*.
- Con `use_item`, la respuesta **nunca** incluye `new_melds`, `extension_tiles`, `new_board` ni `shop_choice`. Solo `move_type`, `reason` e `item_use`.
- Los tipos `pass`, `play_melds`, `extend_meld` y `replace_board` **sí cierran el turno** y nunca llevan `item_use`.

Estructura de `item_use`:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `item` | `string` | Código del objeto (ver 1.10.4). |
| `target_player_idx` | `number?` | Índice del jugador objetivo (mismo esquema que `opponent_rack_counts`). Ausente si el objeto es autoaplicado o no requiere objetivo. |
| `reason` | `string` | Texto informativo para logs/UI. |
| `params` | `object?` | Parámetros específicos del objeto (ej. `{"color": "B", "value_range": [1,13]}` para Bola de cristal). |

**Qué debe hacer el backend**: al recibir `use_item`, el backend ejecuta (o deniega) el efecto y vuelve a llamar a `/api/bot/move` añadiendo el código del objeto a `arcade.items_used_this_turn` (ver 1.10.2 y 1.10.8). El bot nunca repetirá un objeto que aparezca en esa lista, lo que garantiza que el bucle termine.

Para el flujo completo (varios `use_item` encadenados, denegación, terminación), ver la sección **1.10.8 Flujo del turno arcade**.

### <a id="sec-1-10-4"></a>1.10.4 Catálogo de objetos (códigos `ItemType`)

| Código (`item`) | Objeto | Requiere objetivo | Notas |
|-----------------|--------|-------------------|-------|
| `GUARDIAN_ANGEL` | Ángel de la guarda | — | Escudo pasivo, **no acumulable** y **no activable**. Al adquirirlo entra en `my_items`; el backend lo "convierte" a escudo al inicio del siguiente turno del portador (retira del inventario y pone `guardian_angel_active=true`). Si ya había escudo activo, el Ángel permanece en `my_items` hasta que pueda convertirse. Cada escudo bloquea un único objeto ofensivo y se gasta. El bot nunca lo sugiere en `use_item`. |
| `CRYSTAL_BALL` | Bola de cristal | No | Ver fichas de un color o rango numérico de todos los jugadores. `params`: `{ "color": "B" }` o `{ "value_range": [1,7] }`. |
| `TRUTH_MAGNIFIER` | Lupa de la verdad | Sí | Ver fichas y objetos de un jugador. |
| `MIDAS_TOUCH` | Toque de Midas | No (auto) | Convierte 2–4 de tus fichas en doradas al azar. |
| `MINUS_POWER` | Poder del − | No (auto) | Convierte 2–4 de tus fichas de valor positivo en negativo. El bot **no lo sugiere** (perjudica al propio). |
| `RAINBOW_REFRACTION` | Refracción multicolor | No (auto) | Convierte 1–2 de tus fichas en arcoíris al azar. |
| `PLUS_FOUR` | +4 | Sí | Hace que un oponente robe 4 fichas. |
| `SWAP_ON_FAIL` | Trueque al fallo | Sí | Ver 3 fichas del oponente, elegir 1 y una tuya, intercambiarlas. |
| `WHITE_GLOVE` | Guante blanco | Sí | Robar un objeto a un oponente (requiere que tenga al menos uno). |
| `SMOKE_BOMB` | Bomba de humo | Sí | El jugador objetivo no ve las fichas del tablero durante su turno. |
| `CHILI_PEPPER` | Guindilla en el culo | Sí | Reduce a la mitad el tiempo del próximo turno de un jugador. |
| `RUM_ROCKS` | Ron con hielo / Dos copas de más | Sí | Invierte los controles del oponente un turno. |
| `GLASS_CEILING` | Techo de cristal | Sí | La próxima jugada del oponente debe sumar ≥30 puntos. |

### <a id="sec-1-10-5"></a>1.10.5 Restricciones que aplica el propio bot

- **Color bloqueado**: el bot nunca genera jugadas que añadan al tablero fichas del color bloqueado (incluye extensiones y reorganizaciones desde la mano). Las fichas con habilidad arcoíris (`A`) **no están afectadas** por el bloqueo aunque su color base coincida. Las fichas del tablero anterior se pueden mover en una reorganización.
- **Techo de cristal (`min_play_points`)**: el bot descarta cualquier opción cuya suma de puntos jugados (incluidos modificadores dorada/negativa) sea menor al umbral. Si no queda ninguna, devuelve `pass`.
- **Fichas especiales** en melds: se validan igual que las clásicas; arcoíris cuenta como color flexible (grupo) o color dominante (escalera) y su valor se mantiene.
- **No repetir objetos en el mismo turno**: el bot filtra cualquier `ItemType` que aparezca en `arcade.items_used_this_turn` antes de proponer un `use_item`. Esto garantiza que el bucle de fases del turno arcade (ver 1.10.8) termine en un número finito de llamadas.

### <a id="sec-1-10-6"></a>1.10.6 Compatibilidad con Spring Boot

El DTO existente (sección 1.8) sigue siendo válido. Para modo arcade añade:

```java
public record ArcadePayload(
    Boolean enabled,
    String blocked_color,
    Integer min_play_points,
    List<String> my_items,
    List<Integer> opponent_item_counts,
    Integer time_limit_s,
    Double shop_discount,
    Boolean draw_at_turn_start,
    ShopPayload shop,                    // opcional: tienda abierta este turno (ver 1.10.7)
    List<String> items_used_this_turn,   // objetos ya usados/denegados en este turno (ver 1.10.8)
    Boolean guardian_angel_active        // escudo de Ángel activo (ver 1.10.4)
) {}

// BotMoveRequest pasa a incluir opcionalmente:
@JsonInclude(JsonInclude.Include.NON_NULL)
public record BotMoveRequest(
    List<List<String>> board,
    int pool_count,
    List<String> my_tiles,
    List<Integer> opponent_rack_counts,
    Boolean opened,
    Integer level,
    Double randomness,
    Integer seed,
    ArcadePayload arcade   // opcional: null → modo normal
) {}

public record ItemUsePayload(
    String item,
    Integer target_player_idx,
    String reason,
    Map<String, Object> params
) {}

// MovePayload se amplía con:
@JsonInclude(JsonInclude.Include.NON_NULL)
public record MovePayload(
    String move_type,
    String reason,
    List<List<String>> new_melds,
    Integer extend_index,
    List<String> extension_tiles,
    List<List<String>> new_board,
    ItemUsePayload item_use,      // opcional: null si el bot no sugiere objeto
    ShopChoicePayload shop_choice // opcional: null si no había tienda abierta
) {}
```

### <a id="sec-1-10-7"></a>1.10.7 Tienda arcade (integrada en `arcade`)

En modo arcade, al empezar el turno de cada jugador el backend puede abrir una tienda con 2–3 ofertas aleatorias. La tienda **la gestiona siempre el backend**: compone el surtido, fija el precio (con el descuento del evento `shop_discount` si procede), aplica el límite de 3 objetos y cobra el saldo. Cuando el jugador es un bot, **la consulta se hace en el mismo `POST /api/bot/move`**: el backend envía la oferta dentro de `arcade.shop` y el bot devuelve su decisión en `move.shop_choice`. No hay endpoint separado.

Campo `arcade.shop` en el request (opcional):

| Campo | Tipo | Descripción |
|---|---|---|
| `offer` | `array` de `{ "item": string, "price": int }` | 1–N ofertas actuales. `item` es un código `ItemType` (ver 1.10.4); `price` es un entero ≥ 0 (ya con descuentos aplicados por el backend). |
| `balance` | `int` | Saldo del bot en la moneda de la tienda. Si no llega se asume 0 (el bot no podrá comprar nada). |

Si `arcade.shop` está ausente, el bot entiende que la tienda **no está abierta** este turno y no emitirá `shop_choice`.

Campo `move.shop_choice` en la respuesta (opcional):

| Campo | Tipo | Descripción |
|---|---|---|
| `buy` | `string` o `null` | Código `ItemType` del objeto elegido entre los ofrecidos. `null` si el bot prefiere no comprar. |
| `reason` | `string` | Texto breve en español con el motivo (útil para logs y UI). |

Solo aparece cuando el request trajo `arcade.shop.offer` no vacío. Si no, el backend simplemente no lo verá en la respuesta.

**Semántica importante:** la jugada devuelta (`move`) se calcula asumiendo el inventario **previo a la compra** (`arcade.my_items`). El bot decide jugada y compra en la misma respuesta, pero el objeto recién comprado **no se usa ese mismo turno**: el backend suma el objeto al inventario del jugador para futuros turnos. Esto evita circularidades y es coherente con cómo funciona en la vida del juego (primero juegas con lo que tienes; lo comprado queda disponible la próxima vuelta).

**Solo una compra por turno y solo al cerrar el turno.** `shop_choice` se emite **únicamente** junto a una jugada que cierra el turno (`pass`, `play_melds`, `extend_meld`, `replace_board`). Nunca se emite junto a un `move_type: "use_item"`. En la práctica, en un turno arcade con bucle de fases (ver 1.10.8), todas las respuestas intermedias son `use_item` sin `shop_choice`, y solo la última (la jugada) puede llevar `shop_choice`. El backend por tanto procesa la compra **una sola vez**: al recibir la respuesta que cierra el turno. Si `arcade.shop` viaja en peticiones intermedias, el bot lo ignora de cara a emitir compra en esa fase (solo lo tiene en cuenta en la respuesta final).

Ejemplo de request arcade con tienda abierta:

```json
{
  "board": [["B05","B06","B07"]],
  "pool_count": 70,
  "my_tiles": ["R05","O05","K05","K10","B12","R13"],
  "opponent_rack_counts": [6, 12],
  "level": 7, "randomness": 0.2,
  "arcade": {
    "enabled": true,
    "my_items": ["CHILI_PEPPER"],
    "shop": {
      "offer": [
        { "item": "MIDAS_TOUCH",    "price": 50 },
        { "item": "PLUS_FOUR",      "price": 80 },
        { "item": "GUARDIAN_ANGEL", "price": 30 }
      ],
      "balance": 120
    }
  }
}
```

Respuesta posible:

```json
{
  "move": {
    "move_type": "play_melds",
    "reason": "nuevo meld",
    "new_melds": [["R05","O05","K05"]],
    "shop_choice": { "buy": "PLUS_FOUR", "reason": "rival cerca de ganar: +4 es muy útil" }
  },
  "move_short": "[R05 O05 K05]"
}
```

Criterios de decisión del bot (resumen; ver 2.6.4 para detalles):

- Inventario lleno (`my_items.length >= 3`) ⇒ `buy: null`.
- Ninguna oferta asequible (`price > balance`) ⇒ `buy: null`.
- `MINUS_POWER` siempre se descarta (se perjudicaría).
- Debuffs (`PLUS_FOUR`, `GLASS_CEILING`, `CHILI_PEPPER`, …) suben cuando hay un rival con ≤ 5 fichas.
- Buffs (`MIDAS_TOUCH`, `RAINBOW_REFRACTION`) suben con mano grande (≥ 12) o sin abrir.
- Información (`TRUTH_MAGNIFIER`, `CRYSTAL_BALL`) solo en `level ≥ 7`.
- Se elige la mejor **utilidad / precio** entre las viables, con umbral mínimo para evitar compras pobres.

Compatibilidad con Spring Boot:

```java
public record ShopOfferPayload(String item, int price) {}

public record ShopPayload(
    List<ShopOfferPayload> offer,
    int balance
) {}

// ArcadePayload se amplía con shop (opcional):
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ArcadePayload(
    Boolean enabled,
    String blocked_color,
    Integer min_play_points,
    List<String> my_items,
    List<Integer> opponent_item_counts,
    Integer time_limit_s,
    Double shop_discount,
    Boolean draw_at_turn_start,
    ShopPayload shop
) {}

public record ShopChoicePayload(String buy, String reason) {}

// MovePayload se amplía con shop_choice (opcional):
@JsonInclude(JsonInclude.Include.NON_NULL)
public record MovePayload(
    String move_type,
    String reason,
    List<List<String>> new_melds,
    Integer extend_index,
    List<String> extension_tiles,
    List<List<String>> new_board,
    ItemUsePayload item_use,
    ShopChoicePayload shop_choice
) {}
```

### <a id="sec-1-10-8"></a>1.10.8 Flujo del turno arcade (fases `use_item` + jugada final)

El turno de un bot en modo arcade ya no es una única petición, sino un **bucle de fases** que el backend orquesta:

1. **Inicio de turno**: el backend abre el turno del bot, resetea `arcade.items_used_this_turn` a `[]` y hace el primer `POST /api/bot/move`.
2. **Respuesta**: el bot devuelve uno de estos dos tipos de `move`:
   - **`use_item`** → el bot quiere usar un objeto antes de jugar. El backend:
     1. Ejecuta el efecto (o lo deniega por la razón que sea).
     2. Añade el código del objeto a `items_used_this_turn`.
     3. Si el objeto modifica el rack del bot (Toque de Midas, Refracción multicolor, Poder del −, Trueque al fallo) o su inventario (Guante blanco), actualiza `my_tiles` y/o `my_items` antes de reenviar.
     4. Vuelve al paso 1 (otra llamada `/api/bot/move` con el estado actualizado).
   - **`pass` / `play_melds` / `extend_meld` / `replace_board`** → el bot ha terminado con los objetos y devuelve la jugada final. El backend la aplica y pasa el turno al siguiente jugador.
3. **Fin de turno**: cuando se cierra el turno, `items_used_this_turn` se descarta.

**Garantía de terminación**: el bot filtra internamente cualquier objeto que aparezca en `items_used_this_turn`. Como `my_items` tiene como mucho 3 entradas, el bucle tarda como máximo `len(my_items) + 1` llamadas en cerrar.

**Denegación**: si el backend decide no aplicar un `use_item` sugerido (por un `GUARDIAN_ANGEL` del objetivo, por política del evento, por falta de precondición...), basta con añadir el objeto a `items_used_this_turn` y volver a preguntar. El bot no lo repetirá. El objeto se considera "consumido o no disponible" a efectos del turno; que también se descuente del inventario real es decisión del backend según las reglas de la casa.

**Ejemplo completo de turno (dos objetos y jugada final):**

```
Request 1 → arcade.my_items=[MIDAS_TOUCH, PLUS_FOUR, GUARDIAN_ANGEL]
             arcade.items_used_this_turn=[]
Response 1 ← { move_type: "use_item",
               item_use: { item: "MIDAS_TOUCH", reason: "..." } }

Backend: aplica Midas (doradas al azar sobre el rack del bot).

Request 2 → my_tiles con doradas, arcade.my_items=[PLUS_FOUR, GUARDIAN_ANGEL]
             arcade.items_used_this_turn=[MIDAS_TOUCH]
Response 2 ← { move_type: "use_item",
               item_use: { item: "PLUS_FOUR", target_player_idx: 1, reason: "..." } }

Backend: ejecuta +4 sobre el jugador 1.

Request 3 → arcade.my_items=[GUARDIAN_ANGEL]
             arcade.items_used_this_turn=[MIDAS_TOUCH, PLUS_FOUR]
Response 3 ← { move_type: "play_melds",
               new_melds: [["R05D","O05","K05"]] }

Backend: aplica la jugada y cierra el turno. items_used_this_turn se descarta.
```

**Objetos que “no hace falta” encadenar**: para objetos que no modifican el rack ni la información del bot (p. ej. `CHILI_PEPPER`, `PLUS_FOUR`, `GLASS_CEILING`, `SMOKE_BOMB`, `RUM_ROCKS`), el backend podría aplicarlos "en paralelo" con una jugada del bot sin reenviar nada. Aun así, el contrato actual es uniforme: **siempre** que el bot devuelva `use_item` se debe volver a llamar. Esto simplifica el cliente (una única ruta) a cambio de una llamada extra por objeto, con impacto despreciable.

**Tienda dentro del bucle**: si el turno tiene tienda abierta (`arcade.shop` en el request), la compra viaja **solo en la respuesta final** del turno, nunca en las fases `use_item`. El backend puede seguir enviando `arcade.shop` en las peticiones intermedias (no molesta), pero el bot solo emitirá `shop_choice` cuando devuelva una jugada que cierra el turno. De este modo el backend procesa exactamente una compra por turno, al aplicar la jugada final.

### <a id="sec-1-10-9"></a>1.10.9 Responsabilidades en modo arcade (bot vs backend)

Esta sección es la **guía visual de integración**: para cada mecánica arcade se indica si la ejecuta el bot, el backend o ambos, y lo que el otro lado debe asumir. Leyenda:

| Icono | Significado |
|---|---|
| 🟢 | **Gestiona el bot (este servicio)**: aplica la restricción o aporta una decisión. |
| 🔴 | **Gestiona el backend (Spring Boot)**: es el autoritario de la mecánica. |
| 🟡 | **Compartida**: el backend es el autoritario pero el bot la consume para decidir. |
| ⚪ | **Informativa**: el bot la recibe pero no actúa sobre ella salvo como contexto. |

#### <a id="sec-1-10-9-1"></a>1.10.9.1 Tienda

Al empezar el turno de cada jugador, el backend puede abrir una tienda con 2–3 ofertas aleatorias. El bot solo decide si comprar o no **una** oferta por turno, y la compra se comunica junto a la jugada que cierra el turno.

| Tema | Quién | Detalle |
|---|:-:|---|
| Apertura de la tienda | 🔴 | El backend decide si este turno hay tienda y, si la hay, la envía en `arcade.shop`. El bot no abre tienda por su cuenta. |
| Composición del surtido (2–3 ofertas, precios, descuentos por evento) | 🔴 | El backend genera el catálogo y aplica `shop_discount` sobre los precios antes de mandarlos. Los precios que recibe el bot ya son los finales. |
| Saldo del jugador | 🔴 | Lo mantiene el backend y lo envía en `arcade.shop.balance`. El bot no suma ni resta saldo. |
| Inventario del jugador (máx 3) | 🟡 | El backend es el autoritario. El bot lo recibe en `arcade.my_items` y, por seguridad, trunca a 3 si llega con más. |
| Decisión de compra | 🟢 | El bot puntúa cada oferta con una heurística y responde `move.shop_choice = { buy, reason }` eligiendo una o ninguna. |
| Ejecución de la compra (cobrar saldo, añadir al inventario) | 🔴 | El backend aplica la compra tras recibir `shop_choice`. |
| No comprar Ángeles redundantes | 🟢 | Si `arcade.guardian_angel_active` es `true` o ya hay un `GUARDIAN_ANGEL` en `arcade.my_items`, el bot descarta comprar otro (no acumulable). |
| Momento en que se envía la compra | 🟢 | El bot **solo** emite `shop_choice` junto a una jugada que cierra el turno (`pass`, `play_melds`, `extend_meld`, `replace_board`). **Nunca** junto a `use_item`. |
| Uso del objeto recién comprado | 🔴 | El objeto comprado **no se usa ese mismo turno**. Queda disponible a partir del siguiente turno del jugador. |

#### <a id="sec-1-10-9-2"></a>1.10.9.2 Eventos especiales del turno

Cuando empieza una ronda de turnos, el backend puede sortear un evento aleatorio que altera ese turno. El bot se limita a respetar las restricciones que le afectan.

| Tema | Quién | Detalle |
|---|:-:|---|
| Sorteo del evento | 🔴 | El backend decide qué evento ocurre (o ninguno). |
| Ficha extra al empezar el turno | 🔴 | El backend reparte la ficha. El bot solo ve más fichas en `my_tiles`. Si se avisa, viene en `arcade.draw_at_turn_start` (informativo ⚪). |
| Color bloqueado | 🟢 | El backend lo comunica en `arcade.blocked_color`. El bot **nunca** propone jugadas que añadan fichas de ese color desde la mano (melds, extensiones, reorganizaciones). Las fichas con habilidad arcoíris (`A`) **no se ven afectadas** aunque su color base coincida. `validate_move` actúa como última barrera. |
| Descuento del 50% en tienda | 🔴 | El backend aplica el descuento y envía los precios ya rebajados. El bot solo lo recibe como `arcade.shop_discount` (⚪ informativo). |
| Tiempo de turno a 30 s / 90 s | 🟡 | El backend aplica el reloj real. El bot recibe `arcade.time_limit_s` y lo usa para acotar su búsqueda interna (menos tiempo ⇒ menos profundidad/beam). |

#### <a id="sec-1-10-9-3"></a>1.10.9.3 Objetos: reglas generales y flujo del turno

Esta es la parte más delicada, porque el turno arcade del bot **ya no es una única petición sino un bucle de fases** (ver 1.10.8). Las responsabilidades se reparten así:

| Tema | Quién | Detalle |
|---|:-:|---|
| Inventario máx 3 objetos | 🔴 | Autoritario del inventario. El bot trunca por seguridad si llega con más de 3. |
| Ejecución real del efecto del objeto | 🔴 | **Siempre** lo ejecuta el backend (cambia fichas, reparte, revela, reduce tiempo, invierte controles, etc.). |
| Decisión de *qué* objeto usar | 🟢 | El bot responde con `move_type: "use_item"` e `item_use = { item, target_player_idx?, params?, reason }`. Una sugerencia por respuesta, sin jugada mezclada. |
| Actualización del estado entre fases | 🔴 | Si el efecto modifica algo que el bot ve (`my_tiles` tras Midas / Refracción / Poder del − / Trueque, `my_items` tras Guante blanco, `opponent_rack_counts` tras +4...), el backend lo refleja en el siguiente request. El bot asume que lo recibido ya tiene aplicados los efectos anteriores del turno. |
| `items_used_this_turn` (contador anti‑repetición) | 🟡 | El backend inicializa la lista a `[]` al abrir turno del bot y añade el `ItemType` tras cada `use_item` (aplicado o denegado). El bot filtra esa lista antes de proponer cualquier objeto. |
| Denegación de un `use_item` | 🔴 | Si el backend decide no ejecutar la sugerencia (Ángel de la guarda del objetivo, precondición no cumplida, política de evento...), añade igualmente el objeto a `items_used_this_turn` y vuelve a preguntar. El bot no insistirá. |
| Garantía de terminación del bucle | 🟢 | El bot solo sugiere objetos presentes en `my_items` y ausentes en `items_used_this_turn`. Con `my_items ≤ 3`, el turno cierra en como mucho `len(my_items) + 1` peticiones. |
| Cierre del turno | 🟢 | El bot cierra el turno devolviendo `pass`, `play_melds`, `extend_meld` o `replace_board`. Ese mismo `Move` puede llevar `shop_choice` (ver 1.10.9.1), nunca `item_use`. |
| Conversión de `GUARDIAN_ANGEL` a escudo | 🔴 | Al inicio del turno del portador, si tiene un Ángel en `my_items` y **no** hay escudo activo, el backend lo retira del inventario y activa `guardian_angel_active=true`. Si ya había escudo activo, el Ángel se queda en `my_items` (no acumula) y el backend reintentará la conversión al siguiente turno. El bot no participa en este proceso. |
| Consumo del escudo al recibir un ataque | 🔴 | Cuando un objeto ofensivo afecta al portador y éste tiene `guardian_angel_active=true`, el backend bloquea el efecto automáticamente y pone el flag a `false`. El bot lo ve reflejado en el siguiente request. |

#### <a id="sec-1-10-9-4"></a>1.10.9.4 Objetos: tipo por tipo

Matiz por objeto; el bot puede **sugerir** el uso de algunos y los marcados como pasivos o autolesivos no los propone nunca.

| Objeto | Sugiere | Ejecuta | Notas |
|---|:-:|:-:|---|
| `GUARDIAN_ANGEL` — Ángel de la guarda | ❌ | 🔴 | Escudo pasivo, **no acumulable** y **no activable**. Al adquirirlo entra en `my_items`. Al inicio del siguiente turno del portador, si no había ya un escudo activo, el backend lo **retira de `my_items`** y pone `guardian_angel_active=true`: ya no ocupa slot. El escudo bloquea automáticamente el siguiente objeto ofensivo que afecte al portador, se gasta (flag a `false`) y si había otro Ángel pendiente en `my_items` se convertirá en el siguiente turno. No es robable por Guante Blanco porque el escudo vive fuera de `my_items`. El bot nunca lo sugiere en `use_item` y no compra Ángeles redundantes. |
| `CRYSTAL_BALL` — Bola de cristal | 🟢 (nivel ≥ 8) | 🔴 | El bot sugiere `params.color` o `params.value_range`; el backend ejecuta la consulta. |
| `TRUTH_MAGNIFIER` — Lupa de la verdad | 🟢 (nivel ≥ 8, contra líder) | 🔴 | El backend revela fichas y objetos del objetivo. |
| `MIDAS_TOUCH` — Toque de Midas | 🟢 (mano grande sin abrir) | 🔴 | El backend elige al azar 2–4 fichas propias y las convierte en doradas (sufijo `D`). |
| `MINUS_POWER` — Poder del − | ❌ | 🔴 | El bot **nunca** lo sugiere (perjudica al propio). Si llega aplicado, lo puntúa correctamente por el sufijo `N`. |
| `RAINBOW_REFRACTION` — Refracción multicolor | 🟢 (mano grande sin abrir) | 🔴 | Convierte 1–2 fichas del bot en arcoíris (sufijo `A`). |
| `PLUS_FOUR` — +4 | 🟢 (rival cerca de ganar) | 🔴 | El backend hace que el objetivo robe 4 fichas. |
| `SWAP_ON_FAIL` — Trueque al fallo | 🟢 (indica target) | 🔴 | El backend gestiona la elección e intercambio (requiere UI); el bot **no** elige las fichas. |
| `WHITE_GLOVE` — Guante blanco | 🟢 (rival con más objetos) | 🔴 | El backend ejecuta el robo de **un objeto del `my_items` del objetivo**. Requiere que el objetivo tenga al menos uno. El escudo activo (`guardian_angel_active`) **no es robable**: vive fuera del inventario. |
| `SMOKE_BOMB` — Bomba de humo | 🟢 (si va a reorganizar) | 🔴 | El backend oculta el tablero al objetivo durante su turno. |
| `CHILI_PEPPER` — Guindilla | 🟢 (rival líder) | 🔴 | Reduce a la mitad el tiempo del próximo turno del objetivo. |
| `RUM_ROCKS` — Ron con hielo | 🟢 (indica target) | 🔴 | Invierte los controles del objetivo un turno (mecánica del cliente/backend). |
| `GLASS_CEILING` — Techo de cristal | 🟢 (como emisor, contra rival pocas fichas) + 🟢 (como receptor) | 🔴 | Como emisor: el bot puede sugerirlo. Como receptor: el backend envía `arcade.min_play_points` y el bot **rechaza** cualquier jugada propia por debajo del umbral. |

#### <a id="sec-1-10-9-5"></a>1.10.9.5 Fichas especiales (habilidades `A`, `D`, `N`)

Formato `Palo+Número` con sufijos de habilidad: `A`=arcoíris, `D`=dorado, `N`=negativo. Ejemplos: `B07A`, `O03D`, `R10N`. El comodín sigue siendo `J*`. Ver 1.10.1 para la gramática completa.

| Tema | Quién | Detalle |
|---|:-:|---|
| Generación (decidir qué fichas se transforman) | 🔴 | El backend decide mediante objetos (Midas → doradas, Refracción → arcoíris, Poder del − → negativas). |
| Puntuación dorada (`D`) | 🟢 | `Tile.points()` aplica ×2 (en apertura, en evaluación heurística y en techo de cristal). |
| Puntuación negativa (`N`) | 🟢 | `Tile.points()` aplica signo opuesto: puede dificultar la apertura; el bot vacía la mano de estas cuando le conviene. |
| Reglas de meld con arcoíris (`A`) | 🟢 | `rules.is_valid_set` la admite como color flexible en grupos; `rules.is_valid_run` la admite como color dominante. El color base es cosmético y **no** le afecta `blocked_color`. |
| Serialización / parseo de sufijos combinados | 🟢 | Al parsear admite cualquier orden (`B05AD` ≡ `B05DA`). Al serializar usa orden alfabético fijo `A, D, N` (p.ej. `B05AD`, `R09DN`). |

#### <a id="sec-1-10-9-6"></a>1.10.9.6 Resumen operativo

1. **Autoridad de la partida**: siempre el backend. Eventos, tienda, inventario, saldo, reloj y ejecución de objetos son suyos.
2. **Un único endpoint**: `POST /api/bot/move` cubre modo normal y modo arcade (jugada, bucle `use_item` y compra en tienda).
3. **Lo que hace el bot** a partir del bloque `arcade` del request:
   - Respeta `blocked_color` (las arcoíris quedan exentas).
   - Respeta `min_play_points` (techo de cristal contra él).
   - Puntúa correctamente fichas dorada / negativa y valida melds con arcoíris.
   - Decide uso de objetos por fases mediante `use_item` y filtra `items_used_this_turn`.
   - Decide compra en tienda al cerrar el turno mediante `shop_choice` (una por turno).
4. **Lo que hace el backend** entre fases del turno:
   - Ejecuta (o deniega) cada `use_item`, actualiza el estado visible y añade el objeto a `items_used_this_turn`.
   - Vuelve a llamar a `/api/bot/move` hasta que el bot devuelva una jugada que cierra el turno.
   - Al cerrar el turno, aplica la jugada, procesa `shop_choice` (si la hay) y descarta `items_used_this_turn`.

---

# <a id="sec-2"></a>2. Qué es este código y cómo funciona el modelo

> Esta sección está orientada a **programadores** que quieran entender el paquete por dentro. No es necesaria para consumir la API correctamente.

---

## <a id="sec-2-1"></a>2.1 Qué es RummiPlus

RummiPlus es un **paquete en Python** que proporciona:

- Las **reglas** de Rummikub clásico (melds (conjuntos) válidos, apertura de 30 puntos, comodines).
- Un **bot** que, dado el estado del juego (tablero, bolsa, su mano), devuelve una jugada (pasar, jugar melds (conjuntos), extender, reorganizar tablero).
- Una **API HTTP** (servidor incluido en el paquete) para que backends en otros lenguajes (Java, GDScript, etc.) envíen ese estado y reciban la jugada en JSON.

El **motor de la partida** (quién reparte, quién roba, quién gana) lo lleva siempre tu backend; RummiPlus solo responde a la pregunta: “con este estado, ¿qué jugada hace el bot?”.

---

## <a id="sec-2-2"></a>2.2 Tipo de “IA”: no es aprendizaje automático

El bot **no es un modelo de aprendizaje automático** (no hay red neuronal, ni entrenamiento con datos, ni ML típico). Es un **agente basado en reglas y búsqueda**:

- **Reglas:** Genera solo jugadas que cumplen las reglas del juego (melds (conjuntos) válidos, fichas en la mano (rack), apertura ≥30 si aplica).
- **Heurísticas:** Asigna a cada jugada un “score” con fórmulas fijas (puntos jugados, fichas que quedan en mano, bonus por vaciar mano, etc.).
- **Búsqueda:** En niveles altos, simula varias jugadas hacia delante (minimax con poda) y combina ese valor con el score de la opción.
- **Selección:** No elige siempre la mejor opción; introduce ruido y temperatura para que los niveles bajos fallen más y el comportamiento sea menos perfecto.

Por tanto, es un **sistema simbólico** (reglas + puntuaciones + búsqueda acotada), no un “modelo de IA” en el sentido de ML/DL.

---

## <a id="sec-2-3"></a>2.3 Cómo obtiene una respuesta el bot (paso a paso)

El flujo interno para decidir una jugada es el siguiente. Todo ocurre **en el turno actual**; el bot no guarda memoria entre turnos.

### <a id="sec-2-3-paso-1"></a>Paso 1 — Generar opciones

A partir del **estado actual** (tablero y **su** mano):

- Si aún no ha abierto (opened): se generan **combinaciones de melds** (conjuntos) que sumen al menos 30 puntos (apertura), más la opción de pasar.
- Si ya abrió: se generan **melds** (conjuntos) nuevos desde la mano (rack), **extensiones** de conjuntos del tablero con una ficha de la mano, y **reorganizaciones** (quitar fichas de conjuntos del tablero y formar nuevos conjuntos usando también la mano). También la opción de pasar.

La cantidad de opciones generadas está **limitada** y depende del **nivel** del bot: niveles bajos ven menos opciones (se les corta la lista antes), así que tienen menos donde elegir y suelen jugar peor.

### <a id="sec-2-3-paso-2"></a>Paso 2 — Filtrar legales

Cada opción se **valida** con las reglas del juego (fichas en la mano (rack), melds (conjuntos) válidos, apertura correcta, etc.). Las que no pasan se descartan. Si no queda ninguna legal, el bot devuelve “pasar” como única jugada permitida.

### <a id="sec-2-3-paso-3"></a>Paso 3 — Puntuación heurística

A cada opción que quedó se le asigna un **número (score)** con una función fija que tiene en cuenta, por ejemplo:

- Puntos jugados (más es mejor).
- Número de fichas usadas (más es mejor, acerca a vaciar la mano).
- Puntos que quedan en la mano (menos es mejor).
- Bonus si la jugada deja la mano vacía (ganar).
- Pequeñas penalizaciones (p. ej. usar comodines en jugadas que no son apertura).

Esta función **no usa información de los rivales**; solo la mano del bot y lo que se juega. Es puramente “qué tan buena es esta jugada para mí”.

### <a id="sec-2-3-paso-4"></a>Paso 4 — Búsqueda (solo nivel ≥ 3)

Para niveles 3 en adelante, y si hay más de una opción, el bot **simula** qué pasaría si juega cada una de las mejores opciones (limitado por tiempo y por número de ramas):

- Simula la jugada en una **copia** del estado.
- En esa copia, alterna turnos entre el bot y los rivales (los rivales también se simulan con el mismo bot).
- Cada “estado futuro” se **evalúa** con otra función que compara: puntos en mi mano (menos es mejor), puntos en mano (rack) de rivales (más es peor), si ya abrí, cuántos melds (conjuntos) hay en el tablero, etc.
- En **modo fairplay** (juego limpio: el bot no ve las fichas de los rivales) en esa evaluación solo se usa el **número de fichas** de cada rival (no qué fichas son). Eso se guarda en el estado como `opponent_rack_counts` (cantidad de fichas por rival).
- El resultado de esta simulación (un valor numérico por opción) se **combina** con el score heurístico del paso 3 (por ejemplo, score + 0.65 × valor_futuro). Así las opciones se **reordenan** según “jugada buena ahora y buena a futuro”.

La búsqueda está **acotada**: hay un límite de tiempo por turno, un máximo de opciones exploradas por nivel (beam) y una profundidad máxima. No es un minimax completo; es un “minimax recortado” con evaluación heurística en las hojas (no hay red neuronal que evalúe).

### <a id="sec-2-3-paso-5"></a>Paso 5 — Selección final

El bot **no elige siempre la opción con mejor score**. Se introduce:

- **Ruido:** Con cierta probabilidad (mayor en niveles bajos) elige una jugada de la mitad peor de la lista (“blunder”).
- **Temperatura:** Entre las opciones restantes se hace un **muestreo** según los scores (temperatura alta = más aleatorio, temperatura baja = más determinista). Así el mismo estado puede dar jugadas distintas en partidas distintas, y los niveles bajos son más erráticos.

El resultado de todo esto es **una sola jugada** (move; objeto `Move`), que la API convierte a JSON y devuelve al consumidor.

---

## <a id="sec-2-4"></a>2.4 Fairplay frente a simulación

- **Fairplay (producción):** El bot solo recibe tablero, tamaño de la bolsa, **sus fichas** y el **número de fichas** de cada rival. No ve las fichas concretas de los otros jugadores. Es el modo pensado para partidas con jugadores reales.
- **Simulación:** El bot recibe el estado completo (incluidas las manos de todos). Sirve para tests o para partidas solo entre bots donde quieres que el bot “vea todo” (por ejemplo en el motor de simulación incluido en el paquete).

La API HTTP que usa Spring Boot trabaja **siempre en modo fairplay** (juego limpio): tú envías solo lo que quieres que el bot use (tablero, `pool_count` (bolsa), `my_tiles` (mis fichas), opcionalmente `opponent_rack_counts` (fichas por rival)), y el servidor no tiene acceso a las manos de los rivales.

---

## <a id="sec-2-5"></a>2.5 Resumen técnico del “modelo”

- **Tipo:** Agente simbólico (reglas + heurísticas + búsqueda), **no** modelo de ML.
- **Entrada:** Estado (tablero, bolsa (pool), mano del bot (rack); en fairplay (juego limpio), conteos de rivales).
- **Proceso:** Generar candidatos → filtrar legales → puntuar con heurística → (opcional) re-puntuar con minimax acotado (beam + tiempo + profundidad) → seleccionar con ruido y temperatura.
- **Salida:** Una jugada (move): `pass` (pasar), `play_melds` (jugar conjuntos), `extend_meld` (extender conjunto), `replace_board` (reorganizar tablero), lista para aplicar en el motor del consumidor.

---

## <a id="sec-2-6"></a>2.6 Soporte de modo arcade

> Esta sub-sección describe **solo** las diferencias introducidas por el modo arcade. Lo explicado en 2.1–2.5 sigue siendo válido.

El bot **no gestiona eventos ni ejecuta objetos**: eso lo hace el backend. El papel del bot en modo arcade es **respetar restricciones** y **sugerir** el uso de un objeto.

### <a id="sec-2-6-1"></a>2.6.1 Qué hace el bot cuando recibe un `ArcadeState`

- **Color bloqueado**: en `_generate_options` se construye un *rack efectivo* filtrando las fichas del color bloqueado, y ninguna jugada generada (melds nuevos, extensiones, reorganizaciones) las usa. En `validate_move` se comprueba como última barrera.
- **Techo de cristal (`min_play_points`)**: `validate_move` rechaza cualquier jugada cuya suma de puntos añadidos por el bot sea menor al umbral. Como la heurística prioriza opciones de más puntos, el corte se produce naturalmente; si no hay opción válida, devuelve `pass`.
- **Fichas especiales** (dorada, negativa, arcoíris): se tratan en `Tile.points()` y en `rules.is_valid_set` / `is_valid_run`. Para la heurística no hace falta nada extra: `_evaluate_used_tiles` usa `t.points()` y ya recibe los modificadores aplicados.
- **Sugerencia de objeto (`item_use`)**: `_suggest_item_use` se ejecuta al final de `choose_move`. Aplica una heurística conservadora basada en el estado visible (número de fichas de rivales, tamaño del rack propio, objetos del rival, tipo de jugada elegida). Nunca sugiere `GUARDIAN_ANGEL` (pasivo) ni `MINUS_POWER` (perjudica al bot). Si no hay buen encaje, devuelve `None`.

### <a id="sec-2-6-2"></a>2.6.2 Qué sigue sin hacer el bot

- No genera eventos, no gestiona el reloj ni la tienda.
- No aplica efectos de objetos al estado: solo los sugiere.
- No recuerda nada entre turnos: sigue siendo *state in / move out*. El backend debe mandar el `arcade` actual con cada petición.
- No valida composición de mazo ni cantidad de fichas especiales: confía en el payload del backend.

### <a id="sec-2-6-3"></a>2.6.3 Impacto en la búsqueda (minimax)

Durante la simulación interna (niveles ≥ 3), el estado clonado conserva el `ArcadeState`. Eso implica que:

- **`blocked_color`** se aplica también al simular turnos de rivales. Coherente, porque el evento afecta a toda la ronda.
- **`min_play_points`** está pensado para el bot; si el backend lo pasa, se aplicará también a los rivales simulados. Es una aproximación conservadora (sesgo a favor del bot en la evaluación) asumida por simplicidad.

### <a id="sec-2-6-4"></a>2.6.4 Decisión de compra en tienda (`arcade.shop` + `move.shop_choice`)

La tienda vive dentro del propio endpoint `POST /api/bot/move`. Cuando el request incluye `arcade.shop.offer` no vacío, `choose_move` llama internamente a `StrategicBot.choose_shop_item` y adjunta el resultado a la jugada como `move.shop_choice`. El flujo es:

1. El backend abre la tienda al empezar el turno del bot, compone la oferta (2–3 entradas) con precios ya descontados y la mete en `arcade.shop` junto al saldo del jugador.
2. El bot decide **jugada** con el inventario actual (`arcade.my_items`) y, **en paralelo**, qué comprar (o nada). La compra no se aplica antes de la jugada ni se usa en ella.
3. La respuesta trae `move` + `move_short`; si había oferta, también `move.shop_choice`. El backend cobra, añade el objeto al inventario (para turnos futuros) y aplica la jugada.

La heurística de selección es la misma que en versiones anteriores y no mantiene estado entre peticiones: decide con la oferta y el contexto que le llegan.

1. **Filtros duros**: inventario con 3 objetos o ninguna oferta asequible ⇒ `buy: null`.
2. **Deduplicación**: si dos ofertas son del mismo `ItemType`, se mantiene la más barata.
3. **Utilidad por objeto**: cada oferta recibe una utilidad abstracta según el objeto y el contexto (rival líder, tamaño de mano, si el bot ya abrió, `level`). Ejemplos:
   - `MIDAS_TOUCH` y `RAINBOW_REFRACTION` valen más con mano grande o sin abrir.
   - `PLUS_FOUR`, `GLASS_CEILING`, `CHILI_PEPPER`, `SWAP_ON_FAIL`, `RUM_ROCKS` valen más cuando un rival tiene ≤ 5 fichas.
   - `GUARDIAN_ANGEL` sube de valor cuanto más cargado esté ya el inventario (merece la pena proteger).
   - `TRUTH_MAGNIFIER` y `CRYSTAL_BALL` solo interesan en `level ≥ 7`.
   - `WHITE_GLOVE` tiene valor moderado.
   - `MINUS_POWER` siempre se descarta.
4. **Ratio utilidad/precio**: se ordenan las ofertas por `utilidad / max(1, price)` de mayor a menor.
5. **Umbral mínimo**: si el mejor ratio es ≤ `0.02` el bot prefiere ahorrar y devuelve `buy: null` con la razón correspondiente.

El bot **no consulta catálogos del backend**, **no conoce el precio base** ni **aplica descuentos**: esa política es del backend. Si el evento `shop_discount = 0.5` está activo, el backend enviará precios ya rebajados en `arcade.shop.offer[i].price`. El bot tampoco decide cuándo se abre la tienda: solo responde cuando el bloque `arcade.shop` aparece en el request.

---

# <a id="sec-3"></a>3. Estructura del paquete

> Descripción de los ficheros del paquete `rummiplus` y del servidor, para quien quiera leer o modificar el código.

---

## <a id="sec-3-1"></a>3.1 Árbol y responsabilidades

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

## <a id="sec-3-2"></a>3.2 Ficheros del paquete (detalle)

### <a id="sec-3-2-core"></a>`core.py`

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

### <a id="sec-3-2-rules"></a>`rules.py`

**Qué hace:** Implementa las **reglas de Rummikub** a nivel de melds (conjuntos) y generación de candidatos.

- **is_valid_meld / is_valid_set / is_valid_run:** Comprueban si una lista de fichas forma un grupo válido (mismo valor, colores distintos) o una escalera válida (mismo color, valores consecutivos; comodines cubren huecos).
- **generate_meld_candidates:** A partir de un **rack** (mano), genera todos los melds (conjuntos) válidos de tamaño 3 hasta un máximo (p. ej. 5).
- **find_opening_combos:** Dado un rack y mínimo de puntos (30), encuentra combinaciones de melds **disjuntos** que sumen al menos ese mínimo (backtracking).
- **extend_meld_with_tile:** Comprueba si un meld (conjunto) del tablero puede extenderse con una ficha (añadir al grupo o a un extremo de la escalera) y devuelve el nuevo meld o `None`.
- **rack_without_tiles:** Utilidad para restar de un rack (mano) las fichas usadas en una jugada.

**Quién lo usa:** `move_logic` (validación), `ai` (generación de opciones).

---

### <a id="sec-3-2-move-logic"></a>`move_logic.py`

**Qué hace:** Conecta **reglas** con **estado**: valida jugadas y aplica jugadas **modificando el estado en sitio**.

- **opening_points:** Puntos que cuentan para la apertura (solo fichas no comodín).
- **clone_state:** Copia profunda de un `GameState` (para que el bot pueda simular sin alterar el estado real).
- **validate_move:** Comprueba si una `Move` (jugada) es legal (fichas en la mano (rack), melds (conjuntos) válidos, apertura ≥30 si aplica, extensión/reorganización coherente). Devuelve `(True, detalle)` o `(False, mensaje)`.
- **apply_move_inplace:** Si la jugada es legal, la ejecuta sobre el `GameState`: quita fichas del rack (mano), actualiza el tablero, y en caso de pass (pasar) puede robar de la bolsa (pool).

**Quién lo usa:** `ai` (para simular y para validar opciones), `engine` (para aplicar la jugada elegida en la partida), `api` (clone_state para fairplay y para state_from_bot_request).

---

### <a id="sec-3-2-ai"></a>`ai.py`

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

### <a id="sec-3-2-api"></a>`api.py`

**Qué hace:** Expone la **API pública** del paquete para quien integra el bot (en Python o vía JSON).

- **ViewMode:** Enum FAIRPLAY (juego limpio) / SIMULATION.
- **BotConfig:** Reexporta/amplía la config del bot (usada por BotFacade).
- **make_fairplay_view:** Dado un estado completo y un índice de jugador, devuelve un estado donde ese jugador ve solo su mano (rack) y el tablero; los demás racks (manos) se vacían y se rellenan `opponent_rack_counts` (fichas por rival).
- **move_to_dict:** Convierte un `Move` (jugada) a un diccionario listo para JSON (para enviar por HTTP).
- **state_from_bot_request:** Recibe el payload JSON que envía el backend (board (tablero), pool_count (bolsa), my_tiles (mis fichas), etc.) y construye un `GameState` con el que el bot puede decidir (ya en forma fairplay (juego limpio)).
- **BotFacade:** Fachada que recibe `BotConfig` y expone `decide_turn(state, player_idx)` y `decide_turn_fairplay(state, player_idx)` (este último construye la vista fairplay (juego limpio) y llama a decide_turn).

**Quién lo usa:** `engine` (simulación), `server` (state_from_bot_request, BotFacade, move_to_dict), y cualquier código que quiera usar el bot desde Python.

---

### <a id="sec-3-2-engine"></a>`engine.py`

**Qué hace:** **Motor de simulación** de partidas entre bots (sin interfaz).

- **SimulationConfig:** Número y configuración de bots, seed, máximo de turnos, tamaño de mano (rack) inicial, modo (fairplay (juego limpio) o simulación).
- **_init_state:** Crea el mazo, baraja, reparte fichas a cada bot y devuelve el `GameState` inicial y la lista de `BotFacade`.
- **run_simulation:** Bucle de turnos: en cada uno el bot correspondiente elige (fairplay (juego limpio) o simulación según config), se aplica la jugada (move) con `apply_move_inplace`; si es ilegal se penaliza con pass (pasar)+robo. Al final devuelve ganador, número de turnos, logs y puntos por jugador.

**Quién lo usa:** Quien quiera ejecutar partidas automáticas (p. ej. tests o estadísticas). La API HTTP no usa el engine; el engine usa la API (BotFacade) para que cada bot decida.

---

### <a id="sec-3-2-server"></a>`server.py`

**Qué hace:** **Servidor HTTP** mínimo para exponer el bot a backends externos.

- **BotAPIHandler:** Manejador de peticiones. Atiende GET `/api/health` (responde `{"ok": true}`) y POST `/api/bot/move`: lee el body JSON, llama a `state_from_bot_request`, crea un `BotFacade` con level/randomness/seed del payload, obtiene la jugada con `decide_turn(state, 0)` y devuelve `move_to_dict(move)` y `move_short`.
- **main:** Crea un `ThreadingHTTPServer` que atiende cada petición en un hilo (varias partidas pueden pedir jugadas a la vez).

**Quién lo usa:** El backend (Spring Boot) arranca este módulo con `python -m rummiplus.server` y hace POST a `/api/bot/move` cuando es el turno de un bot.

---

## <a id="sec-3-3"></a>3.3 Dónde está cada cosa

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

## <a id="sec-3-4"></a>3.4 Cambios para modo arcade

> Todos los cambios son **retrocompatibles**: si el backend no envía el bloque `arcade` en el request, el comportamiento es idéntico al modo normal.

| Archivo | Cambios añadidos |
|---------|------------------|
| `core.py` | Habilidades especiales arcade en `Tile`: `gold` (D), `negative` (N), `rainbow` (A). `Tile.points()` aplica signo y duplicación; rainbow no afecta a puntos. `short()` / `tile_from_short` usan sufijos `A`/`D`/`N` en orden alfabético al serializar y en cualquier orden al parsear. Nuevos tipos `ItemType`, `ItemUse`, `ShopOffer`, `ShopChoice`, `ArcadeState` (con `shop_offer`, `shop_balance`, `items_used_this_turn` y `guardian_angel_active`). Nuevo `MoveType.USE_ITEM` para el flujo de turno arcade por fases. `GameState` gana campo opcional `arcade`. `Move` gana campos opcionales `item_use` y `shop_choice`. |
| `rules.py` | `is_valid_set` admite arcoíris (`t.rainbow`) ocupando slots de color libres. `is_valid_run` admite arcoíris tomando el color dominante del resto. Validación clásica inalterada en ausencia de arcoíris. |
| `move_logic.py` | `clone_state` copia el `ArcadeState` completo (incluidas `shop_offer`, `items_used_this_turn`). Nueva función `_validate_arcade_constraints` (color bloqueado + techo de cristal). `validate_move` rechaza `USE_ITEM` (es señal de API, no jugada del motor) y aplica restricciones arcade a `play_melds`, `extend_meld` y `replace_board`. |
| `api.py` | Nuevo `_parse_arcade` en `state_from_bot_request` (bloque `arcade` del payload, incluyendo `arcade.shop`, `arcade.items_used_this_turn` y `arcade.guardian_angel_active`). `move_to_dict` serializa `USE_ITEM` con solo `move_type`/`reason`/`item_use`; para jugadas clásicas añade `shop_choice` cuando procede. Utilidades `item_use_to_dict` y `shop_choice_to_dict`. Método opcional `BotFacade.decide_shop` para usos embebidos. |
| `ai.py` | `_arcade_rack` filtra el color bloqueado para la generación de jugadas. `_suggest_item_use` filtra también los objetos que aparecen en `arcade.items_used_this_turn`. `choose_move` devuelve `Move(USE_ITEM, item_use=...)` cuando hay una sugerencia viable; en caso contrario devuelve la jugada clásica con `shop_choice` adjunto si procede. `choose_shop_item` recibe `guardian_angel_active` y descarta Ángeles redundantes (ya hay escudo activo o pendiente). Garantía de terminación: máx `len(my_items) + 1` llamadas por turno. |
| `server.py` | Un solo endpoint `POST /api/bot/move` cubre modo normal y arcade (incluidas tienda y bucle de fases `use_item`). Sin cambios respecto a la semántica del endpoint; la lógica nueva está en `api.py`/`ai.py`. |
| `__init__.py` | Exporta los nuevos tipos: `ArcadeState`, `ItemType`, `ItemUse`, `item_use_to_dict`, `ShopOffer`, `ShopChoice`, `shop_choice_to_dict`. El nuevo `MoveType.USE_ITEM` se expone a través del propio `MoveType`. |

---

*RummiPlus — Bot de Rummikub clásico para backends Spring Boot, con soporte opcional de modo arcade.*
