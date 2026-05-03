# 🚀 Guía de Deployment en Cloud

Esta guía explica cómo desplegar el **Enterprise WhatsApp AI Chatbot Platform** en diferentes proveedores cloud.

## 📋 Pre-requisitos

- Docker y Docker Compose instalados
- Cuenta en proveedor cloud (AWS/GCP/Azure)
- Dominio configurado (opcional pero recomendado)
- SSL/TLS certificate (Let's Encrypt)

## 🔐 Variables de Entorno Requeridas

Antes de desplegar, configura estas variables:

```bash
# Seguridad - OBLIGATORIAS
JWT_SECRET=<genera-un-secreto-seguro-de-64-caracteres>
ADMIN_PASSWORD=<password-seguro>
OPERATOR_PASSWORD=<password-operador-seguro>

# Base de datos
DATABASE_URL=postgresql://user:password@host:5432/chatbot

# Redis
REDIS_URL=redis://host:6379/0

# Rate limiting (recomendado)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_ENABLED=true
RATE_LIMIT_REDIS_URL=redis://host:6379/0

# CORS
CORS_ORIGINS=https://tu-dominio.com

# Rotación Fernet
FERNET_KEY_ROTATION_DAYS=90

# WhatsApp Cloud (si usas Cloud API)
WHATSAPP_MODE=cloud
WHATSAPP_CLOUD_TOKEN=<tu-token>
WHATSAPP_CLOUD_PHONE_NUMBER_ID=<phone-number-id>
WHATSAPP_CLOUD_VERIFY_TOKEN=<verify-token>
WHATSAPP_APP_SECRET=<app-secret-meta-para-firma-webhook>

# APIs de IA
GEMINI_API_KEY=<api-key>
OPENAI_API_KEY=<api-key>
```

### Generación segura de secretos (recomendado)

```bash
# JWT/whatsapp/app secrets (64 bytes hex)
openssl rand -hex 64

# Passwords robustas
openssl rand -base64 32
```

También puedes generar desde Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 🌩️ AWS (Amazon Web Services)

### Opción 1: ECS con Fargate

```bash
# 1. Crear repositorio ECR
aws ecr create-repository --repository-name chatbot-whatsapp

# 2. Build y push imagen
docker build -t chatbot-whatsapp .
docker tag chatbot-whatsapp:latest <account>.dkr.ecr.<region>.amazonaws.com/chatbot-whatsapp:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/chatbot-whatsapp:latest

# 3. Crear task definition (ver archivo ecs-task.json)
aws ecs register-task-definition --cli-input-json file://ecs-task.json

# 4. Crear servicio
aws ecs create-service \
    --cluster chatbot-cluster \
    --service-name chatbot-service \
    --task-definition chatbot-whatsapp \
    --desired-count 1 \
    --launch-type FARGATE
```

### Opción 2: EC2 con Docker Compose

```bash
# 1. Lanzar instancia EC2 (t3.medium mínimo)
# 2. Conectar via SSH

# 3. Instalar Docker
sudo yum update -y
sudo amazon-linux-extras install docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# 4. Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. Clonar repo y configurar
git clone https://github.com/tu-usuario/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
cp .env.example .env
# Editar .env con valores de producción

# 6. Iniciar servicios
docker-compose up -d
```

---

## 🔷 Google Cloud Platform (GCP)

### Cloud Run

```bash
# 1. Build y push a Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/chatbot-whatsapp

# 2. Deploy a Cloud Run
gcloud run deploy chatbot-whatsapp \
    --image gcr.io/PROJECT_ID/chatbot-whatsapp \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars "JWT_SECRET=xxx,DATABASE_URL=xxx" \
    --memory 1Gi \
    --cpu 1
```

### GCE con Docker

```bash
# 1. Crear instancia
gcloud compute instances create chatbot-vm \
    --machine-type e2-medium \
    --zone us-central1-a \
    --image-family ubuntu-2204-lts \
    --image-project ubuntu-os-cloud

# 2. SSH y configurar (similar a EC2)
gcloud compute ssh chatbot-vm
```

---

## 🔶 Microsoft Azure

### Azure Container Instances

```bash
# 1. Crear resource group
az group create --name chatbot-rg --location eastus

# 2. Crear container registry
az acr create --resource-group chatbot-rg --name chatbotacr --sku Basic

# 3. Build y push
az acr build --registry chatbotacr --image chatbot-whatsapp:v1 .

# 4. Deploy container
az container create \
    --resource-group chatbot-rg \
    --name chatbot-service \
    --image chatbotacr.azurecr.io/chatbot-whatsapp:v1 \
    --dns-name-label chatbot-unique \
    --ports 8003 \
    --environment-variables JWT_SECRET=xxx DATABASE_URL=xxx
```

---

## 🐳 Docker Compose (VPS genérico)

Para cualquier VPS (DigitalOcean, Linode, Vultr, Hetzner):

```bash
# 1. Instalar Docker
curl -fsSL https://get.docker.com | sh

# 2. Clonar y configurar
git clone https://github.com/tu-usuario/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm

# 3. Crear .env de producción
cat > .env << 'EOF'
JWT_SECRET=tu-secreto-seguro-64-caracteres-aqui
ADMIN_PASSWORD=password-seguro-produccion
DATABASE_URL=postgresql://chatbot:password@postgres:5432/chatbot
POSTGRES_PASSWORD=password-seguro-db
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://tu-dominio.com
WHATSAPP_MODE=cloud
EOF

# 4. Iniciar en producción
docker-compose up -d

# 4.a Validar configuración compose antes de levantar servicios
docker compose config -q
docker compose -f docker-compose.yml -f docker-compose.proxy.yml config -q
docker compose -f docker-compose.yml -f docker-compose.backup.yml config -q

# 4.b (Recomendado beta) iniciar con reverse proxy
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d

# 4.c (Recomendado beta) habilitar backup automático PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.backup.yml up -d

# 5. Ver logs
docker-compose logs -f app
```

---

## 🔒 Configuración de Nginx (Reverse Proxy)

Este repositorio incluye una opción lista para usar en [docker-compose.proxy.yml](docker-compose.proxy.yml)
y configuración base en [config/nginx/default.conf](config/nginx/default.conf).

Para activarlo:

```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tu-dominio.com;

    ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> Nota: para TLS en 443 puedes mantener Nginx externo (host) o extender el servicio de proxy con certificados de Let's Encrypt.

---

## 📝 Checklist de Producción

- [ ] Variables de entorno configuradas
- [ ] `CORS_ORIGINS` con dominios específicos
- [ ] `JWT_SECRET` con 64+ caracteres
- [ ] PostgreSQL en lugar de SQLite
- [ ] Redis habilitado
- [ ] HTTPS configurado
- [ ] Firewall configurado (solo puertos 80, 443)
- [ ] Backups automáticos de DB
- [ ] Monitoring configurado
- [ ] Logs centralizados
- [ ] Rate limit Redis habilitado (`RATE_LIMIT_REDIS_ENABLED=true`)
- [ ] Política de rotación Fernet definida (`FERNET_KEY_ROTATION_DAYS`)

### Backups automáticos PostgreSQL (compose)

Este repositorio incluye [docker-compose.backup.yml](docker-compose.backup.yml) con un servicio `postgres-backup`.

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml up -d
```

Salida de backups: `./data/backups/postgres`.

Variables de retención/schedule:

- `BACKUP_SCHEDULE` (default `@daily`)
- `BACKUP_KEEP_DAYS` (default `7`)
- `BACKUP_KEEP_WEEKS` (default `4`)
- `BACKUP_KEEP_MONTHS` (default `6`)

---

## 🔄 CI/CD Deploy automático (GitHub Actions)

Para activar deploy remoto por SSH, define estos secrets en el repositorio:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `JWT_SECRET`
- `ADMIN_PASSWORD`
- `OPERATOR_PASSWORD`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `WHATSAPP_APP_SECRET` (obligatorio en modo cloud)

El deploy falla de forma temprana si falta alguno de estos valores, antes de ejecutar `docker compose up`.

El pipeline publica imagen en GHCR, ejecuta `alembic upgrade head` y levanta servicios con `docker compose` (postgres/redis/app/worker-web/scheduler).

Nota de hardening: para autenticación con GHCR en scripts, usar `docker login --password-stdin` en lugar de `-p`.

### Verificación real en host remoto (manual)

Este repositorio incluye el workflow manual [post_deploy_verify.yml](../.github/workflows/post_deploy_verify.yml)
para validar en entorno real:

- `/healthz` (incluye componentes `database`, `redis`, `disk`, `memory`)
- `/metrics`
- autenticación real (`/api/auth/login` + `/api/auth/me`)
- estado de `app`, `worker-web`, `scheduler`

Ejecútalo desde Actions → **Post Deploy Verification** (`workflow_dispatch`).

### Checklist de salida beta

Antes de marcar release beta, completar: [BETA_GO_LIVE_CHECKLIST.md](BETA_GO_LIVE_CHECKLIST.md)

---

## 🔍 Monitoreo

### Health Check
```bash
curl https://tu-dominio.com/healthz
# Respuesta esperada: {"status": "ok"}
```

### Entrypoint recomendado

```bash
gunicorn admin_panel:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8003 --workers 2 --timeout 120 --graceful-timeout 30
```

### Runbook de apagado controlado (graceful shutdown)

El servicio ahora cierra recursos críticos en `lifespan` al recibir señal de apagado:

- Cierre del rate limiter HTTP (`http_rate_limiter.aclose()`)
- Limpieza de conexiones SQLAlchemy (`cleanup_connections()`)

Operación recomendada:

```bash
# Docker Compose
docker-compose stop app

# Kubernetes
kubectl rollout restart deployment/chatbot
```

Verificación post-shutdown:

- Confirmar ausencia de errores de cierre en logs.
- Confirmar que no quedan conexiones huérfanas en DB.
- Confirmar que el servicio vuelve a `{"status":"ok"}` en `/healthz` tras reinicio.

### Smoke test post-deploy (beta)

```bash
curl -fsS https://tu-dominio.com/healthz
HEALTH_JSON=$(curl -fsS https://tu-dominio.com/healthz)
printf '%s' "$HEALTH_JSON" | python3 -c "import json,sys; p=json.load(sys.stdin); c=p.get('components') or {}; req={'database','redis','disk','memory'}; missing=sorted(req-set(c.keys())); assert 'status' in p; assert isinstance(c, dict); assert not missing, f'missing components: {missing}'"
curl -fsS https://tu-dominio.com/metrics | head -n 20

# Debe responder 401 sin token
test "$(curl -s -o /dev/null -w "%{http_code}" https://tu-dominio.com/api/auth/me)" = "401"

# Login + /api/auth/me autenticado
LOGIN_RESPONSE=$(curl -fsS -X POST "https://tu-dominio.com/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"<admin-password>"}')
ACCESS_TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")
test -n "$ACCESS_TOKEN"
curl -fsS "https://tu-dominio.com/api/auth/me" -H "Authorization: Bearer ${ACCESS_TOKEN}"

# Estado de servicios críticos
docker compose ps
for svc in app worker-web scheduler; do
    docker compose ps "$svc" | grep -Eiq "Up|running|healthy"
done
```

Validar además:

- Migraciones aplicadas (`alembic_version` en DB).
- `worker-web` y `scheduler` en estado healthy.
- Sin errores críticos en logs de `app`, `worker-web` y `scheduler`.

Si algún smoke check falla, levantar diagnóstico rápido:

```bash
docker compose ps
docker compose logs --tail=120 app worker-web scheduler
```

### Métricas Prometheus (futuro)
```bash
curl https://tu-dominio.com/metrics
```

---

## 🆘 Troubleshooting

### Error de conexión a DB
```bash
# Verificar conectividad
docker-compose exec app python -c "from src.models.admin_db import get_session; print(get_session())"
```

### WhatsApp no conecta
```bash
# Ver logs del worker
docker-compose logs worker-web
```

### Errores de memoria
```bash
# Aumentar límites en docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G
```
