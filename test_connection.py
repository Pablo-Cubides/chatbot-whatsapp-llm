#!/usr/bin/env python3
import requests
import json

def test_lm_studio():
    url = "http://127.0.0.1:1234/v1/chat/completions"
    payload = {
        "model": "nemotron-mini-4b-instruct",
        "messages": [
            {"role": "user", "content": "Hola, ¿cómo estás?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ LM Studio funcionando correctamente!")
            print(f"Respuesta: {result['choices'][0]['message']['content']}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == "__main__":
    test_lm_studio()
