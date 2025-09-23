# 🛠️ Development Guide

## Overview

This comprehensive development guide covers the technical implementation details, coding standards, testing strategies, and best practices for the WhatsApp LLM Chatbot platform.

## Development Environment Setup

### Prerequisites
```bash
# Core requirements
Python 3.11+ (recommended)
Node.js 18+ (for frontend development)
Docker Desktop (for containerized development)
Git (latest version)

# Development tools
pip install -r requirements-dev.txt
pre-commit install
```

### Environment Configuration
```bash
# Clone repository
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm

# Create development environment
python -m venv venv-dev
source venv-dev/bin/activate  # Linux/Mac
# or
venv-dev\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .  # Editable install for development

# Setup pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Code Organization & Architecture

### Directory Structure
```
chatbot-whatsapp-llm/
├── src/
│   ├── core/                 # Core business logic
│   │   ├── domain/          # Domain models & entities
│   │   ├── services/        # Business services
│   │   └── repositories/    # Data access layer
│   ├── infrastructure/      # Infrastructure concerns
│   │   ├── api/            # REST API endpoints
│   │   ├── messaging/      # Message processing
│   │   ├── persistence/    # Database & storage
│   │   └── external/       # External integrations
│   └── shared/             # Shared utilities
│       ├── config/         # Configuration management
│       ├── logging/        # Logging infrastructure
│       ├── security/       # Security utilities
│       └── testing/        # Testing utilities
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── e2e/                # End-to-end tests
│   └── fixtures/           # Test data & mocks
├── docs/                   # Documentation
├── scripts/                # Development scripts
├── docker/                 # Docker configurations
└── tools/                  # Development tools
```

### Architectural Patterns

#### 1. **Clean Architecture Implementation**
```
└── Core Business Logic (Entities, Use Cases)
    └── Application Layer (Services, DTOs)
        └── Infrastructure Layer (External Concerns)
            └── Frameworks & Drivers (Web, DB, External APIs)
```

**Benefits**:
- **Testability**: Business logic isolated from external dependencies
- **Maintainability**: Clear separation of concerns
- **Flexibility**: Easy to swap implementations
- **Independence**: Framework-agnostic core logic

#### 2. **Dependency Injection Pattern**
```python
from typing import Protocol
from abc import ABC, abstractmethod

# Define interface
class MessageRepository(Protocol):
    async def save_message(self, message: Message) -> None:
        ...

    async def get_conversation(self, chat_id: str) -> List[Message]:
        ...

# Concrete implementation
class SQLiteMessageRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def save_message(self, message: Message) -> None:
        async with self.session_factory() as session:
            session.add(message)
            await session.commit()

# Service using dependency injection
class MessageService:
    def __init__(self, repository: MessageRepository):
        self.repository = repository

    async def process_message(self, message: Message) -> None:
        # Business logic here
        await self.repository.save_message(message)
```

#### 3. **Repository Pattern**
```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        pass

    @abstractmethod
    async def get_all(self) -> List[T]:
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        pass

    @abstractmethod
    async def delete(self, id: int) -> None:
        pass

class ConversationRepository(BaseRepository[Conversation]):
    async def get_by_chat_id(self, chat_id: str) -> List[Conversation]:
        query = select(Conversation).where(Conversation.chat_id == chat_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_recent_conversations(self, limit: int = 50) -> List[Conversation]:
        query = select(Conversation).order_by(
            Conversation.timestamp.desc()
        ).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
```

## Coding Standards & Best Practices

### Type Hints & Documentation
```python
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class MessageRequest(BaseModel):
    """Request model for sending messages.

    Attributes:
        content: The message content to send
        chat_id: Target WhatsApp chat identifier
        priority: Message priority level (1-5)
    """
    content: str = Field(..., min_length=1, max_length=4096)
    chat_id: str = Field(..., pattern=r'^\d+@c\.us$')
    priority: int = Field(default=3, ge=1, le=5)

async def send_message(
    request: MessageRequest,
    user_id: str,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Send a message through WhatsApp.

    This function handles the complete message sending workflow including:
    - Input validation
    - Rate limiting
    - Queue management
    - Error handling and retry logic

    Args:
        request: Validated message request
        user_id: ID of the user sending the message
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dictionary containing message ID and status

    Raises:
        MessageValidationError: If message validation fails
        RateLimitExceededError: If rate limit is exceeded
        WhatsAppConnectionError: If WhatsApp connection fails

    Example:
        >>> request = MessageRequest(
        ...     content="Hello, World!",
        ...     chat_id="1234567890@c.us"
        ... )
        >>> result = await send_message(request, "user123")
        >>> print(result)
        {'message_id': 'msg_123', 'status': 'queued'}
    """
    logger.info(
        "Sending message",
        extra={
            'user_id': user_id,
            'chat_id': request.chat_id,
            'correlation_id': correlation_id,
            'content_length': len(request.content)
        }
    )

    try:
        # Validate rate limits
        await check_rate_limit(user_id, request.priority)

        # Queue message for processing
        message_id = await queue_service.add_message(
            content=request.content,
            chat_id=request.chat_id,
            user_id=user_id,
            priority=request.priority
        )

        logger.info(
            "Message queued successfully",
            extra={'message_id': message_id}
        )

        return {
            'message_id': message_id,
            'status': 'queued',
            'estimated_delivery': datetime.utcnow() + timedelta(seconds=30)
        }

    except RateLimitExceededError as e:
        logger.warning(
            "Rate limit exceeded",
            extra={'user_id': user_id, 'retry_after': e.retry_after}
        )
        raise

    except Exception as e:
        logger.error(
            "Failed to send message",
            exc_info=True,
            extra={
                'user_id': user_id,
                'chat_id': request.chat_id,
                'correlation_id': correlation_id
            }
        )
        raise MessageProcessingError("Failed to queue message") from e
```

### Error Handling Patterns
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger(__name__)

class ApplicationError(Exception):
    """Base application error with context."""
    def __init__(self, message: str, code: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

class ValidationError(ApplicationError):
    """Validation error with field information."""
    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for field '{field}': {reason}",
            "VALIDATION_ERROR",
            {"field": field, "value": value, "reason": reason}
        )

class DatabaseError(ApplicationError):
    """Database operation error."""
    def __init__(self, operation: str, table: str, details: Dict):
        super().__init__(
            f"Database {operation} failed on table '{table}'",
            "DATABASE_ERROR",
            details
        )

@asynccontextmanager
async def database_transaction(session) -> AsyncGenerator[None, None]:
    """Database transaction context manager with error handling."""
    try:
        async with session.begin():
            yield
    except SQLAlchemyError as e:
        logger.error(
            "Database transaction failed",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        raise DatabaseError(
            "transaction",
            "unknown",
            {"original_error": str(e)}
        ) from e

async def create_conversation(
    chat_id: str,
    initial_message: str,
    user_id: str
) -> Conversation:
    """Create a new conversation with error handling."""
    if not chat_id or not isinstance(chat_id, str):
        raise ValidationError("chat_id", chat_id, "must be non-empty string")

    if not initial_message or len(initial_message.strip()) == 0:
        raise ValidationError("initial_message", initial_message, "cannot be empty")

    async with database_transaction(session_factory()) as session:
        # Check for existing conversation
        existing = await session.execute(
            select(Conversation).where(Conversation.chat_id == chat_id)
        )
        if existing.scalar_one_or_none():
            raise ApplicationError(
                f"Conversation already exists for chat {chat_id}",
                "DUPLICATE_CONVERSATION"
            )

        # Create new conversation
        conversation = Conversation(
            chat_id=chat_id,
            initial_message=initial_message,
            user_id=user_id,
            created_at=datetime.utcnow()
        )

        session.add(conversation)
        await session.flush()  # Get ID without committing

        logger.info(
            "Conversation created",
            extra={
                'conversation_id': conversation.id,
                'chat_id': chat_id,
                'user_id': user_id
            }
        )

        return conversation
```

## Testing Strategy

### Unit Testing with Mocks
```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pytest_asyncio import fixture

@fixture
async def mock_repository():
    """Mock repository for testing."""
    repo = Mock()
    repo.save_message = AsyncMock(return_value=None)
    repo.get_conversation = AsyncMock(return_value=[])
    return repo

@fixture
async def message_service(mock_repository):
    """Message service with mocked dependencies."""
    return MessageService(mock_repository)

@pytest.mark.asyncio
class TestMessageService:
    async def test_send_message_success(self, message_service, mock_repository):
        """Test successful message sending."""
        request = MessageRequest(
            content="Test message",
            chat_id="1234567890@c.us",
            priority=3
        )

        result = await message_service.send_message(request, "user123")

        assert result["status"] == "queued"
        assert "message_id" in result
        mock_repository.save_message.assert_called_once()

    async def test_send_message_validation_error(self, message_service):
        """Test message validation error."""
        request = MessageRequest(
            content="",  # Empty content should fail
            chat_id="1234567890@c.us"
        )

        with pytest.raises(ValidationError) as exc_info:
            await message_service.send_message(request, "user123")

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "content" in exc_info.value.details["field"]

    @patch('message_service.check_rate_limit')
    async def test_send_message_rate_limited(
        self, mock_rate_limit, message_service, mock_repository
    ):
        """Test rate limiting behavior."""
        mock_rate_limit.side_effect = RateLimitExceededError(
            retry_after=60
        )

        request = MessageRequest(
            content="Test message",
            chat_id="1234567890@c.us"
        )

        with pytest.raises(RateLimitExceededError):
            await message_service.send_message(request, "user123")

        # Verify message was not saved due to rate limit
        mock_repository.save_message.assert_not_called()
```

### Integration Testing
```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import docker

@pytest.fixture(scope="session")
def docker_compose():
    """Start docker-compose services for integration tests."""
    docker_compose = docker.from_env()

    # Start services
    docker_compose.up(detach=True, services=["db", "redis"])

    yield docker_compose

    # Cleanup
    docker_compose.down()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_message_flow(docker_compose, test_client: AsyncClient):
    """Test complete message sending workflow."""
    # Setup test data
    test_message = {
        "content": "Integration test message",
        "chat_id": "1234567890@c.us",
        "priority": 1
    }

    # Send message via API
    response = await test_client.post(
        "/api/messages",
        json=test_message,
        headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    result = response.json()

    # Verify message was queued
    assert result["status"] == "queued"
    assert "message_id" in result

    # Verify database state
    async with get_test_session() as session:
        message = await session.execute(
            select(QueuedMessage).where(
                QueuedMessage.id == result["message_id"]
            )
        )
        assert message.scalar_one() is not None

    # Verify Redis queue state
    redis_client = get_test_redis()
    queued_items = redis_client.lrange("message_queue", 0, -1)
    assert len(queued_items) > 0
```

### End-to-End Testing
```python
import pytest
from playwright.async_api import Browser, Page
import time

@pytest.mark.e2e
class TestWhatsAppIntegration:
    @pytest.fixture(autouse=True)
    async def setup_browser(self, browser: Browser):
        """Setup browser for WhatsApp testing."""
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await context.new_page()
        yield
        await context.close()

    async def test_whatsapp_message_detection(self):
        """Test real WhatsApp message detection."""
        # Navigate to WhatsApp Web
        await self.page.goto("https://web.whatsapp.com")

        # Wait for QR code (manual intervention required for E2E)
        await self.page.wait_for_selector("canvas", timeout=30000)

        # Mock message detection
        test_message = "E2E test message"
        await self.simulate_incoming_message(test_message)

        # Verify message detection
        detected_messages = await self.get_detected_messages()
        assert test_message in detected_messages

    async def test_message_response_flow(self):
        """Test complete message response workflow."""
        # Setup test scenario
        await self.setup_test_conversation()

        # Send test message
        await self.send_test_message("Hello, bot!")

        # Wait for response
        response = await self.wait_for_bot_response(timeout=30)

        # Verify response quality
        assert len(response) > 10
        assert not self.contains_errors(response)

        # Verify conversation state
        conversation = await self.get_conversation_state()
        assert conversation["message_count"] >= 2
        assert conversation["last_activity"] > time.time() - 60
```

## Performance Testing & Profiling

### Load Testing Setup
```python
import locust
from locust import HttpUser, task, between

class WhatsAppUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def send_message(self):
        """Simulate message sending."""
        self.client.post("/api/messages", json={
            "content": "Load test message",
            "chat_id": f"{self.user_id}@c.us",
            "priority": 3
        })

    @task(1)
    def get_conversation(self):
        """Simulate conversation retrieval."""
        self.client.get(f"/api/conversations/{self.user_id}")

    @task(1)
    def health_check(self):
        """Health check endpoint."""
        self.client.get("/healthz")

# Configuration for load testing
@locust.events.init.add_listener
def on_locust_init(environment, **kwargs):
    environment.host = "http://localhost:8014"
```

### Memory Profiling
```python
import tracemalloc
import psutil
import os
from memory_profiler import profile

@profile
def process_large_conversation():
    """Profile memory usage for large conversation processing."""
    tracemalloc.start()

    # Simulate large conversation processing
    conversations = load_large_dataset()

    for conversation in conversations:
        process_conversation(conversation)

    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
    print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")

    tracemalloc.stop()

def monitor_system_resources():
    """Monitor system resource usage."""
    process = psutil.Process(os.getpid())

    while True:
        cpu_percent = process.cpu_percent()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()

        print(f"CPU: {cpu_percent:.1f}%")
        print(f"Memory: {memory_info.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)")

        time.sleep(1)
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run linting
      run: |
        flake8 src/ tests/
        mypy src/
        black --check src/ tests/

    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml --cov-report=html

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Run security scan
      uses: securecodewarrior/github-action-bandit@v1
      with:
        path: src/

  docker:
    runs-on: ubuntu-latest
    needs: [test, security]
    steps:
    - uses: actions/checkout@v4

    - name: Build Docker image
      run: docker build -t whatsapp-llm-chatbot .

    - name: Run container tests
      run: |
        docker run --rm whatsapp-llm-chatbot python -m pytest tests/

    - name: Push to registry
      if: github.ref == 'refs/heads/main'
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker tag whatsapp-llm-chatbot myregistry/whatsapp-llm-chatbot:latest
        docker push myregistry/whatsapp-llm-chatbot:latest
```

## Debugging & Troubleshooting

### Advanced Logging Configuration
```python
import logging.config
from pythonjsonlogger import jsonlogger

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
            'level': 'DEBUG'
        }
    },
    'loggers': {
        'src': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO'
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### Debug Tools & Utilities
```python
import pdb
import traceback
import sys
from rich.console import Console
from rich.traceback import install

# Enhanced traceback display
install(show_locals=True)

console = Console()

def debug_function(func):
    """Decorator for debugging function calls."""
    def wrapper(*args, **kwargs):
        console.print(f"[bold blue]Calling {func.__name__}[/bold blue]")
        console.print(f"Args: {args}")
        console.print(f"Kwargs: {kwargs}")

        try:
            result = func(*args, **kwargs)
            console.print(f"[bold green]Success: {result}[/bold green]")
            return result
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            console.print_exception()
            raise
    return wrapper

def profile_function(func):
    """Decorator for profiling function performance."""
    def wrapper(*args, **kwargs):
        import time
        start_time = time.time()

        result = func(*args, **kwargs)

        end_time = time.time()
        duration = end_time - start_time

        console.print(f"[yellow]Function {func.__name__} took {duration:.4f} seconds[/yellow]")

        return result
    return wrapper
```

## Deployment & DevOps

### Infrastructure as Code
```hcl
# Terraform configuration for AWS deployment
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_ecs_cluster" "whatsapp_llm" {
  name = "whatsapp-llm-cluster"
}

resource "aws_ecs_service" "app" {
  name            = "whatsapp-llm-service"
  cluster         = aws_ecs_cluster.whatsapp_llm.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 3

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "whatsapp-llm"
    container_port   = 8014
  }
}

resource "aws_rds_instance" "database" {
  allocated_storage    = 20
  engine              = "postgres"
  engine_version      = "15.4"
  instance_class      = "db.t3.micro"
  db_name             = "chatbot"
  username            = var.db_username
  password            = var.db_password
  skip_final_snapshot = true
}
```

### Monitoring & Alerting
```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics definitions
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

MESSAGE_PROCESSED = Counter(
    'messages_processed_total',
    'Total messages processed'
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(time.time() - start_time)

    return response
```

This development guide demonstrates enterprise-level software engineering practices with comprehensive coverage of architecture, testing, performance optimization, and DevOps practices. The implementation showcases advanced concepts suitable for production environments with high scalability and reliability requirements.