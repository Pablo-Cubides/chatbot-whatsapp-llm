#!/usr/bin/env python3
"""
🆓 Instalador de APIs Gratuitas Adicionales
Configura automáticamente APIs gratuitas para el chatbot
"""

import os
import requests
import subprocess
import json
from pathlib import Path

class FreeAPIsInstaller:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / ".env"
    
    def install_ollama(self):
        """Instala Ollama para modelos locales gratuitos"""
        print("🦙 Instalando Ollama (Modelos locales gratuitos)...")
        
        try:
            # Verificar si ya está instalado
            result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Ollama ya está instalado")
                return self._setup_ollama_models()
        except FileNotFoundError:
            pass
        
        # Instalar según el sistema operativo
        import platform
        system = platform.system().lower()
        
        if system == 'windows':
            print("📥 Descarga Ollama para Windows desde: https://ollama.com/download")
            print("💡 Después de instalar, ejecuta este script nuevamente")
            return False
        elif system == 'darwin':  # macOS
            subprocess.run(['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'], shell=True)
        elif system == 'linux':
            subprocess.run(['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'], shell=True)
        
        return self._setup_ollama_models()
    
    def _setup_ollama_models(self):
        """Configura modelos recomendados en Ollama"""
        models = [
            "llama3.2:3b",      # Ligero, rápido
            "qwen2.5:3b",       # Excelente para español
            "gemma2:2b"         # Muy liviano
        ]
        
        for model in models:
            print(f"📦 Descargando modelo {model}...")
            try:
                subprocess.run(['ollama', 'pull', model], check=True)
                print(f"✅ Modelo {model} instalado")
            except subprocess.CalledProcessError:
                print(f"❌ Error instalando {model}")
        
        # Actualizar .env
        self._update_env({
            'OLLAMA_BASE_URL': 'http://localhost:11434',
            'OLLAMA_MODEL': 'llama3.2:3b'
        })
        
        return True
    
    def setup_free_apis(self):
        """Configura APIs con planes gratuitos generosos"""
        
        apis_info = {
            "🟢 Google Gemini": {
                "free_tier": "15 RPM gratis",
                "signup_url": "https://aistudio.google.com/app/apikey",
                "docs": "https://ai.google.dev/gemini-api/docs"
            },
            "🔵 OpenAI": {
                "free_tier": "$5 crédito inicial",
                "signup_url": "https://platform.openai.com/api-keys",
                "docs": "https://platform.openai.com/docs"
            },
            "🟣 Anthropic Claude": {
                "free_tier": "$5 crédito inicial",
                "signup_url": "https://console.anthropic.com/",
                "docs": "https://docs.anthropic.com/"
            },
            "🟤 Cohere": {
                "free_tier": "1000 calls/month",
                "signup_url": "https://dashboard.cohere.ai/api-keys",
                "docs": "https://docs.cohere.com/"
            },
            "🔴 Together AI": {
                "free_tier": "$5 crédito inicial",
                "signup_url": "https://api.together.xyz/settings/api-keys",
                "docs": "https://docs.together.ai/"
            },
            "🟡 Groq": {
                "free_tier": "14,400 tokens/min gratis",
                "signup_url": "https://console.groq.com/keys",
                "docs": "https://console.groq.com/docs"
            }
        }
        
        print("\n🆓 APIs GRATUITAS DISPONIBLES")
        print("=" * 50)
        
        for name, info in apis_info.items():
            print(f"\n{name}")
            print(f"   💰 Plan gratuito: {info['free_tier']}")
            print(f"   🔗 Registro: {info['signup_url']}")
            print(f"   📖 Documentación: {info['docs']}")
        
        print("\n💡 RECOMENDACIONES:")
        print("1. 🥇 Gemini: Mejor relación gratis/performance")
        print("2. 🥈 Groq: Muy rápido, límites generosos") 
        print("3. 🥉 Together AI: Muchos modelos disponibles")
        print("4. 🏅 Ollama: 100% gratis y privado (local)")
        
    def create_env_template(self):
        """Crea template .env con todas las opciones"""
        template = """
# ========================================
# 🆓 CONFIGURACIÓN APIS GRATUITAS
# ========================================

# Proveedor principal (recomendado: gemini)
DEFAULT_LLM_PROVIDER=gemini

# ========================================
# 🟢 GOOGLE GEMINI (15 RPM gratis)
# ========================================
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-1.5-flash

# ========================================
# 🟡 GROQ (14,400 tokens/min gratis)
# ========================================
# GROQ_API_KEY=your_groq_key_here
# GROQ_MODEL=llama3-8b-8192

# ========================================
# 🔴 TOGETHER AI ($5 crédito inicial)
# ========================================
# TOGETHER_API_KEY=your_together_key_here
# TOGETHER_MODEL=meta-llama/Llama-2-7b-chat-hf

# ========================================
# 🟤 COHERE (1000 calls/month gratis)
# ========================================
# COHERE_API_KEY=your_cohere_key_here
# COHERE_MODEL=command-r-plus

# ========================================
# 🦙 OLLAMA (100% gratis y local)
# ========================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# ========================================
# 🔵 OPENAI ($5 crédito inicial)
# ========================================
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4o-mini

# ========================================
# 🟣 ANTHROPIC CLAUDE ($5 crédito inicial) 
# ========================================
# CLAUDE_API_KEY=your_claude_key_here
# CLAUDE_MODEL=claude-3-haiku-20240307
        """
        
        env_example = self.project_root / ".env.free_apis_template"
        with open(env_example, 'w') as f:
            f.write(template.strip())
        
        print(f"✅ Template creado en: {env_example}")
        print("💡 Copia las APIs que consigas al archivo .env")
    
    def _update_env(self, variables: dict):
        """Actualiza variables en el archivo .env"""
        env_content = ""
        
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                env_content = f.read()
        
        # Agregar nuevas variables
        for key, value in variables.items():
            if f"{key}=" not in env_content:
                env_content += f"\n{key}={value}\n"
        
        with open(self.env_file, 'w') as f:
            f.write(env_content)
    
    def check_api_status(self):
        """Verifica el estado de las APIs configuradas"""
        print("🔍 VERIFICANDO APIS CONFIGURADAS...")
        print("=" * 40)
        
        # Verificar Ollama
        try:
            response = requests.get("http://localhost:11434/api/version", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama: Disponible")
            else:
                print("❌ Ollama: Error de conexión")
        except:
            print("❌ Ollama: No disponible (instalar con: curl -fsSL https://ollama.com/install.sh | sh)")
        
        # Verificar APIs desde .env
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                env_content = f.read()
                
            apis = [
                ('GEMINI_API_KEY', 'Google Gemini'),
                ('OPENAI_API_KEY', 'OpenAI'),
                ('CLAUDE_API_KEY', 'Anthropic Claude'),
                ('GROQ_API_KEY', 'Groq'),
                ('TOGETHER_API_KEY', 'Together AI'),
                ('COHERE_API_KEY', 'Cohere')
            ]
            
            for env_var, name in apis:
                if f"{env_var}=" in env_content and "your_" not in env_content:
                    print(f"✅ {name}: Configurado")
                else:
                    print(f"⚠️ {name}: No configurado")

def main():
    installer = FreeAPIsInstaller()
    
    print("\n🆓 CONFIGURADOR DE APIS GRATUITAS")
    print("=" * 40)
    
    while True:
        print("\n📋 Opciones disponibles:")
        print("1. 📋 Ver APIs gratuitas disponibles")
        print("2. 🦙 Instalar Ollama (modelos locales)")
        print("3. 📄 Crear template de configuración")
        print("4. 🔍 Verificar estado de APIs")
        print("5. 🚪 Salir")
        
        choice = input("\n🎯 Selecciona una opción (1-5): ").strip()
        
        if choice == "1":
            installer.setup_free_apis()
        elif choice == "2":
            installer.install_ollama()
        elif choice == "3":
            installer.create_env_template()
        elif choice == "4":
            installer.check_api_status()
        elif choice == "5":
            print("👋 ¡Hasta pronto!")
            break
        else:
            print("❌ Opción inválida")

if __name__ == "__main__":
    main()
