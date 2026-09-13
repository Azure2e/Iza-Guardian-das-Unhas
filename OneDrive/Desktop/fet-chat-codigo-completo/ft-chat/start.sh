#!/bin/bash
cd "$(dirname "$0")"
export PORT="${PORT:-3000}"
mkdir -p data public/uploads
echo "Instalando dependencias..."
python3 -m pip install -r requirements.txt
echo "Iniciando FT Chat na porta $PORT (reinicia sozinho se cair)"
while true; do
  python3 -u server.py
  code=$?
  echo "Servidor saiu com código $code. Subindo de novo em 1s…"
  sleep 1
done
