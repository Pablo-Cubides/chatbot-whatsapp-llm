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

    # 2) Inyecta perfil/estrategia y Docs locales como system prompts previos al historial
    try:
        import chat_sessions as cs
        profile = cs.get_profile(chat_id)
        active_strategy = cs.get_active_strategy(chat_id)
        pre_systems = []
        
        # Primero agregar el perfil del bot/empresa
        def _read_text(fp: str) -> str:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                try:
                    with open(fp, 'r', encoding='cp1252', errors='ignore') as f:
                        return f.read()
                except Exception:
                    return ""
            except Exception:
                return ""

        def _load_chat_specific_context(chat_id: str) -> dict:
            """
            Carga el contexto específico para un chat desde contextos/{chat_id}/
            Retorna dict con 'perfil', 'contexto' y 'objetivo' específicos del usuario
            """
            # Consider both folders: contextos/{chat_id} and contextos/chat_{chat_id}
            candidates = [
                os.path.join(HERE, 'contextos', chat_id),
                os.path.join(HERE, 'contextos', f'chat_{chat_id}')
            ]
            result = {'perfil': '', 'contexto': '', 'objetivo': ''}

            print(f"🔍 Buscando contexto para chat_id: {chat_id}")
            for contextos_dir in candidates:
                print(f"🔍 Directorio candidato: {contextos_dir} -> existe={os.path.exists(contextos_dir)}")
                if not os.path.exists(contextos_dir):
                    continue

                # Cargar perfil específico del usuario
                perfil_path = os.path.join(contextos_dir, 'perfil.txt')
                if os.path.exists(perfil_path) and not result['perfil']:
                    result['perfil'] = _read_text(perfil_path)
                    print(f"✅ Cargado perfil del usuario: {len(result['perfil'])} caracteres")

                # Cargar contexto específico del usuario
                contexto_path = os.path.join(contextos_dir, 'contexto.txt')
                if os.path.exists(contexto_path) and not result['contexto']:
                    result['contexto'] = _read_text(contexto_path)
                    print(f"✅ Cargado contexto del usuario: {len(result['contexto'])} caracteres")

                # Cargar objetivo específico del usuario
                objetivo_path = os.path.join(contextos_dir, 'objetivo.txt')
                if os.path.exists(objetivo_path) and not result['objetivo']:
                    result['objetivo'] = _read_text(objetivo_path)
                    print(f"✅ Cargado objetivo del usuario: {len(result['objetivo'])} caracteres")

            return result

        docs_dir = os.path.join(HERE, 'Docs')
        
        # Cargar archivos globales del sistema
        try:
            perfil_fp = os.path.join(docs_dir, 'Perfil.txt')
            ej_fp = os.path.join(docs_dir, 'ejemplo_chat.txt')
            ult_fp = os.path.join(docs_dir, 'Ultimo_contexto.txt')
            
            perfil_global_txt = _read_text(perfil_fp) if os.path.exists(perfil_fp) else ""
            ejemplo_txt = _read_text(ej_fp) if os.path.exists(ej_fp) else ""
            ultimo_txt = _read_text(ult_fp) if os.path.exists(ult_fp) else ""
            
            # Cargar contexto específico del chat/usuario
            chat_context = _load_chat_specific_context(chat_id)
            
            # ORDEN DE PRIORIDAD SEGÚN TU ESPECIFICACIÓN:
            # 1. System base de payload.json (ya está)
            # 2. System "Guía de conversación" (de ejemplo_chat.txt)
            # 3. System "Perfil Global" (de Docs/Perfil.txt)  
            # 4. System "Perfil Usuario" (de contextos/{chat_id}/perfil.txt)
            # 5. System "Contexto Usuario" (de contextos/{chat_id}/contexto.txt)
            # 6. System "Contexto diario" (de Docs/Ultimo_contexto.txt)
            # 7. System "Contexto RAG" (después)
            
            if ejemplo_txt.strip():
                pre_systems.append({
                    "role": "system", 
                    "content": f"GUÍA DE CONVERSACIÓN - Estilo y comportamiento (sigue estas pautas siempre):\n{ejemplo_txt}"
                })
            
            if perfil_global_txt.strip():
                pre_systems.append({
                    "role": "system", 
                    "content": f"PERFIL GLOBAL - Información general sobre ti:\n{perfil_global_txt}"
                })
            
            if chat_context['perfil'].strip():
                pre_systems.append({
                    "role": "system", 
                    "content": f"PERFIL DE USUARIO - Información específica sobre este usuario ({chat_id}):\n{chat_context['perfil']}"
                })
            
            if chat_context['contexto'].strip():
                pre_systems.append({
                    "role": "system", 
                    "content": f"CONTEXTO DE USUARIO - Información de contexto específica para este usuario ({chat_id}):\n{chat_context['contexto']}"
                })
            if chat_context.get('objetivo','').strip():
                pre_systems.append({
                    "role": "system",
                    "content": f"OBJETIVO DEL CHAT - Qué se busca lograr en esta conversación ({chat_id}):\n{chat_context['objetivo']}"
                })
            
            if ultimo_txt.strip():
                pre_systems.append({
                    "role": "system", 
                    "content": f"CONTEXTO DIARIO - Información reciente y actualizada:\n{ultimo_txt}"
                })
            
            # Agregar información del perfil y estrategia desde la DB si existe
            if profile and hasattr(profile, 'name'):
                pre_systems.append({
                    "role": "system", 
                    "content": f"PERFIL DB - {profile.name}: {getattr(profile, 'description', 'Sin descripción')}"
                })
            
            if active_strategy and hasattr(active_strategy, 'name'):
                pre_systems.append({
                    "role": "system", 
                    "content": f"ESTRATEGIA ACTIVA - {active_strategy.name}: {getattr(active_strategy, 'description', 'Sin descripción')}"
                })
                
        except Exception as _e:
            logging.getLogger(__name__).debug(f"Docs no inyectados: {_e}")
        
        # Luego agregar configuraciones específicas del chat
        if profile:
            if (profile.initial_context or '').strip():
                pre_systems.append({"role": "system", "content": f"Contexto inicial del chat: {profile.initial_context}"})
            if (profile.objective or '').strip():
                pre_systems.append({"role": "system", "content": f"Objetivo del chat (a cumplir por el asistente): {profile.objective}"})
            if (profile.instructions or '').strip():
                pre_systems.append({"role": "system", "content": f"Instrucciones adicionales: {profile.instructions}"})
        if active_strategy and (active_strategy.strategy_text or '').strip():
            pre_systems.append({"role": "system", "content": f"Estrategia activa para este chat (seguir estrictamente):\n{active_strategy.strategy_text}"})

        # Consolida todos los pre_systems en UN solo system fuerte para maximizar cumplimiento
        # Añade instrucciones clave para reforzar identidad y estilo
        preamble = (
            "INSTRUCCIONES CLAVE (siempre obedecer):\n"
            "- Cuando te pregunten quién eres o cómo te llamas, responde según el PERFIL (global y/o del usuario) y jamás como 'modelo' o 'IA'.\n"
            "- Usa el tono y estilo de la GUÍA DE CONVERSACIÓN.\n"
            "- Para hechos recientes, apóyate en CONTEXTO DIARIO y RAG si están presentes.\n"
        )
        pre_systems.insert(0, {"role": "system", "content": preamble})
        combined_text = "\n\n".join([s.get("content", "") for s in pre_systems if s.get("content")])

        # 3) Añadir Contexto RAG (top-k) directamente al bloque combinado
        try:
            from rag_utils import retrieve_context
            rag_ctx = retrieve_context(user_message)
            if rag_ctx and rag_ctx.strip():
                combined_text += ("\n\n" if combined_text else "") + f"CONTEXTO RAG (fragmentos relevantes):\n{rag_ctx}"
        except Exception as _re:
            logging.getLogger(__name__).debug(f"RAG no disponible: {_re}")

        # Inserta el bloque combinado como 2º system (dejando primero el system base del payload)
        base_msgs = payload["messages"]
        if base_msgs and isinstance(base_msgs[0], dict) and base_msgs[0].get("role") == "system":
            payload["messages"] = [base_msgs[0]]
            if combined_text:
                payload["messages"].append({"role": "system", "content": combined_text})
            payload["messages"].extend(base_msgs[1:])
        else:
            # Si no hay system base, agregamos solo el combinado
            payload["messages"] = ([{"role": "system", "content": combined_text}] if combined_text else []) + base_msgs
    except Exception as e:
        # If anything fails, continue without extra system messages
        print(f"Warn: profile/strategy injection failed: {e}")

    # 3) (Opcional) Contextos de usuario desde DB: se anexan al bloque combinado si existen
    try:
        from admin_db import get_session
        from models import UserContext
        session = get_session()
        user_contexts = session.query(UserContext).filter(UserContext.user_id == chat_id).all()
        session.close()

        if user_contexts:
            user_ctx_text = "\n".join([uc.text for uc in user_contexts])
            # Insertar justo después del primer system (el base) o al principio si no hay base
            idx = 1 if (payload["messages"] and payload["messages"][0].get("role") == "system") else 0
            payload["messages"].insert(idx + 1, {  # después del combinado
                "role": "system",
                "content": f"CONTEXTO DEL USUARIO (DB):\n{user_ctx_text}"
            })
    except Exception as e:
        logging.getLogger(__name__).debug(f"UserContext DB no disponible: {e}")

    # 4) RAG ya inyectado en el bloque combinado (arriba)

    # 5) Añade el historial pero limitado para evitar que eclipse el perfil
    try:
        import os as _os
        max_msgs = int(_os.environ.get("CHAT_HISTORY_MAX_MSGS", "12"))
    except Exception:
        max_msgs = 12
    trimmed_history = history[-max_msgs:] if isinstance(history, list) else []
    payload["messages"].extend(trimmed_history)

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
