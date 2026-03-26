from abc import ABC, abstractmethod

from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

from .embedding_item import EmbeddingItem


class TextEmbedder(ABC):
    """Interface for Embedder class."""

    @abstractmethod
    def set_settings(self, settings: OsLmsSettings):
        pass

    @abstractmethod
    def embed_text(self, texts: list[str]) -> list[EmbeddingItem]:
        """Embed a list of texts.

        Returns:
            List of EmbeddingResult with text and vector attributes.
        """
        pass
