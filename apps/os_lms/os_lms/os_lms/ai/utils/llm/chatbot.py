from abc import ABC, abstractmethod

from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings


class Chatbot(ABC):

    @abstractmethod
    def set_settings(self, settings: OsLmsSettings):
        pass

    @abstractmethod
    def ask(self, question: str, contexts: list[str]) -> str:
        pass
