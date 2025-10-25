import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


fake = Faker()

# Initialize Frappe client

# Initialize OpenAI client
openai_client = AsyncOpenAI()


# Load appraisal data from JSON file
def load_appraisal_data() -> dict[str, Any]:
    json_path = Path(__file__).parent.parent.joinpath("data", "appraisals.json")
    return json.loads(json_path.read_text(encoding="utf-8"))


# Load the data once when the module is imported
appraisal_data = load_appraisal_data()

# Sample KRAs with descriptions and weightages
SAMPLE_KRAS = appraisal_data["sample_kras"]

# Self appraisal templates that will be randomized
SELF_APPRAISAL_TEMPLATES = appraisal_data["self_appraisal_templates"]

# Areas of work/improvement for self appraisals
AREAS = appraisal_data["areas"]

ACHIEVEMENTS = appraisal_data["achievements"]

IMPROVEMENT_AREAS = appraisal_data["improvement_areas"]

FUTURE_GOALS = appraisal_data["future_goals"]

PROGRESS_LEVELS = appraisal_data["progress_levels"]
METRICS = appraisal_data["metrics"]
METRIC_DETAILS = appraisal_data["metric_details"]


def generate_performance_cycles(company_name: str) -> list[dict[str, Any]]:
    """Generate performance cycle data for the current year."""
    current_year = datetime.now().year
    last_year = current_year - 1
    # current_date = datetime.now().date()

    # Define quarters for the current year
    quarters = [
        {
            "name": f"Q1 {last_year}",
            "start_date": datetime(last_year, 1, 1),
            "end_date": datetime(last_year, 3, 31),
        },
        {
            "name": f"Q2 {last_year}",
            "start_date": datetime(last_year, 4, 1),
            "end_date": datetime(last_year, 6, 30),
        },
        {
            "name": f"Q3 {last_year}",
            "start_date": datetime(last_year, 7, 1),
            "end_date": datetime(last_year, 9, 30),
        },
        {
            "name": f"Q4 {last_year}",
            "start_date": datetime(last_year, 10, 1),
            "end_date": datetime(last_year, 12, 31),
        },
        {
            "name": f"Q1 {current_year}",
            "start_date": datetime(current_year, 1, 1),
            "end_date": datetime(current_year, 3, 31),
        },
        {
            "name": f"Q2 {current_year}",
            "start_date": datetime(current_year, 4, 1),
            "end_date": datetime(current_year, 6, 30),
        },
        {
            "name": f"Q3 {current_year}",
            "start_date": datetime(current_year, 7, 1),
            "end_date": datetime(current_year, 9, 30),
        },
        {
            "name": f"Q4 {current_year}",
            "start_date": datetime(current_year, 10, 1),
            "end_date": datetime(current_year, 12, 31),
        },
    ]

    # Format for Frappe
    cycle_docs = []
    for quarter in quarters:
        # Determine initial status based on date, but don't set docstatus yet
        # start_date = quarter["start_date"].date()
        # end_date = quarter["end_date"].date()

        # if end_date < current_date:
        #     status = "In Progress"  # Must be in progress in order to generate appraisals
        # elif start_date <= current_date <= end_date:
        #     status = "In Progress"
        # else:
        #     status = "Not Started"

        cycle_docs.append(
            {
                "doctype": "Appraisal Cycle",
                "cycle_name": quarter["name"],
                "company": company_name,
                "start_date": quarter["start_date"].strftime("%Y-%m-%d"),
                "end_date": quarter["end_date"].strftime("%Y-%m-%d"),
            }
        )

    return cycle_docs


def generate_self_appraisal() -> str:
    """Generate a realistic self appraisal statement."""
    template = random.choice(SELF_APPRAISAL_TEMPLATES)

    # Replace placeholders with random values from our lists
    filled_template = template.format(
        cycle=random.choice(["quarter", "period", "appraisal cycle"]),
        progress_level=random.choice(PROGRESS_LEVELS),
        area1=random.choice(AREAS),
        area2=random.choice(AREAS),
        metric1=random.choice(METRICS),
        metric_detail=random.choice(METRIC_DETAILS),
        achievement=random.choice(ACHIEVEMENTS),
        improvement_area=random.choice(IMPROVEMENT_AREAS),
        future_goal=random.choice(FUTURE_GOALS),
        achievement_impact="the team" if random.random() > 0.5 else "the project",
        feedback_area=random.choice(AREAS),
        team_contribution=random.choice(["team goals", "department objectives", "company initiatives"]),
    )

    return filled_template


def generate_kras(num_kras=3) -> list[dict[str, Any]]:
    """Generate a list of KRAs for an appraisal."""
    selected_kras = random.sample(SAMPLE_KRAS, min(num_kras, len(SAMPLE_KRAS)))

    kra_list = []
    total_weightage = 0

    # First pass: assign random weightages from ranges
    for kra in selected_kras:
        weightage = random.randint(*kra["weightage_range"])
        total_weightage += weightage

        kra_list.append(
            {
                "key_result_area": kra["kra"],
                "weightage": weightage,
                "per_goal_completion": random.randint(70, 100),
                "description": kra["description"],
            }
        )

    # Adjust weightages to sum to 100%
    if total_weightage != 100:
        # Simple normalization
        factor = 100 / total_weightage
        for kra_item in kra_list:
            kra_item["weightage"] = round(kra_item["weightage"] * factor)

        # Handle any remaining difference due to rounding
        diff = 100 - sum(kra_item["weightage"] for kra_item in kra_list)
        if diff != 0:
            kra_list[0]["weightage"] += diff

    # Calculate goal score
    for kra_item in kra_list:
        kra_item["goal_score"] = round((kra_item["weightage"] * kra_item["per_goal_completion"]) / 100)

    return kra_list


def generate_reflection() -> str:
    """Generate a realistic reflection statement for an appraisal."""
    achievements = [
        "managed sprint deliverables more efficiently",
        "improved code quality with fewer review comments",
        "mentored junior developers effectively",
        "conducted internal tech talks",
        "optimized database queries resulting in performance improvements",
        "implemented CI/CD pipeline optimizations",
        "reduced bug count in production releases",
        "contributed to open source projects",
        "improved test coverage across the codebase",
        "streamlined the code review process",
        "led architecture discussions for new features",
        "documented legacy systems",
        "refactored complex code modules",
        "resolved critical production issues",
        "facilitated knowledge sharing sessions",
    ]

    improvement_areas = [
        "could have spent more time on external certifications",
        "need to improve documentation habits",
        "should focus more on exploring new technologies",
        "could enhance communication with non-technical stakeholders",
        "need to delegate tasks more effectively",
        "should improve estimation accuracy for complex tasks",
        "could contribute more to architectural discussions",
        "should dedicate more time to mentoring junior team members",
        "need to create more comprehensive test scenarios",
        "could reduce technical debt more proactively",
        "should participate more actively in code reviews",
    ]

    future_goals = [
        "prioritize external certifications",
        "improve technical documentation",
        "explore emerging technologies",
        "take on more leadership responsibilities",
        "contribute to system architecture",
        "enhance collaboration with other departments",
        "develop better time management strategies",
        "focus on building scalable solutions",
        "improve communication with stakeholders",
        "deepen expertise in specific technical domains",
    ]

    # Select 2-3 random achievements
    selected_achievements = random.sample(achievements, random.randint(2, 3))
    # Select 1-2 improvement areas
    selected_improvements = random.sample(improvement_areas, random.randint(1, 2))
    # Select 1 future goal
    selected_goal = random.choice(future_goals)

    # Construct the reflection
    reflection = f"This quarter, I've made strong progress in {selected_achievements[0]} and {selected_achievements[1]}"
    if len(selected_achievements) > 2:
        reflection += f". I also {selected_achievements[2]}"

    reflection += f". I {selected_improvements[0]}"
    if len(selected_improvements) > 1:
        reflection += f" and {selected_improvements[1]}"

    reflection += f", which I plan to {selected_goal} in the next cycle. Overall, I believe I've added value to the team both technically and collaboratively."

    return reflection


def ensure_kra_exists(kra_title: str) -> bool:
    """Ensure a KRA document exists for the given title. Create it if it doesn't exist."""

    client = frappe_client.create_client()

    try:
        # Check if KRA already exists
        existing_kras = client.get_list(
            "KRA",
            fields=["name", "title"],
            filters=[["title", "=", kra_title]],
            limit_page_length=1,
        )

        if existing_kras:
            logger.debug(f"KRA already exists: {kra_title}")
            return True

        # Create the KRA if it doesn't exist
        client.insert({"doctype": "KRA", "title": kra_title})
        logger.info(f"Created missing KRA: {kra_title}")
        return True

    except Exception as e:
        logger.error(f"Failed to ensure KRA exists for '{kra_title}': {e!s}")
        return False


def generate_appraisal(
    employee: dict[str, Any],
    cycle: dict[str, Any],
    templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate a single appraisal record with KRAs from templates if available."""
    # Check if we have templates available
    if templates and len(templates) > 0:
        # Select a random template
        template = random.choice(templates)

        # Ensure all KRAs from the template exist as documents
        for goal in template["goals"]:
            ensure_kra_exists(goal["key_result_area"])

        # Generate KRAs from template goals
        kras = []
        for _, goal in enumerate(template["goals"], 1):
            goal_completion = random.randint(70, 100)
            goal_score = round((float(goal["per_weightage"]) * goal_completion) / 100)

            kra = {
                "key_result_area": goal["key_result_area"],
                "weightage": float(goal["per_weightage"]),
                "per_goal_completion": goal_completion,
                "goal_score": goal_score,
            }
            kras.append(kra)

        # Generate self ratings from template rating criteria
        self_ratings = []
        for _, criterion in enumerate(template["rating_criteria"], 1):
            rating = {
                "criteria": criterion["criteria"],
                "per_weightage": float(criterion["per_weightage"]),
                "rating": round(random.uniform(0.7, 1.0), 1),  # Random rating between 0.7 and 1.0
            }
            self_ratings.append(rating)

        # Calculate total score
        total_score = sum(kra["goal_score"] for kra in kras)

        # Generate reflections
        reflection = generate_reflection()

        # Prepare appraisal_kra with proper format
        appraisal_kra = []
        for idx, goal in enumerate(template["goals"], 1):
            goal_completion = random.randint(70, 100)
            goal_score = round((float(goal["per_weightage"]) * goal_completion) / 100)

            kra_item = {
                "doctype": "Appraisal KRA",
                "idx": idx,
                "kra": goal["key_result_area"],
                "per_weightage": float(goal["per_weightage"]),
                "goal_completion": goal_completion,
                "goal_score": goal_score,
                "parentfield": "appraisal_kra",
                "parenttype": "Appraisal",
            }
            appraisal_kra.append(kra_item)

        # Generate appraisal document with template data
        appraisal = {
            "doctype": "Appraisal",
            "employee": employee["name"],
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
            "company": employee.get("company", ""),
            "appraisal_cycle": cycle["name"],
            "status": "Completed",
            "kra": kras,
            "self_appraisal": generate_self_appraisal(),
            "reflections": reflection,
            "total_score": total_score,
            "appraisal_template": template["name"],
            "appraisal_kra": appraisal_kra,
            "self_ratings": self_ratings,
        }
    else:
        # Use the original logic if no templates are available
        # Generate KRAs
        original_kras = generate_kras(random.randint(3, 5))

        # Ensure all KRAs exist as documents
        for kra in original_kras:
            ensure_kra_exists(kra["key_result_area"])

        # Format KRAs for appraisal_kra field
        appraisal_kra = []
        for idx, kra in enumerate(original_kras, 1):
            kra_item = {
                "doctype": "Appraisal KRA",
                "idx": idx,
                "kra": kra["key_result_area"],
                "per_weightage": kra["weightage"],
                "goal_completion": kra["per_goal_completion"],
                "goal_score": kra["goal_score"],
                "parentfield": "appraisal_kra",
                "parenttype": "Appraisal",
            }
            appraisal_kra.append(kra_item)

        # Calculate total score
        total_score = sum(kra["goal_score"] for kra in original_kras)

        # Generate reflections
        reflection = generate_reflection()

        # Generate appraisal document
        appraisal = {
            "doctype": "Appraisal",
            "employee": employee["name"],
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
            "company": employee.get("company", ""),
            "appraisal_cycle": cycle["name"],
            "status": "Completed",
            "kra": original_kras,
            "appraisal_kra": appraisal_kra,
            "self_appraisal": generate_self_appraisal(),
            "reflections": reflection,
            "total_score": total_score,
        }

    return appraisal


async def insert_performance_cycles():
    """Insert performance cycles into Frappe."""
    client = frappe_client.create_client()

    company = companies.get_default_company()
    company_name = company["name"]

    # Generate performance cycles
    cycle_docs = generate_performance_cycles(company_name)

    # Insert cycles one by one
    for cycle in cycle_docs:
        # Remove docstatus for initial insert
        cycle_name = cycle["cycle_name"]

        try:
            # Insert with default docstatus (0)
            client.insert(cycle)
            logger.info(f"Successfully added appraisal cycle {cycle_name}")

        except Exception as e:
            logger.error(f"Failed to add appraisal cycle {cycle_name}: {e!s}")

    return cycle_docs


async def update_cycle_statuses():
    """Update cycle statuses based on their dates.
    - Past cycles: Completed
    - Current cycle: In Progress
    - Future cycles: Not Started
    """
    client = frappe_client.create_client()

    company = companies.get_default_company()
    company_name = company["name"]
    current_date = datetime.now().date()

    # Get all appraisal cycles
    cycles = client.get_list(
        "Appraisal Cycle",
        limit_page_length=10,
        fields=["name", "start_date", "end_date"],
        filters=[["company", "=", company_name]],
    )

    if not cycles:
        logger.error("No appraisal cycles found")
        return

    # Update status for each cycle
    for cycle in cycles:
        try:
            start_date = datetime.strptime(cycle["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(cycle["end_date"], "%Y-%m-%d").date()

            # Determine cycle status based on date
            if end_date < current_date:
                status = "Completed"
                docstatus = 1
            elif start_date <= current_date <= end_date:
                status = "In Progress"
                docstatus = 0
            else:
                status = "Not Started"
                docstatus = 0

            # Update cycle status and docstatus
            client.update(
                {
                    "doctype": "Appraisal Cycle",
                    "name": cycle["name"],
                    "status": status,
                    "docstatus": docstatus,
                }
            )

            logger.info(f"Updated cycle {cycle['name']} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update status for cycle {cycle['name']}: {e!s}")


async def insert_appraisals(count=30):
    """Generate and insert employee appraisals."""
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]
    current_date = datetime.now().date()

    # Get all active employees
    employees = client.get_list(
        "Employee",
        limit_page_length=100,
        fields=["name", "first_name", "last_name", "company"],
        filters=[["status", "=", "Active"], ["company", "=", company_name]],
    )

    if not employees:
        logger.error("No active employees found")
        return

    logger.info(f"Found {len(employees)} active employees")

    # Get all appraisal cycles with full details
    cycles = client.get_list(
        "Appraisal Cycle",
        limit_page_length=10,
        fields=["name", "start_date", "end_date"],
        filters=[["company", "=", company_name]],
    )

    if not cycles:
        logger.error("No appraisal cycles found. Please run insert_performance_cycles() first.")
        return

    logger.info(f"Found {len(cycles)} appraisal cycles")

    # Get appraisal templates
    appraisal_templates = client.get_list("Appraisal Template", limit_page_length=settings.LIST_LIMIT)

    # Get detailed template information
    detailed_appraisal_templates = []
    if appraisal_templates:
        for appraisal_template in appraisal_templates:
            try:
                doc = client.get_doc("Appraisal Template", appraisal_template["name"])
                detailed_appraisal_templates.append(doc)
            except Exception as e:
                logger.error(f"Failed to get template {appraisal_template['name']}: {e!s}")

    # Filter cycles to only include past quarters and current quarter
    valid_cycles = []
    for cycle in cycles:
        cycle_end_date = datetime.strptime(cycle["end_date"], "%Y-%m-%d").date()
        cycle_start_date = datetime.strptime(cycle["start_date"], "%Y-%m-%d").date()

        # Include if cycle is in the past or current quarter
        if cycle_end_date <= current_date or (cycle_start_date <= current_date <= cycle_end_date):
            valid_cycles.append(cycle)

    if not valid_cycles:
        logger.error("No valid cycles found (past or current quarters)")
        return

    logger.info(f"Found {len(valid_cycles)} valid cycles (past and current quarters)")

    # Random selection of employees and cycles
    selected_employees = random.sample(employees, min(count, len(employees)))

    # Generate and insert appraisals
    for employee in selected_employees:
        # Get full employee doc
        employee_doc = client.get_doc("Employee", employee["name"])

        # Select a random cycle from valid cycles
        cycle = random.choice(valid_cycles)

        # Generate appraisal with templates if available
        appraisal = generate_appraisal(employee_doc, cycle, detailed_appraisal_templates)

        try:
            # Insert with default docstatus (0)
            result = client.insert(appraisal)
            logger.info(f"Successfully added appraisal for {employee['name']} in cycle {cycle['name']}")

            # Check if cycle is current or past
            cycle_end_date = datetime.strptime(cycle["end_date"], "%Y-%m-%d").date()
            if cycle_end_date <= current_date:
                # Update docstatus to 1 for completed cycles
                client.update({"doctype": "Appraisal", "name": result.get("name"), "docstatus": 1})
                logger.info(f"Updated docstatus to 1 for appraisal {result.get('name')}")

        except Exception as e:
            logger.error(f"Failed to add appraisal for {employee['name']}: {e!s}")

    # Update cycle statuses after all appraisals are inserted
    await update_cycle_statuses()


async def delete_all_appraisals():
    """Delete all appraisals and cycles."""
    client = frappe_client.create_client()
    # Delete appraisals
    appraisals = client.get_list("Appraisal", limit_page_length=settings.LIST_LIMIT)
    for appraisal in appraisals:
        try:
            if appraisal["docstatus"] == 1:
                updated_appraisal = {
                    "doctype": "Appraisal",
                    "name": appraisal["name"],
                    "docstatus": 2,
                }
                client.update(updated_appraisal)

            client.delete("Appraisal", appraisal["name"])
        except Exception as e:
            logger.error(f"Failed to delete appraisal {appraisal['name']}: {e!s}")


async def delete_all_cycles():
    """Delete all cycles."""
    client = frappe_client.create_client()
    cycles = client.get_list("Appraisal Cycle", limit_page_length=1000)
    for cycle in cycles:
        try:
            client.delete("Appraisal Cycle", cycle["name"])
            logger.info(f"Deleted cycle {cycle['name']}")
        except Exception as e:
            logger.error(f"Failed to delete cycle {cycle['name']}: {e!s}")


async def generate_feedback_content(employee_name: str, designation: str, reviewer_name: str, reviewer_designation: str) -> str:
    """Generate feedback content using cached data or OpenAI GPT-4o-mini as fallback."""

    # Define the path to the feedback content JSON file
    feedback_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "feedback_content.json")

    # Create designation pair key for caching
    designation_pair_key = f"{designation}|{reviewer_designation}"

    # Check if cached feedback content exists
    if feedback_file_path.exists():
        try:
            with feedback_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                cached_feedback_content = data.get("feedback_templates", {})

                # Check if we have cached feedback content for this designation pair
                if designation_pair_key in cached_feedback_content:
                    feedback_content = cached_feedback_content[designation_pair_key]
                    logger.info(f"Using cached feedback content for pair: {designation_pair_key}")

                    # Personalize the feedback content with actual names
                    personalized_feedback = feedback_content.replace("{{employee_name}}", employee_name)
                    personalized_feedback = personalized_feedback.replace("{{reviewer_name}}", reviewer_name)
                    personalized_feedback = personalized_feedback.replace("{{employee_designation}}", designation)
                    personalized_feedback = personalized_feedback.replace("{{reviewer_designation}}", reviewer_designation)

                    return personalized_feedback

        except Exception as e:
            logger.error(f"Failed to read cached feedback content: {e!s}")

    # If no cached content found, try to generate using OpenAI (with error handling)
    logger.info(f"No cached content found for pair: {designation_pair_key}, attempting GPT generation")

    try:
        prompt = f"""Generate a professional performance feedback for {employee_name}, a {designation}, 
        written by {reviewer_name}, who is a {reviewer_designation}. 
        
        The feedback should be in HTML format with the following structure:
        - A brief introduction mentioning the reviewer's perspective
        - 2-3 key strengths
        - 1-2 areas for improvement
        - A constructive conclusion
        
        Format the response in HTML using <div class="ql-editor read-mode"> tags and proper HTML formatting, but don't include ```html```"""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional HR manager writing performance feedback.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        feedback_html = response.choices[0].message.content
        logger.info(f"Successfully generated feedback content using GPT for pair: {designation_pair_key}")

        # Save the generated content to cache for future use
        try:
            # Ensure the directory exists
            feedback_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing cache or create new
            cached_data = {}
            if feedback_file_path.exists():
                with feedback_file_path.open(encoding="utf-8") as f:
                    cached_data = json.load(f)

            # Create template version with placeholders
            template_feedback = feedback_html.replace(employee_name, "{{employee_name}}")
            template_feedback = template_feedback.replace(reviewer_name, "{{reviewer_name}}")
            template_feedback = template_feedback.replace(designation, "{{employee_designation}}")
            template_feedback = template_feedback.replace(reviewer_designation, "{{reviewer_designation}}")

            # Update cache
            if "feedback_templates" not in cached_data:
                cached_data["feedback_templates"] = {}

            cached_data["feedback_templates"][designation_pair_key] = template_feedback
            cached_data["last_updated"] = datetime.now().isoformat()

            # Save to file
            with feedback_file_path.open("w", encoding="utf-8") as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved new feedback template for designation pair: {designation_pair_key}")

        except Exception as cache_error:
            logger.error(f"Failed to save generated feedback to cache: {cache_error!s}")

        return feedback_html

    except Exception as e:
        logger.error(f"Failed to generate feedback content with GPT: {e!s}")
        # Fallback to template-based feedback if OpenAI fails
        logger.info(f"Using fallback template for pair: {designation_pair_key}")

        fallback_content = f"""
        <div class="ql-editor read-mode">
            <p>As {reviewer_designation}, I have had the opportunity to work closely with {employee_name} and observe their performance as a {designation}.</p>
            <p>Key strengths include:</p>
            <p>
                <p>Strong technical skills and problem-solving abilities</p>
                <p>Effective communication with team members</p>
                <p>Consistent delivery of quality work</p>
            </p>
            <p>Areas for improvement:</p>
            <p>
                <p>Could benefit from more proactive leadership in team projects</p>
                <p>Opportunity to enhance cross-functional collaboration</p>
            </p>
            <p>Overall, {employee_name} is a valuable team member who continues to show growth and potential.</p>
        </div>
        """

        return fallback_content


async def create_feedback(
    employee: dict[str, Any],
    reviewer: dict[str, Any],
    appraisal: dict[str, Any],
    company_name: str,
) -> dict[str, Any]:
    """Create a single feedback document."""

    client = frappe_client.create_client()
    try:
        # Generate feedback content using OpenAI
        feedback_content = await generate_feedback_content(
            employee["employee_name"],
            employee["designation"],
            reviewer["employee_name"],
            reviewer["designation"],
        )

        # Set 80% of feedbacks to completed status (docstatus=1)
        docstatus = 1 if random.random() < 0.8 else 0

        feedback = {
            "doctype": "Employee Performance Feedback",
            "employee": employee["name"],
            "employee_name": employee["employee_name"],
            "department": employee["department"],
            "designation": employee["designation"],
            "company": company_name,
            "reviewer": reviewer["name"],
            "reviewer_name": reviewer["employee_name"],
            "reviewer_designation": reviewer["designation"],
            "user": reviewer["user_id"],
            "added_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "appraisal_cycle": appraisal["appraisal_cycle"],
            "appraisal": appraisal["name"],
            "total_score": round(random.uniform(3.0, 5.0), 1),
            "feedback": feedback_content,
            "docstatus": docstatus,
        }

        # Insert feedback (synchronous operation)
        result = client.insert(feedback)
        logger.info(f"Successfully added feedback for employee {feedback['employee_name']} with docstatus {docstatus}, result: {result}")
        return feedback
    except Exception as e:
        logger.error(f"Failed to create feedback for employee {employee['employee_name']}: {e!s}")
        return None


async def insert_feedbacks(number_of_feedbacks=50):
    """Generate and insert employee performance feedbacks."""
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    # Define the path to the feedback content JSON file
    feedback_file_path = Path("data/generated/feedback_content.json")

    # Ensure the directory exists
    feedback_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if cached feedback content exists
    cached_feedback_content = {}
    if feedback_file_path.exists():
        logger.info("Found existing feedback_content.json file, loading data from it")
        try:
            with feedback_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_company = data.get("company_name", "")

                # Use stored data if it's for the same company
                if stored_company == company_name:
                    cached_feedback_content = data.get("feedback_templates", {})
                    logger.info(f"Loaded cached feedback content for {len(cached_feedback_content)} designation pairs")
                else:
                    logger.info("Stored data is for different company, will generate new data")
        except Exception as e:
            logger.error(f"Failed to read feedback_content.json: {e!s}")
            logger.info("Falling back to GPT generation")
    else:
        logger.info("feedback_content.json file not found, will generate new feedback content")

    # Get all active employees (synchronous operation)
    employees = client.get_list(
        "Employee",
        limit_page_length=100,
        fields=[
            "name",
            "employee_name",
            "department",
            "designation",
            "company",
            "user_id",
        ],
        filters=[["status", "=", "Active"], ["company", "=", company_name]],
    )

    if not employees:
        logger.error("No active employees found")
        return

    logger.info(f"Found {len(employees)} active employees")

    # Get all appraisal cycles that are not completed (synchronous operation)
    cycles = client.get_list(
        "Appraisal Cycle",
        limit_page_length=10,
        fields=["name", "start_date", "end_date", "status"],
        filters=[["company", "=", company_name], ["status", "!=", "Completed"]],
    )

    if not cycles:
        logger.error("No non-completed appraisal cycles found")
        return

    logger.info(f"Found {len(cycles)} non-completed appraisal cycles")

    # Get cycle names for filtering appraisals
    valid_cycle_names = [cycle["name"] for cycle in cycles]

    # Get all appraisals that belong to non-completed cycles (synchronous operation)
    appraisals = client.get_list(
        "Appraisal",
        limit_page_length=100,
        fields=["name", "employee", "appraisal_cycle"],
        filters=[
            ["company", "=", company_name],
            ["appraisal_cycle", "in", valid_cycle_names],
        ],
    )

    if not appraisals:
        logger.error("No appraisals found for non-completed cycles")
        return

    logger.info(f"Found {len(appraisals)} appraisals for non-completed cycles")

    new_feedback_content = {}
    successful_feedbacks = []

    # Generate feedbacks
    for _ in range(number_of_feedbacks):
        # Select random employee and their appraisal
        employee = random.choice(employees)
        employee_appraisals = [a for a in appraisals if a["employee"] == employee["name"]]

        if not employee_appraisals:
            continue

        appraisal = random.choice(employee_appraisals)

        # Find a reviewer (another employee from the same department)
        potential_reviewers = [e for e in employees if e["name"] != employee["name"] and e["department"] == employee["department"]]

        if not potential_reviewers:
            continue

        reviewer = random.choice(potential_reviewers)

        # Create designation pair key for caching
        designation_pair_key = f"{employee['designation']}|{reviewer['designation']}"

        # Check if we have cached feedback content for this designation pair
        if designation_pair_key in cached_feedback_content:
            feedback_content = cached_feedback_content[designation_pair_key]
            logger.info(f"Using cached feedback content for pair: {designation_pair_key}")
        else:
            # Generate new feedback content using GPT
            logger.info(f"Generating new feedback content for pair: {designation_pair_key}")
            try:
                prompt = f"""Generate a professional performance feedback for an employee with designation {employee["designation"]}, 
                written by a reviewer with designation {reviewer["designation"]}. 
                
                The feedback should be in HTML format with the following structure:
                - A brief introduction mentioning the reviewer's perspective
                - 2-3 key strengths
                - 1-2 areas for improvement
                - A constructive conclusion
                
                Format the response in HTML using <div class="ql-editor read-mode"> tags and proper HTML formatting, but don't include ```html```
                
                Use placeholder {{employee_name}} for the employee name and {{reviewer_name}} for the reviewer name."""

                response = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional HR manager writing performance feedback templates that can be reused for similar role combinations.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=500,
                )

                feedback_content = response.choices[0].message.content

                # Store new feedback content for caching
                new_feedback_content[designation_pair_key] = feedback_content

            except Exception as e:
                logger.error(f"Failed to generate feedback content: {e!s}")
                # Fallback to template-based feedback if OpenAI fails
                feedback_content = """
                <div class="ql-editor read-mode">
                    <p>As {{reviewer_designation}}, I have had the opportunity to work closely with {{employee_name}} and observe their performance as a {{employee_designation}}.</p>
                    <p>Key strengths include:</p>
                    <p>
                        <p>Strong technical skills and problem-solving abilities</p>
                        <p>Effective communication with team members</p>
                        <p>Consistent delivery of quality work</p>
                    </p>
                    <p>Areas for improvement:</p>
                    <p>
                        <p>Could benefit from more proactive leadership in team projects</p>
                        <p>Opportunity to enhance cross-functional collaboration</p>
                    </p>
                    <p>Overall, {{employee_name}} is a valuable team member who continues to show growth and potential.</p>
                </div>
                """
                new_feedback_content[designation_pair_key] = feedback_content

        # Personalize the feedback content with actual names
        personalized_feedback = feedback_content.replace("{{employee_name}}", employee["employee_name"])
        personalized_feedback = personalized_feedback.replace("{{reviewer_name}}", reviewer["employee_name"])
        personalized_feedback = personalized_feedback.replace("{{employee_designation}}", employee["designation"])
        personalized_feedback = personalized_feedback.replace("{{reviewer_designation}}", reviewer["designation"])

        # Set 80% of feedbacks to completed status (docstatus=1)
        docstatus = 1 if random.random() < 0.8 else 0

        feedback = {
            "doctype": "Employee Performance Feedback",
            "employee": employee["name"],
            "employee_name": employee["employee_name"],
            "department": employee["department"],
            "designation": employee["designation"],
            "company": company_name,
            "reviewer": reviewer["name"],
            "reviewer_name": reviewer["employee_name"],
            "reviewer_designation": reviewer["designation"],
            "user": reviewer["user_id"],
            "added_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "appraisal_cycle": appraisal["appraisal_cycle"],
            "appraisal": appraisal["name"],
            "total_score": round(random.uniform(3.0, 5.0), 1),
            "feedback": personalized_feedback,
            "docstatus": docstatus,
        }

        try:
            # Insert feedback (synchronous operation)
            result = client.insert(feedback)
            logger.info(f"Successfully added feedback for employee {feedback['employee_name']} with docstatus {docstatus}, result: {result}")
            successful_feedbacks.append(feedback)
        except Exception as e:
            logger.error(f"Failed to create feedback for employee {employee['employee_name']}: {e!s}")

    # Save new feedback content to cache file (merge with existing data)
    if new_feedback_content or cached_feedback_content:
        all_feedback_content = {**cached_feedback_content, **new_feedback_content}
        feedback_cache_data = {
            "feedback_templates": all_feedback_content,
            "company_name": company_name,
            "theme_subject": settings.DATA_THEME_SUBJECT,
            "last_updated": datetime.now().isoformat(),
            "total_cached_pairs": len(all_feedback_content),
        }

        try:
            with feedback_file_path.open("w", encoding="utf-8") as f:
                json.dump(feedback_cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved feedback content for {len(all_feedback_content)} designation pairs to {feedback_file_path}")
        except Exception as e:
            logger.error(f"Failed to save feedback content to file: {e!s}")

    logger.info(f"Successfully created {len(successful_feedbacks)} feedbacks out of {number_of_feedbacks} requested")
    return successful_feedbacks


async def delete_all_feedbacks():
    """Delete all feedbacks."""
    client = frappe_client.create_client()
    feedbacks = client.get_list("Employee Performance Feedback", limit_page_length=settings.LIST_LIMIT)
    for feedback in feedbacks:
        try:
            if feedback["docstatus"] == 1:
                client.update(
                    {
                        "doctype": "Employee Performance Feedback",
                        "name": feedback["name"],
                        "docstatus": 2,
                    }
                )
            client.delete("Employee Performance Feedback", feedback["name"])
            logger.info(f"Deleted feedback {feedback['name']}")
        except Exception as e:
            logger.error(f"Failed to delete feedback {feedback['name']}: {e!s}")


class KRA(BaseModel):
    key_result_area: str = Field(..., description="Name of the Key Result Area")
    per_weightage: int = Field(..., description="Percentage weightage of this KRA (0-100)")


class RatingCriterion(BaseModel):
    criteria: str = Field(..., description="Rating criterion description")
    per_weightage: int = Field(..., description="Percentage weightage (weights should sum to 100%)")


class AppraisalTemplate(BaseModel):
    title: str = Field(..., description="Title of the appraisal template")
    description: str = Field(..., description="Description of the template purpose")
    kras: list[KRA] = Field(..., description="List of Key Result Areas with their weightages")
    rating_criteria: list[RatingCriterion] = Field(..., description="List of rating criteria with weights that sum to 100%")


class AppraisalTemplateList(BaseModel):
    templates: list[AppraisalTemplate] = Field(..., description="List of appraisal templates")


async def insert_appraisal_templates(count=3):
    """Insert multiple appraisal templates with AI-generated content using Pydantic models."""
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    # Define the path to the appraisal templates JSON file
    templates_file_path = Path("data/generated/appraisal_templates.json")

    # Ensure the directory exists
    templates_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if cached template data exists
    cached_templates = []
    if templates_file_path.exists():
        logger.info("Found existing appraisal_templates.json file, loading data from it")
        try:
            with templates_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_company = data.get("company_name", "")
                stored_count = data.get("template_count", 0)

                # Use stored data if it's for the same company and meets the required count
                if stored_company == company_name and stored_count >= count:
                    cached_templates = data.get("templates", [])[:count]
                    logger.info(f"Using cached data: {len(cached_templates)} templates for company {company_name}")
                else:
                    logger.info("Stored data insufficient or for different company, will generate new data")
        except Exception as e:
            logger.error(f"Failed to read appraisal_templates.json: {e!s}")
            logger.info("Falling back to GPT generation")
    else:
        logger.info("appraisal_templates.json file not found, will generate new template data")

    templates_created = 0
    generated_templates = []

    if cached_templates:
        # Use cached templates
        logger.info(f"Using {len(cached_templates)} cached appraisal templates")

        for template_data in cached_templates:
            # First create the KRAs
            for kra_data in template_data.get("kras", []):
                try:
                    client.insert({"doctype": "KRA", "title": kra_data["key_result_area"]})
                    logger.info(f"Created KRA: {kra_data['key_result_area']}")
                except Exception as e:
                    logger.error(f"Failed to create KRA: {kra_data['key_result_area']}: {e!s}")

            # Create the rating criteria
            for criterion_data in template_data.get("rating_criteria", []):
                try:
                    client.insert(
                        {
                            "doctype": "Employee Feedback Criteria",
                            "criteria": criterion_data["criteria"],
                        }
                    )
                    logger.info(f"Created rating criterion: {criterion_data['criteria']}")
                except Exception as e:
                    logger.error(f"Failed to create rating criterion: {criterion_data['criteria']}: {e!s}")

            # Then create the template
            template_doc = {
                "doctype": "Appraisal Template",
                "template_title": template_data["title"],
                "description": template_data["description"],
                "goals": [
                    {
                        "doctype": "Appraisal Template Goal",
                        "key_result_area": kra["key_result_area"],
                        "per_weightage": kra["per_weightage"],
                        "parentfield": "goals",
                        "parenttype": "Appraisal Template",
                    }
                    for kra in template_data["kras"]
                ],
                "rating_criteria": [
                    {
                        "doctype": "Employee Feedback Rating",
                        "criteria": criterion["criteria"],
                        "per_weightage": criterion["per_weightage"],
                        "parentfield": "rating_criteria",
                        "parenttype": "Appraisal Template",
                        "rating": 0,
                    }
                    for criterion in template_data["rating_criteria"]
                ],
            }

            try:
                result = client.insert(template_doc)
                logger.info(f"Created appraisal template from cache: {template_doc['template_title']}")
                templates_created += 1
            except Exception as e:
                logger.error(f"Failed to create appraisal template '{template_doc['template_title']}': {e!s}")
    else:
        # Generate new templates using GPT
        logger.info(f"Generating {count} new appraisal templates using GPT")

        try:
            # Generate template data using OpenAI with Pydantic parsing
            response = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an HR professional creating performance appraisal templates.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate {count} unique performance appraisal templates for a {settings.DATA_THEME_SUBJECT}.
                        
                        Each template should include:
                        1. A clear title (e.g., 'Engineering Performance Review', 'Sales Team Evaluation')
                        2. A brief description of the template purpose
                        3. 3-5 Key Result Areas (KRAs) with weightages that sum to 100%
                        4. 3-5 Rating criteria used to evaluate performance, each with:
                           - A descriptive criterion (e.g., "Quality of Work", "Communication Skills")
                           - A percentage weightage value
                           
                        IMPORTANT: For each template, the sum of all rating criteria weightages must equal exactly 100%.
                        """,
                    },
                ],
                response_format=AppraisalTemplateList,
            )

            template_list = response.choices[0].message.parsed

            # Insert each template
            for template in template_list.templates:
                # Store template data for caching
                template_data = {
                    "title": template.title,
                    "description": template.description,
                    "kras": [
                        {
                            "key_result_area": kra.key_result_area,
                            "per_weightage": kra.per_weightage,
                        }
                        for kra in template.kras
                    ],
                    "rating_criteria": [
                        {
                            "criteria": criterion.criteria,
                            "per_weightage": criterion.per_weightage,
                        }
                        for criterion in template.rating_criteria
                    ],
                }
                generated_templates.append(template_data)

                # First create the KRAs
                for kra in template.kras:
                    try:
                        client.insert({"doctype": "KRA", "title": kra.key_result_area})
                        logger.info(f"Created KRA: {kra.key_result_area}")
                    except Exception as e:
                        logger.error(f"Failed to create KRA: {kra.key_result_area}: {e!s}")

                # Create the rating criteria
                for criterion in template.rating_criteria:
                    try:
                        client.insert(
                            {
                                "doctype": "Employee Feedback Criteria",
                                "criteria": criterion.criteria,
                            }
                        )
                        logger.info(f"Created rating criterion: {criterion.criteria}")
                    except Exception as e:
                        logger.error(f"Failed to create rating criterion: {criterion.criteria}: {e!s}")

                # Then create the template
                template_doc = {
                    "doctype": "Appraisal Template",
                    "template_title": template.title,
                    "description": template.description,
                    "goals": [
                        {
                            "doctype": "Appraisal Template Goal",
                            "key_result_area": kra.key_result_area,
                            "per_weightage": kra.per_weightage,
                            "parentfield": "goals",
                            "parenttype": "Appraisal Template",
                        }
                        for kra in template.kras
                    ],
                    "rating_criteria": [
                        {
                            "doctype": "Employee Feedback Rating",
                            "criteria": criterion.criteria,
                            "per_weightage": criterion.per_weightage,
                            "parentfield": "rating_criteria",
                            "parenttype": "Appraisal Template",
                            "rating": 0,
                        }
                        for criterion in template.rating_criteria
                    ],
                }

                try:
                    result = client.insert(template_doc)
                    logger.info(f"Created appraisal template: {template_doc['template_title']}")
                    templates_created += 1
                except Exception as e:
                    logger.error(f"Failed to create appraisal template '{template_doc['template_title']}': {e!s}")

        except Exception as e:
            logger.error(f"Failed to generate appraisal templates with OpenAI: {e!s}")

            # Fallback to creating a simple template if OpenAI fails
            fallback_template_data = {
                "title": f"Standard Template {fake.random_letter()}{fake.random_letter()}",
                "description": "Standard performance evaluation template",
                "kras": [
                    {"key_result_area": "Performance Efficiency", "per_weightage": 40},
                    {"key_result_area": "Quality of Work", "per_weightage": 30},
                    {"key_result_area": "Team Collaboration", "per_weightage": 30},
                ],
                "rating_criteria": [
                    {"criteria": "Technical Knowledge", "per_weightage": 35},
                    {"criteria": "Communication Skills", "per_weightage": 25},
                    {"criteria": "Team Collaboration", "per_weightage": 25},
                    {"criteria": "Initiative & Innovation", "per_weightage": 15},
                ],
            }

            generated_templates.append(fallback_template_data)

            template_doc = {
                "doctype": "Appraisal Template",
                "template_title": fallback_template_data["title"],
                "description": fallback_template_data["description"],
                "goals": [
                    {
                        "doctype": "Appraisal Template Goal",
                        "key_result_area": "Performance Efficiency",
                        "per_weightage": 40,
                        "parentfield": "goals",
                        "parenttype": "Appraisal Template",
                    },
                    {
                        "doctype": "Appraisal Template Goal",
                        "key_result_area": "Quality of Work",
                        "per_weightage": 30,
                        "parentfield": "goals",
                        "parenttype": "Appraisal Template",
                    },
                    {
                        "doctype": "Appraisal Template Goal",
                        "key_result_area": "Team Collaboration",
                        "per_weightage": 30,
                        "parentfield": "goals",
                        "parenttype": "Appraisal Template",
                    },
                ],
                "rating_criteria": [
                    {
                        "doctype": "Employee Feedback Rating",
                        "criteria": "Technical Knowledge",
                        "per_weightage": 35,
                        "parentfield": "rating_criteria",
                        "parenttype": "Appraisal Template",
                        "rating": 0,
                    },
                    {
                        "doctype": "Employee Feedback Rating",
                        "criteria": "Communication Skills",
                        "per_weightage": 25,
                        "parentfield": "rating_criteria",
                        "parenttype": "Appraisal Template",
                        "rating": 0,
                    },
                    {
                        "doctype": "Employee Feedback Rating",
                        "criteria": "Team Collaboration",
                        "per_weightage": 25,
                        "parentfield": "rating_criteria",
                        "parenttype": "Appraisal Template",
                        "rating": 0,
                    },
                    {
                        "doctype": "Employee Feedback Rating",
                        "criteria": "Initiative & Innovation",
                        "per_weightage": 15,
                        "parentfield": "rating_criteria",
                        "parenttype": "Appraisal Template",
                        "rating": 0,
                    },
                ],
            }

            try:
                result = client.insert(template_doc)
                logger.info(f"Created fallback appraisal template: {template_doc['template_title']}, result: {result}")
                templates_created += 1
            except Exception as e:
                logger.error(f"Failed to create fallback appraisal template: {e!s}")

        # Save generated templates to cache file
        if generated_templates:
            templates_cache_data = {
                "templates": generated_templates,
                "company_name": company_name,
                "template_count": len(generated_templates),
                "theme_subject": settings.DATA_THEME_SUBJECT,
                "last_updated": datetime.now().isoformat(),
                "generation_context": f"Generated {len(generated_templates)} appraisal templates using GPT-4o-mini",
            }

            try:
                with templates_file_path.open("w", encoding="utf-8") as f:
                    json.dump(templates_cache_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(generated_templates)} appraisal templates to {templates_file_path}")
            except Exception as e:
                logger.error(f"Failed to save appraisal templates to file: {e!s}")

    logger.info(f"Successfully created {templates_created} appraisal templates")
    return templates_created


async def update_employee_kras():
    """Update the KRAs for all employees."""
    # Get appraisal templates
    client = frappe_client.create_client()
    appraisal_templates = client.get_list("Appraisal Template", limit_page_length=settings.LIST_LIMIT)

    # Get detailed template information
    detailed_appraisal_templates = []
    for appraisal_template in appraisal_templates:
        doc = client.get_doc("Appraisal Template", appraisal_template["name"])
        detailed_appraisal_templates.append(doc)

    # Get all appraisals that are not submitted
    appraisals = client.get_list(
        "Appraisal",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "employee", "appraisal_cycle"],
        filters=[["docstatus", "=", 0]],
    )

    if not appraisals:
        logger.error("No appraisals found to update")
        return

    if not detailed_appraisal_templates:
        logger.error("No appraisal templates found")
        return

    # For each appraisal, assign a template and update with KRAs
    for appraisal in appraisals:
        try:
            # Get full appraisal doc
            # appraisal_doc = client.get_doc("Appraisal", appraisal["name"])

            # Select a random template
            template = random.choice(detailed_appraisal_templates)

            # Prepare KRAs from template goals
            appraisal_kra = []
            total_weightage = 0
            for idx, goal in enumerate(template["goals"], 1):
                goal_completion = random.randint(70, 100)
                per_weightage = float(goal["per_weightage"])
                total_weightage += per_weightage
                goal_score = round((per_weightage * goal_completion) / 100)

                kra = {
                    "doctype": "Appraisal KRA",
                    "idx": idx,
                    "kra": goal["key_result_area"],
                    "per_weightage": per_weightage,
                    "goal_completion": goal_completion,
                    "goal_score": goal_score,
                    "parentfield": "appraisal_kra",
                    "parenttype": "Appraisal",
                }
                appraisal_kra.append(kra)

            # Adjust weightages if needed to ensure they sum to 100%
            if total_weightage != 100:
                # Simple normalization and rounding
                factor = 100 / total_weightage
                for kra in appraisal_kra:
                    kra["per_weightage"] = round(kra["per_weightage"] * factor)

                # Handle any rounding errors to ensure total is exactly 100
                total_after_adjustment = sum(kra["per_weightage"] for kra in appraisal_kra)
                if total_after_adjustment != 100 and appraisal_kra:
                    # Add/subtract the difference from the first KRA
                    appraisal_kra[0]["per_weightage"] += 100 - total_after_adjustment

            # Prepare self ratings from template rating criteria
            self_ratings = []
            for idx, criterion in enumerate(template["rating_criteria"], 1):
                rating = {
                    "doctype": "Employee Feedback Rating",
                    "idx": idx,
                    "criteria": criterion["criteria"],
                    "per_weightage": criterion["per_weightage"],
                    "rating": round(random.uniform(0.7, 1.0), 1),  # Random rating between 0.7 and 1.0
                    "parentfield": "self_ratings",
                    "parenttype": "Appraisal",
                }
                self_ratings.append(rating)

            # Generate reflection
            reflection = generate_reflection()

            # Update appraisal with new KRAs and ratings
            update_data = {
                "doctype": "Appraisal",
                "name": appraisal["name"],
                "appraisal_template": template["name"],
                "appraisal_kra": appraisal_kra,
                "self_ratings": self_ratings,
                "reflections": reflection,
            }

            # Update the appraisal
            client.update(update_data)

            logger.info(f"Updated KRAs for appraisal {appraisal['name']} with template {template['name']}")

        except Exception as e:
            logger.error(f"Failed to update KRAs for appraisal {appraisal['name']}: {e!s}")

    logger.info(f"Updated KRAs for {len(appraisals)} appraisals")


# async def update_appraisal_cycle_statuses():
#     """Update the status of appraisal cycles based on their dates."""
#     client = frappe_client.create_client()
#     company = companies.get_default_company()
#     company_name = company

#     # Get all appraisal cycles
#     cycles = client.get_list(
#         "Appraisal Cycle",
#         limit_page_length=10,
#         fields=["name", "start_date", "end_date"],
#         filters=[["company", "=", company_name]],
#     )
