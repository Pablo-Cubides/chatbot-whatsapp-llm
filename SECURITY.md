# 🔒 Política de Seguridad

## 📋 Versiones Soportadas

Actualmente proporcionamos actualizaciones de seguridad para las siguientes versiones:

| Versión | Soporte de Seguridad |
| ------- | -------------------- |
| 2.x.x   | ✅ Soportada         |
| 1.x.x   | ⚠️ Soporte limitado  |
| < 1.0   | ❌ No soportada      |

## 🚨 Reportar Vulnerabilidades de Seguridad

Si descubres una vulnerabilidad de seguridad, **NO** la reportes a través de issues públicos de GitHub. En su lugar, sigue este proceso:

### 🔐 Proceso de Reporte Confidencial

1. **Contacto directo**: Reportar al maintainer del repositorio de forma privada
2. **Asunto**: "SECURITY: [Breve descripción]"
3. **No publicar** el detalle en issues públicos hasta que sea mitigado
4. **Información Requerida**:
   - Descripción detallada de la vulnerabilidad
   - Pasos para reproducir el problema
   - Versiones afectadas
   - Impacto potencial
   - Cualquier mitigación que hayas identificado

### ⏱️ Tiempo de Respuesta

- **Confirmación inicial**: Dentro de 24 horas
- **Evaluación inicial**: Dentro de 72 horas
- **Resolución**: Dependiendo de la severidad
  - 🔴 **Crítica**: 1-7 días
  - 🟡 **Alta**: 1-2 semanas
  - 🟢 **Media/Baja**: 2-4 semanas

### 🏆 Programa de Reconocimiento

Reconocemos y agradecemos a los investigadores de seguridad responsables:

- **Hall of Fame**: Listado en nuestro README
- **Créditos**: Mención en notas de release
- **Certificado**: Certificado digital de reconocimiento

## 🛡️ Mejores Prácticas de Seguridad

### Controles activos en el proyecto (estado actual)

- Middleware global de autenticación para rutas `/api/*` (excepto login)
- Endpoints de control de procesos (`/api/system/*`, `/api/lmstudio/*`) restringidos a rol admin
- Verificación de firma `X-Hub-Signature-256` en webhook de WhatsApp Cloud
- Autenticación JWT-only para API y dependencias de router (`get_current_user` / `require_admin`)
- Claves de Gemini enviadas por header (`x-goog-api-key`) y no en query string
- Cabeceras de hardening HTTP: CSP, `X-Frame-Options`, `X-Content-Type-Options`, COOP/CORP, `Referrer-Policy`
- Rate limiting HTTP global con buckets por endpoint (`/api/*`, `/api/auth/login`, `/api/system/*`) y backend Redis con fallback en memoria
- CORS estricto: si `CORS_ORIGINS` contiene `*` y hay credenciales, el servidor fuerza una lista segura por defecto
- Endurecimiento de permisos de `data/fernet.key` (ACL en Windows + permisos restrictivos en POSIX)
- Verificación programada de antigüedad de Fernet key para cumplir política de rotación (`FERNET_KEY_ROTATION_DAYS`)

### Para Usuarios

#### 🔑 Configuración Segura

```bash
# ✅ Buenas prácticas
export JWT_SECRET="clave-super-secreta-minimo-32-caracteres-aleatorios"
export ADMIN_PASSWORD="ContraseñaSegura123!"
export DATABASE_URL="postgresql://user:pass@localhost/chatbot_prod"

# ❌ Evitar
export JWT_SECRET="123"  # Muy simple
export ADMIN_PASSWORD="admin"  # Password por defecto
```

#### 🔒 Variables de Entorno

**Obligatorias para producción:**
```bash
# Autenticación
JWT_SECRET=your-super-secret-jwt-key-minimum-32-chars
ADMIN_PASSWORD=strong-admin-password

# Base de datos
DATABASE_URL=postgresql://user:pass@localhost/chatbot

# APIs (solo las que uses)
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key

# CORS (solo dominios necesarios)
CORS_ORIGINS=https://tu-dominio.com,https://admin.tu-dominio.com

# Rate limiting global (Redis recomendado)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_ENABLED=true
RATE_LIMIT_REDIS_URL=redis://redis:6379/0

# Rotación de clave Fernet
FERNET_KEY_ROTATION_DAYS=90
```

#### 🚧 Configuración de Producción

```bash
# Firewall
ufw allow 22/tcp      # SSH
ufw allow 443/tcp     # HTTPS
ufw allow 80/tcp      # HTTP (redirigir a HTTPS)
ufw deny 8003/tcp     # NO exponer puerto interno

# Proxy inverso (nginx/apache)
# Configurar HTTPS con certificados SSL
# Rate limiting a nivel de servidor
# Logging de accesos
```

### Para Desarrolladores

#### 🔍 Revisión de Código

Verificar en cada PR:

- [ ] No hay credenciales hardcoded
- [ ] Validación de input en todos los endpoints
- [ ] Manejo seguro de errores (no exponer stack traces)
- [ ] Uso de parameterized queries
- [ ] Validación de permisos de usuario
- [ ] Rate limiting implementado
- [ ] Logging de eventos de seguridad

#### 🧪 Testing de Seguridad

```python
# Tests de autenticación
def test_unauthorized_access():
    """Verificar que endpoints protegidos rechazan acceso sin token"""
    
def test_expired_token():
    """Verificar manejo de tokens expirados"""
    
def test_invalid_token():
    """Verificar manejo de tokens inválidos"""

# Tests de validación
def test_sql_injection_protection():
    """Verificar protección contra SQL injection"""
    
def test_xss_protection():
    """Verificar protección contra XSS"""
    
def test_input_validation():
    """Verificar validación de input malicioso"""
```

## ⚠️ Vulnerabilidades Conocidas

### 🔴 Críticas - Requieren Acción Inmediata

Ninguna conocida actualmente.

### 🟡 Moderadas - Recommended Updates

| CVE | Descripción | Versión Afectada | Fix Disponible |
|-----|-------------|------------------|----------------|
| N/A | N/A | N/A | N/A |

### 🟢 Informativas

| Descripción | Componente | Mitigación |
|-------------|------------|------------|
| Rate limiting configurado por defecto | API | Configurar según necesidades |
| SQLite por defecto | Database | Migrar a PostgreSQL en producción |

## 🔧 Herramientas de Seguridad

### Análisis de Dependencias

```bash
# Verificar vulnerabilidades en dependencias
pip-audit -r requirements.txt

# Actualizar dependencias con fixes de seguridad
pip install --upgrade package_name
```

### Análisis Estático

```bash
# Bandit - Security linter para Python
bandit -r src/

# Safety - Verificar vulnerabilidades conocidas
safety check

# Semgrep - Static analysis
semgrep --config=auto src/
```

### Testing de Penetración

Herramientas recomendadas para testing:

- **OWASP ZAP**: Para testing de aplicaciones web
- **Burp Suite**: Para análisis de APIs
- **SQLMap**: Para testing de SQL injection
- **Nikto**: Para escaneo de vulnerabilidades web

## 📊 Monitoreo de Seguridad

### Logs de Seguridad

El sistema registra automáticamente:

```python
# Eventos de autenticación
logger.info(f"Login exitoso: {username}")
logger.warning(f"Intento de login fallido: {username}")
logger.error(f"Token inválido usado: {client_ip}")

# Eventos de rate limiting
logger.warning(f"Rate limit excedido: {client_ip}")

# Eventos de circuit breaker
logger.error(f"Circuit breaker activado: {service}")
```

### Métricas de Seguridad

Monitorear:

- **Intentos de login fallidos** por minuto
- **Requests bloqueados** por rate limiting
- **Errores 401/403** por endpoint
- **Circuit breakers activados**
- **Tiempo de respuesta** de endpoints críticos

### Alertas Automáticas

Configurar alertas para:

- Múltiples intentos de login fallidos
- Rate limiting excesivo desde una IP
- Errores 500 en endpoints de autenticación
- Circuit breakers abiertos por mucho tiempo
- Uso inusual de API keys

## 🆘 Incident Response

### 1. Detección

- Monitoreo automático activo
- Reportes de usuarios
- Análisis de logs

### 2. Evaluación

**Severidad:**
- 🔴 **Crítica**: Compromiso de datos, sistema no funcional
- 🟡 **Alta**: Funcionalidad limitada, riesgo de datos
- 🟢 **Media**: Degradación menor del servicio
- ⚪ **Baja**: Issue cosmético o documentación

Runbook operativo: ver [docs/SECURITY_RUNBOOK.md](docs/SECURITY_RUNBOOK.md).

### 3. Respuesta

**Crítica:**
1. Aislar sistema afectado
2. Evaluar alcance del compromiso
3. Notificar stakeholders
4. Implementar fix de emergencia
5. Comunicación pública si es necesario

**Alta/Media:**
1. Investigar root cause
2. Desarrollar fix
3. Testing en staging
4. Deploy coordinado
5. Monitoreo post-fix

### 4. Post-Mortem

- Documentar timeline del incidente
- Identificar mejoras en procesos
- Actualizar runbooks
- Implementar prevenciones adicionales

## 📞 Contactos de Emergencia

### Equipo de Seguridad

- **Reporte de vulnerabilidades**: abrir un issue privado en el repositorio o contactar directamente al maintainer
- **Incidentes en producción**: seguir el runbook en [RUNBOOK.md](RUNBOOK.md)

### Escalación

1. **Nivel 1**: Desarrollador on-call — diagnóstico inicial y mitigación
2. **Nivel 2**: Dueño del backend — cambios de configuración o rollback
3. **Nivel 3**: Infra/DB owner — incidentes de red, storage o DB crítica

## 🔄 Actualizaciones de Seguridad

### Proceso de Patches

1. **Evaluación**: Análisis de impacto y urgencia
2. **Desarrollo**: Fix en rama de security
3. **Testing**: Tests automatizados + manual
4. **Staging**: Deploy en ambiente de pruebas
5. **Producción**: Deploy coordinado
6. **Verificación**: Monitoreo post-deploy

### Notificaciones

- **GitHub Security Advisories**: Para vulnerabilidades confirmadas
- **Email Newsletter**: Para actualizaciones importantes
- **Discord Channel**: Para discusión de security

## 📚 Recursos Adicionales

### Documentación

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [API Security Best Practices](https://github.com/OWASP/API-Security)

### Training

- **Para el equipo**: Security awareness training anual
- **Para usuarios**: Guías de configuración segura
- **Para la comunidad**: Security best practices documentation

## 🔖 Versión de esta Política

- **Versión**: 1.1
- **Última actualización**: Abril 2026
- **Próxima revisión**: Julio 2026
- **Responsable**: Pablo Cubides

---

## ⚖️ Compliance

Este proyecto busca cumplir con:

- **GDPR**: Protección de datos personales en UE
- **CCPA**: Privacidad del consumidor en California
- **SOC 2**: Controles de seguridad para servicios
- **ISO 27001**: Gestión de seguridad de la información

---

*Para reportar vulnerabilidades: contactar al maintainer directamente a través del repositorio.*

*Esta política se revisa y actualiza regularmente.*
