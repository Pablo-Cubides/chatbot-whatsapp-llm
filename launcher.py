#!/usr/bin/env python3
"""
🚀 Launcher Universal del Chatbot Empresarial
Script de inicio unificado con configuración automática
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
import platform

class UniversalLauncher:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / ".env"
        self.business_config_file = self.project_root / "data" / "business_config.json"
        
    def welcome_message(self):
        """Mensaje de bienvenida"""
        print("\n" + "="*60)
        print("🤖 CHATBOT EMPRESARIAL UNIVERSAL")
        print("💼 Para cualquier tipo de negocio")
        print("🌟 Multi-API con fallback automático")
        print("="*60)
        
    def check_first_run(self):
        """Verifica si es la primera ejecución"""
        return not self.business_config_file.exists()
    
    def check_dependencies(self):
        """Verifica dependencias principales"""
        print("🔍 Verificando dependencias...")
        
        required_packages = [
            ('fastapi', 'FastAPI'),
            ('playwright', 'Playwright'),
            ('requests', 'Requests'),
            ('aiohttp', 'AsyncHTTP')
        ]
        
        missing_packages = []
        
        for package, display_name in required_packages:
            try:
                __import__(package)
                print(f"✅ {display_name}")
            except ImportError:
                print(f"❌ {display_name} - FALTANTE")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"\n⚠️ Paquetes faltantes: {', '.join(missing_packages)}")
            install = input("🔧 ¿Instalar automáticamente? (y/N): ")
            if install.lower() == 'y':
                self.install_dependencies(missing_packages)
            else:
                print("❌ No se pueden continuar sin las dependencias")
                return False
        
        return True
    
    def install_dependencies(self, packages):
        """Instala dependencias faltantes"""
        print("📦 Instalando dependencias...")
        
        for package in packages:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✅ {package} instalado")
            except subprocess.CalledProcessError:
                print(f"❌ Error instalando {package}")
    
    def setup_playwright(self):
        """Configura Playwright si es necesario"""
        print("🎭 Verificando Playwright...")
        
        try:
            # Verificar si chromium está instalado
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("✅ Playwright configurado correctamente")
                return True
        except Exception:
            print("⚠️ Instalando navegadores de Playwright...")
            try:
                subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])
                print("✅ Chromium instalado")
                return True
            except subprocess.CalledProcessError:
                print("❌ Error instalando Chromium")
                return False
    
    def first_time_setup(self):
        """Configuración inicial para primera ejecución"""
        print("\n🎉 ¡Bienvenido! Vamos a configurar tu chatbot...")
        print("=" * 50)
        
        # Configurar tipo de negocio
        print("\n📋 PASO 1: Tipo de negocio")
        subprocess.run([sys.executable, "configure_business.py"])
        
        # Configurar APIs
        print("\n🔑 PASO 2: APIs de IA")
        print("Necesitas al menos una API de IA para que funcione el chatbot.")
        
        choice = input("¿Quieres ver las opciones gratuitas disponibles? (y/N): ")
        if choice.lower() == 'y':
            subprocess.run([sys.executable, "setup_free_apis.py"])
        
        # Verificar configuración básica
        if not self._check_basic_config():
            print("⚠️ Configuración incompleta. Usando valores por defecto.")
            self._create_basic_config()
        
        print("\n✅ Configuración inicial completada!")
    
    def _check_basic_config(self):
        """Verifica configuración básica"""
        if not self.env_file.exists():
            return False
        
        with open(self.env_file, 'r') as f:
            env_content = f.read()
        
        # Verificar al menos una API
        api_keys = ['GEMINI_API_KEY', 'OPENAI_API_KEY', 'OLLAMA_BASE_URL']
        return any(key in env_content for key in api_keys)
    
    def _create_basic_config(self):
        """Crea configuración básica por defecto"""
        basic_env = """# Configuración básica del Chatbot Empresarial Universal
BUSINESS_TYPE=general
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
ADMIN_BASE=http://127.0.0.1:8003
DEBUG=True
"""
        with open(self.env_file, 'w') as f:
            f.write(basic_env)
    
    def check_api_availability(self):
        """Verifica disponibilidad de APIs configuradas"""
        print("🔍 Verificando APIs de IA...")
        
        if not self.env_file.exists():
            print("❌ Archivo .env no encontrado")
            return False
        
        # Import the LLM manager
        from multi_provider_llm import llm_manager
        
        available_providers = llm_manager.get_available_providers()
        
        if not available_providers:
            print("❌ No hay proveedores de IA disponibles")
            print("💡 Ejecuta: python setup_free_apis.py")
            return False
        
        print("✅ Proveedores disponibles:")
        for provider in available_providers:
            status = "🟢" if provider['active'] else "🔴"
            local = "📍" if provider['local'] else "🌐"
            print(f"   {status} {local} {provider['name']} ({provider['model']})")
        
        return True
    
    def start_server(self):
        """Inicia el servidor principal"""
        print("\n🚀 Iniciando Chatbot Empresarial Universal...")
        
        # Cargar configuración de negocio si existe
        business_context = self._load_business_context()
        if business_context:
            business_name = business_context.get('business_info', {}).get('name', 'Chatbot Universal')
            print(f"💼 Negocio configurado: {business_name}")
        
        # URLs importantes
        print("\n🌐 URLs del sistema:")
        print("   📊 Dashboard: http://127.0.0.1:8003/ui/index.html")
        print("   💬 Chat rápido: http://127.0.0.1:8003/chat")
        print("   📖 API Docs: http://127.0.0.1:8003/docs")
        
        print("\n⏳ Iniciando servidor...")
        print("   (Presiona Ctrl+C para detener)")
        
        try:
            # Ejecutar el panel de administración principal
            subprocess.run([sys.executable, "admin_panel.py"])
        except KeyboardInterrupt:
            print("\n👋 Servidor detenido. ¡Hasta pronto!")
    
    def _load_business_context(self):
        """Carga contexto del negocio configurado"""
        try:
            if self.business_config_file.exists():
                with open(self.business_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return None
    
    def show_help(self):
        """Muestra ayuda y comandos disponibles"""
        print("\n📚 COMANDOS DISPONIBLES:")
        print("=" * 30)
        print("🔧 python configure_business.py    - Configurar tipo de negocio")
        print("🆓 python setup_free_apis.py       - Configurar APIs gratuitas")
        print("🤖 python launcher.py              - Iniciar chatbot (este archivo)")
        print("📊 python admin_panel.py           - Solo servidor admin")
        print("\n📁 ARCHIVOS IMPORTANTES:")
        print("   .env                    - Configuración general")
        print("   data/business_config.json  - Configuración del negocio")
        print("   payload.json           - Prompts principales")
        print("   payload_reasoner.json  - Configuración del razonador")
        
    def run(self):
        """Ejecuta el launcher principal"""
        self.welcome_message()
        
        # Verificar argumentos de línea de comandos
        if len(sys.argv) > 1:
            if sys.argv[1] in ['--help', '-h']:
                self.show_help()
                return
            elif sys.argv[1] == '--setup':
                self.first_time_setup()
                return
        
        # Verificar dependencias
        if not self.check_dependencies():
            return
        
        # Configurar Playwright
        if not self.setup_playwright():
            print("⚠️ Continuando sin Playwright (funciones limitadas)")
        
        # Primera ejecución
        if self.check_first_run():
            self.first_time_setup()
        
        # Verificar APIs
        if not self.check_api_availability():
            print("⚠️ Continuando con configuración limitada...")
        
        # Iniciar servidor
        self.start_server()

def main():
    launcher = UniversalLauncher()
    
    try:
        launcher.run()
    except KeyboardInterrupt:
        print("\n👋 ¡Configuración cancelada!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
        print("💡 Ejecuta con --help para ver opciones")

if __name__ == "__main__":
    main()
