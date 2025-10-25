import asyncio

import pandas as pd

from apps.odooproject.config.settings import settings
from apps.odooproject.models.task import Task, TaskResponse
from common.logger import logger
from common.openai import get_system_prompt, openai
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "tasks.json"


async def generate_tasks(count: int):
    logger.start(f"Generating {count} tasks for each project... (not including subtasks and blockers)")

    df_projects = pd.read_json(settings.DATA_PATH.joinpath("projects.json"))
    df_activity_types = pd.read_json(settings.DATA_PATH.joinpath("activity_types.json"))
    df_task_stages = pd.read_json(settings.DATA_PATH.joinpath("task_stages.json"))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            tasks = await _generate_tasks(count, df_projects, df_activity_types, df_task_stages)
            save_to_json([task.model_dump() for task in tasks], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))
            logger.succeed(f"Generated {len(tasks)} tasks")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info("Retrying...")
            else:
                logger.error(f"Failed to generate tasks after {max_retries} attempts: {e}")
                return []


async def _generate_tasks(count: int, df_projects: pd.DataFrame, df_activity_types: pd.DataFrame, df_task_stages: pd.DataFrame) -> list[Task]:
    promises = []
    for project_name in df_projects["name"].to_list():
        task_prompt = f"""
            Generate exactly {count} realistic tasks for project {project_name} in an Odoo Project system.
            
            The tasks should be relevant for a US-based SME in the '{settings.DATA_THEME_SUBJECT}' industry.
            Each task should have:
            - A descriptive task name that clearly indicates what needs to be done, and relate to {project_name}
            - A project name is {project_name}
            - A detailed description explaining the task requirements and objectives
            - A priority: 'low', 'normal', or 'high'
            - A realistic deadline date (within 2025)
            - A stage: Get from provided list of task stages: {df_task_stages["name"].to_list()}
            - 2-4 relevant tags that help categorize the task
            - A next activity type: Get from provided list of activity types: {df_activity_types["name"].to_list()}
            - A list of child tasks that are related to the parent task
            - A list of blockers that are related to the task
            - A list of email addresses that were in the CC of the incoming emails from this task and that are not currently linked to an existing customer.
            The domain must be gmail.com or outlook.com
            
            Tasks should represent various types of work activities including planning, execution, review, and completion phases.
        """

        promises.append(
            openai.responses.parse(
                model=settings.DEFAULT_MODEL,
                input=[
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": task_prompt},
                ],
                text_format=TaskResponse,
                temperature=0.2,
            )
        )

    responses = await asyncio.gather(*promises)

    tasks: list[Task] = []
    for response in responses:
        if not response.output_parsed:
            logger.warning("No tasks generated. Please generate again.")
            return

        tasks.extend(response.output_parsed.tasks)

    if not tasks:
        logger.warning("No tasks generated. Please generate again.")
        return []

    return tasks
