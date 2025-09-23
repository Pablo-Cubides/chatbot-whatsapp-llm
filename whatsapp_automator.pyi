from typing import Any, Tuple, Optional

def setup_logging(log_path: str) -> None: ...

def fetch_new_message(page: Any, respond_to_all: bool = False) -> Tuple[Optional[str], Optional[str]]: ...

def send_reply(page: Any, chat_id: str, reply_text: str) -> None: ...

def send_reply_with_typing(page: Any, chat_id: str, reply_text: str, per_char_delay: float = 0.05) -> bool: ...

def _get_message_input(page: Any) -> Any: ...

def cleanup_search_and_return_to_normal(page: Any) -> None: ...

def send_manual_message(page: Any, chat_id: str, message_text: str, per_char_delay: float = 0.05) -> bool: ...

def exit_chat_safely(page: Any) -> None: ...

def process_manual_queue(page: Any) -> bool: ...

def main(*args: Any, **kwargs: Any) -> Any: ...

__all__ = [
    'setup_logging',
    'fetch_new_message',
    'send_reply',
    'send_reply_with_typing',
    '_get_message_input',
    'cleanup_search_and_return_to_normal',
    'send_manual_message',
    'exit_chat_safely',
    'process_manual_queue',
    'main',
]
