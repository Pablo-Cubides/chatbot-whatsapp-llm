"""
📱 Sistema de WhatsApp Mejorado
Integración completa con configuración de negocio y multi-API
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from playwright.async_api import async_playwright
import re

logger = logging.getLogger(__name__)

class WhatsAppManager:
    def __init__(self, business_config_manager=None, multi_llm=None, analytics_manager=None):
        self.business_config = business_config_manager
        self.multi_llm = multi_llm
        self.analytics = analytics_manager
        self.browser = None
        self.page = None
        self.is_running = False
        self.active_chats = {}
        
    async def start(self) -> Dict[str, Any]:
        """Iniciar el sistema de WhatsApp"""
        try:
            if self.is_running:
                return {"success": False, "message": "WhatsApp bot ya está ejecutándose"}
            
            logger.info("Iniciando WhatsApp bot...")
            
            # Iniciar browser
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=False)
            self.page = await self.browser.new_page()
            
            # Ir a WhatsApp Web
            await self.page.goto("https://web.whatsapp.com/")
            
            # Esperar a que se cargue
            await self.page.wait_for_selector('[data-testid="chat-list"]', timeout=30000)
            
            # Configurar listeners de mensajes
            await self._setup_message_listeners()
            
            self.is_running = True
            logger.info("WhatsApp bot iniciado exitosamente")
            
            # Registrar métrica
            if self.analytics:
                self.analytics.record_metric("whatsapp_bot_start", 1, {"timestamp": datetime.now().isoformat()})
            
            return {
                "success": True, 
                "message": "WhatsApp bot iniciado exitosamente",
                "status": "running",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error iniciando WhatsApp bot: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def stop(self) -> Dict[str, Any]:
        """Detener el sistema de WhatsApp"""
        try:
            if not self.is_running:
                return {"success": False, "message": "WhatsApp bot no está ejecutándose"}
            
            if self.browser:
                await self.browser.close()
            
            self.is_running = False
            self.active_chats.clear()
            
            # Registrar métrica
            if self.analytics:
                self.analytics.record_metric("whatsapp_bot_stop", 1, {"timestamp": datetime.now().isoformat()})
            
            logger.info("WhatsApp bot detenido")
            return {
                "success": True, 
                "message": "WhatsApp bot detenido exitosamente",
                "status": "stopped"
            }
            
        except Exception as e:
            logger.error(f"Error deteniendo WhatsApp bot: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def _setup_message_listeners(self):
        """Configurar listeners para mensajes nuevos"""
        await self.page.evaluate("""
            () => {
                // Función para detectar mensajes nuevos
                const observer = new MutationObserver(mutations => {
                    mutations.forEach(mutation => {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1 && node.classList && 
                                node.classList.contains('message-in')) {
                                // Nuevo mensaje entrante detectado
                                window.newMessage = {
                                    timestamp: Date.now(),
                                    element: node
                                };
                            }
                        });
                    });
                });
                
                const chatContainer = document.querySelector('[data-testid="conversation-panel-messages"]');
                if (chatContainer) {
                    observer.observe(chatContainer, { childList: true, subtree: true });
                }
            }
        """)
        
        # Loop para procesar mensajes
        asyncio.create_task(self._message_processing_loop())
    
    async def _message_processing_loop(self):
        """Loop principal para procesar mensajes"""
        while self.is_running:
            try:
                # Verificar mensajes nuevos
                new_message = await self.page.evaluate("window.newMessage")
                
                if new_message:
                    await self._process_incoming_message()
                    await self.page.evaluate("window.newMessage = null")
                
                await asyncio.sleep(1)  # Check cada segundo
                
            except Exception as e:
                logger.error(f"Error en loop de mensajes: {e}")
                await asyncio.sleep(5)
    
    async def _process_incoming_message(self):
        """Procesar mensaje entrante"""
        try:
            # Obtener información del chat actual
            chat_info = await self._get_current_chat_info()
            if not chat_info:
                return
            
            contact_name = chat_info.get("name")
            message_text = chat_info.get("last_message")
            
            if not message_text or not contact_name:
                return
            
            # Verificar si ya procesamos este mensaje
            message_id = f"{contact_name}_{hash(message_text)}"
            if message_id in self.active_chats.get(contact_name, {}).get("processed_messages", set()):
                return
            
            logger.info(f"Procesando mensaje de {contact_name}: {message_text}")
            
            # Inicializar chat si es necesario
            if contact_name not in self.active_chats:
                self.active_chats[contact_name] = {
                    "messages": [],
                    "started_at": datetime.now(),
                    "processed_messages": set(),
                    "session_id": f"wa_{contact_name}_{int(datetime.now().timestamp())}"
                }
                
                # Registrar nueva conversación
                if self.analytics:
                    self.analytics.record_conversation_start(
                        self.active_chats[contact_name]["session_id"],
                        contact_name
                    )
            
            # Agregar mensaje procesado
            self.active_chats[contact_name]["processed_messages"].add(message_id)
            self.active_chats[contact_name]["messages"].append({
                "role": "user",
                "content": message_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Generar respuesta
            response = await self._generate_response(contact_name, message_text)
            
            if response:
                # Enviar respuesta
                await self._send_message(response)
                
                # Agregar respuesta al historial
                self.active_chats[contact_name]["messages"].append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Respuesta enviada a {contact_name}: {response[:100]}...")
        
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
    
    async def _get_current_chat_info(self) -> Optional[Dict[str, Any]]:
        """Obtener información del chat actual"""
        try:
            return await self.page.evaluate("""
                () => {
                    // Obtener nombre del contacto
                    const headerElement = document.querySelector('[data-testid="conversation-header"]');
                    const nameElement = headerElement ? headerElement.querySelector('span[title]') : null;
                    const contactName = nameElement ? nameElement.getAttribute('title') : null;
                    
                    // Obtener último mensaje
                    const messages = document.querySelectorAll('[data-testid="msg-container"]');
                    const lastMessage = messages[messages.length - 1];
                    const messageText = lastMessage ? lastMessage.querySelector('.copyable-text span')?.textContent : null;
                    
                    return {
                        name: contactName,
                        last_message: messageText,
                        message_count: messages.length
                    };
                }
            """)
        except:
            return None
    
    async def _generate_response(self, contact_name: str, message_text: str) -> Optional[str]:
        """Generar respuesta usando la configuración actual"""
        try:
            # Obtener configuración de negocio
            if not self.business_config:
                return "Gracias por tu mensaje. Te responderemos pronto."
            
            config = self.business_config.config
            business_info = config.get('business_info', {})
            
            # Construir contexto para la IA
            context_messages = [
                {
                    "role": "system",
                    "content": self.business_config._build_main_prompt(config)
                }
            ]
            
            # Agregar historial reciente del chat
            chat_history = self.active_chats.get(contact_name, {}).get("messages", [])
            recent_messages = chat_history[-10:]  # Últimos 10 mensajes
            context_messages.extend(recent_messages)
            
            # Agregar mensaje actual
            context_messages.append({
                "role": "user", 
                "content": message_text
            })
            
            # Generar respuesta con Multi-API
            if self.multi_llm:
                start_time = datetime.now()
                response = await self.multi_llm.generate_response(
                    messages=context_messages,
                    max_tokens=150,  # Respuesta concisa para WhatsApp
                    temperature=0.7
                )
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Registrar uso de API
                if self.analytics:
                    self.analytics.record_api_usage(
                        api_provider="multi_llm",
                        endpoint="generate_response", 
                        tokens_used=len(response.split()),
                        response_time_ms=int(response_time),
                        success=True
                    )
                
                return response
            else:
                # Respuesta de fallback usando configuración
                greeting = business_info.get('greeting', '¡Hola!')
                return f"{greeting} Gracias por contactarnos. Te ayudo enseguida."
        
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            
            # Registrar error en analytics
            if self.analytics:
                self.analytics.record_api_usage(
                    api_provider="multi_llm",
                    endpoint="generate_response",
                    tokens_used=0,
                    response_time_ms=0,
                    success=False,
                    error_message=str(e)
                )
            
            return "Disculpa, estamos experimentando dificultades técnicas. Un representante te contactará pronto."
    
    async def _send_message(self, message: str) -> bool:
        """Enviar mensaje por WhatsApp"""
        try:
            # Hacer clic en el campo de texto
            message_input = await self.page.wait_for_selector('[data-testid="msg-input"]')
            await message_input.click()
            
            # Escribir mensaje
            await message_input.type(message)
            
            # Enviar mensaje
            send_button = await self.page.wait_for_selector('[data-testid="send"]')
            await send_button.click()
            
            await asyncio.sleep(1)  # Esperar a que se envíe
            return True
            
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado actual del sistema"""
        return {
            "is_running": self.is_running,
            "active_chats": len(self.active_chats),
            "total_messages": sum(len(chat["messages"]) for chat in self.active_chats.values()),
            "uptime_seconds": (datetime.now() - min(
                (chat["started_at"] for chat in self.active_chats.values()), 
                default=datetime.now()
            )).total_seconds() if self.active_chats else 0,
            "chats": {
                name: {
                    "message_count": len(chat["messages"]),
                    "started_at": chat["started_at"].isoformat(),
                    "last_activity": chat["messages"][-1]["timestamp"] if chat["messages"] else None
                } for name, chat in self.active_chats.items()
            }
        }

# Instancia global que se inicializará en el admin panel
whatsapp_manager = None
