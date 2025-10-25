import json
from pathlib import Path


def load_json(filepath: str):
    with Path.open(filepath) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON from {filepath}: {e}") from e
        except FileNotFoundError as e:
            raise ValueError(f"File not found: {filepath}") from e
        except Exception as e:
            raise ValueError(f"An unexpected error occurred while loading {filepath}: {e}") from e
