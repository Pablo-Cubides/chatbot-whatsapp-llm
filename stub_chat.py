# Para activar RAG, importa tu módulo:
from rag_utils import chat_with_rag

def chat(user_message: str, chat_id: str, history: list) -> str:
    # Opción simple:
    # return f"Echo 🤖: {user_message}"

    # Opción RAG:
    return chat_with_rag(user_message)
