# ADR-0002: Mantener `whatsapp_automator` en Playwright síncrono

## Estado
Accepted — 2026-02-15

## Contexto
Se evaluó migrar `whatsapp_automator.py` desde `playwright.sync_api` a `playwright.async_api`.
El módulo actual:
- ejecuta un loop único y persistente sobre una sesión de navegador;
- coordina llamadas bloqueantes externas (modelo, reasoner, colas) mediante `ThreadPoolExecutor`;
- prioriza robustez operacional y recuperación ante fallos por encima de throughput concurrente.

Además, ya se implementó apagado ordenado por señales (`SIGTERM`/`SIGINT`) y cierre explícito de recursos Playwright.

## Decisión
**No migrar por ahora a `async_playwright`.**
Se mantiene arquitectura síncrona para el automator y se documenta la decisión.

## Razones
1. **Riesgo operativo menor**: la ruta síncrona está probada en producción y la migración implica cambios profundos de control de flujo.
2. **Ganancia marginal**: el bot opera sobre una sola sesión de WhatsApp Web; no hay beneficio claro de concurrencia I/O para múltiples páginas.
3. **Complejidad adicional**: migrar a async obligaría a revisar timeouts, backpressure, señalización y dependencias que hoy son bloqueantes.
4. **Shutdown ya resuelto**: con `SHUTDOWN_EVENT` + cierre ordenado se cubre el principal gap de confiabilidad.

## Consecuencias
- Se conserva el modelo síncrono actual de `whatsapp_automator.py`.
- Se reduce riesgo de regresiones inmediatas.
- La deuda técnica queda explícita para una fase futura.

## Plan de revisión futura
Reabrir esta ADR si se cumple al menos una condición:
- soporte oficial para múltiples sesiones concurrentes;
- necesidad de escalar procesamiento en paralelo por conversación;
- métricas de latencia demuestren cuello de botella atribuible al runtime síncrono.

## Alternativas consideradas
- Migración completa a `async_playwright` ahora: descartada por costo/beneficio actual.
- Wrapper híbrido sync/async parcial: descartado por complejidad y superficie de fallo.
