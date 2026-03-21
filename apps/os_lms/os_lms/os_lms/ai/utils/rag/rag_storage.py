from abc import ABC, abstractmethod

from .embedding_item import EmbeddingItem


class RagStorage(ABC):
    """Interface for RAG vector storage backends."""

    @abstractmethod
    def delete_by_lesson(self, course: str, lesson: str):
        pass

    @abstractmethod
    def save(self, course: str, lesson: str, items: list[EmbeddingItem]):
        pass

    @abstractmethod
    def search(self, course: str, lesson: str, query: EmbeddingItem):
        pass
