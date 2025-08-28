import os
import requests
import json
import pytest


def test_chat_completions():
    if os.environ.get("ENABLE_LLM_TEST") != "1":
        pytest.skip("LM server test disabled. Set ENABLE_LLM_TEST=1 to enable.")
    # URL del endpoint de Chat Completions de LM Studio  
    url = "http://localhost:1234/api/v0/chat/completions"
    
    # Define el payload con tu configuración y mensajes de ejemplo  
    payload = {
        "model": "granite-3.0-2b-instruct",  # Ajusta esto si usas otro modelo
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
    
    # Realiza la solicitud POST al endpoint
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    
    # Procesa la respuesta
    if response.status_code == 200:
        result = response.json()
        print("Respuesta del modelo:")
        # Se espera que en result["choices"][0]["message"]["content"] esté la respuesta
        try:
            message = result.get("choices", [])[0].get("message", {}).get("content", "")
            print(message)
        except Exception as e:
            print("Error al parsear la respuesta:", e)
            print(result)
    else:
        print("Error al hacer la solicitud:", response.status_code)
        print(response.text)

if __name__ == "__main__":
    test_chat_completions()