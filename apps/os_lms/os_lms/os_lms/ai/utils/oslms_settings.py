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

    # Audio (TTS / STT) — additive, all defaulted. Reuse openai_key / openai_base_url.
    stt_enabled: bool = False
    stt_provider: str = "openai"
    stt_model: str = "gpt-4o-mini-transcribe"
    tts_enabled: bool = False
    tts_provider: str = "openai"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    tts_autoplay_on_stt: bool = False

    # Realtime / voice (speech-to-speech) — additive, all defaulted.
    realtime_enabled: bool = False
    realtime_provider: str = "openai"
    realtime_model: str = ""
    realtime_voice: str = ""
    turn_detection: str = "server_vad"
    realtime_max_session_seconds: int = 300
