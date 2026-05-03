# API Reference

Base URL: `http://localhost:8003` (desarrollo) / `https://tu-dominio.com` (producción)

**Nota:** En producción `/docs` y `/redoc` están deshabilitados (`DISABLE_DOCS=true`). Para activarlos en desarrollo: `DISABLE_DOCS=false`.

---

## Autenticación

La mayoría de los endpoints `/api/*` requieren:
```
Authorization: Bearer <access_token>
```

Endpoints públicos (sin auth):
- `POST /api/auth/login`
- `GET /api/auth/refresh`
- `GET /api/calendar/oauth/google/callback`
- `GET /api/calendar/oauth/outlook/callback`

---

## Headers de seguridad y throttling

Todos los responses incluyen:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: ...`
- `X-Request-ID: <uuid>` — correlación de requests

Endpoints API incluyen además:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

Si se excede el límite: `429 Too Many Requests` con `Retry-After`.

---

## Modelo de errores

| Código | Significado |
|--------|-------------|
| `400` | Request inválido (body malformado, validación fallida) |
| `401` | Token ausente, inválido o expirado |
| `403` | Rol insuficiente (requiere admin) |
| `404` | Recurso no encontrado |
| `429` | Rate limit excedido |
| `503` | Servicio no disponible (DB o dependencia caída) |
| `500` | Error interno (mensaje sanitizado, sin stack trace) |

---

## Endpoints

### Sistema

#### `GET /healthz`
Health check completo del sistema. Sin autenticación.

Response `200` (todo OK):
```json
{
  "status": "ok",
  "components": {
    "database": {"status": "ok"},
    "redis": {"status": "ok"},
    "disk": {"status": "ok", "free_percent": 42.5},
    "memory": {"status": "ok", "available_percent": 38.2}
  }
}
```

Response `503` (componente caído):
```json
{"status": "unhealthy"}
```

#### `GET /metrics`
Métricas Prometheus. Sin autenticación.

#### `GET /`
Info básica de la app. Sin autenticación.

---

### Auth

#### `POST /api/auth/login`
Obtener access token y refresh token.

Body:
```json
{"username": "admin", "password": "tu_password"}
```

Response `200`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### `GET /api/auth/refresh`
Renovar access token usando el refresh token. Sin autenticación de Bearer, usa cookie o header `X-Refresh-Token`.

#### `GET /api/auth/me`
Información del usuario autenticado.

Response `200`:
```json
{
  "username": "admin",
  "role": "admin"
}
```

#### `POST /api/auth/logout`
Invalidar sesión actual.

#### `POST /api/auth/ws-token`
Obtener token especial para conexión WebSocket de métricas.

Response `200`:
```json
{"ws_token": "eyJ..."}
```

---

### WebSocket

#### `WS /ws/metrics`
Stream de métricas en tiempo real.

Flujo de autenticación:
1. Conectar al WebSocket
2. Enviar inmediatamente: `{"type": "auth", "token": "<ws_token>"}`
3. Recibir mensajes periódicos:

```json
{
  "type": "metrics",
  "timestamp": "2026-04-23T10:00:00Z",
  "queue_pending": 5
}
```

**Nota:** El token en query string está prohibido (cerrado con código 1008).

---

### Proveedores de IA

#### `GET /api/ai-models/available-providers`
Lista todos los proveedores configurados y su estado.

#### `GET /api/llm/providers`
Alias de available-providers.

#### `GET /api/ai-models/config`
Configuración actual de proveedores.

#### `POST /api/ai-models/config`
Actualizar configuración de un proveedor.

#### `POST /api/ai-models/test-connection`
Probar conexión con un proveedor específico.

Body:
```json
{"provider": "gemini", "message": "Hola, ¿funciona?"}
```

#### `POST /api/ai-models/custom-provider`
Agregar proveedor personalizado (URL OpenAI-compatible).

#### `DELETE /api/ai-models/custom-provider/{provider_name}`
Eliminar proveedor personalizado.

---

### Chat

#### `POST /api/chat/message`
Enviar mensaje y obtener respuesta de IA.

#### `GET /api/chats`
Listar todas las sesiones de chat.

#### `GET /api/chats/{chat_id}`
Detalle de una sesión de chat.

#### `PUT /api/chats/{chat_id}`
Actualizar datos de una sesión.

#### `POST /api/chats/{chat_id}/refresh-context`
Forzar recarga del contexto de un chat.

---

### Archivos y contextos

#### `GET /api/files/{filename}`
Leer archivo de contexto. `filename` puede ser: `ejemplo_chat`, `perfil`, `ultimo_contexto`.

#### `PUT /api/files/{filename}`
Actualizar archivo de contexto.

---

### Contactos

#### `GET /api/contacts`
Listar contactos.

#### `POST /api/contacts`
Crear contacto.

#### `PUT /api/contacts/{contact_id}`
Actualizar contacto.

#### `DELETE /api/contacts/{contact_id}`
Eliminar contacto.

---

### Campañas y mensajería

#### `GET /api/campaigns`
Listar campañas.

#### `POST /api/campaigns`
Crear campaña.

#### `GET /api/queue/pending`
Ver mensajes pendientes en la cola.

#### `POST /api/manual/send`
Enviar mensaje manual a un número.

Body:
```json
{"phone": "573001234567", "message": "Hola!"}
```

---

### WhatsApp

#### `GET /api/whatsapp/status`
Estado actual del runtime de WhatsApp.

Response `200`:
```json
{
  "mode": "web",
  "connected": true,
  "phone": "+573001234567"
}
```

#### `POST /api/whatsapp/start`
Iniciar runtime WhatsApp (solo admin).

#### `POST /api/whatsapp/stop`
Detener runtime WhatsApp (solo admin).

#### `POST /api/webhook/whatsapp`
Endpoint de webhook para WhatsApp Cloud API. Verificación con `X-Hub-Signature-256`.

---

### Calendario

#### `GET /api/calendar/status`
Estado de integración de calendario.

#### `GET /api/calendar/config`
Configuración actual del calendario.

#### `POST /api/calendar/config`
Actualizar configuración.

#### `GET /api/calendar/oauth/google/authorize`
Iniciar flujo OAuth Google Calendar.

#### `GET /api/calendar/oauth/google/callback`
Callback OAuth Google (sin auth, usado por Google).

#### `GET /api/calendar/oauth/outlook/authorize`
Iniciar flujo OAuth Outlook.

#### `GET /api/calendar/oauth/outlook/callback`
Callback OAuth Outlook.

#### `POST /api/calendar/google/credentials`
Configurar credenciales de servicio Google (service account).

---

### Sistema (solo admin)

#### `GET /api/system/check-processes`
Estado de procesos del sistema.

#### `POST /api/system/stop-all`
Detener todos los procesos no críticos.

---

### LM Studio (solo admin)

#### `GET /api/lmstudio/status`
Estado de LM Studio local.

#### `GET /api/lmstudio/models`
Modelos disponibles en LM Studio.

---

### Analytics y Monitoreo

#### `GET /api/analytics/summary`
Resumen de métricas de uso.

#### `GET /api/monitoring/status`
Estado detallado del sistema.

---

## Curl examples (5)

```bash
# 1) Health check
curl -fsS http://localhost:8003/healthz

# 2) Login y guardar token
TOKEN=$(curl -fsS -X POST http://localhost:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_PASSWORD"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 3) Usuario actual
curl -fsS http://localhost:8003/api/auth/me -H "Authorization: Bearer ${TOKEN}"

# 4) Listar chats
curl -fsS http://localhost:8003/api/chats -H "Authorization: Bearer ${TOKEN}"

# 5) Cola pendiente
curl -fsS http://localhost:8003/api/queue/pending -H "Authorization: Bearer ${TOKEN}"

# 6) Listar proveedores IA disponibles
curl -fsS http://localhost:8003/api/ai-models/available-providers \
  -H "Authorization: Bearer ${TOKEN}"

# 7) Estado WhatsApp
curl -fsS http://localhost:8003/api/whatsapp/status \
  -H "Authorization: Bearer ${TOKEN}"

# 8) Enviar mensaje manual
curl -fsS -X POST http://localhost:8003/api/manual/send \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"phone":"573001234567","message":"Mensaje de prueba"}'

# 9) WS token (para conectar WebSocket)
curl -fsS -X POST http://localhost:8003/api/auth/ws-token \
  -H "Authorization: Bearer ${TOKEN}"
```
