from pathlib import Path
from app.interfaces.file_manager_interface import FileManagerInterface


class LocalFileManager(FileManagerInterface):
    def __init__(self, root: Path = Path("./storage")):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, src: Path, dest_name: str) -> str:
        dest = self.root / dest_name
        src.replace(dest)
        return str(dest)

    def get(self, name: str) -> Path:
        p = self.root / name
        if not p.exists():
            raise FileNotFoundError(name)
        return p
