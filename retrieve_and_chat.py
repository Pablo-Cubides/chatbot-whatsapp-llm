# retrieve_and_chat.py (fragmento modificado)
import json, faiss, pickle, numpy as np
from openai import OpenAI

# Carga plantilla
with open("payload.json", encoding="utf-8") as f:
    payload = json.load(f)

# Carga índice y docs
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
index = faiss.read_index("docs.index")
with open("docs.pkl","rb") as f:
    docs = pickle.load(f)

# Lee mensaje de usuario
query = input("Usuario: ")

# Embeding de la consulta
res = client.embeddings.create(
    model="text-embedding-nomic-embed-text-v1.5",
    input=query
)
qemb = res.data[0].embedding

# Recupera top‑3
D, I = index.search(np.array([qemb],dtype="float32"), k=3)
rag_context = "\n\n".join(docs[i]["text"] for i in I[0])

# Carga contexto diario
with open("docs/Ultimo_contexto.txt", encoding="cp1252") as f:
    daily_context = f.read()

# Reconstruye payload.messages:
payload["messages"] = [
    payload["messages"][0],  # system prompt original
    {"role":"system", "content": f"Contexto diario:\n{daily_context}"},
    {"role":"system", "content": f"Contexto RAG:\n{rag_context}"},
    {"role":"user",   "content": query}
]

# Llama al API
response = client.chat.completions.create(**payload)
print("\nAsistente:\n", response.choices[0].message.content)
