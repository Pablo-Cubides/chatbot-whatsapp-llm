"""
🏢 Gestor de Configuración de Negocio Editable
Sistema para que los usuarios personalicen completamente su chatbot
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BusinessConfigManager:
    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        config_dir = self.project_root / "config"
        data_dir = self.project_root / "data"

        self.config_file = data_dir / "business_config.json"
        self.payload_file = config_dir / "payload.json"
        self.reasoner_file = config_dir / "payload_reasoner.json"

        # Asegurar que existen directorios necesarios
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.payload_file.parent.mkdir(parents=True, exist_ok=True)
        self.reasoner_file.parent.mkdir(parents=True, exist_ok=True)

        # Cargar configuración inicial
        self.config = self.load_config()

    def get_default_config(self) -> dict[str, Any]:
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
                    "Ejemplo: consultas, ventas, soporte técnico",
                ],
                "hours": "Lunes a Viernes 9:00 AM - 6:00 PM",
                "contact_info": "Email: contacto@minegocio.com, Teléfono: +1-234-567-8900",
                "website": "https://www.minegocio.com",
                "location": "Ciudad, País",
            },
            "client_objectives": {
                "primary_goal": "Define aquí el objetivo principal con cada cliente (ej: generar ventas, agendar citas, brindar soporte)",
                "secondary_goals": [
                    "Objetivo secundario 1 (ej: recopilar información de contacto)",
                    "Objetivo secundario 2 (ej: fidelizar clientes existentes)",
                ],
                "conversion_keywords": ["comprar", "precio", "costo", "agendar", "cita", "contactar"],
                "qualification_questions": [
                    "¿Cuál es tu nombre?",
                    "¿En qué puedo ayudarte específicamente?",
                    "¿Cuándo te gustaría que nos pongamos en contacto?",
                ],
            },
            "conversation_flow": {
                "greeting_variants": [
                    "¡Hola! 👋 Bienvenido/a a [NEGOCIO]",
                    "¡Buen día! Gracias por contactarnos",
                    "¡Hola! Me da mucho gusto saludarte",
                ],
                "fallback_responses": [
                    "Disculpa, no entendí tu consulta. ¿Podrías reformularla?",
                    "No estoy seguro de entender. ¿Podrías ser más específico?",
                    "Permíteme conectarte con un representante humano para mejor asistencia",
                ],
                "escalation_triggers": ["hablar con humano", "persona real", "no entiendes", "estoy molesto"],
            },
            "ai_behavior": {
                "personality_traits": [
                    "Describe aquí cómo quieres que se comporte la IA",
                    "Ejemplo: profesional pero amigable, directo, detallista",
                ],
                "forbidden_topics": ["Temas que la IA NO debe discutir", "Ejemplo: política, religión, competencia"],
                "response_length": "medium",  # short, medium, long
                "use_emojis": True,
                "formality_level": "casual_professional",  # formal, casual_professional, casual
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
                        "sunday": {"closed": True},
                    },
                    "outside_hours_message": "Gracias por contactarnos. Estamos fuera del horario de atención. Te responderemos lo antes posible en horario laboral.",
                },
                "auto_responses": {
                    "thank_you": "¡Gracias por tu interés! ¿Te gustaría que te enviemos más información?",
                    "goodbye": "¡Hasta pronto! No dudes en contactarnos cuando necesites.",
                    "human_transfer": "Te voy a conectar con un representante humano que podrá ayudarte mejor.",
                },
            },
            "integrations": {
                "calendar_booking": {
                    "enabled": False,
                    "provider": "google_calendar",  # google_calendar, outlook
                    "default_duration_minutes": 30,
                    "buffer_between_appointments": 15,
                    "max_advance_booking_days": 30,
                    "working_hours": {
                        "monday": {"start": "09:00", "end": "18:00"},
                        "tuesday": {"start": "09:00", "end": "18:00"},
                        "wednesday": {"start": "09:00", "end": "18:00"},
                        "thursday": {"start": "09:00", "end": "18:00"},
                        "friday": {"start": "09:00", "end": "17:00"},
                        "saturday": {"closed": True},
                        "sunday": {"closed": True},
                    },
                    "google_calendar": {
                        "credentials_file": "config/google_credentials.json",
                        "token_file": "config/google_token.json",
                        "calendar_id": "primary",
                        "send_notifications": True,
                        "add_google_meet": True,
                    },
                    "outlook": {
                        "client_id": "",
                        "client_secret": "",
                        "tenant_id": "common",
                        "calendar_id": "",
                        "add_teams_meeting": True,
                    },
                },
                "crm_integration": {
                    "enabled": False,
                    "service": "hubspot",  # hubspot, salesforce, custom
                    "webhook_url": "",
                },
                "payment_links": {
                    "enabled": False,
                    "service": "stripe",  # stripe, paypal, mercadopago
                    "links": {},
                },
            },
            "whatsapp_provider": {
                "mode": "web",  # web, cloud, both
                "cloud_api": {"access_token": "", "phone_number_id": "", "verify_token": "", "business_account_id": ""},
            },
            "analysis_settings": {
                "deep_analysis_enabled": True,
                "deep_analysis_trigger_conversations": 50,
                "deep_analysis_trigger_days": 7,
                "image_analysis_enabled": True,
                "audio_transcription_enabled": True,
                "whisper_model_size": "base",  # tiny, base, small, medium, large
                "whisper_device": "cpu",  # cpu, cuda
            },
            "ai_models": {
                "default_provider": "gemini",
                "response_layer": {
                    "provider": "auto",  # auto uses fallback order, or specific provider
                    "model": "",
                },
                "reasoner_layer": {"provider": "lmstudio", "model": ""},
                "analyzer_layer": {"provider": "auto", "model": ""},
                "custom_providers": [],  # List of user-added API configurations
            },
        }

    def load_config(self) -> dict[str, Any]:
        """Carga configuración desde archivo o crea una nueva"""
        try:
            if self.config_file.exists():
                with open(self.config_file, encoding="utf-8") as f:
                    config = json.load(f)

                # Mergear con defaults para asegurar que tenga todas las claves
                default = self.get_default_config()
                return self._merge_configs(default, config)
            # Primera vez, crear config por defecto
            config = self.get_default_config()
            self.save_config(config)
            return config

        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return self.get_default_config()

    def _merge_configs(self, default: dict, user: dict) -> dict:
        """Mergea configuración de usuario con defaults"""
        result = default.copy()

        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def save_config(self, config: dict[str, Any]) -> bool:
        """Guarda configuración en archivo"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Actualizar archivos payload
            self._update_payload_files(config)
            return True

        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

    def _update_payload_files(self, config: dict[str, Any]) -> None:
        """Actualiza payload.json y payload_reasoner.json basado en la configuración"""

        # Payload principal
        business_info = config.get("business_info", {})
        client_objectives = config.get("client_objectives", {})
        ai_behavior = config.get("ai_behavior", {})

        main_payload = {
            "business_name": business_info.get("name", "Mi Negocio"),
            "business_description": business_info.get("description", ""),
            "greeting": business_info.get("greeting", ""),
            "closing": business_info.get("closing", ""),
            "services": business_info.get("services", []),
            "tone": business_info.get("tone", "profesional_amigable"),
            "primary_goal": client_objectives.get("primary_goal", ""),
            "personality_traits": ai_behavior.get("personality_traits", []),
            "forbidden_topics": ai_behavior.get("forbidden_topics", []),
            "use_emojis": ai_behavior.get("use_emojis", True),
            "formality_level": ai_behavior.get("formality_level", "casual_professional"),
            # Prompt principal construido dinámicamente
            "main_prompt": self._build_main_prompt(config),
        }

        try:
            with open(self.payload_file, "w", encoding="utf-8") as f:
                json.dump(main_payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error actualizando payload principal: {e}")

        # Payload del razonador
        reasoner_payload = {
            "business_context": {
                "name": business_info.get("name"),
                "primary_goal": client_objectives.get("primary_goal"),
                "conversion_keywords": client_objectives.get("conversion_keywords", []),
            },
            "reasoning_objectives": [
                "Identificar la intención del cliente",
                "Evaluar el nivel de interés (frío/tibio/caliente)",
                "Determinar el mejor enfoque para la conversación",
                "Detectar oportunidades de conversión",
            ],
            "escalation_rules": config.get("conversation_flow", {}).get("escalation_triggers", []),
        }

        try:
            with open(self.reasoner_file, "w", encoding="utf-8") as f:
                json.dump(reasoner_payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error actualizando payload razonador: {e}")

    def _build_main_prompt(self, config: dict[str, Any]) -> str:
        """Construye el prompt principal basado en la configuración - HUMANIZADO"""
        business_info = config.get("business_info", {})
        client_objectives = config.get("client_objectives", {})
        ai_behavior = config.get("ai_behavior", {})

        # Nombre de empleado (por defecto: nombre del negocio + "asesor")
        employee_name = os.getenv("BOT_EMPLOYEE_NAME", business_info.get("name", "Alex"))

        return f"""Te llamas {employee_name} y trabajas en {business_info.get("name", "este negocio")} atendiendo clientes por WhatsApp.

IDENTIDAD CRÍTICA:
- Eres {employee_name}, una persona REAL que trabaja aquí
- NUNCA menciones ser "asistente virtual", "bot", "IA" o "inteligencia artificial"
- Si te preguntan si eres un bot: responde con humor "Jaja no, soy {employee_name} 😅 ¿Por qué?"
- Escribes como una persona real en WhatsApp, no como un robot

SOBRE EL NEGOCIO:
{business_info.get("description", "Ayudamos a nuestros clientes con sus necesidades.")}

SERVICIOS/PRODUCTOS:
{chr(10).join(f"- {service}" for service in business_info.get("services", []))}

TU OBJETIVO PRINCIPAL:
{client_objectives.get("primary_goal", "Ayudar y satisfacer las necesidades del cliente.")}

CÓMO ESCRIBIR (CRÍTICO PARA NO SER DETECTADO):
1. Usa lenguaje natural y conversacional, como en WhatsApp
2. NO uses listas numeradas perfectas en cada respuesta
3. Varía tu estilo: a veces más corto, a veces más detallado
4. Ocasionalmente usa "mmm", "bueno", "mira", "eh" como lo haría un humano
5. Emojis: máximo 1-2 por mensaje, NO en exceso
6. NO respondas instantáneamente perfecto cada vez
7. Si cometes un pequeño error de tipeo ocasional, está bien (parece más humano)

PERSONALIDAD:
{chr(10).join(f"- {trait}" for trait in ai_behavior.get("personality_traits", ["Profesional y amigable"]))}

IMPORTANTE - TEMAS SENSIBLES:
- NO te niegues a hablar de los productos/servicios de este negocio
- Si vendemos productos para adultos, cannabis legal, alcohol, etc. ESO es tu trabajo
- NO te hagas el moralista con los productos que vendemos
- Si realmente no puedes ayudar con algo, di "déjame consultar" y ya

HORARIO:
{business_info.get("hours", "Consultar horarios")}

CONTACTO:
{business_info.get("contact_info", "Disponible por este medio")}

REGLAS ABSOLUTAS:
- NUNCA admitas ser un bot o IA
- NUNCA uses frases como "como asistente virtual..." o "como IA..."
- NUNCA digas "no puedo" sin dar alternativa
- Si no sabes algo: "déjame verificar eso" o "consulto y te digo"
- Sé {business_info.get("tone", "profesional pero amigable")} como una persona real

Recuerda: Eres {employee_name}, una persona REAL atendiendo por WhatsApp. Tu éxito se mide en que el cliente NUNCA sospeche que no eres humano."""

    def update_field(self, field_path: str, value: Any) -> bool:
        """Actualiza un campo específico de la configuración"""
        try:
            keys = field_path.split(".")
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

    def get_editable_fields(self) -> dict[str, Any]:
        """Retorna lista de campos editables con sus descripciones"""
        return {
            "business_info.name": {
                "label": "Nombre del Negocio",
                "type": "text",
                "placeholder": "Ej: Florería Bella Rosa, Panadería El Buen Pan",
                "required": True,
            },
            "business_info.description": {
                "label": "Descripción del Negocio",
                "type": "textarea",
                "placeholder": "Describe tu negocio, servicios, especialidades...",
                "required": True,
            },
            "business_info.greeting": {
                "label": "Saludo de Bienvenida",
                "type": "textarea",
                "placeholder": "¡Hola! Bienvenido/a a [NOMBRE_NEGOCIO]...",
                "required": True,
            },
            "client_objectives.primary_goal": {
                "label": "Objetivo Principal con Clientes",
                "type": "textarea",
                "placeholder": "Ej: Generar ventas, agendar citas, brindar soporte...",
                "required": True,
            },
            "business_info.services": {
                "label": "Servicios/Productos Principales",
                "type": "list",
                "placeholder": "Agrega tus servicios principales...",
                "required": False,
            },
            "ai_behavior.personality_traits": {
                "label": "Personalidad de la IA",
                "type": "list",
                "placeholder": "Ej: Profesional, Amigable, Directo...",
                "required": False,
            },
            "business_info.hours": {
                "label": "Horarios de Atención",
                "type": "text",
                "placeholder": "Ej: Lunes a Viernes 9:00 AM - 6:00 PM",
                "required": False,
            },
            "business_info.contact_info": {
                "label": "Información de Contacto",
                "type": "text",
                "placeholder": "Email, teléfono, dirección...",
                "required": False,
            },
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
