#!/usr/bin/env python3
"""
Test de inicialización rápida para verificar importaciones
"""

print("🧪 Probando importaciones...")

try:
    print("✅ Importando FastAPI...")
    from fastapi import FastAPI
    
    print("✅ Importando business_config_manager...")
    from business_config_manager import BusinessConfigManager, business_config
    
    print("✅ Importando multi_provider_llm...")
    from multi_provider_llm import MultiProviderLLM, APIConfig
    
    print("✅ Todas las importaciones funcionan!")
    
    print("🚀 Creando BusinessConfigManager...")
    config_manager = BusinessConfigManager()
    print(f"✅ Configuración cargada: {config_manager.config.get('business_info', {}).get('name', 'Sin nombre')}")
    
    print("🎯 ¡Todo funciona correctamente!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
