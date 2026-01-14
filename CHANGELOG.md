# 📋 Changelog

Todos los cambios importantes de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Planeado
- Integración con CRM (HubSpot, Salesforce)
- Sistema de plugins para extensiones
- Dashboard de métricas en tiempo real con WebSockets
- Soporte para múltiples idiomas en la UI

---

## [3.0.0] - 2024-01-14

### 🚀 ENTERPRISE FEATURES - Phases 0-7 Complete

#### Phase 0: Configuración Base y Tests
- **Pytest configurado**: `asyncio_mode = auto` para soporte completo de tests async
- **Tests corregidos**: 3 tests en `test_auth_system.py` ahora funcionando correctamente
- **Código limpiado**: Eliminada función duplicada `require_admin` en `auth_system.py`

#### Phase 1: Autenticación Unificada y Auditoría
- **Autenticación híbrida JWT + Legacy**: Soporte simultáneo para JWT y token legacy con flag `LEGACY_TOKEN_ENABLED`
- **Sistema de auditoría completo**: `src/services/audit_system.py` con modelo `AuditLog`
- **Endpoints de auditoría**: `/api/audit/logs` y `/api/audit/stats` para admin
- **Auditoría automática**: Login, logout, bulk_send, config_change, alert_create, alert_assign, alert_resolve
- **Tracking de IP**: Registro de IPs y user agents en todas las acciones

#### Phase 2: Cola de Mensajes y Scheduler
- **Sistema de cola unificado**: `src/services/queue_system.py` con modelo `QueuedMessage`
- **Respaldo JSON**: Compatible con `manual_queue.json` existente
- **Campañas masivas**: Modelo `Campaign` para seguimiento de envíos bulk
- **Scheduler worker**: `src/workers/scheduler_worker.py` como proceso separado con APScheduler
- **Endpoints de cola**: `/api/queue/pending`, `/api/queue/enqueue`, `/api/queue/{id}/status`
- **Endpoints de campañas**: `/api/campaigns` (GET/POST), `/api/campaigns/{id}` (GET/DELETE), pause/resume/cancel
- **Prioridades**: Sistema de prioridad (high/normal/low) para mensajes en cola

#### Phase 3: Sistema de Alertas Inteligente
- **Motor de reglas**: `src/services/alert_system.py` con 3 tipos (keyword, regex, sentiment)
- **Modelos Alert y AlertRule**: SQLAlchemy con severidades (high/medium/low) y estados (open/assigned/resolved)
- **Reglas por defecto**: Urgencias, quejas y palabras clave agresivas pre-configuradas
- **Endpoints completos**: `/api/alerts` CRUD, `/api/alerts/{id}/assign`, `/api/alerts/{id}/resolve`
- **Gestión de reglas**: `/api/alert-rules` para crear/editar/eliminar reglas
- **Webhooks**: Notificaciones configurables via `ALERT_WEBHOOK_URL`

#### Phase 4: WhatsApp Dual Mode (Web + Cloud API)
- **Abstracción de providers**: `src/services/whatsapp_provider.py` con interfaz `WhatsAppProvider`
- **Mensajes normalizados**: `NormalizedMessage` y `SendResult` para unificación
- **WhatsApp Web Provider**: `src/services/whatsapp_web_provider.py` wrapper para Playwright existente
- **WhatsApp Cloud Provider**: `src/services/whatsapp_cloud_provider.py` con Meta Graph API v17
- **DualProvider**: Routing inteligente con fallback automático (primary/backup)
- **Factory pattern**: `WhatsAppProviderFactory.create_from_env()` según `WHATSAPP_MODE`
- **Webhooks Cloud API**: `/webhooks/whatsapp` GET (verify) y POST (receive)
- **Descarga de media**: Soporte para images, videos, audio, documents de Cloud API

#### Phase 5: Transcripción de Audio
- **faster-whisper integrado**: `src/services/audio_transcriber.py` v1.0.0
- **Caché inteligente**: SHA256-based cache en `data/transcription_cache/`
- **Modelos configurables**: tiny/base/small/medium/large via `WHISPER_MODEL_SIZE`
- **Límites de tamaño**: `MAX_AUDIO_FILE_SIZE_MB` configurable (default 25MB)
- **Integración automática**: CloudProvider transcribe audios automáticamente
- **Opcional**: Flag `AUDIO_TRANSCRIPTION_ENABLED` para activar/desactivar

#### Phase 6: Dockerización Completa
- **Multi-container setup**: 4 servicios en `docker-compose.yml`
- **Dockerfile API**: Python 3.11-slim para FastAPI/admin panel (puerto 8003)
- **Dockerfile.worker-web**: Playwright con chromium para WhatsApp Web automation
- **Dockerfile.scheduler**: Worker separado para APScheduler con scheduled.json
- **PostgreSQL containerizado**: postgres:15-alpine con volumes persistentes
- **Health checks**: Endpoint `/healthz` y checks de postgres
- **Volumes**: postgres_data, whatsapp-profile, data/, logs/
- **Network**: Bridge network `chatbot-network` para comunicación inter-contenedores

#### Phase 7: UI Enterprise Updates
- **alerts.html**: Dashboard completo de alertas con filtros, asignación, resolución
- **index.html mejorado**: 4 nuevos cards (Alertas, Campañas, Scheduler, WhatsApp Provider)
- **Funciones JS**: `showCampaigns()`, `showScheduler()`, `showWhatsAppProvider()`
- **Auto-refresh**: Actualización automática cada 30 segundos
- **Estadísticas visuales**: Cards con totales, abiertas, asignadas, resueltas
- **Modales de acción**: Asignar alertas y resolver con notas
- **Provider status**: Visualización de modo activo (web/cloud/both) con estado de ambos

#### Configuración y Variables de Entorno
- **JWT_SECRET**: Nuevo requerimiento para tokens seguros
- **JWT_EXPIRE_MINUTES**: Duración de tokens (default 1440 = 24h)
- **LEGACY_TOKEN_ENABLED**: Flag para soporte híbrido (default true)
- **WHATSAPP_MODE**: web/cloud/both para selección de provider
- **WHATSAPP_CLOUD_TOKEN**: Token de Meta Business Platform
- **WHATSAPP_PHONE_ID**: Phone ID de Cloud API
- **VERIFY_TOKEN**: Token para verificación de webhooks
- **AUDIO_TRANSCRIPTION_ENABLED**: Activar transcripción (default false)
- **WHISPER_MODEL_SIZE**: Modelo de Whisper (default base)
- **ALERTS_ENABLED**: Sistema de alertas (default true)
- **ALERT_WEBHOOK_URL**: URL para notificaciones de alertas
- **AUDIT_ENABLED**: Sistema de auditoría (default true)
- **DATABASE_URL**: PostgreSQL opcional (default SQLite)

### 🐛 Corregido
- Tests async funcionando correctamente con pytest-asyncio
- Función duplicada `require_admin` eliminada
- Logger no definido en `admin_panel.py`

### 🧪 Testing
- **test_queue_system.py**: 10 tests para cola y campañas
- **test_alert_system.py**: 11 tests para alertas y reglas
- **test_audio_transcriber.py**: 9 tests para transcripción con mocks
- **test_whatsapp_providers.py**: 15 tests para providers y DualProvider

### 📚 Dependencias Agregadas
- **faster-whisper==1.0.0**: Transcripción de audio local

---

## [2.0.0] - 2026-01-13

### 🚀 Agregado

#### Arquitectura Mejorada
- **Nueva estructura modular**: Reorganización completa del código en `src/services/`, `src/models/`
- **Sistema de cache con Redis**: Caché inteligente para configuraciones y respuestas LLM
- **Rate limiting y circuit breaker**: Protección avanzada contra sobrecargas y APIs caídas
- **Soporte PostgreSQL**: Base de datos robusta para producción con pool de conexiones
- **Validación con Pydantic**: Modelos completos para validación de datos de entrada

#### Seguridad Mejorada
- **Autenticación bcrypt**: Reemplazo de SHA256 simple por hashing seguro con salt
- **JWT mejorado**: Tokens con validación robusta, rotación y configuración desde variables de entorno
- **CORS configurable**: Dominios permitidos configurables por variables de entorno
- **Variables de entorno obligatorias**: JWT_SECRET requerido, sin valores por defecto inseguros
- **Manejo seguro de errores**: Logs detallados sin exponer información sensible

#### APIs y Proveedores
- **Claude API implementada**: Integración completa con Anthropic Claude usando formato correcto
- **Sistema multi-API mejorado**: Fallback inteligente con modelos gratuitos/pagos
- **xAI Grok support**: Soporte para Grok de Elon Musk en beta
- **LM Studio optimizado**: Mejor integración con modelos locales
- **Rate limiting por proveedor**: Protección individual para cada API

#### Testing y Calidad
- **Suite completa de tests**: Tests unitarios para auth, LLM, cache y más
- **Coverage configurado**: Objetivo del 60% mínimo con reportes HTML
- **Pytest configurado**: Configuración completa con fixtures y markers
- **CI/CD ready**: Estructura preparada para integración continua

#### DevOps y Escalabilidad
- **Docker support**: Configuración lista para contenedores
- **Environment management**: `.env.example` completo con todas las opciones
- **Database migrations**: Soporte para migración SQLite → PostgreSQL  
- **Monitoring hooks**: Preparado para Prometheus/Grafana
- **Health checks**: Endpoints de salud para todas las dependencias

### 🔧 Cambiado

#### Configuración
- **Reorganización de archivos**: `payload.json`, `schema.json` movidos a `config/`
- **Importaciones actualizadas**: Nuevas rutas para todos los módulos
- **CORS más estricto**: Solo dominios específicos por defecto
- **JWT expiration configurable**: Tiempos de expiración configurables por rol

#### APIs
- **Rate limiting global**: Aplicado a todos los endpoints por defecto
- **Respuestas estandarizadas**: Formato consistente para errores y éxitos
- **Validación de input**: Pydantic models para todos los endpoints
- **Headers mejorados**: Rate limit info en response headers

#### Base de Datos
- **Connection pooling**: Pool configurado para múltiples conexiones
- **Context managers**: Uso de `with` statements para sesiones
- **Error handling**: Rollback automático en errores
- **Migration support**: Herramientas para migrar entre databases

### 🐛 Arreglado

#### Seguridad
- **Credenciales hardcoded eliminadas**: Todo desde variables de entorno
- **Password hashing mejorado**: bcrypt en lugar de SHA256 simple
- **JWT secret validation**: Falla si no está configurado apropiadamente
- **SQL injection protection**: Queries parametrizadas en toda la aplicación

#### Funcionalidad
- **Claude API funcionando**: Implementación correcta del formato de Anthropic
- **Error handling consistente**: Manejo uniforme de errores en toda la app
- **Memory leaks**: Limpieza apropiada de conexiones y recursos
- **Race conditions**: Synchronization mejorada en operaciones async

#### Performance
- **Database queries optimizadas**: Índices y queries más eficientes  
- **Cache hits mejorados**: Estrategia de cache más inteligente
- **Memory usage**: Uso de memoria optimizado para long-running processes
- **Response times**: Tiempos de respuesta más rápidos con cache

### 🗑️ Removido

#### Código Deprecated
- **app.py duplicado**: Archivo confuso eliminado, solo `main_server.py`
- **scheduler.py vacío**: Archivo sin implementación removido
- **Usuarios hardcoded**: Sistema de usuarios fijos reemplazado por configuración
- **Password por defecto**: Eliminados passwords inseguros por defecto

#### Dependencias
- **Dependencias no usadas**: Cleanup de requirements.txt
- **Código muerto**: Funciones y clases no utilizadas eliminadas
- **Debug prints**: Prints de debug reemplazados por logging apropiado

### ⚠️ Breaking Changes

#### Configuración Requerida
```bash
# OBLIGATORIO: Configurar JWT secret
export JWT_SECRET="tu-clave-secreta-minimo-32-caracteres"

# OBLIGATORIO: Configurar passwords de admin
export ADMIN_PASSWORD="tu-password-seguro"
export OPERATOR_PASSWORD="password-operador"

# RECOMENDADO: PostgreSQL para producción
export DATABASE_URL="postgresql://user:pass@localhost:5432/chatbot"
```

#### Imports Cambiados
```python
# Antes
from auth_system import auth_manager
from multi_provider_llm import MultiProviderLLM

# Ahora
from src.services.auth_system import auth_manager
from src.services.multi_provider_llm import MultiProviderLLM
```

#### API Changes
- Endpoints de autenticación requieren headers específicos
- Rate limiting aplicado por defecto (puede requerir ajustes)
- Validación más estricta en todos los endpoints

### 🔧 Migration Guide

#### De 1.x a 2.0

1. **Actualizar configuración**:
   ```bash
   cp .env.example .env
   # Configurar todas las variables requeridas
   ```

2. **Actualizar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Migrar base de datos**:
   ```bash
   python -c "from src.models.admin_db import initialize_schema; initialize_schema()"
   ```

4. **Actualizar imports** en código personalizado según nueva estructura

5. **Testing**:
   ```bash
   pytest tests/ --cov=src
   ```

---

## [1.2.0] - 2025-12-15

### Agregado
- Dashboard web moderno con Chart.js
- Sistema de analytics básico con SQLite
- Chat de prueba en tiempo real con WebSockets
- Configurador visual de negocio
- Templates para floristería, panadería, bufete legal

### Cambiado
- UI mejorada con diseño responsive
- Mejor manejo de errores en frontend
- Logging más detallado

### Arreglado
- Reconexión automática en WebSockets
- Manejo de sesiones de chat mejorado
- Cleanup de recursos al cerrar aplicación

---

## [1.1.0] - 2025-11-20

### Agregado
- Soporte para múltiples proveedores LLM
- Fallback automático entre APIs
- Sistema básico de autenticación
- Panel de administración web

### Cambiado
- Refactoring de sistema de configuración
- Mejoras en documentación

---

## [1.0.0] - 2025-10-15

### Agregado
- Release inicial del chatbot
- Integración básica con WhatsApp Web
- Soporte para OpenAI GPT
- Sistema de configuración JSON
- Documentación básica

---

## 📝 Tipos de Cambios

- `Agregado` para nuevas funcionalidades
- `Cambiado` para cambios en funcionalidades existentes  
- `Deprecated` para funcionalidades que serán removidas
- `Removido` para funcionalidades removidas
- `Arreglado` para bug fixes
- `Seguridad` para vulnerabilidades

## 🏷️ Versionado

Este proyecto usa [Semantic Versioning](https://semver.org/):

- **MAJOR**: Cambios incompatibles en API
- **MINOR**: Funcionalidad agregada compatible hacia atrás  
- **PATCH**: Bug fixes compatibles hacia atrás

## 📚 Links de Referencia

- [Repositorio](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm)
- [Issues](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm/issues)
- [Pull Requests](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm/pulls)
- [Releases](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm/releases)
