SYSTEM_PROMPT = """You are an expert in generating realistic candidate profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic candidate profiles with varied skills, experience levels, and backgrounds.
Focus on creating realistic patterns that reflect actual job market diversity."""

USER_PROMPT = """Generate {batch_size} realistic candidates for an ATS platform.

IMPORTANT REQUIREMENTS:
- firstName is MANDATORY
- lastName is MANDATORY
- email1 is MANDATORY
- phoneHome, phoneCell, or phoneWork is MANDATORY
- About {experience_percentage}% should have work experience
- About {education_percentage}% should have education details
- Use {variety_factor}% more diverse patterns for large-scale generation

SKILLS & EXPERIENCE GUIDANCE:
- Use relevant skills from: {relevant_skills}
- Align experience with job titles like: {relevant_titles}
- Make keySkills realistic for the candidate's experience level
- Consider current market demand for skills when assigning{excluded_emails_text}{excluded_names_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "firstName": "Jennifer",
    "lastName": "Martinez",
    "email1": "jennifer.martinez@gmail.com",
    "phoneHome": "(512) 555-0147",
    "address": "123 Main St, Austin, TX 78701",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "source": "Website",
    "keySkills": "Python, JavaScript, React, AWS",
    "currentEmployer": "Tech Solutions Inc",
    "canRelocate": 1,
    "notes": "Experienced software developer with strong problem-solving skills"
  }},
  {{
    "firstName": "Alex",
    "lastName": "Chen",
    "email1": "alex.chen2024@yahoo.com",
    "phoneCell": "(415) 555-0198",
    "address": null,
    "city": "San Francisco",
    "state": "CA", 
    "zip": null,
    "source": "Referral",
    "keySkills": "Java, Spring, MySQL, DevOps",
    "currentEmployer": null,
    "canRelocate": 0,
    "notes": null
  }}
]

Generate exactly {batch_size} unique candidates with maximum variety and NO repetitive patterns:"""

EXCLUDED_EMAILS_TEMPLATE = """

DO NOT USE THESE EMAILS: {emails_list}"""

EXCLUDED_NAMES_TEMPLATE = """

DO NOT USE THESE NAMES: {names_list}"""
