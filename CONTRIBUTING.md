# CONTRIBUTING

## Setup local (obligatorio antes de PR)

```bash
# 1. Entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 2. Dependencias de desarrollo
pip install -r requirements-dev.txt

# 3. Hooks de pre-commit
pip install pre-commit
pre-commit install
```

Validación rápida local antes de abrir un PR:

```bash
pre-commit run --all-files
pytest tests/ -q
```

---

## Flujo de trabajo

1. Crear rama desde `main` → `feature/<nombre>` o `fix/<nombre>`
2. Mantener cambios atómicos con tests incluidos
3. Ejecutar linters y tests antes de abrir PR
4. Nunca pushear directamente a `main`

---

## Estándares de código

- **Type hints** en todas las funciones nuevas o modificadas
- **Sin comentarios innecesarios** — el código debe ser legible por sí solo
- Agregar/actualizar tests para cualquier cambio de lógica de negocio
- Cambios de esquema de DB deben incluir migración Alembic:
  ```bash
  alembic revision --autogenerate -m "descripcion_del_cambio"
  alembic upgrade head
  ```

---

## Agregar un nuevo proveedor de IA

Si quieres agregar un proveedor nuevo:

1. Agregar el valor al enum `LLMProvider` en `src/services/multi_provider_llm.py`
2. Agregar la configuración en `load_configurations()` (condicional a la API key)
3. Agregar el dispatch en `_call_provider()`
4. Implementar el método `_call_<nombre>()` — si es compatible con OpenAI, reusar `_call_openai_compatible()`
5. Agregar las variables a `.env` con comentarios sobre el modelo recomendado
6. Actualizar `AI_FALLBACK_ORDER` en `.env`
7. Actualizar la tabla de proveedores en `ARCHITECTURE.md`

---

## Actualizar modelos de IA

Cuando un proveedor lanza nuevos modelos o depreca los existentes:

1. Actualizar el valor default en `load_configurations()` de `multi_provider_llm.py`
2. Actualizar el valor en `.env`
3. Actualizar la tabla de modelos en `README.md` y `ARCHITECTURE.md`
4. Verificar que el nuevo modelo funciona con `POST /api/ai-models/test-connection`

---

## Checklist de PR

- [ ] Tests relevantes en verde (`pytest tests/ -q`)
- [ ] Sin errores de lint (`ruff check .` + `ruff format --check .`)
- [ ] `pre-commit` ejecutado sin errores
- [ ] Documentación actualizada si el cambio afecta comportamiento externo
  - `RUNBOOK.md` para cambios operativos
  - `TROUBLESHOOTING.md` para nuevos modos de fallo conocidos
  - `docs/API.md` para cambios en endpoints
  - `ARCHITECTURE.md` para cambios estructurales
- [ ] Cambios de esquema DB acompañados de migración Alembic
- [ ] Variables de entorno nuevas documentadas en `.env` con comentarios

---

## Tests

```bash
# Suite completa con cobertura
pytest tests/ --cov=src --cov-report=html

# Solo tests rápidos (sin integración)
pytest tests/ -q -m "not integration"

# Test específico
pytest tests/test_auth_system.py -v
```

El CI requiere cobertura mínima del 70%. Verificar antes de abrir PR.
