# Chatbot WhatsApp con LLM

Un bot de conversación inteligente para WhatsApp Web que utiliza modelos de lenguaje grandes (LLM) para mantener conversaciones naturales y fluidas.

## 🚀 Características

- **Automatización de WhatsApp Web**: Detecta mensajes entrantes automáticamente usando Playwright
- **Integración con LLM**: Compatible con LM Studio y modelos OpenAI para respuestas inteligentes
- **Panel de Administración Web**: Interfaz web para configurar y monitorear el bot
- **Gestión de Contactos**: Control granular sobre qué contactos pueden recibir respuestas
- **Múltiples Modos de Conversación**: Conversacional, razonador y otros estilos personalizables
- **Logging Detallado**: Sistema completo de logs para monitoreo y debugging

## 📋 Requisitos

- Python 3.8+
- LM Studio o acceso a API de OpenAI
- Navegador Chrome/Chromium
- WhatsApp Web

## 🛠️ Instalación

1. **Clona el repositorio**:
```bash
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
```

2. **Instala las dependencias**:
```bash
pip install -r requirements.txt
```

3. **Instala Playwright**:
```bash
playwright install chromium
```

## ⚙️ Configuración

1. **LM Studio**: Asegúrate de tener LM Studio ejecutándose en `http://localhost:1234`

2. **WhatsApp Web**: El bot necesitará acceso a WhatsApp Web. La primera ejecución requerirá escanear un código QR.

3. **Panel de Administración**: Ejecuta el panel web:
```bash
python admin_panel.py
```
Luego ve a `http://localhost:8001` para configurar el bot.

## 🚀 Uso

1. **Iniciar el Bot**:
```bash
python whatsapp_automator.py
```

2. **Configurar Contactos**: Usa el panel de administración para habilitar/deshabilitar contactos específicos.

3. **Personalizar Prompts**: Ajusta los prompts de conversación según tus necesidades.

## 📁 Estructura del Proyecto

```
├── whatsapp_automator.py  # Script principal de automatización
├── admin_panel.py         # Panel de administración web
├── chat_sessions.py       # Gestión de sesiones y contactos
├── stub_chat.py          # Integración con LLM
├── rag_utils.py          # Utilidades para recuperación de información
├── web_ui/               # Interfaz web del panel de administración
├── config/               # Archivos de configuración
├── data/                 # Datos y configuraciones
└── logs/                 # Archivos de log del sistema
```

## 🔧 Características Técnicas

- **Detección Robusta de Mensajes**: Múltiples estrategias para detectar badges de mensajes no leídos
- **Manejo de Errores**: Sistema completo de manejo de excepciones y recuperación
- **Configuración Flexible**: Soporte para múltiples tipos de prompt y configuraciones
- **Escalabilidad**: Diseñado para manejar múltiples conversaciones simultáneas

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -am 'Agrega nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🆘 Soporte

Si encuentras algún problema o tienes preguntas, por favor abre un issue en GitHub.

## ⚠️ Disclaimer

Este bot está diseñado para uso personal y educativo. Asegúrate de cumplir con los términos de servicio de WhatsApp al usarlo.
