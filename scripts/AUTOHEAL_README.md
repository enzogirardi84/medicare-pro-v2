# AutoHeal — Sistema Autónomo de Mantenimiento

Escanea, corrige y testea MediCare PRO automáticamente sin intervención manual.

## Uso Rápido

```bash
# Un solo escaneo
python scripts/autoheal.py --path views/

# Escaneo + fixes + tests
python scripts/autoheal.py --fix --create-tests --run-tests

# MODO DAEMON: se ejecuta cada 15 minutos AUTOMÁTICAMENTE
python scripts/autoheal.py --watch 15 --fix --create-tests --run-tests --auto-commit --log autoheal.log

# Instalar como servicio programado de Windows (se ejecuta cada 15 min)
python scripts/autoheal.py --install-service
```

## Modo Daemon (--watch)

El modo daemon ejecuta un ciclo completo cada N minutos:
1. Escanea todos los archivos `.py` en `views/` y `core/`
2. Aplica correcciones automáticas (NoneType crashes, etc.)
3. Crea tests para módulos sin cobertura
4. Ejecuta la suite de tests
5. Hace auto-commit y push a GitHub
6. Loggea todo a `autoheal.log`
7. Espera N minutos y repite

Para correrlo en segundo plano en Windows:
```powershell
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "scripts/autoheal.py --watch 15 --fix --create-tests --run-tests --auto-commit --log autoheal.log"
```

Para detenerlo:
```powershell
Get-Process | Where-Object {$_.CommandLine -like "*autoheal*"} | Stop-Process
```

## Opciones

| Flag | Descripción |
|------|-------------|
| `--path DIR` | Escanea directorio específico |
| `--fix` | Aplica correcciones automáticas |
| `--create-tests` | Crea tests para módulos sin cobertura |
| `--run-tests` | Ejecuta pytest al final |
| `--watch N` | Modo daemon: cada N minutos |
| `--auto-commit` | Auto-commit + push (requiere --watch) |
| `--log FILE` | Archivo de log |
| `--ci` | Modo CI: exit 1 si hay issues críticos |
| `--install-service` | Instala como tarea programada de Windows |

## Escáneres

| Escáner | Severidad | Descripción |
|---------|-----------|-------------|
| `.get(key)[:N]` | HIGH | NoneType crash si key existe con None |
| `UnboundLocalError` | CRITICAL | log_event antes de import local |
| `st.error` sin `log_event` | HIGH | Violación de estándar de logging |
| `unsafe_allow_html` sin escape | HIGH | Riesgo XSS |
| `verify_patient_access` ausente | CRITICAL | Riesgo IDOR |
| Subíndice en loop sin guard | MEDIUM | Crash si lista contiene None |
