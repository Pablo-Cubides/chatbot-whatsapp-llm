#!/usr/bin/env python3
"""
Script de prueba rápida para verificar la conexión con LM Studio
"""

import requests
import json

def test_lm_studio_direct():
    """Prueba la conexión directa con LM Studio"""
    print("=== Probando conexión directa con LM Studio ===")
    
    try:
        # Test 1: Listar modelos
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=5)
        if response.status_code == 200:
            models = response.json()
            print(f"✅ LM Studio responde. Modelos disponibles: {len(models['data'])}")
            for model in models['data']:
                print(f"   - {model['id']}")
        else:
            print(f"❌ Error listando modelos: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error conectando con LM Studio: {e}")
        return False
    
    # Test 2: Llamada de chat simple
    print("\n=== Probando llamada de chat ===")
    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "user", "content": "Di solo 'Hola'"}
        ],
        "temperature": 0.7,
        "max_tokens": 10
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            print(f"✅ Respuesta del modelo: '{reply}'")
            return True
        else:
            print(f"❌ Error en chat: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error en llamada de chat: {e}")
        return False

def test_our_chat_system():
    """Prueba nuestro sistema de chat"""
    print("\n=== Probando nuestro sistema de chat ===")
    
    try:
        import stub_chat
        reply = stub_chat.chat("Hola, esto es una prueba", "test_chat", [])
        print(f"✅ Respuesta de nuestro sistema: '{reply}'")
        return True
    except Exception as e:
        print(f"❌ Error en nuestro sistema: {e}")
        return False

def test_admin_panel():
    """Prueba el endpoint del panel admin"""
    print("\n=== Probando panel admin ===")
    
    try:
        response = requests.post(
            "http://127.0.0.1:8001/api/automator/test-reply",
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ Panel admin funciona: '{result.get('reply', 'Sin respuesta')}'")
                return True
            else:
                print(f"❌ Panel admin error: {result.get('error', 'Error desconocido')}")
                return False
        else:
            print(f"❌ Error en panel admin: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error conectando con panel admin: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Diagnóstico del sistema de chat\n")
    
    tests = [
        test_lm_studio_direct,
        test_our_chat_system,
        test_admin_panel
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        print()
    
    print("📋 Resumen:")
    print(f"   LM Studio directo: {'✅' if results[0] else '❌'}")
    print(f"   Nuestro sistema:   {'✅' if results[1] else '❌'}")
    print(f"   Panel admin:       {'✅' if results[2] else '❌'}")
    
    if all(results):
        print("\n🎉 Todo funciona correctamente!")
    else:
        print("\n⚠️  Hay problemas que resolver.")
