@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 goto error
)
if not exist .venv\cupri_instalado (
  .venv\Scripts\python.exe -m pip install --upgrade pip
  if errorlevel 1 goto error
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto error
  echo instalado>.venv\cupri_instalado
)
echo Abre http://127.0.0.1:8765 en tu navegador.
.venv\Scripts\python.exe local\server.py
pause
exit /b
:error
echo No se pudo completar la instalacion. Instala Python 3.11 y revisa tu conexion.
pause
exit /b 1
