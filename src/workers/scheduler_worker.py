"""
⏰ Scheduler Worker - Proceso separado para mensajes programados
Coordina tareas periódicas para cola DB y mantenimiento operativo
"""

import logging
import os
import signal
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/scheduler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

from src.services.queue_system import queue_manager
from crypto import is_key_rotation_due


class SchedulerWorker:
    """Worker que procesa mensajes programados"""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.running = False
        logger.info("⏰ Scheduler Worker inicializado")

    def start(self) -> None:
        """Iniciar el worker"""
        logger.info("🚀 Iniciando Scheduler Worker...")

        # Configurar señales para shutdown graceful
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Programar tarea de procesamiento cada 30 segundos
        self.scheduler.add_job(
            func=self.process_scheduled_messages,
            trigger=IntervalTrigger(seconds=30),
            id="process_scheduled",
            name="Procesar mensajes programados",
            replace_existing=True,
        )

        self.scheduler.add_job(
            func=self.check_fernet_rotation,
            trigger=IntervalTrigger(hours=12),
            id="fernet_rotation_check",
            name="Verificar rotación de Fernet key",
            replace_existing=True,
        )

        self.scheduler.start()
        self.running = True

        logger.info("✅ Scheduler Worker activo")

        # Mantener el proceso corriendo
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⚠️ Interrupción recibida, apagando...")
        finally:
            self.shutdown()

    def process_scheduled_messages(self) -> None:
        """DB-backed scheduler: currently acts as heartbeat/visibility checkpoint."""
        try:
            pending_due = queue_manager.get_pending_messages(limit=1, include_scheduled=True)
            logger.debug("Scheduler heartbeat - due messages snapshot: %s", len(pending_due))
        except Exception as e:
            logger.error("❌ Error procesando mensajes programados: %s", e)

    def shutdown(self) -> None:
        """Apagar el worker de forma ordenada"""
        logger.info("🛑 Apagando Scheduler Worker...")
        self.running = False

        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

        logger.info("✅ Scheduler Worker apagado")

    def check_fernet_rotation(self) -> None:
        """Emit warning when Fernet key age reaches rotation policy threshold."""
        try:
            rotation_days = int(os.getenv("FERNET_KEY_ROTATION_DAYS", "90"))
            due, age_days = is_key_rotation_due(rotation_days=rotation_days)
            if due:
                logger.warning(
                    "🔐 Fernet key rotation due: key age %.1f days (threshold=%s).",
                    age_days,
                    rotation_days,
                )
            else:
                logger.info(
                    "🔐 Fernet key age %.1f days (rotation threshold=%s)",
                    age_days,
                    rotation_days,
                )
        except Exception as e:
            logger.warning("No se pudo verificar rotación de Fernet key: %s", e)

    def _signal_handler(self, signum: int, frame: object | None) -> None:
        """Manejar señales de sistema"""
        logger.info("⚠️ Señal %s recibida", signum)
        self.running = False


def main() -> None:
    """Función principal"""
    logger.info("=" * 60)
    logger.info("⏰ SCHEDULER WORKER")
    logger.info("Procesamiento de mensajes programados")
    logger.info("=" * 60)

    worker = SchedulerWorker()
    worker.start()


if __name__ == "__main__":
    main()
