# Genera app-release.apk en tu PC (requiere Flutter en PATH).
# Uso: PowerShell en esta carpeta:  ..\tool\build_apk.ps1
#   o:  cd medicare_paciente_alerta; .\tool\build_apk.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error "Flutter no esta en PATH. Instalalo y ejecuta 'flutter doctor'. Ver: https://docs.flutter.dev/get-started/install/windows"
}

if (-not (Test-Path (Join-Path $Root "android"))) {
    Write-Host "Creando carpetas android/ios/web con flutter create..."
    flutter create . --org com.medicare
}

flutter pub get
flutter build apk --release

$apk = Join-Path $Root "build\app\outputs\flutter-apk\app-release.apk"
if (Test-Path $apk) {
    Write-Host ""
    Write-Host "APK lista:" -ForegroundColor Green
    Write-Host (Resolve-Path $apk).Path
    Write-Host ""
    Write-Host "Copiala al telefono e instala (Origen desconocido / instalar de todas formas)."
} else {
    Write-Error "No se encontro la APK en $apk"
}
