#!/usr/bin/env python3
"""
🔍 Script de Validación Post-Instalación
Verifica que todas las dependencias y configuraciones estén correctas
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Verifica versión de Python"""
    print("🐍 Verificando Python...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (se requiere 3.11+)")
        return False

def check_dependencies():
    """Verifica dependencias críticas"""
    print("\n📦 Verificando dependencias...")
    
    critical_deps = {
        'fastapi': 'FastAPI',
        'jwt': 'PyJWT',
        'bcrypt': 'bcrypt',
        'sqlalchemy': 'SQLAlchemy',
        'playwright': 'Playwright',
        'dotenv': 'python-dotenv',
        'aiohttp': 'aiohttp',
        'apscheduler': 'APScheduler',
    }
    
    optional_deps = {
        'faster_whisper': 'faster-whisper (para transcripción de audio)',
        'psycopg2': 'psycopg2-binary (para PostgreSQL)',
        'redis': 'redis (para cache)',
    }
    
    all_ok = True
    
    for module, name in critical_deps.items():
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - FALTANTE (crítico)")
            all_ok = False
    
    print("\n📦 Verificando dependencias opcionales...")
    for module, name in optional_deps.items():
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ⚠️  {name} - No instalado (opcional)")
    
    return all_ok

def check_file_structure():
    """Verifica estructura de archivos"""
    print("\n📁 Verificando estructura de archivos...")
    
    required_files = [
        'admin_panel.py',
        'requirements.txt',
        'pytest.ini',
        'src/services/auth_system.py',
        'src/services/queue_system.py',
        'src/services/alert_system.py',
        'src/services/audit_system.py',
        'src/services/whatsapp_provider.py',
        'src/services/whatsapp_web_provider.py',
        'src/services/whatsapp_cloud_provider.py',
        'src/services/audio_transcriber.py',
        'src/workers/scheduler_worker.py',
        'ui/index.html',
        'ui/alerts.html',
        'docker-compose.yml',
        'Dockerfile',
    ]
    
    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - FALTANTE")
            all_ok = False
    
    return all_ok

def check_env_file():
    """Verifica archivo .env"""
    print("\n🔐 Verificando configuración...")
    
    if not Path('.env').exists():
        if Path('.env.example').exists():
            print("   ⚠️  .env no existe, pero .env.example está disponible")
            print("      Crea tu .env: cp .env.example .env")
            return False
        else:
            print("   ❌ Ni .env ni .env.example existen")
            return False
    
    print("   ✅ .env existe")
    
    # Verificar variables críticas
    from dotenv import load_dotenv
    load_dotenv()
    
    critical_vars = {
        'JWT_SECRET': 'Secreto JWT',
        'LEGACY_API_TOKEN': 'Token de API legacy',
    }
    
    all_ok = True
    for var, desc in critical_vars.items():
        value = os.getenv(var)
        if value and value != 'CHANGE_ME' and value != 'tu-secreto-super-seguro':
            print(f"   ✅ {desc} configurado")
        else:
            print(f"   ⚠️  {desc} no configurado o usa valor por defecto")
            all_ok = False
    
    return all_ok

def check_database():
    """Verifica conexión a base de datos"""
    print("\n💾 Verificando base de datos...")
    
    try:
        from sqlalchemy import create_engine
        from dotenv import load_dotenv
        load_dotenv()
        
        db_url = os.getenv('DATABASE_URL', 'sqlite:///chatbot_context.db')
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            print(f"   ✅ Conexión exitosa a: {db_url.split('@')[-1] if '@' in db_url else db_url}")
            return True
    except Exception as e:
        print(f"   ⚠️  Error de conexión: {e}")
        return False

def check_tests():
    """Verifica que los tests se puedan ejecutar"""
    print("\n🧪 Verificando configuración de tests...")
    
    test_files = [
        'tests/test_auth_system.py',
        'tests/test_queue_system.py',
        'tests/test_alert_system.py',
        'tests/test_audio_transcriber.py',
        'tests/test_whatsapp_providers.py',
    ]
    
    all_ok = True
    for test_file in test_files:
        if Path(test_file).exists():
            print(f"   ✅ {test_file}")
        else:
            print(f"   ❌ {test_file} - FALTANTE")
            all_ok = False
    
    return all_ok

def main():
    """Función principal"""
    print("=" * 60)
    print("🚀 VALIDACIÓN POST-INSTALACIÓN - Chatbot WhatsApp Enterprise")
    print("=" * 60)
    
    results = {
        'Python': check_python_version(),
        'Dependencias': check_dependencies(),
        'Estructura': check_file_structure(),
        'Configuración': check_env_file(),
        'Base de Datos': check_database(),
        'Tests': check_tests(),
    }
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VALIDACIÓN")
    print("=" * 60)
    
    for check, result in results.items():
        status = "✅ OK" if result else "❌ FALLÓ"
        print(f"{check:20} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ¡TODAS LAS VALIDACIONES PASARON!")
        print("\n📝 Próximos pasos:")
        print("   1. Ejecutar tests: pytest tests/ -v")
        print("   2. Iniciar servidor: python admin_panel.py")
        print("   3. Abrir panel: http://localhost:8003")
        print("=" * 60)
        return 0
    else:
        print("⚠️  ALGUNAS VALIDACIONES FALLARON")
        print("\n📝 Acciones recomendadas:")
        if not results['Dependencias']:
            print("   - Instalar dependencias: pip install -r requirements.txt")
        if not results['Configuración']:
            print("   - Configurar .env: cp .env.example .env")
            print("   - Editar .env con valores reales")
        if not results['Base de Datos']:
            print("   - Verificar DATABASE_URL en .env")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
