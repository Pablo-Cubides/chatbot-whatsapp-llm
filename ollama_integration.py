"""
Ollama Integration - Integración completa con Ollama para modelos locales
Ollama permite ejecutar modelos LLM localmente sin necesidad de APIs externas
"""

import json
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime
import time
from settings import settings

logger = logging.getLogger(__name__)

class OllamaIntegration:
    """Integración completa con Ollama para modelos locales"""
    
    def __init__(self, api_manager=None):
        self.api_manager = api_manager
        self.provider = 'ollama'
        
        # URLs configurables para Ollama
        self.base_url = 'http://localhost:11434'
        self.alternative_urls = [
            'http://127.0.0.1:11434',
            'http://localhost:11434',
            'http://0.0.0.0:11434'
        ]
        
        # Modelos populares que pueden estar disponibles
        self.popular_models = {
            'llama3.2': {
                'name': 'Llama 3.2',
                'description': 'Meta\'s latest Llama model (3B/1B parameters)',
                'size_info': '3B parameters (1.7GB) / 1B parameters (1.3GB)',
                'category': 'general',
                'strengths': ['reasoning', 'multilingual', 'code']
            },
            'llama3.1': {
                'name': 'Llama 3.1',
                'description': 'Meta Llama 3.1 (8B/70B/405B parameters)',
                'size_info': '8B (4.7GB) / 70B (40GB) / 405B (229GB)',
                'category': 'general',
                'strengths': ['reasoning', 'multilingual', 'long-context']
            },
            'llama3': {
                'name': 'Llama 3',
                'description': 'Meta Llama 3 (8B/70B parameters)',
                'size_info': '8B (4.7GB) / 70B (40GB)',
                'category': 'general',
                'strengths': ['conversational', 'reasoning', 'code']
            },
            'mistral': {
                'name': 'Mistral 7B',
                'description': 'Mistral AI\'s 7B parameter model',
                'size_info': '7B parameters (4.1GB)',
                'category': 'general',
                'strengths': ['efficient', 'fast', 'code']
            },
            'mixtral': {
                'name': 'Mixtral 8x7B',
                'description': 'Mistral AI\'s mixture of experts model',
                'size_info': '8x7B parameters (26GB)',
                'category': 'general',
                'strengths': ['reasoning', 'multilingual', 'efficient']
            },
            'codellama': {
                'name': 'Code Llama',
                'description': 'Meta\'s code-specialized Llama model',
                'size_info': '7B (3.8GB) / 13B (7.3GB) / 34B (19GB)',
                'category': 'code',
                'strengths': ['programming', 'code-completion', 'debugging']
            },
            'phi3': {
                'name': 'Phi-3',
                'description': 'Microsoft\'s efficient small language model',
                'size_info': '3.8B parameters (2.3GB)',
                'category': 'efficient',
                'strengths': ['small-size', 'reasoning', 'multilingual']
            },
            'gemma2': {
                'name': 'Gemma 2',
                'description': 'Google\'s latest Gemma model family',
                'size_info': '2B (1.6GB) / 9B (5.5GB) / 27B (16GB)',
                'category': 'general',
                'strengths': ['efficient', 'safety', 'reasoning']
            },
            'qwen2.5': {
                'name': 'Qwen2.5',
                'description': 'Alibaba\'s latest Qwen model',
                'size_info': '0.5B-72B parameters (various sizes)',
                'category': 'general',
                'strengths': ['multilingual', 'reasoning', 'math']
            },
            'deepseek-coder': {
                'name': 'DeepSeek Coder',
                'description': 'DeepSeek\'s specialized coding model',
                'size_info': '1.3B-33B parameters',
                'category': 'code',
                'strengths': ['programming', 'code-generation', 'debugging']
            }
        }
        
        # Cache para modelos disponibles
        self._available_models_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 60  # 60 segundos de cache
    
    def _get_working_url(self) -> Optional[str]:
        """Encontrar URL funcional de Ollama"""
        urls_to_try = [self.base_url] + self.alternative_urls
        
        for url in urls_to_try:
            try:
                response = requests.get(f"{url}/api/tags", timeout=5)
                if response.status_code == 200:
                    self.base_url = url
                    return url
            except Exception:
                continue
        return None
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Realizar petición a Ollama API"""
        working_url = self._get_working_url()
        if not working_url:
            raise Exception("Ollama server not accessible. Make sure Ollama is running on localhost:11434")
        
        url = f"{working_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=300)  # 5 minutos para generación
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            raise Exception("Could not connect to Ollama. Is Ollama running?")
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out. Model may be loading or generating")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {e}")
            raise Exception(f"Ollama API error: {str(e)}")
    
    def _make_streaming_request(self, endpoint: str, data: Dict):
        """Realizar petición streaming a Ollama API"""
        working_url = self._get_working_url()
        if not working_url:
            raise Exception("Ollama server not accessible")
        
        url = f"{working_url}/{endpoint}"
        
        try:
            response = requests.post(url, json=data, timeout=300, stream=True)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama streaming request failed: {e}")
            raise Exception(f"Ollama streaming error: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Probar conexión con Ollama"""
        try:
            start_time = time.time()
            
            # Verificar si Ollama está corriendo
            working_url = self._get_working_url()
            if not working_url:
                return {
                    'success': False,
                    'message': 'Ollama server not found',
                    'suggestion': 'Install and start Ollama: curl -fsSL https://ollama.ai/install.sh | sh && ollama serve',
                    'checked_urls': self.alternative_urls
                }
            
            # Obtener información del servidor
            server_info = self._make_request('api/version')
            response_time = time.time() - start_time
            
            # Obtener modelos instalados
            models_data = self._make_request('api/tags')
            installed_models = [model.get('name', 'unknown') for model in models_data.get('models', [])]
            
            return {
                'success': True,
                'message': f'Connected to Ollama at {working_url}',
                'server_version': server_info.get('version', 'unknown'),
                'response_time_ms': round(response_time * 1000, 2),
                'installed_models': installed_models,
                'total_models': len(installed_models),
                'server_url': working_url
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'error_type': type(e).__name__,
                'suggestion': 'Make sure Ollama is installed and running: ollama serve'
            }
    
    def get_available_models(self) -> Dict:
        """Obtener modelos disponibles en Ollama"""
        try:
            # Verificar cache
            current_time = time.time()
            if (self._available_models_cache and 
                current_time - self._cache_timestamp < self._cache_ttl):
                return self._available_models_cache
            
            # Verificar conexión
            working_url = self._get_working_url()
            if not working_url:
                return {
                    'success': False,
                    'models': {},
                    'error': 'Ollama server not accessible',
                    'popular_models': self.popular_models,
                    'suggestion': 'Install Ollama and pull models: ollama pull llama3.2'
                }
            
            # Obtener modelos instalados
            models_data = self._make_request('api/tags')
            installed_models = models_data.get('models', [])
            
            # Formatear modelos para respuesta
            formatted_models = {}
            for model in installed_models:
                model_name = model.get('name', 'unknown')
                model_id = model_name.split(':')[0]  # Remover tag si existe
                
                # Buscar información adicional en modelos populares
                model_info = self.popular_models.get(model_id, {})
                
                formatted_models[model_name] = {
                    'name': model_info.get('name', model_name),
                    'description': model_info.get('description', 'Local model via Ollama'),
                    'size': model.get('size', 0),
                    'size_gb': round(model.get('size', 0) / (1024**3), 2),
                    'modified': model.get('modified_at', ''),
                    'category': model_info.get('category', 'local'),
                    'strengths': model_info.get('strengths', ['local-inference']),
                    'cost_per_1m_input': 0.0,  # Gratis para modelos locales
                    'cost_per_1m_output': 0.0,
                    'local': True
                }
            
            result = {
                'success': True,
                'models': formatted_models,
                'total_installed': len(installed_models),
                'server_url': working_url,
                'popular_models': self.popular_models,
                'cache_info': {
                    'cached_at': datetime.now().isoformat(),
                    'ttl_seconds': self._cache_ttl
                }
            }
            
            # Actualizar cache
            self._available_models_cache = result
            self._cache_timestamp = current_time
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return {
                'success': False,
                'models': {},
                'error': str(e),
                'popular_models': self.popular_models,
                'suggestion': 'Ensure Ollama is running and models are installed'
            }
    
    def _format_messages_for_ollama(self, messages: List[Dict]) -> str:
        """Formatear mensajes para Ollama (formato de prompt simple)"""
        formatted_parts = []
        
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            if role == 'system':
                formatted_parts.append(f"System: {content}")
            elif role == 'user':
                formatted_parts.append(f"Human: {content}")
            elif role == 'assistant':
                formatted_parts.append(f"Assistant: {content}")
        
        # Agregar prompt final para respuesta
        formatted_parts.append("Assistant:")
        
        return "\n\n".join(formatted_parts)
    
    def generate_response(self, messages: List[Dict], model: str = 'llama3.2', 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict:
        """Generar respuesta usando Ollama"""
        try:
            # Verificar que el modelo esté disponible
            available_models = self.get_available_models()
            if not available_models.get('success', False):
                raise Exception("Could not get available models from Ollama")
            
            model_list = list(available_models.get('models', {}).keys())
            if not model_list:
                return {
                    'success': False,
                    'error': 'No models installed in Ollama',
                    'suggestion': 'Install a model: ollama pull llama3.2',
                    'available_models': []
                }
            
            # Usar primer modelo disponible si el solicitado no existe
            if model not in model_list:
                model = model_list[0]
                logger.warning(f"Requested model not found, using: {model}")
            
            # Formatear prompt para Ollama
            if len(messages) == 1 and messages[0].get('role') == 'user':
                # Prompt simple
                prompt = messages[0].get('content', '')
            else:
                # Múltiples mensajes - formatear como conversación
                prompt = self._format_messages_for_ollama(messages)
            
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            # Preparar datos para la API
            request_data = {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature,
                    'num_predict': max_tokens,
                    'top_p': 0.9,
                    'stop': ['Human:', 'User:', '\n\nHuman:', '\n\nUser:']
                }
            }
            
            start_time = time.time()
            response = self._make_request('api/generate', 'POST', request_data)
            response_time = time.time() - start_time
            
            # Extraer respuesta
            content = response.get('response', '').strip()
            
            # Limpiar respuesta si es necesario
            if content.startswith('Assistant:'):
                content = content[10:].strip()
            
            # Información de tokens (usar valores reales de Ollama si están disponibles)
            prompt_tokens = response.get('prompt_eval_count', len(prompt.split()))
            completion_tokens = response.get('eval_count', len(content.split()))
            total_tokens = prompt_tokens + completion_tokens
            
            return {
                'success': True,
                'content': content,
                'model_used': model,
                'finish_reason': 'stop',
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'cost_usd': 0.0  # Gratis para modelos locales
                },
                'response_time_ms': round(response_time * 1000, 2),
                'timestamp': datetime.now().isoformat(),
                'local_model': True,
                'model_info': response.get('model', {}),
                'load_duration_ms': response.get('load_duration', 0) // 1000000,  # ns to ms
                'eval_duration_ms': response.get('eval_duration', 0) // 1000000
            }
            
        except Exception as e:
            logger.error(f"Error generating Ollama response: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_requested': model,
                'timestamp': datetime.now().isoformat(),
                'suggestion': 'Check if model is installed: ollama list'
            }
    
    def generate_streaming_response(self, messages: List[Dict], model: str = 'llama3.2',
                                  temperature: float = 0.7, max_tokens: Optional[int] = None):
        """Generar respuesta en streaming usando Ollama"""
        try:
            # Verificar modelo disponible
            available_models = self.get_available_models()
            if not available_models.get('success', False):
                yield {'success': False, 'error': 'Could not access Ollama models'}
                return
            
            model_list = list(available_models.get('models', {}).keys())
            if not model_list:
                yield {'success': False, 'error': 'No models installed in Ollama'}
                return
            
            if model not in model_list:
                model = model_list[0]
            
            # Formatear prompt
            if len(messages) == 1 and messages[0].get('role') == 'user':
                prompt = messages[0].get('content', '')
            else:
                prompt = self._format_messages_for_ollama(messages)
            
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            request_data = {
                'model': model,
                'prompt': prompt,
                'stream': True,
                'options': {
                    'temperature': temperature,
                    'num_predict': max_tokens,
                    'top_p': 0.9,
                    'stop': ['Human:', 'User:', '\n\nHuman:', '\n\nUser:']
                }
            }
            
            response = self._make_streaming_request('api/generate', request_data)
            
            # Procesar stream
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        content = chunk.get('response', '')
                        done = chunk.get('done', False)
                        
                        if content:
                            yield {
                                'success': True,
                                'content': content,
                                'model': model,
                                'done': done,
                                'local_model': True
                            }
                        
                        if done:
                            break
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error in Ollama streaming: {e}")
            yield {
                'success': False,
                'error': str(e),
                'model': model
            }
    
    def pull_model(self, model_name: str) -> Dict:
        """Descargar un modelo en Ollama"""
        try:
            request_data = {
                'name': model_name,
                'stream': False
            }
            
            response = self._make_request('api/pull', 'POST', request_data)
            
            return {
                'success': True,
                'message': f'Model {model_name} pulled successfully',
                'model_name': model_name,
                'status': response.get('status', 'completed')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model_name': model_name,
                'suggestion': f'Try: ollama pull {model_name}'
            }
    
    def delete_model(self, model_name: str) -> Dict:
        """Eliminar un modelo de Ollama"""
        try:
            request_data = {'name': model_name}
            self._make_request('api/delete', 'DELETE', request_data)
            
            # Limpiar cache
            self._available_models_cache = None
            
            return {
                'success': True,
                'message': f'Model {model_name} deleted successfully',
                'model_name': model_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model_name': model_name
            }
    
    def estimate_cost(self, text: str, model: str = 'llama3.2') -> Dict:
        """Estimar costo para Ollama (siempre gratis)"""
        try:
            estimated_tokens = len(text.split())
            
            return {
                'success': True,
                'estimated_tokens': estimated_tokens,
                'estimated_cost_usd': 0.0,
                'model': model,
                'note': 'Local models are free to use',
                'local_model': True,
                'cost_breakdown': {
                    'input_cost': 0.0,
                    'output_cost': 0.0,
                    'total_cost': 0.0
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_usage_stats(self) -> Dict:
        """Obtener estadísticas de uso (información del sistema local)"""
        try:
            # Información básica del servidor
            connection_info = self.test_connection()
            models_info = self.get_available_models()
            
            if not connection_info.get('success'):
                return {
                    'success': False,
                    'error': 'Ollama not accessible',
                    'suggestion': 'Start Ollama: ollama serve'
                }
            
            return {
                'success': True,
                'message': 'Local Ollama usage statistics',
                'server_info': {
                    'version': connection_info.get('server_version'),
                    'url': connection_info.get('server_url'),
                    'status': 'running'
                },
                'models': {
                    'total_installed': models_info.get('total_installed', 0),
                    'models_list': list(models_info.get('models', {}).keys())
                },
                'costs': {
                    'total_cost_usd': 0.0,
                    'note': 'Local inference is free'
                },
                'recommendations': [
                    'Monitor disk space for model storage',
                    'Consider model sizes vs available RAM',
                    'Use smaller models for faster inference',
                    'Popular models: llama3.2, mistral, phi3'
                ]
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_system_info(self) -> Dict:
        """Obtener información del sistema Ollama"""
        try:
            working_url = self._get_working_url()
            if not working_url:
                return {
                    'success': False,
                    'error': 'Ollama not accessible'
                }
            
            # Información básica
            version_info = self._make_request('api/version')
            models_info = self._make_request('api/tags')
            
            total_size = sum(model.get('size', 0) for model in models_info.get('models', []))
            
            return {
                'success': True,
                'server_info': {
                    'version': version_info.get('version'),
                    'url': working_url,
                    'status': 'running'
                },
                'storage': {
                    'total_models_size_bytes': total_size,
                    'total_models_size_gb': round(total_size / (1024**3), 2),
                    'models_count': len(models_info.get('models', []))
                },
                'capabilities': {
                    'local_inference': True,
                    'no_api_costs': True,
                    'privacy_focused': True,
                    'offline_capable': True
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }