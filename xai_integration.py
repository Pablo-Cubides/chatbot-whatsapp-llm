"""
X.AI Grok Integration - Integración completa con la API de X.AI Grok
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

class XAIIntegration:
    """Integración completa con X.AI Grok API"""
    
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.provider = 'xai'
        self.base_url = 'https://api.x.ai/v1'
        
        # Modelos disponibles de X.AI Grok
        self.available_models = {
            'grok-beta': {
                'name': 'Grok Beta',
                'description': 'Modelo conversacional avanzado con acceso a información en tiempo real',
                'max_tokens': 131072,  # 128k tokens
                'max_output_tokens': 4096,
                'cost_per_1m_input': 5.00,  # Estimado
                'cost_per_1m_output': 15.00,  # Estimado
                'context_window': 131072,
                'supports_real_time': True,
                'note': 'Pricing is estimated - check X.AI documentation for current rates'
            },
            'grok-vision-beta': {
                'name': 'Grok Vision Beta',
                'description': 'Modelo con capacidades de visión y análisis de imágenes',
                'max_tokens': 131072,
                'max_output_tokens': 4096,
                'cost_per_1m_input': 5.00,  # Estimado
                'cost_per_1m_output': 15.00,  # Estimado
                'context_window': 131072,
                'supports_vision': True,
                'note': 'Pricing is estimated - check X.AI documentation for current rates'
            }
        }
        
        # Configuración de rate limiting específica para X.AI
        self.rate_limits = {
            'requests_per_minute': 60,  # Límite conservador
            'tokens_per_minute': 60000,
            'requests_per_day': 5000
        }
    
    def _get_api_key(self) -> Optional[str]:
        """Obtener clave de API de forma segura"""
        return self.api_manager.get_api_key(self.provider, decrypt=True)
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Realizar petición autenticada a X.AI API con rate limiting"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No X.AI API key configured")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # Rate limiting: esperar un poco entre requests
            time.sleep(0.1)  # 100ms de delay para ser conservador
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=180)  # Timeout más largo
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Manejo específico de rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '60')
                raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"X.AI API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 429:
                    raise Exception("X.AI rate limit exceeded. Please wait before making more requests")
                elif e.response.status_code == 503:
                    raise Exception("X.AI service temporarily unavailable")
            raise Exception(f"X.AI API error: {str(e)}")
    
    def _make_streaming_request(self, endpoint: str, data: Dict):
        """Realizar petición streaming a X.AI API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No X.AI API key configured")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # Rate limiting para streaming
            time.sleep(0.2)
            
            response = requests.post(url, headers=headers, json=data, timeout=180, stream=True)
            
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '60')
                raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"X.AI streaming request failed: {e}")
            raise Exception(f"X.AI streaming error: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Probar conexión con X.AI API"""
        try:
            start_time = time.time()
            
            # Test simple con el modelo beta
            test_data = {
                'model': 'grok-beta',
                'messages': [{'role': 'user', 'content': 'Hello'}],
                'max_tokens': 10,
                'temperature': 0.1
            }
            
            response = self._make_request('chat/completions', 'POST', test_data)
            response_time = time.time() - start_time
            
            # Verificar que la respuesta sea válida
            if response and 'choices' in response:
                return {
                    'success': True,
                    'message': 'Connected successfully to X.AI Grok API',
                    'response_time_ms': round(response_time * 1000, 2),
                    'model_tested': 'grok-beta',
                    'rate_limits': self.rate_limits
                }
            else:
                return {
                    'success': False,
                    'message': 'Invalid response from X.AI API',
                    'response_time_ms': round(response_time * 1000, 2)
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'error_type': type(e).__name__,
                'note': 'X.AI API may have strict rate limits or limited availability'
            }
    
    def get_available_models(self) -> Dict:
        """Obtener modelos disponibles"""
        try:
            # X.AI API puede no tener endpoint público de modelos
            # Intentar acceder, pero usar fallback si falla
            try:
                models_response = self._make_request('models')
                api_models = [model.get('id', '') for model in models_response.get('data', [])]
                
                # Filtrar modelos conocidos
                available = {}
                for model_id, model_info in self.available_models.items():
                    model_info_copy = model_info.copy()
                    if model_id in api_models:
                        model_info_copy['available_in_api'] = True
                    else:
                        model_info_copy['available_in_api'] = False
                    available[model_id] = model_info_copy
                
                return {
                    'success': True,
                    'models': available,
                    'total_api_models': len(api_models),
                    'rate_limits': self.rate_limits
                }
                
            except Exception:
                # Fallback a modelos predefinidos
                api_key = self._get_api_key()
                if not api_key:
                    return {
                        'success': False,
                        'models': self.available_models,
                        'error': 'No X.AI API key configured',
                        'fallback': True
                    }
                
                return {
                    'success': True,
                    'models': self.available_models,
                    'note': 'Using predefined models - X.AI models endpoint may be restricted',
                    'rate_limits': self.rate_limits
                }
            
        except Exception as e:
            logger.error(f"Error getting X.AI models: {e}")
            return {
                'success': False,
                'models': self.available_models,
                'error': str(e),
                'fallback': True
            }
    
    def _format_messages_for_xai(self, messages: List[Dict]) -> List[Dict]:
        """Formatear mensajes para la API de X.AI (compatible con OpenAI)"""
        formatted_messages = []
        
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            # X.AI Grok usa formato similar a OpenAI
            if role in ['system', 'user', 'assistant']:
                formatted_messages.append({
                    'role': role,
                    'content': content
                })
        
        return formatted_messages
    
    def generate_response(self, messages: List[Dict], model: str = 'grok-beta', 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict:
        """Generar respuesta usando X.AI API"""
        try:
            if model not in self.available_models:
                model = 'grok-beta'  # Fallback por defecto
            
            # Formatear mensajes para X.AI
            formatted_messages = self._format_messages_for_xai(messages)
            
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            # Preparar datos para la API
            model_info = self.available_models.get(model, {})
            max_output = min(max_tokens, model_info.get('max_output_tokens', 4096))
            
            request_data = {
                'model': model,
                'messages': formatted_messages,
                'max_tokens': max_output,
                'temperature': temperature,
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
            cost_input = (input_tokens / 1000000) * model_info.get('cost_per_1m_input', 0)
            cost_output = (output_tokens / 1000000) * model_info.get('cost_per_1m_output', 0)
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
                'timestamp': datetime.now().isoformat(),
                'rate_limits': self.rate_limits
            }
            
        except Exception as e:
            logger.error(f"Error generating X.AI response: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_requested': model,
                'timestamp': datetime.now().isoformat(),
                'note': 'X.AI may have rate limits or availability restrictions'
            }
    
    def generate_streaming_response(self, messages: List[Dict], model: str = 'grok-beta',
                                  temperature: float = 0.7, max_tokens: Optional[int] = None):
        """Generar respuesta en streaming usando X.AI API"""
        try:
            if model not in self.available_models:
                model = 'grok-beta'
            
            formatted_messages = self._format_messages_for_xai(messages)
            
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            model_info = self.available_models.get(model, {})
            max_output = min(max_tokens, model_info.get('max_output_tokens', 4096))
            
            request_data = {
                'model': model,
                'messages': formatted_messages,
                'max_tokens': max_output,
                'temperature': temperature,
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
            logger.error(f"Error in X.AI streaming: {e}")
            yield {
                'success': False,
                'error': str(e),
                'model': model
            }
    
    def estimate_cost(self, text: str, model: str = 'grok-beta') -> Dict:
        """Estimar costo de una consulta"""
        try:
            # Estimación aproximada: ~4 caracteres por token
            estimated_tokens = len(text) / 4
            
            model_info = self.available_models.get(model, self.available_models['grok-beta'])
            estimated_cost = (estimated_tokens / 1000000) * model_info.get('cost_per_1m_input', 0)
            
            return {
                'success': True,
                'estimated_tokens': round(estimated_tokens),
                'estimated_cost_usd': round(estimated_cost, 6),
                'model': model,
                'note': model_info.get('note', 'Cost estimation is approximate'),
                'rate_limits': self.rate_limits
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_usage_stats(self) -> Dict:
        """Obtener estadísticas de uso"""
        try:
            # X.AI no proporciona endpoint público para estadísticas
            return {
                'success': True,
                'message': 'Usage stats require X.AI Console access',
                'note': 'Check X.AI platform for detailed usage statistics',
                'rate_limits': self.rate_limits,
                'recommendations': [
                    'Monitor rate limits carefully',
                    'X.AI has strict usage policies',
                    'Consider caching responses when possible',
                    'Use appropriate delays between requests'
                ]
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_rate_limit_info(self) -> Dict:
        """Obtener información específica sobre límites de tasa"""
        return {
            'success': True,
            'rate_limits': self.rate_limits,
            'recommendations': [
                'Space out requests by at least 100ms',
                'Monitor daily usage limits',
                'Implement exponential backoff for 429 errors',
                'Cache responses when possible to reduce API calls'
            ],
            'status_codes': {
                '429': 'Rate limit exceeded - wait before retrying',
                '503': 'Service unavailable - X.AI may be at capacity'
            }
        }