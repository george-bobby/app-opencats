import asyncio
import json
from datetime import datetime
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.custom_attributes import CUSTOM_ATTRIBUTE_FILE_PATH
from apps.chatwoot.core.labels import LABELS_FILE_PATH
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


StandardAttributes = Literal[
    "message_type",  # incoming, outgoing
    "content",  # message content for text matching
    "email",  # contact email
    "inbox_id",  # inbox identifier
    "status",  # conversation status: open, resolved, pending
    "assignee_id",  # assigned agent ID
    "team_id",  # assigned team ID
    "priority",  # conversation priority: low, medium, high, urgent
    "conversation_language",  # language code: en, es, fr, de, etc.
    "phone_number",  # contact phone number
]


CustomAttributeType = Literal["", "contact_attribute", "conversation_attribute"]

ValidActionName = Literal[
    "assign_agent",
    "assign_team",
    "add_label",
    "remove_label",
    "send_email_to_team",
    "send_email_transcript",
    "mute_conversation",
    "snooze_conversation",
    "resolve_conversation",
    "open_conversation",
    "send_webhook_event",
]

StandardAttributeKey = Literal[
    "message_type",
    "content",
    "email",
    "inbox_id",
    "status",
    "assignee_id",
    "team_id",
    "priority",
    "conversation_language",
    "phone_number",
]


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
automations_file = settings.DATA_PATH / "generated" / "automations.json"


def load_custom_attributes() -> tuple[list[str], list[str]]:
    """
    Load custom attributes from the JSON file and return lists of contact and conversation attributes.

    Returns:
        tuple: (contact_attributes, conversation_attributes)
    """
    try:
        custom_attributes_file = settings.DATA_PATH / "generated" / "custom_attributes.json"
        with custom_attributes_file.open(encoding="utf-8") as f:
            attributes_data = json.load(f)

        contact_attrs = []
        conversation_attrs = []

        for attr in attributes_data:
            key = attr.get("attribute_key")
            model = attr.get("attribute_model")

            if key:
                if model == 0:  # Contact custom attribute
                    contact_attrs.append(key)
                elif model == 1:  # Conversation custom attribute
                    conversation_attrs.append(key)

        return contact_attrs, conversation_attrs

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Could not load custom attributes: {e}")
        # Return empty lists if file is not available - all attributes will be validated as standard only
        return [], []


def validate_attribute_key(attribute_key: str) -> tuple[bool, str]:
    """
    Validate an attribute key and determine its type.

    Args:
        attribute_key: The attribute key to validate

    Returns:
        tuple: (is_valid, custom_attribute_type)
    """
    # Standard attributes
    standard_attrs = ["message_type", "content", "email", "inbox_id", "status", "assignee_id", "team_id", "priority", "conversation_language", "phone_number"]

    if attribute_key in standard_attrs:
        return True, ""

    # Load dynamic custom attributes from custom_attributes.json
    contact_attrs, conversation_attrs = load_custom_attributes()

    if attribute_key in contact_attrs:
        return True, "contact_attribute"
    elif attribute_key in conversation_attrs:
        return True, "conversation_attribute"
    else:
        return False, ""


def get_all_valid_attributes() -> dict[str, list[str]]:
    """
    Get all valid attribute keys organized by type.

    Returns:
        dict: Dictionary with 'standard', 'contact_custom', and 'conversation_custom' keys
    """
    standard_attrs = ["message_type", "content", "email", "inbox_id", "status", "assignee_id", "team_id", "priority", "conversation_language", "phone_number"]

    # Load dynamic custom attributes from custom_attributes.json
    contact_attrs, conversation_attrs = load_custom_attributes()

    return {
        "standard": standard_attrs,
        "contact_custom": contact_attrs,
        "conversation_custom": conversation_attrs,
    }


class EmailTeamParams(BaseModel):
    team_ids: list[int] = Field(description="List of team IDs to send email to")
    message: str = Field(description="Email message content")


class AutomationCondition(BaseModel):
    attribute_key: str = Field(description="The attribute to check - validated against standard attributes and custom_attributes.json")
    filter_operator: Literal["equal_to", "not_equal_to", "contains", "does_not_contain"] = Field(description="The operator to use for comparison")
    values: list[str] = Field(description="List of values to compare against")
    query_operator: Literal["and", "or"] = Field(description="The logical operator", default="and")
    custom_attribute_type: CustomAttributeType = Field(
        description="Type of custom attribute: '' for standard, 'contact_attribute' for contact, 'conversation_attribute' for conversation", default=""
    )

    def model_post_init(self, __context) -> None:
        """Auto-set custom_attribute_type based on attribute_key if not explicitly set."""
        if self.custom_attribute_type == "":
            is_valid, attribute_type = validate_attribute_key(self.attribute_key)
            if is_valid:
                self.custom_attribute_type = attribute_type
            else:
                raise ValueError(f"Invalid attribute key: '{self.attribute_key}'. Use validate_attribute_key() to check valid attributes.")


class AutomationAction(BaseModel):
    action_name: ValidActionName = Field(description="The action to perform - must be from predefined valid actions")
    action_params: list[str | int | EmailTeamParams] = Field(description="Parameters for the action")


class Automation(BaseModel):
    name: str = Field(description="The name of the automation rule")
    description: str = Field(description="Description of what the automation does")
    event_name: str = Field(description="The event that triggers the automation (e.g., 'message_created')")
    conditions: list[AutomationCondition] = Field(description="List of conditions that must be met")
    actions: list[AutomationAction] = Field(description="List of actions to perform when conditions are met")
    created_at: datetime = Field(description="When the automation was created")
    updated_at: datetime = Field(description="When the automation was last updated")


class AutomationList(BaseModel):
    automations: list[Automation] = Field(description="A list of automation rules")


def _build_automation_prompt(
    number_of_automations: int,
    reference_automations: list,
    available_labels: list,
    contact_custom_attributes: list,
    conversation_custom_attributes: list,
) -> str:
    """Build a clean, readable prompt for automation generation."""

    # Basic introduction
    intro = f"""Generate EXACTLY {number_of_automations} automation rules for a Chatwoot customer support system of {settings.COMPANY_NAME}, a {settings.DATA_THEME_SUBJECT}.

IMPORTANT: You must generate exactly {number_of_automations} automation rules, no more, no less.
"""

    # Reference examples
    examples_section = ""
    if reference_automations:
        examples_section = f"""
Learn from these example automation rules to understand the structure and patterns:
```json
{json.dumps(reference_automations, indent=2)}
```
"""

    # Core documentation
    core_docs = """
Automation rules are triggered by events and execute actions when conditions are met. Here are the key components:

**Event Types:**
- "message_created" - When a new message is created (use this for content-based conditions)
- "conversation_created" - When a new conversation starts (use this for contact/conversation attributes only)
- "conversation_updated" - When conversation details change

**IMPORTANT EVENT-CONDITION COMPATIBILITY:**
- Use "message_created" when checking "content" attribute
- Use "conversation_created" or "conversation_updated" for contact/conversation attributes
- Never use "content" attribute with "conversation_created" event

**Condition Attributes:**
- "message_type" - Values: ["incoming", "outgoing"] (only with message_created)
- "content" - Values: ["bug", "refund", "help", "sales"] (ONLY with message_created event)
- "email" - Values: ["vip@company.com", "support@company.com"] (contact email patterns)
- "inbox_id" - Values: [1, 2, 3, 4, 5] (different inboxes)
- "status" - Values: ["open", "resolved", "pending"]
- "assignee_id" - Values: [1, 2, 3, 4, 5] (different agents)
- "team_id" - Values: [1, 2, 3, 4, 5, 6] (different teams)
- "priority" - Values: ["low", "medium", "high", "urgent"]
- "conversation_language" - Values: ["en", "es", "fr", "de"]
- "phone_number" - Values: ["+1234567890", "+9876543210"] (contact phone patterns)
"""

    # Custom attributes sections
    contact_attrs_section = ""
    if contact_custom_attributes:
        attrs_list = [f'- "{attr["key"]}" - Values: {attr["values"]} (use custom_attribute_type: "contact_attribute")' for attr in contact_custom_attributes]
        contact_attrs_section = f"""
**Contact Custom Attributes:**
{chr(10).join(attrs_list)}
"""

    conversation_attrs_section = ""
    if conversation_custom_attributes:
        attrs_list = [f'- "{attr["key"]}" - Values: {attr["values"]} (use custom_attribute_type: "conversation_attribute")' for attr in conversation_custom_attributes]
        conversation_attrs_section = f"""
**Conversation Custom Attributes:**
{chr(10).join(attrs_list)}
"""

    # Custom attributes formatting section
    custom_attrs_format_section = """
**IMPORTANT - Custom Attribute Formatting:**
When using custom attributes in conditions, use this EXACT format:
- For contact custom attributes:
  ```json
  {
    "attribute_key": "custom_attribute_key_name",
    "filter_operator": "equal_to", 
    "values": ["value1", "value2"],
    "query_operator": "and",
    "custom_attribute_type": "contact_attribute"
  }
  ```
- For conversation custom attributes:
  ```json
  {
    "attribute_key": "custom_attribute_key_name",
    "filter_operator": "equal_to",
    "values": ["value1", "value2"], 
    "query_operator": "and",
    "custom_attribute_type": "conversation_attribute"
  }
  ```

**DO NOT** prefix the attribute_key with "contact_custom_attribute_" or "conversation_custom_attribute_". Use ONLY the key name and set the custom_attribute_type field correctly.
"""

    # Operators and actions
    operators_and_actions = """
**Filter Operators:**
- "equal_to" - Exact match
- "not_equal_to" - Not equal
- "contains" - Contains text
- "does_not_contain" - Does not contain text

**Action Types:**
- "assign_agent" - action_params: [agent_id] (1-20)
- "assign_team" - action_params: [team_id] (1-6)
- "add_label" - action_params: ["label_name"] (from available labels)
- "remove_label" - action_params: ["label_name"] (from available labels)
- "send_email_to_team" - action_params: [EmailTeamParams with team_ids array and message string]
- "send_email_transcript" - action_params: ["email@example.com"]
- "mute_conversation" - action_params: []
- "snooze_conversation" - action_params: [hours]
- "resolve_conversation" - action_params: []
- "open_conversation" - action_params: []
- "send_webhook_event" - action_params: ["https://webhook.url", "event_name"]

**Important for send_email_to_team:**
Use the EmailTeamParams structure: {"team_ids": [1,2,3], "message": "Alert message text"}
"""

    # Available labels
    labels_section = f"""
**IMPORTANT - Available Labels:**
You MUST only use labels from this exact list when using add_label or remove_label actions:
{available_labels}
"""

    # Use cases and requirements
    use_cases_and_requirements = f"""
**Common Automation Use Cases:**
1. **Auto-Assignment**: Route messages to specific teams/agents based on inbox or content
2. **Priority Management**: Set priority based on keywords or customer attributes
3. **Labeling**: Auto-tag conversations based on content or source
4. **Escalation**: Route urgent issues to specialized teams
5. **Customer Journey**: Different actions for new vs returning customers
6. **Language Routing**: Route based on customer language
7. **VIP Treatment**: Special handling based on custom attributes like customer tier
8. **SLA Management**: Actions based on custom attributes like SLA breach status

**Requirements:**
- Use descriptive names that clearly indicate the automation's purpose
- Include meaningful descriptions explaining what the automation does
- Use realistic condition combinations (typically 1-3 conditions)
- Combine multiple actions for comprehensive workflows
- Use realistic agent IDs (1-20) and team IDs (1-6)
- ONLY use labels from the provided available labels list: {available_labels}
- Use custom attributes from the loaded data: contact custom attributes and conversation custom attributes
- Make automation rules specific to {settings.COMPANY_NAME} ({settings.DATA_THEME_SUBJECT}) context when relevant
- Use professional, helpful messages for customer communication
- Ensure conditions and actions work together logically

Focus on creating automation rules that improve response times, routing efficiency, and customer experience while reducing manual work for agents.
"""

    # Combine all sections
    return (
        intro
        + examples_section
        + core_docs
        + contact_attrs_section
        + conversation_attrs_section
        + custom_attrs_format_section
        + operators_and_actions
        + labels_section
        + use_cases_and_requirements
    ).strip()


async def generate_automations(number_of_automations: int):
    """Generate specified number of automation rules using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    automations_file.parent.mkdir(parents=True, exist_ok=True)

    # Load reference automations from automations.json file for examples
    reference_automations_file = settings.DATA_PATH / "automations.json"
    reference_automations = []
    try:
        with reference_automations_file.open(encoding="utf-8") as f:
            reference_automations = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Reference automations file not found: {reference_automations_file}")

    # Load available labels from the generated labels.json file
    labels_file = LABELS_FILE_PATH
    available_labels = []
    try:
        with labels_file.open(encoding="utf-8") as f:
            labels_data = json.load(f)
            available_labels = [label["title"] for label in labels_data]
    except FileNotFoundError:
        logger.warning(f"Labels file not found: {labels_file}")
        logger.warning("Using default labels for automation generation")
        available_labels = ["bug_report", "technical_support", "sales_inquiry", "billing_issue"]

    # Load custom attributes from the generated custom_attributes.json file
    contact_custom_attributes = []
    conversation_custom_attributes = []
    try:
        with CUSTOM_ATTRIBUTE_FILE_PATH.open(encoding="utf-8") as f:
            custom_attrs_data = json.load(f)
            for attr in custom_attrs_data:
                if attr["attribute_model"] == 0:  # Contact custom attributes
                    contact_custom_attributes.append({"key": attr["attribute_key"], "values": attr["attribute_values"] if attr["attribute_values"] else ["sample_value"]})
                elif attr["attribute_model"] == 1:  # Conversation custom attributes
                    conversation_custom_attributes.append({"key": attr["attribute_key"], "values": attr["attribute_values"] if attr["attribute_values"] else ["sample_value"]})
            logger.info(f"Loaded {len(contact_custom_attributes)} contact custom attributes and {len(conversation_custom_attributes)} conversation custom attributes")
    except FileNotFoundError:
        logger.warning(f"Custom attributes file not found: {CUSTOM_ATTRIBUTE_FILE_PATH}")
        logger.warning("Please run generate custom_attributes first to create the custom attributes file")
        # Use empty lists if file not found
        contact_custom_attributes = []
        conversation_custom_attributes = []

    logger.start(f"Generating {number_of_automations} automation rules")

    # Generate automation rules using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            automations_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates realistic automation rule data for Chatwoot. Always generate the EXACT number of automation rules requested."
                        ),
                    },
                    {
                        "role": "user",
                        "content": _build_automation_prompt(
                            number_of_automations,
                            reference_automations,
                            available_labels,
                            contact_custom_attributes,
                            conversation_custom_attributes,
                        ),
                    },
                ],
                response_format=AutomationList,
            )

            automations_data = automations_response.choices[0].message.parsed.automations

            # Validate we got the correct number
            if len(automations_data) >= number_of_automations:
                # Trim to exact number if we got more
                automations_data = automations_data[:number_of_automations]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(automations_data)} automations, need {number_of_automations}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_automations} automations after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate automations after {max_retries} attempts")
                return

    # Add timestamps to each automation
    for automation in automations_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        automation.created_at = created_at
        automation.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_automations = [automation.model_dump(mode="json") for automation in automations_data]

    # Store automations in JSON file
    with automations_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_automations, f, indent=2, default=str)
        logger.succeed(f"Stored {len(automations_data)} automation rules in {automations_file}")


async def seed_automations():
    """Seed automation rules from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        automations = None
        try:
            with automations_file.open(encoding="utf-8") as f:
                automations = [Automation(**automation) for automation in json.load(f)]
                logger.info(f"Loaded {len(automations)} automation rules from {automations_file}")
        except FileNotFoundError:
            logger.error(f"Automations file not found: {automations_file}")
            logger.error("Please run generate_automations() first to create the automations file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {automations_file}")
            return

        if automations is None:
            logger.error("No automation rules loaded from file")
            return

        def transform_custom_attribute_conditions(conditions: list[dict]) -> list[dict]:
            """Transform custom attribute conditions to the correct format for Chatwoot API."""
            transformed_conditions = []
            for condition in conditions:
                transformed_condition = condition.copy()

                # Check if this is a custom attribute with old prefix format
                attribute_key = condition.get("attribute_key", "")

                if attribute_key.startswith("contact_custom_attribute_"):
                    # Remove the prefix and set the custom_attribute_type
                    transformed_condition["attribute_key"] = attribute_key.replace("contact_custom_attribute_", "")
                    transformed_condition["custom_attribute_type"] = "contact_attribute"
                elif attribute_key.startswith("conversation_custom_attribute_"):
                    # Remove the prefix and set the custom_attribute_type
                    transformed_condition["attribute_key"] = attribute_key.replace("conversation_custom_attribute_", "")
                    transformed_condition["custom_attribute_type"] = "conversation_attribute"

                transformed_conditions.append(transformed_condition)

            return transformed_conditions

        # Create async tasks for adding automation rules concurrently
        async def add_single_automation(automation: Automation) -> dict | None:
            """Add a single automation rule and return the automation if successful, None if failed."""
            try:
                # Convert Pydantic model to dict for API call (exclude timestamps)
                automation_config = automation.model_dump(exclude={"created_at", "updated_at"})

                # Transform custom attribute conditions to correct format
                automation_config["conditions"] = transform_custom_attribute_conditions(automation_config["conditions"])

                result = await client.add_automation_rule(
                    name=automation_config["name"],
                    description=automation_config["description"],
                    event_name=automation_config["event_name"],
                    conditions=automation_config["conditions"],
                    actions=automation_config["actions"],
                )

                if result:
                    logger.info(f"Added automation rule: {automation.name}")
                    return automation.model_dump()
                else:
                    logger.error(f"Failed to add automation rule: {automation.name}")
                    return None
            except Exception as e:
                logger.error(f"Error adding automation rule {automation.name}: {e}")
                return None

        # Run all add_automation_rule calls concurrently
        logger.start(f"Adding {len(automations)} automation rules concurrently...")
        results = await asyncio.gather(*[add_single_automation(automation) for automation in automations], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added automations
        added_automations = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_automations)} out of {len(automations)} automation rules")
