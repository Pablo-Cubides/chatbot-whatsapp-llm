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
        print(f"Cleared ALL histories: {n} rows")
    else:
        n = clear_conversation_history(args.chat_id)
        print(f"Cleared chat '{args.chat_id}': {n} rows")

if __name__ == '__main__':
    main()
