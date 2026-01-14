# Script de PowerShell para iniciar el chatbot WhatsApp
Write-Host "🤖 Iniciando Chatbot WhatsApp LLM..." -ForegroundColor Green
Write-Host "📍 Ubicación: e:\IA\chatbot-whatsapp-llm" -ForegroundColor Cyan

# Cambiar al directorio del proyecto
Set-Location "e:\IA\chatbot-whatsapp-llm"

Write-Host "🔄 Activando entorno virtual..." -ForegroundColor Yellow
# El entorno virtual ya está configurado, solo ejecutamos Python

Write-Host "🚀 Iniciando servidor admin en puerto 8003..." -ForegroundColor Magenta
Write-Host "📱 Dashboard: http://127.0.0.1:8003/ui/index.html" -ForegroundColor Cyan
Write-Host "💬 Chat: http://127.0.0.1:8003/chat" -ForegroundColor Cyan
Write-Host "📖 Docs: http://127.0.0.1:8003/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  Presiona Ctrl+C para detener el servidor" -ForegroundColor Red
Write-Host ""

# Ejecutar el panel de administración
& "E:\IA\.venv\Scripts\python.exe" admin_panel.py
