# TROUBLESHOOTING OPERACIONAL

Guía de resolución rápida para incidentes frecuentes.

## 0) Checklist universal antes de empezar

1. Registrar timestamp de inicio.
2. Verificar alcance (1 usuario, todos, región, endpoint).
3. Capturar estado de servicios.
4. Capturar logs de los últimos 15 minutos.

```bash
docker compose ps
docker compose logs --since=15m app
docker compose logs --since=15m worker-web
docker compose logs --since=15m scheduler
curl -i http://localhost:8003/healthz
```

---

## 1) 401 en endpoints protegidos

### Árbol de decisión

- ¿Falla solo un usuario?
	- Sí → revisar credenciales y expiración de token.
	- No → revisar `JWT_SECRET` y reloj del servidor.

### Comandos

```bash
curl -i http://localhost:8003/api/auth/me -H "Authorization: Bearer <token>"
```

### Esperado

- 200 con payload de usuario.

### Si falla

- 401: token inválido/expirado o firma no válida.
- Confirmar que todos los servicios usan el mismo `JWT_SECRET`.

---

## 2) Login bloqueado o rate limit excesivo

### Diagnóstico

- Revisar intentos fallidos y lockout.
- Confirmar configuración de límites por endpoint.

```bash
docker compose logs --since=30m app | grep -i "SECURITY_LOGIN_FAILED\|lockout\|rate limit"
```

### Esperado

- Eventos auditables con motivos claros.

### Acción

- Identificar IP/origen abusivo.
- Ajustar temporalmente límites solo con change control.

---

## 3) WebSocket de métricas no conecta

### Diagnóstico

- Confirmar token WS emitido.
- Confirmar que cliente envía auth como primer mensaje.

```bash
curl -i -X POST http://localhost:8003/api/auth/ws-token -H "Authorization: Bearer <access_token>"
```

### Esperado

- 200 con `ws_token`.

### Causas típicas

- Token enviado en query string (rechazado).
- Scope inválido en token WS.
- Token expirado.

---

## 4) `/healthz` responde 503

### Diagnóstico

- Revisar conexión DB.

```bash
docker compose logs --tail=200 app
docker compose exec postgres pg_isready -U ${POSTGRES_USER:-chatbot}
```

### Acción

- Reiniciar postgres si está unhealthy.
- Validar `DATABASE_URL`.

---

## 5) Error de conexión a PostgreSQL

### Diagnóstico

```bash
docker compose exec postgres psql -U ${POSTGRES_USER:-chatbot} -d ${POSTGRES_DB:-chatbot} -c "SELECT 1"
```

### Esperado

- Resultado `1`.

### Acción

- Si falla autenticación: revisar usuario/password.
- Si timeout: revisar red y puertos.

---

## 6) Redis no responde

### Diagnóstico

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

### Esperado

- `PONG`.

### Acción

- Validar contraseña y estado del contenedor.
- Reiniciar redis y verificar salud.

---

## 7) Respuestas LLM lentas o fallidas

### Diagnóstico

- Revisar proveedor primario.
- Verificar fallback activo.
- Revisar timeouts.

```bash
docker compose logs --since=20m app | grep -i "provider\|fallback\|timeout\|circuit"
```

### Acción

- Confirmar claves API.
- Forzar proveedor alterno temporal si aplica.

---

## 8) Cola de mensajes crece y no drena

### Diagnóstico

- Revisar worker-web y scheduler.

```bash
docker compose logs --since=20m worker-web
docker compose logs --since=20m scheduler
```

### Acción

- Reiniciar worker-web si hay sesión rota.
- Confirmar estado de WhatsApp Web.

---

## 9) Mensajes no enviados desde dashboard manual

### Diagnóstico

- Validar endpoint `/api/whatsapp/send`.
- Validar runtime de WhatsApp activo.

```bash
curl -i http://localhost:8003/api/whatsapp/status -H "Authorization: Bearer <token>"
```

### Acción

- Si runtime parado: iniciar runtime vía endpoint admin.
- Verificar errores en `worker-web`.

---

## 10) UI carga pero acciones fallan

### Diagnóstico

- Revisar consola del navegador.
- Revisar códigos HTTP en Network tab.

### Causas comunes

- Sesión expirada.
- CORS inconsistente.
- CSP bloqueando recursos.

### Acción

- Reautenticar.
- Confirmar `CORS_ORIGINS`.
- Verificar headers de seguridad en response.

---

## 11) Migraciones Alembic fallan

### Diagnóstico

```bash
alembic current
alembic heads
alembic history --verbose
```

### Acción

- Resolver múltiples heads.
- Aplicar `alembic upgrade head` tras backup.

---

## 12) Build Docker falla en CI

### Diagnóstico

- Revisar step de lint/type/test/security.
- Revisar permisos de registry.

### Acción

- Corregir errores previos al build.
- Validar tokens de publish.

---

## 13) Dependencias vulnerables detectadas

### Diagnóstico

- Revisar reporte Bandit/Trivy/pip-audit.

### Acción

- Priorizar HIGH/CRITICAL.
- Actualizar dependencia y correr regresión.

---

## 14) Archivo de configuración inválido

### Diagnóstico

- Validación de entorno en startup falla.

### Acción

- Completar variables obligatorias (`JWT_SECRET`, `ADMIN_PASSWORD`, etc.).
- Si `WHATSAPP_MODE=cloud|both`, definir `WHATSAPP_APP_SECRET`.

---

## 15) Recuperación rápida (playbook corto)

1. Confirmar incidente y severidad.
2. Hacer captura de evidencia.
3. Reiniciar servicio afectado.
4. Validar `/healthz` y flujo mínimo.
5. Comunicar estado.

```bash
docker compose restart app
sleep 5
curl -fsS http://localhost:8003/healthz
```

---

## 16) Referencias de código útiles

- Auth router: `src/routers/auth.py`
- Core app/middlewares/ws: `admin_panel.py`
- Auditoría: `src/services/audit_system.py`
- Control de procesos: `src/services/process_control.py`
- Crypto/Fernet: `crypto.py`

---

## 17) Cierre de incidente

- Confirmar servicio estable 30 minutos.
- Documentar causa raíz.
- Registrar acciones preventivas.
- Crear tareas de seguimiento.
