"""Generate contacts data for OpenCATS using AI."""

import asyncio
import random
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    CONTACTS_BATCH_SIZE,
    CONTACTS_FILEPATH,
    COMPANIES_FILEPATH,
    DEFAULT_CONTACTS_COUNT,
    JOB_TITLES,
    DEPARTMENTS,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import load_existing_data, validate_data_structure, format_phone_number
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_contacts():
    """Load existing contacts to prevent duplicates."""
    existing_data = load_existing_data(CONTACTS_FILEPATH)
    
    used_emails = set()
    used_names = set()
    
    for contact in existing_data:
        if contact.get("email1"):
            used_emails.add(contact["email1"].lower())
        if contact.get("firstName") and contact.get("lastName"):
            full_name = f"{contact['firstName']} {contact['lastName']}".lower()
            used_names.add(full_name)
    
    return {
        "used_emails": used_emails,
        "used_names": used_names,
        "generated_contacts": existing_data,
    }


def load_companies_for_contacts():
    """Load companies to assign contacts to."""
    companies_data = load_existing_data(COMPANIES_FILEPATH)
    
    if not companies_data:
        logger.warning("No companies found. Contacts will be generated without company assignments.")
        return []
    
    # Create a list of companies with their IDs (simulated as index + 1)
    companies_with_ids = []
    for idx, company in enumerate(companies_data):
        companies_with_ids.append({
            "id": idx + 1,  # Simulated company ID
            "name": company.get("name", ""),
            "departments": company.get("departmentsCSV", "").split(",") if company.get("departmentsCSV") else []
        })
    
    return companies_with_ids


def create_contacts_prompt(used_emails: set, used_names: set, companies: List[Dict], batch_size: int) -> str:
    """Create prompt for contact generation."""
    excluded_emails_text = ""
    if used_emails:
        recent_emails = list(used_emails)[-10:]
        excluded_emails_text = f"\n\nDo not use these email addresses (already exist): {', '.join(recent_emails)}"
    
    excluded_names_text = ""
    if used_names:
        recent_names = list(used_names)[-10:]
        excluded_names_text = f"\n\nDo not use these names (already exist): {', '.join(recent_names)}"
    
    # Select random companies for this batch
    selected_companies = random.sample(companies, min(batch_size, len(companies))) if companies else []
    
    companies_info = ""
    if selected_companies:
        companies_list = []
        for company in selected_companies:
            dept_info = f" (departments: {', '.join(company['departments'])})" if company['departments'] else ""
            companies_list.append(f"ID {company['id']}: {company['name']}{dept_info}")
        companies_info = f"\n\nAssign contacts to these companies:\n{chr(10).join(companies_list)}"
    
    job_titles_list = ", ".join(random.sample(JOB_TITLES, min(15, len(JOB_TITLES))))
    departments_list = ", ".join(random.sample(DEPARTMENTS, min(10, len(DEPARTMENTS))))
    
    prompt = f"""Generate {batch_size} realistic business contacts for {settings.DATA_THEME_SUBJECT}.

Use these job titles: {job_titles_list}
Use these departments: {departments_list}

Each contact should have:
- companyID: Company ID from the provided list (required)
- firstName: First name
- lastName: Last name  
- title: Job title from the provided list
- department: Department name (optional, 70% chance)
- reportsTo: Name of manager (optional, 40% chance)
- email1: Primary business email (firstname.lastname@company.com format)
- email2: Secondary email (optional, 20% chance)
- phoneWork: Work phone number in format (XXX) XXX-XXXX
- phoneCell: Cell phone number (optional, 60% chance)
- phoneOther: Other phone number (optional, 15% chance)
- address: Business address
- city: City name
- state: 2-letter US state code
- zip: 5-digit ZIP code
- isHot: 1 for important contacts (25% chance), 0 otherwise
- notes: Brief note about the contact's role or importance (1 sentence)
- departmentsCSV: Relevant departments for the company (optional)

Return as JSON array.{companies_info}{excluded_emails_text}{excluded_names_text}"""
    
    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_contacts_batch(used_emails: set, used_names: set, companies: List[Dict], batch_size: int) -> List[Dict[str, Any]]:
    """Generate a batch of contacts using AI."""
    prompt = create_contacts_prompt(used_emails, used_names, companies, batch_size)
    
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
    
    contacts_data = parse_anthropic_response(response)
    if not contacts_data:
        logger.error("Failed to parse contacts data from API response")
        return []
    
    # Validate and clean the data
    validated_contacts = []
    for contact in contacts_data:
        if validate_contact_data(contact):
            # Clean and format the data
            cleaned_contact = clean_contact_data(contact)
            validated_contacts.append(cleaned_contact)
        else:
            logger.warning(f"Invalid contact data: {contact}")
    
    return validated_contacts


def validate_contact_data(contact: Dict[str, Any]) -> bool:
    """Validate contact data structure."""
    required_fields = ["companyID", "firstName", "lastName", "title"]
    
    for field in required_fields:
        if not contact.get(field):
            return False
    
    return True


def clean_contact_data(contact: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and format contact data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "companyID": int(contact.get("companyID", 1)),
        "firstName": contact.get("firstName", "").strip(),
        "lastName": contact.get("lastName", "").strip(),
        "title": contact.get("title", "").strip(),
        "department": contact.get("department", "").strip(),
        "reportsTo": contact.get("reportsTo", "").strip(),
        "email1": contact.get("email1", "").strip().lower(),
        "email2": contact.get("email2", "").strip().lower(),
        "phoneWork": format_phone_number(contact.get("phoneWork", "")),
        "phoneCell": format_phone_number(contact.get("phoneCell", "")),
        "phoneOther": format_phone_number(contact.get("phoneOther", "")),
        "address": contact.get("address", "").strip(),
        "city": contact.get("city", "").strip(),
        "state": contact.get("state", "").strip().upper(),
        "zip": contact.get("zip", "").strip(),
        "isHot": 1 if contact.get("isHot") else 0,
        "notes": contact.get("notes", "").strip(),
        "departmentsCSV": contact.get("departmentsCSV", "").strip(),
    }
    
    return cleaned


async def contacts(n_contacts: int = None) -> Dict[str, Any]:
    """Generate contacts data."""
    target_count = n_contacts or DEFAULT_CONTACTS_COUNT
    logger.info(f"👥 Starting contact generation - Target: {target_count}")
    
    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    
    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)
    
    # Load existing data
    existing = load_existing_contacts()
    used_emails = existing["used_emails"]
    used_names = existing["used_names"]
    generated_contacts = existing["generated_contacts"]
    
    # Load companies for assignment
    companies = load_companies_for_contacts()
    if not companies:
        logger.error("❌ No companies available. Generate companies first.")
        return {"contacts": generated_contacts}
    
    current_count = len(generated_contacts)
    remaining_count = max(0, target_count - current_count)
    
    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} contacts, no generation needed")
        return {"contacts": generated_contacts}
    
    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")
    
    # Generate contacts in batches
    new_contacts = []
    batches = (remaining_count + CONTACTS_BATCH_SIZE - 1) // CONTACTS_BATCH_SIZE
    
    for batch_num in range(batches):
        batch_size = min(CONTACTS_BATCH_SIZE, remaining_count - len(new_contacts))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} contacts)")
        
        try:
            batch_contacts = await generate_contacts_batch(used_emails, used_names, companies, batch_size)
            
            if batch_contacts:
                # Update used identifiers to avoid duplicates
                for contact in batch_contacts:
                    if contact.get("email1"):
                        used_emails.add(contact["email1"].lower())
                    if contact.get("firstName") and contact.get("lastName"):
                        full_name = f"{contact['firstName']} {contact['lastName']}".lower()
                        used_names.add(full_name)
                
                new_contacts.extend(batch_contacts)
                logger.info(f"✅ Generated {len(batch_contacts)} contacts in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No contacts generated in batch {batch_num + 1}")
                
        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {str(e)}")
            continue
        
        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)
    
    # Combine with existing data
    all_contacts = generated_contacts + new_contacts
    
    # Save to file
    if save_to_json(all_contacts, CONTACTS_FILEPATH):
        logger.succeed(f"✅ Contact generation completed! Generated {len(new_contacts)} new contacts, total: {len(all_contacts)}")
    else:
        logger.error("❌ Failed to save contacts data")
    
    return {"contacts": all_contacts}
