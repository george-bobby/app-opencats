from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_task_stages():
    task_stages = load_json(settings.DATA_PATH.joinpath("task_stages.json"))

    logger.start(f"Inserting {len(task_stages)} task stages into Odoo...")
    async with OdooClient() as client:
        stage_records = []
        for stage in task_stages:
            stage_record = {
                "name": stage["name"],
                "fold": stage.get("fold", False),
            }
            stage_records.append(stage_record)
        await client.create("project.task.type", [stage_records])
    logger.succeed(f"Inserted {len(task_stages)} task stages successfully.")
