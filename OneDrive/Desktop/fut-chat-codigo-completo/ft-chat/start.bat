@echo off
cd /d "%~dp0"
if not defined PORT set PORT=3000
if not exist data mkdir data
if not exist public\uploads mkdir public\uploads

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=py -3
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    set PY=python
  ) else (
    echo Python nao encontrado.
    echo Instale em https://www.python.org/downloads/
    echo Na instalacao marque: Add python.exe to PATH
    pause
    exit /b 1
  )
)

echo Instalando dependencias Python...
%PY% -m pip install -r requirements.txt
echo.
echo Iniciando FT Chat em http://localhost:%PORT%
echo Feche esta janela para parar.
echo.

:loop
%PY% -u server.py
echo Servidor saiu. Subindo de novo em 1s...
timeout /t 1 /nobreak >nul
goto loop
