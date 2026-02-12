"""
💬 Sistema de Chat en Tiempo Real para Testing
Integración con Multi-API y WebSockets
"""

import contextlib
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ChatConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.chat_sessions: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Conectar nueva sesión de chat"""
        await websocket.accept()
        self.active_connections.append(websocket)

        if session_id not in self.chat_sessions:
            self.chat_sessions[session_id] = {
                "messages": [],
                "started_at": datetime.now(),
                "user_id": session_id,
                "status": "active",
            }

        await self.send_personal_message(
            {
                "type": "system",
                "message": "Conectado al chat de prueba. ¡Escribe tu mensaje!",
                "timestamp": datetime.now().isoformat(),
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Desconectar sesión de chat"""
        self.active_connections.remove(websocket)
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]["status"] = "disconnected"

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Enviar mensaje a una conexión específica"""
        await websocket.send_text(json.dumps(message, ensure_ascii=False))

    async def broadcast(self, message: dict):
        """Broadcast a todas las conexiones"""
        for connection in self.active_connections:
            with contextlib.suppress(Exception):
                await connection.send_text(json.dumps(message, ensure_ascii=False))

    async def process_message(self, session_id: str, user_message: str, websocket: WebSocket):
        """Procesar mensaje del usuario y generar respuesta"""
        try:
            # Agregar mensaje del usuario al historial
            self.chat_sessions[session_id]["messages"].append(
                {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()}
            )

            # Enviar confirmación de recepción
            await self.send_personal_message(
                {"type": "user_message", "message": user_message, "timestamp": datetime.now().isoformat()}, websocket
            )

            # Simular "typing" indicator
            await self.send_personal_message(
                {"type": "typing", "message": "Bot está escribiendo...", "timestamp": datetime.now().isoformat()}, websocket
            )

            # Generar respuesta del bot (aquí integrarías con multi_provider_llm)
            bot_response = await self.generate_bot_response(session_id, user_message)

            # Agregar respuesta del bot al historial
            self.chat_sessions[session_id]["messages"].append(
                {"role": "assistant", "content": bot_response, "timestamp": datetime.now().isoformat()}
            )

            # Enviar respuesta del bot
            await self.send_personal_message(
                {
                    "type": "bot_message",
                    "message": bot_response,
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                },
                websocket,
            )

        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await self.send_personal_message(
                {
                    "type": "error",
                    "message": "Error procesando tu mensaje. Intenta de nuevo.",
                    "timestamp": datetime.now().isoformat(),
                },
                websocket,
            )

    async def generate_bot_response(self, session_id: str, user_message: str) -> str:
        """Generar respuesta del bot usando la configuración actual"""
        try:
            # Aquí integrarías con business_config_manager y multi_provider_llm
            # Por ahora, respuesta simulada inteligente

            user_message_lower = user_message.lower()

            # Respuestas contextuales simples
            if any(word in user_message_lower for word in ["hola", "buenos días", "buenas tardes"]):
                return "¡Hola! 👋 Bienvenido/a a nuestro chat de prueba. Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?"

            elif any(word in user_message_lower for word in ["precio", "costo", "cuánto", "valor"]):
                return "Me interesa ayudarte con información sobre precios. ¿Podrías ser más específico sobre qué producto o servicio te interesa? 💰"

            elif any(word in user_message_lower for word in ["horario", "hora", "cuándo", "abierto"]):
                return "Nuestros horarios de atención son de Lunes a Viernes de 9:00 AM a 6:00 PM. ¿Te gustaría agendar una cita? 📅"

            elif any(word in user_message_lower for word in ["contacto", "teléfono", "email", "dirección"]):
                return "Puedes contactarnos por:\n📧 Email: contacto@minegocio.com\n📞 Teléfono: +1-234-567-8900\n📍 Ubicación: Ciudad, País"

            elif any(word in user_message_lower for word in ["ayuda", "help", "qué puedes hacer"]):
                return """¡Perfecto! Puedo ayudarte con:

✅ Información sobre nuestros servicios
💰 Consultas de precios y cotizaciones
📅 Agendar citas y reuniones
📞 Información de contacto
🕒 Horarios de atención
❓ Responder preguntas frecuentes

¿Con qué te gustaría que empiece?"""

            else:
                return f"Gracias por tu mensaje: '{user_message}'. Estoy procesando tu consulta con nuestra configuración de negocio personalizada. ¿Hay algo específico en lo que pueda ayudarte? 🤖"

        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return "Disculpa, hubo un error procesando tu mensaje. ¿Podrías intentar reformular tu pregunta?"

    def get_session_stats(self) -> dict[str, Any]:
        """Obtener estadísticas de las sesiones"""
        active_sessions = sum(1 for s in self.chat_sessions.values() if s["status"] == "active")
        total_messages = sum(len(s["messages"]) for s in self.chat_sessions.values())

        return {
            "active_connections": len(self.active_connections),
            "total_sessions": len(self.chat_sessions),
            "active_sessions": active_sessions,
            "total_messages": total_messages,
            "sessions": self.chat_sessions,
        }


# Instancia global del manager
chat_manager = ChatConnectionManager()
