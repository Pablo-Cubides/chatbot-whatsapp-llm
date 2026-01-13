# 🎯 Guía Rápida - Chatbot Empresarial Universal

## ⚡ Inicio Súper Rápido (5 minutos)

### 1. **Descargar y Ejecutar**
```bash
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
python launcher.py
```

### 2. **Primera Configuración (Automática)**
El launcher te guiará para:
- ✅ Elegir tu tipo de negocio (floristería, panadería, legal, etc.)
- ✅ Configurar APIs gratuitas 
- ✅ Instalar dependencias automáticamente

### 3. **¡Listo!** 
- 🌐 Dashboard: http://localhost:8003/ui/index.html
- 📱 Escanea QR de WhatsApp y comienza

---

## 🏪 Ejemplos de Configuración por Industria

### 🌸 **Floristería**
```bash
# El configurador automático crea:
BUSINESS_TYPE=floristeria
BUSINESS_CONTEXT=Florería especializada en arreglos y eventos
GEMINI_API_KEY=tu_key_aqui
DEFAULT_LLM_PROVIDER=gemini
```

### ⚖️ **Bufete Legal**  
```bash
# Configuración automática para abogados:
BUSINESS_TYPE=bufete_legal
BUSINESS_CONTEXT=Bufete legal con consultas iniciales
OPENAI_API_KEY=tu_key_aqui
DEFAULT_LLM_PROVIDER=openai
```

### 🥖 **Panadería**
```bash
# Para panaderías y pastelerías:
BUSINESS_TYPE=panaderia  
BUSINESS_CONTEXT=Panadería con productos frescos diarios
OLLAMA_MODEL=llama3.2:3b
DEFAULT_LLM_PROVIDER=ollama  # ¡100% gratuito!
```

---

## 🆓 APIs Gratuitas Recomendadas

| API | Plan Gratuito | Ideal Para |
|-----|---------------|------------|
| 🟢 **Gemini** | 15 RPM gratis | Pequeños negocios |
| 🦙 **Ollama** | Ilimitado (local) | Máxima privacidad |
| 🟡 **Groq** | 14,400 tokens/min | Alta velocidad |
| 🔵 **OpenAI** | $5 crédito inicial | Máxima calidad |

### **Configuración Súper Rápida**:
```bash
python setup_free_apis.py  # Te guía paso a paso
```

---

## 📋 Comandos Esenciales

```bash
# 🚀 Inicio completo (recomendado)
python launcher.py

# 🔧 Solo configurar negocio  
python configure_business.py

# 🆓 Solo configurar APIs
python setup_free_apis.py

# 📊 Solo panel admin
python admin_panel.py
```

---

## 🎯 Casos de Uso Reales

### **Antes del Chatbot:**
- ❌ Responder WhatsApp manualmente 8-12 horas/día
- ❌ Perder clientes fuera del horario 
- ❌ Respuestas inconsistentes
- ❌ No seguimiento de leads

### **Con el Chatbot:**
- ✅ Respuestas automáticas 24/7
- ✅ +40% más conversiones
- ✅ Información consistente siempre
- ✅ Seguimiento automático de clientes

---

## 🔧 Personalización Express

### **Cambiar Prompts** (archivo `payload.json`):
```json
{
  "greeting": "¡Hola! Bienvenido a [TU NEGOCIO]",
  "main_context": "Soy el asistente de [TU NEGOCIO]. Ayudo con...",
  "services": ["servicio1", "servicio2", "servicio3"]
}
```

### **Agregar Palabras Clave**:
```json
{
  "keywords": {
    "precios": ["precio", "cuánto", "costo", "vale"],
    "horarios": ["hora", "abierto", "horario", "cuándo"]
  }
}
```

---

## 🚨 Solución de Problemas Express

### **Error: No hay APIs disponibles**
```bash
python setup_free_apis.py  # Configura APIs gratuitas
```

### **Error: Playwright no funciona**
```bash
python -m playwright install chromium
```

### **Error: Puerto ocupado**
```bash
# Cambiar puerto en .env:
UVICORN_PORT=8004
```

---

## 📞 Soporte Rápido

- 🐛 **Issues**: [GitHub Issues](https://github.com/Pablo-Cubides/chatbot-whatsapp-llm/issues)
- 💬 **WhatsApp**: Mensaje directo al desarrollador
- 📧 **Email**: soporte técnico disponible

---

## 🎉 ¡Ya está!

**Tu chatbot empresarial está listo en menos de 5 minutos.**

**Próximo paso**: Personalizar prompts para tu industria específica en el dashboard.

---

<div align="center">

**🚀 ¿Listo para automatizar tu negocio?**

```bash
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm  
python launcher.py
```

</div>
