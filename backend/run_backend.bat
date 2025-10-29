@echo off
setlocal
cd /d %~dp0
echo 🔧 Iniciando entorno virtual...
call venv\Scripts\activate

echo 🚀 Ejecutando servidor Waitress...
python -m waitress --listen=127.0.0.1:8000 app:create_app

pause
endlocal
