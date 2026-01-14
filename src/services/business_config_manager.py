"""
🏢 Gestor de Configuración de Negocio Editable
Sistema para que los usuarios personalicen completamente su chatbot
"""

import os
import json
from typing import Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BusinessConfigManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_file = self.project_root / "data" / "business_config.json"
        self.payload_file = self.project_root / "payload.json"
        self.reasoner_file = self.project_root / "payload_reasoner.json"
        
        # Asegurar que existe el directorio data
        self.config_file.parent.mkdir(exist_ok=True)
        
        # Cargar configuración inicial
        self.config = self.load_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Retorna configuración por defecto completamente editable"""
        return {
            "business_info": {
                "name": "Mi Negocio",
                "description": "Coloca aquí la descripción de tu negocio, qué servicios ofreces, cuál es tu especialidad y qué te diferencia de la competencia",
                "greeting": "¡Hola! Bienvenido/a a [NOMBRE_NEGOCIO]. ¿En qué puedo ayudarte hoy?",
                "closing": "Gracias por contactarnos. ¡Que tengas un excelente día!",
                "tone": "profesional_amigable",
                "services": [
                    "Coloca aquí tus principales servicios o productos",
                    "Ejemplo: consultas, ventas, soporte técnico"
                ],
                "hours": "Lunes a Viernes 9:00 AM - 6:00 PM",
                "contact_info": "Email: contacto@minegocio.com, Teléfono: +1-234-567-8900",
                "website": "https://www.minegocio.com",
                "location": "Ciudad, País"
            },
            "client_objectives": {
                "primary_goal": "Define aquí el objetivo principal con cada cliente (ej: generar ventas, agendar citas, brindar soporte)",
                "secondary_goals": [
                    "Objetivo secundario 1 (ej: recopilar información de contacto)",
                    "Objetivo secundario 2 (ej: fidelizar clientes existentes)"
                ],
                "conversion_keywords": [
                    "comprar", "precio", "costo", "agendar", "cita", "contactar"
                ],
                "qualification_questions": [
                    "¿Cuál es tu nombre?",
                    "¿En qué puedo ayudarte específicamente?",
                    "¿Cuándo te gustaría que nos pongamos en contacto?"
                ]
            },
            "conversation_flow": {
                "greeting_variants": [
                    "¡Hola! 👋 Bienvenido/a a [NEGOCIO]",
                    "¡Buen día! Gracias por contactarnos",
                    "¡Hola! Me da mucho gusto saludarte"
                ],
                "fallback_responses": [
                    "Disculpa, no entendí tu consulta. ¿Podrías reformularla?",
                    "No estoy seguro de entender. ¿Podrías ser más específico?",
                    "Permíteme conectarte con un representante humano para mejor asistencia"
                ],
                "escalation_triggers": [
                    "hablar con humano", "persona real", "no entiendes", "estoy molesto"
                ]
            },
            "ai_behavior": {
                "personality_traits": [
                    "Describe aquí cómo quieres que se comporte la IA",
                    "Ejemplo: profesional pero amigable, directo, detallista"
                ],
                "forbidden_topics": [
                    "Temas que la IA NO debe discutir",
                    "Ejemplo: política, religión, competencia"
                ],
                "response_length": "medium",  # short, medium, long
                "use_emojis": True,
                "formality_level": "casual_professional"  # formal, casual_professional, casual
            },
            "business_rules": {
                "working_hours": {
                    "enabled": True,
                    "schedule": {
                        "monday": {"start": "09:00", "end": "18:00"},
                        "tuesday": {"start": "09:00", "end": "18:00"},
                        "wednesday": {"start": "09:00", "end": "18:00"},
                        "thursday": {"start": "09:00", "end": "18:00"},
                        "friday": {"start": "09:00", "end": "18:00"},
                        "saturday": {"closed": True},
                        "sunday": {"closed": True}
                    },
                    "outside_hours_message": "Gracias por contactarnos. Estamos fuera del horario de atención. Te responderemos lo antes posible en horario laboral."
                },
                "auto_responses": {
                    "thank_you": "¡Gracias por tu interés! ¿Te gustaría que te enviemos más información?",
                    "goodbye": "¡Hasta pronto! No dudes en contactarnos cuando necesites.",
                    "human_transfer": "Te voy a conectar con un representante humano que podrá ayudarte mejor."
                }
            },
            "integrations": {
                "calendar_booking": {
                    "enabled": False,
                    "service": "calendly",  # calendly, google_calendar, custom
                    "link": "https://calendly.com/tu-negocio"
                },
                "crm_integration": {
                    "enabled": False,
                    "service": "hubspot",  # hubspot, salesforce, custom
                    "webhook_url": ""
                },
                "payment_links": {
                    "enabled": False,
                    "service": "stripe",  # stripe, paypal, mercadopago
                    "links": {}
                }
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Carga configuración desde archivo o crea una nueva"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Mergear con defaults para asegurar que tenga todas las claves
                default = self.get_default_config()
                return self._merge_configs(default, config)
            else:
                # Primera vez, crear config por defecto
                config = self.get_default_config()
                self.save_config(config)
                return config
        
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return self.get_default_config()
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Mergea configuración de usuario con defaults"""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Guarda configuración en archivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Actualizar archivos payload
            self._update_payload_files(config)
            return True
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False
    
    def _update_payload_files(self, config: Dict[str, Any]):
        """Actualiza payload.json y payload_reasoner.json basado en la configuración"""
        
        # Payload principal
        business_info = config.get('business_info', {})
        client_objectives = config.get('client_objectives', {})
        ai_behavior = config.get('ai_behavior', {})
        
        main_payload = {
            "business_name": business_info.get('name', 'Mi Negocio'),
            "business_description": business_info.get('description', ''),
            "greeting": business_info.get('greeting', ''),
            "closing": business_info.get('closing', ''),
            "services": business_info.get('services', []),
            "tone": business_info.get('tone', 'profesional_amigable'),
            "primary_goal": client_objectives.get('primary_goal', ''),
            "personality_traits": ai_behavior.get('personality_traits', []),
            "forbidden_topics": ai_behavior.get('forbidden_topics', []),
            "use_emojis": ai_behavior.get('use_emojis', True),
            "formality_level": ai_behavior.get('formality_level', 'casual_professional'),
            
            # Prompt principal construido dinámicamente
            "main_prompt": self._build_main_prompt(config)
        }
        
        try:
            with open(self.payload_file, 'w', encoding='utf-8') as f:
                json.dump(main_payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error actualizando payload principal: {e}")
        
        # Payload del razonador
        reasoner_payload = {
            "business_context": {
                "name": business_info.get('name'),
                "primary_goal": client_objectives.get('primary_goal'),
                "conversion_keywords": client_objectives.get('conversion_keywords', [])
            },
            "reasoning_objectives": [
                "Identificar la intención del cliente",
                "Evaluar el nivel de interés (frío/tibio/caliente)",
                "Determinar el mejor enfoque para la conversación",
                "Detectar oportunidades de conversión"
            ],
            "escalation_rules": config.get('conversation_flow', {}).get('escalation_triggers', [])
        }
        
        try:
            with open(self.reasoner_file, 'w', encoding='utf-8') as f:
                json.dump(reasoner_payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error actualizando payload razonador: {e}")
    
    def _build_main_prompt(self, config: Dict[str, Any]) -> str:
        """Construye el prompt principal basado en la configuración"""
        business_info = config.get('business_info', {})
        client_objectives = config.get('client_objectives', {})
        ai_behavior = config.get('ai_behavior', {})
        
        prompt = f"""Eres el asistente virtual de {business_info.get('name', 'nuestro negocio')}.

DESCRIPCIÓN DEL NEGOCIO:
{business_info.get('description', 'Ayudamos a nuestros clientes con sus necesidades.')}

TU OBJETIVO PRINCIPAL:
{client_objectives.get('primary_goal', 'Ayudar y satisfacer las necesidades del cliente.')}

SERVICIOS QUE OFRECEMOS:
{chr(10).join(f'- {service}' for service in business_info.get('services', []))}

PERSONALIDAD:
{chr(10).join(f'- {trait}' for trait in ai_behavior.get('personality_traits', ['Profesional y amigable']))}

TEMAS QUE NO DEBO DISCUTIR:
{chr(10).join(f'- {topic}' for topic in ai_behavior.get('forbidden_topics', []))}

HORARIO DE ATENCIÓN:
{business_info.get('hours', 'Consultar horarios de atención')}

CONTACTO:
{business_info.get('contact_info', 'Información de contacto disponible')}

INSTRUCCIONES ESPECÍFICAS:
1. Saluda de manera {ai_behavior.get('formality_level', 'profesional pero amigable')}
2. {"Usa emojis apropiados" if ai_behavior.get('use_emojis') else "No uses emojis"}
3. Mantén respuestas {ai_behavior.get('response_length', 'medium')} (ni muy cortas ni muy largas)
4. Siempre busca cumplir el objetivo principal con cada cliente
5. Si no sabes algo, ofrece conectar con un humano

Recuerda: Eres la primera impresión del negocio, sé {business_info.get('tone', 'profesional y amigable')}."""

        return prompt
    
    def update_field(self, field_path: str, value: Any) -> bool:
        """Actualiza un campo específico de la configuración"""
        try:
            keys = field_path.split('.')
            config = self.config
            
            # Navegar hasta el campo padre
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # Actualizar el campo
            config[keys[-1]] = value
            
            # Guardar
            return self.save_config(self.config)
            
        except Exception as e:
            logger.error(f"Error actualizando campo {field_path}: {e}")
            return False
    
    def get_editable_fields(self) -> Dict[str, Any]:
        """Retorna lista de campos editables con sus descripciones"""
        return {
            "business_info.name": {
                "label": "Nombre del Negocio",
                "type": "text",
                "placeholder": "Ej: Florería Bella Rosa, Panadería El Buen Pan",
                "required": True
            },
            "business_info.description": {
                "label": "Descripción del Negocio",
                "type": "textarea",
                "placeholder": "Describe tu negocio, servicios, especialidades...",
                "required": True
            },
            "business_info.greeting": {
                "label": "Saludo de Bienvenida",
                "type": "textarea",
                "placeholder": "¡Hola! Bienvenido/a a [NOMBRE_NEGOCIO]...",
                "required": True
            },
            "client_objectives.primary_goal": {
                "label": "Objetivo Principal con Clientes",
                "type": "textarea",
                "placeholder": "Ej: Generar ventas, agendar citas, brindar soporte...",
                "required": True
            },
            "business_info.services": {
                "label": "Servicios/Productos Principales",
                "type": "list",
                "placeholder": "Agrega tus servicios principales...",
                "required": False
            },
            "ai_behavior.personality_traits": {
                "label": "Personalidad de la IA",
                "type": "list",
                "placeholder": "Ej: Profesional, Amigable, Directo...",
                "required": False
            },
            "business_info.hours": {
                "label": "Horarios de Atención",
                "type": "text",
                "placeholder": "Ej: Lunes a Viernes 9:00 AM - 6:00 PM",
                "required": False
            },
            "business_info.contact_info": {
                "label": "Información de Contacto",
                "type": "text",
                "placeholder": "Email, teléfono, dirección...",
                "required": False
            }
        }
    
    def export_config(self) -> str:
        """Exporta configuración como JSON"""
        return json.dumps(self.config, indent=2, ensure_ascii=False)
    
    def import_config(self, config_json: str) -> bool:
        """Importa configuración desde JSON"""
        try:
            new_config = json.loads(config_json)
            self.config = self._merge_configs(self.get_default_config(), new_config)
            return self.save_config(self.config)
        except Exception as e:
            logger.error(f"Error importando configuración: {e}")
            return False

# Instancia global
business_config = BusinessConfigManager()
