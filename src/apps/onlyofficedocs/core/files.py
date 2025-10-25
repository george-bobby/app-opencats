import re
import urllib.parse
from pathlib import Path

import requests

from apps.onlyofficedocs.config.settings import settings
from common.logger import logger


def upload_file(file_path: str) -> dict:
    """Upload a file to OnlyOffice Docs server."""
    current_dir = Path.cwd()
    absolute_file_path = current_dir / file_path

    if not absolute_file_path.exists():
        return {"success": False, "error": "File not found", "file_name": file_path}

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": settings.BASE_URL,
        "Referer": f"{settings.BASE_URL}/example/?userid={settings.USER_ID}&lang={settings.LANGUAGE}&directUrl=false",
        "X-Requested-With": "XMLHttpRequest",
    }

    with absolute_file_path.open("rb") as file:
        files = {"uploadedFile": (absolute_file_path.name, file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

        try:
            response = requests.post(f"{settings.BASE_URL}{settings.UPLOAD_ENDPOINT}", files=files, headers=headers, timeout=30)
            response.raise_for_status()

            try:
                return {"success": True, "data": response.json(), "file_name": absolute_file_path.name}
            except ValueError:
                return {"success": True, "data": response.text, "file_name": absolute_file_path.name}

        except requests.RequestException as e:
            return {"success": False, "error": str(e), "file_name": absolute_file_path.name}


def get_data_files() -> list[str]:
    """Get all .docx files from the data directory."""
    return [f"apps/onlyofficedocs/data/{f.name}" for f in settings.DATA_PATH.glob("*.docx")]


def upload_files(file_paths: list[str]) -> list[dict]:
    """Upload multiple files."""
    results = []
    for file_path in file_paths:
        result = upload_file(file_path)
        results.append(result)

        if result["success"]:
            logger.succeed(f"{result['file_name']}")
        else:
            logger.error(f"{result['file_name']}: {result['error']}")

    return results


def get_uploaded_files() -> dict:
    """Get all uploaded files from OnlyOffice server by parsing the main page."""
    try:
        response = requests.get(f"{settings.BASE_URL}/example/", timeout=30)
        response.raise_for_status()

        # Parse HTML to extract file information
        files = []

        # Find all table rows with file information
        file_rows = re.findall(
            r'<tr class="tableRow"[^>]*title="([^"]+)"[^>]*>.*?<a class="stored-edit[^"]*"[^>]*href="[^"]*fileName=([^"]+)"[^>]*>\s*<span>([^<]+)</span>', response.text, re.DOTALL
        )

        for title, encoded_name, display_name in file_rows:
            # Decode URL-encoded filename
            decoded_name = urllib.parse.unquote(encoded_name)

            # Extract file extension and type
            file_ext = decoded_name.split(".")[-1].lower() if "." in decoded_name else ""
            file_type = "unknown"

            if file_ext in ["docx", "doc", "odt", "rtf", "txt"]:
                file_type = "word"
            elif file_ext in ["xlsx", "xls", "ods", "csv"]:
                file_type = "cell"
            elif file_ext in ["pptx", "ppt", "odp"]:
                file_type = "slide"
            elif file_ext == "pdf":
                file_type = "pdf"

            files.append(
                {
                    "name": decoded_name,
                    "display_name": display_name,
                    "title": title,
                    "extension": file_ext,
                    "type": file_type,
                    "edit_url": f"/example/editor?fileName={encoded_name}",
                    "download_url": f"/example/download?fileName={encoded_name}",
                }
            )

        return {"success": True, "files": files, "count": len(files)}

    except requests.RequestException as e:
        return {"success": False, "error": str(e), "files": [], "count": 0}


def download_file(download_url: str, save_path: str) -> dict:
    """Download a single file from OnlyOffice server."""
    try:
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()

        # Write file to specified path
        save_file = Path(save_path)
        with save_file.open("wb") as f:
            f.write(response.content)

        return {"success": True, "path": save_path, "size": len(response.content)}

    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def download_all_files(files_list: list, downloads_dir: str) -> dict:
    """Download multiple files from OnlyOffice server to specified directory."""
    downloaded_files = []
    failed_files = []

    for file_info in files_list:
        file_name = file_info["name"]
        download_url = f"{settings.BASE_URL}{file_info['download_url']}"
        save_path = Path(downloads_dir) / file_name

        result = download_file(download_url, str(save_path))

        if result["success"]:
            downloaded_files.append({"name": file_name, "path": result["path"], "size": result["size"]})
            logger.succeed(f"Downloaded {file_name}")
        else:
            failed_files.append({"name": file_name, "error": result["error"]})
            logger.error(f"Failed to download {file_name}: {result['error']}")

    return {"success": True, "downloaded": len(downloaded_files), "failed": len(failed_files), "downloaded_files": downloaded_files, "failed_files": failed_files}


def delete_file(file_name: str) -> dict:
    """Delete a single file from OnlyOffice server."""
    headers = {
        "Accept": "*/*",
        "Origin": settings.BASE_URL,
        "Referer": f"{settings.BASE_URL}/example/",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "text/xml",
    }

    # URL encode the filename
    encoded_filename = urllib.parse.quote(file_name)
    delete_url = f"{settings.BASE_URL}/example/file?filename={encoded_filename}"

    try:
        response = requests.delete(delete_url, headers=headers, timeout=30)
        response.raise_for_status()

        return {"success": True, "file_name": file_name}

    except requests.RequestException as e:
        return {"success": False, "error": str(e), "file_name": file_name}


def delete_all_files(files_list: list) -> dict:
    """Delete multiple files from OnlyOffice server."""
    deleted_files = []
    failed_files = []

    for file_info in files_list:
        file_name = file_info["name"]
        result = delete_file(file_name)

        if result["success"]:
            deleted_files.append({"name": file_name})
            logger.succeed(f"Deleted {file_name}")
        else:
            failed_files.append({"name": file_name, "error": result["error"]})
            logger.error(f"Failed to delete {file_name}: {result['error']}")

    return {"success": True, "deleted": len(deleted_files), "failed": len(failed_files), "deleted_files": deleted_files, "failed_files": failed_files}
