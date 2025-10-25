from apps.odooproject.config.settings import settings
from apps.odooproject.models.project import Project, ProjectResponse
from common.logger import logger
from common.openai import get_system_prompt, openai
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "projects.json"


async def generate_projects(count: int):
    logger.start(f"Generating {count} projects...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            projects = await _generate_projects(count)
            save_to_json([project.model_dump() for project in projects], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))
            logger.succeed(f"Generated {len(projects)} projects")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info("Retrying...")
            else:
                logger.error(f"Failed to generate projects after {max_retries} attempts: {e}")
                return []


async def _generate_projects(count: int) -> list[Project]:
    """Internal function to generate projects."""
    project_prompt = f"""
        Generate at least {count} realistic projects for a US-based SME using an Odoo Project system.
        
        The projects should be relevant for a company in the '{settings.DATA_THEME_SUBJECT}' industry.
        Each project should have:
        - A realistic project name that reflects business activities
        - A customer/client name (use major US companies like Target, Walmart, Costco, etc.)
        - 2-3 relevant tags from common project categories
        - Realistic start and end dates (within 2025)
        - A detailed description explaining the project scope and objectives
        
        Projects should vary in scope, duration, and complexity to represent a realistic project portfolio.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": project_prompt},
        ],
        text_format=ProjectResponse,
        temperature=0.2,
    )

    projects = response.output_parsed.projects

    if not projects:
        logger.warning("No projects generated. Please generate again.")
        return []

    return projects
