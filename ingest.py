# ingest.py
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
import chromadb

print("Loading documents from ./docs ...")
documents = SimpleDirectoryReader("docs", recursive=True).load_data()
print(f"  Loaded {len(documents)} files")

# Use Ollama for embeddings — fully local, no API key needed!
# nomic-embed-text is a small, fast embedding model
print("Setting up embedding model (nomic-embed-text)...")
print("  Run this first if you haven't: ollama pull nomic-embed-text")

Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://localhost:11434",
)

# Set up Chroma as the vector store
print("Connecting to Chroma vector DB...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")  # saves to disk
chroma_collection = chroma_client.get_or_create_collection("portswigger")

vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# This is the magic step — chunks docs, embeds them, stores in Chroma
print("Embedding and indexing... (this takes a few minutes the first time)")
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    show_progress=True,
)

print("\n✓ Done! Your knowledge base is saved in ./chroma_db")
print("  You only need to run this once (or when you add new docs)")