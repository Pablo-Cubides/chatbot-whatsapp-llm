import argparse
import logging
from chat_sessions import add_or_update_contact, upsert_profile


def main():
    parser = argparse.ArgumentParser(description="Alta/actualización de contacto y perfil")
    parser.add_argument('--chat-id', required=True, help='ID del chat (teléfono o título en WhatsApp)')
    parser.add_argument('--name', default=None)
    parser.add_argument('--enable', action='store_true', help='Habilitar respuestas automáticas')
    parser.add_argument('--disable', action='store_true', help='Deshabilitar respuestas automáticas')
    parser.add_argument('--initial-context', default='', help='Contexto inicial')
    parser.add_argument('--objective', default='', help='Objetivo del chat')
    parser.add_argument('--instructions', default='', help='Instrucciones adicionales')
    parser.add_argument('--ready', action='store_true', help='Marcar perfil como listo')

    args = parser.parse_args()
    auto_enabled = True
    if args.disable:
        auto_enabled = False
    if args.enable:
        auto_enabled = True

    add_or_update_contact(args.chat_id, name=args.name, auto_enabled=auto_enabled)
    upsert_profile(
        args.chat_id,
        initial_context=args.initial_context,
        objective=args.objective,
        instructions=args.instructions,
        is_ready=args.ready or False,
    )
    logging.getLogger(__name__).info(f"Contacto {args.chat_id} actualizado. auto_enabled={auto_enabled}, ready={args.ready}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
