# 🤖 Chatbot WhatsApp con LLM

Un chatbot inteligente para WhatsApp Web que utiliza modelos de lenguaje grandes (LLM) para mantener conversaciones naturales y fluidas. Incluye un panel de administración web completo y arquitectura de doble agente (conversacional + razonador estratégico).

## 🚨 INICIO RÁPIDO PARA DESARROLLO

### ⚠️ IMPORTANTE: Orden de Inicio Correcto
```bash
# ❌ NUNCA iniciar directamente con:
python whatsapp_automator.py
python local_chat.py

# ✅ SIEMPRE iniciar con:
python clean_start.py
```

### 🛠️ Utilidades de Desarrollo
```bash
# Preparar entorno (limpiar logs + análisis)
python dev_utils.py prep

# Limpiar logs (mantener últimas 50 líneas)
python dev_utils.py clean

# Ver logs recientes
python dev_utils.py show

# Analizar problemas en logs
python dev_utils.py analyze
```

📖 **Ver instrucciones completas:** [DEV_INSTRUCTIONS.md](DEV_INSTRUCTIONS.md)

---

## ✨ Características Principales

### 🚀 **Automatización de WhatsApp Web**
- **Detección automática** de mensajes entrantes usando Playwright
- **Navegación robusta** con múltiples estrategias de selección de elementos
- **Gestión de sesiones** persistentes con perfiles de navegador
- **Manejo de errores** avanzado con recuperación automática

### 🧠 **Integración con LLM**
- **Compatible con LM Studio** para modelos locales
- **Soporte para OpenAI API** (GPT-3.5, GPT-4, etc.)
- **Cambio dinámico de modelos** desde el panel de administración
- **Configuración flexible** de temperatura, max_tokens y otros parámetros

### 👥 **Gestión Inteligente de Contactos**
- **Lista de contactos permitidos** con control granular
- **Contextos personalizados** por cada chat/contacto
- **Perfiles de conversación** con objetivos específicos
- **Base de datos** para almacenamiento persistente de configuraciones

### 🎯 **Sistema de Doble Agente**
- **Agente Conversacional**: Responde mensajes en tiempo real
- **Agente Razonador**: Analiza conversaciones y genera estrategias
- **Estrategias adaptivas** que evolucionan según el contexto
- **Activación automática** del razonador cada N mensajes

### 📊 **Panel de Administración Web**
- **Dashboard moderno** en `http://localhost:8001`
- **Control de modelos LLM** con detección automática
- **Editor de archivos** para prompts y contextos
- **Monitoreo en tiempo real** del estado del sistema
- **Inicio/parada remota** de servicios
- **API RESTful** completa para integración

### 🚀 Cómo Empezar

1.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configurar el entorno**:
    - Asegúrate de tener LM Studio corriendo con un modelo cargado en `http://localhost:1234`.
    - O configura tus credenciales de OpenAI si prefieres usar su API.
3.  **Iniciar la aplicación**:
    Para un inicio limpio que reinicia ciertos estados, utiliza el script `clean_start.py`:
    ```powershell
    python ./clean_start.py
    ```
    Esto lanzará el panel de administración y el automator de WhatsApp.

## 📋 Requisitos del Sistema

### Software Necesario
- **Python 3.8+** (recomendado 3.9 o superior)
- **LM Studio** o acceso a OpenAI API
- **Navegador Chromium** (instalado automáticamente con Playwright)
- **WhatsApp Web** activo

### Dependencias Python
```
playwright==1.51.0
openai==1.52.0
fastapi>=0.100.0
uvicorn>=0.20.0
sqlalchemy>=2.0.0
cryptography>=43.0.0
APScheduler==3.11.0
psutil>=5.9.0
requests>=2.32.0
python-dotenv>=1.1.0
```

## 🛠️ Instalación y Configuración

### 1. **Clonar el Repositorio**
```bash
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
```

### 2. **Crear Entorno Virtual (Recomendado)**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. **Instalar Dependencias**
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. **Configurar LM Studio**
1. Descargar e instalar [LM Studio](https://lmstudio.ai/)
2. Cargar un modelo (ej: `phi-4-Q4_K_M`, `llama-3.2-3b`, etc.)
3. Iniciar el servidor local en puerto `1234`
4. Verificar que responde en `http://localhost:1234/v1/models`

### 5. **Configuración Inicial**
```bash
# Crear directorios necesarios
mkdir -p data logs config contextos Docs

# Configurar archivo de configuración de Playwright
cp config/playwright_config.json.example config/playwright_config.json
```

## ⚙️ Configuración Avanzada

### Variables de Entorno (Opcional)
Crear archivo `.env`:
```env
# LM Studio
LM_STUDIO_PORT=1234
LM_STUDIO_EXE=D:/IA/Texto/Lmstudio/LM Studio.exe

# Rutas personalizadas
MODELS_DIR=D:/IA/Texto/Models
REASONER_PAYLOAD_PATH=./payload_reasoner.json

# Configuración del bot
KEEP_AUTOMATOR_OPEN=true
```

### Archivos de Configuración

#### `config/playwright_config.json`
```json
{
  "headless": false,
  "userDataDir": "$HOME/whatsapp-profile",
  "viewport": {"width": 1280, "height": 720},
  "args": ["--no-first-run", "--disable-blink-features=AutomationControlled"]
}
```

#### `payload.json` - Configuración del modelo principal
```json
{
  "model": "phi-4-Q4_K_M",
  "messages": [],
  "temperature": 0.7,
  "max_tokens": 512,
  "stream": false
}
```

#### `payload_reasoner.json` - Configuración del modelo razonador
```json
{
  "model": "phi-4-Q4_K_M",
  "messages": [],
  "temperature": 0.3,
  "max_tokens": 1024,
  "stream": false
}
```

## 🚀 Uso del Sistema

### 1. **Iniciar Panel de Administración**
```bash
python admin_panel.py
```
Acceder a: `http://localhost:8001/ui/index.html`

### 2. **Configurar Contactos Permitidos**
En el panel web:
1. Ir a la sección "Gestión de Contactos"
2. Agregar números de WhatsApp (formato: `573XXXXXXXXX`)
3. Configurar contexto y objetivos específicos

### 3. **Iniciar Automatización de WhatsApp**
```bash
python whatsapp_automator.py
```
O desde el panel web: "Control de WhatsApp" → "Iniciar"

### 4. **Escanear QR de WhatsApp**
1. El navegador se abrirá en WhatsApp Web
2. Escanear código QR con la app móvil
3. El bot comenzará a monitorear mensajes automáticamente

## 📁 Estructura del Proyecto

```
chatbot-whatsapp-llm/
├── 🤖 Automatización Principal
│   ├── whatsapp_automator.py      # Motor principal de automatización
│   ├── stub_chat.py               # Integración con LLM
│   └── reasoner.py                # Sistema de razonamiento estratégico
│
├── 🎛️ Panel de Administración
│   ├── admin_panel.py             # API FastAPI del panel
│   ├── admin_db.py                # Gestión de base de datos
│   └── web_ui/index.html          # Interfaz web moderna
│
├── 📊 Gestión de Datos
│   ├── models.py                  # Modelos SQLAlchemy
│   ├── chat_sessions.py           # Sesiones de chat
│   ├── crypto.py                  # Cifrado de datos sensibles
│   └── model_manager.py           # Gestor de modelos LLM
│
├── ⚙️ Configuración
│   ├── config/playwright_config.json
│   ├── payload.json               # Config modelo principal
│   ├── payload_reasoner.json      # Config modelo razonador
│   └── requirements.txt
│
├── 📂 Datos del Sistema
│   ├── data/                      # Configuraciones y claves
│   ├── logs/                      # Archivos de log
│   ├── contextos/                 # Contextos por chat
│   └── Docs/                      # Documentos de referencia
│
└── 🧪 Testing
    ├── test_complete_system.py    # Tests integrales
    ├── test_with_lmstudio.py      # Tests con LM Studio
    └── tests/test_model_manager.py # Tests unitarios
```

## 🔧 API del Panel de Administración

### Endpoints Principales

#### **Gestión de Modelos**
```bash
GET  /api/lmstudio/models          # Listar modelos disponibles
POST /api/lmstudio/server/start    # Iniciar servidor LM Studio
POST /api/lmstudio/load            # Cargar modelo específico
PUT  /api/current-model            # Cambiar modelo activo
```

#### **Control de WhatsApp**
```bash
GET  /api/whatsapp/status          # Estado del automator
POST /api/whatsapp/start           # Iniciar automatización
POST /api/whatsapp/stop            # Detener automatización
```

#### **Gestión de Contactos**
```bash
GET  /api/allowed-contacts         # Listar contactos permitidos
POST /api/allowed-contacts         # Agregar nuevo contacto
GET  /api/chats/{chat_id}          # Obtener contexto de chat
PUT  /api/chats/{chat_id}          # Actualizar contexto
```

#### **Configuración**
```bash
GET/PUT /api/settings              # Configuraciones generales
GET/PUT /api/prompts              # Prompts del sistema
GET/PUT /api/files/{filename}     # Archivos de contexto
```

## 🎯 Configuración de Prompts

### Prompt Conversacional
Define cómo responde el bot en conversaciones normales:
```text
Eres un asistente conversacional amigable y útil. 
Responde de manera natural y mantén un tono profesional pero cercano.
Adapta tus respuestas al contexto de la conversación.
```

### Prompt del Razonador
Define cómo analiza y genera estrategias:
```text
Analiza la conversación actual y genera una estrategia operativa específica
para los próximos 10 mensajes. Considera el perfil del usuario, el objetivo
de la conversación y el contexto histórico.
```

## 📊 Monitoreo y Logs

### Archivos de Log
- `logs/automation.log` - Log principal del automator
- `logs/admin_panel.log` - Log del panel de administración
- `logs/debug/` - Logs detallados de debugging

### Dashboard de Estado
El panel web muestra en tiempo real:
- ✅ Estado de LM Studio (conectado/desconectado)
- ✅ Estado del automator (activo/inactivo)
- ✅ Modelo LLM actual
- ✅ Número de contactos configurados
- ✅ Estadísticas de conversaciones

## 🔒 Seguridad y Privacidad

### Características de Seguridad
- **Cifrado de datos sensibles** usando Fernet (cryptography)
- **Token de autenticación** para API del panel
- **Filtrado de números** en logs para privacidad
- **Aislamiento de procesos** entre automator y panel

### Recomendaciones
- Cambiar el token por defecto `admintoken` en producción
- Configurar firewall para puerto 8001 en entornos públicos
- Revisar regularmente los logs por actividad inusual
- Hacer backup de la carpeta `data/` periódicamente

## 🔄 Flujo de Operación

### 1. **Detección de Mensajes**
```mermaid
WhatsApp Web → Playwright → Detección de Badge → Extracción de Texto
```

### 2. **Procesamiento de Respuesta**
```mermaid
Mensaje → Verificar Contacto → LLM Principal → Respuesta
                   ↓
            Cada N mensajes → Razonador → Nueva Estrategia
```

### 3. **Gestión de Estrategias**
```mermaid
Historial → Análisis → Estrategia → Aplicación → Evaluación
```

## 🧪 Testing y Validación

### Ejecutar Tests
```bash
# Test completo del sistema
python test_complete_system.py

# Test específico de LM Studio
python test_with_lmstudio.py

# Tests unitarios
pytest tests/ -v
```

### Validación Manual
```bash
# Test de conexión LM Studio
curl http://localhost:1234/v1/models

# Test del panel de administración
curl http://localhost:8001/healthz

# Test de respuesta del bot
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "test", "message": "Hola"}'
```

## 🚨 Solución de Problemas

### Problemas Comunes

#### **LM Studio no responde**
```bash
# Verificar que el servidor esté activo
curl http://localhost:1234/v1/models

# Reiniciar LM Studio
python -c "import requests; requests.post('http://localhost:8001/api/lmstudio/server/start')"
```

#### **WhatsApp no detecta mensajes**
1. Verificar que WhatsApp Web esté cargado completamente
2. Revisar logs en `logs/automation.log`
3. Confirmar que el perfil de navegador tenga la sesión activa

#### **Panel de administración no carga**
1. Verificar que el puerto 8001 esté libre
2. Revisar logs en `logs/admin_panel.log`
3. Confirmar que la base de datos sea accesible

#### **Bot no responde a contactos**
1. Verificar que el contacto esté en la lista permitida
2. Confirmar configuración de contexto en el panel
3. Revisar que `respond_to_all` esté configurado apropiadamente

## 🔄 Actualización y Mantenimiento

### Backup Regular
```bash
# Backup de configuración
cp -r data/ backup-data-$(date +%Y%m%d)/
cp -r contextos/ backup-contextos-$(date +%Y%m%d)/
```

### Actualización de Dependencias
```bash
pip install -r requirements.txt --upgrade
playwright install chromium
```

### Limpieza de Logs
```bash
# Limpiar logs antiguos (automático con RotatingFileHandler)
find logs/ -name "*.log.*" -mtime +30 -delete
```

## 🤝 Contribuir al Proyecto

### Preparar Entorno de Desarrollo
```bash
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
python -m venv venv
source venv/bin/activate  # o venv\Scripts\activate en Windows
pip install -r requirements.txt
```

### Estructura de Commits
```
feat: nueva funcionalidad
fix: corrección de bug
docs: actualización de documentación
test: agregar/modificar tests
refactor: refactorización de código
```

### Pull Requests
1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit de cambios (`git commit -am 'feat: agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para detalles completos.

## 🆘 Soporte y Contacto

### Documentación Adicional
- **API Reference**: `http://localhost:8001/docs` (cuando el panel esté activo)
- **Logs detallados**: Revisar carpeta `logs/` para troubleshooting

### Reportar Issues
Si encuentras problemas o tienes sugerencias:
1. Revisar issues existentes en GitHub
2. Crear nuevo issue con información detallada:
   - Descripción del problema
   - Pasos para reproducir
   - Logs relevantes
   - Información del sistema (OS, Python version, etc.)

### Community
- **GitHub Issues**: Para bugs y feature requests
- **GitHub Discussions**: Para preguntas y discusión general

## ⚠️ Disclaimer

**Uso Responsable**: Este chatbot está diseñado para uso personal y educativo. Asegúrate de:
- Cumplir con los Términos de Servicio de WhatsApp
- Respetar la privacidad de los usuarios
- No enviar spam o contenido inapropiado
- Usar responsablemente en entornos comerciales

**Limitaciones**: El bot depende de WhatsApp Web y puede verse afectado por cambios en la interfaz de WhatsApp. Mantenemos el código actualizado, pero algunos elementos pueden requerir ajustes ocasionales.

---

**Desarrollado con ❤️ para la comunidad de IA conversacional**
