# 🚀 Quick Start Guide - Enterprise Features

## ⚡ Inicio Rápido (5 minutos)

### 1. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
# Copiar template
cp .env.example .env

# Editar con tus valores
# Mínimo requerido:
JWT_SECRET=tu-secreto-super-seguro-de-al-menos-32-caracteres
LEGACY_API_TOKEN=tu-token-actual
```

### 3. Ejecutar Tests
```bash
# Windows PowerShell
.\run_tests.ps1

# O directamente
pytest tests/ -v
```

### 4. Iniciar Servidor
```bash
python admin_panel.py
```

### 5. Abrir Panel
```
http://localhost:8003
```

---

## 🐳 Inicio con Docker (Recomendado para Producción)

### 1. Configurar .env
```bash
cp .env.example .env
# Editar .env con valores reales
```

### 2. Levantar Servicios
```bash
docker-compose up --build
```

### 3. Acceder
- **Panel Admin**: http://localhost:8003
- **API Docs**: http://localhost:8003/docs
- **PostgreSQL**: localhost:5432

### Servicios Incluidos:
- ✅ **app**: FastAPI + Admin Panel (puerto 8003)
- ✅ **postgres**: Base de datos persistente
- ✅ **worker-web**: WhatsApp Web automation (Playwright)
- ✅ **scheduler**: Programación de mensajes (APScheduler)

---

## 📋 Checklist Post-Instalación

### Validación Automática
```bash
python validate_installation.py
```

### Validación Manual
- [ ] Python 3.11+ instalado
- [ ] Todas las dependencias instaladas (`pip list`)
- [ ] Archivo `.env` configurado
- [ ] Tests pasando (`pytest tests/ -v`)
- [ ] Servidor inicia sin errores
- [ ] Panel accesible en http://localhost:8003

---

## 🎯 Features Implementadas

### ✅ Phase 0: Tests & Config
- pytest configurado con asyncio
- 17+ tests funcionando

### ✅ Phase 1: Auth & Audit
- JWT + Legacy hybrid authentication
- Sistema de auditoría completo
- `/api/auth/login`, `/api/audit/logs`

### ✅ Phase 2: Queue & Scheduler
- Cola unificada de mensajes
- Campañas masivas
- Scheduler worker separado
- `/api/queue/*`, `/api/campaigns/*`

### ✅ Phase 3: Alerts
- Motor de reglas inteligente
- Detección automática
- Asignación y resolución
- `/api/alerts/*`, `/api/alert-rules/*`

### ✅ Phase 4: WhatsApp Dual Mode
- WhatsApp Web (Playwright)
- WhatsApp Cloud API (Meta)
- Dual mode con fallback
- `/webhooks/whatsapp`, `/api/whatsapp/provider/status`

### ✅ Phase 5: Audio Transcription
- faster-whisper local
- Cache inteligente
- Integración automática con Cloud API

### ✅ Phase 6: Docker
- Multi-container setup
- PostgreSQL containerizado
- Health checks
- Volumes persistentes

### ✅ Phase 7: UI Enterprise
- Dashboard de alertas (`alerts.html`)
- Panel principal actualizado
- 8 módulos funcionales
- Auto-refresh

---

## 📚 Documentación Completa

- **[ENTERPRISE_FEATURES.md](docs/ENTERPRISE_FEATURES.md)**: Guía detallada de 500+ líneas
- **[CHANGELOG.md](CHANGELOG.md)**: Historial completo de cambios
- **[API.md](docs/API.md)**: Documentación de endpoints
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)**: Guía de deployment

---

## 🧪 Testing

### Ejecutar Todos los Tests
```bash
pytest tests/ -v
```

### Tests por Módulo
```bash
pytest tests/test_auth_system.py -v          # Autenticación
pytest tests/test_queue_system.py -v         # Cola y campañas
pytest tests/test_alert_system.py -v         # Alertas
pytest tests/test_audio_transcriber.py -v    # Transcripción
pytest tests/test_whatsapp_providers.py -v   # WhatsApp providers
```

### Coverage Report
```bash
pytest tests/ --cov=src --cov-report=html
# Abrir htmlcov/index.html
```

---

## 🔧 Configuración Básica

### Variables Críticas (.env)
```bash
# JWT Authentication
JWT_SECRET=cambiar-por-secreto-seguro-minimo-32-caracteres
JWT_EXPIRE_MINUTES=1440

# Legacy Support
LEGACY_TOKEN_ENABLED=true
LEGACY_API_TOKEN=tu-token-actual

# WhatsApp Mode
WHATSAPP_MODE=both  # web | cloud | both

# WhatsApp Cloud API (si WHATSAPP_MODE=cloud o both)
WHATSAPP_CLOUD_TOKEN=EAAxxxxxxxxxxxx
WHATSAPP_PHONE_ID=123456789
VERIFY_TOKEN=mi-token-secreto-para-webhooks

# Audio Transcription (opcional)
AUDIO_TRANSCRIPTION_ENABLED=true
WHISPER_MODEL_SIZE=base  # tiny | base | small | medium | large

# Alerts (opcional)
ALERTS_ENABLED=true
ALERT_WEBHOOK_URL=https://tu-webhook.com/alerts

# Database (opcional, default SQLite)
DATABASE_URL=postgresql://user:pass@localhost:5432/chatbot_db
```

---

## 🆘 Troubleshooting

### Tests fallan por "No module named 'jwt'"
```bash
pip install PyJWT aiohttp
```

### "cannot import name 'Base' from 'models'"
✅ Ya corregido en última versión (imports actualizados)

### WhatsApp Cloud API no recibe webhooks
1. URL debe ser HTTPS (usa ngrok en desarrollo)
2. Verificar `VERIFY_TOKEN` coincide en Meta y .env
3. Verificar firewall permite POST desde Meta IPs

### Docker no inicia
```bash
# Verificar .env existe
cp .env.example .env

# Reconstruir sin cache
docker-compose build --no-cache
docker-compose up
```

---

## 📞 Soporte

- **Issues**: [GitHub Issues](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm/issues)
- **Documentación**: `docs/` folder
- **Examples**: Ver archivos de test para ejemplos de uso

---

## 🎉 ¡Todo Listo!

Tu sistema enterprise está completamente configurado con:
- ✅ Autenticación híbrida JWT + Legacy
- ✅ Sistema de auditoría
- ✅ Cola de mensajes y campañas
- ✅ Alertas inteligentes
- ✅ WhatsApp dual mode (Web + Cloud)
- ✅ Transcripción de audio
- ✅ Docker ready
- ✅ UI enterprise completa

**Próximo paso**: Abre http://localhost:8003 y explora el panel! 🚀
