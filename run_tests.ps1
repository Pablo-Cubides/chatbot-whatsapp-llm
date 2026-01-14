# 🧪 Script de Tests - Chatbot WhatsApp Enterprise

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "🧪 EJECUTANDO TESTS - Chatbot WhatsApp Enterprise" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "pytest.ini")) {
    Write-Host "❌ ERROR: No se encuentra pytest.ini" -ForegroundColor Red
    Write-Host "   Ejecuta este script desde el directorio raíz del proyecto" -ForegroundColor Yellow
    exit 1
}

# Verificar que existe la carpeta tests
if (-not (Test-Path "tests")) {
    Write-Host "❌ ERROR: No se encuentra la carpeta tests/" -ForegroundColor Red
    exit 1
}

Write-Host "📁 Directorio: " -NoNewline
Write-Host (Get-Location) -ForegroundColor Green
Write-Host ""

# Menú de opciones
Write-Host "Selecciona una opción:" -ForegroundColor Yellow
Write-Host "1. Ejecutar TODOS los tests" -ForegroundColor White
Write-Host "2. Ejecutar solo tests de autenticación" -ForegroundColor White
Write-Host "3. Ejecutar solo tests de cola y campañas" -ForegroundColor White
Write-Host "4. Ejecutar solo tests de alertas" -ForegroundColor White
Write-Host "5. Ejecutar solo tests de transcripción" -ForegroundColor White
Write-Host "6. Ejecutar solo tests de WhatsApp providers" -ForegroundColor White
Write-Host "7. Ejecutar con reporte de coverage" -ForegroundColor White
Write-Host "8. Ejecutar tests que fallaron (last-failed)" -ForegroundColor White
Write-Host ""

$option = Read-Host "Opción (1-8)"

switch ($option) {
    "1" {
        Write-Host "`n🚀 Ejecutando TODOS los tests..." -ForegroundColor Cyan
        pytest tests/ -v --tb=short
    }
    "2" {
        Write-Host "`n🔐 Ejecutando tests de autenticación..." -ForegroundColor Cyan
        pytest tests/test_auth_system.py -v --tb=short
    }
    "3" {
        Write-Host "`n📨 Ejecutando tests de cola y campañas..." -ForegroundColor Cyan
        pytest tests/test_queue_system.py -v --tb=short
    }
    "4" {
        Write-Host "`n🚨 Ejecutando tests de alertas..." -ForegroundColor Cyan
        pytest tests/test_alert_system.py -v --tb=short
    }
    "5" {
        Write-Host "`n🎤 Ejecutando tests de transcripción..." -ForegroundColor Cyan
        pytest tests/test_audio_transcriber.py -v --tb=short
    }
    "6" {
        Write-Host "`n📱 Ejecutando tests de WhatsApp providers..." -ForegroundColor Cyan
        pytest tests/test_whatsapp_providers.py -v --tb=short
    }
    "7" {
        Write-Host "`n📊 Ejecutando con coverage report..." -ForegroundColor Cyan
        pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
        Write-Host "`n✅ Reporte HTML generado en: htmlcov/index.html" -ForegroundColor Green
    }
    "8" {
        Write-Host "`n🔄 Ejecutando tests que fallaron..." -ForegroundColor Cyan
        pytest --lf -v --tb=short
    }
    default {
        Write-Host "`n❌ Opción inválida" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "✅ Ejecución completada" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
