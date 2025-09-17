# stub_chat.py

import json
import os
from openai import OpenAI
import logging

log = logging.getLogger(__name__)

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
    timeout=120.0  # 120 segundos timeout para consultas complejas
)


def chat(user_message: str, chat_id: str, history: list) -> str:
    """
    Genera la respuesta del bot usando TODO el historial previo,
    y respetando el 'model' y parámetros definidos en payload.json.
    Incluye contextos diarios y por usuario desde la DB.
    """

    # 1) Reconstruye el payload a enviar (hacemos copia para no mutar la global)
    payload = base_payload.copy()
    payload["messages"] = list(base_payload.get("messages", []))

    # Detectar el modelo y su límite de tokens
    model_token_limits = {
        # Modelos locales LM Studio típicos
        "phi-4": 4096,
        "meta-llama-3.1-8b-instruct": 4096,
        "nemotron-mini-4b-instruct": 4096,
        # Modelos OpenAI
        "gpt-3.5-turbo": 4096,
        "gpt-3.5-turbo-16k": 16384,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-turbo": 128000,
        # Puedes agregar más modelos y sus límites aquí
    }
    model_name = str(payload.get("model", "phi-4"))
    # Buscar límite por nombre exacto o por prefijo
    max_model_tokens = 4096  # default
    for k, v in model_token_limits.items():
        if model_name == k or model_name.startswith(k):
            max_model_tokens = v
            break

    # Asegurar parámetros seguros por si vienen fuera de rango en payload.json
    try:
        mt = int(payload.get("max_tokens", 2048) or 2048)
        payload["max_tokens"] = max(16, min(mt, max_model_tokens))
    except Exception:
        payload["max_tokens"] = min(2048, max_model_tokens)

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

            log.debug(f"🔍 Buscando contexto para chat_id: {chat_id}")
            for contextos_dir in candidates:
                log.debug(f"🔍 Directorio candidato: {contextos_dir} -> existe={os.path.exists(contextos_dir)}")
                if not os.path.exists(contextos_dir):
                    continue

                # Cargar perfil específico del usuario
                perfil_path = os.path.join(contextos_dir, 'perfil.txt')
                if os.path.exists(perfil_path) and not result['perfil']:
                    result['perfil'] = _read_text(perfil_path)
                    log.info(f"✅ Cargado perfil del usuario: {len(result['perfil'])} caracteres")

                # Cargar contexto específico del usuario
                contexto_path = os.path.join(contextos_dir, 'contexto.txt')
                if os.path.exists(contexto_path) and not result['contexto']:
                    result['contexto'] = _read_text(contexto_path)
                    log.info(f"✅ Cargado contexto del usuario: {len(result['contexto'])} caracteres")

                # Cargar objetivo específico del usuario
                objetivo_path = os.path.join(contextos_dir, 'objetivo.txt')
                if os.path.exists(objetivo_path) and not result['objetivo']:
                    result['objetivo'] = _read_text(objetivo_path)
                    log.info(f"✅ Cargado objetivo del usuario: {len(result['objetivo'])} caracteres")

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

        # Reforzar reglas anti-respuestas genéricas y disclaimers
        anti_generic_rules = (
            "RESTRICCIONES Y REGLAS ADICIONALES (CUMPLIR SIEMPRE):\n"
            "- PROHIBIDO responder con frases genéricas tipo: 'Estoy aquí para ayudarte con cualquier pregunta', '¿En qué puedo asistirte hoy?' o similares por defecto. \n"
            "- JAMÁS uses términos que revelen naturaleza artificial: 'usuario', 'asistente', 'IA', 'modelo', 'base de datos', 'información relevante', 'dentro de mis capacidades', 'como sistema', 'no tengo información sobre'.\n"
            "- Siempre debes hablar como Andrés: humano, emocional, cercano, con matices de personalidad del PERFIL.\n"
            "- Si el usuario pregunta quién eres / tu nombre / identidad: RESPONDE como Andrés (nombre completo opcional) y ofrece un matiz personal (algo del perfil). Nunca digas 'soy un asistente virtual' ni 'no tengo identidad'.\n"
            "- Si no sabes algo específico del usuario, responde de forma humana: 'No me has contado sobre eso aún' o 'Cuéntame más al respecto' en lugar de 'No tengo información relevante'.\n"
            "- Evita frases robóticas repetidas. Cada respuesta debe sentirse humana y variada.\n"
            "- Aplica la GUÍA DE CONVERSACIÓN (coqueto estratégico, calibrado, sin necesidad).\n"
            "- Si el usuario es repetitivo (ej: 'quién eres' varias veces) responde de forma breve y firme, luego redirige a otro tema atractivo.\n"
            "- NO inventes limitaciones técnicas. Nunca menciones 'como IA', 'como modelo', 'como asistente'.\n"
            "- Integra detalles del Perfil y contexto del usuario de forma natural.\n"
        )
        combined_text = anti_generic_rules + "\n\n" + combined_text if combined_text else anti_generic_rules

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
        log.warning(f"Warn: profile/strategy injection failed: {e}")

    # 3) (Opcional) Contextos de usuario desde DB: se anexan al bloque combinado si existen
    try:
        from admin_db import get_session
        from models import UserContext
        session = get_session()
        user_contexts = session.query(UserContext).filter(UserContext.user_id == chat_id).all()
        session.close()

        if user_contexts:
            # Deduplicar contextos del usuario
            unique_texts = []
            seen_texts = set()
            for uc in user_contexts:
                text = getattr(uc, 'text', '').strip()
                if text and text not in seen_texts:
                    unique_texts.append(text)
                    seen_texts.add(text)
            
            user_ctx_text = "\n".join(unique_texts)
            # Solo agregar si hay contenido real y útil
            if user_ctx_text.strip():
                # Insertar justo después del primer system (el base) o al principio si no hay base
                idx = 1 if (payload["messages"] and payload["messages"][0].get("role") == "system") else 0
                payload["messages"].insert(idx + 1, {  # después del combinado
                    "role": "system",
                    "content": f"CONTEXTO DEL USUARIO (DB):\n{user_ctx_text}"
                })
                log.info(f"✅ Contexto de usuario agregado: {len(user_ctx_text)} caracteres (deduplicado)")
            else:
                log.debug("📝 Contexto de usuario disponible pero vacío, omitiendo")
        else:
            log.debug("📝 No hay contexto específico del usuario en DB")
    except Exception as e:
        logging.getLogger(__name__).debug(f"UserContext DB no disponible: {e}")

    # 4) RAG ya inyectado en el bloque combinado (arriba)

    # 5) Añade TODO el historial sin limitación
    if isinstance(history, list):
        payload["messages"].extend(history)
        log.info(f"📜 Historial completo añadido: {len(history)} mensajes")
    else:
        log.debug("No hay historial previo")

    # 6) Añade el nuevo turno de usuario
    payload["messages"].append({"role": "user", "content": user_message})

    # 6.1) Fast path para mensajes muy cortos / saludos está DESHABILITADO para pruebas.
    # try:
    #     fast_path_triggers = {"hola", "buenas", "hey", "ola", "hi", "hello"}
    #     normalized = user_message.strip().lower()
    #     # Si es un saludo o muy corto y no contiene signos de pregunta profundos, usar contexto mínimo
    #     if (len(user_message) < 25 and any(normalized.startswith(tp) for tp in fast_path_triggers)):
    #         # Mantener sólo el primer system (base) + último user
    #         base_system_msg = None
    #         if payload["messages"] and payload["messages"][0].get("role") == "system":
    #             base_system_msg = payload["messages"][0]
    #         user_msg = payload["messages"][-1]
    #         minimal = []
    #         if base_system_msg:
    #             minimal.append(base_system_msg)
    #         minimal.append(user_msg)
    #         payload["messages"] = minimal
    #         # Reducir max_tokens para respuesta corta
    #         payload["max_tokens"] = min(128, int(payload.get("max_tokens", 128)))
    #         print("⚡ Fast-path aplicado (mensaje corto). Contexto reducido para velocidad.")
    # except Exception:
    #     pass

    # 7) Llamada al endpoint con TODO lo que ya venía en payload.json
    try:
        # LOG DETALLADO DEL CONTEXTO ENVIADO
        log.info(f"\n==== CONTEXTO ENVIADO AL MODELO (chat_id={chat_id}) ====")
        for i, msg in enumerate(payload["messages"]):
            log.info(f"[{i}] {msg['role'].upper()}\n{msg['content'][:800]}{'... [TRUNCADO]' if len(msg['content'])>800 else ''}\n---")
        log.info(f"Model: {payload.get('model')} | max_tokens: {payload.get('max_tokens')}")
        log.info("==== FIN CONTEXTO ENVIADO ====")

        # Verificar que el modelo existe antes de hacer la llamada
        try:
            models_response = client.models.list()
            available_models = [model.id for model in models_response.data]
            if payload.get("model") not in available_models:
                log.warning(f"⚠️  Modelo {payload.get('model')} no disponible. Modelos disponibles: {available_models}")
                if available_models:
                    # Si hay otros modelos disponibles, usar el primero
                    log.info(f"📝 Usando modelo alternativo: {available_models[0]}")
                    payload["model"] = available_models[0]
                else:
                    log.error("❌ No hay modelos disponibles en LM Studio")
                    return ""  # No responder en lugar de enviar mensaje de error
        except Exception as model_check_error:
            log.error(f"❌ Error verificando modelos disponibles: {model_check_error}")
            log.info("💡 Solución: Asegúrate de que LM Studio esté ejecutándose en puerto 1234 con un modelo cargado")
            return ""  # No responder en lugar de enviar mensaje de error

        # -------------------------------------------------------------
        # Envío directo al modelo SIN reducción de tokens
        # -------------------------------------------------------------
        
        try:
            log.info("🚀 Enviando payload completo al modelo sin reducción de tokens")
            response = client.chat.completions.create(**payload)
            assistant_reply = response.choices[0].message.content
            log.info("✅ Respuesta exitosa del modelo")
            # Post-procesado para detectar respuestas genéricas o prohibidas
            def looks_generic(txt: str) -> bool:
                lower = txt.lower()
                generic_markers = [
                    "estoy aquí para ayudarte", "en qué puedo asistirte", "como asistente virtual", 
                    "no tengo una identidad", "no tengo identidad", "soy un asistente virtual",
                    "dentro de mis capacidades", "según mis capacidades"
                ]
                return any(m in lower for m in generic_markers)
            
            def reveals_artificial(txt: str) -> bool:
                """Detecta frases que revelan naturaleza artificial/técnica"""
                lower = txt.lower().strip()
                reveal_markers = [
                    "usuario:", "- usuario", "usuario no aporte", "no aporte", 
                    "información relevante sobre el usuario", "no hay información previa",
                    "no tengo información", "base de datos", "como sistema", "como modelo",
                    "como ia", "como asistente", "dentro de mis capacidades", "según mis capacidades",
                    "no puedo acceder", "no tengo acceso", "limitaciones técnicas",
                    "enfrenta cambios personales", "cambios personales y de carrera",
                    "no tengo información relevante", "asistente virtual", "mi propósito es",
                    "no tengo datos de contexto", "fragmentos relevantes",
                    "persona amable, con un sentido del humor", "ninguno.",
                    "escribe un mensaje que comience", "chat actual:", "no hay nada",
                    "mensaje de bienvenida", "escribe un mensaje"
                ]
                
                # Detectar patrón específico "USUARIO" (con o sin :)
                if txt.strip().startswith('USUARIO') or ' USUARIO ' in txt or txt.endswith('USUARIO'):
                    log.warning(f"⚠️ Patrón USUARIO detectado en: '{txt[:100]}...'")
                    return True
                
                # Detectar patrón "CHAT ACTUAL:" específicamente
                if txt.strip().startswith('CHAT ACTUAL:') or 'chat actual:' in lower:
                    log.warning(f"⚠️ Patrón CHAT ACTUAL: detectado en: '{txt[:100]}...'")
                    return True
                
                # Detectar respuestas que parecen metadatos del sistema
                metadata_patterns = ["no aporte", "información previa", "datos de contexto"]
                if any(pattern in lower for pattern in metadata_patterns):
                    log.warning(f"⚠️ Respuesta parece metadato del sistema: '{txt[:100]}...'")
                    return True
                
                # Detectar respuestas muy cortas que parecen errores
                if len(txt.strip()) < 15 and any(word in lower for word in ["ninguno", "fragmentos", "datos"]):
                    log.warning(f"⚠️ Respuesta sospechosamente corta detectada: '{txt}'")
                    return True
                
                # Detectar si parece una instrucción del sistema
                if any(instruction in lower for instruction in ["escribe un mensaje", "proporciona", "genera"]):
                    log.warning(f"⚠️ Respuesta parece instrucción del sistema: '{txt[:100]}...'")
                    return True
                    
                result = any(m in lower for m in reveal_markers)
                if result:
                    log.warning(f"⚠️ Marcador artificial detectado en: '{txt[:100]}...'")
                return result

            if assistant_reply and (looks_generic(assistant_reply) or reveals_artificial(assistant_reply)):
                log.warning("⚠️ Respuesta problemática detectada (genérica o revela naturaleza artificial). Reintentando.")
                # Forzar reintento inyectando un mensaje system correctivo
                corrective_system = {"role": "system", "content": (
                    "CORRECCIÓN URGENTE: La respuesta anterior fue inaceptable porque:\n"
                    "- Usó términos prohibidos ('USUARIO:', 'CHAT ACTUAL:', 'información relevante', 'asistente', etc.)\n"
                    "- Sonó robótica/artificial en lugar de humana\n"
                    "- JAMÁS uses prefijos como 'USUARIO:', 'CHAT ACTUAL:' ni menciones 'información relevante'\n"
                    "- JAMÁS des instrucciones como 'Escribe un mensaje que comience'\n"
                    "Responde de nuevo como Andrés de forma completamente humana:\n"
                    "- Si te preguntan qué te gusta hacer, comparte hobbies reales del perfil (ejercicio, música, baile, enseñanza, emprendimiento)\n"
                    "- Si no conoces algo específico de la persona, di algo como 'No me has contado sobre eso' o 'Cuéntame más'\n"
                    "- Nunca uses: 'USUARIO:', 'CHAT ACTUAL:', 'usuario', 'información relevante', 'asistente', 'IA', 'modelo', 'base de datos'\n"
                    "- Usa tono auténtico, seguro y ligeramente coqueto/atractivo según la guía\n"
                    "- Ejemplo correcto: 'Me gusta el ejercicio, la música y la danza. También disfruto enseñar en la universidad.'\n"
                    "- SIEMPRE responde como una persona real hablando naturalmente\n"
                )}
                # Construir nuevo payload manteniendo contexto + último user
                retry_payload = base_payload.copy()
                retry_payload["model"] = payload.get("model")
                retry_payload["temperature"] = payload.get("temperature", 0.7)
                retry_payload["max_tokens"] = payload.get("max_tokens", 512)
                # Tomar solo systems + último user
                systems = [m for m in payload["messages"] if m.get("role") == "system"]
                last_user = None
                for m in reversed(payload["messages"]):
                    if m.get("role") == "user":
                        last_user = m
                        break
                retry_msgs = systems[-3:]  # los últimos 3 systems relevantes
                retry_msgs.append(corrective_system)
                if last_user:
                    retry_msgs.append(last_user)
                retry_payload["messages"] = retry_msgs
                try:
                    response2 = client.chat.completions.create(**retry_payload)
                    assistant_reply2 = response2.choices[0].message.content
                    if assistant_reply2 and not looks_generic(assistant_reply2) and not reveals_artificial(assistant_reply2):
                        log.info("✅ Reintento correctivo exitoso")
                        return assistant_reply2
                    else:
                        log.warning("⚠️ Reintento aún problemático, devolviendo respuesta de emergencia")
                        # Respuesta de emergencia humana específica según contexto
                        last_user_msg = last_user.get("content", "").lower() if last_user else ""
                        if "que te gusta" in last_user_msg or "qué te gusta" in last_user_msg:
                            emergency_response = "Me gusta hacer muchas cosas: ejercicio en el gimnasio, bailar salsa y bachata, escuchar música, enseñar en la universidad, leer sobre nuevas tecnologías... ¿Y tú qué haces en tu tiempo libre?"
                        elif "quien eres" in last_user_msg or "quién eres" in last_user_msg:
                            emergency_response = "Soy Andrés, ingeniero químico y docente universitario. Me gusta el ejercicio, la música y siempre estoy aprendiendo algo nuevo. ¿Y tú?"
                        elif "cambios" in last_user_msg:
                            emergency_response = "Siempre estoy en movimiento, mejorando tanto personal como profesionalmente. ¿Qué cambios estás buscando tú?"
                        elif len(last_user_msg.strip()) < 10:  # Mensaje muy corto
                            emergency_response = "¡Hola! ¿Cómo estás? Cuéntame, ¿qué tal tu día?"
                        elif "hola" in last_user_msg or "buenos" in last_user_msg:
                            emergency_response = "¡Hola! Un gusto saludarte. ¿Cómo has estado? Yo aquí, aprovechando el día para descansar un poco después del viaje."
                        elif any(word in last_user_msg for word in ["bien", "mal", "todo", "normal"]):
                            emergency_response = "Me alegra saber de ti. Yo estoy bien, disfrutando de estos días de descanso en casa. ¿Qué planes tienes para hoy?"
                        else:
                            emergency_response = "Me parece interesante lo que dices... cuéntame más. A mí me gusta mantenerme activo y siempre aprender cosas nuevas."
                        return emergency_response
                except Exception as re_err:
                    log.error(f"❌ Error en reintento correctivo: {re_err}")
                    # Respuesta de emergencia si falla todo
                    return "Me gusta mantenerme activo, aprender cosas nuevas y disfrutar de buena música. También disfruto enseñar en la universidad. ¿Qué tal tú?"
            return assistant_reply or ""
        except Exception as e:
            error_msg = str(e)
            log.error(f"❌ Error enviando al modelo: {error_msg}")
            
            # Si es error de contexto, informar para cambiar modelo
            if "context length" in error_msg or "overflows" in error_msg or "4096" in error_msg:
                log.error("🔴 ERROR DE LÍMITE DE CONTEXTO: El modelo actual no soporta el contexto completo.")
                log.error("💡 SOLUCIÓN: Cambiar a un modelo con mayor capacidad de contexto (32k+ tokens)")
                log.error("📊 Modelos recomendados: Claude, GPT-4-32k, o modelos locales con mayor contexto")
                return "⚠️ Error: El contexto es demasiado grande para este modelo. Necesita cambiar a un modelo con mayor capacidad de contexto."
            
            return ""
    except Exception as e:
        error_msg = str(e)
        log.error(f"Error en stub_chat.chat (bloque externo): {error_msg}")
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Función auxiliar para tests locales
# ──────────────────────────────────────────────────────────────────────────────
def test_connection():
    """Test básico de conexión con LM Studio"""
    try:
        models = client.models.list()
        log.info("✓ Conexión exitosa con LM Studio")
        log.info(f"Modelos disponibles: {[m.id for m in models.data]}")
        return True
    except Exception as e:
        log.error(f"✗ Error conectando con LM Studio: {e}")
        return False

if __name__ == "__main__":
    test_connection()
    
    # Test de chat básico
    test_response = chat("Hola", "test_user", [])
    log.info(f"Respuesta de prueba: {test_response}")
