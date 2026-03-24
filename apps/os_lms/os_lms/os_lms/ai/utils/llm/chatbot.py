from abc import ABC, abstractmethod


class Chatbot(ABC):

    @abstractmethod
    def set_model(self, model: str) -> None:
        pass

    @abstractmethod
    def set_system_prompt(self, system_prompt: str) -> None:
        pass

    @abstractmethod
    def ask(self, question: str, contexts: list[str]) -> str:
        pass
