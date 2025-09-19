from typing import Optional
import time

from admin_db import get_session
from models import ModelConfig, Rule, AllowedContact
from crypto import encrypt_text


class ModelError(Exception):
    pass


class ModelManager:
    def __init__(self):
        self.session = None

    def select_model_for_chat(self, chat_id: str, message_count: int = 1) -> str:
        """Alias for choose_model_for_conversation for backward compatibility"""
        return self.choose_model_for_conversation(chat_id, message_count)

    def get_reasoner_model(self) -> str:
        """Get the model configured for reasoning tasks"""
        session = get_session()
        try:
            # Look for a reasoner-specific model first
            reasoner_model = session.query(ModelConfig).filter(
                ModelConfig.active == True,
                ModelConfig.name.ilike('%reasoner%')
            ).first()
            if reasoner_model:
                return reasoner_model.name
            
            # Fall back to first active model
            default = session.query(ModelConfig).filter(ModelConfig.active == True).first()
            return default.name if default else "default"
        finally:
            session.close()

    def choose_model_for_conversation(self, chat_id: str, message_count: int) -> str:
        """Evalúa las reglas y devuelve el provider/name del modelo a usar.

        Devuelve el nombre del modelo configurado por la primera regla que coincida
        (every_n_messages). Si no hay reglas aplicables, devuelve el primer modelo activo.
        """
        session = get_session()
        try:
            rules = session.query(Rule).filter(Rule.enabled == True).all()
            for r in rules:
                if r.every_n_messages and r.every_n_messages > 0 and message_count % r.every_n_messages == 0:
                    if r.model:
                        return r.model.name
            default = session.query(ModelConfig).filter(ModelConfig.active == True).first()
            return default.name if default else "default"
        finally:
            session.close()

    def is_contact_allowed(self, contact_id: str) -> bool:
        session = get_session()
        try:
            enc = encrypt_text(contact_id)
            found = session.query(AllowedContact).filter(AllowedContact.contact_id == enc).first()
            return found is not None
        finally:
            session.close()


def simulate_typing_send(send_callback, text: str, per_char_delay: float = 0.05):
    """Simula typing enviando en chunks; send_callback debe aceptar el chunk.
    per_char_delay en segundos (ej. 1.0 para 1s/char)."""
    for ch in text:
        send_callback(ch)
        time.sleep(per_char_delay)
