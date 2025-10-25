"""Generate calendar events data for OpenCATS using AI."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    DEFAULT_EVENTS_COUNT,
    EVENT_DESCRIPTIONS,
    EVENTS_BATCH_SIZE,
    EVENTS_FILEPATH,
    OpenCATSEventType,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import format_date_for_opencats, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_events():
    """Load existing events to prevent duplicates."""
    existing_data = load_existing_data(EVENTS_FILEPATH)

    used_titles = set()

    for event in existing_data:
        if event.get("title"):
            used_titles.add(event["title"].lower())

    return {
        "used_titles": used_titles,
        "generated_events": existing_data,
    }


def generate_date_range():
    """Generate a date range for events (past 30 days to future 60 days)."""
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=60)

    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime("%m-%d-%y"))
        current_date += timedelta(days=1)

    return dates


def create_events_prompt(used_titles: set, batch_size: int) -> str:
    """Create prompt for event generation."""
    excluded_titles_text = ""
    if used_titles:
        recent_titles = list(used_titles)[-10:]
        excluded_titles_text = f"\n\nDo not use these event titles (already exist): {', '.join(recent_titles)}"

    # Get event types and their descriptions
    event_types_info = []
    for event_type in OpenCATSEventType:
        descriptions = EVENT_DESCRIPTIONS.get(event_type, [])
        sample_descriptions = random.sample(descriptions, min(3, len(descriptions)))
        event_types_info.append(f"{event_type.value}: {event_type.name} (examples: {', '.join(sample_descriptions)})")

    event_types_text = "\n".join(event_types_info)

    # Generate sample dates
    date_range = generate_date_range()
    sample_dates = random.sample(date_range, min(10, len(date_range)))

    prompt = f"""Generate {batch_size} realistic calendar events for {settings.DATA_THEME_SUBJECT}.

Event types and examples:
{event_types_text}

Use these sample dates (MM-DD-YY format): {", ".join(sample_dates)}

Each event should have:
- dateAdd: Event date in MM-DD-YY format from the provided samples
- type: Event type ID (100-600 from the list above)
- duration: Duration in minutes (15, 30, 45, 60, 90, 120)
- allDay: 1 for all-day events (20% chance), 0 for timed events
- hour: Hour (1-12) if not all-day
- minute: Minute (0, 15, 30, 45) if not all-day
- meridiem: "AM" or "PM" if not all-day
- title: Event title relevant to the type and business context
- description: Detailed description of the event (2-3 sentences)
- publicEntry: 1 for public events (60% chance), 0 for private
- reminderToggle: 1 to enable reminder (70% chance), 0 otherwise
- sendEmail: Email address for reminder (use {settings.OPENCATS_ADMIN_EMAIL} if reminder enabled)
- reminderTime: Reminder time in minutes before event (15, 30, 60, 120) if reminder enabled

Return as JSON array.{excluded_titles_text}"""

    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_events_batch(used_titles: set, batch_size: int) -> list[dict[str, Any]]:
    """Generate a batch of events using AI."""
    prompt = create_events_prompt(used_titles, batch_size)

    response = await make_anthropic_request(
        prompt=prompt,
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.DEFAULT_MODEL,
        max_tokens=4000,
        temperature=0.8,
    )

    if not response:
        logger.error("Failed to get response from Anthropic API")
        return []

    events_data = parse_anthropic_response(response)
    if not events_data:
        logger.error("Failed to parse events data from API response")
        return []

    # Validate and clean the data
    validated_events = []
    for event in events_data:
        if validate_event_data(event):
            # Clean and format the data
            cleaned_event = clean_event_data(event)
            validated_events.append(cleaned_event)
        else:
            logger.warning(f"Invalid event data: {event}")

    return validated_events


def validate_event_data(event: dict[str, Any]) -> bool:
    """Validate event data structure."""
    required_fields = ["dateAdd", "type", "title"]

    for field in required_fields:
        if not event.get(field):
            return False

    # Validate event type
    valid_types = [et.value for et in OpenCATSEventType]
    try:
        event_type = int(event.get("type", 0))
        if event_type not in valid_types:
            return False
    except (ValueError, TypeError):
        return False

    return True


def clean_event_data(event: dict[str, Any]) -> dict[str, Any]:
    """Clean and format event data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "dateAdd": format_date_for_opencats(event.get("dateAdd", "")),
        "type": int(event.get("type", 600)),  # Default to "Other"
        "duration": int(event.get("duration", 30)),
        "allDay": 1 if event.get("allDay") else 0,
        "hour": int(event.get("hour", 9)) if not event.get("allDay") else "",
        "minute": int(event.get("minute", 0)) if not event.get("allDay") else "",
        "meridiem": event.get("meridiem", "AM").upper() if not event.get("allDay") else "",
        "title": event.get("title", "").strip(),
        "description": event.get("description", "").strip(),
        "publicEntry": 1 if event.get("publicEntry") else 0,
        "reminderToggle": 1 if event.get("reminderToggle") else 0,
        "sendEmail": event.get("sendEmail", "").strip() if event.get("reminderToggle") else "",
        "reminderTime": int(event.get("reminderTime", 30)) if event.get("reminderToggle") else "",
    }

    return cleaned


async def events(n_events: int | None = None) -> dict[str, Any]:
    """Generate events data."""
    target_count = n_events or DEFAULT_EVENTS_COUNT
    logger.info(f"📅 Starting event generation - Target: {target_count}")

    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    # Load existing data
    existing = load_existing_events()
    used_titles = existing["used_titles"]
    generated_events = existing["generated_events"]

    current_count = len(generated_events)
    remaining_count = max(0, target_count - current_count)

    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} events, no generation needed")
        return {"events": generated_events}

    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")

    # Generate events in batches
    new_events = []
    batches = (remaining_count + EVENTS_BATCH_SIZE - 1) // EVENTS_BATCH_SIZE

    for batch_num in range(batches):
        batch_size = min(EVENTS_BATCH_SIZE, remaining_count - len(new_events))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} events)")

        try:
            batch_events = await generate_events_batch(used_titles, batch_size)

            if batch_events:
                # Update used titles to avoid duplicates
                for event in batch_events:
                    if event.get("title"):
                        used_titles.add(event["title"].lower())

                new_events.extend(batch_events)
                logger.info(f"✅ Generated {len(batch_events)} events in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No events generated in batch {batch_num + 1}")

        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {e!s}")
            continue

        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)

    # Combine with existing data
    all_events = generated_events + new_events

    # Save to file
    if save_to_json(all_events, EVENTS_FILEPATH):
        logger.succeed(f"✅ Event generation completed! Generated {len(new_events)} new events, total: {len(all_events)}")
    else:
        logger.error("❌ Failed to save events data")

    return {"events": all_events}
