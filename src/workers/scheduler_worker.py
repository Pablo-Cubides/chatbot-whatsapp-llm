"""
⏰ Scheduler Worker - Proceso separado para mensajes programados
Procesa scheduled.json y encola mensajes en el momento indicado
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime

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

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.queue_system import queue_manager


class SchedulerWorker:
    """Worker que procesa mensajes programados"""

    def __init__(self):
        self.scheduled_file = os.path.join(os.path.dirname(__file__), "..", "data", "scheduled.json")
        self.scheduler = BackgroundScheduler()
        self.running = False
        logger.info("⏰ Scheduler Worker inicializado")

    def start(self):
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

    def process_scheduled_messages(self):
        """Procesar mensajes programados cuya hora llegó"""
        try:
            # Leer archivo scheduled.json
            if not os.path.exists(self.scheduled_file):
                return

            with open(self.scheduled_file, encoding="utf-8") as f:
                scheduled = json.load(f)

            if not scheduled:
                return

            now = datetime.utcnow()
            messages_to_process = []
            remaining_messages = []

            for entry in scheduled:
                # Parsear fecha programada
                when_str = entry.get("when", "now")

                if when_str == "now":
                    # Enviar inmediatamente
                    messages_to_process.append(entry)
                else:
                    try:
                        scheduled_time = datetime.fromisoformat(when_str.replace("Z", "+00:00"))

                        if scheduled_time <= now:
                            # Ha llegado el momento
                            messages_to_process.append(entry)
                        else:
                            # Todavía no
                            remaining_messages.append(entry)
                    except (ValueError, AttributeError):
                        # Fecha inválida, procesar de todos modos
                        logger.warning(f"⚠️ Fecha inválida: {when_str}, procesando de todos modos")
                        messages_to_process.append(entry)

            # Procesar mensajes cuya hora llegó
            for msg in messages_to_process:
                try:
                    chat_id = msg.get("chat_id")
                    message = msg.get("message")
                    metadata = msg.get("metadata", {})
                    metadata["scheduled_at"] = msg.get("when")
                    metadata["scheduled_by"] = msg.get("created_by", "scheduler")

                    # Encolar en el sistema de cola
                    message_id = queue_manager.enqueue_message(
                        chat_id=chat_id,
                        message=message,
                        when=None,  # Enviar inmediatamente
                        priority=1,  # Prioridad media
                        metadata=metadata,
                    )

                    logger.info(f"✅ Mensaje programado encolado: {message_id} para {chat_id}")

                except Exception as e:
                    logger.error(f"❌ Error procesando mensaje programado: {e}")
                    # Mantener en la lista para reintentar
                    remaining_messages.append(msg)

            # Actualizar archivo con mensajes restantes
            with open(self.scheduled_file, "w", encoding="utf-8") as f:
                json.dump(remaining_messages, f, indent=2, ensure_ascii=False)

            if messages_to_process:
                logger.info(f"📬 Procesados {len(messages_to_process)} mensajes programados")

        except FileNotFoundError:
            # Archivo no existe, crear vacío
            os.makedirs(os.path.dirname(self.scheduled_file), exist_ok=True)
            with open(self.scheduled_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        except json.JSONDecodeError:
            logger.error("❌ Error decodificando scheduled.json, archivo corrupto")
        except Exception as e:
            logger.error(f"❌ Error procesando mensajes programados: {e}")

    def shutdown(self):
        """Apagar el worker de forma ordenada"""
        logger.info("🛑 Apagando Scheduler Worker...")
        self.running = False

        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

        logger.info("✅ Scheduler Worker apagado")

    def _signal_handler(self, signum, frame):
        """Manejar señales de sistema"""
        logger.info(f"⚠️ Señal {signum} recibida")
        self.running = False


def main():
    """Función principal"""
    logger.info("=" * 60)
    logger.info("⏰ SCHEDULER WORKER")
    logger.info("Procesamiento de mensajes programados")
    logger.info("=" * 60)

    worker = SchedulerWorker()
    worker.start()


if __name__ == "__main__":
    main()
