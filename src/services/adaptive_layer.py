"""
🧠 Capa 3 Adaptativa
Orquesta análisis profundo periódico y experimentación A/B para mejorar estrategia automáticamente.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.services.ab_test_manager import ABExperiment, ExperimentStatus, VariantType, ab_test_manager
from src.services.deep_analyzer import ObjectiveStatus, deep_analyzer

logger = logging.getLogger(__name__)


class AdaptiveLayerManager:
    """Orquestador de la capa adaptativa (análisis + experimentación)."""

    def __init__(self, deep_analyzer_instance=None, ab_manager=None, business_config_manager=None, analytics_manager=None):
        self.deep_analyzer = deep_analyzer_instance or deep_analyzer
        self.ab_manager = ab_manager or ab_test_manager
        self.business_config = business_config_manager
        self.analytics = analytics_manager

        self.auto_create_experiment = os.getenv("ADAPTIVE_AUTO_EXPERIMENT", "true").lower() == "true"
        self.default_batch_limit = int(os.getenv("ADAPTIVE_BATCH_LIMIT", "25"))
        self._analysis_in_progress = False

        self.last_run_at: Optional[datetime] = None
        self.last_run_summary: dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.total_runs = 0

    def sync_runtime_settings(self):
        """Sincroniza runtime con business_config.analysis_settings."""
        if not self.business_config:
            return

        settings = self.business_config.config.get("analysis_settings", {})
        enabled = bool(settings.get("deep_analysis_enabled", True))
        trigger_conversations = int(settings.get("deep_analysis_trigger_conversations", 50) or 50)
        trigger_days = int(settings.get("deep_analysis_trigger_days", 7) or 7)

        self.deep_analyzer.enabled = enabled
        self.deep_analyzer.trigger_every_n_conversations = max(1, trigger_conversations)
        self.deep_analyzer.trigger_every_n_days = max(1, trigger_days)

    def _get_active_experiment(self) -> Optional[ABExperiment]:
        running = [e for e in self.ab_manager.experiments.values() if e.status == ExperimentStatus.RUNNING]
        if running:
            return running[0]
        return None

    def ensure_default_experiment(self) -> Optional[ABExperiment]:
        """Crea un experimento base si no hay uno activo."""
        if not self.ab_manager.enabled or not self.auto_create_experiment:
            return None

        existing = self._get_active_experiment()
        if existing:
            return existing

        experiment = self.ab_manager.create_experiment(
            name="Adaptive Style Optimization",
            description="Optimiza estilo de respuesta para maximizar objetivo y naturalidad",
            variant_type=VariantType.MIXED,
            variants=[
                {
                    "name": "Concise Professional",
                    "description": "Respuestas más cortas y directas",
                    "traffic_percentage": 50,
                    "config": {"temperature": 0.65, "max_tokens": 130, "style": "concise"},
                },
                {
                    "name": "Empathic Conversational",
                    "description": "Respuestas con mayor empatía y contexto",
                    "traffic_percentage": 50,
                    "config": {"temperature": 0.8, "max_tokens": 190, "style": "empathetic"},
                },
            ],
            success_metric="objectives",
        )
        self.ab_manager.start_experiment(experiment.id)
        logger.info(f"🧪 Experimento adaptativo iniciado: {experiment.id}")
        return experiment

    def register_interaction(self, chat_id: str):
        """Registra una interacción y garantiza asignación de variante."""
        self.sync_runtime_settings()

        experiment = self.ensure_default_experiment()
        if experiment:
            self.ab_manager.assign_variant(chat_id, experiment.id)

        self.deep_analyzer.record_conversation_end()

    def _variant_by_id(self, experiment: ABExperiment, variant_id: str) -> Optional[dict[str, Any]]:
        variant = next((v for v in experiment.variants if v.id == variant_id), None)
        if not variant:
            return None
        return {
            "id": variant.id,
            "name": variant.name,
            "config": dict(variant.config or {}),
        }

    def get_runtime_overrides(self, chat_id: Optional[str] = None) -> dict[str, Any]:
        """Obtiene configuración efectiva (ganador global o variante por chat)."""
        experiment = self._get_active_experiment()
        if not experiment:
            return {}

        # Si ya hay ganador significativo, aplicar como global
        if experiment.is_statistically_significant and experiment.winner_variant_id:
            winner = self._variant_by_id(experiment, experiment.winner_variant_id)
            if winner:
                return {
                    "source": "winner",
                    "experiment_id": experiment.id,
                    "variant_id": winner["id"],
                    "variant_name": winner["name"],
                    **winner["config"],
                }

        # En caso contrario, usar variante asignada para el chat
        if chat_id:
            assigned = self.ab_manager.assign_variant(chat_id, experiment.id)
            if assigned:
                return {
                    "source": "assignment",
                    "experiment_id": experiment.id,
                    "variant_id": assigned.id,
                    "variant_name": assigned.name,
                    **dict(assigned.config or {}),
                }

        return {}

    def apply_runtime_overrides(self, overrides: dict[str, Any], project_root: str):
        """Aplica overrides a configuración runtime (settings.json + business_config)."""
        if not overrides:
            return

        root = Path(project_root)
        settings_path = root / "data" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        current: dict[str, Any] = {}
        if settings_path.exists():
            try:
                current = json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                current = {}

        changed = False
        for key in ("temperature", "max_tokens"):
            if key in overrides and overrides.get(key) is not None:
                value = overrides.get(key)
                if current.get(key) != value:
                    current[key] = value
                    changed = True

        style = overrides.get("style")
        if style and current.get("adaptive_style") != style:
            current["adaptive_style"] = style
            changed = True

        if changed:
            settings_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

        if self.business_config:
            adaptive_cfg = self.business_config.config.get("adaptive_layer", {})
            adaptive_cfg["active_overrides"] = {
                "source": overrides.get("source"),
                "variant_id": overrides.get("variant_id"),
                "variant_name": overrides.get("variant_name"),
                "temperature": overrides.get("temperature"),
                "max_tokens": overrides.get("max_tokens"),
                "style": overrides.get("style"),
                "updated_at": datetime.now().isoformat(),
            }
            self.business_config.config["adaptive_layer"] = adaptive_cfg
            self.business_config.save_config(self.business_config.config)

    def should_run_now(self) -> bool:
        return (not self._analysis_in_progress) and self.deep_analyzer.should_trigger_analysis()

    async def run_analysis(self, conversations: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
        """Ejecuta ciclo adaptativo completo sobre un batch de conversaciones."""
        if self._analysis_in_progress:
            return {"success": False, "message": "Análisis adaptativo ya en ejecución"}

        if not force and not self.deep_analyzer.should_trigger_analysis():
            return {"success": False, "message": "Trigger adaptativo no cumplido"}

        if not conversations:
            return {"success": False, "message": "No hay conversaciones para analizar"}

        self._analysis_in_progress = True
        self.last_error = None

        try:
            business_objectives = []
            if self.business_config:
                primary_goal = self.business_config.config.get("client_objectives", {}).get("primary_goal")
                if primary_goal:
                    business_objectives.append(primary_goal)

            analyses = await self.deep_analyzer.analyze_batch(
                conversations=conversations,
                business_objectives=business_objectives or None,
            )

            summary = self._summarize_results(analyses)
            self._update_ab_metrics(analyses)
            self._promote_winner_if_ready()
            self._persist_adaptive_snapshot(summary)

            self.last_run_at = datetime.now()
            self.last_run_summary = summary
            self.total_runs += 1

            if self.analytics:
                self.analytics.record_metric("adaptive_cycle_success", 1, summary)

            return {
                "success": True,
                "message": "Ciclo adaptativo ejecutado",
                "summary": summary,
            }

        except Exception as exc:
            self.last_error = str(exc)
            logger.error(f"❌ Error en capa adaptativa: {exc}")
            if self.analytics:
                self.analytics.record_metric("adaptive_cycle_error", 1, {"error": str(exc)})
            return {"success": False, "message": str(exc)}
        finally:
            self._analysis_in_progress = False

    async def run_adaptive_cycle(self, conversations: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
        """Alias explícito del ciclo adaptativo para uso async desde routers."""
        return await self.run_analysis(conversations=conversations, force=force)

    def run_analysis_sync(self, conversations: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
        """API desaconsejada: usar siempre `await run_adaptive_cycle(...)`.

        Se mantiene por compatibilidad, pero evita ejecutar event loops anidados.
        """
        raise RuntimeError(
            "run_analysis_sync() está deshabilitado para evitar mal uso de asyncio. "
            "Usa await run_adaptive_cycle(...)."
        )

    def _summarize_results(self, analyses: list[Any]) -> dict[str, Any]:
        total = len(analyses)
        if total == 0:
            return {"total_conversations": 0}

        achieved = sum(1 for a in analyses if a.objective_status == ObjectiveStatus.ACHIEVED)
        partial = sum(1 for a in analyses if a.objective_status == ObjectiveStatus.PARTIAL)
        bot_suspicions = sum(1 for a in analyses if a.bot_suspicion_detected)

        avg_quality = sum(a.conversation_quality_score for a in analyses) / total
        avg_naturalness = sum(a.response_naturalness_score for a in analyses) / total
        avg_satisfaction = sum(a.customer_satisfaction_score for a in analyses) / total

        return {
            "total_conversations": total,
            "objective_achieved_rate": round((achieved / total) * 100, 2),
            "objective_partial_rate": round((partial / total) * 100, 2),
            "bot_suspicion_rate": round((bot_suspicions / total) * 100, 2),
            "avg_quality": round(avg_quality, 2),
            "avg_naturalness": round(avg_naturalness, 2),
            "avg_satisfaction": round(avg_satisfaction, 2),
            "ran_at": datetime.now().isoformat(),
        }

    def _update_ab_metrics(self, analyses: list[Any]):
        experiment = self._get_active_experiment()
        if not experiment:
            return

        for analysis in analyses:
            contact = analysis.contact
            if not contact:
                continue

            objective_achieved = analysis.objective_status == ObjectiveStatus.ACHIEVED
            success = objective_achieved or analysis.objective_status == ObjectiveStatus.PARTIAL

            self.ab_manager.record_conversation_result(
                contact=contact,
                experiment_id=experiment.id,
                success=success,
                response_time=0.0,
                satisfaction_score=float(analysis.customer_satisfaction_score),
                bot_suspicion=bool(analysis.bot_suspicion_detected),
                objective_achieved=objective_achieved,
            )

        if self.ab_manager._should_calculate_significance(experiment):
            self.ab_manager._calculate_statistical_significance(experiment)

    def _promote_winner_if_ready(self):
        """Si ya hay ganador significativo, lo promueve como configuración global activa."""
        experiment = self._get_active_experiment()
        if not experiment:
            return

        if not experiment.is_statistically_significant:
            return

        winner = self.ab_manager._calculate_winner(experiment)
        if not winner:
            return

        experiment.winner_variant_id = winner.id

        overrides = {
            "source": "winner",
            "variant_id": winner.id,
            "variant_name": winner.name,
            **dict(winner.config or {}),
        }

        if self.business_config:
            try:
                project_root = str(Path(__file__).resolve().parents[2])
                self.apply_runtime_overrides(overrides, project_root)
            except Exception as exc:
                logger.warning(f"No se pudo aplicar ganador global: {exc}")

    def _persist_adaptive_snapshot(self, summary: dict[str, Any]):
        """Persiste snapshot ligero para inspección en UI/API."""
        if not self.business_config:
            return

        adaptive_cfg = self.business_config.config.get("adaptive_layer", {})
        adaptive_cfg["last_report"] = summary
        adaptive_cfg["last_run_at"] = summary.get("ran_at")
        adaptive_cfg["total_runs"] = int(adaptive_cfg.get("total_runs", 0)) + 1
        adaptive_cfg["ab_stats"] = self.ab_manager.get_stats()

        self.business_config.config["adaptive_layer"] = adaptive_cfg
        self.business_config.save_config(self.business_config.config)

    def get_status(self) -> dict[str, Any]:
        """Estado runtime de la capa 3."""
        active_experiment = self._get_active_experiment()
        return {
            "enabled": bool(self.deep_analyzer.enabled),
            "analysis_in_progress": self._analysis_in_progress,
            "should_trigger": self.deep_analyzer.should_trigger_analysis(),
            "conversations_since_last_analysis": self.deep_analyzer.conversations_since_last_analysis,
            "last_analysis_date": self.deep_analyzer.last_analysis_date.isoformat()
            if self.deep_analyzer.last_analysis_date
            else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_error": self.last_error,
            "total_runs": self.total_runs,
            "last_run_summary": self.last_run_summary,
            "ab_testing": {
                "enabled": self.ab_manager.enabled,
                "active_experiment_id": active_experiment.id if active_experiment else None,
                "active_experiment_name": active_experiment.name if active_experiment else None,
                "active_winner_variant_id": active_experiment.winner_variant_id if active_experiment else None,
                "stats": self.ab_manager.get_stats(),
            },
            "effective_overrides": self.get_runtime_overrides(),
        }


adaptive_layer_manager = AdaptiveLayerManager()
