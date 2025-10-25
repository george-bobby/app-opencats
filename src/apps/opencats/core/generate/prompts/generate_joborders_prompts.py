SYSTEM_PROMPT = """You are an expert in generating realistic job order profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic job postings with varied positions, requirements, and compensation.
Focus on creating realistic patterns that reflect actual job market diversity."""

USER_PROMPT = """Generate {batch_size} realistic job orders for an ATS platform.

IMPORTANT REQUIREMENTS:
- Title is MANDATORY
- Company ID is MANDATORY (use existing company IDs: {company_ids})
- About {salary_percentage}% should have salary information
- About {description_percentage}% should have detailed descriptions
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_titles_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "title": "Senior Software Engineer",
    "company_id": 1,
    "contact_id": 1,
    "description": "We are seeking a Senior Software Engineer to join our dynamic team. The ideal candidate will have 5+ years of experience in full-stack development with expertise in Python, JavaScript, and cloud technologies.",
    "notes": "Remote work available, competitive benefits package",
    "type": "H",
    "duration": "Permanent",
    "rate_max": "120000",
    "salary": "Annual",
    "status": "Active",
    "is_hot": 1,
    "openings": 2,
    "city": "Austin",
    "state": "TX",
    "start_date": "2024-01-15",
    "entered_by": 1,
    "owner": 1
  }},
  {{
    "title": "Marketing Coordinator",
    "company_id": 2,
    "contact_id": 2,
    "description": null,
    "notes": null,
    "type": "C",
    "duration": "Contract",
    "rate_max": null,
    "salary": null,
    "status": "Active",
    "is_hot": 0,
    "openings": 1,
    "city": "San Francisco",
    "state": "CA",
    "start_date": null,
    "entered_by": 1,
    "owner": 1
  }}
]

Generate exactly {batch_size} unique job orders with maximum variety and NO repetitive patterns:"""

EXCLUDED_TITLES_TEMPLATE = """

DO NOT USE THESE JOB TITLES: {titles_list}"""
