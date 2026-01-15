"""
📊 Sistema de Métricas en Tiempo Real
WebSocket para dashboard en vivo con actualización cada 5 segundos
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Set
from datetime import datetime, timedelta
from fastapi import WebSocket
from collections import defaultdict

logger = logging.getLogger(__name__)


class RealtimeMetricsManager:
    """Gestor de métricas en tiempo real con WebSocket"""
    
    def __init__(self, analytics_manager=None):
        self.analytics = analytics_manager
        self.active_connections: Set[WebSocket] = set()
        self.is_running = False
        self.update_interval = 5  # Actualizar cada 5 segundos
        
        # Métricas en memoria (últimas 24 horas)
        self.metrics_cache = {
            "conversations": defaultdict(int),  # Por hora
            "messages": defaultdict(int),
            "response_times": [],
            "llm_usage": defaultdict(int),
            "errors": defaultdict(int),
            "humanization_events": defaultdict(int),
        }
        
        logger.info("📊 RealtimeMetricsManager inicializado")
    
    async def connect(self, websocket: WebSocket):
        """Conectar un nuevo WebSocket"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"✅ Cliente WebSocket conectado (total: {len(self.active_connections)})")
        
        # Enviar snapshot inicial
        await self.send_initial_snapshot(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Desconectar WebSocket"""
        self.active_connections.discard(websocket)
        logger.info(f"❌ Cliente WebSocket desconectado (total: {len(self.active_connections)})")
    
    async def send_initial_snapshot(self, websocket: WebSocket):
        """Enviar snapshot inicial de métricas al conectar"""
        try:
            snapshot = self.get_current_metrics()
            await websocket.send_json({
                "type": "snapshot",
                "data": snapshot,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"❌ Error enviando snapshot: {e}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Enviar mensaje a todos los clientes conectados"""
        if not self.active_connections:
            return
        
        disconnected = set()
        
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"❌ Error enviando a WebSocket: {e}")
                disconnected.add(websocket)
        
        # Limpiar conexiones muertas
        for ws in disconnected:
            self.active_connections.discard(ws)
    
    def start_broadcast_loop(self):
        """Iniciar loop de actualización de métricas"""
        if self.is_running:
            logger.warning("⚠️ Loop de métricas ya está corriendo")
            return
        
        self.is_running = True
        asyncio.create_task(self._broadcast_loop())
        logger.info("🚀 Loop de broadcast iniciado")
    
    async def _broadcast_loop(self):
        """Loop principal de actualización de métricas"""
        while self.is_running:
            try:
                if self.active_connections:
                    metrics = self.get_current_metrics()
                    
                    await self.broadcast({
                        "type": "update",
                        "data": metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Error en loop de broadcast: {e}")
                await asyncio.sleep(self.update_interval)
    
    def stop_broadcast_loop(self):
        """Detener loop de actualización"""
        self.is_running = False
        logger.info("⏸️ Loop de broadcast detenido")
    
    def record_conversation_start(self, session_id: str, contact: str):
        """Registrar inicio de conversación"""
        hour_key = datetime.now().replace(minute=0, second=0, microsecond=0)
        self.metrics_cache["conversations"][hour_key] += 1
        
        # También registrar en analytics si está disponible
        if self.analytics:
            try:
                self.analytics.record_conversation_start(session_id, contact)
            except Exception as e:
                logger.error(f"❌ Error registrando en analytics: {e}")
    
    def record_message(self, session_id: str, role: str, message: str):
        """Registrar mensaje"""
        hour_key = datetime.now().replace(minute=0, second=0, microsecond=0)
        self.metrics_cache["messages"][hour_key] += 1
        
        if self.analytics:
            try:
                self.analytics.record_message(session_id, role, message)
            except Exception as e:
                logger.error(f"❌ Error registrando mensaje: {e}")
    
    def record_llm_usage(self, provider: str, tokens: int, response_time: float):
        """Registrar uso de LLM"""
        self.metrics_cache["llm_usage"][provider] += 1
        self.metrics_cache["response_times"].append({
            "provider": provider,
            "time": response_time,
            "timestamp": datetime.now()
        })
        
        # Limpiar response_times viejos (más de 1 hora)
        cutoff = datetime.now() - timedelta(hours=1)
        self.metrics_cache["response_times"] = [
            rt for rt in self.metrics_cache["response_times"]
            if rt["timestamp"] > cutoff
        ]
        
        if self.analytics:
            try:
                self.analytics.record_llm_call(provider, tokens, True, response_time)
            except Exception as e:
                logger.error(f"❌ Error registrando LLM: {e}")
    
    def record_error(self, error_type: str, details: str):
        """Registrar error"""
        hour_key = datetime.now().replace(minute=0, second=0, microsecond=0)
        self.metrics_cache["errors"][hour_key] += 1
    
    def record_humanization_event(self, event_type: str):
        """Registrar evento de humanización"""
        hour_key = datetime.now().replace(minute=0, second=0, microsecond=0)
        key = f"{hour_key}_{event_type}"
        self.metrics_cache["humanization_events"][key] += 1
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Obtener métricas actuales para dashboard"""
        now = datetime.now()
        
        # Última hora
        last_hour = now - timedelta(hours=1)
        
        # Conversaciones activas (últimos 5 minutos)
        active_cutoff = now - timedelta(minutes=5)
        
        # Calcular métricas
        conversations_last_hour = sum(
            count for time, count in self.metrics_cache["conversations"].items()
            if time >= last_hour
        )
        
        messages_last_hour = sum(
            count for time, count in self.metrics_cache["messages"].items()
            if time >= last_hour
        )
        
        errors_last_hour = sum(
            count for time, count in self.metrics_cache["errors"].items()
            if time >= last_hour
        )
        
        # LLM usage
        llm_usage = dict(self.metrics_cache["llm_usage"])
        
        # Response times promedio
        recent_response_times = [
            rt for rt in self.metrics_cache["response_times"]
            if rt["timestamp"] >= last_hour
        ]
        
        avg_response_time = 0
        if recent_response_times:
            avg_response_time = sum(rt["time"] for rt in recent_response_times) / len(recent_response_times)
        
        # Eventos de humanización
        humanization_events = {}
        for key, count in self.metrics_cache["humanization_events"].items():
            time_str, event_type = key.rsplit("_", 1)
            time = datetime.fromisoformat(time_str)
            if time >= last_hour:
                humanization_events[event_type] = humanization_events.get(event_type, 0) + count
        
        # Gráfico de conversaciones por hora (últimas 24 horas)
        hourly_conversations = []
        for i in range(24):
            hour = now - timedelta(hours=i)
            hour_key = hour.replace(minute=0, second=0, microsecond=0)
            count = self.metrics_cache["conversations"].get(hour_key, 0)
            hourly_conversations.insert(0, {
                "hour": hour.strftime("%H:00"),
                "count": count
            })
        
        # Gráfico de mensajes por hora
        hourly_messages = []
        for i in range(24):
            hour = now - timedelta(hours=i)
            hour_key = hour.replace(minute=0, second=0, microsecond=0)
            count = self.metrics_cache["messages"].get(hour_key, 0)
            hourly_messages.insert(0, {
                "hour": hour.strftime("%H:00"),
                "count": count
            })
        
        return {
            "overview": {
                "conversations_last_hour": conversations_last_hour,
                "messages_last_hour": messages_last_hour,
                "errors_last_hour": errors_last_hour,
                "avg_response_time": round(avg_response_time, 2),
                "active_connections": len(self.active_connections),
            },
            "llm_usage": llm_usage,
            "humanization_events": humanization_events,
            "charts": {
                "hourly_conversations": hourly_conversations,
                "hourly_messages": hourly_messages,
            },
            "response_times_distribution": self._get_response_time_distribution(recent_response_times),
        }
    
    def _get_response_time_distribution(self, response_times: List[Dict]) -> Dict[str, int]:
        """Distribución de tiempos de respuesta"""
        if not response_times:
            return {}
        
        distribution = {
            "0-1s": 0,
            "1-3s": 0,
            "3-5s": 0,
            "5-10s": 0,
            "10s+": 0,
        }
        
        for rt in response_times:
            time = rt["time"]
            if time < 1:
                distribution["0-1s"] += 1
            elif time < 3:
                distribution["1-3s"] += 1
            elif time < 5:
                distribution["3-5s"] += 1
            elif time < 10:
                distribution["5-10s"] += 1
            else:
                distribution["10s+"] += 1
        
        return distribution
    
    def cleanup_old_metrics(self):
        """Limpiar métricas antiguas (más de 24 horas)"""
        cutoff = datetime.now() - timedelta(hours=24)
        
        # Limpiar conversaciones
        old_keys = [k for k in self.metrics_cache["conversations"] if k < cutoff]
        for k in old_keys:
            del self.metrics_cache["conversations"][k]
        
        # Limpiar mensajes
        old_keys = [k for k in self.metrics_cache["messages"] if k < cutoff]
        for k in old_keys:
            del self.metrics_cache["messages"][k]
        
        # Limpiar errores
        old_keys = [k for k in self.metrics_cache["errors"] if k < cutoff]
        for k in old_keys:
            del self.metrics_cache["errors"][k]
        
        # Limpiar eventos de humanización
        old_keys = []
        for key in self.metrics_cache["humanization_events"]:
            time_str = key.rsplit("_", 1)[0]
            time = datetime.fromisoformat(time_str)
            if time < cutoff:
                old_keys.append(key)
        for k in old_keys:
            del self.metrics_cache["humanization_events"][k]
        
        logger.info("🧹 Métricas antiguas limpiadas")


# Instancia global
realtime_metrics = RealtimeMetricsManager()
