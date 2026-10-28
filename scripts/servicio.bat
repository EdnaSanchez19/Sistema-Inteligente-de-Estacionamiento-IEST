@echo off
rem Doble clic o: scripts\servicio.bat instalar ^| estado ^| detener ^| iniciar ^| reiniciar ^| quitar
set ACCION=%1
if "%ACCION%"=="" set ACCION=estado
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servicio.ps1" %ACCION%
echo.
pause
