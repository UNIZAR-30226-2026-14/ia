"""
Servidor HTTP mínimo que expone solo la API del bot (POST /api/bot/move).

Parte del paquete rummiplus: al instalar el paquete puedes levantar la API con
  python -m rummiplus.server --port 8765
Para Spring Boot; sin UI ni archivos estáticos.

Usa ThreadingHTTPServer: cada petición se atiende en un hilo, así que varias
partidas pueden pedir jugadas a la vez sin bloquearse entre sí.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus


class BotAPIHandler(BaseHTTPRequestHandler):
    """
    Manejador HTTP: GET /api/health y POST /api/bot/move.
    En POST lee JSON (board, pool_count, my_tiles, level...), construye estado,
    pide jugada al bot y devuelve move + move_short en JSON.
    """

    def log_message(self, format: str, *args: object) -> None:
        pass  # Silenciar logs por petición; quitar para depurar.

    def _json_response(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        """Envía respuesta JSON con el status indicado."""
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        """Solo /api/health responde; el resto 404."""
        if self.path == "/api/health":
            self._json_response({"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        """
        POST /api/bot/move: body JSON con estado (board, pool_count, my_tiles, ...).
        Construye GameState, crea bot con level/randomness/seed del payload,
        obtiene jugada y devuelve {"move": {...}, "move_short": "..."}.
        """
        if self.path != "/api/bot/move":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response({"error": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            from .api import BotConfig, BotFacade, move_to_dict, state_from_bot_request

            state = state_from_bot_request(payload)
            level = max(1, min(10, int(payload.get("level", 5))))
            randomness = max(0.0, min(1.0, float(payload.get("randomness", 0.25))))
            seed = payload.get("seed")
            if seed is not None:
                seed = int(seed)
            bot = BotFacade(BotConfig(level=level, randomness=randomness, seed=seed))
            move = bot.decide_turn(state, 0)
            self._json_response({"move": move_to_dict(move), "move_short": move.short()})
        except ValueError as e:
            self._json_response({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json_response({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    """Arranca el servidor HTTP en host:port (por defecto 127.0.0.1:8765)."""
    parser = argparse.ArgumentParser(description="API del bot Rummiplus (POST /api/bot/move)")
    parser.add_argument("--host", default="127.0.0.1", help="Host")
    parser.add_argument("--port", type=int, default=8765, help="Puerto")
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), BotAPIHandler)
    print(f"API bot: http://{args.host}:{args.port}/api/bot/move (concurrente)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
