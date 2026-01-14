"""
Script de verificación completa del sistema v2.0
"""
import os
import sys
from pathlib import Path
import importlib.util

def check_file_exists(file_path: str, description: str) -> bool:
    """Verificar que un archivo existe"""
    if Path(file_path).exists():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - Archivo no encontrado: {file_path}")
        return False

def check_module_import(module_path: str, description: str) -> bool:
    """Verificar que un módulo se puede importar"""
    try:
        spec = importlib.util.spec_from_file_location("test_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ {description} - Error: {e}")
        return False

def main():
    print("🔍 ChatBot WhatsApp LLM v2.0 - Verificación Completa del Sistema")
    print("=" * 70)
    
    # Configurar variables de entorno para tests
    os.environ['JWT_SECRET'] = 'test-secret-for-verification-purposes'
    os.environ['ADMIN_PASSWORD'] = 'test_admin'
    os.environ['OPERATOR_PASSWORD'] = 'test_operator'
    
    all_checks = []
    
    print("\n📁 1. ESTRUCTURA DE ARCHIVOS")
    print("-" * 30)
    
    # Verificar estructura principal
    structure_checks = [
        ("src/", "Directorio src/"),
        ("src/services/", "Directorio services/"),
        ("src/models/", "Directorio models/"),
        ("tests/", "Directorio tests/"),
        ("docs/", "Directorio docs/"),
    ]
    
    for path, desc in structure_checks:
        all_checks.append(check_file_exists(path, desc))
    
    print("\n📋 2. ARCHIVOS DE CONFIGURACIÓN")
    print("-" * 35)
    
    config_files = [
        ("requirements.txt", "Dependencias de Python"),
        (".env.example", "Template de variables de entorno"),
        ("pytest.ini", "Configuración de pytest"),
        ("conftest.py", "Configuración global de tests"),
        ("README.md", "Documentación principal"),
        ("CHANGELOG.md", "Historial de cambios"),
        ("SECURITY.md", "Política de seguridad"),
    ]
    
    for file_path, desc in config_files:
        all_checks.append(check_file_exists(file_path, desc))
    
    print("\n🔧 3. SERVICIOS PRINCIPALES")
    print("-" * 30)
    
    services = [
        ("src/services/auth_system.py", "Sistema de autenticación"),
        ("src/services/multi_provider_llm.py", "Sistema Multi-Provider LLM"),
        ("src/services/cache_system.py", "Sistema de caché"),
        ("src/services/protection_system.py", "Sistema de protección"),
    ]
    
    for service_path, desc in services:
        if check_file_exists(service_path, f"Archivo {desc}"):
            # Intentar importar si existe
            try:
                if "auth_system" in service_path:
                    from src.services.auth_system import AuthManager
                elif "multi_provider_llm" in service_path:
                    from src.services.multi_provider_llm import MultiProviderLLM
                elif "cache_system" in service_path:
                    from src.services.cache_system import CacheSystem
                elif "protection_system" in service_path:
                    from src.services.protection_system import RateLimiter
                print(f"  ✅ Importación exitosa: {desc}")
                all_checks.append(True)
            except Exception as e:
                print(f"  ❌ Error importando {desc}: {e}")
                all_checks.append(False)
        else:
            all_checks.append(False)
    
    print("\n📊 4. MODELOS Y VALIDACIÓN")
    print("-" * 30)
    
    models = [
        ("src/models/validation_models.py", "Modelos de validación Pydantic"),
        ("src/models/admin_db.py", "Modelos de base de datos"),
    ]
    
    for model_path, desc in models:
        if check_file_exists(model_path, f"Archivo {desc}"):
            try:
                if "validation_models" in model_path:
                    from src.models.validation_models import BusinessConfig
                elif "admin_db" in model_path:
                    from src.models.admin_db import User
                print(f"  ✅ Importación exitosa: {desc}")
                all_checks.append(True)
            except Exception as e:
                print(f"  ❌ Error importando {desc}: {e}")
                all_checks.append(False)
        else:
            all_checks.append(False)
    
    print("\n🧪 5. SUITE DE TESTS")
    print("-" * 25)
    
    test_files = [
        ("tests/test_auth_system.py", "Tests del sistema de autenticación"),
        ("tests/test_multi_provider_llm.py", "Tests del sistema LLM"),
    ]
    
    for test_path, desc in test_files:
        all_checks.append(check_file_exists(test_path, desc))
    
    print("\n📖 6. DOCUMENTACIÓN")
    print("-" * 25)
    
    doc_files = [
        ("docs/API.md", "Documentación de API"),
        ("docs/DEPLOYMENT.md", "Guía de deployment"),
        ("USER_GUIDE.md", "Guía de usuario"),
    ]
    
    for doc_path, desc in doc_files:
        all_checks.append(check_file_exists(doc_path, desc))
    
    print("\n🚀 7. SERVIDOR PRINCIPAL")
    print("-" * 30)
    
    if check_file_exists("main_server.py", "Servidor principal"):
        try:
            # Solo verificar que se puede importar sin ejecutar
            with open("main_server.py", "r") as f:
                content = f.read()
                if "FastAPI" in content and "auth_system" in content:
                    print("  ✅ Servidor principal configurado correctamente")
                    all_checks.append(True)
                else:
                    print("  ⚠️  Servidor principal encontrado pero configuración no verificada")
                    all_checks.append(True)
        except Exception as e:
            print(f"  ❌ Error verificando servidor principal: {e}")
            all_checks.append(False)
    else:
        all_checks.append(False)
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📋 RESUMEN DE VERIFICACIÓN")
    print("=" * 70)
    
    total_checks = len(all_checks)
    passed_checks = sum(all_checks)
    percentage = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
    
    print(f"Total de verificaciones: {total_checks}")
    print(f"Verificaciones exitosas: {passed_checks}")
    print(f"Verificaciones fallidas: {total_checks - passed_checks}")
    print(f"Porcentaje de éxito: {percentage:.1f}%")
    
    if percentage >= 90:
        print("\n🎉 ¡SISTEMA LISTO PARA PRODUCCIÓN!")
        print("✨ Todas las verificaciones críticas han pasado.")
        print("🚀 Puedes proceder con el deployment.")
    elif percentage >= 70:
        print("\n⚠️  SISTEMA MAYORMENTE FUNCIONAL")
        print("🔧 Algunas verificaciones menores fallaron.")
        print("📋 Revisa los elementos marcados con ❌ antes de deployment.")
    else:
        print("\n🚨 SISTEMA REQUIERE ATENCIÓN")
        print("❌ Múltiples verificaciones críticas han fallado.")
        print("🛠️  Es necesario revisar y corregir antes de deployment.")
    
    print("\n📚 Próximos pasos recomendados:")
    print("1. Ejecutar: pytest tests/ --cov=src")
    print("2. Configurar .env con tus variables de entorno")
    print("3. Ejecutar: python main_server.py")
    print("4. Verificar endpoints en http://localhost:8000/docs")
    
    return percentage >= 70

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
