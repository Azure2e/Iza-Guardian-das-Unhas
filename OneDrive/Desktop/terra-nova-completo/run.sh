#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 manage.py migrate --noinput
python3 manage.py seed_loja
echo "Loja: http://127.0.0.1:8000/"
echo "Painel: http://127.0.0.1:8000/painel/   (admin / TerraNova@2026)"
python3 manage.py runserver 0.0.0.0:8000
