# stub_chat.py

import json
import os
from openai import OpenAI
import logging

# ──────────────────────────────────────────────────────────────────────────────
# 1) Carga global de la plantilla payload.json
# ──────────────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(__file__)
PAYLOAD_PATH = os.path.join(HERE, "payload.json")

with open(PAYLOAD_PATH, encoding="utf-8") as f:
    base_payload = json.load(f)
# Ahora base_payload tiene keys como "model", "temperature", "max_tokens", etc.
# y su lista original de mensajes (p. ej. el system prompt base).

# Inicializa el cliente de LM Studio con timeout
client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio",
    timeout=30.0  # 30 segundos timeout
)


def chat(user_message: str, chat_id: str, history: list) -> str:
    """
    Genera la respuesta del bot usando TODO el historial previo,
    y respetando el 'model' y parámetros definidos en payload.json.
    Incluye contextos diarios y por usuario desde la DB.
    """

    # 1) Reconstruye el payload a enviar (hacemos copia para no mutar la global)
    payload = base_payload.copy()
    # Asegurarnos de no compartir referencias de lista entre llamadas
    payload["messages"] = list(base_payload.get("messages", []))
    # Asegurar parámetros seguros por si vienen fuera de rango en payload.json
    try:
        mt = int(payload.get("max_tokens", 2048) or 2048)
        payload["max_tokens"] = max(16, min(mt, 4096))
    except Exception:
        payload["max_tokens"] = 2048

    # 2) Inyecta perfil y estrategia activa como system prompts previos al historial
    try:
        import chat_sessions as cs
        profile = cs.get_profile(chat_id)
        active_strategy = cs.get_active_strategy(chat_id)
        pre_systems = []
        if profile:
            if (profile.initial_context or '').strip():
                pre_systems.append({"role": "system", "content": f"Contexto inicial del chat: {profile.initial_context}"})
            if (profile.objective or '').strip():
                pre_systems.append({"role": "system", "content": f"Objetivo del chat (a cumplir por el asistente): {profile.objective}"})
            if (profile.instructions or '').strip():
                pre_systems.append({"role": "system", "content": f"Instrucciones adicionales: {profile.instructions}"})
        if active_strategy and (active_strategy.strategy_text or '').strip():
            pre_systems.append({"role": "system", "content": f"Estrategia activa para este chat (seguir estrictamente):\n{active_strategy.strategy_text}"})
        # Insert them at the very beginning, before any existing system messages
        payload["messages"] = pre_systems + payload["messages"]
    except Exception as e:
        # If anything fails, continue without extra system messages
        print(f"Warn: profile/strategy injection failed: {e}")

    # 3) Agregar contexto diario desde DB
    try:
        from admin_db import get_session
        from models import DailyContext, UserContext
        session = get_session()
        
        # Último contexto diario
        daily = session.query(DailyContext).order_by(DailyContext.date.desc()).first()
        if daily:
            payload["messages"].insert(1, {
                "role": "system", 
                "content": f"Contexto diario: {daily.text}"
            })
        
        # Contextos del usuario específico (usar chat_id como user_id)
        user_contexts = session.query(UserContext).filter(UserContext.user_id == chat_id).all()
        if user_contexts:
            user_ctx_text = "\n".join([uc.text for uc in user_contexts])
            payload["messages"].insert(-1, {
                "role": "system",
                "content": f"Contexto del usuario: {user_ctx_text}"
            })
        
        session.close()
    except Exception as e:
        # Si falla la DB, continuar sin contextos adicionales
        print(f"Warning: Could not load contexts from DB: {e}")

    # 4) (Opcional) Si quieres contexto RAG, descomenta:
    # from rag_utils import retrieve_context
    # rag_ctx = retrieve_context(user_message)
    # payload["messages"].insert(1, {"role":"system", "content": f"Contexto RAG:\n{rag_ctx}"})

    # 5) Añade el historial completo
    payload["messages"].extend(history)

    # 6) Añade el nuevo turno de usuario
    payload["messages"].append({"role": "user", "content": user_message})

    # 7) Llamada al endpoint con TODO lo que ya venía en payload.json
    try:
        logging.getLogger(__name__).debug(f"LLM request for chat_id={chat_id} with {len(payload['messages'])} mensajes")
        
        # Verificar que el modelo existe antes de hacer la llamada
        try:
            models_response = client.models.list()
            available_models = [model.id for model in models_response.data]
            if payload.get("model") not in available_models:
                print(f"Modelo {payload.get('model')} no disponible. Modelos disponibles: {available_models}")
                return "El modelo configurado no está disponible en LM Studio. Por favor verifica la configuración."
        except Exception as model_check_error:
            print(f"Error verificando modelos disponibles: {model_check_error}")
            return "No se puede conectar con LM Studio. ¿Está el servidor iniciado?"
        
        response = client.chat.completions.create(**payload)
        assistant_reply = response.choices[0].message.content
        return assistant_reply or ""
    except Exception as e:
        # Registro ligero para diagnóstico; devolvemos mensaje seguro
        error_msg = str(e)
        print(f"Error en stub_chat.chat: {error_msg}")
        
        # Mensajes específicos según el tipo de error
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return "El servidor de IA está tardando demasiado en responder. Intenta de nuevo."
        elif "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return "No se puede conectar con el servidor de IA. ¿Está LM Studio ejecutándose?"
        elif "404" in error_msg or "not found" in error_msg.lower():
            return "El modelo de IA configurado no se encuentra disponible."
        else:
            return "Ocurrió un error al generar la respuesta. Intenta de nuevo."


# ──────────────────────────────────────────────────────────────────────────────
# Función auxiliar para tests locales
# ──────────────────────────────────────────────────────────────────────────────
def test_connection():
    """Test básico de conexión con LM Studio"""
    try:
        models = client.models.list()
        print("✓ Conexión exitosa con LM Studio")
        print(f"Modelos disponibles: {[m.id for m in models.data]}")
        return True
    except Exception as e:
        print(f"✗ Error conectando con LM Studio: {e}")
        return False

if __name__ == "__main__":
    test_connection()
    
    # Test de chat básico
    test_response = chat("Hola", "test_user", [])
    print(f"Respuesta de prueba: {test_response}")
