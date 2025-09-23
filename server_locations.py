"""
Server Locations Manager - Sistema de balanceador de carga y failover
Maneja múltiples ubicaciones/regiones de servidores para APIs LLM
"""

import logging
import time
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import random
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ServerStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class ServerLocation:
    """Información de una ubicación de servidor"""
    id: str
    name: str
    region: str
    base_url: str
    priority: int = 1  # 1 = alta prioridad, 5 = baja prioridad
    latency_ms: float = 0.0
    status: ServerStatus = ServerStatus.UNKNOWN
    last_check: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0
    provider: str = ""

class ServerLocationManager:
    """Gestor de ubicaciones de servidor con balanceador de carga"""
    
    def __init__(self):
        self.locations: Dict[str, Dict[str, ServerLocation]] = {}
        self.health_check_interval = 300  # 5 minutos
        self.max_error_count = 3
        self.timeout_seconds = 10
        
        # Configurar ubicaciones predefinidas
        self._setup_default_locations()
    
    def _setup_default_locations(self):
        """Configurar ubicaciones predefinidas para cada provider"""
        
        # OpenAI tiene múltiples regiones
        openai_locations = [
            ServerLocation(
                id="openai_us_east",
                name="OpenAI US East",
                region="us-east-1",
                base_url="https://api.openai.com/v1",
                priority=1,
                provider="openai"
            ),
            ServerLocation(
                id="openai_eu_west",
                name="OpenAI EU West", 
                region="eu-west-1",
                base_url="https://api.openai.com/v1",
                priority=2,
                provider="openai"
            )
        ]
        
        # Azure OpenAI puede tener múltiples regiones
        azure_locations = [
            ServerLocation(
                id="azure_us_east",
                name="Azure OpenAI US East",
                region="eastus",
                base_url="https://{resource}.openai.azure.com",
                priority=1,
                provider="azure_openai"
            ),
            ServerLocation(
                id="azure_eu_west",
                name="Azure OpenAI EU West",
                region="westeurope", 
                base_url="https://{resource}.openai.azure.com",
                priority=2,
                provider="azure_openai"
            ),
            ServerLocation(
                id="azure_asia",
                name="Azure OpenAI Asia",
                region="japaneast",
                base_url="https://{resource}.openai.azure.com",
                priority=3,
                provider="azure_openai"
            )
        ]
        
        # Anthropic Claude
        claude_locations = [
            ServerLocation(
                id="claude_us",
                name="Anthropic Claude US",
                region="us-west-2",
                base_url="https://api.anthropic.com",
                priority=1,
                provider="claude"
            )
        ]
        
        # Google Gemini
        gemini_locations = [
            ServerLocation(
                id="gemini_global",
                name="Google Gemini Global",
                region="global",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                priority=1,
                provider="gemini"
            )
        ]
        
        # X.AI Grok
        xai_locations = [
            ServerLocation(
                id="xai_us",
                name="X.AI Grok US",
                region="us-west-1",
                base_url="https://api.x.ai/v1",
                priority=1,
                provider="xai"
            )
        ]
        
        # Ollama (local)
        ollama_locations = [
            ServerLocation(
                id="ollama_local",
                name="Ollama Local",
                region="localhost",
                base_url="http://localhost:11434",
                priority=1,
                provider="ollama"
            ),
            ServerLocation(
                id="ollama_alt",
                name="Ollama Alternative",
                region="localhost",
                base_url="http://127.0.0.1:11434",
                priority=2,
                provider="ollama"
            )
        ]
        
        # Organizar por provider
        self.locations = {
            "openai": {loc.id: loc for loc in openai_locations},
            "azure_openai": {loc.id: loc for loc in azure_locations},
            "claude": {loc.id: loc for loc in claude_locations},
            "gemini": {loc.id: loc for loc in gemini_locations},
            "xai": {loc.id: loc for loc in xai_locations},
            "ollama": {loc.id: loc for loc in ollama_locations}
        }
    
    def add_location(self, provider: str, location: ServerLocation):
        """Agregar una nueva ubicación de servidor"""
        if provider not in self.locations:
            self.locations[provider] = {}
        self.locations[provider][location.id] = location
        logger.info(f"Added server location: {location.name} for {provider}")
    
    def remove_location(self, provider: str, location_id: str):
        """Eliminar una ubicación de servidor"""
        if provider in self.locations and location_id in self.locations[provider]:
            removed = self.locations[provider].pop(location_id)
            logger.info(f"Removed server location: {removed.name}")
            return True
        return False
    
    def get_locations(self, provider: str) -> List[ServerLocation]:
        """Obtener todas las ubicaciones para un provider"""
        return list(self.locations.get(provider, {}).values())
    
    def check_server_health(self, location: ServerLocation) -> Tuple[bool, float, str]:
        """Verificar salud de un servidor específico"""
        try:
            start_time = time.time()
            
            # Construir URL de health check según el provider
            if location.provider == "openai":
                test_url = f"{location.base_url}/models"
                headers = {"Authorization": "Bearer test"}
            elif location.provider == "claude":
                test_url = f"{location.base_url}/v1/messages"
                headers = {"x-api-key": "test", "anthropic-version": "2023-06-01"}
            elif location.provider == "gemini":
                test_url = f"{location.base_url}/models"
                headers = {}
            elif location.provider == "xai":
                test_url = f"{location.base_url}/models"
                headers = {"Authorization": "Bearer test"}
            elif location.provider == "ollama":
                test_url = f"{location.base_url}/api/tags"
                headers = {}
            else:
                test_url = location.base_url
                headers = {}
            
            # Realizar request de prueba
            response = requests.get(
                test_url, 
                headers=headers,
                timeout=self.timeout_seconds,
                allow_redirects=True
            )
            
            latency = (time.time() - start_time) * 1000  # ms
            
            # Evaluar respuesta
            if response.status_code in [200, 401, 403]:  # 401/403 = auth error pero servidor funciona
                return True, latency, "Server responding"
            else:
                return False, latency, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, self.timeout_seconds * 1000, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, 0.0, "Connection failed"
        except Exception as e:
            return False, 0.0, f"Error: {str(e)}"
    
    def update_health_status(self, provider: str):
        """Actualizar estado de salud de todas las ubicaciones de un provider"""
        if provider not in self.locations:
            return
        
        for location in self.locations[provider].values():
            # Solo verificar si ha pasado suficiente tiempo
            if (location.last_check is None or 
                datetime.now() - location.last_check > timedelta(seconds=self.health_check_interval)):
                
                is_healthy, latency, message = self.check_server_health(location)
                
                location.latency_ms = latency
                location.last_check = datetime.now()
                
                if is_healthy:
                    location.success_count += 1
                    location.error_count = max(0, location.error_count - 1)  # Recuperación gradual
                    
                    if location.error_count == 0:
                        location.status = ServerStatus.HEALTHY
                    else:
                        location.status = ServerStatus.DEGRADED
                else:
                    location.error_count += 1
                    if location.error_count >= self.max_error_count:
                        location.status = ServerStatus.DOWN
                    else:
                        location.status = ServerStatus.DEGRADED
                
                logger.debug(f"Health check {location.name}: {location.status.value} (latency: {latency:.1f}ms)")
    
    def get_best_location(self, provider: str, exclude_ids: Optional[List[str]] = None) -> Optional[ServerLocation]:
        """Obtener la mejor ubicación disponible para un provider"""
        if provider not in self.locations:
            return None
        
        exclude_ids = exclude_ids or []
        available_locations = [
            loc for loc in self.locations[provider].values()
            if loc.id not in exclude_ids and loc.status in [ServerStatus.HEALTHY, ServerStatus.DEGRADED]
        ]
        
        if not available_locations:
            # Si no hay ubicaciones saludables, intentar con cualquiera
            available_locations = [
                loc for loc in self.locations[provider].values()
                if loc.id not in exclude_ids
            ]
        
        if not available_locations:
            return None
        
        # Ordenar por prioridad y luego por latencia
        available_locations.sort(key=lambda x: (x.priority, x.latency_ms))
        
        # Balanceo de carga: 70% mejor servidor, 30% distribución
        if len(available_locations) > 1 and random.random() < 0.3:
            # Seleccionar aleatoriamente entre los 3 mejores
            candidates = available_locations[:min(3, len(available_locations))]
            return random.choice(candidates)
        
        return available_locations[0]
    
    def get_failover_sequence(self, provider: str) -> List[ServerLocation]:
        """Obtener secuencia de failover ordenada para un provider"""
        if provider not in self.locations:
            return []
        
        locations = list(self.locations[provider].values())
        # Ordenar por prioridad, estado de salud y latencia
        locations.sort(key=lambda x: (
            x.priority,
            0 if x.status == ServerStatus.HEALTHY else 1 if x.status == ServerStatus.DEGRADED else 2,
            x.latency_ms
        ))
        
        return locations
    
    def execute_with_failover(self, provider: str, request_func, max_retries: int = 3, **kwargs):
        """Ejecutar una función con failover automático entre ubicaciones"""
        failover_sequence = self.get_failover_sequence(provider)
        
        if not failover_sequence:
            raise Exception(f"No server locations configured for provider: {provider}")
        
        last_error = None
        tried_locations = []
        
        for attempt in range(max_retries):
            # Obtener mejor ubicación disponible (excluyendo las ya intentadas)
            location = self.get_best_location(provider, exclude_ids=[loc.id for loc in tried_locations])
            
            if location is None:
                # Reiniciar la lista si hemos agotado todas las ubicaciones
                tried_locations = []
                location = self.get_best_location(provider)
                
                if location is None:
                    break
            
            tried_locations.append(location)
            
            try:
                logger.debug(f"Attempting request to {location.name} (attempt {attempt + 1})")
                
                # Actualizar kwargs con la URL de la ubicación
                kwargs['base_url'] = location.base_url
                kwargs['location_info'] = {
                    'id': location.id,
                    'name': location.name,
                    'region': location.region
                }
                
                result = request_func(**kwargs)
                
                # Marcar como exitoso
                location.success_count += 1
                location.error_count = max(0, location.error_count - 1)
                
                return result
                
            except Exception as e:
                last_error = e
                location.error_count += 1
                logger.warning(f"Request failed for {location.name}: {str(e)}")
                
                # Actualizar estado si hay muchos errores
                if location.error_count >= self.max_error_count:
                    location.status = ServerStatus.DOWN
                
                # Esperar un poco antes del siguiente intento
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        
        # Si llegamos aquí, todos los intentos fallaron
        raise Exception(f"All server locations failed for {provider}. Last error: {str(last_error)}")
    
    def get_status_summary(self) -> Dict:
        """Obtener resumen del estado de todas las ubicaciones"""
        summary = {}
        
        for provider, locations in self.locations.items():
            provider_status = {
                'total_locations': len(locations),
                'healthy': 0,
                'degraded': 0,
                'down': 0,
                'unknown': 0,
                'avg_latency_ms': 0.0,
                'locations': []
            }
            
            total_latency = 0
            healthy_count = 0
            
            for location in locations.values():
                status_count = location.status.value
                provider_status[status_count] = provider_status.get(status_count, 0) + 1
                
                if location.status == ServerStatus.HEALTHY:
                    total_latency += location.latency_ms
                    healthy_count += 1
                
                provider_status['locations'].append({
                    'id': location.id,
                    'name': location.name,
                    'region': location.region,
                    'status': location.status.value,
                    'latency_ms': location.latency_ms,
                    'priority': location.priority,
                    'error_count': location.error_count,
                    'success_count': location.success_count,
                    'last_check': location.last_check.isoformat() if location.last_check else None
                })
            
            if healthy_count > 0:
                provider_status['avg_latency_ms'] = total_latency / healthy_count
            
            summary[provider] = provider_status
        
        return summary
    
    def force_health_check(self, provider: Optional[str] = None):
        """Forzar verificación de salud inmediata"""
        providers_to_check = [provider] if provider else list(self.locations.keys())
        
        for prov in providers_to_check:
            if prov in self.locations:
                for location in self.locations[prov].values():
                    location.last_check = None  # Forzar nueva verificación
                self.update_health_status(prov)
    
    def configure_custom_location(self, provider: str, config: Dict) -> bool:
        """Configurar una ubicación personalizada"""
        try:
            location = ServerLocation(
                id=config.get('id', f"{provider}_custom_{int(time.time())}"),
                name=config.get('name', 'Custom Location'),
                region=config.get('region', 'custom'),
                base_url=config['base_url'],  # Requerido
                priority=config.get('priority', 3),
                provider=provider
            )
            
            self.add_location(provider, location)
            
            # Verificar salud inmediatamente
            is_healthy, latency, message = self.check_server_health(location)
            location.latency_ms = latency
            location.last_check = datetime.now()
            location.status = ServerStatus.HEALTHY if is_healthy else ServerStatus.DOWN
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure custom location: {e}")
            return False
    
    def export_configuration(self) -> Dict:
        """Exportar configuración completa"""
        config = {}
        
        for provider, locations in self.locations.items():
            config[provider] = []
            for location in locations.values():
                config[provider].append({
                    'id': location.id,
                    'name': location.name,
                    'region': location.region,
                    'base_url': location.base_url,
                    'priority': location.priority,
                    'provider': location.provider
                })
        
        return config
    
    def import_configuration(self, config: Dict):
        """Importar configuración"""
        for provider, location_configs in config.items():
            if provider not in self.locations:
                self.locations[provider] = {}
            
            for loc_config in location_configs:
                location = ServerLocation(
                    id=loc_config['id'],
                    name=loc_config['name'],
                    region=loc_config['region'],
                    base_url=loc_config['base_url'],
                    priority=loc_config.get('priority', 1),
                    provider=loc_config['provider']
                )
                self.locations[provider][location.id] = location