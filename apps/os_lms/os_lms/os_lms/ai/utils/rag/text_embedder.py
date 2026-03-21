from abc import ABC, abstractmethod

from .embedding_item import EmbeddingItem


class TextEmbedder(ABC):
    """Interface for Embedder class."""

    @abstractmethod
    def set_model(self, model: str):
        pass

    @abstractmethod
    def embed_text(self, texts: list[str]) -> list[EmbeddingItem]:
        """Embed a list of texts.

        Returns:
            List of EmbeddingResult with text and vector attributes.
        """
        pass
