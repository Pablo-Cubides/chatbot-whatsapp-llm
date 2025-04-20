# analyze_conversation.py
import json
from openai import OpenAI

# --- Configuración ---
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
# Carga el esquema
with open("schema.json", encoding="utf-8") as f:
    schema = json.load(f)

# 1) Lee la conversación desde un archivo de texto
#    (puede ser un .txt que exportes de tu chat)
convo_path = input("Ruta al archivo de conversación: ")
with open(convo_path, encoding="utf-8") as f:
    conversation = f.read()

# 2) Arma el payload para análisis
payload = {
    "model": "meta-llama-3.1-8b-instruct",
    "messages": [
        {
          "role": "system",
          "content": "Eres Andrés Cubides, un maestro en seducción al estilo RSD y Ross Jeffries. No reveles tu proceso de pensamiento ni análisis interno. Extrae solo la sugerencia de cita y el nivel de interés de esta conversación."
        },
        {
          "role": "user",
          "content": conversation
        }
    ],
    "temperature": 0.0,
    "max_tokens": 200,
    "stream": False,
    "response_format": {
      "type": "json_schema",
      "json_schema": schema
    }
}

# 3) Llama al API
response = client.chat.completions.create(**payload)

# 4) Imprime el JSON resultante
print("\n=== Análisis Estructurado ===")
print(response.choices[0].message.content)
