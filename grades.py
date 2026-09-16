import json


def load_config(path="config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)