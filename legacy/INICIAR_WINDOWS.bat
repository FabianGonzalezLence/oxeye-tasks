@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  OXEYE - LISTA DE TRABAJO COMPARTIDA
echo  ------------------------------------
echo  Abre http://localhost:8765 en este equipo.
echo  Para los demas equipos usa http://IP_DE_ESTE_PC:8765
 echo  (Para conocer la IP, abre otra consola y escribe ipconfig.)
echo.
echo  La primera clave esta en datos\ACCESO_INICIAL.txt
 echo  Mantén esta ventana abierta para seguir sincronizando.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 servidor.py --host 0.0.0.0 --port 8765
) else (
  python servidor.py --host 0.0.0.0 --port 8765
)
echo.
echo  El servidor se ha detenido.
pause
