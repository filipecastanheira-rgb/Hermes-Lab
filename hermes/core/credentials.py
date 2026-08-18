import json
from pathlib import Path


class CredentialStore:
    def get(self, name: str) -> dict:
        raise NotImplementedError

    def list_names(self) -> list[str]:
        raise NotImplementedError


class LocalFileCredentialStore(CredentialStore):
    def __init__(self, path: Path):
        self.path = path

    def get(self, name: str) -> dict:
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if name not in data:
            raise KeyError(f"Credential not found: {name}")

        return data[name]

    def list_names(self) -> list[str]:
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return list(data.keys())


def get_store() -> CredentialStore:
    path = Path(__file__).resolve().parents[2] / "secrets" / "credentials.json"
    return LocalFileCredentialStore(path)


credentials = get_store()
