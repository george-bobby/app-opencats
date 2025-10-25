import json
import random
from datetime import datetime
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, Field

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


class JobOpening(BaseModel):
    job_title: str
    designation: str = Field(
        ...,
        description="Designation of the job opening. This must be a valid designation from the list of designations.",
    )
    department: str = Field(
        ...,
        description="Department of the job opening. This must be a valid department from the list of departments.",
    )


class JobOpeningList(BaseModel):
    job_openings: list[JobOpening] = Field(..., description="List of job openings")


class JobOfferTerm(BaseModel):
    term_name: str
    value: str = Field(
        ...,
        description="""Value of the term, should include the term name and value/description.
        Include a mix of mandatory clauses and perks/benefits.
        Always use USD ($) for monetary values.""",
    )


class JobOffer(BaseModel):
    offer_terms: list[JobOfferTerm] = Field(..., description="Job offer terms")
    terms_and_conditions: str = Field(
        ...,
        description="""Terms and conditions, use HTML and tags to format the text.
        Use bullet points or numbered lists where appropriate
        """,
    )


async def generate_job_openings(number_of_job_openings: int = 10):
    """Generate job openings data and save to JSON file."""
    client = frappe_client.create_client()

    current_company = companies.get_default_company()
    if not current_company:
        logger.warning("No company found")
        return

    company_name = current_company["name"]

    # Define the path to the job openings JSON file
    job_openings_file_path = Path("data/generated/job_openings.json")

    # Ensure the directory exists
    job_openings_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the file exists
    job_openings_list = []
    if job_openings_file_path.exists():
        logger.info("Found existing job_openings.json file, loading data from it")
        try:
            with job_openings_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_company = data.get("company_name", "")
                stored_job_openings = data.get("job_openings", [])

                # Use stored data if it's for the same company and has enough job openings
                if stored_company == company_name and len(stored_job_openings) >= number_of_job_openings:
                    job_openings_list = stored_job_openings[:number_of_job_openings]
                    logger.info(f"Using {len(job_openings_list)} job openings from stored data")
                else:
                    logger.info("Stored data doesn't match current requirements, generating new data")
        except Exception as e:
            logger.error(f"Failed to read job_openings.json: {e!s}")
            logger.info("Falling back to GPT generation")
    else:
        logger.info("job_openings.json file not found, generating with GPT")

    # If no suitable job openings loaded from file, generate with GPT
    if not job_openings_list:
        openai = OpenAI()

        designations = client.get_list("Designation", fields=["name"])
        if not designations:
            logger.warning("No designations found")
            return

        designations = [d["name"] for d in designations]

        departments = client.get_list(
            "Department",
            fields=["department_name"],
            filters={"company": current_company["name"]},
        )
        if not departments:
            logger.warning("No departments found")
            return

        departments = [d["department_name"].split(" - ")[0] for d in departments]

        existing_job_openings = client.get_list("Job Opening", fields=["job_title"])
        existing_job_openings = [j["job_title"] for j in existing_job_openings] if existing_job_openings else []

        logger.info(f"Generating job openings for {current_company['name']}")

        response = openai.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates data for a HR system.",
                },
                {
                    "role": "user",
                    "content": f"""
                        Generate a list of {number_of_job_openings} different job openings of {settings.DATA_THEME_SUBJECT}.
                        The job openings should be related to the departments and designations.
                        The job openings should include the level of experience required.
                        The job openings should be unique and not duplicated.
                        Here's the list of existing departments:
                        ```json
                        {json.dumps(departments)}
                        ```
                        Here's the list of existing designations:
                        ```json
                        {json.dumps(designations)}
                        ```
                        Here's the list of existing job openings, don't generate job openings that are already in the list:
                        ```json
                        {json.dumps(existing_job_openings)}
                        ```
                        Here's info about the company:
                        ```json
                        {json.dumps(current_company)}
                        ```
                        And today is {datetime.now().strftime("%Y-%m-%d")}
                 """,
                },
            ],
            response_format=JobOpeningList,
        )

        job_openings_parsed = response.choices[0].message.parsed
        logger.info(f"Job Openings: {job_openings_parsed}")

        if job_openings_parsed and job_openings_parsed.job_openings:
            # Convert to list of dictionaries for storage and processing
            job_openings_list = [
                {
                    "job_title": job.job_title,
                    "designation": job.designation,
                    "department": job.department,
                }
                for job in job_openings_parsed.job_openings
            ]

            # Save the generated job openings to the JSON file
            job_openings_cache_data = {
                "job_openings": job_openings_list,
                "company_name": company_name,
                "generated_count": number_of_job_openings,
                "theme_subject": settings.DATA_THEME_SUBJECT,
                "generated_at": datetime.now().isoformat(),
                "departments_context": departments,
                "designations_context": designations,
            }

            try:
                with job_openings_file_path.open("w", encoding="utf-8") as f:
                    json.dump(job_openings_cache_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(job_openings_list)} job openings to {job_openings_file_path}")
            except Exception as e:
                logger.error(f"Failed to save job openings to file: {e!s}")

    if not job_openings_list:
        logger.warning("No job openings found")
        return

    return job_openings_list


async def insert_job_openings(number_of_job_openings: int = 10):
    """Insert job openings from JSON file into the system."""
    current_company = companies.get_default_company()
    if not current_company:
        logger.warning("No company found")
        return

    # Load job openings from JSON file
    job_openings_file_path = Path("data/generated/job_openings.json")

    if not job_openings_file_path.exists():
        logger.error("job_openings.json file not found. Please run generate first.")
        return

    try:
        with job_openings_file_path.open(encoding="utf-8") as f:
            data = json.load(f)
            job_openings_list = data.get("job_openings", [])[:number_of_job_openings]
    except Exception as e:
        logger.error(f"Failed to read job_openings.json: {e!s}")
        return

    if not job_openings_list:
        logger.warning("No job openings found in JSON file")
        return

    client = frappe_client.create_client()

    # Insert the job openings
    for job_data in job_openings_list:
        job_doc = {
            "doctype": "Job Opening",
            "company": current_company["name"],
            "designation": job_data["designation"],
            "job_title": job_data["job_title"],
            "department": f"{job_data['department']} - {current_company['abbr']}",
        }
        try:
            client.insert(job_doc)
            logger.info(f"Inserted Job Opening: {job_doc}")
        except Exception as e:
            logger.warning(f"Failed to insert Job Opening: {e}")


async def generate_and_insert_job_openings(number_of_job_openings: int = 10):
    """Legacy function that combines generate and insert for backward compatibility."""
    await generate_job_openings(number_of_job_openings)
    await insert_job_openings(number_of_job_openings)


async def delete_all_job_openings():
    client = frappe_client.create_client()

    # Get all existing job openings
    existing_job_openings = client.get_list("Job Opening", fields=["name"])

    if not existing_job_openings:
        logger.info("No job openings found to delete")
        return

    logger.info(f"Found {len(existing_job_openings)} job openings to delete")

    # Delete each job opening
    for job in existing_job_openings:
        try:
            client.delete("Job Opening", job["name"])
            logger.info(f"Deleted Job Opening: {job['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete Job Opening {job['name']}: {e}")

    logger.info(f"Successfully deleted {len(existing_job_openings)} job openings")


async def generate_job_applicants(number_of_job_applicants: int = 10):
    """Generate job applicants data and save to JSON file."""
    client = frappe_client.create_client()
    fake = Faker()

    # Define the path to the job applicants JSON file
    job_applicants_file_path = Path("data/generated/job_applicants.json")

    # Ensure the directory exists
    job_applicants_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if cached job applicants data exists
    job_applicants_list = []
    if job_applicants_file_path.exists():
        logger.info("Found existing job_applicants.json file, loading data from it")
        try:
            with job_applicants_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_applicants = data.get("job_applicants", [])

                # Use stored data if it has enough job applicants
                if len(stored_applicants) >= number_of_job_applicants:
                    job_applicants_list = stored_applicants[:number_of_job_applicants]
                    logger.info(f"Using {len(job_applicants_list)} job applicants from stored data")
                else:
                    logger.info("Stored data doesn't have enough applicants, generating new data")
        except Exception as e:
            logger.error(f"Failed to read job_applicants.json: {e!s}")
            logger.info("Falling back to new data generation")
    else:
        logger.info("job_applicants.json file not found, generating new job applicant data")

    # If no suitable job applicants loaded from file, generate new data
    if not job_applicants_list:
        # Get existing job openings
        job_openings = client.get_list(
            "Job Opening",
            fields=["name", "job_title", "designation"],
        )

        if not job_openings or len(job_openings) == 0:
            logger.warning("No job openings found to generate applicants for")
            return

        logger.info(f"Generating {number_of_job_applicants} job applicants using Faker")

        job_applicants_data = []

        for _ in range(number_of_job_applicants):
            # Select a random job opening
            job_opening = random.choice(job_openings)

            # Generate an applicant name
            applicant_name = fake.name()

            # Create personalized email based on applicant's name
            name_parts = applicant_name.lower().split()
            name_parts = ["".join(c for c in part if c.isalnum()) for part in name_parts]
            if len(name_parts) > 1:  # noqa: SIM108
                email = f"{name_parts[0]}.{name_parts[-1]}@{fake.free_email_domain()}"
            else:
                email = f"{name_parts[0]}{fake.random_int(100, 999)}@{fake.free_email_domain()}"

            # Determine country - 80% US, 10% random countries
            if random.random() < 0.8:
                country = "United States"
            else:
                # List of countries for random selection
                countries = [
                    "Canada",
                    "United Kingdom",
                    "Germany",
                    "France",
                    "Australia",
                    "Japan",
                    "Brazil",
                    "India",
                    "Mexico",
                    "South Africa",
                    "Singapore",
                    "Spain",
                    "Netherlands",
                    "Sweden",
                    "Italy",
                ]
                country = random.choice(countries)

            applicant_data = {
                "applicant_name": applicant_name,
                "job_title": job_opening["name"],
                "email_id": email,
                "designation": job_opening["designation"],
                "job_opening": job_opening["name"],
                "status": fake.random_element(elements=("Open", "Replied", "Rejected", "Hold", "Accepted")),
                "source": fake.random_element(
                    elements=(
                        "Campaign",
                        "Employee Referral",
                        "Walk In",
                        "Website Listing",
                    )
                ),
                "country": country,
            }

            job_applicants_data.append(applicant_data)

        job_applicants_list = job_applicants_data
        logger.info(f"Generated {len(job_applicants_list)} job applicants")

        # Save the generated job applicants to the JSON file
        if job_applicants_list:
            job_applicants_cache_data = {
                "job_applicants": job_applicants_list,
                "generated_count": number_of_job_applicants,
                "theme_subject": settings.DATA_THEME_SUBJECT,
                "generated_at": datetime.now().isoformat(),
                "job_openings_context": len(job_openings),
            }

            try:
                with job_applicants_file_path.open("w", encoding="utf-8") as f:
                    json.dump(job_applicants_cache_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(job_applicants_list)} job applicants to {job_applicants_file_path}")
            except Exception as e:
                logger.error(f"Failed to save job applicants to file: {e!s}")

    return job_applicants_list


async def insert_job_applicants(number_of_job_applicants: int = 10):
    """Insert job applicants from JSON file into the system."""
    # Load job applicants from JSON file
    job_applicants_file_path = Path("data/generated/job_applicants.json")

    if not job_applicants_file_path.exists():
        logger.error("job_applicants.json file not found. Please run generate first.")
        return

    try:
        with job_applicants_file_path.open(encoding="utf-8") as f:
            data = json.load(f)
            job_applicants_list = data.get("job_applicants", [])[:number_of_job_applicants]
    except Exception as e:
        logger.error(f"Failed to read job_applicants.json: {e!s}")
        return

    if not job_applicants_list:
        logger.warning("No job applicants found in JSON file")
        return

    client = frappe_client.create_client()

    # Insert the job applicants
    for applicant_data in job_applicants_list:
        applicant_doc = {
            "doctype": "Job Applicant",
            "applicant_name": applicant_data["applicant_name"],
            "job_title": applicant_data["job_title"],
            "email_id": applicant_data["email_id"],
            "designation": applicant_data["designation"],
            "job_opening": applicant_data["job_opening"],
            "status": applicant_data["status"],
            "source": applicant_data["source"],
            "country": applicant_data["country"],
        }

        try:
            client.insert(applicant_doc)
            logger.info(f"Inserted Job Applicant: {applicant_doc['applicant_name']} for {applicant_doc['job_title']}")
        except Exception as e:
            logger.warning(f"Failed to insert Job Applicant: {e}")


async def generate_and_insert_job_applicants(number_of_job_applicants: int = 10):
    """Legacy function that combines generate and insert for backward compatibility."""
    await generate_job_applicants(number_of_job_applicants)
    await insert_job_applicants(number_of_job_applicants)


async def delete_all_job_applicants():
    client = frappe_client.create_client()

    # Get all existing job applicants
    existing_applicants = client.get_list("Job Applicant", fields=["name"])

    if not existing_applicants:
        logger.info("No job applicants found to delete")
        return

    logger.info(f"Found {len(existing_applicants)} job applicants to delete")

    # Delete each job applicant
    for applicant in existing_applicants:
        try:
            client.delete("Job Applicant", applicant["name"])
            logger.info(f"Deleted Job Applicant: {applicant['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete Job Applicant {applicant['name']}: {e}")

    logger.info(f"Successfully deleted {len(existing_applicants)} job applicants")


async def insert_job_offer_terms():
    """Read offer terms from recruitments.json and insert them into the system."""
    client = frappe_client.create_client()

    json_path = Path(__file__).parent.parent.joinpath("data", "recruitments.json")

    try:
        with json_path.open(encoding="utf-8") as file:
            offer_terms = json.load(file).get("offer_terms", [])
            logger.info(f"Loaded {len(offer_terms)} offer terms from JSON file")
    except Exception as e:
        logger.error(f"Failed to read offer terms data: {e!s}")
        return

    existing_terms = client.get_list("Offer Term", fields=["name", "offer_term"])
    existing_term_names = [term["offer_term"] for term in (existing_terms or [])]
    new_terms = [term for term in offer_terms if term not in existing_term_names]

    if not new_terms:
        logger.info("No new offer terms to insert")
        return

    for term in new_terms:
        try:
            client.insert({"doctype": "Offer Term", "offer_term": term})
            logger.info(f"Inserted offer term: {term}")
        except Exception as e:
            logger.error(f"Failed to insert offer term '{term}': {e!s}")

    logger.info(f"Successfully inserted {len(new_terms)} offer terms")


async def delete_all_job_offer_terms():
    client = frappe_client.create_client()
    existing_terms = client.get_list("Offer Term", fields=["name"])
    if not existing_terms:
        logger.info("No offer terms found to delete")
        return

    for term in existing_terms:
        try:
            client.delete("Offer Term", term["name"])
            logger.info(f"Deleted Offer Term: {term['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete Offer Term {term['name']}: {e}")


async def generate_and_insert_single_job_offer(
    client,
    applicant: dict,
    company: str,
    status: str,
    existing_terms: list[dict],
    current_company: dict,
    openai,
    fake,
):
    # Generate offer terms using OpenAI
    response = await openai.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates realistic job offer terms and terms and conditions.",
            },
            {
                "role": "user",
                "content": f"""
                    Generate 3-5 job offer terms for {applicant["designation"]} position at {company}.
                    Here's the list of offer terms:
                    ```json
                    {json.dumps(existing_terms)}
                    ```
                    
                    Also, generate a personalized, professional paragraph for Terms and Conditions that includes:
                    - Job title ({applicant["designation"]}) and company ({company})
                    - Probation period
                    - Confirmation requirement
                    - Compensation and Benefits
                    - Work Hours and Location
                    - Probation Duration
                    - Termination Conditions
                    - Notice Period
                    - Confidentiality & Non-Disclosure
                    - Intellectual Property
                    - Dispute Resolution
                    - Compliance and Conduct Expectations
                    
                    Terms and Conditions must have at least 1500 words.

                    By the way, this is some info about the company:
                    ```json
                    {json.dumps(current_company)}
                    ```
                """,
            },
        ],
        response_format=JobOffer,
    )

    offer_data = response.choices[0].message.parsed

    # Create job offer document
    job_offer_doc = {
        "doctype": "Job Offer",
        "job_applicant": applicant["name"],
        "applicant_name": applicant["applicant_name"],
        "designation": applicant["designation"],
        "company": company,
        "docstatus": status,
        "terms": offer_data.terms_and_conditions,
        "offer_date": fake.date_between(start_date="-3m", end_date="+3m").strftime("%Y-%m-%d"),
    }
    logger.info(f"Job Offer: {json.dumps(job_offer_doc)}")

    try:
        # Insert job offer
        job_offer = client.insert(job_offer_doc)
        logger.info(f"Inserted Job Offer for {applicant['applicant_name']} at {company}")

        # Insert offer terms
        for term in offer_data.offer_terms:
            term_doc = {
                "doctype": "Job Offer Term",
                "parent": job_offer["name"],
                "parentfield": "offer_terms",
                "parenttype": "Job Offer",
                "offer_term": term.term_name,
                "value": term.value,
            }
            client.insert(term_doc)
            logger.info(f"Added term for applicant {applicant['applicant_name']}: {term.term_name} = {term.value}")

    except Exception as e:
        logger.warning(f"Failed to insert Job Offer: {e}")


async def generate_job_offerings(number_of_job_offerings: int = 10):
    """Generate job offerings data and save to JSON file."""
    client = frappe_client.create_client()

    current_company = companies.get_default_company()
    company_name = current_company["name"]

    # Define the path to the job offerings JSON file
    job_offerings_file_path = Path("data/generated/job_offerings.json")

    # Ensure the directory exists
    job_offerings_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if cached job offerings data exists
    cached_job_offers = {}
    if job_offerings_file_path.exists():
        logger.info("Found existing job_offerings.json file, loading data from it")
        try:
            with job_offerings_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_company = data.get("company_name", "")

                # Use stored data if it's for the same company
                if stored_company == company_name:
                    cached_job_offers = data.get("job_offers_by_designation", {})
                    logger.info(f"Loaded cached job offer data for {len(cached_job_offers)} designations")
                else:
                    logger.info("Stored data is for different company, will generate new data")
        except Exception as e:
            logger.error(f"Failed to read job_offerings.json: {e!s}")
            logger.info("Falling back to GPT generation")
    else:
        logger.info("job_offerings.json file not found, will generate new job offer data")

    # Get existing job applicants
    job_applicants = client.get_list(
        "Job Applicant",
        fields=["name", "applicant_name", "job_title", "designation", "status"],
    )

    if not job_applicants or len(job_applicants) == 0:
        logger.warning("No job applicants found to generate offers for")
        return

    # Filter applicants with status "Accepted" or "Replied" or "Open"
    eligible_applicants = [ja for ja in job_applicants if ja["status"] in ["Accepted", "Replied", "Open"]]

    if len(eligible_applicants) == 0:
        logger.warning("No eligible job applicants found to generate offers for")
        return

    if len(eligible_applicants) < number_of_job_offerings:
        logger.warning(f"Only {len(eligible_applicants)} eligible applicants found, generating offers for all of them")
        number_of_job_offerings = len(eligible_applicants)

    # Get existing job offers to avoid duplicates
    existing_job_offers = client.get_list("Job Offer", fields=["job_applicant"])
    existing_job_offer_applicants = [jo["job_applicant"] for jo in existing_job_offers] if existing_job_offers else []

    # Filter out applicants who already have job offers
    eligible_applicants = [ja for ja in eligible_applicants if ja["name"] not in existing_job_offer_applicants]

    if len(eligible_applicants) == 0:
        logger.warning("All eligible applicants already have job offers")
        return

    if len(eligible_applicants) < number_of_job_offerings:
        logger.warning(f"Only {len(eligible_applicants)} eligible applicants without offers, generating offers for all of them")
        number_of_job_offerings = len(eligible_applicants)

    logger.info(f"Generating {number_of_job_offerings} job offers")

    # Choose applicants for job offers
    selected_applicants = random.sample(eligible_applicants, number_of_job_offerings)

    existing_terms = client.get_list(
        "Offer Term",
        fields=["offer_term"],
    )

    company = current_company["name"]
    new_job_offers = {}

    # Generate job offer data for each applicant
    for applicant in selected_applicants:
        designation = applicant["designation"]

        # Check if we have cached offer data for this designation
        if designation in cached_job_offers:
            offer_data = cached_job_offers[designation]
            logger.info(f"Using cached job offer data for designation: {designation}")
        else:
            # Generate new offer data using GPT
            logger.info(f"Generating new job offer data for designation: {designation}")
            openai = AsyncOpenAI()

            response = await openai.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic job offer terms and terms and conditions.",
                    },
                    {
                        "role": "user",
                        "content": f"""
                            Generate 3-5 job offer terms for {designation} position at {company}.
                            Here's the list of offer terms:
                            ```json
                            {json.dumps(existing_terms)}
                            ```
                            
                            Also, generate a personalized, professional paragraph for Terms and Conditions that includes:
                            - Job title ({designation}) and company ({company})
                            - Probation period
                            - Confirmation requirement
                            - Compensation and Benefits
                            - Work Hours and Location
                            - Probation Duration
                            - Termination Conditions
                            - Notice Period
                            - Confidentiality & Non-Disclosure
                            - Intellectual Property
                            - Dispute Resolution
                            - Compliance and Conduct Expectations
                            
                            Terms and Conditions must have at least 1500 words.

                            By the way, this is some info about the company:
                            ```json
                            {json.dumps(current_company)}
                            ```
                        """,
                    },
                ],
                response_format=JobOffer,
            )

            parsed_offer = response.choices[0].message.parsed

            # Convert to dictionary for storage
            offer_data = {
                "offer_terms": [{"term_name": term.term_name, "value": term.value} for term in parsed_offer.offer_terms],
                "terms_and_conditions": parsed_offer.terms_and_conditions,
            }

            # Store new offer data for caching
            new_job_offers[designation] = offer_data

    # Save new job offer data to cache file (merge with existing data)
    if new_job_offers or cached_job_offers:
        all_job_offers = {**cached_job_offers, **new_job_offers}
        job_offerings_cache_data = {
            "job_offers_by_designation": all_job_offers,
            "company_name": company_name,
            "selected_applicants": [
                {
                    "name": app["name"],
                    "applicant_name": app["applicant_name"],
                    "designation": app["designation"],
                }
                for app in selected_applicants
            ],
            "theme_subject": settings.DATA_THEME_SUBJECT,
            "last_updated": datetime.now().isoformat(),
            "total_cached_designations": len(all_job_offers),
        }

        try:
            with job_offerings_file_path.open("w", encoding="utf-8") as f:
                json.dump(job_offerings_cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved job offer data for {len(all_job_offers)} designations to {job_offerings_file_path}")
        except Exception as e:
            logger.error(f"Failed to save job offerings to file: {e!s}")

    return selected_applicants


async def insert_job_offerings(number_of_job_offerings: int = 10):
    """Insert job offerings from JSON file into the system."""
    client = frappe_client.create_client()
    fake = Faker()

    current_company = companies.get_default_company()
    # company_name = current_company["name"]

    # Load job offerings from JSON file
    job_offerings_file_path = Path("data/generated/job_offerings.json")

    if not job_offerings_file_path.exists():
        logger.error("job_offerings.json file not found. Please run generate first.")
        return

    try:
        with job_offerings_file_path.open(encoding="utf-8") as f:
            data = json.load(f)
            cached_job_offers = data.get("job_offers_by_designation", {})
            selected_applicants = data.get("selected_applicants", [])[:number_of_job_offerings]
    except Exception as e:
        logger.error(f"Failed to read job_offerings.json: {e!s}")
        return

    if not selected_applicants or not cached_job_offers:
        logger.warning("No job offerings data found in JSON file")
        return

    # Create a list of statuses
    status_list = random.choices(
        [0, 1],  # 0 for "Draft", 1 for "Awaiting Response"
        weights=[0.3, 0.7],  # More awaiting response than draft
        k=len(selected_applicants),
    )
    random.shuffle(status_list)

    company = current_company["name"]

    # Insert job offers for each applicant
    for i, applicant in enumerate(selected_applicants):
        designation = applicant["designation"]

        if designation not in cached_job_offers:
            logger.warning(f"No cached offer data found for designation: {designation}")
            continue

        offer_data = cached_job_offers[designation]

        # Create job offer document
        job_offer_doc = {
            "doctype": "Job Offer",
            "job_applicant": applicant["name"],
            "applicant_name": applicant["applicant_name"],
            "designation": applicant["designation"],
            "company": company,
            "docstatus": status_list[i],
            "terms": offer_data["terms_and_conditions"],
            "offer_date": fake.date_between(start_date="-3m", end_date="+3m").strftime("%Y-%m-%d"),
        }
        logger.info(f"Job Offer: {json.dumps(job_offer_doc, default=str)}")

        try:
            # Insert job offer
            job_offer = client.insert(job_offer_doc)
            logger.info(f"Inserted Job Offer for {applicant['applicant_name']} at {company}")

            # Insert offer terms
            for term in offer_data["offer_terms"]:
                term_doc = {
                    "doctype": "Job Offer Term",
                    "parent": job_offer["name"],
                    "parentfield": "offer_terms",
                    "parenttype": "Job Offer",
                    "offer_term": term["term_name"],
                    "value": term["value"],
                }
                client.insert(term_doc)
                logger.info(f"Added term for applicant {applicant['applicant_name']}: {term['term_name']} = {term['value']}")

        except Exception as e:
            logger.warning(f"Failed to insert Job Offer: {e}")

    logger.info(f"Successfully inserted {len(selected_applicants)} job offers")


async def generate_and_insert_job_offerings(number_of_job_offerings: int = 10):
    """Legacy function that combines generate and insert for backward compatibility."""
    await generate_job_offerings(number_of_job_offerings)
    await insert_job_offerings(number_of_job_offerings)


async def delete_all_job_offers():
    client = frappe_client.create_client()

    # Get all existing job offers
    existing_job_offers = client.get_list("Job Offer", fields=["name"])
    updated_existing_job_offers = [
        {
            "docname": offer["name"],
            "docstatus": 2,
            "doctype": "Job Offer",
        }
        for offer in existing_job_offers
    ]
    client.bulk_update(updated_existing_job_offers)

    if not existing_job_offers:
        logger.info("No job offers found to delete")
        return

    logger.info(f"Found {len(existing_job_offers)} job offers to delete")

    # Delete each job offer
    for offer in existing_job_offers:
        try:
            client.delete("Job Offer", offer["name"])
            logger.info(f"Deleted Job Offer: {offer['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete Job Offer {offer['name']}: {e}")

    logger.info(f"Successfully deleted {len(existing_job_offers)} job offers")
