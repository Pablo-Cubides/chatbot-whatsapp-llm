# rag_utils.py

import json
import pickle
import os
from typing import List
import numpy as np
from openai import OpenAI

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None

# Inicializaciones al importar (robustas)
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", timeout=120.0)

_INDEX = None
_DOCS: List[dict] = []
_DAILY = ""

def _read_text_safe(path: str) -> str:
    if not os.path.exists(path):
        return ""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                return f.read()
        except Exception:
            continue
    return ""

def _lazy_load_index_and_docs():
    global _INDEX, _DOCS, _DAILY
    if _INDEX is None and faiss is not None and os.path.exists("docs.index"):
        try:
            _INDEX = faiss.read_index("docs.index")
        except Exception:
            _INDEX = None
    if not _DOCS and os.path.exists("docs.pkl"):
        try:
            with open("docs.pkl", "rb") as f:
                _DOCS = pickle.load(f)
        except Exception:
            _DOCS = []
    if not _DAILY:
        _DAILY = _read_text_safe(os.path.join("Docs", "Ultimo_contexto.txt")) or _read_text_safe("docs/Ultimo_contexto.txt")

def retrieve_context(query: str, top_k: int = 3) -> str:
    _lazy_load_index_and_docs()
    if faiss is None or _INDEX is None or not _DOCS:
        return ""

    try:
        # 1) Embedding
        res = client.embeddings.create(
            model="text-embedding-nomic-embed-text-v1.5",
            input=query
        )
        qemb = res.data[0].embedding

        # 2) Búsqueda
        distances, indices = _INDEX.search(
            np.array([qemb], dtype="float32"),
            k=top_k
        )
        # Filtro por rangos válidos
        ids = [i for i in indices[0] if 0 <= i < len(_DOCS)]
        docs_texts = "\n\n".join((_DOCS[i].get("text") or "") for i in ids)
        return docs_texts
    except Exception as e:
        # Si falla el RAG (ej: embeddings no disponibles), devolver vacío
        import logging
        logging.getLogger(__name__).warning(f"RAG falló: {e}")
        return ""

def chat_with_rag(query: str) -> str:
    _lazy_load_index_and_docs()
    with open("payload.json", encoding="utf-8") as f:
        payload = json.load(f)

    rag_ctx = retrieve_context(query)
    daily_context = _DAILY

    payload["messages"] = [
        payload["messages"][0],
        {"role": "system", "content": f"Contexto diario:\n{daily_context}"} if daily_context else None,
        {"role": "system", "content": f"Contexto RAG:\n{rag_ctx}"} if rag_ctx else None,
        {"role": "user", "content": query},
    ]
    # Limpia None
    payload["messages"] = [m for m in payload["messages"] if m]

    response = client.chat.completions.create(**payload)
    return response.choices[0].message.content
