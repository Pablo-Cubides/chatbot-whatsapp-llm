"""
🔬 Sistema de Análisis Profundo - 3ra Capa
Analiza conversaciones periódicamente para detectar patrones, emociones y cumplimiento de objetivos
SE EJECUTA SOLO PERIÓDICAMENTE (cada 50 conversaciones o semanalmente) para ahorrar recursos
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EmotionType(Enum):
    """Emociones detectadas en conversaciones"""

    SATISFIED = "satisfied"  # Cliente satisfecho
    FRUSTRATED = "frustrated"  # Cliente frustrado
    CONFUSED = "confused"  # Cliente confundido
    ANGRY = "angry"  # Cliente enojado
    EXCITED = "excited"  # Cliente emocionado
    NEUTRAL = "neutral"  # Cliente neutral
    SUSPICIOUS = "suspicious"  # Cliente sospecha que es bot
    IMPATIENT = "impatient"  # Cliente impaciente


class ObjectiveStatus(Enum):
    """Estado de cumplimiento de objetivo"""

    ACHIEVED = "achieved"  # Objetivo logrado
    FAILED = "failed"  # Objetivo no logrado
    PARTIAL = "partial"  # Objetivo parcialmente logrado
    ABANDONED = "abandoned"  # Cliente abandonó
    IN_PROGRESS = "in_progress"  # Aún en progreso


@dataclass
class ConversationAnalysis:
    """Resultado de análisis profundo de conversación"""

    session_id: str
    contact: str
    analyzed_at: datetime

    # Análisis de emoción
    primary_emotion: EmotionType
    emotion_confidence: float  # 0-1
    emotion_timeline: list[dict[str, Any]]  # Cómo cambió la emoción

    # Detección de sospecha de bot
    bot_suspicion_detected: bool
    bot_suspicion_indicators: list[str]
    bot_suspicion_severity: float  # 0-1

    # Análisis de objetivo
    objective_status: ObjectiveStatus
    objective_name: Optional[str]
    objective_achieved_at: Optional[datetime]
    success_factors: list[str]
    failure_factors: list[str]

    # Calidad de conversación
    conversation_quality_score: float  # 0-100
    response_naturalness_score: float  # 0-100
    customer_satisfaction_score: float  # 0-100

    # Insights y recomendaciones
    insights: list[str]
    recommended_actions: list[str]
    warnings: list[str]


class DeepAnalyzer:
    """Analizador profundo de conversaciones usando LLM"""

    def __init__(self, multi_llm=None, analytics_manager=None):
        self.multi_llm = multi_llm
        self.analytics = analytics_manager

        # Configuración
        self.enabled = os.getenv("DEEP_ANALYSIS_ENABLED", "true").lower() == "true"
        self.trigger_every_n_conversations = int(os.getenv("DEEP_ANALYSIS_TRIGGER_CONVERSATIONS", "50"))
        self.trigger_every_n_days = int(os.getenv("DEEP_ANALYSIS_TRIGGER_DAYS", "7"))

        # Estado
        self.conversations_since_last_analysis = 0
        self.last_analysis_date = None
        self.analysis_history = []

        logger.info("🔬 DeepAnalyzer inicializado")
        logger.info(f"  Trigger cada {self.trigger_every_n_conversations} conversaciones")
        logger.info(f"  Trigger cada {self.trigger_every_n_days} días")

    def should_trigger_analysis(self) -> bool:
        """Determina si es momento de ejecutar análisis profundo"""
        if not self.enabled:
            return False

        # Trigger por cantidad de conversaciones
        if self.conversations_since_last_analysis >= self.trigger_every_n_conversations:
            logger.info(f"🔬 Trigger: {self.conversations_since_last_analysis} conversaciones")
            return True

        # Trigger por tiempo
        if self.last_analysis_date:
            days_since = (datetime.now() - self.last_analysis_date).days
            if days_since >= self.trigger_every_n_days:
                logger.info(f"🔬 Trigger: {days_since} días desde último análisis")
                return True

        return False

    def record_conversation_end(self):
        """Registra que una conversación terminó"""
        self.conversations_since_last_analysis += 1

    async def analyze_conversation(
        self, session_id: str, contact: str, messages: list[dict[str, Any]], business_objectives: Optional[list[str]] = None
    ) -> ConversationAnalysis:
        """
        Analiza una conversación completa en profundidad
        SE LLAMA SOLO CUANDO ES NECESARIO, no en cada mensaje
        """
        try:
            logger.info(f"🔬 Analizando conversación: {session_id}")

            # Construir contexto para el LLM
            conversation_text = self._format_conversation(messages)
            analysis_prompt = self._build_analysis_prompt(conversation_text, business_objectives)

            # Usar LLM para análisis (preferir modelos de razonamiento)
            if self.multi_llm:
                response = await self.multi_llm.generate_response(
                    messages=[{"role": "user", "content": analysis_prompt}],
                    prefer_reasoning=True,  # xAI Grok, o1-preview, etc.
                )

                if response["success"]:
                    analysis_data = self._parse_llm_analysis(response["message"])
                else:
                    logger.error(f"❌ Error en análisis LLM: {response.get('error')}")
                    analysis_data = self._create_fallback_analysis()
            else:
                analysis_data = self._create_fallback_analysis()

            # Crear objeto de análisis
            analysis = ConversationAnalysis(
                session_id=session_id, contact=contact, analyzed_at=datetime.now(), **analysis_data
            )

            # Guardar análisis
            self.analysis_history.append(analysis)

            # Registrar en analytics si está disponible
            if self.analytics:
                self._save_to_analytics(analysis)

            logger.info(
                f"✅ Análisis completado: {analysis.primary_emotion.value}, calidad={analysis.conversation_quality_score:.1f}"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Error en análisis profundo: {e}")
            return self._create_error_analysis(session_id, contact, str(e))

    async def analyze_batch(
        self, conversations: list[dict[str, Any]], business_objectives: Optional[list[str]] = None
    ) -> list[ConversationAnalysis]:
        """
        Analiza múltiples conversaciones en batch
        Usa cuando se triggerea el análisis periódico
        """
        logger.info(f"🔬 Analizando batch de {len(conversations)} conversaciones")

        results = []
        for conv in conversations:
            analysis = await self.analyze_conversation(
                session_id=conv.get("session_id"),
                contact=conv.get("contact"),
                messages=conv.get("messages", []),
                business_objectives=business_objectives,
            )
            results.append(analysis)

            # Pequeña pausa para no saturar API
            await asyncio.sleep(0.5)

        # Resetear contador
        self.conversations_since_last_analysis = 0
        self.last_analysis_date = datetime.now()

        # Generar reporte agregado
        aggregate_report = self._generate_aggregate_report(results)
        logger.info(f"📊 Reporte agregado: {json.dumps(aggregate_report, indent=2)}")

        return results

    def _format_conversation(self, messages: list[dict[str, Any]]) -> str:
        """Formatea conversación para análisis"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            msg.get("timestamp", "")

            prefix = "Cliente:" if role == "user" else "Asistente:"
            lines.append(f"{prefix} {content}")

        return "\n".join(lines)

    def _build_analysis_prompt(self, conversation: str, business_objectives: Optional[list[str]]) -> str:
        """Construye prompt para análisis profundo"""

        objectives_text = ""
        if business_objectives:
            objectives_text = "\n".join([f"- {obj}" for obj in business_objectives])
            objectives_section = f"""
OBJETIVOS DE NEGOCIO:
{objectives_text}
"""
        else:
            objectives_section = ""

        prompt = f"""Eres un analista experto en conversaciones de atención al cliente. Analiza la siguiente conversación EN PROFUNDIDAD.

CONVERSACIÓN:
{conversation}
{objectives_section}

Tu análisis debe incluir (responde en formato JSON):

1. **Análisis de Emoción:**
   - primary_emotion: (satisfied/frustrated/confused/angry/excited/neutral/suspicious/impatient)
   - emotion_confidence: (0.0-1.0)
   - emotion_timeline: lista de {{message_index, emotion, trigger}} mostrando cómo cambió

2. **Detección de Sospecha de Bot:**
   - bot_suspicion_detected: (true/false)
   - bot_suspicion_indicators: lista de frases o patrones que indican sospecha
   - bot_suspicion_severity: (0.0-1.0) qué tan seguro está el cliente de que es bot

3. **Análisis de Objetivo:**
   - objective_status: (achieved/failed/partial/abandoned/in_progress)
   - objective_name: nombre del objetivo detectado o null
   - success_factors: lista de factores que contribuyeron al éxito
   - failure_factors: lista de factores que causaron fallo

4. **Calidad de Conversación:**
   - conversation_quality_score: (0-100) calidad general
   - response_naturalness_score: (0-100) qué tan naturales son las respuestas
   - customer_satisfaction_score: (0-100) satisfacción estimada del cliente

5. **Insights y Recomendaciones:**
   - insights: lista de insights importantes (3-5 puntos)
   - recommended_actions: acciones específicas a tomar (3-5 puntos)
   - warnings: advertencias críticas si las hay

IMPORTANTE:
- Sé específico y honesto
- Si detectas que el bot se reveló, márcalo con alta severidad
- Si el objetivo no se cumplió, identifica por qué
- Las recomendaciones deben ser ACCIONABLES

Responde SOLO con JSON válido, sin explicaciones adicionales."""

        return prompt

    def _parse_llm_analysis(self, llm_response: str) -> dict[str, Any]:
        """Parsea respuesta del LLM a formato estructurado"""
        try:
            # Intentar parsear como JSON
            # Limpiar respuesta (a veces el LLM agrega markdown)
            clean_response = llm_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            data = json.loads(clean_response)

            # Convertir enums
            data["primary_emotion"] = EmotionType(data.get("primary_emotion", "neutral"))
            data["objective_status"] = ObjectiveStatus(data.get("objective_status", "in_progress"))

            # Parsear fecha si existe
            if data.get("objective_achieved_at"):
                data["objective_achieved_at"] = datetime.fromisoformat(data["objective_achieved_at"])

            return data

        except Exception as e:
            logger.error(f"❌ Error parseando análisis LLM: {e}")
            logger.debug(f"Respuesta LLM: {llm_response[:500]}...")
            return self._create_fallback_analysis()

    def _create_fallback_analysis(self) -> dict[str, Any]:
        """Crea análisis básico cuando LLM falla"""
        return {
            "primary_emotion": EmotionType.NEUTRAL,
            "emotion_confidence": 0.5,
            "emotion_timeline": [],
            "bot_suspicion_detected": False,
            "bot_suspicion_indicators": [],
            "bot_suspicion_severity": 0.0,
            "objective_status": ObjectiveStatus.IN_PROGRESS,
            "objective_name": None,
            "objective_achieved_at": None,
            "success_factors": [],
            "failure_factors": ["Análisis automático no disponible"],
            "conversation_quality_score": 50.0,
            "response_naturalness_score": 50.0,
            "customer_satisfaction_score": 50.0,
            "insights": ["Análisis manual requerido"],
            "recommended_actions": ["Revisar conversación manualmente"],
            "warnings": ["Sistema de análisis automático no disponible"],
        }

    def _create_error_analysis(self, session_id: str, contact: str, error: str) -> ConversationAnalysis:
        """Crea análisis de error"""
        return ConversationAnalysis(
            session_id=session_id,
            contact=contact,
            analyzed_at=datetime.now(),
            primary_emotion=EmotionType.NEUTRAL,
            emotion_confidence=0.0,
            emotion_timeline=[],
            bot_suspicion_detected=False,
            bot_suspicion_indicators=[],
            bot_suspicion_severity=0.0,
            objective_status=ObjectiveStatus.IN_PROGRESS,
            objective_name=None,
            objective_achieved_at=None,
            success_factors=[],
            failure_factors=[f"Error en análisis: {error}"],
            conversation_quality_score=0.0,
            response_naturalness_score=0.0,
            customer_satisfaction_score=0.0,
            insights=[],
            recommended_actions=["Revisar error en logs"],
            warnings=[f"Error crítico: {error}"],
        )

    def _save_to_analytics(self, analysis: ConversationAnalysis):
        """Guarda análisis en sistema de analytics"""
        try:
            # Aquí se guardaría en base de datos o analytics
            # Por ahora solo log
            logger.info(f"💾 Guardando análisis de {analysis.session_id}")
        except Exception as e:
            logger.error(f"❌ Error guardando análisis: {e}")

    def _generate_aggregate_report(self, analyses: list[ConversationAnalysis]) -> dict[str, Any]:
        """Genera reporte agregado de múltiples análisis"""
        if not analyses:
            return {}

        # Estadísticas de emociones
        emotion_counts = {}
        for analysis in analyses:
            emotion = analysis.primary_emotion.value
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # Estadísticas de objetivos
        objective_counts = {}
        for analysis in analyses:
            status = analysis.objective_status.value
            objective_counts[status] = objective_counts.get(status, 0) + 1

        # Detección de sospechas de bot
        bot_suspicions = sum(1 for a in analyses if a.bot_suspicion_detected)

        # Promedios de calidad
        avg_quality = sum(a.conversation_quality_score for a in analyses) / len(analyses)
        avg_naturalness = sum(a.response_naturalness_score for a in analyses) / len(analyses)
        avg_satisfaction = sum(a.customer_satisfaction_score for a in analyses) / len(analyses)

        # Advertencias críticas
        all_warnings = []
        for analysis in analyses:
            all_warnings.extend(analysis.warnings)

        # Insights más comunes
        all_insights = []
        for analysis in analyses:
            all_insights.extend(analysis.insights)

        return {
            "total_conversations": len(analyses),
            "analyzed_at": datetime.now().isoformat(),
            "emotions": emotion_counts,
            "objectives": objective_counts,
            "bot_suspicions": {"total": bot_suspicions, "percentage": (bot_suspicions / len(analyses)) * 100},
            "quality_metrics": {
                "avg_conversation_quality": round(avg_quality, 2),
                "avg_response_naturalness": round(avg_naturalness, 2),
                "avg_customer_satisfaction": round(avg_satisfaction, 2),
            },
            "critical_warnings": list(set(all_warnings)),
            "top_insights": list(set(all_insights))[:10],
        }

    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del analizador"""
        return {
            "enabled": self.enabled,
            "conversations_since_last_analysis": self.conversations_since_last_analysis,
            "last_analysis_date": self.last_analysis_date.isoformat() if self.last_analysis_date else None,
            "total_analyses": len(self.analysis_history),
            "trigger_conversations": self.trigger_every_n_conversations,
            "trigger_days": self.trigger_every_n_days,
            "should_trigger": self.should_trigger_analysis(),
        }


# Instancia global
deep_analyzer = DeepAnalyzer()
