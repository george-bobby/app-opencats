import json
from pathlib import Path

from apps.teable.config.constants import EXAMPLE_ATTACHMENTS_URL, TABLES_FILE
from apps.teable.config.settings import settings
from apps.teable.core import bases
from apps.teable.utils.teable import get_teable_client
from common.logger import Logger


logger = Logger()


async def insert_attachments():
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    client = await get_teable_client()

    for table in tables:
        for field in table.get("fields", []):
            if field.get("type") == "attachment":
                table_id = None
                space_name = table.get("parent_workspace_name")
                base_name = table.get("parent_base_name")
                table_name = table.get("name")
                base_id = await bases.get_base_id_by_name(space_name, base_name)
                existing_tables = await client.get_tables(base_id)
                for existing_table in existing_tables:
                    if existing_table.get("name") == table_name:
                        table_id = existing_table.get("id")
                        break

                if not table_id:
                    return

                fields = await client.get_fields(table_id)
                records = (await client.get_records(table_id, take=1000))["records"]

                for field in fields:
                    if field.get("type") == "attachment":
                        field_id = field.get("id")

                        for record in records:
                            record_id = record.get("id")

                            try:
                                await client.upload_attachment(
                                    table_id,
                                    record_id,
                                    field_id,
                                    EXAMPLE_ATTACHMENTS_URL,
                                )
                            except Exception:
                                logger.info(f"Adding attachment to record {record_id} not successful")

                logger.succeed(f"Added attachments to {table_name} successfully")
