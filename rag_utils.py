# rag_utils.py

import json, faiss, pickle, numpy as np
from openai import OpenAI

# Inicializaciones al importar
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
index = faiss.read_index("docs.index")
with open("docs.pkl","rb") as f:
    docs = pickle.load(f)
with open("docs/Ultimo_contexto.txt","r", encoding="cp1252") as f:
    daily_context = f.read()

def retrieve_context(query: str, top_k: int = 3) -> str:
    # 1) Embedding
    res = client.embeddings.create(
        model="text-embedding-nomic-embed-text-v1.5",
        input=query
    )
    qemb = res.data[0].embedding

    # 2) Búsqueda
    D, I = index.search(
        np.array([qemb], dtype="float32"),
        k=top_k
    )
    docs_texts = "\n\n".join(docs[i]["text"] for i in I[0])
    return docs_texts

def chat_with_rag(query: str) -> str:
    # Carga payload base
    with open("payload.json", encoding="utf-8") as f:
        payload = json.load(f)

    # Arma mensajes
    rag_ctx = retrieve_context(query)
    payload["messages"] = [
        payload["messages"][0],
        {"role":"system", "content": f"Contexto diario:\n{daily_context}"},
        {"role":"system", "content": f"Contexto RAG:\n{rag_ctx}"},
        {"role":"user",   "content": query}
    ]

    # Llamada a LM Studio
    response = client.chat.completions.create(**payload)
    return response.choices[0].message.content
