import json
from pathlib import Path


def save_to_json(data, file_path):
    """Save data to JSON file and return True on success, False on failure."""
    try:
        # Ensure the directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with Path.open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        return True
    except (TypeError, IOError, OSError) as e:
        print(f"Error saving to JSON: {e}")
        return False
