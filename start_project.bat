@echo off
echo Iniciando el proyecto de chatbot WhatsApp...
cd /d "e:\IA\chatbot-whatsapp-llm"
echo.
echo Activando entorno virtual...
call "E:\IA\.venv\Scripts\activate.bat"
echo.
echo Ejecutando el servidor admin...
"E:\IA\.venv\Scripts\python.exe" admin_panel.py
pause
