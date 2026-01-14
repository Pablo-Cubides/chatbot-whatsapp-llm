# 🤝 Guía de Contribución

¡Gracias por tu interés en contribuir al Chatbot WhatsApp Empresarial! Esta guía te ayudará a participar de manera efectiva.

## 📋 Índice

- [Código de Conducta](#código-de-conducta)
- [Cómo Contribuir](#cómo-contribuir)
- [Configuración del Entorno](#configuración-del-entorno)
- [Estándares de Código](#estándares-de-código)
- [Proceso de Pull Request](#proceso-de-pull-request)
- [Tipos de Contribuciones](#tipos-de-contribuciones)
- [Reportar Bugs](#reportar-bugs)
- [Sugerir Features](#sugerir-features)

## 🤝 Código de Conducta

Este proyecto adhiere al Código de Conducta del Contributor Covenant. Al participar, esperamos que mantengas estos estándares:

- **Sé respetuoso** con otros contribuidores
- **Sé constructivo** en tus críticas
- **Sé paciente** con nuevos contribuidores
- **Mantén un ambiente inclusivo** para todos

## 🚀 Cómo Contribuir

### 1. Fork y Clone

```bash
# Fork el repositorio en GitHub, luego:
git clone https://github.com/tu-usuario/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm
```

### 2. Crear Rama Feature

```bash
git checkout -b feature/nombre-descriptivo
# o para bugs:
git checkout -b fix/descripcion-del-fix
```

### 3. Hacer Cambios y Commit

```bash
git add .
git commit -m "feat: descripción clara del cambio"
```

### 4. Push y Pull Request

```bash
git push origin feature/nombre-descriptivo
# Luego crear Pull Request en GitHub
```

## ⚙️ Configuración del Entorno

### Prerequisitos

- Python 3.9+
- Node.js 16+ (para Playwright)
- Git
- Editor con soporte para Python (recomendado: VS Code)

### Setup Completo

```bash
# 1. Clonar repositorio
git clone https://github.com/Pablo-Cubides/chatbot-whatsapp-llm.git
cd chatbot-whatsapp-llm

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Instalar Playwright
playwright install chromium

# 5. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 6. Inicializar base de datos
python -c "from src.models.admin_db import initialize_schema; initialize_schema()"

# 7. Ejecutar tests
pytest

# 8. Ejecutar servidor
python main_server.py
```

### Dependencias de Desarrollo

Crear `requirements-dev.txt`:

```text
# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0

# Linting y formatting
black>=24.0.0
isort>=5.12.0
flake8>=7.0.0
mypy>=1.8.0

# Pre-commit hooks
pre-commit>=3.6.0

# Documentation
mkdocs>=1.5.0
mkdocs-material>=9.5.0
```

## 📏 Estándares de Código

### Estilo de Código

- **Formatter**: Black con línea máxima de 88 caracteres
- **Import sorting**: isort
- **Linting**: flake8
- **Type checking**: mypy

```bash
# Formatear código
black src/ tests/
isort src/ tests/

# Verificar linting
flake8 src/ tests/

# Verificar tipos
mypy src/
```

### Convenciones de Naming

```python
# Variables y funciones: snake_case
user_name = "john"
def get_user_data():
    pass

# Clases: PascalCase
class UserManager:
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3

# Archivos: snake_case.py
multi_provider_llm.py
```

### Docstrings

Usar formato Google:

```python
def calculate_response_time(start_time: float, end_time: float) -> float:
    """Calculate response time between two timestamps.
    
    Args:
        start_time: Unix timestamp when request started
        end_time: Unix timestamp when request completed
        
    Returns:
        Response time in seconds
        
    Raises:
        ValueError: If end_time is before start_time
        
    Example:
        >>> calculate_response_time(1609459200.0, 1609459201.5)
        1.5
    """
    if end_time < start_time:
        raise ValueError("end_time must be after start_time")
    return end_time - start_time
```

### Type Hints

Siempre usar type hints:

```python
from typing import List, Dict, Optional, Union
from datetime import datetime

def process_messages(
    messages: List[Dict[str, str]], 
    user_id: Optional[str] = None,
    timeout: float = 30.0
) -> Dict[str, Union[str, int, bool]]:
    """Process chat messages with type safety."""
    pass
```

## 🧪 Testing

### Estructura de Tests

```
tests/
├── __init__.py
├── unit/
│   ├── test_auth_system.py
│   ├── test_multi_provider_llm.py
│   └── test_cache_system.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_whatsapp_flow.py
└── fixtures/
    ├── __init__.py
    └── common_fixtures.py
```

### Escribir Tests

```python
import pytest
from unittest.mock import patch, AsyncMock

class TestAuthSystem:
    """Tests para el sistema de autenticación."""
    
    @pytest.fixture
    def auth_manager(self):
        """Fixture para AuthManager."""
        with patch.dict(os.environ, {'JWT_SECRET': 'test-secret-key'}):
            return AuthManager()
    
    def test_hash_password(self, auth_manager):
        """Test hashing de password."""
        password = "test_password_123"
        hashed = auth_manager._hash_password(password)
        
        assert hashed != password
        assert len(hashed) == 60  # bcrypt length
    
    @pytest.mark.asyncio
    async def test_api_endpoint(self, client):
        """Test endpoint de API."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401
```

### Coverage Target

- **Mínimo**: 60% coverage total
- **Objetivo**: 80% coverage total
- **Crítico**: 90% coverage para auth_system, multi_provider_llm

```bash
# Ejecutar tests con coverage
pytest --cov=src --cov-report=html --cov-fail-under=60
```

## 🔄 Proceso de Pull Request

### 1. Checklist Antes de Submit

- [ ] ✅ Tests pasan localmente
- [ ] ✅ Coverage mantiene/mejora porcentaje
- [ ] ✅ Código formateado con black/isort
- [ ] ✅ Sin errores de flake8/mypy
- [ ] ✅ Documentación actualizada
- [ ] ✅ CHANGELOG.md actualizado
- [ ] ✅ Variables de entorno documentadas

### 2. Template de PR

```markdown
## 📋 Descripción

Descripción clara y concisa de los cambios.

## 🎯 Tipo de Cambio

- [ ] 🐛 Bug fix (cambio que arregla un issue)
- [ ] ✨ Nueva feature (cambio que agrega funcionalidad)
- [ ] 💥 Breaking change (cambio que rompe compatibilidad)
- [ ] 📚 Documentación
- [ ] 🧹 Refactor (sin cambios funcionales)
- [ ] ⚡ Performance improvement

## 🧪 Testing

- [ ] Tests unitarios agregados/actualizados
- [ ] Tests de integración agregados/actualizados
- [ ] Tests manuales completados

## 📸 Screenshots (si aplica)

Agregar screenshots para cambios de UI.

## 📝 Notas para Reviewers

Cualquier información adicional para los reviewers.
```

### 3. Proceso de Review

1. **Auto-checks**: CI/CD debe pasar
2. **Peer Review**: Al menos 1 aprobación
3. **Manual Testing**: Para features críticas
4. **Security Review**: Para cambios de auth/security

## 📝 Tipos de Contribuciones

### 🐛 Bug Fixes

```bash
# Rama para bug fix
git checkout -b fix/issue-123-auth-error

# Commit message
git commit -m "fix: resolver error de autenticación con tokens expirados

- Agregar validación de expiración antes de usar token
- Mejorar mensaje de error para usuario
- Agregar test para token expirado

Fixes #123"
```

### ✨ Nuevas Features

```bash
# Rama para feature
git checkout -b feature/claude-integration

# Commit message
git commit -m "feat: agregar integración con Claude API

- Implementar llamadas a Anthropic Claude API
- Agregar configuración para modelo claude-3-haiku
- Agregar tests para nuevos endpoints
- Documentar configuración en README

Resolves #456"
```

### 📚 Documentación

```bash
# Rama para docs
git checkout -b docs/api-reference

# Commit message
git commit -m "docs: agregar documentación completa de API

- Documentar todos los endpoints con ejemplos
- Agregar guía de configuración de variables de entorno
- Mejorar README con casos de uso
- Agregar diagramas de arquitectura"
```

### 🔧 Refactoring

```bash
# Rama para refactor
git checkout -b refactor/auth-system-cleanup

# Commit message
git commit -m "refactor: limpiar sistema de autenticación

- Extraer validaciones a funciones separadas
- Mejorar legibilidad del código
- Eliminar código duplicado
- Mantener misma funcionalidad"
```

## 🐛 Reportar Bugs

### Template de Bug Report

```markdown
## 🐛 Descripción del Bug

Descripción clara del bug.

## 🔄 Pasos para Reproducir

1. Ir a '...'
2. Hacer click en '....'
3. Scroll down to '....'
4. Ver error

## 🎯 Comportamiento Esperado

Descripción de lo que esperabas que pasara.

## 📸 Screenshots

Si es aplicable, agregar screenshots.

## 💻 Información del Sistema

- OS: [e.g. Windows 11, Ubuntu 20.04]
- Python Version: [e.g. 3.9.7]
- Browser: [e.g. Chrome 98]
- Version del proyecto: [e.g. v1.2.0]

## 📋 Información Adicional

Cualquier otra información sobre el problema.
```

## 💡 Sugerir Features

### Template de Feature Request

```markdown
## ✨ Feature Request

### 🎯 ¿El problema que resuelve?

Descripción clara del problema que esta feature resolvería.

### 💡 Solución Propuesta

Descripción clara de lo que quieres que pase.

### 🔄 Alternativas Consideradas

Descripción de soluciones alternativas que consideraste.

### 📋 Información Adicional

Cualquier otra información sobre el feature request.
```

## 🏷️ Convenciones de Commit

Usar [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Formato
<type>[scope]: <description>

[optional body]

[optional footer]

# Ejemplos
feat(auth): agregar login con Google
fix(api): resolver error 500 en /api/chat
docs: actualizar guía de instalación
style(ui): mejorar responsive design
refactor(llm): optimizar llamadas a API
test(auth): agregar tests para JWT
chore: actualizar dependencias
```

### Types Disponibles

- `feat`: Nueva feature
- `fix`: Bug fix
- `docs`: Cambios en documentación
- `style`: Cambios de formatting, sin lógica
- `refactor`: Refactoring sin cambios funcionales
- `test`: Agregar o mejorar tests
- `chore`: Tareas de mantenimiento

## 🆘 Obtener Ayuda

### Canales de Comunicación

- **GitHub Issues**: Para bugs y feature requests
- **GitHub Discussions**: Para preguntas generales
- **Discord**: [Enlace al servidor] - Para chat en tiempo real
- **Email**: soporte@chatbot-empresarial.com

### Preguntas Frecuentes

**Q: ¿Cómo configuro las APIs de LLM para desarrollo?**
A: Puedes usar Ollama local o LM Studio para desarrollo sin necesidad de API keys.

**Q: ¿Los tests requieren APIs externas?**
A: No, los tests usan mocks para APIs externas. Solo necesitas configuración local.

**Q: ¿Cómo ejecuto solo los tests de un módulo?**
A: `pytest tests/test_auth_system.py -v`

**Q: ¿Cómo actualizo la documentación?**
A: Edita los archivos .md y ejecuta `mkdocs serve` para preview local.

## 🎉 Reconocimientos

Agradecemos a todos los contribuidores que hacen posible este proyecto:

- Mantenedores principales
- Contribuidores de código
- Reportadores de bugs
- Escritores de documentación
- Testers de la comunidad

---

## 📄 Licencia

Al contribuir, aceptas que tus contribuciones sean licenciadas bajo la misma licencia MIT del proyecto.

---

¿Listo para contribuir? ¡Haz tu primer fork y comenzamos! 🚀
