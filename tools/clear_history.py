#!/usr/bin/env python3
"""
Utility to clear conversation history stored in SQLite.
Usage:
  python tools/clear_history.py --chat-id <id>
  python tools/clear_history.py --all
"""
import argparse
from chat_sessions import clear_conversation_history, clear_all_conversation_histories

def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--chat-id', help='Chat ID to clear')
    g.add_argument('--all', action='store_true', help='Clear all chats')
    args = p.parse_args()

    if args.all:
        n = clear_all_conversation_histories()
        import logging
        logging.getLogger(__name__).info("Cleared ALL histories: %s rows", n)
    else:
        n = clear_conversation_history(args.chat_id)
        import logging
        logging.getLogger(__name__).info("Cleared chat '%s': %s rows", args.chat_id, n)

if __name__ == '__main__':
    main()
