"""
Claude (Anthropic) Integration - Integración completa con la API de Anthropic Claude
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

class ClaudeIntegration:
    """Integración completa con Anthropic Claude API"""
    
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.provider = 'anthropic'
        self.base_url = 'https://api.anthropic.com/v1'
        
        # Modelos disponibles de Claude
        self.available_models = {
            'claude-3-5-sonnet-20241022': {
                'name': 'Claude 3.5 Sonnet',
                'description': 'Modelo más avanzado, equilibrio perfecto entre inteligencia y velocidad',
                'max_tokens': 200000,
                'max_output_tokens': 8192,
                'cost_per_1m_input': 3.00,
                'cost_per_1m_output': 15.00,
                'context_window': 200000
            },
            'claude-3-5-haiku-20241022': {
                'name': 'Claude 3.5 Haiku',
                'description': 'Modelo más rápido y económico, ideal para tareas simples',
                'max_tokens': 200000,
                'max_output_tokens': 8192,
                'cost_per_1m_input': 0.25,
                'cost_per_1m_output': 1.25,
                'context_window': 200000
            },
            'claude-3-opus-20240229': {
                'name': 'Claude 3 Opus',
                'description': 'Modelo más poderoso para tareas complejas y razonamiento avanzado',
                'max_tokens': 200000,
                'max_output_tokens': 4096,
                'cost_per_1m_input': 15.00,
                'cost_per_1m_output': 75.00,
                'context_window': 200000
            },
            'claude-3-sonnet-20240229': {
                'name': 'Claude 3 Sonnet',
                'description': 'Balance entre rendimiento y costo para uso general',
                'max_tokens': 200000,
                'max_output_tokens': 4096,
                'cost_per_1m_input': 3.00,
                'cost_per_1m_output': 15.00,
                'context_window': 200000
            },
            'claude-3-haiku-20240307': {
                'name': 'Claude 3 Haiku',
                'description': 'Modelo rápido y económico para tareas simples',
                'max_tokens': 200000,
                'max_output_tokens': 4096,
                'cost_per_1m_input': 0.25,
                'cost_per_1m_output': 1.25,
                'context_window': 200000
            }
        }
    
    def _get_api_key(self) -> Optional[str]:
        """Obtener clave de API de forma segura"""
        return self.api_manager.get_api_key(self.provider, decrypt=True)
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Realizar petición autenticada a Claude API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No Anthropic API key configured")
        
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=120)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Claude API request failed: {e}")
            raise Exception(f"Claude API error: {str(e)}")
    
    def _make_streaming_request(self, endpoint: str, data: Dict):
        """Realizar petición streaming a Claude API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No Anthropic API key configured")
        
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120, stream=True)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Claude streaming request failed: {e}")
            raise Exception(f"Claude streaming error: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Probar conexión con Claude API"""
        try:
            start_time = time.time()
            
            # Claude API no tiene endpoint de modelos público, hacer una petición de test mínima
            test_data = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}]
            }
            
            response = self._make_request('messages', 'POST', test_data)
            response_time = time.time() - start_time
            
            # Verificar que la respuesta sea válida
            if response and 'content' in response:
                return {
                    'success': True,
                    'message': 'Connected successfully to Claude API',
                    'response_time_ms': round(response_time * 1000, 2),
                    'model_tested': 'claude-3-haiku-20240307'
                }
            else:
                return {
                    'success': False,
                    'message': 'Invalid response from Claude API',
                    'response_time_ms': round(response_time * 1000, 2)
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
            # Claude API no proporciona endpoint público de modelos
            # Devolver modelos predefinidos con verificación de clave API
            api_key = self._get_api_key()
            
            if not api_key:
                return {
                    'success': False,
                    'models': self.available_models,
                    'error': 'No Anthropic API key configured',
                    'fallback': True
                }
            
            return {
                'success': True,
                'models': self.available_models,
                'total_models': len(self.available_models),
                'note': 'Models based on Anthropic documentation - API key verified'
            }
            
        except Exception as e:
            logger.error(f"Error getting Claude models: {e}")
            return {
                'success': False,
                'models': self.available_models,
                'error': str(e),
                'fallback': True
            }
    
    def _format_messages_for_claude(self, messages: List[Dict]) -> List[Dict]:
        """Formatear mensajes para la API de Claude"""
        formatted_messages = []
        
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            # Claude usa 'user' y 'assistant' como roles válidos
            if role == 'system':
                # Los mensajes del sistema se convierten en mensajes del usuario con prefijo
                formatted_messages.append({
                    'role': 'user',
                    'content': f"System: {content}"
                })
            elif role in ['user', 'assistant']:
                formatted_messages.append({
                    'role': role,
                    'content': content
                })
        
        return formatted_messages
    
    def generate_response(self, messages: List[Dict], model: str = 'claude-3-haiku-20240307', 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict:
        """Generar respuesta usando Claude API"""
        try:
            if model not in self.available_models:
                model = 'claude-3-haiku-20240307'  # Fallback por defecto
            
            # Formatear mensajes para Claude
            formatted_messages = self._format_messages_for_claude(messages)
            
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            # Preparar datos para la API
            request_data = {
                'model': model,
                'messages': formatted_messages,
                'max_tokens': min(max_tokens, self.available_models[model]['max_output_tokens']),
                'temperature': temperature
            }
            
            start_time = time.time()
            response = self._make_request('messages', 'POST', request_data)
            response_time = time.time() - start_time
            
            # Extraer información de uso
            usage = response.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            total_tokens = input_tokens + output_tokens
            
            # Calcular costo estimado
            model_info = self.available_models.get(model, {})
            cost_input = (input_tokens / 1000000) * model_info.get('cost_per_1m_input', 0)
            cost_output = (output_tokens / 1000000) * model_info.get('cost_per_1m_output', 0)
            total_cost = cost_input + cost_output
            
            # Extraer respuesta
            content_blocks = response.get('content', [])
            if not content_blocks:
                raise Exception("No content blocks returned")
            
            content = content_blocks[0].get('text', '') if content_blocks else ''
            stop_reason = response.get('stop_reason', 'unknown')
            
            return {
                'success': True,
                'content': content,
                'model_used': model,
                'stop_reason': stop_reason,
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
            logger.error(f"Error generating Claude response: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_requested': model,
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_streaming_response(self, messages: List[Dict], model: str = 'claude-3-haiku-20240307',
                                  temperature: float = 0.7, max_tokens: int = 512):
        """Generar respuesta en streaming usando Claude API"""
        try:
            if model not in self.available_models:
                model = 'claude-3-haiku-20240307'
            
            formatted_messages = self._format_messages_for_claude(messages)
            
            request_data = {
                'model': model,
                'messages': formatted_messages,
                'max_tokens': min(max_tokens, self.available_models[model]['max_output_tokens']),
                'temperature': temperature,
                'stream': True
            }
            
            response = self._make_streaming_request('messages', request_data)
            
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
                            chunk_type = chunk.get('type')
                            
                            if chunk_type == 'content_block_delta':
                                delta = chunk.get('delta', {})
                                text = delta.get('text', '')
                                if text:
                                    yield {
                                        'success': True,
                                        'content': text,
                                        'model': model,
                                        'type': 'content'
                                    }
                            elif chunk_type == 'message_stop':
                                yield {
                                    'success': True,
                                    'content': '',
                                    'model': model,
                                    'type': 'stop'
                                }
                                break
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Error in Claude streaming: {e}")
            yield {
                'success': False,
                'error': str(e),
                'model': model
            }
    
    def estimate_cost(self, text: str, model: str = 'claude-3-haiku-20240307') -> Dict:
        """Estimar costo de una consulta"""
        try:
            # Estimación aproximada: ~4 caracteres por token (puede variar según el modelo)
            estimated_tokens = len(text) / 4
            
            model_info = self.available_models.get(model, self.available_models['claude-3-haiku-20240307'])
            estimated_cost = (estimated_tokens / 1000000) * model_info.get('cost_per_1m_input', 0)
            
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
    
    def get_usage_stats(self) -> Dict:
        """Obtener estadísticas de uso"""
        try:
            # Anthropic no proporciona endpoint público para estadísticas de uso
            return {
                'success': True,
                'message': 'Usage stats require Anthropic Console access',
                'note': 'Check https://console.anthropic.com/usage for detailed usage statistics'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }