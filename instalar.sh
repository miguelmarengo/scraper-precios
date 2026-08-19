#!/usr/bin/env bash
# Instalación en Mac. Ejecuta:  bash instalar.sh
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "No encontré python3. Instálalo desde https://www.python.org/downloads/ y vuelve a correr esto."
  exit 1
fi

echo "→ Creando el entorno virtual…"
python3 -m venv .venv

echo "→ Instalando dependencias…"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

mkdir -p ~/.config/scraper-precios

echo
echo "Listo. Para abrir la aplicación:"
echo "    bash abrir.sh"
echo
echo "Falta un paso: pon tu archivo de credenciales de Google en"
echo "    ~/.config/scraper-precios/credenciales.json"
echo "(instrucciones en el README, sección Google)"
echo
echo "Opcional: si alguna tienda arma su catálogo con JavaScript (React/Vue/Angular) y te da 0"
echo "productos, en la barra lateral hay una casilla '🧪 Renderizar con navegador'. Para usarla,"
echo "corre una sola vez (gratis, ~180 MB, es de código abierto):"
echo "    ./.venv/bin/playwright install chromium"
