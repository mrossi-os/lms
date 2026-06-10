from dataclasses import dataclass


@dataclass
class OsLmsSettings:
    # Legacy RAG tutor fields
    enabled: bool
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    llm_model: str
    openai_key: str

    # Simulation-era fields (additive, all defaulted so existing call sites keep working)
    simulations_enabled: bool = False
    simulation_chat_provider: str = "auto"
    simulation_debrief_provider: str = "auto"
    simulation_provider_default: str = "openai"
    simulation_provider_fallback_order: str = "openai,gemini,deepseek"
    simulation_chat_model: str = ""
    simulation_debrief_model: str = "gpt-4.1"

    # Provider connection details
    openai_base_url: str = ""
    gemini_key: str = ""
    deepseek_key: str = ""
    anthropic_key: str = ""
