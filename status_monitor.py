"""
Status Monitor - Sistema de monitoreo en tiempo real para APIs
Proporciona indicadores de estado, latencia y disponibilidad en tiempo real
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import threading

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    CHECKING = "checking"
    UNKNOWN = "unknown"

@dataclass
class ServiceHealth:
    """Estado de salud de un servicio"""
    service_name: str
    status: ServiceStatus
    latency_ms: float
    last_check: datetime
    error_message: Optional[str] = None
    response_time_trend: Optional[List[float]] = None
    uptime_percentage: float = 100.0
    api_key_configured: bool = False
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None
    
    def __post_init__(self):
        if self.response_time_trend is None:
            self.response_time_trend = []

class StatusMonitor:
    """Monitor de estado en tiempo real para todos los servicios LLM"""
    
    def __init__(self):
        self.services = {}
        self.integrations = {}
        self.monitoring_active = False
        self.monitor_thread = None
        self.check_interval = 30  # segundos
        self.max_trend_points = 20
        self.subscribers = []  # Callbacks para notificaciones
        
        # Configurar servicios a monitorear
        self._setup_services()
    
    def _setup_services(self):
        """Configurar servicios para monitorear"""
        services_config = [
            {
                'name': 'openai',
                'display_name': 'OpenAI GPT',
                'priority': 1,
                'expected_latency_ms': 1500,
                'timeout_ms': 10000
            },
            {
                'name': 'claude',
                'display_name': 'Anthropic Claude',
                'priority': 2,
                'expected_latency_ms': 2000,
                'timeout_ms': 15000
            },
            {
                'name': 'gemini',
                'display_name': 'Google Gemini',
                'priority': 3,
                'expected_latency_ms': 1800,
                'timeout_ms': 12000
            },
            {
                'name': 'xai',
                'display_name': 'X.AI Grok',
                'priority': 4,
                'expected_latency_ms': 3000,
                'timeout_ms': 20000
            },
            {
                'name': 'ollama',
                'display_name': 'Ollama Local',
                'priority': 5,
                'expected_latency_ms': 500,
                'timeout_ms': 5000
            }
        ]
        
        for config in services_config:
            self.services[config['name']] = ServiceHealth(
                service_name=config['name'],
                status=ServiceStatus.UNKNOWN,
                latency_ms=0.0,
                last_check=datetime.now(),
                response_time_trend=[]
            )
    
    def register_integrations(self, integrations: Dict):
        """Registrar integraciones LLM para monitoreo"""
        self.integrations = integrations
        logger.info(f"Registered {len(integrations)} integrations for monitoring")
    
    def subscribe_to_updates(self, callback: Callable[[Dict], None]):
        """Suscribirse a actualizaciones de estado"""
        self.subscribers.append(callback)
    
    def unsubscribe_from_updates(self, callback: Callable[[Dict], None]):
        """Desuscribirse de actualizaciones"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def _notify_subscribers(self, update_data: Dict):
        """Notificar a suscriptores sobre cambios de estado"""
        for callback in self.subscribers:
            try:
                callback(update_data)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    async def check_service_health(self, service_name: str) -> ServiceHealth:
        """Verificar salud de un servicio específico"""
        if service_name not in self.services:
            return ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.UNKNOWN,
                latency_ms=0.0,
                last_check=datetime.now(),
                error_message="Service not configured"
            )
        
        service = self.services[service_name]
        integration = self.integrations.get(service_name)
        
        if not integration:
            service.status = ServiceStatus.OFFLINE
            service.error_message = "Integration not available"
            service.last_check = datetime.now()
            return service
        
        try:
            # Marcar como checking
            service.status = ServiceStatus.CHECKING

            start_time = time.time()

            # Ejecutar test_connection de forma compatible con async o sync
            async def _run_test():
                try:
                    maybe = integration.test_connection()
                except TypeError:
                    # integration or method might be missing or invalid
                    return {'success': False, 'message': 'test_connection not callable'}

                if asyncio.iscoroutine(maybe):
                    return await maybe
                # sync function -> run in threadpool
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, integration.test_connection)

            # timeout configuration (use integration.timeout_sec or service timeout_ms)
            timeout_sec = getattr(integration, 'timeout_sec', None)
            if timeout_sec is None:
                timeout_ms = getattr(integration, 'timeout_ms', None) or 10000
                timeout_sec = float(timeout_ms) / 1000.0

            try:
                result = await asyncio.wait_for(_run_test(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                service.status = ServiceStatus.DEGRADED
                service.error_message = 'Health check timed out'
                service.last_check = datetime.now()
                service.latency_ms = 0.0
                logger.warning(f"Health check timeout for {service_name}")
                return service

            latency = (time.time() - start_time) * 1000  # ms

            # Actualizar métricas
            service.latency_ms = latency
            service.last_check = datetime.now()

            # Actualizar tendencia de respuesta
            service.response_time_trend.append(latency)
            if len(service.response_time_trend) > self.max_trend_points:
                service.response_time_trend.pop(0)

            # Normalizar result
            if not isinstance(result, dict):
                # suponer success si no hay excepción y se obtuvo algo
                result = {'success': True, 'message': str(result)}

            # Evaluar estado basado en la respuesta
            if result.get('success', False):
                # Detectar api_key de forma robusta
                if 'api_key_configured' in result:
                    service.api_key_configured = bool(result.get('api_key_configured'))
                else:
                    service.api_key_configured = bool(result.get('api_key') or result.get('key_present')) or ('API key' not in result.get('message', ''))

                expected_latency = getattr(integration, 'expected_latency_ms', None) or 10000
                if latency > float(expected_latency):
                    service.status = ServiceStatus.DEGRADED
                    service.error_message = 'High latency detected'
                elif not service.api_key_configured and service_name != 'ollama':
                    service.status = ServiceStatus.DEGRADED
                    service.error_message = 'API key not configured'
                else:
                    service.status = ServiceStatus.ONLINE
                    service.error_message = None
            else:
                service.status = ServiceStatus.OFFLINE
                service.error_message = result.get('message', 'Connection failed')

            # rate limit parsing
            if 'rate_limit_remaining' in result:
                val = result.get('rate_limit_remaining')
                if val is not None:
                    try:
                        service.rate_limit_remaining = int(val)
                    except Exception:
                        pass
            if 'rate_limit_reset' in result:
                rr = result.get('rate_limit_reset')
                if rr:
                    try:
                        if isinstance(rr, (int, float)):
                            service.rate_limit_reset = datetime.fromtimestamp(float(rr))
                        else:
                            # ensure rr is str
                            service.rate_limit_reset = datetime.fromisoformat(str(rr))
                    except Exception:
                        pass

            # Calcular uptime
            service.uptime_percentage = self._calculate_uptime(service_name)

            return service

        except Exception as e:
            service.status = ServiceStatus.OFFLINE
            service.error_message = f"Health check failed: {str(e)}"
            service.last_check = datetime.now()
            service.latency_ms = 0.0
            logger.error(f"Health check failed for {service_name}: {e}")
            return service
    
    def _calculate_uptime(self, service_name: str) -> float:
        """Calcular porcentaje de uptime basado en tendencia"""
        service = self.services.get(service_name)
        if not service or not service.response_time_trend:
            return 0.0
        
        # Contar respuestas exitosas (latencia > 0)
        successful_checks = sum(1 for t in service.response_time_trend if t > 0)
        total_checks = len(service.response_time_trend)
        
        return (successful_checks / total_checks) * 100 if total_checks > 0 else 0.0
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Verificar salud de todos los servicios"""
        results = {}
        
        # Verificar servicios en paralelo
        tasks = []
        for service_name in self.services.keys():
            task = asyncio.create_task(self.check_service_health(service_name))
            tasks.append((service_name, task))
        
        # Esperar resultados
        for service_name, task in tasks:
            try:
                results[service_name] = await task
            except Exception as e:
                logger.error(f"Failed to check {service_name}: {e}")
                results[service_name] = ServiceHealth(
                    service_name=service_name,
                    status=ServiceStatus.OFFLINE,
                    latency_ms=0.0,
                    last_check=datetime.now(),
                    error_message=str(e)
                )
        
        # Notificar suscriptores
        update_data = {
            'timestamp': datetime.now().isoformat(),
            'services': {name: asdict(health) for name, health in results.items()}
        }
        self._notify_subscribers(update_data)
        
        return results
    
    def start_monitoring(self):
        """Iniciar monitoreo continuo"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Status monitoring started")
    
    def stop_monitoring(self):
        """Detener monitoreo"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Status monitoring stopped")
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.monitoring_active:
                loop.run_until_complete(self.check_all_services())
                
                # Esperar hasta el siguiente check
                for _ in range(self.check_interval):
                    if not self.monitoring_active:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
        finally:
            loop.close()
    
    def get_current_status(self) -> Dict:
        """Obtener estado actual de todos los servicios"""
        now = datetime.now()
        
        services_status = {}
        for name, service in self.services.items():
            # Verificar si el último check es muy antiguo
            if now - service.last_check > timedelta(minutes=5):
                service.status = ServiceStatus.UNKNOWN
                service.error_message = "Status outdated"
            
            services_status[name] = {
                'service_name': service.service_name,
                'status': service.status.value,
                'latency_ms': service.latency_ms,
                'last_check': service.last_check.isoformat(),
                'error_message': service.error_message,
                'response_time_trend': service.response_time_trend,
                'uptime_percentage': service.uptime_percentage,
                'api_key_configured': service.api_key_configured,
                'rate_limit_remaining': service.rate_limit_remaining,
                'rate_limit_reset': service.rate_limit_reset.isoformat() if service.rate_limit_reset else None
            }
        
        return {
            'timestamp': now.isoformat(),
            'monitoring_active': self.monitoring_active,
            'services': services_status,
            'summary': self._get_summary()
        }
    
    def _get_summary(self) -> Dict:
        """Obtener resumen general del estado"""
        total_services = len(self.services)
        online_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.ONLINE)
        degraded_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.DEGRADED)
        offline_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.OFFLINE)
        
        avg_latency = 0.0
        if self.services:
            latencies = [s.latency_ms for s in self.services.values() if s.latency_ms > 0]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        # Estado general
        if online_count == total_services:
            overall_status = "healthy"
        elif online_count + degraded_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "critical"
        
        return {
            'overall_status': overall_status,
            'total_services': total_services,
            'online': online_count,
            'degraded': degraded_count,
            'offline': offline_count,
            'average_latency_ms': round(avg_latency, 2),
            'last_update': datetime.now().isoformat()
        }
    
    def get_service_recommendations(self) -> Dict[str, List[str]]:
        """Obtener recomendaciones para cada servicio"""
        recommendations = {}
        
        for name, service in self.services.items():
            service_recommendations = []
            
            if service.status == ServiceStatus.OFFLINE:
                if not service.api_key_configured and name != 'ollama':
                    service_recommendations.append("Configure API key in settings")
                elif name == 'ollama':
                    service_recommendations.append("Start Ollama server: ollama serve")
                else:
                    service_recommendations.append("Check network connectivity")
                    service_recommendations.append("Verify API credentials")
            
            elif service.status == ServiceStatus.DEGRADED:
                if service.latency_ms > 5000:
                    service_recommendations.append("High latency detected - consider switching regions")
                if not service.api_key_configured:
                    service_recommendations.append("Configure API key for full functionality")
            
            elif service.status == ServiceStatus.ONLINE:
                if service.latency_ms > 3000:
                    service_recommendations.append("Consider optimizing for better performance")
                if service.uptime_percentage < 95:
                    service_recommendations.append("Monitor service stability")
            
            if service_recommendations:
                recommendations[name] = service_recommendations
        
        return recommendations
    
    def force_status_update(self):
        """Forzar actualización inmediata de estado"""
        if self.monitoring_active:
            # Trigger immediate check in background
            threading.Thread(
                target=lambda: asyncio.run(self.check_all_services()),
                daemon=True
            ).start()
        else:
            # Run single check
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.check_all_services())
            finally:
                loop.close()
    
    def get_health_trends(self, service_name: str, hours: int = 24) -> Dict:
        """Obtener tendencias de salud para un servicio"""
        service = self.services.get(service_name)
        if not service:
            return {"error": "Service not found"}
        
        return {
            'service_name': service_name,
            'current_status': service.status.value,
            'response_time_trend': service.response_time_trend,
            'uptime_percentage': service.uptime_percentage,
            'last_check': service.last_check.isoformat(),
            'trend_analysis': {
                'avg_response_time': sum(service.response_time_trend) / len(service.response_time_trend) if service.response_time_trend else 0,
                'min_response_time': min(service.response_time_trend) if service.response_time_trend else 0,
                'max_response_time': max(service.response_time_trend) if service.response_time_trend else 0,
                'stability_score': service.uptime_percentage
            }
        }