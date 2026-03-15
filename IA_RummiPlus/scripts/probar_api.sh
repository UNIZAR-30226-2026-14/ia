#!/usr/bin/env bash
# Pruebas rápidas del servicio RummiPlus (bot por HTTP).
# Uso: ./scripts/probar_api.sh [host:port]
# Por defecto: 127.0.0.1:8765

set -e
BASE="${1:-http://127.0.0.1:8765}"

echo "=== 1. Health ==="
curl -s "$BASE/api/health" | head -1
echo ""

echo "=== 2. Bot: pedir jugada (apertura) ==="
curl -s -X POST "$BASE/api/bot/move" \
  -H "Content-Type: application/json" \
  -d '{
    "board": [],
    "pool_count": 60,
    "my_tiles": ["B01","B02","B03","B04","B05","B06","B07","B08","B09","B10","B11","B12","B13","R01"],
    "opponent_rack_counts": [14],
    "opened": false,
    "level": 5
  }' | python3 -m json.tool
echo ""

echo "=== 3. Bot: tablero con melds, pedir jugada ==="
curl -s -X POST "$BASE/api/bot/move" \
  -H "Content-Type: application/json" \
  -d '{
    "board": [["B02","B03","B04"],["R01","O01","K01"]],
    "pool_count": 50,
    "my_tiles": ["B05","B06","B07","B08","B09","B10","B11","B12","B13","K01","K02","K03","K04","K05"],
    "opponent_rack_counts": [14,14],
    "opened": false,
    "level": 5
  }' | python3 -m json.tool
echo ""

echo "=== 4. Bot: nivel bajo (1) vs nivel alto (9) — solo comprobar que responden ==="
echo "Nivel 1:"
curl -s -X POST "$BASE/api/bot/move" -H "Content-Type: application/json" \
  -d '{"board":[],"pool_count":60,"my_tiles":["B01","B02","B03","B04","B05","B06","B07","B08","B09","B10","B11","B12","B13","R01"],"opened":false,"level":1}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  move_type:', d['move']['move_type'], '| move_short:', d.get('move_short','')[:50])"
echo "Nivel 9:"
curl -s -X POST "$BASE/api/bot/move" -H "Content-Type: application/json" \
  -d '{"board":[],"pool_count":60,"my_tiles":["B01","B02","B03","B04","B05","B06","B07","B08","B09","B10","B11","B12","B13","R01"],"opened":false,"level":9}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  move_type:', d['move']['move_type'], '| move_short:', d.get('move_short','')[:50])"
echo ""
echo "Listo. Si todo ha devuelto JSON sin error, el modelo y la API van bien."
