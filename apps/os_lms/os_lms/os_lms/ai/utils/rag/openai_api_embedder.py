import os

import frappe
import requests
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings
from .text_embedder import TextEmbedder
from .embedding_item import EmbeddingItem


class OpenAIApiEmbedder(TextEmbedder):
    """OpenAI API-based text embedder."""

    def __init__(self):
        self._api_key = None
        self._model = "text-embedding-3-small"

    def set_settings(self, settings: OsLmsSettings):
        self._model = settings.embedding_model
        self._api_key = settings.openai_key

    MAX_TOKENS_PER_REQUEST = 200000
    APPROX_CHARS_PER_TOKEN = 4

    def embed_text(self, texts: list[str]) -> list[EmbeddingItem]:
        if not texts or not self._api_key:
            return []

        batches = self._split_into_batches(texts)
        results = []
        for batch in batches:
            results.extend(self._embed_batch(batch))
        return results

    def _split_into_batches(self, texts: list[str]) -> list[list[str]]:
        """Split texts into batches that fit within the token limit."""
        max_chars = self.MAX_TOKENS_PER_REQUEST * self.APPROX_CHARS_PER_TOKEN
        batches = []
        current_batch = []
        current_chars = 0

        for text in texts:
            text_chars = len(text)
            if current_batch and current_chars + text_chars > max_chars:
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
            current_batch.append(text)
            current_chars += text_chars

        if current_batch:
            batches.append(current_batch)

        return batches

    def _embed_batch(self, texts: list[str]) -> list[EmbeddingItem]:
        """Send a single embedding request for a batch of texts."""
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": texts,
                "model": self._model,
            },
            timeout=60,
        )

        if response.status_code != 200:
            frappe.throw(f"OpenAI API error: {response.text}")

        data = response.json()
        return [
            EmbeddingItem(text=text, vector=item["embedding"])
            for text, item in zip(texts, data["data"])
        ]
