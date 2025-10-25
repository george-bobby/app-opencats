"""Generate candidates data for OpenCATS using AI."""

import asyncio
import random
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    CANDIDATES_BATCH_SIZE,
    CANDIDATES_FILEPATH,
    DEFAULT_CANDIDATES_COUNT,
    TECH_SKILLS,
    JOB_TITLES,
    MAJOR_CITIES,
    US_STATES,
    OpenCATSEEOEthnicType,
    OpenCATSEEOVeteranType,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import load_existing_data, format_phone_number, format_date_for_opencats
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_candidates():
    """Load existing candidates to prevent duplicates."""
    existing_data = load_existing_data(CANDIDATES_FILEPATH)
    
    used_emails = set()
    used_names = set()
    
    for candidate in existing_data:
        if candidate.get("email1"):
            used_emails.add(candidate["email1"].lower())
        if candidate.get("firstName") and candidate.get("lastName"):
            full_name = f"{candidate['firstName']} {candidate['lastName']}".lower()
            used_names.add(full_name)
    
    return {
        "used_emails": used_emails,
        "used_names": used_names,
        "generated_candidates": existing_data,
    }


def create_candidates_prompt(used_emails: set, used_names: set, batch_size: int) -> str:
    """Create prompt for candidate generation."""
    excluded_emails_text = ""
    if used_emails:
        recent_emails = list(used_emails)[-10:]
        excluded_emails_text = f"\n\nDo not use these email addresses (already exist): {', '.join(recent_emails)}"
    
    excluded_names_text = ""
    if used_names:
        recent_names = list(used_names)[-10:]
        excluded_names_text = f"\n\nDo not use these names (already exist): {', '.join(recent_names)}"
    
    skills_list = ", ".join(random.sample(TECH_SKILLS, min(20, len(TECH_SKILLS))))
    cities_list = ", ".join(random.sample(MAJOR_CITIES, min(15, len(MAJOR_CITIES))))
    
    prompt = f"""Generate {batch_size} realistic job candidates for {settings.DATA_THEME_SUBJECT}.

Use these technical skills: {skills_list}
Use these cities: {cities_list}

Each candidate should have:
- firstName: First name
- middleName: Middle name (optional, 30% chance)
- lastName: Last name
- email1: Primary email address
- email2: Secondary email (optional, 25% chance)
- phoneHome: Home phone number (optional, 60% chance)
- phoneCell: Cell phone number in format (XXX) XXX-XXXX
- phoneWork: Work phone number (optional, 40% chance)
- address: Home address
- city: City name from the provided list
- state: 2-letter US state code
- zip: 5-digit ZIP code
- source: How they were found (e.g., "LinkedIn", "Referral", "Job Board", "Company Website")
- keySkills: 3-6 relevant technical skills from the list, comma-separated
- dateAvailable: Available start date in MM-DD-YY format (optional, 70% chance)
- currentEmployer: Current company name (optional, 80% chance)
- canRelocate: 1 if willing to relocate (40% chance), 0 otherwise
- currentPay: Current salary as number (optional, 60% chance)
- desiredPay: Desired salary as number (optional, 80% chance)
- notes: Brief professional summary (2-3 sentences)
- webSite: Personal website or portfolio URL (optional, 30% chance)
- bestTimeToCall: Preferred contact time (optional, 50% chance)
- gender: "M", "F", or "" (optional, 70% chance)
- race: EEO ethnic type ID (1-5, optional, 60% chance)
- veteran: EEO veteran type ID (1-4, optional, 20% chance)
- disability: Disability status ("Y", "N", or "", optional, 10% chance)
- textResumeBlock: Brief resume text (optional, 40% chance)
- textResumeFilename: Resume filename if textResumeBlock provided

Return as JSON array.{excluded_emails_text}{excluded_names_text}"""
    
    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_candidates_batch(used_emails: set, used_names: set, batch_size: int) -> List[Dict[str, Any]]:
    """Generate a batch of candidates using AI."""
    prompt = create_candidates_prompt(used_emails, used_names, batch_size)
    
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
    
    candidates_data = parse_anthropic_response(response)
    if not candidates_data:
        logger.error("Failed to parse candidates data from API response")
        return []
    
    # Validate and clean the data
    validated_candidates = []
    for candidate in candidates_data:
        if validate_candidate_data(candidate):
            # Clean and format the data
            cleaned_candidate = clean_candidate_data(candidate)
            validated_candidates.append(cleaned_candidate)
        else:
            logger.warning(f"Invalid candidate data: {candidate}")
    
    return validated_candidates


def validate_candidate_data(candidate: Dict[str, Any]) -> bool:
    """Validate candidate data structure."""
    required_fields = ["firstName", "lastName"]
    
    for field in required_fields:
        if not candidate.get(field):
            return False
    
    return True


def clean_candidate_data(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and format candidate data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "firstName": candidate.get("firstName", "").strip(),
        "middleName": candidate.get("middleName", "").strip(),
        "lastName": candidate.get("lastName", "").strip(),
        "email1": candidate.get("email1", "").strip().lower(),
        "email2": candidate.get("email2", "").strip().lower(),
        "phoneHome": format_phone_number(candidate.get("phoneHome", "")),
        "phoneCell": format_phone_number(candidate.get("phoneCell", "")),
        "phoneWork": format_phone_number(candidate.get("phoneWork", "")),
        "address": candidate.get("address", "").strip(),
        "city": candidate.get("city", "").strip(),
        "state": candidate.get("state", "").strip().upper(),
        "zip": candidate.get("zip", "").strip(),
        "source": candidate.get("source", "").strip(),
        "keySkills": candidate.get("keySkills", "").strip(),
        "dateAvailable": format_date_for_opencats(candidate.get("dateAvailable", "")),
        "currentEmployer": candidate.get("currentEmployer", "").strip(),
        "canRelocate": 1 if candidate.get("canRelocate") else 0,
        "currentPay": str(candidate.get("currentPay", "")).strip(),
        "desiredPay": str(candidate.get("desiredPay", "")).strip(),
        "notes": candidate.get("notes", "").strip(),
        "webSite": candidate.get("webSite", "").strip(),
        "bestTimeToCall": candidate.get("bestTimeToCall", "").strip(),
        "gender": candidate.get("gender", "").strip().upper(),
        "race": validate_eeo_ethnic_type(candidate.get("race")),
        "veteran": validate_eeo_veteran_type(candidate.get("veteran")),
        "disability": candidate.get("disability", "").strip().upper(),
        "textResumeBlock": candidate.get("textResumeBlock", "").strip(),
        "textResumeFilename": candidate.get("textResumeFilename", "").strip(),
        "associatedAttachment": "",  # Not used in generation
    }
    
    return cleaned


def validate_eeo_ethnic_type(value: Any) -> int:
    """Validate EEO ethnic type value."""
    if not value:
        return 0
    
    try:
        int_value = int(value)
        if 1 <= int_value <= 5:
            return int_value
    except (ValueError, TypeError):
        pass
    
    return 0


def validate_eeo_veteran_type(value: Any) -> int:
    """Validate EEO veteran type value."""
    if not value:
        return 0
    
    try:
        int_value = int(value)
        if 1 <= int_value <= 4:
            return int_value
    except (ValueError, TypeError):
        pass
    
    return 0


async def candidates(n_candidates: int = None) -> Dict[str, Any]:
    """Generate candidates data."""
    target_count = n_candidates or DEFAULT_CANDIDATES_COUNT
    logger.info(f"👨‍💼 Starting candidate generation - Target: {target_count}")
    
    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    
    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)
    
    # Load existing data
    existing = load_existing_candidates()
    used_emails = existing["used_emails"]
    used_names = existing["used_names"]
    generated_candidates = existing["generated_candidates"]
    
    current_count = len(generated_candidates)
    remaining_count = max(0, target_count - current_count)
    
    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} candidates, no generation needed")
        return {"candidates": generated_candidates}
    
    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")
    
    # Generate candidates in batches
    new_candidates = []
    batches = (remaining_count + CANDIDATES_BATCH_SIZE - 1) // CANDIDATES_BATCH_SIZE
    
    for batch_num in range(batches):
        batch_size = min(CANDIDATES_BATCH_SIZE, remaining_count - len(new_candidates))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} candidates)")
        
        try:
            batch_candidates = await generate_candidates_batch(used_emails, used_names, batch_size)
            
            if batch_candidates:
                # Update used identifiers to avoid duplicates
                for candidate in batch_candidates:
                    if candidate.get("email1"):
                        used_emails.add(candidate["email1"].lower())
                    if candidate.get("firstName") and candidate.get("lastName"):
                        full_name = f"{candidate['firstName']} {candidate['lastName']}".lower()
                        used_names.add(full_name)
                
                new_candidates.extend(batch_candidates)
                logger.info(f"✅ Generated {len(batch_candidates)} candidates in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No candidates generated in batch {batch_num + 1}")
                
        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {str(e)}")
            continue
        
        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)
    
    # Combine with existing data
    all_candidates = generated_candidates + new_candidates
    
    # Save to file
    if save_to_json(all_candidates, CANDIDATES_FILEPATH):
        logger.succeed(f"✅ Candidate generation completed! Generated {len(new_candidates)} new candidates, total: {len(all_candidates)}")
    else:
        logger.error("❌ Failed to save candidates data")
    
    return {"candidates": all_candidates}
