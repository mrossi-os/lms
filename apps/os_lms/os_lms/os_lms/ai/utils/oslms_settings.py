from dataclasses import dataclass


@dataclass
class OsLmsSettings:
    enabled: bool
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    llm_model: str
    system_prompt: str
