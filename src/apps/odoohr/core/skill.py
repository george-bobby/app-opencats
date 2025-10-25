"""Manages employee skills, types, and proficiency levels."""

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


levels = [
    {
        "name": "Beginner",
        "level_progress": 40,
    },
    {
        "name": "Intermediate",
        "level_progress": 60,
    },
    {
        "name": "Advanced",
        "level_progress": 80,
    },
    {
        "name": "Expert",
        "level_progress": 100,
    },
]


async def get_skills_by_type(skill_type: str):
    """
    Get skill by type from Odoo.
    """

    async with OdooClient() as client:
        skill_types = await client.search_read(HRModelName.HR_SKILL_TYPE.value, [("name", "=", skill_type)], ["id"])

        skill_ids = await client.search_read(
            HRModelName.HR_SKILL.value,
            [("skill_type_id", "=", skill_types[0]["id"])],
            ["id", "skill_type_id"],
        )

    return skill_ids


async def get_skills():
    """
    Get all skills from Odoo.
    """
    async with OdooClient() as client:
        skills = await client.search_read(HRModelName.HR_SKILL.value, [], ["id", "name", "skill_type_id"])
        return skills


async def insert_skills():
    await delete_default_skills()

    skills_config = load_json(settings.DATA_PATH.joinpath("skills.json"))

    if not skills_config:
        raise ValueError("No users found in the JSON file.")

    skill_types = skills_config.get("types", [])
    languages = skills_config.get("languages", [])
    hard_skills = skills_config.get("hardSkills", [])
    soft_skills = skills_config.get("softSkills", [])

    logger.start("Inserting skills")
    await insert_skill_types(skill_types)
    await insert_skills_by_type("Languages", languages)
    await insert_skills_by_type("Hard Skills", hard_skills)
    await insert_skills_by_type("Soft Skills", soft_skills)
    await insert_skills_level()

    logger.succeed(f"Inserted {len(hard_skills + soft_skills)} skills")


async def insert_skill_types(skill_types: list[str]):
    """
    Insert skill types into Odoo.
    """

    async with OdooClient() as client:
        # existing_skill_types = await client.search_read(HRModelName.HR_SKILL_TYPE.value, [("name", "in", skill_types)], ["id"])
        # if existing_skill_types:
        #     await client.unlink(HRModelName.HR_SKILL_TYPE.value, [s["id"] for s in existing_skill_types])
        data = []
        for skill_type in skill_types:
            data.append({"name": skill_type})

        return await client.create(HRModelName.HR_SKILL_TYPE.value, [data])


async def insert_skills_by_type(skill_type: str, skills: list[str]):
    async with OdooClient() as client:
        skill_types = await client.search_read(HRModelName.HR_SKILL_TYPE.value, [("name", "=", skill_type)], ["id"])
        data = []
        for skill in skills:
            data.append({"name": skill, "skill_type_id": skill_types[0]["id"]})

        await client.create(HRModelName.HR_SKILL.value, [data])


async def insert_skills_level():
    """
    Insert skill levels into Odoo.
    """
    async with OdooClient() as client:
        skill_types = await client.search_read(HRModelName.HR_SKILL_TYPE.value, [], ["id", "name"])
        data = []

        for skill_type in skill_types:
            for level in levels:
                data.append({"skill_type_id": skill_type["id"], "name": level["name"], "level_progress": level["level_progress"]})

        await client.create(HRModelName.HR_SKILL_LEVEL.value, [data])


async def delete_default_skills():
    """
    Delete default skills from Odoo.
    """
    async with OdooClient() as client:
        skills = await client.search_read(HRModelName.HR_SKILL.value, [], ["id", "name"])
        if skills:
            await client.unlink(HRModelName.HR_SKILL.value, [s["id"] for s in skills])
