# chromadb_client.py — REMOVED in v3.0
#
# ChromaDB has been replaced by Qdrant 1.13+.
# See: src/infrastructure/clients/qdrant_client.py
#
# This file is kept as an empty placeholder so existing imports fail loudly
# rather than silently (the module exists but has no usable class).

raise ImportError(
    "chromadb_client is no longer available. "
    "Import QdrantVectorClient from src.infrastructure.clients.qdrant_client instead."
)
