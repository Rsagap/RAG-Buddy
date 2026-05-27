# query.py
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
import chromadb
import httpx

# --- Configuration ---
OLLAMA_MODEL = "qwen2.5:3b"  # Override with the OLLAMA_MODEL env var if needed
SIMILARITY_TOP_K = 4       # How many doc chunks to retrieve per query
OLLAMA_REQUEST_TIMEOUT = 300.0

# --- Setup ---
Settings.llm = Ollama(model=OLLAMA_MODEL, base_url="http://localhost:11434", request_timeout=OLLAMA_REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text", base_url="http://localhost:11434")

# Load the existing Chroma DB (no re-embedding!)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = chroma_client.get_or_create_collection("portswigger")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

# Security-focused system prompt
SYSTEM_PROMPT = """You are a web security expert and hacking companion helping a student
learn ethical hacking through PortSwigger Web Security Academy labs.

When answering:
- Explain the vulnerability concept clearly
- Give hints before full solutions (unless asked directly)
- Reference what to look for in Burp Suite when relevant
- Use simple language since the user is learning
- Always remind that these skills are for ethical/authorized testing only
"""

query_engine = index.as_query_engine(
    similarity_top_k=SIMILARITY_TOP_K,
    system_prompt=SYSTEM_PROMPT,
)

# --- Chat Loop ---
print("=" * 50)
print("  PortSwigger AI Hacking Companion  ")
print("  (Ctrl+C to exit)")
print("=" * 50)

while True:
    try:
        question = input("\nYou: ").strip()
        if not question:
            continue
        if question.lower() in ["exit", "quit", "bye"]:
            break
        
        print("\nAssistant: ", end="", flush=True)
        try:
            response = query_engine.query(question)
        except httpx.ReadTimeout:
            print(f"Ollama timed out after {OLLAMA_REQUEST_TIMEOUT:.0f} seconds. Use a smaller/faster model or reduce the prompt size.")
            continue
        except Exception as exc:
            message = str(exc)
            if "system memory" in message:
                print("Ollama model too large for available RAM. Set OLLAMA_MODEL to a smaller model like llama3.2:3b or qwen2.5:3b.")
                continue
            if "not found" in message or "pull" in message:
                print(f"Ollama could not load model '{OLLAMA_MODEL}'. Pull it first or set OLLAMA_MODEL to an installed model.")
                continue
            raise

        print(response)
        
        # Optional: show which docs were used as sources
        print("\n  [Sources used]:", end=" ")
        for node in response.source_nodes:
            source = node.metadata.get("file_name", "unknown")
            score = round(node.score or 0, 2)
            print(f"{source}({score})", end=" ")
        print()
        
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        break