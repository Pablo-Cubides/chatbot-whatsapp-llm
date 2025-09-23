"""
OpenAI Integration - Integración completa con la API de OpenAI
Utiliza las claves almacenadas de forma segura por el API Manager
"""

import json
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime
import time
from settings import settings

logger = logging.getLogger(__name__)

class OpenAIIntegration:
    """Integración completa con OpenAI API"""
    
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.provider = 'openai'
        self.base_url = 'https://api.openai.com/v1'
        
        # Modelos disponibles
        self.available_models = {
            'gpt-4': {
                'name': 'GPT-4',
                'description': 'Modelo más avanzado, mejor para tareas complejas',
                'max_tokens': 8192,
                'cost_per_1k_input': 0.03,
                'cost_per_1k_output': 0.06
            },
            'gpt-4-turbo': {
                'name': 'GPT-4 Turbo',
                'description': 'Versión optimizada de GPT-4, más rápida y económica',
                'max_tokens': 128000,
                'cost_per_1k_input': 0.01,
                'cost_per_1k_output': 0.03
            },
            'gpt-3.5-turbo': {
                'name': 'GPT-3.5 Turbo',
                'description': 'Equilibrio entre costo y rendimiento',
                'max_tokens': 4096,
                'cost_per_1k_input': 0.0015,
                'cost_per_1k_output': 0.002
            }
        }
    
    def _get_api_key(self) -> Optional[str]:
        """Obtener clave de API de forma segura"""
        return self.api_manager.get_api_key(self.provider, decrypt=True)
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Realizar petición autenticada a OpenAI API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No OpenAI API key configured")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=60)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _make_streaming_request(self, endpoint: str, data: Dict):
        """Realizar petición streaming a OpenAI API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No OpenAI API key configured")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60, stream=True)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI streaming request failed: {e}")
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Probar conexión con OpenAI API"""
        try:
            start_time = time.time()
            models = self._make_request('models')
            response_time = time.time() - start_time
            
            model_count = len(models.get('data', []))
            
            return {
                'success': True,
                'message': f'Connected successfully - {model_count} models available',
                'response_time_ms': round(response_time * 1000, 2),
                'models_available': model_count
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'error_type': type(e).__name__
            }
    
    def get_available_models(self) -> Dict:
        """Obtener modelos disponibles"""
        try:
            # Intentar obtener modelos en tiempo real de la API
            models_response = self._make_request('models')
            api_models = [model['id'] for model in models_response.get('data', [])]
            
            # Filtrar solo los modelos que tenemos configurados y están disponibles en la API
            available = {}
            for model_id, model_info in self.available_models.items():
                if model_id in api_models:
                    available[model_id] = model_info
                    available[model_id]['available_in_api'] = True
                else:
                    available[model_id] = model_info
                    available[model_id]['available_in_api'] = False
            
            return {
                'success': True,
                'models': available,
                'total_api_models': len(api_models)
            }
            
        except Exception as e:
            logger.error(f"Error getting OpenAI models: {e}")
            # Si falla la API, devolver modelos predeterminados
            return {
                'success': False,
                'models': self.available_models,
                'error': str(e),
                'fallback': True
            }
    
    def generate_response(self, messages: List[Dict], model: str = 'gpt-3.5-turbo', 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict:
        """Generar respuesta usando OpenAI API"""
        try:
            if model not in self.available_models:
                model = 'gpt-3.5-turbo'  # Fallback por defecto
            
            # Determine default max_tokens from centralized settings if caller omitted
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            # Preparar datos para la API
            request_data = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'stream': False
            }
            
            start_time = time.time()
            response = self._make_request('chat/completions', 'POST', request_data)
            response_time = time.time() - start_time
            
            # Extraer información de uso
            usage = response.get('usage', {})
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            
            # Calcular costo estimado
            model_info = self.available_models.get(model, {})
            cost_input = (input_tokens / 1000) * model_info.get('cost_per_1k_input', 0)
            cost_output = (output_tokens / 1000) * model_info.get('cost_per_1k_output', 0)
            total_cost = cost_input + cost_output
            
            # Extraer respuesta
            choices = response.get('choices', [])
            if not choices:
                raise Exception("No response choices returned")
            
            content = choices[0].get('message', {}).get('content', '')
            finish_reason = choices[0].get('finish_reason', 'unknown')
            
            return {
                'success': True,
                'content': content,
                'model_used': model,
                'finish_reason': finish_reason,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': total_tokens,
                    'estimated_cost_usd': round(total_cost, 6)
                },
                'response_time_ms': round(response_time * 1000, 2),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_requested': model,
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_streaming_response(self, messages: List[Dict], model: str = 'gpt-3.5-turbo',
                                  temperature: float = 0.7, max_tokens: int = 512):
        """Generar respuesta en streaming usando OpenAI API"""
        try:
            if model not in self.available_models:
                model = 'gpt-3.5-turbo'
            
            request_data = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'stream': True
            }
            
            response = self._make_streaming_request('chat/completions', request_data)
            
            # Generator para procesar el stream
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remover 'data: '
                        if data == '[DONE]':
                            break
                        
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield {
                                        'success': True,
                                        'content': content,
                                        'model': model,
                                        'finish_reason': choices[0].get('finish_reason')
                                    }
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Error in OpenAI streaming: {e}")
            yield {
                'success': False,
                'error': str(e),
                'model': model
            }
    
    def get_usage_stats(self) -> Dict:
        """Obtener estadísticas de uso (requiere configuración adicional en OpenAI)"""
        try:
            # Nota: OpenAI no proporciona endpoint público para estadísticas de uso en tiempo real
            # Esto requeriría integración con su sistema de billing
            
            return {
                'success': True,
                'message': 'Usage stats require OpenAI dashboard access',
                'note': 'Check https://platform.openai.com/usage for detailed usage statistics'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def estimate_cost(self, text: str, model: str = 'gpt-3.5-turbo') -> Dict:
        """Estimar costo de una consulta"""
        try:
            # Estimación aproximada: ~4 caracteres por token
            estimated_tokens = len(text) / 4
            
            model_info = self.available_models.get(model, self.available_models['gpt-3.5-turbo'])
            estimated_cost = (estimated_tokens / 1000) * model_info.get('cost_per_1k_input', 0)
            
            return {
                'success': True,
                'estimated_tokens': round(estimated_tokens),
                'estimated_cost_usd': round(estimated_cost, 6),
                'model': model,
                'note': 'This is an approximation - actual costs may vary'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }