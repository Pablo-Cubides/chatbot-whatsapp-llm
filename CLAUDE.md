# CLAUDE.md — Instrucciones para Claude Code

## Reglas de trabajo

- **No usar worktrees.** Trabajar siempre directamente en este directorio (`D:\Mis aplicaciones\Chatbot_Citas`). No usar `isolation: "worktree"` ni operar desde carpetas temporales `.claude/worktrees/`, salvo que el usuario lo pida explícitamente en ese mensaje.

## Contexto del proyecto

Chatbot de WhatsApp con IA multi-proveedor. Ver `.env.example` para las variables de entorno necesarias.

- Backend: FastAPI + SQLAlchemy (SQLite en dev, PostgreSQL en prod)
- Automatización WhatsApp: Playwright
- LLM: configurable vía `DEFAULT_MODEL` en `.env` (ver `stub_chat.py`)
- Auth API: token en variable de entorno `ADMIN_TOKEN`
