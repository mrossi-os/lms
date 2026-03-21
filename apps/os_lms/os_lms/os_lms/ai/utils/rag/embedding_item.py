from dataclasses import dataclass


@dataclass
class EmbeddingItem:
    text: str
    vector: list[float]
