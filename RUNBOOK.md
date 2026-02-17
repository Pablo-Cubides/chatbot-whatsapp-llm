# RUNBOOK OPERACIONAL

Este documento define la operación de producción del sistema Chatbot WhatsApp.

## 1) Alcance y objetivos

- Garantizar disponibilidad y recuperación rápida.
- Estandarizar respuesta a incidentes.
- Reducir MTTR con pasos ejecutables.

## 2) Servicios críticos

- app (API FastAPI + Admin UI)
- worker-web (automatización WhatsApp Web)
- scheduler (procesamiento periódico)
- postgres (persistencia principal)
- redis (caché y control de throughput)

## 3) URLs operativas

- Health principal: http://localhost:8003/healthz
- API docs: http://localhost:8003/docs
- UI principal: http://localhost:8003/ui/index.html
- Dashboard realtime: http://localhost:8003/ui/realtime_dashboard.html

## 4) Matriz de severidad

- Sev-1: caída total del servicio o pérdida activa de datos.
- Sev-2: funcionalidad core degradada (login, envío, webhooks).
- Sev-3: degradación parcial o intermitente.
- Sev-4: impacto bajo / operativo interno.

## 5) Umbrales de alertas sugeridos

- API p95 > 2s por 10 minutos.
- Error rate (5xx) > 2% por 5 minutos.
- /healthz != 200 por 3 checks consecutivos.
- Redis no responde por 60s.
- Postgres connection errors > 10/min.
- Cola pendiente > 1,000 mensajes por 15 minutos.

## 6) Escalation matrix

- Nivel 1 (on-call): respuesta inicial y mitigación.
- Nivel 2 (backend owner): cambios de config o rollback.
- Nivel 3 (infra/db owner): incidentes de red, storage o DB crítica.

## 7) Checklist de inicio de turno

1. Validar estado de contenedores.
2. Validar `/healthz`.
3. Validar logs últimos 15 minutos.
4. Validar backlog de cola.
5. Validar uso de CPU/RAM de `app` y `worker-web`.

Comandos:

```bash
docker compose ps
curl -fsS http://localhost:8003/healthz
docker compose logs --since=15m app
docker compose logs --since=15m worker-web
docker stats --no-stream
```

## 8) Procedimiento de despliegue

1. Confirmar rama/tag y ventana de cambio.
2. Respaldar DB.
3. Ejecutar build y pull de imágenes.
4. Aplicar migraciones.
5. Reiniciar servicios por orden.
6. Validar smoke tests.

Comandos de referencia:

```bash
docker compose pull
docker compose build --no-cache app worker-web scheduler
alembic upgrade head
docker compose up -d postgres redis
docker compose up -d app scheduler worker-web
curl -fsS http://localhost:8003/healthz
```

## 9) Smoke test post-deploy

1. Login admin.
2. `POST /api/auth/ws-token` responde 200 autenticado.
3. Dashboard carga sin errores JS críticos.
4. Envío de mensaje de prueba.
5. Evento de auditoría visible.

## 10) Rollback estándar

1. Seleccionar tag estable previo.
2. Revertir migración si la release incluye cambios de esquema incompatibles.
3. Levantar versión anterior.
4. Validar salud y flujo mínimo.

Comandos:

```bash
docker compose down
docker image ls | head
# ajustar tags en compose/.env
docker compose up -d
curl -fsS http://localhost:8003/healthz
```

## 11) Backup de PostgreSQL

Frecuencia recomendada:

- Full diario.
- Incremental/WAL según política de plataforma.

Comando ejemplo:

```bash
pg_dump -h localhost -U chatbot -d chatbot -Fc -f backups/chatbot_$(date +%Y%m%d_%H%M).dump
```

Validación del backup:

```bash
pg_restore -l backups/chatbot_YYYYMMDD_HHMM.dump | head
```

## 12) Restore de PostgreSQL

1. Crear DB destino vacía.
2. Restaurar dump.
3. Ejecutar chequeos de consistencia.

```bash
createdb -h localhost -U chatbot chatbot_restore
pg_restore -h localhost -U chatbot -d chatbot_restore backups/chatbot_YYYYMMDD_HHMM.dump
psql -h localhost -U chatbot -d chatbot_restore -c "SELECT NOW();"
```

## 13) Disaster recovery (DR)

Objetivos sugeridos:

- RPO: 15 minutos.
- RTO: 60 minutos.

Secuencia DR:

1. Declarar incidente Sev-1.
2. Congelar cambios y PRs no críticos.
3. Levantar infraestructura alterna.
4. Restaurar backup más reciente válido.
5. Rehidratar servicios app/worker/scheduler.
6. Ejecutar smoke tests y abrir tráfico gradualmente.
7. Publicar postmortem.

## 14) Operación de incidentes

Plantilla de respuesta:

1. Detección
2. Confirmación
3. Contención
4. Mitigación
5. Recuperación
6. Cierre

Campos mínimos de bitácora:

- timestamp
- síntoma
- hipótesis
- acción ejecutada
- resultado
- siguiente acción

## 15) Diagnóstico rápido por componente

### app

```bash
docker compose logs --tail=200 app
curl -i http://localhost:8003/healthz
```

### worker-web

```bash
docker compose logs --tail=200 worker-web
```

### scheduler

```bash
docker compose logs --tail=200 scheduler
```

### postgres

```bash
docker compose exec postgres pg_isready -U ${POSTGRES_USER:-chatbot}
```

### redis

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

## 16) Procedimientos de mantenimiento

- Rotar secretos trimestralmente.
- Revisar dependencias semanalmente.
- Revisar tamaño de logs y retención semanal.
- Prueba de restore mensual.

## 17) Gestión de capacidad

- Monitorear crecimiento de tabla de auditoría y mensajes.
- Revisar índices más usados mensualmente.
- Ajustar recursos de contenedores en picos estacionales.

## 18) Seguridad operacional

- No exponer `JWT_SECRET`, `ADMIN_PASSWORD`, `REDIS_PASSWORD` en logs.
- Usar sólo secretos por variables de entorno/secret manager.
- No compartir dumps sin cifrado en canales no aprobados.

## 19) Contactos y ownership

- Backend owner: responsable de API, auth, routers.
- Infra owner: compose, red, persistencia.
- Data owner: backups, migraciones y consistencia.

## 20) Cierre y postmortem

- Todo incidente Sev-1/Sev-2 requiere postmortem.
- Incluir línea temporal, causa raíz, factores contribuyentes y acciones preventivas.
- Registrar acciones en backlog con responsable y fecha compromiso.

## 21) Anexo: comandos útiles

```bash
docker compose ps
docker compose logs --since=30m app
docker compose logs --since=30m worker-web
docker compose logs --since=30m scheduler
docker compose restart app
docker compose restart worker-web
docker compose restart scheduler
pytest -q -k "phase1 or phase2 or phase3 or phase5 or phase6"
```

## 22) Revisión semanal de SLO/SLA

1. Extraer disponibilidad semanal.
2. Revisar p95/p99 de endpoints críticos.
3. Revisar tasa de errores 4xx/5xx.
4. Revisar incidentes abiertos y deuda operativa.

Formato recomendado de reporte:

- ventana analizada
- disponibilidad
- latencia p95
- latencia p99
- error rate
- top 3 causas de incidentes
- acciones preventivas

## 23) Plantilla de comunicación de incidente

Mensaje inicial:

- estado: investigando
- impacto: usuarios/endpoints
- alcance: parcial/total
- próxima actualización: 15 minutos

Mensaje de mitigación:

- estado: mitigado/parcialmente mitigado
- workaround aplicado
- riesgo residual

Mensaje de cierre:

- estado: resuelto
- causa raíz resumida
- acciones de follow-up

## 24) Simulacros operativos

- Simulacro de restore DB: mensual.
- Simulacro de caída de worker-web: quincenal.
- Simulacro de rollback de release: mensual.

Evidencias mínimas por simulacro:

- fecha/hora
- responsables
- duración
- resultado
- acciones de mejora
