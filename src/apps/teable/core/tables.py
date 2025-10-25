import asyncio
import copy
import json
import random
import re
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI

from apps.teable.config.constants import TABLES_FILE
from apps.teable.config.settings import settings
from apps.teable.core.bases import get_base_id_by_name
from apps.teable.utils.faker import faker
from apps.teable.utils.teable import close_global_client, get_teable_client
from common.logger import Logger


logger = Logger()
openai_client = AsyncOpenAI()

# Store table name to ID mapping for resolving foreign table references
table_name_to_id_map = {}


def weighted_random_selection(elements, weights, num_selections, unique=True):
    """
    Custom weighted random selection function.

    Args:
        elements: List of elements to choose from
        weights: List of weights corresponding to each element
        num_selections: Number of elements to select
        unique: If True, each element can only be selected once

    Returns:
        List of selected elements
    """
    if not elements or not weights or len(elements) != len(weights):
        return []

    if num_selections <= 0:
        return []

    # Create a list of (element, weight) pairs
    weighted_elements = list(zip(elements, weights, strict=False))
    selected = []

    for _ in range(min(num_selections, len(elements) if unique else num_selections)):
        if not weighted_elements:
            break

        # Calculate total weight
        total_weight = sum(weight for _, weight in weighted_elements)
        if total_weight <= 0:
            break

        # Generate random number between 0 and total_weight
        rand_num = random.uniform(0, total_weight)

        # Select element based on cumulative weights
        cumulative_weight = 0
        selected_element = None
        selected_index = -1

        for i, (element, weight) in enumerate(weighted_elements):
            cumulative_weight += weight
            if rand_num <= cumulative_weight:
                selected_element = element
                selected_index = i
                break

        if selected_element is not None:
            selected.append(selected_element)
            if unique:
                # Remove selected element from the pool
                weighted_elements.pop(selected_index)

    return selected


def get_data_filename(name: str, parent_base_name: str) -> str:
    """Clean a string to be used as a filename by removing special characters and combining name and parent_base_name"""

    def clean(s):
        cleaned = re.sub(r"[^\w\s-]", "", s.strip())
        cleaned = re.sub(r"[-\s]+", "_", cleaned)
        return cleaned.lower()

    return f"{clean(name)}_{clean(parent_base_name)}"


def load_table_records(table_name: str, parent_base_name: str) -> list:
    """Load generated records for a table from the data files"""
    table_filename = get_data_filename(table_name, parent_base_name) + ".json"
    table_data_path = settings.DATA_PATH.joinpath("generated/tables", table_filename)

    if not table_data_path.exists():
        logger.info(f"No generated data file found for table '{table_name}'")
        return []

    try:
        with Path.open(table_data_path, encoding="utf-8") as f:
            table_data = json.load(f)
            records = table_data.get("records", [])
        logger.info(f"Loaded {len(records)} records for table '{table_name}'")
        return records
    except Exception as e:
        logger.error(f"Failed to load data for table '{table_name}': {e}")
        return []


async def create_table_with_first_field(teable, table: dict, base_id: str) -> object:
    """Create a single table without any fields and return the created table object"""
    try:
        # Create table with just the name and no fields or records
        created_table = await teable.create_table(
            base_id,
            table["name"],
            [table["fields"][0]],
            [],  # Empty fields and records
        )
        logger.succeed(f"Created empty table '{table['name']}'")

        table_id = created_table["id"]
        records = await teable.get_records(table_id)
        if records.get("records", []):
            await teable.delete_record(table_id, [record["id"] for record in records.get("records", [])])

    except Exception as e:
        logger.error(f"Failed to create table '{table['name']}': {e}")
        raise e

    return created_table


async def create_all_tables_with_first_field():
    teable = await get_teable_client()
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    """Create all tables without any fields first"""
    for table in tables:
        base_id = await get_base_id_by_name(table["parent_workspace_name"], table["parent_base_name"])

        if not base_id:
            logger.error(f"Base with name {table['parent_base_name']} not found")
            continue

        await create_table_with_first_field(teable, table, base_id)


async def insert_tables():
    """
    Insert all tables into Teable by first creating all tables without fields
    """
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    # Create all tables without fields first
    logger.info(f"Creating {len(tables)} tables without fields")
    await create_all_tables_with_first_field()

    logger.info(f"Adding fields to {len(tables)} tables")
    await add_remaining_fields_to_tables()

    logger.info(f"Adding records to {len(tables)} tables...")
    await add_records_to_tables()

    logger.info(f"Linking records in {len(tables)} tables")
    await link_records_in_tables()


async def link_records_in_tables():
    teable = await get_teable_client()
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    for tbl in tables:
        current_table = await get_table_id_by_name(tbl["parent_workspace_name"], tbl["parent_base_name"], tbl["name"])
        current_table_id = current_table["id"]

        for tbl_field in tbl["fields"]:
            if tbl_field.get("type") == "link":
                field_name = tbl_field["name"]
                relationship = tbl_field["options"]["relationship"]
                foreign_table_name = tbl_field["options"].get("foreignTableName")
                current_table_records = await teable.get_records(
                    current_table_id,
                    filter=json.dumps(
                        {
                            "filterSet": [
                                {
                                    "fieldId": field_name,
                                    "operator": "isEmpty",
                                    "value": None,
                                }
                            ],
                            "conjunction": "and",
                        }
                    ),
                )

                if not foreign_table_name:
                    logger.warning(f"Foreign table name not found for {tbl_field['name']}")
                    continue

                foreign_table = await get_table_id_by_name(
                    tbl["parent_workspace_name"],
                    tbl["parent_base_name"],
                    foreign_table_name,
                )
                foreign_table_id = foreign_table["id"]
                foreign_table_records = await teable.get_records(foreign_table_id)

                if relationship == "manyMany":
                    selectable_foreign_records = copy.deepcopy(foreign_table_records.get("records", []))

                    # Track selection counts for weighted selection
                    selection_counts = {record["id"]: 0 for record in selectable_foreign_records}

                    for record in current_table_records.get("records", []):
                        record_id = record["id"]

                        # Calculate weights (higher count = lower weight)
                        weights = []
                        for foreign_record in selectable_foreign_records:
                            count = selection_counts[foreign_record["id"]]
                            # Weight decreases as count increases (using exponential decay)
                            weight = max(0.1, 1.0 / (1 + count * 0.5))  # Minimum weight of 0.1
                            weights.append(weight)

                        # Perform weighted random selection
                        num_selections = faker.random_int(min=1, max=2)
                        selected_foreign_records = weighted_random_selection(
                            selectable_foreign_records,
                            weights,
                            num_selections,
                            True,
                        )

                        # Update selection counts and log selection statistics
                        for selected_record in selected_foreign_records:
                            selection_counts[selected_record["id"]] += 1

                        selected_foreign_records = [
                            {
                                "id": record.get("id"),
                                "title": record.get("name", record.get("title", "")),
                            }
                            for record in selected_foreign_records
                        ]
                        await teable.update_record(
                            current_table_id,
                            record_id,
                            {"fields": {field_name: selected_foreign_records}},
                        )

                if relationship == "manyOne":
                    remaining_foreign_records = copy.deepcopy(foreign_table_records.get("records", []))

                    for record in current_table_records.get("records", []):
                        record_id = record["id"]

                        # Check if we've run out of foreign records
                        if len(remaining_foreign_records) == 0:
                            remaining_foreign_records = copy.deepcopy(foreign_table_records.get("records", []))
                            if len(remaining_foreign_records) == 0:
                                logger.info(f"No more foreign records available for {field_name} in table {tbl['name']}, skipping...")
                                break

                        selected_foreign_record = faker.random_element(elements=remaining_foreign_records)
                        # Remove the selected record from remaining_foreign_records
                        remaining_foreign_records.remove(selected_foreign_record)
                        await teable.update_record(
                            current_table_id,
                            record_id,
                            {"fields": {field_name: selected_foreign_record}},
                        )

                logger.succeed(f"Linked {len(current_table_records.get('records', []))} records with {field_name} in table {tbl['name']}")


async def add_records_to_tables():
    teable = await get_teable_client()
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    for tbl in tables:
        current_table = await get_table_id_by_name(tbl["parent_workspace_name"], tbl["parent_base_name"], tbl["name"])
        current_table_id = current_table["id"]
        if not current_table_id:
            continue

        records = load_table_records(tbl["name"], tbl["parent_base_name"])
        await teable.create_record(current_table_id, records)


async def add_remaining_fields_to_tables():
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    teable = await get_teable_client()
    for tbl in tables:
        current_table = await get_table_id_by_name(tbl["parent_workspace_name"], tbl["parent_base_name"], tbl["name"])
        for index, field in enumerate(tbl["fields"]):
            if index == 0:
                continue

            if field.get("type") == "link":
                foreign_table_name = field["options"]["foreignTableName"]
                relationship = field["options"]["relationship"]
                is_one_way = field["options"].get("isOneWay", True)
                foreign_table = await get_table_id_by_name(
                    tbl["parent_workspace_name"],
                    tbl["parent_base_name"],
                    foreign_table_name,
                )

                foreign_table_id = foreign_table["id"]
                field["options"] = {
                    "foreignTableId": foreign_table_id,
                    "relationship": relationship,
                    "isOneWay": is_one_way,
                }

            await teable.add_field(
                current_table["id"],
                name=field["name"],
                field_type=field["type"],
                options=field.get("options", {}),
                unique=field.get("unique", False),
                not_null=field.get("notNull", False),
                description=field.get("description", ""),
                lookup_options=field.get("lookupOptions", {}),
                ai_config=field.get("aiConfig", {}),
            )

        logger.succeed(f"Added {len(tbl['fields'])} fields to {tbl['name']}")


async def get_table_id_by_name(workspace_name: str, base_name: str, table_name: str):
    teable = await get_teable_client()
    base_id = await get_base_id_by_name(workspace_name, base_name)
    tables = await teable.get_tables(base_id)
    for table in tables:
        if table["name"] == table_name:
            return table


async def get_context_tables_data(table: dict):
    context_tables_data = {}
    teable = await get_teable_client()
    parent_workspace_name = table.get("parent_workspace_name")
    parent_base_name = table.get("parent_base_name")
    base_id = await get_base_id_by_name(parent_workspace_name, parent_base_name)
    tables_response = await teable.get_tables(base_id)

    for tbl in tables_response:
        if tbl.get("name") in table.get("context_tables", []):
            records = await teable.get_records(tbl.get("id"))
            records = [{k: v for k, v in record.items() if isinstance(v, str) and k not in ["id", "createdBy"]} for record in records.get("records", [])]
            context_tables_data[tbl.get("name")] = records
    return context_tables_data


async def generate_table_data(table: dict):
    context_tables_data = await get_context_tables_data(table)
    table_data = {
        "table_name": table["name"],
        "parent_workspace_name": table["parent_workspace_name"],
        "parent_base_name": table["parent_base_name"],
        "records": [],
    }

    """Generate realistic data for a table using OpenAI JSON mode"""

    prompt = f"""Generate {table["row_count"]} rows of realistic data for a table called "{table["name"]}".

    Table fields:
    {json.dumps(table["fields"])}

    Generate diverse, realistic data that makes sense for each field type.
    Ensure data variety and realism.
    For your information, the company is {settings.DATA_THEME_SUBJECT}, admin email is {settings.TEABLE_ADMIN_EMAIL}.

    Return the data as a JSON object with a "rows" array, where each row is an object with field names as keys.
    Note:
      - If the field type is "singleSelect", the value should be one of the provided options as string.
      - If the field type is "multiSelect", the value should be an array of strings, each being one of the provided options.
      - If the field type is "link", skip generating data for that field, don't include it in the data.
      - If a field has offline: true, skip generating data for that field, don't include it in the data.
      - If a field has prompt, follow the prompt to generate data for that field.

    Today's date is {datetime.now().strftime("%Y-%m-%d")}.
    Generate data relative to today.
    """

    if context_tables_data:
        prompt += f"""
        Here're some other tables that are related to the table you are generating data for:
        {json.dumps(context_tables_data)}
        """

    logger.info(f"Generating data for table '{table['name']} {'with context tables' if context_tables_data else ''}'")

    # Generate data with retry logic to ensure we get enough rows
    all_generated_rows = []
    max_attempts = 5
    attempt = 1

    while len(all_generated_rows) < table["row_count"] and attempt <= max_attempts:
        remaining_rows = table["row_count"] - len(all_generated_rows)
        current_prompt = prompt.replace(f"Generate {table['row_count']} rows", f"Generate {remaining_rows} rows")

        logger.info(f"Attempt {attempt}: Generating {remaining_rows} rows for table '{table['name']}'")

        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Teable data generation assistant.
                    Generate realistic, diverse data that matches the given schema exactly.
                    You should generate minified JSON data.
                    """,
                },
                {"role": "user", "content": current_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,  # Add some variety to the generated data
        )

        generated_data = json.loads(response.choices[0].message.content)
        generated_rows = generated_data.get("rows", [])

        logger.info(f"Attempt {attempt}: Generated {len(generated_rows)} rows")

        # Add the new rows to our collection
        all_generated_rows.extend(generated_rows)
        attempt += 1

    # Trim to exact count if we have too many rows
    if len(all_generated_rows) > table["row_count"]:
        all_generated_rows = all_generated_rows[: table["row_count"]]

    logger.info(f"Final result: Generated {len(all_generated_rows)} rows for table '{table['name']}' (required: {table['row_count']})")

    table_data["records"] = [{"fields": row} for row in all_generated_rows]

    try:
        # Prepare the data structure for saving

        # Create filename from table name and parent_base_name
        filename = get_data_filename(table["name"], table["parent_base_name"]) + ".json"

        # Ensure the directory exists
        output_dir = settings.DATA_PATH.joinpath("generated/tables")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save to file
        output_path = output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(table_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved generated data for '{table['name']}' to {output_path}")
        return table_data

    except Exception as e:
        logger.error(f"Error generating data for table '{table['name']}': {e!s}")
        return None


async def generate_tables(skip_existing: bool = True):
    with Path.open(settings.DATA_PATH.joinpath(TABLES_FILE)) as f:
        tables = json.load(f)

    # Create semaphore to limit concurrent tasks (prevent overwhelming the server)
    semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent table generations

    async def generate_with_semaphore(table):
        async with semaphore:
            return await generate_table_data(table)

    # Create tasks for concurrent processing
    tasks = []
    for table in tables:
        logger.info(f"Table: {table['name']}")
        logger.info(f"Parent workspace: {table['parent_workspace_name']}")
        logger.info(f"Parent base: {table['parent_base_name']}")
        logger.info(f"Row count: {table['row_count']}")

        # Check if data file already exists
        if skip_existing:
            table_name = table["name"]
            parent_base_name = table["parent_base_name"]
            table_filename = get_data_filename(table_name, parent_base_name) + ".json"
            table_data_path = settings.DATA_PATH.joinpath("generated/tables", table_filename)

            if table_data_path.exists():
                logger.info(f"Data file already exists for table '{table_name}', skipping generation")
                continue

        # Create task for generating data for this table with semaphore
        task = asyncio.create_task(generate_with_semaphore(table))
        tasks.append((task, table))

        # break  # Remove this break to process all tables

    # Wait for all tasks to complete
    logger.info(f"Starting concurrent generation of {len(tasks)} tables...")

    for task, table in tasks:
        try:
            generated_data = await task
            if generated_data:
                logger.succeed(f"Successfully generated data for '{table['name']}'")
                # Log a sample of the generated data
                sample_rows = generated_data.get("records", [])[:3]  # Show first 3 rows
                for i, row in enumerate(sample_rows, 1):
                    logger.info(f"Sample row {i}: {row}")
            else:
                logger.fail(f"Failed to generate data for '{table['name']}'")
        except Exception as e:
            logger.fail(f"Error processing table '{table['name']}': {e!s}")


async def cleanup_teable_client():
    """Clean up the global teable client when shutting down"""

    await close_global_client()
    logger.info("Teable client cleaned up")


async def get_all_tables():
    teable = await get_teable_client()
    workspaces = await teable.get_spaces()
    tables = []
    for workspace in workspaces:
        bases = await teable.get_bases(workspace["id"])
        for base in bases:
            tables = await teable.get_tables(base["id"])
            for table in tables:
                tables.append(table)
        return tables
