#!/usr/bin/env bash
# Corre todas las pruebas. Ejecuta:  bash probar.sh
set -e
cd "$(dirname "$0")/tests"
PY="../.venv/bin/python"
[ -x "$PY" ] || PY="python3"
for t in test_scraper.py test_filtros.py test_sincronizacion.py test_sheets_api.py; do
  echo "───────────────────────────────────────── $t"
  "$PY" "$t"
done
