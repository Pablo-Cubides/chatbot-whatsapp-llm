"""
🧪 Sistema de A/B Testing
Permite experimentar con diferentes configuraciones y medir resultados
"""

import asyncio
import logging
import json
import random
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import os

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Estado del experimento"""
    DRAFT = "draft"              # Borrador, no iniciado
    RUNNING = "running"          # En ejecución
    PAUSED = "paused"            # Pausado
    COMPLETED = "completed"      # Completado
    CANCELLED = "cancelled"      # Cancelado


class VariantType(Enum):
    """Tipo de variante en experimento"""
    PROMPT = "prompt"                    # Diferentes prompts
    MODEL = "model"                      # Diferentes modelos LLM
    TEMPERATURE = "temperature"          # Diferentes temperaturas
    MAX_TOKENS = "max_tokens"            # Diferentes límites de tokens
    RESPONSE_STYLE = "response_style"    # Diferentes estilos de respuesta
    TIMING = "timing"                    # Diferentes delays/timing
    MIXED = "mixed"                      # Combinación de varios


@dataclass
class Variant:
    """Variante de un experimento A/B"""
    id: str
    name: str
    description: str
    config: Dict[str, Any]
    traffic_percentage: float  # 0-100
    
    # Métricas
    total_conversations: int = 0
    successful_conversations: int = 0
    avg_response_time: float = 0.0
    avg_satisfaction_score: float = 0.0
    bot_suspicions: int = 0
    objectives_achieved: int = 0


@dataclass
class ABExperiment:
    """Experimento A/B completo"""
    id: str
    name: str
    description: str
    variant_type: VariantType
    status: ExperimentStatus
    
    variants: List[Variant]
    
    # Configuración
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    
    min_sample_size: int  # Mínimo de conversaciones por variante
    confidence_level: float  # Nivel de confianza (ej: 0.95)
    
    # Criterio de éxito
    success_metric: str  # "satisfaction", "objectives", "quality", etc.
    
    # Estado
    total_participants: int = 0
    winner_variant_id: Optional[str] = None
    is_statistically_significant: bool = False


class ABTestManager:
    """Gestor de experimentos A/B"""
    
    def __init__(self, analytics_manager=None, deep_analyzer=None):
        self.analytics = analytics_manager
        self.deep_analyzer = deep_analyzer
        
        # Experimentos activos
        self.experiments: Dict[str, ABExperiment] = {}
        
        # Asignaciones de usuarios a variantes
        self.user_assignments: Dict[str, Dict[str, str]] = {}  # {contact: {experiment_id: variant_id}}
        
        # Configuración
        self.enabled = os.getenv("AB_TESTING_ENABLED", "true").lower() == "true"
        self.default_min_sample_size = int(os.getenv("AB_TEST_MIN_SAMPLE_SIZE", "30"))
        self.default_confidence_level = float(os.getenv("AB_TEST_CONFIDENCE_LEVEL", "0.95"))
        
        logger.info("🧪 ABTestManager inicializado")
    
    def create_experiment(
        self,
        name: str,
        description: str,
        variant_type: VariantType,
        variants: List[Dict[str, Any]],
        success_metric: str = "satisfaction",
        min_sample_size: Optional[int] = None,
        confidence_level: Optional[float] = None
    ) -> ABExperiment:
        """
        Crea un nuevo experimento A/B
        
        Args:
            name: Nombre del experimento
            description: Descripción
            variant_type: Tipo de variante
            variants: Lista de configuraciones de variantes
            success_metric: Métrica principal de éxito
            min_sample_size: Tamaño mínimo de muestra
            confidence_level: Nivel de confianza estadística
        """
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Crear variantes
        variant_objects = []
        for i, var_config in enumerate(variants):
            variant = Variant(
                id=f"{experiment_id}_var_{i}",
                name=var_config.get('name', f'Variant {chr(65+i)}'),  # A, B, C...
                description=var_config.get('description', ''),
                config=var_config.get('config', {}),
                traffic_percentage=var_config.get('traffic_percentage', 100 / len(variants))
            )
            variant_objects.append(variant)
        
        # Normalizar porcentajes de tráfico
        total_traffic = sum(v.traffic_percentage for v in variant_objects)
        if total_traffic != 100:
            logger.warning(f"⚠️ Tráfico total es {total_traffic}%, normalizando a 100%")
            for variant in variant_objects:
                variant.traffic_percentage = (variant.traffic_percentage / total_traffic) * 100
        
        experiment = ABExperiment(
            id=experiment_id,
            name=name,
            description=description,
            variant_type=variant_type,
            status=ExperimentStatus.DRAFT,
            variants=variant_objects,
            created_at=datetime.now(),
            started_at=None,
            ended_at=None,
            min_sample_size=min_sample_size or self.default_min_sample_size,
            confidence_level=confidence_level or self.default_confidence_level,
            success_metric=success_metric
        )
        
        self.experiments[experiment_id] = experiment
        
        logger.info(f"🧪 Experimento creado: {name} ({experiment_id})")
        logger.info(f"  Variantes: {len(variant_objects)}")
        logger.info(f"  Métrica de éxito: {success_metric}")
        
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Inicia un experimento"""
        if experiment_id not in self.experiments:
            logger.error(f"❌ Experimento {experiment_id} no encontrado")
            return False
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status == ExperimentStatus.RUNNING:
            logger.warning(f"⚠️ Experimento {experiment_id} ya está corriendo")
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()
        
        logger.info(f"🚀 Experimento iniciado: {experiment.name}")
        return True
    
    def pause_experiment(self, experiment_id: str) -> bool:
        """Pausa un experimento"""
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.PAUSED
        
        logger.info(f"⏸️ Experimento pausado: {experiment.name}")
        return True
    
    def end_experiment(self, experiment_id: str) -> bool:
        """Termina un experimento"""
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now()
        
        # Calcular ganador
        winner = self._calculate_winner(experiment)
        if winner:
            experiment.winner_variant_id = winner.id
            logger.info(f"🏆 Ganador: {winner.name}")
        
        logger.info(f"✅ Experimento completado: {experiment.name}")
        return True
    
    def assign_variant(self, contact: str, experiment_id: str) -> Optional[Variant]:
        """
        Asigna una variante a un usuario para un experimento
        Usa asignación consistente (mismo usuario siempre misma variante)
        """
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Verificar si ya tiene asignación
        if contact in self.user_assignments:
            if experiment_id in self.user_assignments[contact]:
                variant_id = self.user_assignments[contact][experiment_id]
                return next((v for v in experiment.variants if v.id == variant_id), None)
        
        # Nueva asignación basada en porcentajes de tráfico
        rand = random.random() * 100
        cumulative = 0
        
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if rand <= cumulative:
                # Asignar esta variante
                if contact not in self.user_assignments:
                    self.user_assignments[contact] = {}
                
                self.user_assignments[contact][experiment_id] = variant.id
                experiment.total_participants += 1
                
                logger.debug(f"👤 {contact} asignado a {variant.name} en {experiment.name}")
                return variant
        
        # Fallback (no debería llegar aquí)
        return experiment.variants[0]
    
    def record_conversation_result(
        self,
        contact: str,
        experiment_id: str,
        success: bool,
        response_time: float,
        satisfaction_score: float,
        bot_suspicion: bool,
        objective_achieved: bool
    ):
        """Registra resultado de conversación en experimento"""
        if experiment_id not in self.experiments:
            return
        
        experiment = self.experiments[experiment_id]
        
        # Obtener variante del usuario
        if contact not in self.user_assignments:
            return
        if experiment_id not in self.user_assignments[contact]:
            return
        
        variant_id = self.user_assignments[contact][experiment_id]
        variant = next((v for v in experiment.variants if v.id == variant_id), None)
        
        if not variant:
            return
        
        # Actualizar métricas
        variant.total_conversations += 1
        if success:
            variant.successful_conversations += 1
        
        # Promedios móviles
        n = variant.total_conversations
        variant.avg_response_time = (variant.avg_response_time * (n-1) + response_time) / n
        variant.avg_satisfaction_score = (variant.avg_satisfaction_score * (n-1) + satisfaction_score) / n
        
        if bot_suspicion:
            variant.bot_suspicions += 1
        
        if objective_achieved:
            variant.objectives_achieved += 1
        
        # Verificar si es momento de calcular significancia
        if self._should_calculate_significance(experiment):
            self._calculate_statistical_significance(experiment)
    
    def _should_calculate_significance(self, experiment: ABExperiment) -> bool:
        """Determina si hay suficientes datos para calcular significancia"""
        min_reached = all(
            v.total_conversations >= experiment.min_sample_size
            for v in experiment.variants
        )
        return min_reached
    
    def _calculate_statistical_significance(self, experiment: ABExperiment):
        """
        Calcula significancia estadística (simplified chi-square test)
        Determina si las diferencias son significativas
        """
        try:
            # Obtener métricas según success_metric
            if experiment.success_metric == "satisfaction":
                scores = [v.avg_satisfaction_score for v in experiment.variants]
            elif experiment.success_metric == "objectives":
                scores = [
                    (v.objectives_achieved / v.total_conversations * 100) if v.total_conversations > 0 else 0
                    for v in experiment.variants
                ]
            elif experiment.success_metric == "quality":
                scores = [
                    (v.successful_conversations / v.total_conversations * 100) if v.total_conversations > 0 else 0
                    for v in experiment.variants
                ]
            else:
                scores = [v.avg_satisfaction_score for v in experiment.variants]
            
            # Calcular diferencia entre mejor y segundo mejor
            sorted_scores = sorted(scores, reverse=True)
            if len(sorted_scores) < 2:
                return
            
            diff_percentage = ((sorted_scores[0] - sorted_scores[1]) / sorted_scores[1]) * 100 if sorted_scores[1] > 0 else 0
            
            # Simplified: si diferencia > 10% y suficientes muestras, es significativo
            # En producción usar scipy.stats.chi2_contingency o similar
            if diff_percentage > 10:
                experiment.is_statistically_significant = True
                logger.info(f"📊 Experimento {experiment.name} tiene diferencia significativa: {diff_percentage:.1f}%")
        
        except Exception as e:
            logger.error(f"❌ Error calculando significancia: {e}")
    
    def _calculate_winner(self, experiment: ABExperiment) -> Optional[Variant]:
        """Calcula la variante ganadora"""
        if not experiment.variants:
            return None
        
        # Ordenar por métrica de éxito
        if experiment.success_metric == "satisfaction":
            sorted_variants = sorted(
                experiment.variants,
                key=lambda v: v.avg_satisfaction_score,
                reverse=True
            )
        elif experiment.success_metric == "objectives":
            sorted_variants = sorted(
                experiment.variants,
                key=lambda v: v.objectives_achieved / v.total_conversations if v.total_conversations > 0 else 0,
                reverse=True
            )
        elif experiment.success_metric == "quality":
            sorted_variants = sorted(
                experiment.variants,
                key=lambda v: v.successful_conversations / v.total_conversations if v.total_conversations > 0 else 0,
                reverse=True
            )
        else:
            sorted_variants = sorted(
                experiment.variants,
                key=lambda v: v.avg_satisfaction_score,
                reverse=True
            )
        
        return sorted_variants[0] if sorted_variants else None
    
    def get_experiment_report(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Genera reporte detallado de experimento"""
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        # Calcular ganador actual
        current_winner = self._calculate_winner(experiment)
        
        # Estadísticas por variante
        variants_stats = []
        for variant in experiment.variants:
            success_rate = (variant.successful_conversations / variant.total_conversations * 100) if variant.total_conversations > 0 else 0
            objective_rate = (variant.objectives_achieved / variant.total_conversations * 100) if variant.total_conversations > 0 else 0
            suspicion_rate = (variant.bot_suspicions / variant.total_conversations * 100) if variant.total_conversations > 0 else 0
            
            variants_stats.append({
                "id": variant.id,
                "name": variant.name,
                "total_conversations": variant.total_conversations,
                "success_rate": round(success_rate, 2),
                "objective_rate": round(objective_rate, 2),
                "avg_satisfaction": round(variant.avg_satisfaction_score, 2),
                "avg_response_time": round(variant.avg_response_time, 2),
                "suspicion_rate": round(suspicion_rate, 2),
                "is_current_winner": variant.id == (current_winner.id if current_winner else None)
            })
        
        duration = None
        if experiment.started_at:
            end_time = experiment.ended_at or datetime.now()
            duration = (end_time - experiment.started_at).total_seconds() / 3600  # horas
        
        return {
            "experiment": {
                "id": experiment.id,
                "name": experiment.name,
                "description": experiment.description,
                "status": experiment.status.value,
                "variant_type": experiment.variant_type.value,
                "success_metric": experiment.success_metric,
                "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
                "ended_at": experiment.ended_at.isoformat() if experiment.ended_at else None,
                "duration_hours": round(duration, 2) if duration else None,
                "total_participants": experiment.total_participants,
                "is_statistically_significant": experiment.is_statistically_significant,
                "winner_variant_id": experiment.winner_variant_id
            },
            "variants": variants_stats,
            "recommendation": self._get_recommendation(experiment, current_winner)
        }
    
    def _get_recommendation(
        self,
        experiment: ABExperiment,
        current_winner: Optional[Variant]
    ) -> str:
        """Genera recomendación basada en resultados"""
        if not current_winner:
            return "Insuficientes datos para recomendar"
        
        if experiment.status != ExperimentStatus.COMPLETED:
            if experiment.is_statistically_significant:
                return f"Recomendado: Implementar '{current_winner.name}' (diferencia significativa detectada)"
            else:
                return "Continuar experimento - diferencias no son significativas aún"
        else:
            if experiment.is_statistically_significant:
                return f"✅ IMPLEMENTAR: '{current_winner.name}' ganó con significancia estadística"
            else:
                return f"⚠️ '{current_winner.name}' lideró pero sin significancia estadística - considerar mantener actual"
    
    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas generales de A/B testing"""
        active_experiments = [e for e in self.experiments.values() if e.status == ExperimentStatus.RUNNING]
        completed_experiments = [e for e in self.experiments.values() if e.status == ExperimentStatus.COMPLETED]
        
        return {
            "enabled": self.enabled,
            "total_experiments": len(self.experiments),
            "active_experiments": len(active_experiments),
            "completed_experiments": len(completed_experiments),
            "total_participants": sum(e.total_participants for e in self.experiments.values()),
            "experiments_with_significance": sum(
                1 for e in self.experiments.values() if e.is_statistically_significant
            )
        }


# Instancia global
ab_test_manager = ABTestManager()
