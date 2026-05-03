# WhatsApp AI Chatbot Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7+-red.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

**Chatbot WhatsApp con IA multi-proveedor, agenda de citas, panel de administración y automatización vía Playwright**

[Inicio rápido](#inicio-rápido) · [Proveedores de IA](#proveedores-de-ia) · [Arquitectura](#arquitectura) · [Docker](#despliegue-con-docker) · [Documentación](#documentación)

</div>

---

## Qué hace este proyecto

- Recibe mensajes de WhatsApp (vía Web automation con Playwright o vía WhatsApp Cloud API)
- Genera respuestas usando IA con fallback automático entre proveedores
- Gestiona agenda de citas con integración a Google Calendar y Outlook
- Expone un panel de administración web con autenticación JWT
- Envía mensajes manuales, campañas y notificaciones programadas

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| API | FastAPI 0.104 + Uvicorn + Gunicorn |
| Auth | JWT (PyJWT) + bcrypt + Fernet |
| Base de datos | PostgreSQL 15 (producción) / SQLite (desarrollo) |
| Migraciones | Alembic |
| Caché | Redis 7 con fallback en memoria |
| IA | Multi-proveedor con fallback automático |
| WhatsApp Web | Playwright (Chromium headless) |
| WhatsApp Cloud | Meta Business Cloud API |
| Calendario | Google Calendar API + Microsoft Outlook |
| Docker | 4 servicios: app, worker-web, scheduler, redis + postgres |
| Python | `python:3.13.3-slim` (pinned en Dockerfile) |

---

## Proveedores de IA

El sistema soporta 7 proveedores con fallback automático configurable:

| Proveedor | Modelo recomendado (Abril 2026) | Costo | Tier gratuito |
|-----------|--------------------------------|-------|---------------|
| **Google Gemini** | `gemini-2.5-flash-lite` | $0.10–0.30/1M tokens | Sí |
| **OpenRouter** | `google/gemini-2.5-flash-lite:free` | $0 (200 req/día) | Sí (29 modelos) |
| **xAI Grok** | `grok-4-1-fast` | $0.20/1M tokens | No |
| **OpenAI** | `gpt-5.4-mini` | $0.75/1M tokens | No |
| **Anthropic Claude** | `claude-haiku-4-5-20251001` | $1/1M tokens | No |
| **Ollama** | `qwen3:4b` | Gratis (local) | Local |
| **LM Studio** | `qwen3.5-4b-q4_k_m` | Gratis (local) | Local |

Orden de fallback configurado en `.env` con `AI_FALLBACK_ORDER`.

> **Mínimo requerido para funcionar:** una `GEMINI_API_KEY` o una `OPENROUTER_API_KEY` (ambas gratuitas).

---

## Inicio rápido

### Requisitos

- Python 3.11+
- Docker + Docker Compose (para producción)
- Git

### Instalación local (desarrollo)

```bash
# 1. Clonar
git clone <repo-url>
cd chatbot-whatsapp-llm

# 2. Entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows

# 3. Dependencias
pip install -r requirements.txt

# 4. Configurar entorno
cp .env .env.local             # .env ya tiene valores seguros generados
# Editar .env: agregar al menos una API key de IA
```

### Variables de entorno mínimas

```env
# Ya generadas automáticamente en .env:
JWT_SECRET=<generado>
ADMIN_PASSWORD=<generado>
POSTGRES_PASSWORD=<generado>
REDIS_PASSWORD=<generado>

# Agregar al menos UNA de estas (Gemini es la más fácil — tier gratuito):
GEMINI_API_KEY=tu_key        # aistudio.google.com/apikey
OPENROUTER_API_KEY=tu_key    # openrouter.ai/keys (sin tarjeta)

# Modelos ya configurados por defecto:
GEMINI_MODEL=gemini-2.5-flash-lite
OPENROUTER_MODEL=google/gemini-2.5-flash-lite:free
```

### Lanzar en desarrollo

```bash
# Con SQLite (sin necesidad de PostgreSQL ni Redis)
python -m uvicorn admin_panel:app --host 127.0.0.1 --port 8003 --reload
```

Acceder a: `http://localhost:8003/ui/index.html`

> **Nota:** En producción `DISABLE_DOCS=true` deshabilita `/docs`. Para desarrollo, cambiar a `DISABLE_DOCS=false`.

---

## Despliegue con Docker

```bash
# Configurar .env con todas las variables (ver arriba)
# Asegurarse de tener POSTGRES_PASSWORD y REDIS_PASSWORD configurados

docker compose up -d

# Verificar salud
curl http://localhost:8003/healthz

# Ver logs
docker compose logs -f app
```

Los 5 servicios levantados:

```
app          → API + Panel admin     (puerto 8003)
worker-web   → WhatsApp Web automation
scheduler    → Tareas programadas en background
postgres     → Base de datos
redis        → Caché y rate limiting
```

### Migraciones de base de datos

Las migraciones se ejecutan automáticamente al iniciar si `AUTO_MIGRATE=true` (default).

Para ejecutarlas manualmente:

```bash
docker compose run --rm app alembic upgrade head
```

---

## Modelos locales — Hardware Acer Nitro (RTX 3050 4GB + 16GB RAM)

Con Ollama (recomendado):

```bash
# Instalar: https://ollama.com
ollama pull qwen3:4b          # 2.75GB VRAM — cabe completo en GPU
ollama pull qwen3.5:4b        # versión mejorada (Abril 2026)
ollama pull phi4-mini         # alternativa liviana
```

Con LM Studio (interfaz gráfica):
- Buscar `qwen3.5-4b-q4_k_m` — 2.7GB VRAM, excelente para chat
- Buscar `phi-4-mini-q4_k_m` — 2.5GB VRAM

Con cualquiera de los dos, descomentar en `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
# o para LM Studio:
LM_STUDIO_URL=http://127.0.0.1:1234/v1
LM_STUDIO_MODEL=qwen3.5-4b-q4_k_m
```

---

## Configuración de WhatsApp

### Modo Web (Playwright) — Default

No requiere cuenta Business. Usa el navegador para conectarse con un QR.

```env
WHATSAPP_MODE=web
KEEP_AUTOMATOR_OPEN=true
```

### Modo Cloud API (Meta Business)

Requiere cuenta Meta Business verificada.

```env
WHATSAPP_MODE=cloud
WHATSAPP_CLOUD_TOKEN=tu_token
WHATSAPP_PHONE_ID=tu_phone_id
WHATSAPP_VERIFY_TOKEN=tu_verify_token
WHATSAPP_APP_SECRET=tu_app_secret    # Obligatorio para modo cloud
```

---

## Seguridad

- JWT con expiración + refresh tokens
- bcrypt para contraseñas
- Fernet para encriptación de datos sensibles
- Rate limiting global por endpoint (Redis backend)
- Circuit breaker para APIs externas
- Headers de seguridad: CSP, X-Frame-Options, HSTS, CORP, COOP
- Audit log de eventos de seguridad
- Docs API (`/docs`) deshabilitados por defecto en producción

Ver [SECURITY.md](SECURITY.md) para la política completa.

---

## Testing

```bash
# Suite completa
pytest tests/ --cov=src --cov-report=html

# Solo tests rápidos
pytest tests/ -q -x

# Linting
ruff check .
ruff format --check .
```

---

## Arquitectura

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para el diagrama completo de componentes y flujo de datos.

---

## Documentación

| Archivo | Contenido |
|---------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diagrama de sistema, componentes, variables |
| [SECURITY.md](SECURITY.md) | Política de seguridad, controles activos |
| [RUNBOOK.md](RUNBOOK.md) | Procedimientos operativos, deployments, backups |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Diagnóstico de problemas frecuentes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guía para contribuir |
| [docs/API.md](docs/API.md) | Referencia de endpoints |
| [docs/BETA_GO_LIVE_CHECKLIST.md](docs/BETA_GO_LIVE_CHECKLIST.md) | Checklist antes de lanzar |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Guía de despliegue en cloud |

---

## Licencia

MIT License — ver [LICENSE](LICENSE) si existe, o contactar al autor.
