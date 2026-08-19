#!/usr/bin/env bash
# Arranca la interfaz web local. Ejecuta:  bash abrir.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Primero corre:  bash instalar.sh"
  exit 1
fi

exec ./.venv/bin/streamlit run app.py
