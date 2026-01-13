#!/usr/bin/env python3
"""
🤖 Configurador Automático de Chatbot Empresarial Universal
Este script configura automáticamente el chatbot según el tipo de negocio
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any

class BusinessConfigurator:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.templates_dir = self.project_root / "templates" / "business-configs"
        self.data_dir = self.project_root / "data"
        
    def available_business_types(self) -> Dict[str, str]:
        """Retorna los tipos de negocio disponibles"""
        return {
            "floristeria": "🌸 Florería - Flores, arreglos florales, eventos",
            "bufete_legal": "⚖️ Bufete Legal - Servicios jurídicos, consultas legales",
            "panaderia": "🥖 Panadería - Pan fresco, pasteles, productos horneados",
            "clinica": "🏥 Clínica/Consultorio - Citas médicas, información de salud",
            "tienda_online": "🛒 Tienda Online - E-commerce, catálogo de productos",
            "consultoria": "💼 Consultoría - Servicios profesionales, generación de leads",
            "educacion": "🎓 Educación - Cursos, inscripciones, soporte estudiantil",
            "hoteleria": "🏨 Hotelería - Reservas, turismo, servicios de hotel",
            "general": "🤖 General - Configuración base personalizable"
        }
    
    def configure_business(self, business_type: str, custom_name: str = None) -> bool:
        """Configura el chatbot para un tipo de negocio específico"""
        try:
            # Verificar si el template existe
            template_file = self.templates_dir / f"{business_type}.json"
            if not template_file.exists():
                print(f"❌ Template para '{business_type}' no encontrado")
                return False
            
            # Cargar configuración del template
            with open(template_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Personalizar nombre si se proporciona
            if custom_name:
                config['business_info']['name'] = custom_name
            
            # Crear directorio de datos si no existe
            self.data_dir.mkdir(exist_ok=True)
            
            # Guardar configuración principal
            config_file = self.data_dir / "business_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Actualizar payload principal
            payload_file = self.project_root / "payload.json"
            self._update_payload(payload_file, config)
            
            # Actualizar payload del razonador
            reasoner_file = self.project_root / "payload_reasoner.json"
            self._update_reasoner_payload(reasoner_file, config)
            
            print(f"✅ Chatbot configurado exitosamente para: {config['business_info']['name']}")
            print(f"📁 Configuración guardada en: {config_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error configurando el negocio: {str(e)}")
            return False
    
    def _update_payload(self, payload_file: Path, config: Dict[str, Any]):
        """Actualiza el archivo payload.json principal"""
        business_info = config['business_info']
        prompts = config['prompts']
        
        payload = {
            "business_name": business_info['name'],
            "business_type": business_info['type'],
            "industry": business_info['industry'],
            "services": business_info['services'],
            "tone": business_info['tone'],
            "main_prompt": prompts['main_context'],
            "greeting": prompts['greeting'],
            "closing": prompts['closing'],
            "conversation_goals": config['conversation_goals'],
            "keywords": config['keywords'],
            "responses": config['responses']
        }
        
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    
    def _update_reasoner_payload(self, reasoner_file: Path, config: Dict[str, Any]):
        """Actualiza el archivo payload_reasoner.json"""
        business_info = config['business_info']
        
        reasoner_payload = {
            "business_context": {
                "name": business_info['name'],
                "type": business_info['type'],
                "services": business_info['services']
            },
            "reasoning_goals": [
                "identificar_intencion_cliente",
                "clasificar_urgencia",
                "sugerir_siguientes_pasos",
                "optimizar_conversion"
            ],
            "strategy": {
                "lead_qualification": True,
                "sentiment_analysis": True,
                "personalization": True,
                "upselling_opportunities": True
            }
        }
        
        with open(reasoner_file, 'w', encoding='utf-8') as f:
            json.dump(reasoner_payload, f, indent=2, ensure_ascii=False)

def main():
    configurator = BusinessConfigurator()
    
    print("\n🤖 CONFIGURADOR AUTOMÁTICO - CHATBOT EMPRESARIAL UNIVERSAL")
    print("=" * 60)
    
    # Mostrar tipos de negocio disponibles
    print("\n📋 Tipos de negocio disponibles:")
    business_types = configurator.available_business_types()
    
    for i, (key, description) in enumerate(business_types.items(), 1):
        print(f"{i:2}. {description}")
    
    # Selección del usuario
    print("\n" + "=" * 60)
    
    try:
        # Seleccionar tipo de negocio
        while True:
            selection = input("🎯 Selecciona el número de tu tipo de negocio (1-9): ").strip()
            try:
                index = int(selection) - 1
                if 0 <= index < len(business_types):
                    business_type = list(business_types.keys())[index]
                    break
                else:
                    print("❌ Número inválido. Intenta de nuevo.")
            except ValueError:
                print("❌ Por favor ingresa un número válido.")
        
        # Nombre personalizado (opcional)
        print(f"\n📝 Configurando para: {business_types[business_type]}")
        custom_name = input("💼 Nombre de tu negocio (Enter para usar el por defecto): ").strip()
        
        if not custom_name:
            custom_name = None
        
        # Configurar
        print("\n🔧 Configurando chatbot...")
        success = configurator.configure_business(business_type, custom_name)
        
        if success:
            print("\n🎉 ¡CONFIGURACIÓN COMPLETADA!")
            print("=" * 60)
            print("📌 Próximos pasos:")
            print("1. Configura tus APIs en el archivo .env")
            print("2. Ejecuta: python admin_panel.py")
            print("3. Accede al dashboard: http://localhost:8003/ui/index.html")
            print("4. ¡Escanea el código QR de WhatsApp y comienza!")
            print("\n💡 Tip: Personaliza los prompts en data/business_config.json")
        
    except KeyboardInterrupt:
        print("\n\n👋 Configuración cancelada. ¡Hasta pronto!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")

if __name__ == "__main__":
    main()
