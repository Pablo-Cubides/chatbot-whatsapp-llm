import asyncio
import contextvars
import json
import logging
import os
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable
import aiohttp
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from pythonjsonlogger import jsonlogger
except Exception:  # pragma: no cover
    jsonlogger = None

redis: Any
try:
    import redis
except Exception:
    redis = None

psutil: Any
try:
    import psutil as _psutil

    psutil = _psutil
except Exception:
    psutil = None

# Setup logger
logger = logging.getLogger(__name__)

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_ws_connections_lock = asyncio.Lock()
_ws_connections_count = 0

from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from src.models.admin_db import cleanup_connections, get_session, initialize_schema
from src.services.audit_system import log_security_event

# Import auth dependencies
from src.services.auth_system import auth_manager, get_current_user
from src.services.http_rate_limit import http_rate_limiter
from src.services.multi_provider_llm import llm_manager
from src.services.queue_system import queue_manager
from src.services.metrics import inc_counter, observe_histogram, set_gauge


class RuntimeEnvSettings(BaseSettings):
    """Runtime settings validated at startup to fail fast on missing/invalid env vars."""

    model_config = SettingsConfigDict(extra="ignore")

    jwt_secret: str = Field(alias="JWT_SECRET", min_length=32)
    admin_password: str = Field(alias="ADMIN_PASSWORD", min_length=8)
    whatsapp_mode: str = Field(alias="WHATSAPP_MODE", default="web")
    whatsapp_app_secret: str | None = Field(alias="WHATSAPP_APP_SECRET", default=None)


class RequestIdFilter(logging.Filter):
    """Inject request_id into log records for correlated request tracing."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get("-")
        return True


def _ensure_request_id_filter() -> None:
    """Attach request-id filter to root handlers once."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if not any(isinstance(existing_filter, RequestIdFilter) for existing_filter in handler.filters):
            handler.addFilter(RequestIdFilter())


def _configure_logging_output() -> None:
    """Enable structured JSON logging when LOG_FORMAT=json."""
    if os.getenv("LOG_FORMAT", "plain").strip().lower() != "json":
        return

    if jsonlogger is None:
        logger.warning("LOG_FORMAT=json solicitado pero python-json-logger no está disponible")
        return

    root_logger = logging.getLogger()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def validate_runtime_environment() -> RuntimeEnvSettings:
    """Validate critical runtime environment and raise explicit startup errors."""
    try:
        settings = RuntimeEnvSettings()  # type: ignore[call-arg]
    except ValidationError as validation_error:
        raise RuntimeError(f"Invalid runtime environment configuration: {validation_error}") from validation_error

    mode = settings.whatsapp_mode.strip().lower()
    if mode in {"cloud", "both"} and not settings.whatsapp_app_secret:
        raise RuntimeError("WHATSAPP_APP_SECRET is required when WHATSAPP_MODE is 'cloud' or 'both'.")

    return settings


def ensure_bot_disabled_by_default() -> None:
    """Ensure respond_to_all is false by default on startup"""
    settings_file = os.path.join(os.path.dirname(__file__), "data", "settings.json")
    try:
        if os.path.exists(settings_file):
            with open(settings_file, encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {}

        # Force respond_to_all to false on startup unless explicitly configured
        if "respond_to_all" not in settings:
            settings["respond_to_all"] = False

        # Save the settings
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        logger.info("Bot auto-responder set to: %s", settings["respond_to_all"])
    except Exception as e:
        logger.warning("Error ensuring bot disabled by default: %s", e)


def run_startup_migrations() -> None:
    """Run Alembic migrations automatically on startup when enabled."""
    auto_migrate = os.environ.get("AUTO_MIGRATE", "true").lower() == "true"
    if not auto_migrate:
        return

    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            logger.info("✅ Alembic migration completed")
        else:
            logger.warning("⚠️ Alembic migration skipped/failed: %s", (result.stderr or result.stdout).strip())
    except Exception as migration_error:
        logger.warning("⚠️ Alembic migration error: %s", migration_error)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    _ensure_request_id_filter()
    _configure_logging_output()
    validate_runtime_environment()
    run_startup_migrations()
    initialize_schema()  # type: ignore[no-untyped-call]
    ensure_bot_disabled_by_default()

    shared_http_session: aiohttp.ClientSession | None = None
    try:
        connector = aiohttp.TCPConnector(limit=max(100, int(os.getenv("HTTP_CLIENT_MAX_CONNECTIONS", "200"))))
        shared_http_session = aiohttp.ClientSession(connector=connector)
        llm_manager.set_http_session(shared_http_session)
        await llm_manager.initialize()
    except Exception as e:
        logger.warning("Error inicializando sesión HTTP compartida LLM: %s", e)

    yield
    # Shutdown
    try:
        llm_manager.set_http_session(None)
        if shared_http_session is not None and not shared_http_session.closed:
            await shared_http_session.close()
    except Exception as e:
        logger.warning("Error closing shared HTTP session: %s", e)

    try:
        await http_rate_limiter.aclose()
    except Exception as e:
        logger.warning("Error closing HTTP rate limiter: %s", e)

    try:
        cleanup_connections()  # type: ignore[no-untyped-call]
    except Exception as e:
        logger.warning("Error cleaning DB connections on shutdown: %s", e)


app = FastAPI(
    title="Chatbot Admin Panel",
    description=(
        "API de administración para chatbot WhatsApp con autenticación JWT, "
        "operación de mensajería, monitoreo, analítica y automatización de procesos."
    ),
    version=os.getenv("APP_VERSION", "1.0.0"),
    openapi_tags=[
        {"name": "auth", "description": "Autenticación y gestión de sesión"},
        {"name": "chat-core", "description": "Chat principal, prompts y settings"},
        {"name": "manual-messaging-admin", "description": "Mensajería manual y campañas"},
        {"name": "contacts", "description": "Gestión de contactos y perfiles"},
        {"name": "analytics", "description": "Métricas y paneles de operación"},
        {"name": "monitoring", "description": "Monitoreo y estado del sistema"},
        {"name": "webhooks", "description": "Integración con proveedores externos"},
    ],
    lifespan=lifespan,
)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Configure CORS from environment variable
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8003,http://127.0.0.1:8003")
_allowed_origins = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
# Allow localhost variants by default for development
if not _allowed_origins:
    _allowed_origins = ["http://localhost:8003", "http://127.0.0.1:8003"]

if any(origin == "*" for origin in _allowed_origins):
    logger.warning("⚠️ CORS_ORIGINS includes '*', forcing safe localhost defaults because credentials are enabled")
    _allowed_origins = ["http://localhost:8003", "http://127.0.0.1:8003"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Add baseline browser hardening headers for API and static UI responses."""
    response = await call_next(request)
    path = request.url.path

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    if path.startswith("/api"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )

    if path == "/chat":
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Attach/propagate X-Request-ID across request lifecycle and response headers."""
    inbound_request_id = (request.headers.get("X-Request-ID") or "").strip()
    request_id = inbound_request_id if inbound_request_id else uuid.uuid4().hex

    request_id_token = request_id_ctx_var.set(request_id)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx_var.reset(request_id_token)


@app.middleware("http")
async def metrics_http_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Collect baseline HTTP metrics for Prometheus export."""
    start_time = asyncio.get_event_loop().time()
    response = await call_next(request)

    elapsed = max(0.0, asyncio.get_event_loop().time() - start_time)
    inc_counter("http_requests")
    observe_histogram("http_request_duration_seconds", elapsed)
    return response

# Mount simple static UI
ui_path = os.path.join(os.path.dirname(__file__), "ui")
if os.path.isdir(ui_path):
    app.mount("/ui", StaticFiles(directory=ui_path), name="ui")

# ═══════════════════════════════════════════════════════════════
# 🔌 INCLUDE EXTRACTED ROUTERS (source of truth)
# ═══════════════════════════════════════════════════════════════
try:
    from src.routers.analysis_adaptive import router as analysis_adaptive_router
    from src.routers.ai_models_admin import router as ai_models_admin_router
    from src.routers.auth import router as auth_router
    from src.routers.analytics import router as analytics_router
    from src.routers.business_config import router as business_config_router
    from src.routers.calendar_admin import router as calendar_admin_router
    from src.routers.campaigns import router as campaigns_router
    from src.routers.chat_core import router as chat_core_router
    from src.routers.chat_files_admin import router as chat_files_admin_router
    from src.routers.contexts_data import router as contexts_data_router
    from src.routers.contacts import router as contacts_router
    from src.routers.lmstudio_admin import router as lmstudio_admin_router
    from src.routers.legacy_admin_data import router as legacy_admin_data_router
    from src.routers.legacy_compat import router as legacy_compat_router
    from src.routers.manual_messaging_admin import router as manual_messaging_admin_router
    from src.routers.model_switch_admin import router as model_switch_admin_router
    from src.routers.models_online import router as models_online_router
    from src.routers.monitoring import router as monitoring_router
    from src.routers.system_admin import router as system_admin_router
    from src.routers.whatsapp_provider import router as whatsapp_provider_router
    from src.routers.whatsapp_runtime_admin import router as whatsapp_runtime_admin_router
    from src.routers.webhooks import router as webhooks_router

    app.include_router(auth_router)
    app.include_router(ai_models_admin_router)
    app.include_router(monitoring_router)
    app.include_router(campaigns_router)
    app.include_router(business_config_router)
    app.include_router(webhooks_router)
    app.include_router(analysis_adaptive_router)
    app.include_router(chat_core_router)
    app.include_router(chat_files_admin_router)
    app.include_router(analytics_router)
    app.include_router(calendar_admin_router)
    app.include_router(contexts_data_router)
    app.include_router(contacts_router)
    app.include_router(legacy_admin_data_router)
    app.include_router(legacy_compat_router)
    app.include_router(lmstudio_admin_router)
    app.include_router(manual_messaging_admin_router)
    app.include_router(model_switch_admin_router)
    app.include_router(models_online_router)
    app.include_router(system_admin_router)
    app.include_router(whatsapp_provider_router)
    app.include_router(whatsapp_runtime_admin_router)
    logger.info("✅ Routers modulares cargados correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudieron cargar routers modulares: {e}")

try:
    from src.routers.metrics import router as metrics_router

    app.include_router(metrics_router)
    logger.info("✅ Metrics endpoint disponible en /metrics")
except ImportError as e:
    logger.warning(f"⚠️ Metrics endpoint no disponible: {e}")


PUBLIC_API_PATHS = {"/api/auth/login", "/api/auth/refresh"}


PUBLIC_API_PATHS.update(
    {
        "/api/calendar/oauth/google/callback",
        "/api/calendar/oauth/outlook/callback",
    }
)


def _authenticate_bearer_token(token: str) -> dict[str, Any] | None:
    """Authenticate bearer token using JWT only."""
    return auth_manager.verify_token(token)


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Apply global API rate limiting with per-endpoint buckets."""
    path = request.url.path

    if request.method == "OPTIONS" or not path.startswith("/api"):
        return await call_next(request)

    identifier = http_rate_limiter.get_client_identifier(request)
    allowed, info = await http_rate_limiter.check_request(path=path, identifier=identifier)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "info": info},
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset"]),
                "Retry-After": str(info["retry_after"]),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset"])
    return response


@app.middleware("http")
async def enforce_api_auth(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Enforce bearer authentication for all protected /api routes."""
    path = request.url.path

    if request.method == "OPTIONS":
        return await call_next(request)

    if not path.startswith("/api"):
        return await call_next(request)

    if path in PUBLIC_API_PATHS:
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing authentication token"})

    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Missing authentication token"})

    payload = _authenticate_bearer_token(token)
    if payload is None:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired authentication token"})

    return await call_next(request)


@app.exception_handler(HTTPException)
async def sanitized_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Prevent leaking internal exception details in 5xx HTTP errors."""
    if exc.status_code >= 500:
        logger.error("❌ HTTP %s at %s", exc.status_code, request.url.path)
        if request.url.path.startswith("/api"):
            return JSONResponse(status_code=exc.status_code, content={"detail": "Internal server error"})

        custom_500 = os.path.join(os.path.dirname(__file__), "ui", "500.html")
        if os.path.isfile(custom_500):
            try:
                with open(custom_500, "r", encoding="utf-8") as file_handler:
                    return HTMLResponse(content=file_handler.read(), status_code=exc.status_code)
            except OSError:
                logger.exception("❌ Failed to load custom 500 page")

        return HTMLResponse(content="<h1>500</h1><p>Error interno del servidor.</p>", status_code=exc.status_code)

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(StarletteHTTPException)
async def not_found_html_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Return branded HTML 404 for UI/browser requests and JSON for API requests."""
    if exc.status_code != 404:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    custom_404 = os.path.join(os.path.dirname(__file__), "ui", "404.html")
    if os.path.isfile(custom_404):
        try:
            with open(custom_404, "r", encoding="utf-8") as file_handler:
                return HTMLResponse(content=file_handler.read(), status_code=404)
        except OSError:
            logger.exception("❌ Failed to load custom 404 page")

    return HTMLResponse(content="<h1>404</h1><p>Página no encontrada.</p>", status_code=404)

@app.exception_handler(Exception)
async def sanitized_unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Catch-all exception handler with safe client message."""
    logger.exception("❌ Unhandled error at %s", request.url.path)
    if not request.url.path.startswith("/api"):
        custom_500 = os.path.join(os.path.dirname(__file__), "ui", "500.html")
        if os.path.isfile(custom_500):
            try:
                with open(custom_500, "r", encoding="utf-8") as file_handler:
                    return HTMLResponse(content=file_handler.read(), status_code=500)
            except OSError:
                logger.exception("❌ Failed to load custom 500 page")

        return HTMLResponse(content="<h1>500</h1><p>Error interno del servidor.</p>", status_code=500)

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Health and root endpoints (don't require auth)
@app.get("/", response_class=JSONResponse)
def root() -> dict[str, str]:
    return {"status": "ok", "app": "admin-panel", "version": "1.0"}


@app.get("/healthz", response_class=JSONResponse, response_model=None)
def health() -> Response:
    db_status: dict[str, Any] = {"status": "unhealthy"}
    redis_status: dict[str, Any] = {"status": "not_configured"}
    disk_status: dict[str, Any] = {"status": "unknown"}
    memory_status: dict[str, Any] = {"status": "unknown"}
    db_failed = False

    overall_ok = True

    # Database check
    try:
        session = get_session()  # type: ignore[no-untyped-call]
        session.execute(text("SELECT 1"))
        session.close()
        db_status = {"status": "ok"}
    except Exception:
        overall_ok = False
        db_status = {"status": "unhealthy"}
        db_failed = True

    # Contrato crítico fase 0: ante fallo de DB, responder mínimo y sin detalles internos.
    if db_failed:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})

    # Redis check (if configured)
    redis_url = os.environ.get("REDIS_URL")
    redis_password = os.environ.get("REDIS_PASSWORD")
    if redis is not None and (redis_url or redis_password):
        try:
            client = (
                redis.from_url(redis_url)
                if redis_url
                else redis.Redis(host="localhost", port=6379, password=redis_password)
            )
            pong = client.ping()
            redis_status = {"status": "ok" if pong else "unhealthy"}
            if not pong:
                overall_ok = False
        except Exception as exc:
            overall_ok = False
            redis_status = {"status": "unhealthy", "error": str(exc)}

    # Disk space check
    try:
        usage = shutil.disk_usage(os.getcwd())
        free_percent = (usage.free / usage.total) * 100 if usage.total else 0.0
        disk_ok = free_percent >= 5.0
        disk_status = {
            "status": "ok" if disk_ok else "unhealthy",
            "free_percent": round(free_percent, 2),
            "free_bytes": usage.free,
        }
        if not disk_ok:
            overall_ok = False
    except Exception as exc:
        overall_ok = False
        disk_status = {"status": "unhealthy", "error": str(exc)}

    # Memory check
    try:
        if psutil is not None:
            vm = psutil.virtual_memory()
            available_percent = (vm.available / vm.total) * 100 if vm.total else 0.0
            memory_ok = available_percent >= 5.0
            memory_status = {
                "status": "ok" if memory_ok else "unhealthy",
                "available_percent": round(available_percent, 2),
                "available_bytes": vm.available,
            }
            if not memory_ok:
                overall_ok = False
        else:
            memory_status = {"status": "unknown", "reason": "psutil not available"}
    except Exception as exc:
        overall_ok = False
        memory_status = {"status": "unhealthy", "error": str(exc)}

    payload = {
        "status": "ok" if overall_ok else "unhealthy",
        "components": {
            "database": db_status,
            "redis": redis_status,
            "disk": disk_status,
            "memory": memory_status,
        },
    }
    return JSONResponse(status_code=200 if overall_ok else 503, content=payload)


@app.get("/favicon.ico")
def favicon() -> Response:
    """Return a simple favicon response"""
    from fastapi.responses import Response

    # Simple 1x1 transparent PNG
    favicon_bytes = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x06,
            0x00,
            0x00,
            0x00,
            0x1F,
            0x15,
            0xC4,
            0x89,
            0x00,
            0x00,
            0x00,
            0x0A,
            0x49,
            0x44,
            0x41,
            0x54,
            0x78,
            0x9C,
            0x63,
            0x00,
            0x01,
            0x00,
            0x00,
            0x05,
            0x00,
            0x01,
            0x0D,
            0x0A,
            0x2D,
            0xB4,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )
    return Response(content=favicon_bytes, media_type="image/png")


# --- Dashboard redirect endpoint for easier access ---
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(current_user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    """Redirect to the main dashboard UI"""
    return HTMLResponse('<script>window.location.href="/ui/index.html"</script>')


# --- Minimal web chat UI -------------------------------------------------
@app.get("/chat", response_class=HTMLResponse)
def chat_ui(request: Request, current_user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse("chat_quick.html", {"request": request})


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket) -> None:
    global _ws_connections_count
    if websocket.query_params.get("token"):
        log_security_event(
            "ws_token_in_query",
            username="unknown",
            role="unknown",
            ip=websocket.client.host if websocket.client else None,
            user_agent=websocket.headers.get("user-agent"),
            success=False,
            details={"reason": "query_token_forbidden"},
            error="WebSocket token in URL query is forbidden",
        )
        await websocket.close(code=1008, reason="Token in URL query forbidden")
        return

    await websocket.accept()

    token = ""
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        if isinstance(auth_message, dict) and auth_message.get("type") == "auth":
            candidate = auth_message.get("token")
            token = candidate.strip() if isinstance(candidate, str) else ""
    except Exception:
        token = ""

    payload = auth_manager.verify_token(token, expected_type="ws") if token else None
    if payload is None:
        log_security_event(
            "ws_unauthorized",
            username="unknown",
            role="unknown",
            ip=websocket.client.host if websocket.client else None,
            user_agent=websocket.headers.get("user-agent"),
            success=False,
            details={"reason": "invalid_or_missing_ws_token"},
            error="Unauthorized websocket access",
        )
        await websocket.close(code=1008, reason="Unauthorized")
        return

    if payload.get("ws_scope") != "metrics":
        log_security_event(
            "ws_invalid_scope",
            username=payload.get("sub", "unknown"),
            role=payload.get("role", "unknown"),
            ip=websocket.client.host if websocket.client else None,
            user_agent=websocket.headers.get("user-agent"),
            success=False,
            details={"scope": payload.get("ws_scope", "unknown")},
            error="Invalid websocket scope",
        )
        await websocket.close(code=1008, reason="Invalid websocket scope")
        return

    try:
        async with _ws_connections_lock:
            _ws_connections_count += 1
            set_gauge("active_ws_connections", float(_ws_connections_count))
        while True:
            await websocket.send_json(
                {
                    "type": "metrics",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "queue_pending": len(queue_manager.get_pending_messages(limit=200)),
                }
            )
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
    finally:
        async with _ws_connections_lock:
            _ws_connections_count = max(0, _ws_connections_count - 1)
            set_gauge("active_ws_connections", float(_ws_connections_count))


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Chatbot Admin Panel on http://127.0.0.1:8003")
    logger.info("Dashboard: http://127.0.0.1:8003/ui/index.html")
    logger.info("Quick Chat: http://127.0.0.1:8003/chat")
    uvicorn.run(app, host="127.0.0.1", port=8003, reload=False)
