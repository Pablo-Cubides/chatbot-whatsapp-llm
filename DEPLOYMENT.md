# 🚀 Deployment Guide

## Production Deployment Architecture

### Infrastructure Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   CDN (Static)  │
│    (AWS ALB)    │    │   (AWS API GW)  │    │   (CloudFront)  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Application Layer   │
                    │    (ECS Fargate)       │
                    │  ├─ API Service        │
                    │  ├─ Message Processor  │
                    │  └─ Background Worker  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Data Layer          │
                    │  ├─ PostgreSQL (RDS)   │
                    │  ├─ Redis (ElastiCache)│
                    │  └─ S3 (File Storage)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    External Services   │
                    │  ├─ WhatsApp Business  │
                    │  ├─ OpenAI API         │
                    │  └─ Monitoring Stack   │
                    └─────────────────────────┘
```

## Prerequisites

### System Requirements
```bash
# Minimum production requirements
- CPU: 2 vCPUs per service instance
- RAM: 4GB per service instance
- Storage: 50GB SSD per instance
- Network: 100Mbps minimum bandwidth

# Recommended for high availability
- CPU: 4 vCPUs per service instance
- RAM: 8GB per service instance
- Storage: 100GB SSD per instance
- Network: 1Gbps bandwidth
```

### Required Accounts & Services
```bash
# Cloud Infrastructure
- AWS Account with appropriate permissions
- Docker Hub or AWS ECR access
- Domain registrar (Route 53 or similar)

# External Services
- WhatsApp Business API access
- OpenAI API key (GPT-4 access recommended)
- Redis Cloud or AWS ElastiCache
- PostgreSQL database (AWS RDS recommended)

# Monitoring & Security
- DataDog or New Relic for monitoring
- AWS CloudWatch for logging
- SSL certificate (Let's Encrypt or AWS ACM)
```

## Environment Configuration

### Production Environment Variables
```bash
# Application Configuration
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@rds-host:5432/chatbot_prod
REDIS_URL=redis://elasticache-host:6379/0

# WhatsApp Configuration
WHATSAPP_API_URL=https://graph.facebook.com/v18.0/
WHATSAPP_ACCESS_TOKEN=your_production_access_token
WHATSAPP_VERIFY_TOKEN=your_verify_token

# OpenAI Configuration
OPENAI_API_KEY=your_production_openai_key
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=4096

# Security Configuration
SECRET_KEY=your_256_bit_secret_key
JWT_SECRET_KEY=your_jwt_secret_key
ENCRYPTION_KEY=your_32_byte_encryption_key

# External Services
S3_BUCKET=your-production-bucket
CLOUDFRONT_DISTRIBUTION_ID=your_distribution_id

# Monitoring
DATADOG_API_KEY=your_datadog_key
SENTRY_DSN=your_sentry_dsn
```

### Secrets Management
```python
# AWS Secrets Manager integration
import boto3
import json
from typing import Dict, Any

class SecretsManager:
    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client('secretsmanager', region_name=region_name)

    async def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """Retrieve secret from AWS Secrets Manager."""
        try:
            response = await self.client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise

# Usage in application
secrets_manager = SecretsManager()
secrets = await secrets_manager.get_secret("whatsapp-llm/production")

# Apply secrets to configuration
config.database_url = secrets['DATABASE_URL']
config.openai_api_key = secrets['OPENAI_API_KEY']
```

## Docker Production Setup

### Multi-Stage Dockerfile
```dockerfile
# Build stage
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8014/healthz || exit 1

# Expose port
EXPOSE 8014

# Start application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8014", "--workers", "4"]
```

### Docker Compose for Production
```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.prod
    image: whatsapp-llm-api:latest
    environment:
      - SERVICE_NAME=api
    env_file:
      - .env.production
    ports:
      - "8014:8014"
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8014/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    image: whatsapp-llm-worker:latest
    environment:
      - SERVICE_NAME=worker
    env_file:
      - .env.production
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    deploy:
      replicas: 3

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: chatbot_prod
      POSTGRES_USER: chatbot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## AWS ECS Deployment

### Task Definition
```json
{
  "family": "whatsapp-llm-task",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/whatsapp-llm:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8014,
          "hostPort": 8014,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "SERVICE_NAME", "value": "api"},
        {"name": "APP_ENV", "value": "production"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/db-url"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/whatsapp-llm",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8014/healthz || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Application Load Balancer Configuration
```hcl
resource "aws_lb" "main" {
  name               = "whatsapp-llm-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = true
}

resource "aws_lb_target_group" "api" {
  name        = "whatsapp-llm-api"
  port        = 8014
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/healthz"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate.cert.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
```

## Database Migration Strategy

### Production Database Setup
```sql
-- Create production database
CREATE DATABASE chatbot_prod;
GRANT ALL PRIVILEGES ON DATABASE chatbot_prod TO chatbot_user;

-- Create extensions
\c chatbot_prod;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_conversations_chat_id ON conversations(chat_id);
CREATE INDEX CONCURRENTLY idx_messages_conversation_id_timestamp ON messages(conversation_id, timestamp DESC);
CREATE INDEX CONCURRENTLY idx_messages_content_gin ON messages USING gin(content gin_trgm_ops);

-- Partitioning strategy for large tables
CREATE TABLE messages_y2024m01 PARTITION OF messages
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Create partitioning function
CREATE OR REPLACE FUNCTION create_monthly_partition(start_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    partition_start DATE;
    partition_end DATE;
BEGIN
    partition_name := 'messages_y' || TO_CHAR(start_date, 'YYYY') || 'm' || TO_CHAR(start_date, 'MM');
    partition_start := start_date;
    partition_end := start_date + INTERVAL '1 month';

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
        partition_name, partition_start, partition_end
    );

    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS idx_%s_timestamp ON %I (timestamp)',
        partition_name, partition_name
    );
END;
$$ LANGUAGE plpgsql;
```

### Migration Scripts
```python
# Alembic migration for production
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

def upgrade():
    # Create new table with improved structure
    op.create_table('conversations_new',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Migrate data
    op.execute(text("""
        INSERT INTO conversations_new (id, chat_id, user_id, created_at, updated_at, metadata)
        SELECT id, chat_id, user_id, created_at, COALESCE(updated_at, created_at), NULL
        FROM conversations
    """))

    # Rename tables
    op.rename_table('conversations', 'conversations_old')
    op.rename_table('conversations_new', 'conversations')

    # Recreate indexes
    op.create_index('idx_conversations_chat_id', 'conversations', ['chat_id'])
    op.create_index('idx_conversations_user_id', 'conversations', ['user_id'])

    # Drop old table
    op.drop_table('conversations_old')

def downgrade():
    # Implement rollback logic
    pass
```

## Monitoring & Observability

### Application Metrics
```python
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from fastapi import Request, Response
import time

# Custom registry for production
registry = CollectorRegistry()

# Business metrics
MESSAGES_PROCESSED = Counter(
    'whatsapp_messages_processed_total',
    'Total messages processed',
    ['status', 'priority'],
    registry=registry
)

CONVERSATION_DURATION = Histogram(
    'conversation_duration_seconds',
    'Conversation duration in seconds',
    ['outcome'],
    registry=registry
)

ACTIVE_USERS = Gauge(
    'active_users',
    'Number of active users',
    registry=registry
)

# System metrics
MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes',
    ['type'],
    registry=registry
)

CPU_USAGE = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage',
    registry=registry
)

# Middleware for request metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise
    finally:
        duration = time.time() - start_time

        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

    return response
```

### Logging Configuration
```python
import logging
from pythonjsonlogger import jsonlogger
import sys

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add custom fields
        log_record['service'] = 'whatsapp-llm'
        log_record['version'] = '1.0.0'
        log_record['environment'] = os.getenv('APP_ENV', 'development')

        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

        # Add user context if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id

# Production logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': CustomJsonFormatter,
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'stream': sys.stdout
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json'
        }
    },
    'loggers': {
        'src': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO'
    }
}
```

### Health Checks & Readiness Probes
```python
from fastapi import APIRouter, HTTPException
import psutil
import asyncio
from typing import Dict, Any

router = APIRouter()

@router.get("/healthz")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "whatsapp-llm-api"
    }

@router.get("/readyz")
async def readiness_check() -> Dict[str, Any]:
    """Readiness probe for Kubernetes."""
    checks = await perform_readiness_checks()

    if not all(checks.values()):
        raise HTTPException(status_code=503, detail="Service not ready")

    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/livez")
async def liveness_check() -> Dict[str, Any]:
    """Liveness probe for Kubernetes."""
    # Check basic system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    if cpu_percent > 95 or memory.percent > 95:
        raise HTTPException(status_code=503, detail="System resources critical")

    return {
        "status": "alive",
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "timestamp": datetime.utcnow().isoformat()
    }

async def perform_readiness_checks() -> Dict[str, bool]:
    """Perform comprehensive readiness checks."""
    checks = {}

    # Database connectivity
    try:
        async with database_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Redis connectivity
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    # External services
    try:
        # Check WhatsApp API
        await check_whatsapp_connectivity()
        checks["whatsapp_api"] = True
    except Exception:
        checks["whatsapp_api"] = False

    try:
        # Check OpenAI API
        await check_openai_connectivity()
        checks["openai_api"] = True
    except Exception:
        checks["openai_api"] = False

    return checks
```

## Security Hardening

### SSL/TLS Configuration
```nginx
# Nginx configuration for SSL termination
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/ssl/certs/yourdomain.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    # Rate limiting
    limit_req zone=api burst=10 nodelay;

    location / {
        proxy_pass http://localhost:8014;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Backup & Disaster Recovery
```bash
#!/bin/bash
# Production backup script

BACKUP_DIR="/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="whatsapp_llm_backup_$TIMESTAMP"

# Database backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > $BACKUP_DIR/$BACKUP_NAME.sql

# Compress backup
gzip $BACKUP_DIR/$BACKUP_NAME.sql

# Upload to S3
aws s3 cp $BACKUP_DIR/$BACKUP_NAME.sql.gz s3://$S3_BACKUP_BUCKET/

# Cleanup old backups (keep last 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# Verify backup integrity
if ! pg_restore --list $BACKUP_DIR/$BACKUP_NAME.sql.gz > /dev/null; then
    echo "Backup verification failed!"
    exit 1
fi

echo "Backup completed successfully: $BACKUP_NAME"
```

### Incident Response Plan
```yaml
# Incident response runbook
incident_response:
  severity_levels:
    - name: "Critical"
      description: "Complete service outage"
      response_time: "15 minutes"
      communication: "Immediate notification to all stakeholders"

    - name: "High"
      description: "Major functionality impacted"
      response_time: "1 hour"
      communication: "Update every 30 minutes"

    - name: "Medium"
      description: "Minor functionality impacted"
      response_time: "4 hours"
      communication: "Daily updates"

    - name: "Low"
      description: "Cosmetic issues"
      response_time: "24 hours"
      communication: "Weekly summary"

  escalation_procedure:
    - "Level 1: On-call engineer"
    - "Level 2: Senior engineer (+30 min)"
    - "Level 3: Engineering manager (+1 hour)"
    - "Level 4: CTO (+2 hours)"

  communication_template: |
    Subject: [INCIDENT] WhatsApp LLM Chatbot - {severity} - {description}

    Status: {status}
    Impact: {impact_description}
    Timeline:
    - {timestamp}: Incident detected
    - {timestamp}: Investigation started
    - {timestamp}: Root cause identified
    - {timestamp}: Fix deployed

    Next Update: {next_update_time}
```

## Performance Optimization

### Database Optimization
```sql
-- Query optimization
EXPLAIN ANALYZE
SELECT c.chat_id, COUNT(m.id) as message_count,
       AVG(EXTRACT(EPOCH FROM (m.timestamp - c.created_at))) as avg_response_time
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
WHERE c.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.chat_id
ORDER BY message_count DESC
LIMIT 100;

-- Index optimization
CREATE INDEX CONCURRENTLY idx_messages_timestamp_covering
ON messages (timestamp DESC)
INCLUDE (conversation_id, content, sender_type);

-- Partition maintenance
CREATE OR REPLACE FUNCTION maintain_partitions()
RETURNS VOID AS $$
DECLARE
    next_month DATE := CURRENT_DATE + INTERVAL '1 month';
BEGIN
    -- Create next month's partition
    PERFORM create_monthly_partition(next_month);

    -- Drop old partitions (keep 1 year)
    FOR partition_name IN
        SELECT tablename FROM pg_tables
        WHERE tablename LIKE 'messages_y%'
        AND tablename < 'messages_y' || TO_CHAR(CURRENT_DATE - INTERVAL '1 year', 'YYYYMM')
    LOOP
        EXECUTE format('DROP TABLE %I', partition_name);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### Caching Strategy
```python
from cachetools import TTLCache
from typing import Optional, Any
import asyncio
import json

class CacheManager:
    def __init__(self, redis_client, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.local_cache = TTLCache(maxsize=1000, ttl=ttl_seconds)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with fallback."""
        # Try local cache first
        if key in self.local_cache:
            return self.local_cache[key]

        # Try Redis
        try:
            value = await self.redis.get(key)
            if value:
                # Cache locally for faster access
                parsed_value = json.loads(value)
                self.local_cache[key] = parsed_value
                return parsed_value
        except Exception:
            pass

        return None

    async def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        try:
            # Store in Redis
            await self.redis.setex(key, self.ttl, json.dumps(value))

            # Store locally
            self.local_cache[key] = value
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache keys matching pattern."""
        try:
            # Invalidate Redis keys
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)

            # Invalidate local cache
            keys_to_delete = [k for k in self.local_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.local_cache[key]
        except Exception as e:
            logger.warning(f"Cache invalidation failed for pattern {pattern}: {e}")

# Usage examples
cache = CacheManager(redis_client)

# Cache user profile
await cache.set(f"user:{user_id}", user_profile)

# Cache conversation summary
await cache.set(f"conversation:{chat_id}:summary", summary)

# Invalidate user cache on update
await cache.invalidate_pattern(f"user:{user_id}*")
```

## Scaling Strategies

### Horizontal Scaling
```python
# Auto-scaling configuration
auto_scaling_config = {
    "min_instances": 2,
    "max_instances": 20,
    "target_cpu_utilization": 70,
    "target_memory_utilization": 80,
    "scale_up_cooldown": 300,  # 5 minutes
    "scale_down_cooldown": 600,  # 10 minutes
}

# Load balancer configuration
load_balancer_config = {
    "health_check_path": "/healthz",
    "health_check_interval": 30,
    "unhealthy_threshold": 2,
    "healthy_threshold": 2,
    "timeout": 5,
    "stickiness_enabled": True,
    "stickiness_duration": 3600,  # 1 hour
}
```

### Database Scaling
```sql
-- Read replica configuration
-- Primary database for writes
-- Read replicas for read operations

-- Connection routing
CREATE OR REPLACE FUNCTION get_replica_connection()
RETURNS TEXT AS $$
DECLARE
    replica_host TEXT;
BEGIN
    -- Simple round-robin load balancing
    SELECT host INTO replica_host
    FROM read_replicas
    ORDER BY last_used ASC
    LIMIT 1;

    -- Update last used timestamp
    UPDATE read_replicas SET last_used = NOW() WHERE host = replica_host;

    RETURN replica_host;
END;
$$ LANGUAGE plpgsql;
```

This deployment guide provides comprehensive production-ready configurations for deploying the WhatsApp LLM Chatbot at enterprise scale with high availability, security, and performance optimizations.