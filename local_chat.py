#!/usr/bin/env python3
"""
Small terminal chat client that uses stub_chat.chat and chat_sessions to persist history.
Usage: python local_chat.py --chat-id <id>
"""
import argparse
import sys
from stub_chat import chat as model_chat
from chat_sessions import load_last_context, save_context

parser = argparse.ArgumentParser()
parser.add_argument('--chat-id', default='local_user', help='chat id / user id to store contexts')
args = parser.parse_args()
chat_id = args.chat_id

print(f"Local chat client. Chat id: {chat_id}. Type Ctrl+C to exit.")

# Load last history (expected list of messages)
history = load_last_context(chat_id) or []

try:
    while True:
        user = input('You: ')
        if not user.strip():
            continue
        reply = model_chat(user, chat_id, history)
        print('\nBot:', reply, '\n')
        # Append to history simple representation
        history.append({'role':'user','content':user})
        history.append({'role':'assistant','content':reply})
        save_context(chat_id, history)
except KeyboardInterrupt:
    print('\nBye')
    sys.exit(0)
