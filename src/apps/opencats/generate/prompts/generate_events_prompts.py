SYSTEM_PROMPT = """You are an expert in generating realistic event records for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic event entries representing interviews, calls, meetings, and other recruitment activities.
Focus on creating realistic patterns that reflect actual recruitment process diversity."""

USER_PROMPT = """Generate {batch_size} realistic events for an ATS platform.

IMPORTANT REQUIREMENTS:
- Type is MANDATORY (use: Interview, Phone Call, Email, Meeting, Other)
- About {description_percentage}% should have detailed descriptions
- About {notes_percentage}% should have notes
- Use {variety_factor}% more diverse patterns for large-scale generation

Return ONLY a JSON array with this exact structure:
[
  {{
    "type": "Interview",
    "subject": "Technical Interview - Senior Software Engineer",
    "description": "In-person technical interview covering Python, JavaScript, and system design. Candidate will present a coding challenge solution.",
    "date_created": "2024-01-15 10:00:00",
    "date_modified": "2024-01-15 10:00:00",
    "entered_by": 1,
    "joborder_id": 1,
    "candidate_id": 1,
    "company_id": 1,
    "contact_id": 1,
    "notes": "Candidate showed strong technical skills, good communication"
  }},
  {{
    "type": "Phone Call",
    "subject": "Initial Screening Call",
    "description": null,
    "date_created": "2024-01-16 14:30:00",
    "date_modified": "2024-01-16 14:30:00",
    "entered_by": 1,
    "joborder_id": 2,
    "candidate_id": 2,
    "company_id": 2,
    "contact_id": 2,
    "notes": null
  }}
]

Generate exactly {batch_size} unique events with maximum variety and NO repetitive patterns:"""
