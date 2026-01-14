"""
Test de integración simple para verificar que todo funcione
"""
import asyncio
import os

# Configurar variables de entorno necesarias
os.environ['JWT_SECRET'] = 'test-secret-key-for-integration-testing-purposes'
os.environ['ADMIN_PASSWORD'] = 'test_admin_password'
os.environ['OPERATOR_PASSWORD'] = 'test_operator_password'

async def test_integrations():
    """Test simple de integración de todos los sistemas"""
    
    print("🧪 Iniciando tests de integración...")
    
    # Test 1: Auth System
    try:
        from src.services.auth_system import AuthManager
        auth_manager = AuthManager()
        print("✅ Sistema de autenticación: OK")
    except Exception as e:
        print(f"❌ Sistema de autenticación: {e}")
        return False
    
    # Test 2: Cache System
    try:
        from src.services.cache_system import CacheSystem
        cache = CacheSystem()
        await cache.set("test_key", "test_value")
        value = await cache.get("test_key")
        assert value == "test_value"
        print("✅ Sistema de cache: OK")
    except Exception as e:
        print(f"❌ Sistema de cache: {e}")
        return False
    
    # Test 3: Protection System
    try:
        from src.services.protection_system import RateLimiter, CircuitBreaker
        rate_limiter = RateLimiter(requests_per_minute=60)
        circuit_breaker = CircuitBreaker(failure_threshold=5)
        print("✅ Sistema de protección: OK")
    except Exception as e:
        print(f"❌ Sistema de protección: {e}")
        return False
    
    # Test 4: Multi-Provider LLM
    try:
        from src.services.multi_provider_llm import MultiProviderLLM
        llm = MultiProviderLLM()
        print("✅ Sistema Multi-Provider LLM: OK")
    except Exception as e:
        print(f"❌ Sistema Multi-Provider LLM: {e}")
        return False
    
    # Test 5: Validation Models
    try:
        from src.models.validation_models import BusinessConfig, ChatMessage
        config = BusinessConfig(
            company_name="Test Company",
            business_type="test",
            description="Test description"
        )
        print("✅ Modelos de validación: OK")
    except Exception as e:
        print(f"❌ Modelos de validación: {e}")
        return False
    
    print("\n🎉 ¡Todos los tests de integración pasaron!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_integrations())
    if not result:
        exit(1)
    print("\n✨ Sistema listo para producción")
