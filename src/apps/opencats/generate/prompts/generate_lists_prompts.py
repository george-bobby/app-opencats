SYSTEM_PROMPT = """You are an expert in generating realistic list entries for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic list items representing saved searches, candidate pools, and custom lists.
Focus on creating realistic patterns that reflect actual recruitment list diversity."""

USER_PROMPT = """Generate {batch_size} realistic lists for an ATS platform.

IMPORTANT REQUIREMENTS:
- Name is MANDATORY
- About {description_percentage}% should have descriptions
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_names_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "name": "Senior Developers - Austin",
    "description": "Pool of senior software developers in Austin area with 5+ years experience",
    "created_by": 1,
    "date_created": "2024-01-15 09:00:00",
    "is_hot_list": 1,
    "notes": "High priority candidates for upcoming projects"
  }},
  {{
    "name": "Marketing Professionals",
    "description": null,
    "created_by": 1,
    "date_created": "2024-01-16 11:30:00",
    "is_hot_list": 0,
    "notes": null
  }}
]

Generate exactly {batch_size} unique lists with maximum variety and NO repetitive patterns:"""

EXCLUDED_NAMES_TEMPLATE = """

DO NOT USE THESE LIST NAMES: {names_list}"""
