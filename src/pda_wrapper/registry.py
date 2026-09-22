import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator


class Registry:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.types = self._load_yaml("types", "type")
        self.executors = self._load_yaml("executors", "executor_id")
        for definition in self.types.values():
            for key in ("input_schema", "output_schema"):
                Draft7Validator.check_schema(definition[key])
        self.questions = self._load_json("judge/questions.json")
        self.fixture = self._load_json("judge/fixture.json")
        self.workflow = self._load_json("workflows/pda_job.json")

    def _load_yaml(self, folder: str, key: str) -> dict:
        items = [
            yaml.safe_load(path.read_text())
            for path in sorted((self.directory / folder).glob("*.yaml"))
        ]
        return {item[key]: item for item in items}

    def _load_json(self, name: str) -> dict | list:
        return json.loads((self.directory / name).read_text())

    def prompt(self, reference: dict) -> str:
        definition = self.types[reference["id"]]
        if reference["version"] != 1:
            raise ValueError("unsupported_prompt_version")
        return (self.directory / definition["prompt"]).read_text()
