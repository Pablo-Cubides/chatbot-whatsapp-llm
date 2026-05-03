# ✅ Beta Go-Live Checklist

Estado objetivo: release beta operable, segura y observable.
Última actualización: Abril 2026.

---

## 1) Secrets y credenciales

- [ ] `JWT_SECRET` generado con 48+ bytes aleatorios (ya generado en `.env`)
- [ ] `ADMIN_PASSWORD` y `OPERATOR_PASSWORD` son valores seguros (no placeholders)
- [ ] `POSTGRES_PASSWORD` configurado (requerido por docker-compose)
- [ ] `REDIS_PASSWORD` configurado (requerido por docker-compose)
- [ ] `LEGACY_TOKEN_ENABLED=false` — token legacy desactivado
- [ ] `WHATSAPP_APP_SECRET` configurado si `WHATSAPP_MODE=cloud` o `both`
- [ ] `.env` **NO** está commiteado en git (verificar con `git ls-files .env`)
- [ ] Al menos una API key de IA configurada y probada:
  - [ ] `GEMINI_API_KEY` (recomendada — tier gratuito) **o**
  - [ ] `OPENROUTER_API_KEY` (alternativa gratuita)

---

## 2) Base de datos y migraciones

- [ ] `alembic upgrade head` aplicado en el entorno destino
- [ ] Conectividad PostgreSQL validada (`pg_isready`)
- [ ] Tablas creadas correctamente (6 migraciones aplicadas)
- [ ] Backups automáticos activos o planificados
- [ ] Restauración de backup probada al menos una vez
- [ ] `DISABLE_DOCS=true` — Swagger UI y ReDoc deshabilitados
- [ ] `LOG_FORMAT=json` — logs estructurados para producción
- [ ] `AUTO_MIGRATE=true` — migraciones automáticas al iniciar
- [ ] `CORS_ORIGINS` apunta solo a dominios de producción (no `*`)

```bash
# Verificar migraciones
docker compose run --rm app alembic current
docker compose run --rm app alembic heads

# Backup manual
docker compose exec postgres pg_dump \
  -U chatbot -d chatbot -Fc \
  -f /tmp/chatbot_$(date +%Y%m%d).dump
```

---

## 3) Runtime y salud de servicios

- [ ] Los 5 servicios en estado `healthy`: `app`, `worker-web`, `scheduler`, `postgres`, `redis`
- [ ] `/healthz` responde `{"status":"ok"}` con `database`, `redis`, `disk`, `memory` OK
- [ ] `/metrics` accesible para Prometheus (si está configurado)
- [ ] Smoke auth validado:

```bash
# Health
curl -fsS http://localhost:8003/healthz

# Login
TOKEN=$(curl -fsS -X POST http://localhost:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<ADMIN_PASSWORD>"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")

# Verificar token
curl -fsS http://localhost:8003/api/auth/me -H "Authorization: Bearer $TOKEN"
```

---

## 4) Seguridad operativa

- [ ] `RATE_LIMIT_ENABLED=true` — rate limiting habilitado en `.env`
- [ ] Headers de seguridad activos (CSP, X-Frame-Options, HSTS)
- [ ] Redis protegido con contraseña (configurado en `redis.conf` vía docker-compose)
- [ ] Puerto 8003 solo accesible vía reverse proxy (no expuesto directamente)
- [ ] Reverse proxy configurado (`docker-compose.proxy.yml`) con HTTPS si aplica
- [ ] `POSTGRES_PASSWORD` y `REDIS_PASSWORD` no en logs

---

## 5) Monitoreo y respuesta a incidentes

- [ ] `/healthz` incluida en monitoreo externo (Uptime Robot, Better Uptime, etc.)
- [ ] Estrategia de retención de logs definida (`logs/` con rotación en docker-compose)
- [ ] Alertas básicas para:
  - [ ] `/healthz` != 200 por 3 checks consecutivos
  - [ ] Error rate (5xx) > 2% por 5 minutos
  - [ ] Cola pendiente > 1,000 mensajes por 15 minutos
- [ ] Canal de incidentes definido (Slack, PagerDuty o similar)
- [ ] Procedimiento de escalada documentado

---

## 6) Rollback y continuidad

- [ ] Procedimiento de rollback documentado (ver SECURITY_RUNBOOK.md)
- [ ] Criterio de rollback definido (errores/latencia/smoke)
- [ ] Imagen Docker del release anterior disponible o tag conocido
- [ ] Runbook de apagado controlado probado

---

## 7) Evidencia final de release

- [ ] Tests en verde: `pytest tests/ -q`
- [ ] Sin errores de lint: `ruff check .`
- [ ] Build Docker exitoso: `docker compose build`
- [ ] Smoke tests post-deploy ejecutados manualmente (ver [post_deploy_verify.yml](../.github/workflows/post_deploy_verify.yml))
- [ ] Modelos de IA actualizados (no usar modelos deprecados)
- [ ] Aprobación registrada (fecha, responsable)
