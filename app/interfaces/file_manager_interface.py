from abc import ABC, abstractmethod
from pathlib import Path


class FileManagerInterface(ABC):
    @abstractmethod
    def save(self, src: Path, dest_name: str) -> str:
        """Save file to storage and return URL/path."""
        raise NotImplementedError

    @abstractmethod
    def get(self, name: str) -> Path:
        raise NotImplementedError
