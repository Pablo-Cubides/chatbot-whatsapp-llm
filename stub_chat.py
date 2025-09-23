# stub_chat.py

from openai import OpenAI
import requests
import logging
import json
import os
from settings import settings # ADDED THIS LINE

log = logging.getLogger(__name__)

# Project dir helper
HERE = os.path.dirname(__file__)

# Determine base_payload safely: prefer settings.reasoner when available,
# otherwise try to load `payload_reasoner.json` from the project, or fall back
# to a minimal payload to keep imports safe in environments without pydantic.
def _load_base_payload():
    try:
        # If settings.reasoner exists and has model_dump (Pydantic), use it
        if hasattr(settings, 'reasoner'):
            reasoner = getattr(settings, 'reasoner')
            # If it's a pydantic model, prefer model_dump
            if hasattr(reasoner, 'model_dump'):
                return reasoner.model_dump()
            # Otherwise, if it's a dict-like object, return as-is
            if isinstance(reasoner, dict):
                return reasoner
    except Exception:
        pass

    # Try to load from payload_reasoner.json in project root
    here = os.path.dirname(__file__)
    fp = os.path.join(here, 'payload_reasoner.json')
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # Minimal safe fallback payload
        return {
            "model": "gpt-3.5",
            "temperature": 0.7,
            "max_tokens": 2048,
            "messages": []
        }


base_payload = _load_base_payload()
# Ahora base_payload tiene keys como "model", "temperature", "max_tokens", etc.

# Inicializa el cliente de LM Studio con timeout
_lm_client = None
def get_lm_client():
    global _lm_client
    if _lm_client is not None:
        return _lm_client

    lm_port = getattr(settings, 'lm_studio_port', 1234)
    lm_api_key = getattr(settings, 'lm_studio_api_key', os.getenv('OPENAI_API_KEY', None))
    
    # If lm_api_key is "lm-studio", treat it as None for local LM Studio instances
    if lm_api_key == "lm-studio":
        lm_api_key = None

    _lm_client = OpenAI(
        base_url=f"http://127.0.0.1:{lm_port}/v1",
        api_key=lm_api_key,
        timeout=120.0
    )
    return _lm_client


def _lmstudio_models_list_via_http(port: int, api_key: str | None):
    """Return list of model ids from LM Studio via direct HTTP call. Doesn't require an API key for local instances."""
    url = f"http://127.0.0.1:{port}/v1/models"
    headers = {}
    if api_key:
        headers['Authorization'] = f"Bearer {api_key}"
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    return [m.get('id') for m in data.get('data', [])]


def _lmstudio_chat_via_http(port: int, payload: dict, api_key: str | None):
    """Send chat/completions to LM Studio via HTTP and return parsed JSON response."""
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f"Bearer {api_key}"
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def chat(user_message: str, chat_id: str, history: list) -> str:
    """
    Genera la respuesta del bot usando TODO el historial previo,
    y respetando el 'model' y parámetros definidos en payload.json.
    Incluye contextos diarios y por usuario desde la DB.
    """

    # 1) Reconstruye el payload a enviar (hacemos copia para no mutar la global)
    payload = base_payload.copy()
    payload["messages"] = list(base_payload.get("messages", []))

    # Asegurar parámetros seguros por si vienen fuera de rango en payload.json
    try:
        mt = int(settings.reasoner.max_tokens)
        payload["max_tokens"] = max(16, mt) # Simplified, assuming settings.reasoner.max_tokens is already validated
    except Exception:
        payload["max_tokens"] = 2048 # Fallback if settings.reasoner.max_tokens is problematic

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
            # Prefer direct HTTP call to LM Studio when possible (local instances do not require API key)
            lm_port = getattr(settings, 'lm_studio_port', 1234)
            lm_api_key = getattr(settings, 'lm_studio_api_key', None) or os.getenv('OPENAI_API_KEY', None)
            try:
                available_models = _lmstudio_models_list_via_http(lm_port, lm_api_key)
            except Exception:
                # fallback to OpenAI client if HTTP fails
                _client = get_lm_client()
                if _client is None:
                    raise RuntimeError('LM client not configured; set settings.lm_studio_api_key or OPENAI_API_KEY')
                models_response = _client.models.list()
                available_models = [model.id for model in models_response.data]

            requested_model = payload.get("model")

            def _normalize_mid(mid: str) -> str:
                import re
                if not mid:
                    return ""
                m = mid.lower()
                # replace separators with hyphen
                m = re.sub(r'[\s_/\\]+', '-', m)
                # remove suffix tokens like q4_k_m or similar technical tags
                m = re.sub(r'-q\d.*$', '', m)
                m = re.sub(r'[^a-z0-9\-\.]', '', m)
                # collapse duplicate hyphens
                while '--' in m:
                    m = m.replace('--', '-')
                return m.strip('-')

            def _best_direct_match(requested: str, candidates: list) -> str | None:
                if not requested:
                    return None
                nr = _normalize_mid(requested)
                # 1) exact normalized match
                for c in candidates:
                    if _normalize_mid(c) == nr:
                        return c
                # 2) contains or prefix matches both ways
                for c in candidates:
                    nc = _normalize_mid(c)
                    if nr.startswith(nc) or nc.startswith(nr) or nc in nr or nr in nc:
                        return c
                return None

            # Priority function - avoid embedding models and prefer instruct/chat names
            def get_model_priority(model_id: str) -> int:
                mid_l = (model_id or '').lower()
                if any(k in mid_l for k in ('embed', 'embedding', 'vector')):
                    return 100
                if 'instruct' in mid_l:
                    return 1
                if 'chat' in mid_l:
                    return 2
                if any(k in mid_l for k in ('gpt', 'llama', 'phi', 'nemotron', 'qwen', 'deepseek')):
                    return 3
                return 5

            if requested_model not in available_models:
                log.warning(f"⚠️  Modelo '{requested_model}' no disponible. Modelos disponibles: {available_models}")
                if not available_models:
                    log.error("❌ No hay modelos disponibles en LM Studio.")
                    return ""

                # Filter chat-capable models (reject embedding-only identifiers)
                def _is_chat_model(mid: str) -> bool:
                    if not mid:
                        return False
                    m = mid.lower()
                    if any(tok in m for tok in ('embed', 'embedding', 'vector')):
                        return False
                    return True

                chat_models = [m for m in available_models if _is_chat_model(m)]

                # Try direct/fuzzy match to the requested model first
                direct = _best_direct_match(str(requested_model or ""), available_models)
                if direct and _is_chat_model(direct):
                    best_model = direct
                    log.info(f"📝 Se encontró coincidencia directa/fuzzy para el solicitado: {best_model}")
                    payload["model"] = best_model
                else:
                    # Preferred models list (choose from these if present)
                    PREFERRED_MODELS = [
                        'openai/gpt-oss-20b', 'phi-4', 'deepseek-r1-distill-qwen-7b', 'nemotron-mini-4b-instruct'
                    ]
                    for pm in PREFERRED_MODELS:
                        if pm in chat_models:
                            payload["model"] = pm
                            log.info(f"📝 Usando modelo preferido: {pm}")
                            break
                    else:
                        # fallback: pick highest-priority chat-capable model
                        sorted_models = sorted(chat_models, key=get_model_priority)
                        if sorted_models:
                            payload["model"] = sorted_models[0]
                            log.info(f"📝 Usando el mejor modelo alternativo disponible: {sorted_models[0]}")
                        else:
                            log.error("❌ No se encontraron modelos de chat adecuados en LM Studio.")
                            return ""
        except Exception as model_check_error:
            log.error(f"❌ Error verificando modelos disponibles: {model_check_error}")
            log.info("💡 Solución: Asegúrate de que LM Studio esté ejecutándose en puerto 1234 con un modelo cargado")
            return ""  # No responder en lugar de enviar mensaje de error

        # -------------------------------------------------------------
        # Envío directo al modelo SIN reducción de tokens
        # -------------------------------------------------------------
        try:
            log.info("🚀 Enviando payload completo al modelo sin reducción de tokens")
            lm_port = getattr(settings, 'lm_studio_port', 1234)
            lm_api_key = getattr(settings, 'lm_studio_api_key', None) or os.getenv('OPENAI_API_KEY', None)

            # Try HTTP path first (local LM Studio doesn't require an API key)
            try:
                resp_json = _lmstudio_chat_via_http(lm_port, payload, lm_api_key)
            except Exception as http_exc:
                # If HTTP failed and there's no API key, return empty (can't fallback)
                if not lm_api_key:
                    log.error(f"LM Studio HTTP chat failed and no API key available to fallback: {http_exc}")
                    return ""
                # Otherwise try client library (API key available)
                _client = get_lm_client()
                if _client is None:
                    raise RuntimeError('LM client not configured; set settings.lm_studio_api_key or OPENAI_API_KEY')
                response = _client.chat.completions.create(**payload)
                resp_json = response.__dict__ if hasattr(response, '__dict__') else response

            # Robustly extract assistant text from varied LM Studio/OpenAI response shapes
            def _extract_text_from_response(obj) -> str:
                """Extract assistant text from many LM Studio / OpenAI-like shapes.

                This function is intentionally defensive: LM Studio and various adapters
                return content in different keys and nested lists. The extractor tries
                a variety of well-known shapes and falls back to a DFS search for the
                first non-empty string leaf.
                """
                def safe_strip(s):
                    try:
                        return s.strip()
                    except Exception:
                        return s

                def extract_from_primitive(p):
                    if p is None:
                        return ""
                    if isinstance(p, str):
                        return p.strip()
                    if isinstance(p, (int, float)):
                        return str(p)
                    return ""

                def extract_from_dict(d):
                    # Common direct text keys
                    for k in ('content', 'text', 'message', 'output', 'response', 'body'):
                        if k in d:
                            v = d[k]
                            res = extract_any(v)
                            if res:
                                return res

                    # Some LM Studio responses embed content as a list of blocks
                    if 'content' in d and isinstance(d['content'], list):
                        for item in d['content']:
                            # item could be {'type': 'output_text', 'text': '...'}
                            if isinstance(item, dict) and 'text' in item:
                                txt = extract_any(item.get('text'))
                                if txt:
                                    return txt
                            # item could be a primitive string
                            txt = extract_any(item)
                            if txt:
                                return txt

                    # HuggingFace/other shapes: 'parts' or 'segments'
                    for list_key in ('parts', 'segments', 'pieces'):
                        if list_key in d and isinstance(d[list_key], list):
                            parts = []
                            for it in d[list_key]:
                                parts.append(extract_any(it))
                            txt = "\n".join([p for p in parts if p])
                            if txt:
                                return txt

                    # Try any nested value
                    for v in d.values():
                        res = extract_any(v)
                        if res:
                            return res
                    return ""

                def extract_from_list(lst):
                    parts = []
                    for item in lst:
                        res = extract_any(item)
                        if res:
                            parts.append(res)
                    return "\n".join(parts).strip()

                def extract_any(x):
                    if x is None:
                        return ""
                    if isinstance(x, str):
                        return x.strip()
                    if isinstance(x, (int, float)):
                        return str(x)
                    if isinstance(x, dict):
                        return extract_from_dict(x)
                    if isinstance(x, list):
                        return extract_from_list(x)
                    return ""

                try:
                    if not obj:
                        return ""

                    # If response is a raw string
                    if isinstance(obj, str):
                        return obj.strip()

                    # Standard OpenAI-like choices path
                    if isinstance(obj, dict):
                        choices = obj.get('choices')
                        if isinstance(choices, list) and choices:
                            # Try to assemble from choices in order
                            for choice in choices:
                                # common: choice.message.content can be str or dict
                                if isinstance(choice, dict):
                                    # message -> content or parts
                                    msg = choice.get('message')
                                    if msg is not None:
                                        # sometimes message is {'content': [{'type':'output_text','text':'...'}]}
                                        if isinstance(msg, dict):
                                            # First try content key
                                            if 'content' in msg:
                                                res = extract_any(msg['content'])
                                                if res:
                                                    return res
                                            # then possible 'parts'
                                            res = extract_any(msg)
                                            if res:
                                                return res

                                    # streaming delta
                                    delta = choice.get('delta')
                                    if delta:
                                        res = extract_any(delta)
                                        if res:
                                            return res

                                    # other direct keys
                                    for k in ('text', 'output', 'response'):
                                        if k in choice:
                                            res = extract_any(choice[k])
                                            if res:
                                                return res

                        # Some runtimes return 'output' as top-level list
                        out = obj.get('output') or obj.get('results')
                        if isinstance(out, list) and out:
                            for item in out:
                                res = extract_any(item)
                                if res:
                                    return res

                        # data[] path (LLM studio for embeddings or other apis)
                        data = obj.get('data')
                        if isinstance(data, list) and data:
                            for d in data:
                                res = extract_any(d)
                                if res:
                                    return res

                        # fallback common keys
                        for k in ('result', 'response', 'message', 'content'):
                            if k in obj:
                                res = extract_any(obj[k])
                                if res:
                                    return res

                    # Last resort: DFS to find first non-empty string leaf
                    def _find_first_string_leaf(o):
                        if isinstance(o, str) and o.strip():
                            return o.strip()
                        if isinstance(o, dict):
                            for v in o.values():
                                res = _find_first_string_leaf(v)
                                if res:
                                    return res
                        if isinstance(o, list):
                            for it in o:
                                res = _find_first_string_leaf(it)
                                if res:
                                    return res
                        return None

                    leaf = _find_first_string_leaf(obj)
                    return leaf or ""
                except Exception:
                    return ""

            assistant_reply = _extract_text_from_response(resp_json)
            log.info("✅ Respuesta exitosa del modelo (parseada)")

            # If parsing produced no assistant text, dump the raw response (truncated) for debugging
            if not assistant_reply or not str(assistant_reply).strip():
                try:
                    raw = json.dumps(resp_json, ensure_ascii=False)
                except Exception:
                    raw = str(resp_json)
                log.debug(f"RAW LM STUDIO RESPONSE (truncated 2000 chars): {raw[:2000]}")

            # Post-process checks
            def looks_generic(txt: str) -> bool:
                lower = txt.lower()
                generic_markers = [
                    "estoy aquí para ayudarte", "en qué puedo asistirte", "como asistente virtual",
                    "no tengo una identidad", "no tengo identidad", "soy un asistente virtual",
                    "dentro de mis capacidades", "según mis capacidades"
                ]
                return any(m in lower for m in generic_markers)

            def reveals_artificial(txt: str) -> bool:
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
                if txt.strip().startswith('USUARIO') or ' USUARIO ' in txt or txt.endswith('USUARIO'):
                    return True
                if txt.strip().startswith('CHAT ACTUAL:') or 'chat actual:' in lower:
                    return True
                metadata_patterns = ["no aporte", "información previa", "datos de contexto"]
                if any(pattern in lower for pattern in metadata_patterns):
                    return True
                if len(txt.strip()) < 15 and any(word in lower for word in ["ninguno", "fragmentos", "datos"]):
                    return True
                if any(instruction in lower for instruction in ["escribe un mensaje", "proporciona", "genera"]):
                    return True
                return any(m in lower for m in reveal_markers)

            if assistant_reply and (looks_generic(assistant_reply) or reveals_artificial(assistant_reply)):
                log.warning("⚠️ Respuesta problemática detectada (genérica o revela naturaleza artificial). Reintentando.")
            elif assistant_reply and not looks_generic(assistant_reply) and not reveals_artificial(assistant_reply):
                # Good reply — return immediately
                return assistant_reply
                # Build retry payload with corrective system
                corrective_system = {"role": "system", "content": (
                    "CORRECCIÓN URGENTE: La respuesta anterior fue inaceptable. Reintenta siguiendo las reglas sin prefijos técnicos."
                )}
                retry_payload = base_payload.copy()
                retry_payload["model"] = payload.get("model")
                retry_payload["temperature"] = payload.get("temperature", 0.7)
                retry_payload["max_tokens"] = payload.get("max_tokens", 512)
                systems = [m for m in payload["messages"] if m.get("role") == "system"]
                last_user = None
                for m in reversed(payload["messages"]):
                    if m.get("role") == "user":
                        last_user = m
                        break
                retry_msgs = systems[-3:]
                retry_msgs.append(corrective_system)
                if last_user:
                    retry_msgs.append(last_user)
                retry_payload["messages"] = retry_msgs

                # Attempt retry via HTTP first, fallback to client only if API key exists
                try:
                    try:
                        resp2 = _lmstudio_chat_via_http(lm_port, retry_payload, lm_api_key)
                    except Exception as http_exc2:
                        if not lm_api_key:
                            log.error(f"LM Studio HTTP retry failed and no API key available to fallback: {http_exc2}")
                            return ""
                        _client = get_lm_client()
                        if _client is None:
                            raise RuntimeError('LM client not configured; set settings.lm_studio_api_key or OPENAI_API_KEY')
                        response2 = _client.chat.completions.create(**retry_payload)
                        resp2 = response2.__dict__ if hasattr(response2, '__dict__') else response2

                    # Use the same robust extractor for the retry response
                    assistant_reply2 = _extract_text_from_response(resp2)
                    if not assistant_reply2 or not str(assistant_reply2).strip():
                        try:
                            raw2 = json.dumps(resp2, ensure_ascii=False)
                        except Exception:
                            raw2 = str(resp2)
                        log.debug(f"RAW LM STUDIO RETRY RESPONSE (truncated 2000 chars): {raw2[:2000]}")

                    if assistant_reply2 and not looks_generic(assistant_reply2) and not reveals_artificial(assistant_reply2):
                        log.info("✅ Reintento correctivo exitoso")
                        return assistant_reply2
                    # else fallthrough to emergency responses below
                except Exception as re_err:
                    log.error(f"❌ Error en reintento correctivo: {re_err}")

                # Emergency human-friendly fallback
                last_user_msg = last_user.get("content", "").lower() if last_user else ""
                if "que te gusta" in last_user_msg or "qué te gusta" in last_user_msg:
                    return "Me gusta hacer muchas cosas: ejercicio, bailar y escuchar música. ¿Y tú?"
                if "quien eres" in last_user_msg or "quién eres" in last_user_msg:
                    return "Soy Andrés, ingeniero y docente. ¿Y tú?"
                if len(last_user_msg.strip()) < 10:
                    return "¡Hola! ¿Cómo estás? Cuéntame algo sobre ti."
                return ""
        except Exception as e:
            error_msg = str(e)
            log.error(f"❌ Error enviando al modelo: {error_msg}")
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

    # Ensure we always return a string on all code paths
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Función auxiliar para tests locales
# ──────────────────────────────────────────────────────────────────────────────
def test_connection():
    """Test básico de conexión con LM Studio"""
    try:
        _client = get_lm_client()
        if _client is None:
            raise RuntimeError('LM client not configured; set settings.lm_studio_api_key or OPENAI_API_KEY')
        models = _client.models.list()
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
