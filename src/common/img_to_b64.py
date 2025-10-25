import base64
from pathlib import Path


def img_to_b64(img_path: str | Path) -> str:
    try:
        with Path(img_path).open("rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except FileNotFoundError:
        raise ValueError(f"Image file not found: {img_path}") from None
    except IsADirectoryError:
        raise ValueError(f"Expected a file but found a directory: {img_path}") from None
    except Exception as e:
        raise ValueError(f"Failed to convert image to base64: {e}") from e
