# Guía de Uso - Dashboard del Chatbot

## Inicio Rápido

### Opción 1: Arranque Completo
1. Ejecutar `start_dashboard.bat` para iniciar todo el sistema
2. Esto iniciará:
   - LM Studio (si está configurado)
   - Panel de administración (puerto 8001)
   - Automator de WhatsApp (si está habilitado)

### Opción 2: Solo Abrir Dashboard
1. Si el servidor ya está corriendo, usar `open_dashboard.bat`
2. Esto solo abrirá el dashboard en el navegador

## URLs Importantes

- **Dashboard Principal**: http://127.0.0.1:8001/ui/index.html
- **API Documentation**: http://127.0.0.1:8001/docs
- **Health Check**: http://127.0.0.1:8001/healthz

## Funciones del Dashboard

### 1. Gestión de Modelos
- Configurar temperatura, max_tokens
- Cambiar frecuencia de reasoning (cada X mensajes)

### 2. Personalidad y Prompts
- Editar prompt conversacional
- Configurar prompt de razonamiento
- Ajustar prompt de conversación

### 3. Control de Contactos
- Ver lista de contactos permitidos (allowlist)
- Agregar/remover contactos
- Ver estadísticas por contacto

### 4. Programación de Mensajes
- Crear mensajes programados
- Ver próximos envíos
- Cancelar mensajes pendientes

### 5. Monitoreo en Tiempo Real
- Ver eventos del sistema
- Logs de conversaciones
- Estado de componentes

## Autenticación API

Los endpoints protegidos requieren autenticación Bearer token:
```
Authorization: Bearer admin-secret-2024
```

## Configuración Avanzada

### Variables de Entorno
- `FERNET_KEY`: Clave de encriptación (auto-generada)
- `LM_STUDIO_PATH`: Ruta al ejecutable de LM Studio
- `KEEP_AUTOMATOR_OPEN`: Mantener automator abierto (true/false)

### Archivos de Configuración
- `data/settings.json`: Configuración del modelo
- `data/prompts.json`: Prompts personalizados
- `data/scheduled.json`: Mensajes programados
- `data/contacts.db`: Base de datos de contactos (encriptada)

## Solución de Problemas

### El servidor no inicia
1. Verificar que Python esté instalado
2. Verificar que el entorno virtual exista
3. Revisar logs en la ventana del servidor

### No puedo acceder al dashboard
1. Verificar que el servidor esté corriendo: http://127.0.0.1:8001/healthz
2. Intentar abrir manualmente: http://127.0.0.1:8001/ui/index.html
3. Revisar firewall/antivirus

### WhatsApp no se conecta
1. Verificar que Playwright esté instalado
2. Revisar logs del automator
3. Intentar login manual en WhatsApp Web

## Comandos Útiles

### PowerShell
```powershell
# Verificar estado del servidor
Invoke-RestMethod -Uri "http://127.0.0.1:8001/healthz"

# Ver configuración actual
Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/status"

# Reiniciar solo el panel admin
.\launcher_admin.ps1
```

### Python (desde el entorno virtual)
```bash
# Ejecutar migración manual
python migrate_sqlite.py

# Probar conexión LLM
python test_llm.py

# Análisis de conversaciones
python analyze_conversation.py
```

## Personalización

Puedes modificar:
- Diseño del dashboard: `web_ui/index.html`
- Lógica del API: `admin_panel.py`
- Comportamiento del automator: `whatsapp_automator.py`
- Configuración de arranque: `run_all.ps1`
