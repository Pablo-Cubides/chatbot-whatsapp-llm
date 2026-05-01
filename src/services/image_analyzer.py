"""
🖼️ Sistema de Análisis de Imágenes
Analiza imágenes usando Gemini Vision (gratis) con fallback a GPT-5.4-mini
"""

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Analizador de imágenes con múltiples proveedores"""

    def __init__(self):
        self.enabled = os.getenv("IMAGE_ANALYSIS_ENABLED", "true").lower() == "true"

        # Configuración de proveedores
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

        # Caché de análisis
        self.cache = {}
        self.cache_ttl = int(os.getenv("IMAGE_CACHE_TTL", "3600"))  # 1 hora

        # Límites
        self.max_image_size_mb = int(os.getenv("MAX_IMAGE_SIZE_MB", "10"))

        if self.enabled:
            logger.info("🖼️ ImageAnalyzer inicializado")
            if self.gemini_key:
                logger.info("  ✅ Gemini Vision disponible (GRATIS)")
            if self.openai_key:
                logger.info("  ✅ GPT-5.4-mini Vision disponible (fallback)")

    async def analyze_image(
        self,
        image_bytes: bytes,
        context: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
        image_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Analiza una imagen y retorna descripción contextual

        Args:
            image_bytes: Bytes de la imagen
            context: Contexto de la conversación
            conversation_history: Historial reciente
            image_id: ID para caché

        Returns:
            Dict con:
            - success: bool
            - description: str (descripción natural)
            - provider: str (gemini/openai)
            - cached: bool
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "Análisis de imágenes deshabilitado",
            }

        try:
            # Verificar tamaño
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > self.max_image_size_mb:
                logger.warning(f"⚠️ Imagen demasiado grande: {size_mb:.2f}MB")
                return {
                    "success": False,
                    "error": f"Imagen muy grande (máx {self.max_image_size_mb}MB)",
                }

            # Verificar caché
            cache_key = self._get_cache_key(image_bytes)
            cached = self._get_from_cache(cache_key)

            if cached:
                logger.info(f"✅ Análisis desde caché: {cache_key[:8]}...")
                return {
                    "success": True,
                    "description": cached["description"],
                    "provider": cached["provider"],
                    "cached": True,
                }

            # Construir prompt contextual
            prompt = self._build_analysis_prompt(context, conversation_history)

            # Intentar con Gemini primero (gratis)
            if self.gemini_key:
                result = await self._analyze_with_gemini(image_bytes, prompt)
                if result["success"]:
                    self._save_to_cache(cache_key, result)
                    return result
                logger.warning("⚠️ Gemini Vision falló, intentando con GPT-5.4-mini")

            # Fallback a GPT-5.4-mini
            if self.openai_key:
                result = await self._analyze_with_openai(image_bytes, prompt)
                if result["success"]:
                    self._save_to_cache(cache_key, result)
                    return result

            return {
                "success": False,
                "error": "Todos los proveedores de visión fallaron",
            }

        except Exception as e:
            logger.error(f"❌ Error analizando imagen: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _build_analysis_prompt(self, context: Optional[str], conversation_history: Optional[list[dict]]) -> str:
        """
        Construye prompt HUMANIZADO para análisis de imagen
        NO debe parecer descripción de IA
        """
        base_prompt = """NO eres un bot describiendo una imagen. Eres una persona REAL que recibió esta imagen por WhatsApp.

Describe brevemente qué ves, como lo haría una persona normal en conversación casual.

REGLAS:
- NO uses frases como "La imagen muestra..." o "Puedo observar..." o "Se puede ver..."
- Sé natural y coloquial, como si le estuvieras contando a un amigo
- Máximo 2-3 líneas, conciso
- Si es relevante para la conversación, enfócate en eso
- Usa lenguaje casual de WhatsApp"""

        if context:
            base_prompt += f"\n\nContexto de la conversación:\n{context}"

        if conversation_history and len(conversation_history) > 0:
            recent = conversation_history[-3:]  # Últimos 3 mensajes
            history_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')[:100]}" for msg in recent])
            base_prompt += f"\n\nÚltimos mensajes:\n{history_text}"

        return base_prompt

    async def _analyze_with_gemini(self, image_bytes: bytes, prompt: str) -> dict[str, Any]:
        """Analiza imagen con Gemini Vision"""
        try:
            # Codificar imagen en base64
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            model = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.gemini_key,
            }

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",  # Asumir JPEG por defecto
                                    "data": image_b64,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 200,  # Descripción concisa
                },
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "candidates" in data and len(data["candidates"]) > 0:
                            text = data["candidates"][0]["content"]["parts"][0]["text"]

                            logger.info(f"✅ Gemini Vision: {text[:100]}...")

                            return {
                                "success": True,
                                "description": text.strip(),
                                "provider": "gemini",
                                "cached": False,
                            }

                    error_text = await response.text()
                    logger.error(f"❌ Gemini Vision error: {error_text}")
                    return {"success": False, "error": error_text}

        except Exception as e:
            logger.error(f"❌ Error con Gemini Vision: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_with_openai(self, image_bytes: bytes, prompt: str) -> dict[str, Any]:
        """Analiza imagen con GPT-5.4-mini Vision"""
        try:
            # Codificar imagen en base64
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            url = "https://api.openai.com/v1/chat/completions"

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.openai_key}"}

            payload = {
                "model": os.getenv("OPENAI_VISION_MODEL", "gpt-5.4-mini"),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.7,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data["choices"][0]["message"]["content"]

                        logger.info(f"✅ GPT-5.4-mini Vision: {text[:100]}...")

                        return {
                            "success": True,
                            "description": text.strip(),
                            "provider": "openai",
                            "cached": False,
                        }

                    error_text = await response.text()
                    logger.error(f"❌ GPT-5.4-mini Vision error: {error_text}")
                    return {"success": False, "error": error_text}

        except Exception as e:
            logger.error(f"❌ Error con GPT-5.4-mini Vision: {e}")
            return {"success": False, "error": str(e)}

    def _get_cache_key(self, image_bytes: bytes) -> str:
        """Genera clave de caché para la imagen"""
        return hashlib.md5(image_bytes, usedforsecurity=False).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Obtiene análisis desde caché si está disponible"""
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            # Verificar si no expiró
            if datetime.now() < cached["expires_at"]:
                return cached["data"]
            else:
                # Expiró, eliminar
                del self.cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, result: dict[str, Any]):
        """Guarda análisis en caché"""
        self.cache[cache_key] = {
            "data": result,
            "expires_at": datetime.now() + timedelta(seconds=self.cache_ttl),
            "cached_at": datetime.now(),
        }

        # Limpiar caché viejo periódicamente
        if len(self.cache) > 100:
            self._cleanup_cache()

    def _cleanup_cache(self):
        """Limpia entradas expiradas del caché"""
        now = datetime.now()
        expired = [key for key, value in self.cache.items() if now >= value["expires_at"]]
        for key in expired:
            del self.cache[key]

        if expired:
            logger.info(f"🧹 Caché limpiado: {len(expired)} entradas eliminadas")

    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del analizador"""
        return {
            "enabled": self.enabled,
            "cache_size": len(self.cache),
            "max_image_size_mb": self.max_image_size_mb,
            "providers_available": {
                "gemini": bool(self.gemini_key),
                "openai": bool(self.openai_key),
            },
        }


# Instancia global
image_analyzer = ImageAnalyzer()
