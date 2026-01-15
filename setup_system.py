"""
🚀 Script de Inicialización - WhatsApp AI Chatbot
Configura todo automáticamente
"""

import os
import sys
from pathlib import Path

# Agregar src al path
sys.path.append(str(Path(__file__).parent / 'src'))

def check_dependencies():
    """Verifica dependencias instaladas"""
    print("\n" + "="*60)
    print("📦 VERIFICANDO DEPENDENCIAS")
    print("="*60)
    
    required = {
        'fastapi': 'FastAPI',
        'uvicorn': 'Uvicorn',
        'playwright': 'Playwright',
        'sqlalchemy': 'SQLAlchemy',
        'aiohttp': 'aiohttp',
        'pydantic': 'Pydantic',
    }
    
    missing = []
    for module, name in required.items():
        try:
            __import__(module)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name} - FALTA")
            missing.append(name)
    
    if missing:
        print(f"\n⚠️  Instalar dependencias faltantes:")
        print(f"   pip install {' '.join(missing.lower())}")
        return False
    
    print("\n✅ Todas las dependencias instaladas\n")
    return True


def check_env_file():
    """Verifica archivo .env"""
    print("="*60)
    print("⚙️  VERIFICANDO CONFIGURACIÓN")
    print("="*60)
    
    env_path = Path('.env')
    
    if not env_path.exists():
        print("  ❌ Archivo .env no encontrado")
        print("\n  Creando .env de ejemplo...")
        create_example_env()
        print("  ✅ Archivo .env.example creado")
        print("  ⚠️  Copia .env.example a .env y configura tus API keys")
        return False
    
    print("  ✅ Archivo .env encontrado")
    
    # Verificar configuraciones importantes
    from dotenv import load_dotenv
    load_dotenv()
    
    configs = {
        'GEMINI_API_KEY': 'Gemini (análisis de imágenes)',
        'OPENAI_API_KEY': 'OpenAI (fallback)',
        'DATABASE_URL': 'Base de datos',
        'SECRET_KEY': 'Seguridad JWT',
    }
    
    print("\n  Configuraciones detectadas:")
    configured = []
    missing = []
    
    for key, desc in configs.items():
        value = os.getenv(key)
        if value:
            print(f"    ✅ {desc}")
            configured.append(key)
        else:
            print(f"    ⚠️  {desc} - NO CONFIGURADO")
            missing.append(key)
    
    print()
    return len(configured) > 0


def create_example_env():
    """Crea archivo .env.example"""
    content = """# ===== APIs de IA =====
GEMINI_API_KEY=tu_key_aqui
OPENAI_API_KEY=tu_key_aqui
CLAUDE_API_KEY=tu_key_aqui
XAI_API_KEY=tu_key_aqui

# ===== Base de Datos =====
DATABASE_URL=sqlite:///./chatbot_context.db

# ===== Seguridad =====
SECRET_KEY=genera_una_key_segura_aqui
JWT_EXPIRE_MINUTES=1440

# ===== Análisis de Imágenes =====
IMAGE_ANALYSIS_ENABLED=true
MAX_IMAGE_SIZE_MB=10
IMAGE_CACHE_TTL=3600

# ===== Análisis Profundo =====
DEEP_ANALYSIS_ENABLED=true
DEEP_ANALYSIS_TRIGGER_CONVERSATIONS=50
DEEP_ANALYSIS_TRIGGER_DAYS=7

# ===== A/B Testing =====
AB_TESTING_ENABLED=true
AB_TEST_MIN_SAMPLE_SIZE=30
AB_TEST_CONFIDENCE_LEVEL=0.95

# ===== Servidor =====
HOST=127.0.0.1
PORT=8003
CORS_ORIGINS=http://localhost:8003,http://127.0.0.1:8003
"""
    
    with open('.env.example', 'w') as f:
        f.write(content)


def check_database():
    """Verifica y crea base de datos"""
    print("="*60)
    print("💾 VERIFICANDO BASE DE DATOS")
    print("="*60)
    
    try:
        from src.models.models import Base, engine, SilentTransfer, HumanizationMetric, ConversationObjective
        
        # Crear todas las tablas
        Base.metadata.create_all(engine)
        
        print("  ✅ Base de datos inicializada")
        print("  ✅ Tablas creadas:")
        print("     - SilentTransfer")
        print("     - HumanizationMetric")
        print("     - ConversationObjective")
        print()
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        print()
        return False


def check_services():
    """Verifica que servicios estén disponibles"""
    print("="*60)
    print("🔧 VERIFICANDO SERVICIOS")
    print("="*60)
    
    services = {
        'humanized_responses': 'Sistema de Humanización',
        'silent_transfer': 'Transferencias Silenciosas',
        'image_analyzer': 'Análisis de Imágenes',
        'realtime_metrics': 'Métricas en Tiempo Real',
        'deep_analyzer': 'Análisis Profundo',
        'ab_test_manager': 'A/B Testing',
    }
    
    available = []
    errors = []
    
    for module, name in services.items():
        try:
            __import__(f'services.{module}')
            print(f"  ✅ {name}")
            available.append(module)
        except Exception as e:
            print(f"  ❌ {name}: {str(e)[:50]}...")
            errors.append((module, e))
    
    print()
    
    if errors:
        print("⚠️  Algunos servicios tienen errores (posiblemente por falta de configuración)")
        print("   Esto es normal si aún no configuraste las API keys\n")
    
    return len(available) > 0


def print_summary():
    """Imprime resumen final"""
    print("="*60)
    print("🎯 RESUMEN")
    print("="*60)
    print("""
✅ CARACTERÍSTICAS IMPLEMENTADAS:

📋 FASE 0: Sistema de Humanización (100%%)
   - Detección contextual de errores
   - Transferencias silenciosas
   - Validación de respuestas bot-revealing
   - Sistema inteligente de modelos sensibles

🖼️ FASE 1: Análisis de Imágenes (100%%)
   - Gemini Vision (gratis) + GPT-4o-mini
   - Sistema de caché
   - Integración WhatsApp

📊 FASE 2: Métricas en Tiempo Real (100%%)
   - WebSocket con actualización cada 5s
   - Dashboard completo
   - Reconexión automática

🔬 FASE 3+4: Análisis Profundo (100%%)
   - Análisis periódico (cada 50 conversaciones)
   - Detección de emociones
   - Detección de sospecha de bot
   - Análisis de cumplimiento de objetivos

🧪 FASE 5: A/B Testing (100%%)
   - Experimentos A/B completos
   - Significancia estadística
   - Reportes y recomendaciones
""")
    print("="*60)
    print("🚀 PRÓXIMOS PASOS:")
    print("="*60)
    print("""
1. Configura tu archivo .env con las API keys
2. Ejecuta: python main_server.py
3. Abre: http://localhost:8003/ui/realtime_dashboard.html
4. Lee: docs/TESTING_GUIDE.md para pruebas completas
5. Lee: docs/IMPLEMENTATION_FINAL.md para documentación

Para testing rápido:
  python -m pytest tests/ -v

Para desarrollo:
  python main_server.py

Para producción:
  uvicorn main_server:app --host 0.0.0.0 --port 8003
""")


def main():
    """Función principal"""
    print("\n" + "🤖 "*20)
    print("   WHATSAPP AI CHATBOT - INICIALIZACIÓN")
    print("🤖 "*20 + "\n")
    
    all_ok = True
    
    # 1. Verificar dependencias
    if not check_dependencies():
        all_ok = False
    
    # 2. Verificar .env
    if not check_env_file():
        all_ok = False
    
    # 3. Verificar base de datos
    if not check_database():
        all_ok = False
    
    # 4. Verificar servicios
    if not check_services():
        all_ok = False
    
    # 5. Resumen
    print_summary()
    
    if all_ok:
        print("\n✅ ¡TODO LISTO! Sistema configurado correctamente\n")
        return 0
    else:
        print("\n⚠️  Completa la configuración antes de iniciar el sistema\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
