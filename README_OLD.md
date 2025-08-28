# Chatbot WhatsApp con Panel de Administración

## Características Implementadas

### ✅ Panel de Administración
- API FastAPI en `admin_panel.py` con autenticación JWT básica
- Gestión de modelos de LLM
- Configuración de reglas de enrutamiento
- Administración de contactos permitidos
- Gestión de contextos diarios y por usuario
- Auditoría de acciones

### ✅ Persistencia de Datos
- Migración de SQLite legacy a SQLAlchemy ORM
- Esquema completo con tablas: conversations, models, rules, allowed_contacts, user_contexts, daily_contexts, audit_log
- Script de migración `migrate_sqlite.py` para preservar datos existentes

### ✅ Protección de Datos
- Cifrado con Fernet para campos sensibles (contact_id, context)
- Módulo `crypto.py` para manejo de cifrado/descifrado
- Clave de cifrado almacenada en `data/fernet.key` o variable de entorno `FERNET_KEY`

### ✅ Simulación de Escritura
- Implementada función `send_reply_with_typing()` en `whatsapp_automator.py`
- Configurable con variable de entorno `TYPING_PER_CHAR` (default: 0.05s/carácter)
- Advertencia automática si se configura >1s/carácter

### ✅ Control de Enrutamiento de Modelos
- `ModelManager` clase para selección dinámica de modelos
- Reglas configurables: cada X mensajes usar modelo específico (ej. modelo razonador)
- Contador de mensajes por conversación

### ✅ Control de Contactos
- Verificación de `AllowedContact` antes de responder automáticamente
- Si contacto no permitido, se crea log de auditoría (implementar notificación manual)
- Cifrado de contact_id en base de datos

### ✅ Contextos Personalizables
- Tabla `user_contexts` para contexto específico por usuario
- Tabla `daily_contexts` para contexto diario global
- API endpoints para agregar/editar contextos desde panel admin

## Instalación y Configuración

```bash
# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar migración de datos
python migrate_sqlite.py

# Iniciar panel de administración
uvicorn admin_panel:app --reload --port 8001

# Iniciar automatización de WhatsApp
python whatsapp_automator.py
```

## Configuración de Variables de Entorno

```bash
# .env
AUTOMATION_ACTIVE=true
TYPING_PER_CHAR=0.05
FERNET_KEY=your-base64-encoded-key
DATABASE_URL=sqlite:///chatbot_context.db
LOG_PATH=logs/automation.log
```

## Uso del Panel de Administración

### Autenticación

## Two-agent pipeline (Responder + Reasoner)

- New DB tables manage contacts, profiles, counters and strategies.
- Use `manage_contacts.py` to add a contact and set the goal/context:

```pwsh
python manage_contacts.py --chat-id "+57XXXXXXXXXX" --name "Nombre" --enable --initial-context "nos conocimos en X" --objective "cerrar cita" --instructions "tono breve" --ready
```

- The responder injects: initial context, objective and the active strategy into system messages on every reply.
- After every 10 assistant replies (config `STRATEGY_REFRESH_EVERY`), the reasoner runs and writes a new active strategy version.
- Configure:
  - REQUIRE_CONTACT_PROFILE=true
  - STRATEGY_REFRESH_EVERY=10
  - REASONER_PAYLOAD_PATH=payload_reasoner.json

### Endpoints Principales
- `POST /models` - Crear modelo LLM
- `GET /models` - Listar modelos
- `POST /rules` - Crear regla de enrutamiento
- `POST /contacts` - Agregar contacto permitido
- `GET /contacts` - Listar contactos

## Arquitectura

```
├── models.py              # Modelos SQLAlchemy
├── admin_db.py           # Conexión y sesiones DB
├── admin_panel.py        # API FastAPI
├── model_manager.py      # Lógica de enrutamiento
├── crypto.py             # Cifrado/descifrado
├── migrate_sqlite.py     # Migración de datos
├── chat_sessions.py      # Interfaz de persistencia (actualizada)
├── whatsapp_automator.py # Automatización principal (mejorada)
└── tests/               # Tests unitarios
```

## Próximos Pasos (Roadmap)

1. **UI Web para Panel Admin** - Interface gráfica con React/Vue
2. **Notificaciones Push** - Para nuevas conversaciones no permitidas
3. **Dashboard Analytics** - Métricas de uso y conversaciones
4. **Integración con múltiples LLM providers** - OpenAI, Claude, etc.
5. **Backup automático** - Exportación regular de datos
6. **2FA y roles de usuario** - Seguridad mejorada

## Tests

```bash
# Ejecutar tests unitarios
pytest tests/test_model_manager.py -v

# Test manual del panel admin
curl -X POST "http://localhost:8001/models" \
  -H "Content-Type: application/json" \
  -d '{"token": "admintoken", "username": "admin"}' \
  -d '{"name": "gpt-4", "provider": "openai", "active": true}'
```

## Seguridad

- Cifrado de datos sensibles con Fernet
- Validación de contactos permitidos
- Auditoría de acciones administrativas
- Logs enmascarados (números de teléfono ocultos)

## Licencia

Proyecto privado - Todos los derechos reservados.
