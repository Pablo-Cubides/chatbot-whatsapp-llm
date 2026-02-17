# CONTRIBUTING

## Setup local (obligatorio antes de PR)

1. Crear/activar entorno virtual.
2. Instalar dependencias del proyecto.
3. Instalar hooks de pre-commit.

```bash
pip install -r requirements.txt
pip install pre-commit
pre-commit install
```

Validación rápida local recomendada:

```bash
pre-commit run --all-files
pytest -q -k "phase1 or phase2 or phase3 or phase5 or phase6"
```

Mutation testing (opcional, no bloquea CI):

```bash
mutmut run
mutmut results
mutmut show <id>
```

## Flujo recomendado
1. Crear rama por cambio (`feature/*`, `fix/*`).
2. Mantener cambios atómicos y con pruebas.
3. Ejecutar linters/tests antes de abrir PR.

## Estándares
- Anotar tipos en funciones nuevas/modificadas.
- Mantener docstrings en routers y servicios públicos.
- Agregar o actualizar tests de unidad/integración para cambios críticos.

## Checklist de PR
- [ ] Tests relevantes en verde.
- [ ] Sin errores de lint.
- [ ] `pre-commit` ejecutado sin errores.
- [ ] Documentación actualizada (`RUNBOOK.md`, `TROUBLESHOOTING.md` cuando aplique).
- [ ] Cambios de esquema acompañados de migración Alembic.
- [ ] (Opcional) Resultado de mutation testing revisado para cambios críticos.
