# Seguridad y mantenimiento

Este repositorio conserva un proyecto independiente histórico. Las nuevas automatizaciones se desarrollan en Cubides Bots; aquí el mantenimiento es limitado y no se ofrece un SLA de respuesta ni soporte de producción garantizado.

## Reportar un problema

Usa el reporte privado de vulnerabilidades de GitHub cuando esté habilitado. No incluyas claves, tokens, conversaciones o datos de personas en issues públicos. Aporta una reproducción mínima con información sintética y comunica el detalle sensible por un canal privado del propietario.

## Revisión de dependencias de octubre de 2026

| Paquete | Versión anterior | Versión de mantenimiento |
|---|---|---|
| certifi | 2026.4.22 | 2026.10.19 |
| cryptography | 48.0.1 | 50.0.0 |
| soupsieve | 2.8.4 | 2.9.0 |
| urllib3 | 2.7.0 | 2.8.0 |
| aiohttp | 3.14.1 | 3.14.4 |
| httpx2 (transitiva) | 2.3.0 | 2.12.0 |
| httpcore2 (transitiva) | 2.3.0 | 2.12.0 |
| idna (compatibilidad del cliente HTTP) | 3.15 | 3.18 |

Las versiones se contrastaron con los avisos publicados en la API JSON de PyPI. Los archivos de requisitos principal e histórico se actualizaron conjuntamente donde declaraban esos paquetes. Las imágenes de API y scheduler también actualizan el pin oficial de Python de 3.13.3 a 3.13.16. Esta comprobación es puntual: revisa nuevos avisos antes de volver a desplegar.

## Límites y controles

- Configura valores propios para JWT, contraseñas, proveedores y base de datos; nunca uses credenciales de ejemplo en un despliegue.
- Conserva la autenticación y autorización de las rutas, las firmas de webhooks y el rate limiting.
- Restringe exposición de red, CORS y permisos del proceso. Las comprobaciones locales de mantenimiento usan loopback.
- No subas archivos de entorno, sesiones de navegador, conversaciones, claves de cifrado ni bases de datos.
- Prueba login y rutas protegidas además de `/healthz`: se corrigió un import faltante que permitía un health check exitoso mientras faltaban rutas.
- Las pruebas no envían mensajes reales ni validan por sí solas los permisos de una cuenta externa.

Si una credencial estuvo expuesta, revócala o rótala. Una actualización de dependencias o un commit que borre el valor no revoca la credencial ni elimina las copias históricas. Los despliegues existentes deben reconstruirse con las dependencias corregidas; actualizar GitHub no modifica automáticamente un servidor ya instalado.
