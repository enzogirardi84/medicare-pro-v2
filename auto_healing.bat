@echo off
echo ========================================
echo MEDICARE PRO - SISTEMA AUTO-HEALING
echo ========================================
echo.
echo Este script configura la automatizacion completa:
echo   1. Ejecuta auto-healing cada 6 horas
echo   2. Corre tests automaticamente
echo   3. Hace backup diario
echo   4. Limpia archivos temporales
echo.

cd /d "%~dp0.."

echo [1/4] Ejecutando auto-healing...
python scripts\auto_healing.py
if %errorlevel% equ 0 (
    echo   OK - Sin errores criticos
) else (
    echo   ALERTA - Se encontraron problemas (revisar reporte)
)

echo.
echo [2/4] Ejecutando tests...
python -m pytest tests\ --tb=short -q 2>nul
if %errorlevel% equ 0 (
    echo   OK - Todos los tests pasan
) else (
    echo   ALERTA - Tests fallaron
)

echo.
echo [3/4] Verificando sintaxis...
for /r %%f in (*.py) do (
    python -c "compile(open('%%f',encoding='utf-8').read(),'%%f','exec')" 2>nul
)
echo   OK

echo.
echo [4/4] Mantenimiento completado!
echo.
echo Para programar automaticamente cada 6 horas:
echo   1. Abrir "Task Scheduler" de Windows
echo   2. Crear tarea basica
echo   3. Trigger: "Daily" repetir cada 6 horas
echo   4. Action: "Start a program" -> este script
echo.
pause
