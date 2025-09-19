# 🤖 WhatsApp Chatbot con Dashboard Moderno

## 📋 Descripción

Sistema completo de chatbot para WhatsApp con una interfaz web moderna desarrollada en Next.js. Incluye dashboard en tiempo real, sistema de guías interactivas, gestión de mensajes, automatización avanzada y monitoreo completo.

## ✨ Características Principales

### 🎯 Dashboard Inteligente
- **Estadísticas en tiempo real** con gráficos interactivos
- **Monitor del sistema** con estados de todos los componentes
- **Actividad reciente** con timeline de eventos
- **Métricas de rendimiento** y tiempos de respuesta

### 💬 Sistema de Mensajería
- **Chat en tiempo real** con interfaz similar a WhatsApp
- **Lista de contactos** con búsqueda y filtros
- **Estados de mensajes** (enviado, entregado, leído)
- **Mensajería masiva** programada

### 🎓 Sistema de Guías Interactivas
- **Configuración paso a paso** para nuevos usuarios
- **Tutoriales interactivos** con progreso guardado
- **Guías contextuales** según el nivel del usuario
- **Tips y mejores prácticas** integrados

### 🔧 Configuración Avanzada
- **Gestión de modelos LLM** (LM Studio, OpenAI)
- **Reglas de automatización** personalizables
- **Plantillas de mensajes** reutilizables
- **Configuración de la API** centralizada

## 🚀 Tecnologías Utilizadas

### Frontend
- **Next.js 14** - Framework React moderno
- **TypeScript** - Tipado estático
- **Tailwind CSS** - Diseño responsivo
- **Chart.js** - Gráficos interactivos
- **Socket.IO** - Comunicación en tiempo real
- **React Hook Form** - Gestión de formularios
- **Framer Motion** - Animaciones fluidas

### Backend (Existente)
- **FastAPI** - API REST moderna
- **SQLite** - Base de datos ligera
- **WhatsApp Web.js** - Integración con WhatsApp
- **LangChain** - Integración con LLMs
- **WebSocket** - Tiempo real

## 📁 Estructura del Proyecto

```
Frontend/
├── src/
│   ├── app/                    # Páginas de Next.js 14
│   │   ├── dashboard/         # Dashboard principal
│   │   ├── messaging/         # Interfaz de mensajería
│   │   ├── layout.tsx         # Layout raíz
│   │   └── page.tsx          # Página principal
│   ├── components/           # Componentes React
│   │   ├── Layout/           # Componentes de layout
│   │   └── UserGuideSystem.tsx # Sistema de guías
│   ├── hooks/               # Custom React hooks
│   ├── lib/                # Utilidades y servicios
│   │   ├── api.ts          # Cliente API
│   │   └── utils.ts        # Funciones auxiliares
│   └── types/              # Definiciones TypeScript
├── public/                 # Archivos estáticos
├── package.json           # Dependencias del proyecto
├── tailwind.config.js     # Configuración de Tailwind
└── tsconfig.json         # Configuración TypeScript
```

## ⚡ Instalación Rápida

### 1. Clonar y configurar
```bash
# Navegar al directorio del proyecto
cd "d:\Mis aplicaciones\Chatbot_Citas"

# Instalar dependencias del frontend
cd Frontend
npm install
```

### 2. Iniciar el desarrollo
```bash
# Opción 1: Desde el directorio Frontend
npm run dev

# Opción 2: Desde el directorio raíz
node start-frontend.js
```

### 3. Acceder al dashboard
- **Frontend**: http://localhost:3000
- **API Backend**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

## 🎮 Guía de Uso

### 📱 Configuración Inicial
1. **Conectar WhatsApp**: Escanea el código QR
2. **Configurar LLM**: Selecciona y configura el modelo
3. **Probar conexión**: Envía un mensaje de prueba

### 💌 Gestión de Mensajes
1. **Mensajes individuales**: Selecciona contacto y escribe
2. **Mensajes masivos**: Selecciona múltiples destinatarios
3. **Programar envíos**: Configura fecha y hora

### 🤖 Automatización
1. **Crear reglas**: Define condiciones y respuestas
2. **Plantillas**: Crea mensajes reutilizables
3. **Monitoreo**: Revisa logs y estadísticas

## 🎨 Características del Diseño

### 🌈 Sistema de Diseño
- **Colores**: Paleta profesional con acentos de WhatsApp
- **Tipografía**: Inter font para máxima legibilidad
- **Iconografía**: Heroicons para consistencia
- **Animaciones**: Transiciones suaves y feedback visual

### 📱 Responsive Design
- **Mobile-first**: Optimizado para dispositivos móviles
- **Tablet**: Layout adaptado para pantallas medianas
- **Desktop**: Aprovecha el espacio disponible
- **Navegación**: Sidebar colapsible automático

### ♿ Accesibilidad
- **Contraste**: Cumple estándares WCAG
- **Keyboard**: Navegación completa por teclado
- **Screen readers**: Etiquetas semánticas
- **Focus**: Indicadores visuales claros

## 🔒 Configuración de Seguridad

### 🛡️ Autenticación
```typescript
// Configurar API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Headers de autenticación
Authorization: `Bearer ${token}`
```

### 🌐 Variables de Entorno
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_ENV=development
```

## 📊 Monitoreo y Analytics

### 📈 Métricas Disponibles
- **Mensajes**: Enviados, recibidos, fallidos
- **Rendimiento**: Tiempos de respuesta, throughput
- **Usuarios**: Contactos activos, conversaciones
- **Sistema**: Estado de componentes, errores

### 🔍 Logs y Debugging
- **Frontend**: Console logs con niveles
- **API**: Logs estructurados en backend
- **WebSocket**: Estado de conexiones
- **Errores**: Captura y reporte automático

## 🚀 Deployment

### 🌍 Producción
```bash
# Build del proyecto
npm run build

# Iniciar en producción
npm start

# O usar PM2
pm2 start ecosystem.config.js
```

### 🐳 Docker (Opcional)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install && npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## 🛠️ Desarrollo

### 🔧 Scripts Disponibles
```json
{
  "dev": "next dev",
  "build": "next build", 
  "start": "next start",
  "lint": "next lint",
  "type-check": "tsc --noEmit"
}
```

### 🎯 Contribuir
1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📞 Soporte

### 🆘 Problemas Comunes
- **Puerto ocupado**: Cambiar puerto con `npm run dev -- -p 3001`
- **Errores de tipo**: Ejecutar `npm run type-check`
- **Estilos**: Verificar configuración de Tailwind
- **API**: Confirmar que el backend esté ejecutándose

### 🐛 Reportar Bugs
1. Descripción detallada del problema
2. Pasos para reproducir
3. Logs relevantes
4. Entorno (OS, Node version, etc.)

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **Next.js Team** - Framework increíble
- **Tailwind CSS** - Sistema de diseño
- **Heroicons** - Iconografía consistente
- **Chart.js** - Visualización de datos
- **WhatsApp** - Plataforma de mensajería

---

**Desarrollado con ❤️ para automatizar y mejorar la comunicación por WhatsApp**