from .oslms_settings import OsLmsSettings


class LLMChatbot:

    def __init__(self, settings: OsLmsSettings):
        self._settings = settings
