"""Seed calendar events data into OpenCATS."""

import asyncio
from typing import Any, Dict, List

from apps.opencats.config.constants import EVENTS_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


async def seed_events() -> Dict[str, Any]:
    """Seed calendar events data into OpenCATS."""
    logger.info("📅 Starting event seeding...")
    
    # Load generated events data
    events_data = load_existing_data(EVENTS_FILEPATH)
    
    if not events_data:
        logger.warning("⚠️ No events data found. Run generation first.")
        return {"seeded_events": 0, "errors": 0}
    
    logger.info(f"📊 Found {len(events_data)} events to seed")
    
    seeded_count = 0
    error_count = 0
    seeded_events = []
    
    async with OpenCATSAPIUtils() as api:
        for idx, event in enumerate(events_data):
            event_title = event.get("title", "Unknown")
            logger.info(f"🔄 Seeding event {idx + 1}/{len(events_data)}: {event_title}")
            
            try:
                # Prepare form data for OpenCATS
                form_data = prepare_event_form_data(event)
                
                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.CALENDAR_ADD.value, form_data)
                
                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Event '{event_title}' seeded successfully (ID: {entity_id})")
                        seeded_events.append({
                            "original_data": event,
                            "opencats_id": entity_id,
                            "status": "success"
                        })
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Event '{event_title}' may have been created but ID not found")
                        seeded_events.append({
                            "original_data": event,
                            "opencats_id": None,
                            "status": "unknown"
                        })
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed event '{event_title}': {result}")
                    seeded_events.append({
                        "original_data": event,
                        "opencats_id": None,
                        "status": "failed",
                        "error": str(result)
                    })
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error seeding event '{event_title}': {str(e)}")
                seeded_events.append({
                    "original_data": event,
                    "opencats_id": None,
                    "status": "error",
                    "error": str(e)
                })
                error_count += 1
            
            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)
    
    logger.succeed(f"✅ Event seeding completed! Seeded: {seeded_count}, Errors: {error_count}")
    
    return {
        "seeded_events": seeded_count,
        "errors": error_count,
        "details": seeded_events
    }


def prepare_event_form_data(event: Dict[str, Any]) -> Dict[str, str]:
    """Prepare event data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "dateAdd": event.get("dateAdd", ""),
        "type": str(event.get("type", "")),
        "title": event.get("title", ""),
        "description": event.get("description", ""),
        "duration": str(event.get("duration", "30")),
    }
    
    # Handle all-day events
    if event.get("allDay"):
        form_data["allDay"] = "1"
    else:
        # Add time fields for timed events
        form_data["hour"] = str(event.get("hour", ""))
        form_data["minute"] = str(event.get("minute", ""))
        form_data["meridiem"] = event.get("meridiem", "")
    
    # Handle checkboxes
    if event.get("publicEntry"):
        form_data["publicEntry"] = "1"
    
    if event.get("reminderToggle"):
        form_data["reminderToggle"] = "1"
        form_data["sendEmail"] = event.get("sendEmail", "")
        form_data["reminderTime"] = str(event.get("reminderTime", ""))
    
    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}
    
    return form_data
