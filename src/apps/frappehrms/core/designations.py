import json
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


class DesignationList(BaseModel):
    designations: list[str] = Field(..., description="List of designations")


async def generate_designations():
    """Generate designations and save to JSON file."""
    client = frappe_client.create_client()
    default_company = companies.get_default_company()
    logger.info(f"Generating designations for {default_company['name']}")

    # Define the path to the designations JSON file
    designations_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "designations.json")

    # Ensure the directory exists
    designations_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the file exists
    if designations_file_path.exists():
        logger.info("Found existing designations.json file, loading data from it")
        try:
            data = json.loads(designations_file_path.read_text(encoding="utf-8"))
            designation_list = data.get("designations", [])
        except Exception as e:
            logger.error(f"Failed to read designations.json: {e!s}")
            logger.info("Falling back to GPT generation")
            designation_list = []
    else:
        logger.info("designations.json file not found, generating with GPT")
        designation_list = []

    # If no designations loaded from file, generate with GPT
    if not designation_list:
        openai = OpenAI()

        departments = client.get_list("Department")
        departments_str = "\n".join([f"- {d['department_name']}" for d in departments])

        response = openai.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates data for a HR system.",
                },
                {
                    "role": "user",
                    "content": f"""
                        Generate a list of designations for different departments of {settings.DATA_THEME_SUBJECT}.
                        Here's the list of existing departments:
                        {departments_str}
                 """,
                },
            ],
            response_format=DesignationList,
        )

        designation_list = response.choices[0].message.parsed.designations

        if designation_list:
            # Save the generated designations to the JSON file
            designations_data = {
                "designations": designation_list,
                "generated_for": settings.DATA_THEME_SUBJECT,
                "company": default_company["name"],
                "departments_context": departments_str,
            }

            try:
                designations_file_path.write_text(json.dumps(designations_data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"Saved {len(designation_list)} designations to {designations_file_path}")
            except Exception as e:
                logger.error(f"Failed to save designations to file: {e!s}")

    if not designation_list:
        logger.warning("Cannot generate designations")
        return

    return designation_list


async def insert_designations():
    """Insert designations from JSON file into the system."""
    client = frappe_client.create_client()
    default_company = companies.get_default_company()

    # Load designations from JSON file
    designations_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "designations.json")

    if not designations_file_path.exists():
        logger.error("designations.json file not found. Please run generate first.")
        return

    try:
        data = json.loads(designations_file_path.read_text(encoding="utf-8"))
        designation_list = data.get("designations", [])
    except Exception as e:
        logger.error(f"Failed to read designations.json: {e!s}")
        return

    if not designation_list:
        logger.warning("No designations found in JSON file")
        return

    designations = [
        {
            "doctype": "Designation",
            "designation_name": designation,
            "company": default_company["name"],
        }
        for designation in designation_list
    ]

    for designation in designations:
        try:
            logger.info(f"Inserting designation: {designation['designation_name']}")
            client = frappe_client.create_client()
            client.insert(designation)
        except Exception as e:
            logger.error(f"Failed to insert designation: {e!s}")


async def generate_and_insert_designations():
    """Legacy function that combines generate and insert for backward compatibility."""
    await generate_designations()
    await insert_designations()


def delete_all_designations():
    client = frappe_client.create_client()
    designations = client.get_list("Designation")

    if not designations:
        logger.warning("No designations to delete")
        return

    for designation in designations:
        logger.info(f"Deleting designation: {designation['name']}")
        try:
            client = frappe_client.create_client()
            client.delete("Designation", designation["name"])
        except Exception as e:
            logger.error(f"Failed to delete designation: {designation['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")
