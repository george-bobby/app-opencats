import json
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


class DepartmentList(BaseModel):
    items: list[str] = Field(..., description="List of department names")


async def generate_departments():
    """Generate departments and save to JSON file."""
    default_company = companies.get_default_company()
    logger.info(f"Generating departments for {default_company['name']}")

    # Define the path to the departments JSON file
    departments_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "departments.json")

    # Ensure the directory exists
    departments_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the file exists
    if departments_file_path.exists():
        logger.info("Found existing departments.json file, loading data from it")
        try:
            data = json.loads(departments_file_path.read_text(encoding="utf-8"))
            department_list = data.get("departments", [])
        except Exception as e:
            logger.error(f"Failed to read departments.json: {e!s}")
            logger.info("Falling back to GPT generation")
            department_list = []
    else:
        logger.info("departments.json file not found, generating with GPT")
        department_list = []

    # If no departments loaded from file, generate with GPT
    if not department_list:
        openai = OpenAI()

        response = openai.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates a list of department names.",
                },
                {
                    "role": "user",
                    "content": f"""
                        Generate a list of department names of a {settings.DATA_THEME_SUBJECT}.
                        Don't forget generic departments like "Management", "Sales", "Marketing", etc.
                 """,
                },
            ],
            response_format=DepartmentList,
        )

        department_list = response.choices[0].message.parsed.items

        if department_list:
            # Save the generated departments to the JSON file
            departments_data = {
                "departments": department_list,
                "generated_for": settings.DATA_THEME_SUBJECT,
                "company": default_company["name"],
            }

            try:
                departments_file_path.write_text(json.dumps(departments_data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"Saved {len(department_list)} departments to {departments_file_path}")
            except Exception as e:
                logger.error(f"Failed to save departments to file: {e!s}")

    if not department_list:
        logger.warning("Cannot generate departments")
        return

    return department_list


async def insert_departments():
    """Insert departments from JSON file into the system."""
    client = frappe_client.create_client()
    default_company = companies.get_default_company()

    # Load departments from JSON file
    departments_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "departments.json")

    if not departments_file_path.exists():
        logger.error("departments.json file not found. Please run generate first.")
        return

    try:
        data = json.loads(departments_file_path.read_text(encoding="utf-8"))
        department_list = data.get("departments", [])
    except Exception as e:
        logger.error(f"Failed to read departments.json: {e!s}")
        return

    if not department_list:
        logger.warning("No departments found in JSON file")
        return

    departments = [
        {
            "doctype": "Department",
            "department_name": department,
            "company": default_company["name"],
        }
        for department in department_list
    ]

    for department in departments:
        try:
            logger.info(f"Inserting department: {department['department_name']}")
            client = frappe_client.create_client()
            client.insert(department)
        except Exception as e:
            logger.error(f"Failed to insert department: {e!s}")


async def generate_and_insert_departments():
    """Legacy function that combines generate and insert for backward compatibility."""
    await generate_departments()
    await insert_departments()


def delete_all_departments():
    client = frappe_client.create_client()
    departments = client.get_list("Department")

    if not departments:
        logger.warning("No departments to delete")
        return

    for department in departments:
        logger.info(f"Deleting department: {department['name']}")
        try:
            client = frappe_client.create_client()
            client.delete("Department", department["name"])
        except Exception as e:
            logger.error(f"Failed to delete department: {department['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")
