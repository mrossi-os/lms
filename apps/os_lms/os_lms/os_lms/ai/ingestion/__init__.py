"""Ingestion subpackage: lesson content → RAG vector store.

Re-exports the public service class so external callers can do
`from os_lms.os_lms.ai.ingestion import IngestionService` without
reaching into the internal module layout.
"""

from .service import IngestionService

__all__ = ["IngestionService"]
