import json
import mimetypes
from pathlib import Path

from apps.supabase.config.settings import settings
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


async def create_storage_buckets():
    """
    Create storage buckets in Supabase based on the configuration in storage.json.
    Each bucket is created with specified settings like public access, file size limits,
    and allowed MIME types.
    """
    logger.start("Creating storage buckets...")

    # Load storage configuration
    storage_config_path = settings.DATA_PATH / "storage.json"
    with Path.open(storage_config_path) as f:
        storage_config = json.load(f)

    # Get Supabase client
    client = await get_supabase_client()

    # Create each bucket
    for bucket in storage_config["buckets"]:
        try:
            await client.storage.create_bucket(
                id=bucket["name"], options={"public": bucket["public"], "file_size_limit": bucket["file_size_limit"], "allowed_mime_types": bucket.get("allowed_mime_types", None)}
            )
            logger.succeed(f"Created bucket: {bucket['name']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.fail(f"Bucket {bucket['name']} already exists")
            else:
                logger.fail(f"Failed to create bucket {bucket['name']}: {e!s}")


def get_storage_url(bucket: str, path: str) -> str:
    """Generate a storage URL without hostname"""
    return f"/storage/v1/object/public/{bucket}/{path}"


async def upload_storage_content():
    """
    Upload files to all storage buckets in Supabase based on the configuration in storage.json.
    Loops through all buckets and uploads files from their respective local directories.
    Returns a dictionary with uploaded files metadata for each bucket.
    """
    logger.start("Uploading content to all Supabase storage buckets...")

    # Load storage configuration
    storage_config_path = settings.DATA_PATH / "storage.json"
    with Path.open(storage_config_path) as f:
        storage_config = json.load(f)

    # Get Supabase client
    client = await get_supabase_client()

    all_uploaded_files = {}

    # Process each bucket
    for bucket_config in storage_config["buckets"]:
        bucket_name = bucket_config["name"]
        logger.info(f"Processing bucket: {bucket_name}")

        # Find the path configuration for this bucket
        bucket_path_config = None
        for path_config in storage_config["paths"]:
            if path_config["bucket_name"] == bucket_name:
                bucket_path_config = path_config
                break

        if not bucket_path_config:
            logger.warning(f"No path configuration found for bucket: {bucket_name}")
            continue

        # Get local directory path
        local_dir = settings.DATA_PATH / "storage" / bucket_path_config["path"]
        if not local_dir.exists():
            logger.warning(f"Local directory not found: {local_dir}")
            continue

        uploaded_files = []

        # Upload all files in the directory
        for file_path in local_dir.iterdir():
            if file_path.is_file():
                try:
                    # Get file size and mime type
                    file_size = file_path.stat().st_size
                    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

                    # Generate storage path
                    storage_path = f"{file_path.name}"

                    # Read file content
                    with file_path.open("rb") as f:
                        file_content = f.read()

                    # Upload to Supabase
                    await client.storage.from_(bucket_name).upload(path=storage_path, file=file_content, file_options={"content-type": mime_type})

                    # Get URL
                    url = get_storage_url(bucket_name, storage_path)

                    uploaded_files.append({"filename": file_path.name, "url": url, "storage_path": storage_path, "file_size_bytes": file_size, "mime_type": mime_type})

                    logger.info(f"Uploaded {file_path.name} to {bucket_name}")

                except Exception as e:
                    if "already exists" in str(e).lower():
                        # If file exists, just get its URL
                        storage_path = f"{file_path.name}"
                        url = get_storage_url(bucket_name, storage_path)

                        # Get file info for existing file
                        file_size = file_path.stat().st_size
                        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

                        uploaded_files.append({"filename": file_path.name, "url": url, "storage_path": storage_path, "file_size_bytes": file_size, "mime_type": mime_type})
                        logger.warning(f"File {file_path.name} already exists in {bucket_name}, using existing URL")
                    else:
                        logger.error(f"Failed to upload {file_path.name} to {bucket_name}: {e!s}")

        all_uploaded_files[bucket_name] = uploaded_files
        logger.succeed(f"Processed {len(uploaded_files)} files for bucket: {bucket_name}")

    # Save all uploaded files metadata
    if any(all_uploaded_files.values()):
        metadata_file = settings.DATA_PATH / "uploaded_storage_content.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with metadata_file.open("w") as f:
            json.dump(all_uploaded_files, f, indent=2)

        total_files = sum(len(files) for files in all_uploaded_files.values())
        logger.info(f"Saved metadata for {total_files} uploaded files across all buckets")

    logger.succeed("Completed uploading content to all storage buckets")
    return all_uploaded_files
