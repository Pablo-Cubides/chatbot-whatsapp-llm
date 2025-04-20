# build_vectorstore.py
import os, pickle, numpy as np
from openai import OpenAI
import faiss

# 1) Inicializa cliente
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

# 2) Carga y embebe cada documento
docs, embs = [], []
for fn in os.listdir("docs"):
    path = os.path.join("docs", fn)
with open(path, encoding="utf-8", errors="ignore") as f:
    text = f.read()
    docs.append({"name": fn, "text": text})
    res = client.embeddings.create(
        model="text-embedding-nomic-embed-text-v1.5",
        input=text
    )
    embs.append(res.data[0].embedding)  # :contentReference[oaicite:0]{index=0}

# 3) Crea índice FAISS y guárdalo
embs = np.array(embs, dtype="float32")
dim = embs.shape[1]
index = faiss.IndexFlatIP(dim)
index.add(embs)
faiss.write_index(index, "docs.index")

# 4) Guarda la lista de documentos
with open("docs.pkl", "wb") as f:
    pickle.dump(docs, f)
