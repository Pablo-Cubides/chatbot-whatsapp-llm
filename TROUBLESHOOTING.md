# Troubleshooting Operacional

Guía de resolución rápida para incidentes frecuentes.

---

## 0) Checklist universal antes de empezar

```bash
docker compose ps
docker compose logs --since=15m app
docker compose logs --since=15m worker-web
docker compose logs --since=15m scheduler
curl -i http://localhost:8003/healthz
```

---

## 1) `401` en endpoints protegidos

**Árbol de decisión:**
- ¿Falla solo un usuario? → revisar credenciales y expiración de token
- ¿Falla para todos? → revisar que `JWT_SECRET` no cambió entre reinicios

```bash
curl -i http://localhost:8003/api/auth/me -H "Authorization: Bearer <token>"
```

**Si el token expiró:** hacer login nuevamente con `POST /api/auth/login` y usar el nuevo `access_token`.

---

## 2) Login bloqueado o rate limit excesivo

```bash
docker compose logs --since=30m app | grep -i "SECURITY_LOGIN_FAILED\|lockout\|rate limit"
```

**Acción:** identificar IP abusiva. Ajustar límites solo con change control.

---

## 3) WebSocket de métricas no conecta

```bash
curl -i -X POST http://localhost:8003/api/auth/ws-token \
  -H "Authorization: Bearer <access_token>"
```

**Causas típicas:**
- Token enviado en query string en vez de en el primer mensaje JSON (rechazado con código 1008)
- Scope inválido en el token WS
- Token WS expirado — obtener uno nuevo

**Flujo correcto:**
1. Conectar al WS
2. Enviar como primer mensaje: `{"type": "auth", "token": "<ws_token>"}`

---

## 4) `/healthz` responde `503`

```bash
docker compose logs --tail=200 app
docker compose exec postgres pg_isready -U ${POSTGRES_USER:-chatbot}
```

**Acción:** si PostgreSQL está unhealthy, reiniciarlo y validar `DATABASE_URL`.

---

## 5) Error de conexión a PostgreSQL

```bash
docker compose exec postgres psql \
  -U ${POSTGRES_USER:-chatbot} \
  -d ${POSTGRES_DB:-chatbot} \
  -c "SELECT 1"
```

**Causas:**
- `POSTGRES_PASSWORD` incorrecto o no configurado en `.env`
- El contenedor de postgres aún no terminó de iniciar — esperar el health check
- `DATABASE_URL` apunta a host incorrecto (usar `postgres` como hostname dentro de Docker)

---

## 6) Redis no responde

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

**Esperado:** `PONG`

**Causas:**
- `REDIS_PASSWORD` en `.env` no coincide con el configurado en `docker-compose.yml`
- Contenedor redis no está running: `docker compose up -d redis`

**Nota:** si Redis no responde, la app continúa funcionando pero sin caché (fallback en memoria). El rate limiting también cae a modo en memoria.

---

## 7) Respuestas LLM lentas o fallidas

```bash
docker compose logs --since=20m app | grep -i "provider\|fallback\|timeout\|circuit\|openrouter\|gemini"
```

**Diagnóstico por proveedor:**

| Síntoma | Causa probable | Acción |
|---------|---------------|--------|
| `Gemini API Error (429)` | Rate limit gratuito alcanzado | Activar fallback o agregar OpenRouter |
| `OpenRouter Error (429)` | 200 req/día agotados | Esperar reset diario o usar modelo de pago |
| `OpenRouter Error (402)` | Créditos insuficientes para modelo de pago | Usar modelo `:free` o recargar créditos |
| `Circuit breaker abierto` | Proveedor falló múltiples veces | Esperar recovery (60s) o reiniciar app |
| Respuesta muy lenta (>10s) | Modelo local (Ollama/LM Studio) lento | Normal para modelos locales; usar modelo cloud |

**Verificar fallback order:**
```bash
grep AI_FALLBACK_ORDER .env
# Debe incluir al menos un proveedor con API key configurada
```

**Verificar API keys:**
```bash
# Probar proveedor específico
curl -X POST http://localhost:8003/api/ai-models/test-connection \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"provider":"gemini","message":"test"}'
```

---

## 8) OpenRouter no funciona

**Verificar configuración:**
```bash
grep OPENROUTER .env
# Debe tener OPENROUTER_API_KEY, OPENROUTER_MODEL
```

**Causas frecuentes:**
- El modelo tiene sufijo `:free` pero agotó los 200 req/día — el reset es a medianoche UTC
- El modelo sin `:free` requiere créditos en la cuenta de OpenRouter
- `OPENROUTER_API_KEY` inválida — verificar en `openrouter.ai/keys`
- `OPENROUTER_MODEL` incorrecto — usar formato `proveedor/modelo:free` ej: `google/gemini-2.5-flash-lite:free`

**Listar modelos gratuitos disponibles en OpenRouter:**
```bash
curl -fsS https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data'] if ':free' in m['id']]"
```

---

## 9) Ollama local no responde

**Verificar que Ollama está corriendo:**
```bash
curl http://localhost:11434/api/version
```

**Verificar que el modelo está descargado:**
```bash
ollama list
# Si qwen3:4b no aparece:
ollama pull qwen3:4b
```

**Verificar GPU utilizada:**
```bash
ollama ps  # muestra modelos cargados y si usan GPU o CPU
```

**Si la respuesta es muy lenta (>30s):** el modelo está en CPU o se está cargando desde disco. En RTX 3050 4GB, usar `qwen3:4b` (cabe completo en VRAM) para mejor velocidad.

**Nota:** Ollama y LM Studio son proveedores de último recurso en el fallback. Si hay API keys de cloud configuradas, se usarán primero.

---

## 10) LM Studio local no responde

**Verificar que LM Studio está corriendo con el servidor activo:**
- Abrir LM Studio → Local Server → Start Server (puerto 1234)
- Verificar que hay un modelo cargado

```bash
curl http://localhost:1234/v1/models
```

**Modelo recomendado para RTX 3050 4GB:** `qwen3.5-4b-q4_k_m` (2.7GB VRAM).

---

## 11) Cola de mensajes crece y no drena

```bash
docker compose logs --since=20m worker-web
docker compose logs --since=20m scheduler
```

**Causas:**
- Sesión de WhatsApp Web expirada (QR vencido) → reconectar desde el panel admin
- `worker-web` no está running → `docker compose restart worker-web`
- Proveedor LLM fallando → ver sección 7

---

## 12) Mensajes no se envían desde el dashboard

```bash
curl -i http://localhost:8003/api/whatsapp/status \
  -H "Authorization: Bearer <token>"
```

**Si `connected: false`:** iniciar el runtime desde el panel admin o vía API:
```bash
curl -X POST http://localhost:8003/api/whatsapp/start \
  -H "Authorization: Bearer <token>"
```

---

## 13) UI carga pero acciones fallan

**Diagnóstico:**
- Abrir DevTools → Network — ver el código HTTP de las peticiones fallidas
- Abrir DevTools → Console — buscar errores JS o CORS

**Causas comunes:**
- Sesión expirada → reautenticar (F5 + login)
- CORS: `CORS_ORIGINS` no incluye el origen del navegador
- CSP: algún script externo bloqueado por Content-Security-Policy

---

## 14) `/docs` no carga (404)

Normal en producción — `DISABLE_DOCS=true` está activo.

Para acceder a la documentación interactiva en desarrollo:
```bash
# En .env
DISABLE_DOCS=false
# Reiniciar app
python -m uvicorn admin_panel:app --reload
# Acceder a http://localhost:8003/docs
```

---

## 15) Migraciones Alembic fallan

```bash
docker compose run --rm app alembic current
docker compose run --rm app alembic heads
docker compose run --rm app alembic history --verbose
```

**Acción:**
- Hacer backup primero
- Resolver múltiples heads si aparecen
- Aplicar: `docker compose run --rm app alembic upgrade head`

---

## 16) Build Docker falla

**Causas frecuentes:**
- `requirements.txt` tiene un paquete que no existe o versión incorrecta
- `ffmpeg` no disponible en la imagen base (ya incluido en Dockerfile)
- Sin espacio en disco

```bash
docker compose build --no-cache app 2>&1 | tail -50
df -h  # verificar espacio
```

---

## 17) Dependencias vulnerables

```bash
pip-audit -r requirements.txt
bandit -r src/
```

**Acción:** actualizar el paquete afectado, correr tests de regresión, rebuildar imagen.

---

## 18) Migraciones fallan al iniciar el contenedor

Puede ser race condition si PostgreSQL no terminó de iniciar.

```bash
# Verificar que postgres está healthy antes de iniciar app
docker compose up -d postgres redis
docker compose ps  # esperar que postgres sea "healthy"
docker compose up -d app scheduler
```

O simplemente reiniciar la app — Alembic reintentará con timeout=120s.

---

## 19) Variables de entorno no se cargan

```bash
# Verificar que .env está en el directorio correcto
ls -la chatbot-whatsapp-llm/.env

# Verificar que el archivo no tiene BOM ni encoding incorrecto
file .env

# Ver las variables que lee el contenedor
docker compose run --rm app env | grep -E "JWT|ADMIN|GEMINI|REDIS"
```

---

## 20) Recuperación rápida (playbook corto)

```bash
# 1. Capturar estado
docker compose ps
curl -i http://localhost:8003/healthz

# 2. Reiniciar servicio afectado
docker compose restart app
# o
docker compose restart worker-web

# 3. Validar
sleep 10
curl -fsS http://localhost:8003/healthz

# 4. Verificar logs post-reinicio
docker compose logs --since=2m app
```

---

## 21) Referencias de código

| Componente | Archivo |
|-----------|---------|
| Middlewares y auth global | `admin_panel.py` |
| Router de autenticación | `src/routers/auth.py` |
| LLM multi-proveedor | `src/services/multi_provider_llm.py` |
| Sistema de auditoría | `src/services/audit_system.py` |
| Control de procesos | `src/services/process_control.py` |
| Encriptación Fernet | `crypto.py` |
| Rate limiting | `src/services/http_rate_limit.py` |
| Circuit breaker | `src/services/protection_system.py` |
