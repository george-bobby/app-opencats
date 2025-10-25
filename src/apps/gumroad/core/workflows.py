import asyncio
import json
import random
import uuid
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.gumroad.config.settings import settings
from apps.gumroad.core.settings import get_profile_settings
from apps.gumroad.utils.gumroad import GumroadAPI
from common.logger import logger


openai_client = AsyncOpenAI()

# Cache file path using settings.DATA_PATH
WORKFLOWS_CACHE_FILE = settings.DATA_PATH / "generated" / "workflows.json"


class WorkflowStep(BaseModel):
    delay: int = 0
    action: Literal["send_email", "add_tag"]
    subject: str | None = None
    content: str | None = None
    tag: str | None = None


class Workflow(BaseModel):
    name: str
    workflow_type: Literal["seller", "follower", "audience", "affiliate", "abandoned_cart"]
    workflow_trigger: str | None = None
    bought_products: list[str] = Field(default_factory=list)
    not_bought_products: list[str] = Field(default_factory=list)
    paid_more_than: int | None = None
    paid_less_than: int | None = None
    send_to_past_customers: bool = True
    steps: list[WorkflowStep]


class WorkflowList(BaseModel):
    workflows: list[Workflow]


def _convert_steps_to_installments(steps: list) -> list:
    """
    Convert workflow steps to email installments format

    Args:
        steps: List of workflow steps from JSON

    Returns:
        List of installment dictionaries for add_workflow_email
    """
    installments = []

    for step in steps:
        if step.get("action") == "send_email":
            # Determine time period and duration based on delay
            delay = step.get("delay", 0)
            if delay == 0:
                time_period = "hour"
                time_duration = 1
            elif delay <= 24:
                time_period = "hour"
                time_duration = delay
            else:
                time_period = "day"
                time_duration = delay

            # Create installment using HTML content directly from JSON
            installment = {
                "id": str(uuid.uuid4()),  # Generate unique ID
                "name": step.get("subject", "Email"),
                "message": step.get("content", ""),  # Use HTML content directly from JSON
                "time_period": time_period,
                "time_duration": time_duration,
                "send_preview_email": False,
                "files": [],
            }
            installments.append(installment)

    return installments


async def _generate_single_workflow(workflow_type: str):
    """Internal function to generate a single workflow using OpenAI"""
    profile = await get_profile_settings()

    # Add variety to prevent identical content
    styles = [
        "conversational and friendly",
        "professional and authoritative",
        "enthusiastic and energetic",
        "minimalist and direct",
        "storytelling and narrative",
    ]

    email_formats = [
        "HTML with emojis and clear sections",
        "clean and minimalist design",
        "rich formatting with callouts",
        "personal and engaging style",
        "professional newsletter format",
    ]

    chosen_style = random.choice(styles)
    chosen_format = random.choice(email_formats)

    response = await openai_client.beta.chat.completions.parse(
        model="gpt-4.1-mini-2025-04-14",
        messages=[
            {
                "role": "system",
                "content": f"You are an expert in creating Gumroad email workflows. Write in a {chosen_style} tone using {chosen_format} for the emails.",
            },
            {
                "role": "user",
                "content": f"""
                Create a compelling workflow for a {workflow_type} sequence.
                
                Seller Profile: {profile}
                
                Requirements:
                • Create a workflow with 2-4 email steps
                • Each email should have:
                  - Engaging subject line
                  - Well-formatted HTML content
                  - Strategic delay timing
                • Consider the workflow type context:
                  - seller: post-purchase engagement
                  - follower: welcome and nurture sequence
                  - audience: general audience engagement
                  - affiliate: onboarding and support
                  - abandoned_cart: recovery sequence
                • Include relevant product triggers and conditions
                • Make each workflow unique and specific to its purpose
                
                Be creative with the structure and content!
                """,
            },
        ],
        response_format=Workflow,
    )
    return response.choices[0].message.parsed


async def generate_workflows(number_of_workflows: int) -> dict:
    """
    Generate workflow data and save to JSON file in settings.DATA_PATH

    Args:
        number_of_workflows: Number of workflows to generate
    """
    logger.info(f"Generating {number_of_workflows} workflows...")

    # Distribute workflows across different types
    workflow_types = ["seller", "follower", "audience", "affiliate", "abandoned_cart"]
    workflow_distribution = []

    for i in range(number_of_workflows):
        workflow_type = workflow_types[i % len(workflow_types)]
        workflow_distribution.append(workflow_type)

    # Generate workflows concurrently
    workflow_tasks = [_generate_single_workflow(wtype) for wtype in workflow_distribution]
    workflows = await asyncio.gather(*workflow_tasks, return_exceptions=True)

    # Process results and handle any exceptions
    workflows_data = []
    for i, workflow in enumerate(workflows):
        if isinstance(workflow, Exception):
            logger.error(f"Error generating workflow for type '{workflow_distribution[i]}': {workflow}")
            continue
        if isinstance(workflow, Workflow):
            workflows_data.append(workflow.model_dump())
        else:
            logger.error(f"Unexpected workflow type for '{workflow_distribution[i]}': {type(workflow)}")
            continue

    # Prepare the final data structure
    output_data = {
        "workflows": workflows_data,
        "count": len(workflows_data),
    }

    # Ensure the data directory exists
    WORKFLOWS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    with WORKFLOWS_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully generated and saved {len(workflows_data)} workflows to {WORKFLOWS_CACHE_FILE}")
    return output_data


async def seed_workflows():
    """
    Load workflows from generated JSON file and insert them into Gumroad
    """
    logger.start("Seeding workflows...")
    async with GumroadAPI() as gumroad:
        # Load workflow configurations from generated JSON file
        if not WORKFLOWS_CACHE_FILE.exists():
            logger.error(f"Workflows file not found: {WORKFLOWS_CACHE_FILE}")
            logger.error("Please run generate_workflows() first to create the workflows file")
            return

        with WORKFLOWS_CACHE_FILE.open() as f:
            data = json.load(f)
            workflows = data.get("workflows", [])

        if not workflows:
            logger.error("No workflows found in the JSON file")
            return

        logger.info(f"Found {len(workflows)} workflows to create")

        for workflow in workflows:
            workflow_id = None
            try:
                # Extract steps for email processing
                steps = workflow.pop("steps", [])

                # Filter out unsupported parameters for workflow creation
                supported_params = {
                    "name",
                    "workflow_type",
                    "workflow_trigger",
                    "bought_products",
                    "bought_variants",
                    "variant_external_id",
                    "permalink",
                    "not_bought_products",
                    "not_bought_variants",
                    "paid_more_than",
                    "paid_less_than",
                    "created_after",
                    "created_before",
                    "bought_from",
                    "affiliate_products",
                    "send_to_past_customers",
                    "save_action_name",
                    "link_id",
                }
                filtered_workflow = {k: v for k, v in workflow.items() if k in supported_params}

                # Create the workflow first
                result = await gumroad.add_workflow(**filtered_workflow)

                if result.get("status_code") in [200, 201]:
                    logger.info(f"Successfully created workflow: '{workflow.get('name')}'")
                    logger.info(f"  - Type: {workflow.get('workflow_type')}")
                    logger.info(f"  - Trigger: {workflow.get('workflow_trigger')}")
                    logger.info(f"  - Steps planned: {len(steps)}")

                    # Check if we have email steps to add
                    email_steps = [step for step in steps if step.get("action") == "send_email"]
                    if email_steps:
                        logger.info(f"  - Email steps found: {len(email_steps)}")

                        # Extract workflow ID from response
                        if "workflow_id" in result:
                            workflow_id = result["workflow_id"]
                        elif "redirect_to" in result:
                            import re

                            match = re.search(r"/workflows/([^/]+)", result["redirect_to"])
                            if match:
                                workflow_id = match.group(1)
                        elif "workflow" in result and isinstance(result["workflow"], dict):
                            workflow_id = result["workflow"].get("id")
                        elif "id" in result:
                            workflow_id = result["id"]

                        if workflow_id:
                            logger.info(f"  - Extracted workflow ID: {workflow_id}")

                            # Convert steps to installments format
                            installments = _convert_steps_to_installments(email_steps)

                            if installments:
                                # Add emails to the workflow
                                email_result = await gumroad.add_workflow_email(
                                    workflow_id=workflow_id,
                                    installments=installments,
                                    send_to_past_customers=workflow.get("send_to_past_customers", True),
                                )

                                if email_result.get("status_code") in [200, 201]:
                                    logger.info(f"  ✅ Successfully added {len(installments)} emails to workflow")
                                    for i, installment in enumerate(installments, 1):
                                        logger.info(
                                            f"    📧 Email {i}: '{installment['name']}' "
                                            f"(after {installment['time_duration']} {installment['time_period']}"
                                            f"{'s' if installment['time_duration'] > 1 else ''})"
                                        )
                                else:
                                    logger.error(f"  ❌ Failed to add emails to workflow: {email_result}")
                        else:
                            logger.warning("  ⚠️ Could not extract workflow ID from response, emails not added")
                            logger.warning(f"     Response keys: {list(result.keys())}")
                    else:
                        logger.info("  - No email steps found in workflow")

                    # Only publish workflow if we have a valid workflow_id
                    if workflow_id:
                        await gumroad.publish_workflow(
                            workflow_id,
                            {
                                "name": workflow.get("name"),
                                "workflow_type": workflow.get("workflow_type"),
                                "workflow_trigger": workflow.get("workflow_trigger"),
                            },
                        )
                        logger.info(f"  ✅ Successfully published workflow: '{workflow.get('name')}'")
                    else:
                        logger.warning(f"  ⚠️ Cannot publish workflow '{workflow.get('name')}' - no workflow ID available")

                else:
                    logger.error(f"Failed to create workflow '{workflow.get('name')}': {result}")

            except Exception as e:
                logger.error(f"Error creating workflow '{workflow.get('name', 'Unknown')}': {e!s}")

    logger.succeed("Workflows seeded successfully")


# Legacy function for backward compatibility
async def add_workflows(number_of_workflows: int):
    """
    Legacy function - use generate_workflows() and seed_workflows() instead
    """
    logger.warning("add_workflows() is deprecated. Use generate_workflows() and seed_workflows() instead.")

    # Generate workflows
    await generate_workflows(number_of_workflows)

    # Seed workflows
    await seed_workflows()
