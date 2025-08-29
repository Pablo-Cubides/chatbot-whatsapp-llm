import os
import requests
import json
import pytest


def test_chat_completions():
    print("=== Iniciando test de LM Studio ===")
    
    if os.environ.get("ENABLE_LLM_TEST") != "1":
        print("Test deshabilitado. Activando automáticamente...")
        os.environ["ENABLE_LLM_TEST"] = "1"
    
    # URL del endpoint de Chat Completions de LM Studio  
    url = "http://127.0.0.1:1234/v1/chat/completions"
    print(f"URL objetivo: {url}")
    
    # Define el payload con tu configuración y mensajes de ejemplo  
    payload = {
        "model": "nemotron-mini-4b-instruct:4",  # Modelo actualizado disponible en el servidor
        "messages": [
            { "role": "system", "content": "Siempre responde en rimas." },
            { "role": "user", "content": "Preséntate por favor." }
        ],
        "temperature": 0.7,     # Parámetro de aleatoriedad (ajústalo según necesites)
        "max_tokens": -1,       # -1 para usar el máximo contexto permitido o un número específico
        "stream": False         # No estamos usando stream en esta prueba
    }
    
    # Encabezados indicando el uso de JSON
    headers = {
        "Content-Type": "application/json"
    }
    
    print("Enviando solicitud a LM Studio...")
    
    try:
        # Realiza la solicitud POST al endpoint
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        
        # Procesa la respuesta
        if response.status_code == 200:
            result = response.json()
            print("✅ Respuesta exitosa del modelo:")
            # Se espera que en result["choices"][0]["message"]["content"] esté la respuesta
            try:
                message = result.get("choices", [])[0].get("message", {}).get("content", "")
                print(f"Mensaje: {message}")
                return True
            except Exception as e:
                print("❌ Error al parsear la respuesta:", e)
                print("Respuesta completa:", result)
                return False
        else:
            print(f"❌ Error HTTP {response.status_code}:")
            print(response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a LM Studio en http://127.0.0.1:1234")
        print("¿Está LM Studio ejecutándose?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Error: Timeout esperando respuesta de LM Studio")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    print("=== Test LM Studio ===")
    success = test_chat_completions()
    if success:
        print("✅ Test completado exitosamente")
    else:
        print("❌ Test falló")
        exit(1)