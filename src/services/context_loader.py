"""
📦 Context Loader Service
Sistema unificado para cargar y preparar todos los contextos relevantes
para inyección en prompts de LLM
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


class ContextLoader:
    """Carga y gestiona contextos para inyección en prompts"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutos
    
    def load_all_contexts(self, chat_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Carga todos los contextos relevantes para una conversación
        
        Args:
            chat_id: ID del chat/conversación
            user_id: ID del usuario (opcional, usa chat_id si no se proporciona)
            
        Returns:
            Dict con todos los contextos disponibles
        """
        user_id = user_id or chat_id
        
        contexts = {
            'chat_id': chat_id,
            'user_id': user_id,
            'loaded_at': datetime.utcnow().isoformat(),
            'daily_context': self.load_daily_context(),
            'user_contexts': self.load_user_contexts(user_id),
            'contact_profile': self.load_contact_profile(chat_id),
            'active_strategy': self.load_active_strategy(chat_id),
            'contact_objective': None,  # Se carga desde contact_profile
        }
        
        # Extraer objetivo del perfil si existe
        if contexts['contact_profile']:
            contexts['contact_objective'] = contexts['contact_profile'].get('objective')
        
        return contexts
    
    def load_daily_context(self) -> Optional[Dict[str, Any]]:
        """Carga el contexto diario activo"""
        try:
            from admin_db import get_session
            from models import DailyContext
            
            session = get_session()
            today = date.today()
            
            # Buscar contexto para hoy
            daily = session.query(DailyContext).filter(
                DailyContext.effective_date == today
            ).first()
            
            if daily:
                result = {
                    'id': daily.id,
                    'text': daily.text,
                    'effective_date': str(daily.effective_date),
                    'source': daily.source
                }
                session.close()
                return result
            
            session.close()
            return None
            
        except Exception as e:
            logger.warning(f"Error cargando contexto diario: {e}")
            return None
    
    def load_user_contexts(self, user_id: str) -> List[Dict[str, Any]]:
        """Carga contextos específicos del usuario"""
        try:
            from admin_db import get_session
            from models import UserContext
            
            session = get_session()
            
            contexts = session.query(UserContext).filter(
                UserContext.user_id == user_id
            ).order_by(UserContext.created_at.desc()).limit(5).all()
            
            result = []
            for ctx in contexts:
                result.append({
                    'id': ctx.id,
                    'text': ctx.text,
                    'source': ctx.source,
                    'created_at': ctx.created_at.isoformat() if ctx.created_at else None
                })
            
            session.close()
            return result
            
        except Exception as e:
            logger.warning(f"Error cargando contextos de usuario: {e}")
            return []
    
    def load_contact_profile(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Carga el perfil del contacto con objetivo y contexto inicial"""
        try:
            from admin_db import get_session
            from models import ChatProfile, AllowedContact
            
            session = get_session()
            
            # Intentar ChatProfile primero
            profile = session.query(ChatProfile).filter(
                ChatProfile.chat_id == chat_id
            ).first()
            
            if profile:
                result = {
                    'chat_id': profile.chat_id,
                    'initial_context': profile.initial_context,
                    'objective': profile.objective,
                    'instructions': profile.instructions,
                    'perfil': getattr(profile, 'perfil', None)
                }
                session.close()
                return result
            
            # Fallback a AllowedContact
            allowed = session.query(AllowedContact).filter(
                AllowedContact.chat_id == chat_id
            ).first()
            
            if allowed:
                result = {
                    'chat_id': allowed.chat_id,
                    'initial_context': getattr(allowed, 'initial_context', None),
                    'objective': getattr(allowed, 'objective', None),
                    'instructions': getattr(allowed, 'instructions', None),
                    'perfil': getattr(allowed, 'perfil', None)
                }
                session.close()
                return result
            
            session.close()
            return None
            
        except Exception as e:
            logger.warning(f"Error cargando perfil de contacto: {e}")
            return None
    
    def load_active_strategy(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Carga la estrategia activa para el chat"""
        try:
            from chat_sessions import get_active_strategy
            
            strategy = get_active_strategy(chat_id)
            
            if strategy:
                return {
                    'version': strategy.version,
                    'strategy_text': strategy.strategy_text,
                    'activated_at': strategy.activated_at.isoformat() if strategy.activated_at else None
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error cargando estrategia activa: {e}")
            return None
    
    def build_context_prompt_section(self, contexts: Dict[str, Any]) -> str:
        """
        Construye la sección de contexto para inyectar en el prompt
        
        Args:
            contexts: Dict de contextos cargados
            
        Returns:
            String formateado para agregar al prompt
        """
        sections = []
        
        # Contexto diario (promociones, eventos, etc)
        if contexts.get('daily_context'):
            daily = contexts['daily_context']
            sections.append(f"""CONTEXTO DEL DÍA ({daily.get('effective_date', 'hoy')}):
{daily.get('text', '')}""")
        
        # Objetivo del contacto (CRÍTICO para la estrategia)
        if contexts.get('contact_objective'):
            sections.append(f"""OBJETIVO CON ESTE CLIENTE (IMPORTANTE):
{contexts['contact_objective']}
- Cada mensaje debe acercarte a este objetivo
- Evalúa el progreso y ajusta tu enfoque""")
        
        # Perfil del contacto
        if contexts.get('contact_profile'):
            profile = contexts['contact_profile']
            profile_parts = []
            
            if profile.get('perfil'):
                profile_parts.append(f"Perfil: {profile['perfil']}")
            if profile.get('initial_context'):
                profile_parts.append(f"Contexto: {profile['initial_context']}")
            if profile.get('instructions'):
                profile_parts.append(f"Instrucciones específicas: {profile['instructions']}")
            
            if profile_parts:
                sections.append("INFORMACIÓN DEL CLIENTE:\n" + "\n".join(profile_parts))
        
        # Estrategia activa
        if contexts.get('active_strategy'):
            strategy = contexts['active_strategy']
            sections.append(f"""ESTRATEGIA OPERATIVA (v{strategy.get('version', '?')}):
{strategy.get('strategy_text', 'Sin estrategia definida')}""")
        
        # Contextos adicionales del usuario
        if contexts.get('user_contexts') and len(contexts['user_contexts']) > 0:
            user_ctx_texts = [ctx['text'] for ctx in contexts['user_contexts'][:3]]
            if user_ctx_texts:
                sections.append("NOTAS SOBRE EL USUARIO:\n- " + "\n- ".join(user_ctx_texts))
        
        if not sections:
            return ""
        
        return "\n\n".join(sections)
    
    def should_inject_contexts(self, chat_id: str) -> bool:
        """Determina si se deben inyectar contextos (evita inyectar en cada mensaje)"""
        # Por ahora, siempre inyectar. Se puede optimizar después.
        return True


# Instancia global
context_loader = ContextLoader()
