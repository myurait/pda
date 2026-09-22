"""Read the versioned declarations without changing their contents."""

from pathlib import Path

import yaml


class Registry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.types = self._read("types", "type")
        self.executors = self._read("executors", "executor_id")

    def _read(self, directory: str, key: str) -> dict[str, dict]:
        result = {}
        for path in sorted((self.root / directory).glob("*.yaml")):
            value = yaml.safe_load(path.read_text())
            result[value[key]] = value
        return result

    def prompt(self, ref: dict, type_name: str) -> str:
        if ref != {"id": type_name, "version": 1}:
            raise ValueError("unsupported prompt_ref")
        return (self.root / self.types[type_name]["prompt"]).read_text()
