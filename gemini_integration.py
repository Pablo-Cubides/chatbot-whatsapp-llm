"""
Gemini (Google) Integration - Integración completa con la API de Google Gemini
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

class GeminiIntegration:
    """Integración completa con Google Gemini API"""
    
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.provider = 'google'
        self.base_url = 'https://generativelanguage.googleapis.com/v1beta'
        
        # Modelos disponibles de Gemini
        self.available_models = {
            'gemini-1.5-pro': {
                'name': 'Gemini 1.5 Pro',
                'description': 'Modelo más avanzado con contexto extendido hasta 1M tokens',
                'max_tokens': 1048576,  # 1M tokens
                'max_output_tokens': 8192,
                'cost_per_1m_input': 3.50,
                'cost_per_1m_output': 10.50,
                'context_window': 1048576,
                'supports_system_instruction': True
            },
            'gemini-1.5-flash': {
                'name': 'Gemini 1.5 Flash',
                'description': 'Modelo optimizado para velocidad y eficiencia',
                'max_tokens': 1048576,
                'max_output_tokens': 8192,
                'cost_per_1m_input': 0.35,
                'cost_per_1m_output': 1.05,
                'context_window': 1048576,
                'supports_system_instruction': True
            },
            'gemini-1.0-pro': {
                'name': 'Gemini 1.0 Pro',
                'description': 'Modelo base confiable para uso general',
                'max_tokens': 32768,
                'max_output_tokens': 2048,
                'cost_per_1m_input': 0.50,
                'cost_per_1m_output': 1.50,
                'context_window': 32768,
                'supports_system_instruction': False
            }
        }
    
    def _get_api_key(self) -> Optional[str]:
        """Obtener clave de API de forma segura"""
        return self.api_manager.get_api_key(self.provider, decrypt=True)
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Realizar petición autenticada a Gemini API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No Google API key configured")
        
        # Agregar la clave API como parámetro de consulta
        url = f"{self.base_url}/{endpoint}"
        if '?' in url:
            url += f"&key={api_key}"
        else:
            url += f"?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
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
            logger.error(f"Gemini API request failed: {e}")
            raise Exception(f"Gemini API error: {str(e)}")
    
    def _make_streaming_request(self, endpoint: str, data: Dict):
        """Realizar petición streaming a Gemini API"""
        api_key = self._get_api_key()
        if not api_key:
            raise Exception("No Google API key configured")
        
        url = f"{self.base_url}/{endpoint}?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ChatBot-WhatsApp/1.0'
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120, stream=True)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini streaming request failed: {e}")
            raise Exception(f"Gemini streaming error: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Probar conexión con Gemini API"""
        try:
            start_time = time.time()
            
            # Listar modelos disponibles como test de conexión
            models = self._make_request('models')
            response_time = time.time() - start_time
            
            model_count = len(models.get('models', []))
            
            return {
                'success': True,
                'message': f'Connected successfully to Gemini API - {model_count} models available',
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
            api_models = []
            
            for model in models_response.get('models', []):
                model_name = model.get('name', '').replace('models/', '')
                if model_name:
                    api_models.append(model_name)
            
            # Filtrar solo los modelos que tenemos configurados
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
                'total_api_models': len(api_models)
            }
            
        except Exception as e:
            logger.error(f"Error getting Gemini models: {e}")
            # Si falla la API, devolver modelos predeterminados
            return {
                'success': False,
                'models': self.available_models,
                'error': str(e),
                'fallback': True
            }
    
    def _format_messages_for_gemini(self, messages: List[Dict], model: str) -> Dict:
        """Formatear mensajes para la API de Gemini"""
        contents = []
        system_instruction = None
        
        model_info = self.available_models.get(model, {})
        supports_system = model_info.get('supports_system_instruction', False)
        
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            if role == 'system':
                if supports_system and system_instruction is None:
                    # Usar como system instruction si el modelo lo soporta
                    system_instruction = content
                else:
                    # Convertir a mensaje del usuario si no se soporta
                    contents.append({
                        'role': 'user',
                        'parts': [{'text': f"System: {content}"}]
                    })
            elif role == 'user':
                contents.append({
                    'role': 'user',
                    'parts': [{'text': content}]
                })
            elif role == 'assistant':
                contents.append({
                    'role': 'model',  # Gemini usa 'model' en lugar de 'assistant'
                    'parts': [{'text': content}]
                })
        
        request_data: Dict = {
            'contents': contents
        }
        
        if system_instruction and supports_system:
            request_data['systemInstruction'] = {
                'parts': [{'text': system_instruction}]
            }
        
        return request_data
    
    def generate_response(self, messages: List[Dict], model: str = 'gemini-1.5-flash', 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict:
        """Generar respuesta usando Gemini API"""
        try:
            if model not in self.available_models:
                model = 'gemini-1.5-flash'  # Fallback por defecto
            
            # Formatear mensajes para Gemini
            request_data = self._format_messages_for_gemini(messages, model)
            
            # Agregar configuración de generación
            try:
                default_mt = int(getattr(settings, 'reasoner').max_tokens)
            except Exception:
                default_mt = 512
            if max_tokens is None:
                max_tokens = default_mt

            model_info = self.available_models.get(model, {})
            max_output = min(max_tokens, model_info.get('max_output_tokens', 2048))
            
            request_data['generationConfig'] = {
                'temperature': temperature,
                'maxOutputTokens': max_output,
                'topP': 0.95,
                'topK': 64
            }
            
            start_time = time.time()
            endpoint = f"models/{model}:generateContent"
            response = self._make_request(endpoint, 'POST', request_data)
            response_time = time.time() - start_time
            
            # Extraer información de uso
            usage = response.get('usageMetadata', {})
            input_tokens = usage.get('promptTokenCount', 0)
            output_tokens = usage.get('candidatesTokenCount', 0)
            total_tokens = usage.get('totalTokenCount', input_tokens + output_tokens)
            
            # Calcular costo estimado
            cost_input = (input_tokens / 1000000) * model_info.get('cost_per_1m_input', 0)
            cost_output = (output_tokens / 1000000) * model_info.get('cost_per_1m_output', 0)
            total_cost = cost_input + cost_output
            
            # Extraer respuesta
            candidates = response.get('candidates', [])
            if not candidates:
                raise Exception("No candidates returned")
            
            candidate = candidates[0]
            content_parts = candidate.get('content', {}).get('parts', [])
            content = content_parts[0].get('text', '') if content_parts else ''
            finish_reason = candidate.get('finishReason', 'unknown')
            
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
            logger.error(f"Error generating Gemini response: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_requested': model,
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_streaming_response(self, messages: List[Dict], model: str = 'gemini-1.5-flash',
                                  temperature: float = 0.7, max_tokens: int = 512):
        """Generar respuesta en streaming usando Gemini API"""
        try:
            if model not in self.available_models:
                model = 'gemini-1.5-flash'
            
            request_data = self._format_messages_for_gemini(messages, model)
            
            model_info = self.available_models.get(model, {})
            max_output = min(max_tokens, model_info.get('max_output_tokens', 2048))
            
            request_data['generationConfig'] = {
                'temperature': temperature,
                'maxOutputTokens': max_output,
                'topP': 0.95,
                'topK': 64
            }
            
            endpoint = f"models/{model}:streamGenerateContent"
            response = self._make_streaming_request(endpoint, request_data)
            
            # Generator para procesar el stream
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remover 'data: '
                        
                        try:
                            chunk = json.loads(data)
                            candidates = chunk.get('candidates', [])
                            
                            if candidates:
                                candidate = candidates[0]
                                content_parts = candidate.get('content', {}).get('parts', [])
                                
                                if content_parts:
                                    text = content_parts[0].get('text', '')
                                    if text:
                                        yield {
                                            'success': True,
                                            'content': text,
                                            'model': model,
                                            'type': 'content'
                                        }
                                
                                finish_reason = candidate.get('finishReason')
                                if finish_reason:
                                    yield {
                                        'success': True,
                                        'content': '',
                                        'model': model,
                                        'type': 'stop',
                                        'finish_reason': finish_reason
                                    }
                                    break
                                    
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Error in Gemini streaming: {e}")
            yield {
                'success': False,
                'error': str(e),
                'model': model
            }
    
    def estimate_cost(self, text: str, model: str = 'gemini-1.5-flash') -> Dict:
        """Estimar costo de una consulta"""
        try:
            # Estimación aproximada: ~4 caracteres por token
            estimated_tokens = len(text) / 4
            
            model_info = self.available_models.get(model, self.available_models['gemini-1.5-flash'])
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
            # Google Cloud no proporciona endpoint específico para estadísticas de Gemini
            return {
                'success': True,
                'message': 'Usage stats require Google Cloud Console access',
                'note': 'Check Google Cloud Console for detailed usage statistics'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }