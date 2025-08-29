import os
import time
import logging
import traceback
import chat_sessions

# Configurar logger
log = logging.getLogger(__name__)

# Registro de último envío
LAST_REPLIED_AT = {}


def fetch_new_message_simple(page, respond_to_all=False):
    """Versión simplificada que SOLO responde si hay badge numérico visible y último mensaje es del usuario"""
    log.debug("→ Entrando a fetch_new_message_simple()")
    log.debug(f"→ respond_to_all = {respond_to_all}")
    
    try:
        page.wait_for_selector("#pane-side", timeout=5000)
        grid = page.locator("#pane-side")
        rows = grid.locator("div[role='listitem'], div[role='row']")
        count = rows.count()
        log.debug(f"– Rows totales en el grid: {count}")
        
        for i in range(count):
            row = rows.nth(i)
            
            # 1. SOLO buscar números visibles - no aria-labels ni estilos
            unread_count = 0
            all_spans = row.locator("span").all()
            
            for span in all_spans:
                try:
                    text = span.inner_text().strip()
                    if text.isdigit() and int(text) > 0:
                        unread_count = int(text)
                        log.info(f"– Row #{i} badge numérico encontrado: {unread_count}")
                        break
                except Exception:
                    continue
            
            # REQUISITO: debe haber número > 0
            if unread_count <= 0:
                continue
                
            # 2. Extraer chat_id
            chat_id = None
            chat_strategies = [
                "span[title]",
                "[data-id] span", 
                "span[dir='auto']"
            ]
            
            for strategy in chat_strategies:
                elements = row.locator(strategy)
                if elements.count() > 0:
                    title_attr = elements.first.get_attribute("title")
                    if title_attr and title_attr.strip():
                        chat_id = title_attr.strip()
                        break
                    text_content = elements.first.inner_text().strip()
                    if text_content and len(text_content) > 3:
                        chat_id = text_content
                        break
            
            if not chat_id:
                log.debug(f"– Row #{i} sin chat_id válido")
                continue
                
            # 3. Verificar cooldown anti-bucle
            try:
                import time as _t
                last_t = LAST_REPLIED_AT.get(chat_id)
                if last_t and (_t.time() - last_t) < 60:  # 60 segundos
                    log.info(f"– {chat_id!r} respondido hace <60s ⇒ saltar")
                    continue
            except Exception:
                pass
                
            # 4. Verificar permisos
            try:
                if not respond_to_all:
                    require = os.getenv("REQUIRE_CONTACT_PROFILE", "true").lower() == "true"
                    if require and not chat_sessions.is_ready_to_reply(chat_id):
                        log.info(f"– {chat_id!r} no habilitado ⇒ saltar")
                        continue
                else:
                    log.info(f"– respond_to_all=True, abriendo {chat_id!r}")
            except Exception:
                log.exception("– Error verificando permisos")
                continue
                
            # 5. Abrir chat y verificar último mensaje
            try:
                row.click()
                log.info(f"– Click en conversación {chat_id!r}")
                page.wait_for_timeout(1000)  # Dar tiempo a cargar
            except Exception as e:
                log.error(f"– Error abriendo chat: {e}")
                continue
                
            # 6. Verificar que el último mensaje NO sea del bot
            try:
                # Buscar el último mensaje
                message_containers = page.locator("div[data-testid='msg-container']")
                if message_containers.count() == 0:
                    # Fallback
                    message_containers = page.locator("div.message-in, div.message-out")
                
                if message_containers.count() > 0:
                    last_msg = message_containers.last
                    
                    # Verificar si es mensaje saliente (del bot)
                    is_outgoing = False
                    try:
                        # Buscar indicadores de mensaje saliente
                        outgoing_indicators = last_msg.locator("[data-testid*='outgoing'], .message-out")
                        if outgoing_indicators.count() > 0:
                            is_outgoing = True
                        else:
                            # Verificar por clases CSS
                            classes = last_msg.get_attribute("class") or ""
                            if "message-out" in classes or "outgoing" in classes:
                                is_outgoing = True
                    except Exception:
                        pass
                    
                    if is_outgoing:
                        log.info(f"– {chat_id!r} último mensaje es del bot ⇒ no responder")
                        continue
                        
                    # Extraer texto del último mensaje
                    try:
                        text_element = last_msg.locator("span.selectable-text").first
                        if text_element.count() > 0:
                            incoming = text_element.inner_text().strip()
                        else:
                            incoming = "[mensaje detectado]"
                    except Exception:
                        incoming = "[mensaje detectado]"
                        
                    log.info(f"– {chat_id!r} último mensaje del usuario: {incoming!r}")
                    return chat_id, incoming
                else:
                    log.warning(f"– {chat_id!r} no se encontraron mensajes")
                    continue
                    
            except Exception as e:
                log.error(f"– Error verificando mensajes en {chat_id!r}: {e}")
                continue
        
        log.debug("– No hay chats con badges numéricos válidos")
        return None, None
        
    except Exception:
        log.error("¡Exception en fetch_new_message_simple()!", exc_info=True)
        return None, None
