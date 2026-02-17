"""
🤖 Gestor de APIs Multi-Proveedor para Chatbot Universal
Maneja múltiples proveedores de IA con fallback automático
Incluye sistema de humanización y detección de respuestas bot
"""

import logging
import os
import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Importar sistema de humanización
try:
    from src.services.humanized_responses import humanized_responses, sensitive_handler
    from src.services.silent_transfer import TransferReason, silent_transfer_manager

    HUMANIZATION_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Sistema de humanización no disponible")
    HUMANIZATION_AVAILABLE = False

# Importar context loader para inyección de contextos
try:
    from src.services.context_loader import context_loader

    CONTEXT_LOADER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Context loader no disponible")
    CONTEXT_LOADER_AVAILABLE = False

try:
    from src.services.cache_system import cache_llm_response, get_cached_llm_response

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

try:
    from src.services.protection_system import CircuitBreakerOpenException, get_or_create_circuit_breaker

    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

try:
    from src.services.metrics import inc_counter, observe_histogram

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


class LLMProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"
    LM_STUDIO = "lmstudio"
    XAI = "xai"
    GROK = "grok"  # Alias para xAI


@dataclass
class APIConfig:
    name: str
    api_key: Optional[str]
    base_url: str
    model: str
    active: bool = True
    max_tokens: int = 2000
    temperature: float = 0.7
    is_reasoning: bool = False  # Para distinguir modelos de razonamiento
    is_free: bool = False  # Para identificar modelos gratuitos


class MultiProviderLLM:
    def __init__(self):
        self.providers = {}
        self.fallback_order = []
        self._http_session: Optional[aiohttp.ClientSession] = None
        self.provider_timeout_seconds = int(os.getenv("LLM_PROVIDER_TIMEOUT_SECONDS", "30"))
        self.retry_base_delay_seconds = float(os.getenv("LLM_RETRY_BASE_DELAY_SECONDS", "0.5"))
        self.cache_enabled = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
        self.cache_ttl_seconds = int(os.getenv("LLM_CACHE_TTL_SECONDS", "3600"))
        self.load_configurations()

    def load_configurations(self):
        """Carga configuraciones de todos los proveedores desde .env"""

        # Gemini (Excelente relación calidad/precio, bueno para uso general)
        if os.getenv("GEMINI_API_KEY"):
            self.providers[LLMProvider.GEMINI] = APIConfig(
                name="Google Gemini",
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta",
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                is_reasoning=False,
                is_free=True,  # 15 RPM gratuitas
            )

        # xAI Grok (Excelente para razonamiento y análisis crítico)
        if os.getenv("XAI_API_KEY"):
            self.providers[LLMProvider.XAI] = APIConfig(
                name="xAI Grok",
                api_key=os.getenv("XAI_API_KEY"),
                base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
                model=os.getenv("XAI_MODEL", "grok-beta"),
                is_reasoning=True,  # Excelente para razonamiento
                is_free=True,  # Límites generosos en beta
            )

        # OpenAI (Mejor calidad general, pero más caro)
        if os.getenv("OPENAI_API_KEY"):
            self.providers[LLMProvider.OPENAI] = APIConfig(
                name="OpenAI",
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                is_reasoning=True,  # GPT-4 es bueno para razonamiento
                is_free=False,  # Pago después del crédito inicial
            )

        # Claude (Excelente para análisis profundo)
        if os.getenv("CLAUDE_API_KEY"):
            self.providers[LLMProvider.CLAUDE] = APIConfig(
                name="Anthropic Claude",
                api_key=os.getenv("CLAUDE_API_KEY"),
                base_url="https://api.anthropic.com",
                model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
                is_reasoning=True,
                is_free=False,
            )

        # Proveedores locales: se registran sin hacer I/O durante import/init.
        self.providers[LLMProvider.OLLAMA] = APIConfig(
            name="Ollama (Local)",
            api_key=None,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            is_reasoning=False,
            is_free=True,
            active=False,
        )

        self.providers[LLMProvider.LM_STUDIO] = APIConfig(
            name="LM Studio (Local)",
            api_key=None,
            base_url=os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1"),
            model=os.getenv("LM_STUDIO_MODEL", "nemotron-mini-4b-instruct"),
            is_reasoning=False,
            is_free=True,
            active=False,
        )

        # Configurar orden de fallback inteligente
        self._setup_intelligent_fallback()

        logger.info("Configurados %s proveedores de IA", len(self.providers))
        self._log_provider_capabilities()

    async def _check_ollama_available_async(self) -> bool:
        """Verifica asíncronamente si Ollama está disponible."""
        timeout = aiohttp.ClientTimeout(total=3)
        url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/version"
        try:
            async with self._session_scope() as session:
                async with session.get(url, timeout=timeout) as response:
                    return response.status == 200
        except Exception:
            return False

    async def _check_lmstudio_available_async(self) -> bool:
        """Verifica asíncronamente si LM Studio está disponible."""
        timeout = aiohttp.ClientTimeout(total=3)
        url = f"{os.getenv('LM_STUDIO_URL', 'http://127.0.0.1:1234')}/v1/models"
        try:
            async with self._session_scope() as session:
                async with session.get(url, timeout=timeout) as response:
                    return response.status == 200
        except Exception:
            return False

    def set_http_session(self, session: Optional[aiohttp.ClientSession]) -> None:
        """Inject shared aiohttp session managed by app lifespan."""
        self._http_session = session

    async def initialize(self) -> None:
        """Initialize runtime provider availability checks (no import-time I/O)."""
        try:
            ollama_available, lmstudio_available = await asyncio.gather(
                self._check_ollama_available_async(),
                self._check_lmstudio_available_async(),
            )

            if LLMProvider.OLLAMA in self.providers:
                self.providers[LLMProvider.OLLAMA].active = bool(ollama_available)
            if LLMProvider.LM_STUDIO in self.providers:
                self.providers[LLMProvider.LM_STUDIO].active = bool(lmstudio_available)

            self._setup_intelligent_fallback()
            logger.info(
                "LLM initialize: ollama=%s lmstudio=%s",
                ollama_available,
                lmstudio_available,
            )
        except Exception as e:
            logger.warning("LLM initialize warning: %s", e)

    @asynccontextmanager
    async def _session_scope(self):
        """Provide shared ClientSession when available; otherwise a short-lived one."""
        if self._http_session is not None and not self._http_session.closed:
            yield self._http_session
            return

        timeout = aiohttp.ClientTimeout(total=self.provider_timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            yield session

    def _setup_intelligent_fallback(self):
        """Configura orden de fallback inteligente basado en benchmarks y uso"""

        # Para conversaciones normales: Priorizar calidad/precio y velocidad
        self.normal_fallback = []
        self.reasoning_fallback = []
        self.free_only_fallback = []

        # Orden personalizado desde .env o por defecto basado en benchmarks
        fallback_order_env = os.getenv("AI_FALLBACK_ORDER", "gemini,xai,openai,claude,ollama,lmstudio").split(",")

        # Clasificar proveedores por tipo
        for provider_name in fallback_order_env:
            try:
                if provider_name == "grok":
                    provider_name = "xai"  # Alias

                provider = LLMProvider(provider_name)
                if provider not in self.providers or not self.providers[provider].active:
                    continue

                config = self.providers[provider]

                # Para conversaciones normales
                self.normal_fallback.append(provider)

                # Para razonamiento (solo modelos buenos en razonamiento)
                if config.is_reasoning:
                    self.reasoning_fallback.append(provider)

                # Para modo gratuito únicamente
                if config.is_free:
                    self.free_only_fallback.append(provider)

            except ValueError:
                logger.warning("Proveedor desconocido en fallback order: %s", provider_name)
                continue

        # Si no hay modelos de razonamiento, usar los normales
        if not self.reasoning_fallback:
            self.reasoning_fallback = self.normal_fallback.copy()

        # Asegurar que siempre haya fallback gratuito
        if not self.free_only_fallback:
            self.free_only_fallback = [p for p in self.normal_fallback if self.providers[p].is_free]

        logger.info("Fallback normal: %s", [p.value for p in self.normal_fallback])
        logger.info("Fallback razonamiento: %s", [p.value for p in self.reasoning_fallback])
        logger.info("Fallback gratuito: %s", [p.value for p in self.free_only_fallback])

    def _log_provider_capabilities(self):
        """Log de capacidades de cada proveedor"""
        for _provider, config in self.providers.items():
            capabilities = []
            if config.is_reasoning:
                capabilities.append("🧠 Razonamiento")
            if config.is_free:
                capabilities.append("🆓 Gratuito")
            if not config.api_key:
                capabilities.append("📍 Local")

            logger.info("✅ %s: %s", config.name, ", ".join(capabilities) if capabilities else "Estándar")

    def get_fallback_order(self, use_case: str = "normal", free_only: bool = False) -> list[LLMProvider]:
        """Retorna el orden de fallback según el caso de uso"""

        if free_only or os.getenv("ENABLE_FREE_MODELS_FALLBACK", "false").lower() == "true":
            return self.free_only_fallback
        elif use_case == "reasoning":
            return self.reasoning_fallback
        else:
            return self.normal_fallback

    def _inject_contexts_into_messages(self, messages: list[dict[str, str]], chat_id: str) -> list[dict[str, str]]:
        """
        Carga e inyecta contextos relevantes en los mensajes
        Incluye: DailyContext, UserContext, objetivos, perfil, estrategia
        """
        if not CONTEXT_LOADER_AVAILABLE:
            return messages

        try:
            # Cargar todos los contextos
            contexts = context_loader.load_all_contexts(chat_id)

            # Construir sección de contexto
            context_section = context_loader.build_context_prompt_section(contexts)

            if not context_section:
                return messages

            # Inyectar como mensaje de sistema adicional
            enhanced_messages = list(messages)

            # Buscar el primer mensaje de sistema y agregar contexto después
            system_index = -1
            for i, msg in enumerate(enhanced_messages):
                if msg.get("role") == "system":
                    system_index = i
                    break

            context_message = {"role": "system", "content": f"CONTEXTOS ACTIVOS:\n\n{context_section}"}

            if system_index >= 0:
                # Insertar después del primer mensaje de sistema
                enhanced_messages.insert(system_index + 1, context_message)
            else:
                # Si no hay mensaje de sistema, insertar al inicio
                enhanced_messages.insert(0, context_message)

            logger.info("📦 Contextos inyectados para chat %s", chat_id)
            return enhanced_messages

        except Exception as e:
            logger.warning("⚠️ Error inyectando contextos: %s", e)
            return messages

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        business_context: Optional[dict] = None,
        use_case: str = "normal",
        free_only: bool = False,
        max_retries: int = 3,
        inject_contexts: bool = True,
    ) -> dict[str, Any]:
        """
        Genera respuesta usando el proveedor disponible con fallback automático
        Incluye sistema de humanización, detección de respuestas bot, e inyección de contextos
        """

        # Obtener mensaje del usuario para análisis contextual
        request_start = asyncio.get_event_loop().time()
        if METRICS_AVAILABLE:
            inc_counter("llm_requests")

        def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
            if METRICS_AVAILABLE:
                elapsed = max(0.0, asyncio.get_event_loop().time() - request_start)
                observe_histogram("llm_response_time", elapsed)
            return payload

        user_message = messages[-1]["content"] if messages else ""
        chat_id = business_context.get("chat_id") if business_context else "unknown"

        # INYECTAR CONTEXTOS (DailyContext, UserContext, objetivos, etc)
        if inject_contexts and chat_id != "unknown":
            messages = self._inject_contexts_into_messages(messages, chat_id)

        # Determinar si el admin habilitó solo modelos gratuitos
        admin_free_only = os.getenv("ENABLE_FREE_MODELS_FALLBACK", "false").lower() == "true"
        if admin_free_only:
            free_only = True

        prompt_hash = self._compute_prompt_hash(messages, business_context, use_case=use_case, free_only=free_only)

        # Para negocios sensibles, priorizar modelos sin censura
        business_type = business_context.get("business_type") if business_context else None
        if HUMANIZATION_AVAILABLE and business_type and sensitive_handler.is_sensitive_business(business_type):
            logger.info("🔞 Negocio sensible detectado: %s - Priorizando modelos sin censura", business_type)
            preferred_models = sensitive_handler.get_preferred_models(business_type)
            # Reordenar fallback para priorizar modelos sin censura
            fallback_providers = self._reorder_for_sensitive(self.get_fallback_order(use_case, free_only), preferred_models)
        else:
            fallback_providers = self.get_fallback_order(use_case, free_only)

        logger.info("Usando caso: %s, solo gratuitos: %s", use_case, free_only)

        # Intentar con cada proveedor
        for provider in fallback_providers:
            try:
                logger.info("Intentando con proveedor: %s", provider.value)
                effective_retries = max(1, int(max_retries))

                if self.cache_enabled and CACHE_AVAILABLE:
                    cached = await get_cached_llm_response(prompt_hash, provider.value)
                    if cached and cached.get("response"):
                        return _finalize({
                            "success": True,
                            "response": cached["response"],
                            "provider": provider.value,
                            "model": self.providers[provider].model,
                            "tokens_used": 0,
                            "is_free": self.providers[provider].is_free,
                            "use_case": use_case,
                            "was_humanized": False,
                            "cached": True,
                        })

                result = await self._call_provider(
                    provider,
                    messages,
                    business_context,
                    max_retries=effective_retries,
                )

                if not (result and result.get("success")):
                    self._record_provider_failure(provider.value)

                if result and result.get("success"):
                    response_text = result["response"]

                    # VALIDACIÓN DE HUMANIZACIÓN
                    if HUMANIZATION_AVAILABLE:
                        # 1. Detectar negación ética
                        is_ethical_refusal = humanized_responses.detect_llm_ethical_refusal(response_text)

                        if is_ethical_refusal:
                            logger.error("❌ NEGACIÓN ÉTICA detectada en %s", provider.value)
                            logger.error("   Respuesta: %s", response_text[:200])

                            # Si no es un modelo sin censura, intentar con siguiente
                            if provider.value not in ["ollama", "lmstudio", "grok"]:
                                logger.info("   Intentando con siguiente proveedor...")
                                continue

                        # 2. Validar que no suene a bot
                        validation = humanized_responses.validate_llm_response(response_text)

                        if not validation["is_valid"]:
                            logger.warning("⚠️ Respuesta suena a BOT: %s", validation["issues"])
                            # Humanizar respuesta
                            response_text = humanized_responses.humanize_response(response_text)
                            logger.info("✅ Respuesta humanizada aplicada")

                    if self.cache_enabled and CACHE_AVAILABLE and response_text:
                        await cache_llm_response(
                            prompt_hash=prompt_hash,
                            response=response_text,
                            provider=provider.value,
                            ttl=self.cache_ttl_seconds,
                        )

                    logger.info("✅ Respuesta exitosa de %s", provider.value)
                    return _finalize({
                        "success": True,
                        "response": response_text,
                        "provider": provider.value,
                        "model": self.providers[provider].model,
                        "tokens_used": result.get("tokens_used", 0),
                        "is_free": self.providers[provider].is_free,
                        "use_case": use_case,
                        "was_humanized": validation.get("is_valid", True) if HUMANIZATION_AVAILABLE else False,
                    })

            except Exception as e:
                logger.warning("❌ Error con %s: %s", provider.value, str(e))
                self._record_provider_failure(provider.value)
                continue

        # TODOS LOS PROVEEDORES FALLARON - Manejo inteligente con humanización
        logger.error("❌ TODOS los proveedores LLM fallaron")

        if HUMANIZATION_AVAILABLE:
            # Análisis contextual de la falla
            error_response = humanized_responses.get_error_response(
                user_message=user_message, error_type="llm_failure", conversation_history=messages, context=business_context
            )

            # ¿Requiere transferencia silenciosa?
            if error_response["transfer_to_human"]:
                logger.error("🔇 TRANSFERENCIA SILENCIOSA activada para: %s", user_message[:50])

                # Crear transferencia
                transfer_id = silent_transfer_manager.create_transfer(
                    chat_id=chat_id,
                    reason=TransferReason.SIMPLE_QUESTION_FAIL,
                    trigger_message=user_message,
                    conversation_history=messages[-10:] if len(messages) > 10 else messages,
                    metadata={
                        "all_llms_failed": True,
                        "attempted_providers": [p.value for p in fallback_providers],
                    },
                    notify_client=False,  # SILENCIOSO
                )

                return _finalize({
                    "success": False,
                    "response": None,  # NO responder
                    "action": "silent_transfer",
                    "transfer_id": transfer_id,
                    "error": "LLM failure - silent transfer initiated",
                })

            # Dar respuesta humanizada y marcar para reintento
            logger.info("💬 Respuesta humanizada: %s", error_response["response"])
            return _finalize({
                "success": True,  # Técnicamente "exitoso" porque damos respuesta
                "response": error_response["response"],
                "action": "humanized_fallback",
                "should_retry": error_response.get("should_retry", False),
                "delay_before_response": error_response.get("delay_before_response", 0),
                "provider": "humanized_fallback",
            })

        # Sin sistema de humanización, fallback tradicional
        return _finalize({
            "success": False,
            "error": f"Todos los proveedores para {use_case} no están disponibles",
            "response": self._get_fallback_response(business_context),
            "provider": "fallback",
            "use_case": use_case,
        })

    def _reorder_for_sensitive(self, providers: list[LLMProvider], preferred: list[str]) -> list[LLMProvider]:
        """
        Reordena proveedores para priorizar modelos sin censura
        SOLO usa modelos que estén REALMENTE disponibles
        """
        if not preferred:
            return providers

        # Filtrar solo los proveedores que realmente están disponibles
        available_providers = [p for p in providers if p in self.providers]

        prioritized = []
        remaining = []

        for provider in available_providers:
            if provider.value in preferred:
                # Verificar que el modelo esté realmente disponible y activo
                if self.providers[provider].active:
                    prioritized.append(provider)
                else:
                    logger.debug("⚠️ %s está en preferred pero no está activo", provider.value)
            else:
                remaining.append(provider)

        # Si no hay modelos preferidos disponibles, usar online
        if not prioritized:
            logger.info("⚠️ Modelos sin censura no disponibles, usando modelos online")
            # Priorizar Grok/xAI si está disponible (menos censurado que OpenAI/Gemini)
            if LLMProvider.XAI in remaining:
                grok_index = remaining.index(LLMProvider.XAI)
                remaining.insert(0, remaining.pop(grok_index))

        return prioritized + remaining

    def _record_provider_failure(self, provider_name: str) -> None:
        """Registra fallos por proveedor para observabilidad del fallback."""
        if not METRICS_AVAILABLE:
            return
        try:
            inc_counter(f"llm_provider_failure_{provider_name}")
        except Exception:
            logger.debug("No se pudo registrar métrica de fallo para proveedor %s", provider_name)

    async def _call_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, str]],
        business_context: Optional[dict] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Llama a un proveedor específico"""

        config = self.providers[provider]

        async def _dispatch() -> dict[str, Any]:
            if provider == LLMProvider.GEMINI:
                return await self._call_gemini(config, messages, business_context, max_retries=max_retries)
            elif provider == LLMProvider.OPENAI:
                return await self._call_openai(config, messages, max_retries=max_retries)
            elif provider == LLMProvider.CLAUDE:
                return await self._call_claude(config, messages, max_retries=max_retries)
            elif provider == LLMProvider.OLLAMA:
                return await self._call_ollama(config, messages, max_retries=max_retries)
            elif provider == LLMProvider.LM_STUDIO:
                return await self._call_lmstudio(config, messages, max_retries=max_retries)
            elif provider == LLMProvider.XAI:
                return await self._call_xai(config, messages, max_retries=max_retries)
            return {"success": False, "error": "Proveedor no soportado"}

        if not CIRCUIT_BREAKER_AVAILABLE:
            return await _dispatch()

        breaker_name = f"llm_{provider.value}"
        breaker = get_or_create_circuit_breaker(
            name=breaker_name,
            failure_threshold=int(os.getenv("LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
            recovery_timeout=int(os.getenv("LLM_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")),
        )

        try:
            return await breaker.call(_dispatch)
        except CircuitBreakerOpenException:
            return {"success": False, "error": f"Circuit breaker abierto para {provider.value}"}

    async def _call_gemini(
        self,
        config: APIConfig,
        messages: list[dict],
        context: Optional[dict] = None,
        max_retries: int = 3,
    ) -> dict:
        """Llama a Google Gemini API"""
        # Convertir mensajes al formato de Gemini
        contents = []
        for msg in messages:
            contents.append({"role": "user" if msg["role"] == "user" else "model", "parts": [{"text": msg["content"]}]})

        url = f"{config.base_url}/models/{config.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": config.api_key}

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": config.temperature, "maxOutputTokens": config.max_tokens},
        }

        timeout = aiohttp.ClientTimeout(total=self.provider_timeout_seconds)
        transient_statuses = {408, 429, 500, 502, 503, 504}

        for attempt in range(max_retries):
            try:
                async with self._session_scope() as session:
                    async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "candidates" in data and len(data["candidates"]) > 0:
                                text = data["candidates"][0]["content"]["parts"][0]["text"]
                                return {
                                    "success": True,
                                    "response": text,
                                    "tokens_used": data.get("usageMetadata", {}).get("totalTokenCount", 0),
                                }

                        error_text = await response.text()
                        if response.status in transient_statuses and attempt < (max_retries - 1):
                            await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                            continue
                        return {"success": False, "error": f"Gemini API Error ({response.status}): {error_text}"}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < (max_retries - 1):
                    await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                    continue
                return {"success": False, "error": str(e)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Gemini retries exhausted"}

    async def _call_openai(self, config: APIConfig, messages: list[dict], max_retries: int = 3) -> dict:
        """Llama a OpenAI API."""
        return await self._call_openai_compatible(
            provider_label="OpenAI",
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=max_retries,
            include_auth_header=True,
        )

    @staticmethod
    def _compute_prompt_hash(
        messages: list[dict[str, str]],
        business_context: Optional[dict[str, Any]],
        use_case: str,
        free_only: bool,
    ) -> str:
        serialized = json.dumps(
            {
                "messages": messages,
                "business_context": business_context or {},
                "use_case": use_case,
                "free_only": bool(free_only),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _call_ollama(self, config: APIConfig, messages: list[dict], max_retries: int = 3) -> dict:
        """Llama a Ollama local"""
        payload = {"model": config.model, "messages": messages, "stream": False}
        timeout = aiohttp.ClientTimeout(total=self.provider_timeout_seconds)
        transient_statuses = {408, 429, 500, 502, 503, 504}

        for attempt in range(max_retries):
            try:
                async with self._session_scope() as session:
                    async with session.post(f"{config.base_url}/api/chat", json=payload, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                "success": True,
                                "response": data["message"]["content"],
                                "tokens_used": 0,
                            }

                        error_text = await response.text()
                        if response.status in transient_statuses and attempt < (max_retries - 1):
                            await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                            continue
                        return {"success": False, "error": f"Ollama Error ({response.status}): {error_text}"}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < (max_retries - 1):
                    await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                    continue
                return {"success": False, "error": f"Ollama Exception: {str(e)}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ollama retries exhausted"}

    async def _call_lmstudio(self, config: APIConfig, messages: list[dict], max_retries: int = 3) -> dict:
        """Llama a LM Studio local."""
        result = await self._call_openai_compatible(
            provider_label="LM Studio",
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=max_retries,
            include_auth_header=False,
        )
        if result.get("success"):
            result["tokens_used"] = 0
        return result

    async def _call_claude(self, config: APIConfig, messages: list[dict], max_retries: int = 3) -> dict:
        """Llama a Claude API con formato correcto de Anthropic"""
        headers = {"Content-Type": "application/json", "X-Api-Key": config.api_key, "anthropic-version": "2023-06-01"}

        claude_messages = []
        system_message = ""

        for msg in messages:
            if msg["role"] == "system":
                system_message += msg["content"] + "\n"
            else:
                claude_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": config.model,
            "messages": claude_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if system_message.strip():
            payload["system"] = system_message.strip()

        timeout = aiohttp.ClientTimeout(total=self.provider_timeout_seconds)
        transient_statuses = {408, 429, 500, 502, 503, 504}

        for attempt in range(max_retries):
            try:
                async with self._session_scope() as session:
                    async with session.post(f"{config.base_url}/v1/messages", headers=headers, json=payload, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data.get("content", [])
                            if content and len(content) > 0:
                                text = content[0].get("text", "")
                                return {
                                    "success": True,
                                    "response": text,
                                    "tokens_used": data.get("usage", {}).get("input_tokens", 0)
                                    + data.get("usage", {}).get("output_tokens", 0),
                                }

                        error_text = await response.text()
                        if response.status in transient_statuses and attempt < (max_retries - 1):
                            await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                            continue
                        return {"success": False, "error": f"Claude API Error ({response.status}): {error_text}"}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < (max_retries - 1):
                    await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                    continue
                return {"success": False, "error": f"Claude Exception: {str(e)}"}
            except Exception as e:
                return {"success": False, "error": f"Claude Exception: {str(e)}"}

        return {"success": False, "error": "Claude retries exhausted"}

    async def _call_xai(self, config: APIConfig, messages: list[dict], max_retries: int = 3) -> dict:
        """Llama a xAI Grok API."""
        return await self._call_openai_compatible(
            provider_label="xAI",
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=max_retries,
            include_auth_header=True,
        )

    async def _call_openai_compatible(
        self,
        provider_label: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        max_retries: int,
        include_auth_header: bool = True,
    ) -> dict:
        """Cliente genérico para APIs compatibles con OpenAI `/chat/completions`."""
        headers = {"Content-Type": "application/json"}
        if include_auth_header and api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        timeout = aiohttp.ClientTimeout(total=self.provider_timeout_seconds)
        transient_statuses = {408, 429, 500, 502, 503, 504}

        for attempt in range(max_retries):
            try:
                async with self._session_scope() as session:
                    async with session.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                "success": True,
                                "response": data["choices"][0]["message"]["content"],
                                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                            }

                        error_text = await response.text()
                        if response.status in transient_statuses and attempt < (max_retries - 1):
                            await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                            continue
                        return {"success": False, "error": f"{provider_label} Error ({response.status}): {error_text}"}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < (max_retries - 1):
                    await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))
                    continue
                return {"success": False, "error": f"{provider_label} Exception: {str(e)}"}
            except Exception as e:
                return {"success": False, "error": f"{provider_label} Exception: {str(e)}"}

        return {"success": False, "error": f"{provider_label} retries exhausted"}

    def _get_fallback_response(self, context: Optional[dict] = None) -> str:
        """Respuesta de emergencia cuando todos los proveedores fallan"""
        business_name = context.get("business_name", "nuestro negocio") if context else "nuestro negocio"

        return (
            f"Disculpa, estoy experimentando dificultades técnicas temporales. "
            f"Por favor, contacta directamente con {business_name} o intenta nuevamente en unos minutos. "
            f"Apreciamos tu paciencia. 🙏"
        )

    def get_available_providers(self) -> list[dict[str, Any]]:
        """Retorna lista de proveedores disponibles con su estado"""
        return [
            {
                "name": config.name,
                "provider": provider.value,
                "model": config.model,
                "active": config.active,
                "local": provider in [LLMProvider.OLLAMA, LLMProvider.LM_STUDIO],
                "is_free": config.is_free,
                "is_reasoning": config.is_reasoning,
                "capabilities": self._get_provider_capabilities(config),
            }
            for provider, config in self.providers.items()
        ]

    def _get_provider_capabilities(self, config: APIConfig) -> list[str]:
        """Retorna lista de capacidades del proveedor"""
        capabilities = []
        if config.is_reasoning:
            capabilities.append("Razonamiento")
        if config.is_free:
            capabilities.append("Gratuito")
        if not config.api_key:
            capabilities.append("Local")
        return capabilities

    def get_providers_by_type(self, reasoning: bool = False, free_only: bool = False) -> list[dict[str, Any]]:
        """Retorna proveedores filtrados por tipo"""
        all_providers = self.get_available_providers()

        filtered = []
        for provider in all_providers:
            if reasoning and not provider["is_reasoning"]:
                continue
            if free_only and not provider["is_free"]:
                continue
            filtered.append(provider)

        return filtered


# Instancia global
llm_manager = MultiProviderLLM()
