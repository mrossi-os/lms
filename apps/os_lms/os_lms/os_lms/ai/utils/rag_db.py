import frappe

from .oslms_settings import OsLmsSettings
from .rag.openai_api_embedder import OpenAIApiEmbedder
from .rag.rag_storage import RagStorage
from .rag.redis_rag_storage import RedisRagStorage
from .rag.text_embedder import TextEmbedder


class RagDB:

    def __init__(self, settings: OsLmsSettings):
        self.__db = RedisRagStorage()
        self.__settings = settings
        self.__embedder = None

    @property
    def _settings(self) -> OsLmsSettings:
        return self.__settings

    @property
    def _db(self) -> RagStorage:
        return self.__db

    @property
    def _embedder(self) -> TextEmbedder:
        if self.__embedder is None:
            self.__embedder = OpenAIApiEmbedder()
            self.__embedder.set_model(self._settings.embedding_model)
        return self.__embedder

    def ingest_data(self, course: str, lesson: str, text: str):
        if not course or not lesson or not text:
            return

        # clear db
        self._db.delete_by_lesson(course, lesson)

        chunks = self._chunk_text(text)
        if not chunks:
            frappe.throw("No chunks generated from content")

        embeddings = self._embedder.embed_text(chunks)
        self._db.save(course, lesson, embeddings)

    def search(self, course: str, lesson: str, query: str):
        query_embeddes = self._embedder.embed_text([query])[0]
        return self._db.search(course, lesson, query_embeddes, self._settings.top_k)

    def _chunk_text(self, text):
        """Split text into chunks by characters."""

        chunk_size = self._settings.chunk_size
        chunk_overlap = self._settings.chunk_overlap

        if not text or len(text) == 0:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - chunk_overlap
            if start < 0:
                start = 0
            if end >= len(text):
                break

        return chunks
