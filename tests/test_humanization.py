"""
🧪 Tests del Sistema de Humanización
"""

import sys
import os
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from services.humanized_responses import (
    humanized_responses,
    ErrorContext,
    HumanizedTiming
)


def test_context_detection():
    """Test: Detección de contexto"""
    print("\n" + "="*60)
    print("TEST 1: DETECCIÓN DE CONTEXTO")
    print("="*60)
    
    test_cases = [
        ("¿Cómo te llamas?", ErrorContext.SIMPLE_INFO),
        ("¿Cuál es tu horario?", ErrorContext.SIMPLE_INFO),
        ("¿Tienes productos disponibles?", ErrorContext.PRODUCT_INFO),
        ("¿Cuánto cuesta esto?", ErrorContext.PRICE_QUOTE),
        ("Dame información completa", ErrorContext.COMPLEX_QUESTION),
    ]
    
    passed = 0
    failed = 0
    
    for message, expected_context in test_cases:
        context = humanized_responses.detect_error_context(message, [])
        
        context_match = context == expected_context
        
        status = "✅" if context_match else "❌"
        
        print(f"\n  {status} Mensaje: '{message}'")
        print(f"     Contexto esperado: {expected_context.value}")
        print(f"     Contexto detectado: {context.value}")
        
        if context_match:
            passed += 1
        else:
            failed += 1
    
    print(f"\n  RESULTADO: {passed}/{len(test_cases)} tests pasaron")
    return failed == 0


def test_bot_response_validation():
    """Test: Validación de respuestas que revelan bot"""
    print("\n" + "="*60)
    print("TEST 2: VALIDACIÓN DE RESPUESTAS BOT-REVEALING")
    print("="*60)
    
    test_cases = [
        ("Como asistente virtual, puedo ayudarte", False, "Menciona 'asistente virtual'"),
        ("Soy un bot de IA aquí para asistirte", False, "Menciona 'bot' e 'IA'"),
        ("Claro, déjame ayudarte con eso", True, "Respuesta natural"),
        ("¡Hola! ¿En qué puedo ayudarte?", True, "Respuesta normal"),
        ("Como modelo de lenguaje, no puedo", False, "Menciona 'modelo de lenguaje'"),
        ("Te ayudo con gusto 😊", True, "Natural con emoji"),
    ]
    
    passed = 0
    failed = 0
    
    for response, should_be_valid, reason in test_cases:
        result = humanized_responses.validate_llm_response(response)
        is_valid = result.get('is_valid', False)
        
        status = "✅" if (is_valid == should_be_valid) else "❌"
        
        print(f"\n  {status} Respuesta: '{response[:50]}...'")
        print(f"     Razón: {reason}")
        print(f"     Válida: {is_valid} (esperado: {should_be_valid})")
        if not is_valid and result.get('issues'):
            print(f"     Issues detectados: {result['issues']}")
        
        if is_valid == should_be_valid:
            passed += 1
        else:
            failed += 1
    
    print(f"\n  RESULTADO: {passed}/{len(test_cases)} tests pasaron")
    return failed == 0


def test_ethical_refusal_detection():
    """Test: Detección de rechazos éticos"""
    print("\n" + "="*60)
    print("TEST 3: DETECCIÓN DE RECHAZOS ÉTICOS")
    print("="*60)
    
    test_cases = [
        ("I cannot discuss adult content as it violates guidelines", True),
        ("I'm not able to provide information about illegal substances", True),
        ("Sorry, I can't help with that type of content", True),
        ("Claro, tenemos varios productos disponibles", False),
        ("Te puedo ayudar con eso", False),
    ]
    
    passed = 0
    failed = 0
    
    for response, is_refusal in test_cases:
        detected = humanized_responses.detect_llm_ethical_refusal(response)
        
        status = "✅" if (detected == is_refusal) else "❌"
        
        print(f"\n  {status} Respuesta: '{response[:50]}...'")
        print(f"     Es rechazo ético: {detected} (esperado: {is_refusal})")
        
        if detected == is_refusal:
            passed += 1
        else:
            failed += 1
    
    print(f"\n  RESULTADO: {passed}/{len(test_cases)} tests pasaron")
    return failed == 0


def test_humanized_response_generation():
    """Test: Generación de respuestas humanizadas"""
    print("\n" + "="*60)
    print("TEST 4: GENERACIÓN DE RESPUESTAS HUMANIZADAS")
    print("="*60)
    
    test_cases = [
        ("¿Cómo te llamas?", "llm_failure"),
        ("¿Qué productos tienen?", "timeout"),
        ("¿Cuánto cuesta?", "ethical_refusal"),
    ]
    
    passed = 0
    
    for message, error_type in test_cases:
        response_dict = humanized_responses.get_error_response(
            user_message=message,
            error_type=error_type,
            conversation_history=[]
        )
        
        response_text = response_dict.get('response', '')
        action = response_dict.get('action', '')
        
        # Verificar que haya una respuesta o acción
        has_response = bool(response_text) or bool(action)
        
        status = "✅" if has_response else "❌"
        
        print(f"\n  {status} Mensaje: '{message}'")
        print(f"     Error type: {error_type}")
        print(f"     Acción: {action}")
        if response_text:
            print(f"     Respuesta: '{response_text[:100]}...'")
        
        if has_response:
            passed += 1
    
    print(f"\n  RESULTADO: {passed}/{len(test_cases)} tests pasaron")
    return passed == len(test_cases)


def test_timing_generation():
    """Test: Generación de delays humanizados"""
    print("\n" + "="*60)
    print("TEST 5: GENERACIÓN DE TIMING HUMANIZADO")
    print("="*60)
    
    test_lengths = [10, 50, 100, 200]
    
    passed = 0
    
    for length in test_lengths:
        delay = HumanizedTiming.calculate_typing_delay(length)
        
        # Verificar que el delay esté en rango razonable (1-10 segundos)
        is_valid = 1.0 <= delay <= 10.0
        
        status = "✅" if is_valid else "❌"
        
        print(f"\n  {status} Longitud de respuesta: {length} caracteres")
        print(f"     Delay calculado: {delay:.2f} segundos")
        print(f"     En rango válido (1-10s): {is_valid}")
        
        if is_valid:
            passed += 1
    
    print(f"\n  RESULTADO: {passed}/{len(test_lengths)} tests pasaron")
    return passed == len(test_lengths)


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "🧪"*30)
    print("   EJECUTANDO TESTS DEL SISTEMA DE HUMANIZACIÓN")
    print("🧪"*30)
    
    results = []
    
    # Test 1: Detección de contexto
    results.append(("Detección de Contexto", test_context_detection()))
    
    # Test 2: Validación de respuestas
    results.append(("Validación Bot-Revealing", test_bot_response_validation()))
    
    # Test 3: Detección de rechazos éticos
    results.append(("Detección Rechazos Éticos", test_ethical_refusal_detection()))
    
    # Test 4: Generación de respuestas
    results.append(("Generación Respuestas", test_humanized_response_generation()))
    
    # Test 5: Timing humanizado
    results.append(("Timing Humanizado", test_timing_generation()))
    
    # Resumen final
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"  {status}: {test_name}")
    
    print(f"\n  TOTAL: {passed}/{total} tests pasaron ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n  🎉 ¡TODOS LOS TESTS PASARON! Sistema funcionando correctamente.")
        return 0
    else:
        print(f"\n  ⚠️  {total - passed} test(s) fallaron. Revisar implementación.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    exit(exit_code)
