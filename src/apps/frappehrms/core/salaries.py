import calendar
import json
import logging
import random
import time
from datetime import date, datetime
from pathlib import Path

from faker import Faker

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core.companies import get_default_company
from apps.frappehrms.utils import frappe_client


logger = logging.getLogger(__name__)


fake = Faker()


async def insert_salary_components():
    """
    Insert salary components into Frappe.
    """
    client = frappe_client.create_client()
    try:
        json_path = Path(__file__).parent.parent.joinpath("data", "salaries.json")
        # Load the salary data from the JSON file
        with json_path.open(encoding="utf-8") as file:
            data = json.load(file)

        components = data.get("components", [])
        company = get_default_company()
        # Prepare documents for insertion
        docs = [
            {
                "doctype": "Salary Component",
                "salary_component": c["name"],
                "salary_component_abbr": c["abbreviation"],
                "type": c["type"],
                "is_tax_applicable": c["is_taxable"],
                "include_in_gross": c["include_in_gross"],
                "payment_account": "Salary - AC",
                "disabled": not c["is_active"],
                "depends_on_payment_days": 0,
                "accounts": [
                    {
                        "doctype": "Salary Component Account",
                        "company": company["name"],
                        "parent": c["name"],
                        "parentfield": "accounts",
                        "parenttype": "Salary Component",
                        "account": f"Bank Account - {company['abbr']}",
                    }
                ],
            }
            for c in components
        ]

        # Insert salary components individually
        if docs:
            inserted_count = 0
            for doc in docs:
                try:
                    client.insert(doc)
                    inserted_count += 1
                except Exception as e:
                    logging.error(f"Error inserting salary component {doc['salary_component']}: {e!s}")
                    # Continue with the next component

            logging.info(f"Inserted {inserted_count} salary components")
            return inserted_count
        else:
            logging.warning("No salary components found")
            return None

    except Exception as e:
        logging.error(f"Error inserting salary components: {e!s}")
        raise


async def insert_salary_structures():
    """
    Insert salary structures into Frappe.
    """
    client = frappe_client.create_client()
    try:
        json_path = Path(__file__).parent.parent.joinpath("data", "salaries.json")
        with json_path.open(encoding="utf-8") as file:
            data = json.load(file)

        structures = data.get("structures", [])

        structures_inserted = 0
        details_inserted = 0

        company = get_default_company()
        company_name = company["name"]

        # Process each structure individually
        for structure in structures:
            # Prepare main salary structure document
            structure_doc = {
                "doctype": "Salary Structure",
                "name": structure["name"],
                "salary_structure": structure["name"],
                "docstatus": 1,  # Submitted
                "is_active": "Yes" if structure["is_active"] else "No",
                "payroll_frequency": structure["frequency"],
                "salary_slip_based_on_timesheet": 0,
                "payment_account": "Salary - AI",  # TODO: determine the correct account
                "description": structure["description"],
                "company": company_name,
            }

            try:
                # Insert the structure document
                logging.info(f"Inserting salary structure: {structure['name']}")
                client.insert(structure_doc)
                structures_inserted += 1

                # Insert earnings and deductions details for this structure
                for idx, earning in enumerate(structure.get("earnings", [])):
                    detail_doc = {
                        "doctype": "Salary Detail",
                        "parent": structure["name"],
                        "parentfield": "earnings",
                        "parenttype": "Salary Structure",
                        "idx": idx + 1,
                        "salary_component": earning["component"],
                        "abbr": earning["abbr"],
                        "amount_based_on_formula": earning["amount_based_on_formula"],
                        "formula": earning["formula"],
                        "amount": earning["amount"],
                    }
                    client.insert(detail_doc)
                    details_inserted += 1

                for idx, deduction in enumerate(structure.get("deductions", [])):
                    detail_doc = {
                        "doctype": "Salary Detail",
                        "parent": structure["name"],
                        "parentfield": "deductions",
                        "parenttype": "Salary Structure",
                        "idx": idx + 1,
                        "salary_component": deduction["component"],
                        "abbr": deduction["abbr"],
                        "amount_based_on_formula": deduction["amount_based_on_formula"],
                        "formula": deduction["formula"],
                        "amount": deduction["amount"],
                    }
                    client.insert(detail_doc)
                    details_inserted += 1

            except Exception as e:
                logging.error(f"Error inserting salary structure {structure['name']}: {e!s}")
                # Continue with the next structure

        return {
            "structures": structures_inserted,
            "details": details_inserted,
        }

    except Exception as e:
        logging.error(f"Error inserting salary structures: {e!s}")
        raise


def delete_salary_components():
    """
    Delete all existing salary components.
    """
    client = frappe_client.create_client()
    try:
        components = client.get_list("Salary Component", limit_page_length=settings.LIST_LIMIT)

        # Delete each component
        deleted_count = 0
        for component in components:
            client.delete("Salary Component", component["name"])
            logging.info(f"Deleted component {component['name']}")
            deleted_count += 1

        return deleted_count

    except Exception as e:
        logging.error(f"Error deleting salary components: {e!s}")
        raise


def delete_salary_structures():
    """
    Delete all existing salary structures.
    """
    client = frappe_client.create_client()
    structures = client.get_list("Salary Structure", limit_page_length=settings.LIST_LIMIT)
    updated_structures = [
        {
            "name": structure["name"],
            "docstatus": 2,
            "doctype": "Salary Structure",
        }
        for structure in structures
    ]

    for structure in updated_structures:
        try:
            client.update(structure)
            logging.info(f"Updated structure {structure['name']}")
        except Exception as e:
            logging.error(f"Error updating structure {structure['name']}: {e!s}")

    # Delete each structure
    deleted_count = 0
    for structure in structures:
        logging.info(f"Deleted structure {structure['name']}")
        client.delete("Salary Structure", structure["name"])
        deleted_count += 1

    return deleted_count


async def delete_salary_components_and_structures():
    """Delete all existing salary components and structures from Frappe."""
    await delete_salary_components()
    await delete_salary_structures()


async def insert_cost_centers():
    """Load cost centers from JSON file and insert them into Frappe."""
    client = frappe_client.create_client()
    try:
        # Load cost centers from JSON
        json_path = Path(__file__).parent.parent.joinpath("data", "salaries.json")
        with json_path.open(encoding="utf-8") as f:
            cost_centers = json.load(f).get("cost_centers", [])

        if not cost_centers:
            logging.warning("No cost centers found")
            return 0

        # Insert cost centers
        company = get_default_company()
        company_suffix = f" - {company['abbr']}"

        for cc in cost_centers:
            doc = {
                "doctype": "Cost Center",
                "cost_center_name": cc["name"],
                "parent_cost_center": (cc["parent_cost_center"] or company["name"]) + company_suffix,
                "company": company["name"],
                "is_group": 1,
            }

            try:
                client.insert(doc)
                logging.info(f"Inserted cost center: {cc['name']}")
            except Exception as e:
                logging.error(f"Error inserting cost center {cc['name']}: {e!s}")

    except Exception as e:
        logging.error(f"Error inserting cost centers: {e!s}")
        raise


async def delete_cost_centers():
    """Delete all cost centers from bottom to top in the hierarchy."""
    client = frappe_client.create_client()
    try:
        # Load cost centers from JSON to determine hierarchy
        json_path = Path(__file__).parent.parent.joinpath("data", "salaries.json")
        with json_path.open(encoding="utf-8") as f:
            cost_centers_data = json.load(f).get("cost_centers", [])

        if not cost_centers_data:
            logging.warning("No cost centers found in JSON")
            return 0

        # Create a mapping of parent to children
        parent_to_children = {}
        for cc in cost_centers_data:
            parent = cc.get("parent_cost_center")
            if parent not in parent_to_children:
                parent_to_children[parent] = []
            parent_to_children[parent].append(cc["name"])

        # Get all cost centers from Frappe
        cost_centers = client.get_list("Cost Center")

        if not cost_centers:
            logging.warning("No cost centers found in Frappe")
            return 0

        # Create a mapping of cost center names to their full names (with company suffix)
        cost_center_mapping = {cc["cost_center_name"]: cc["name"] for cc in cost_centers}

        # Function to delete cost centers in hierarchical order
        async def delete_children(parent_name):
            deleted = 0
            # Delete all children first
            children = parent_to_children.get(parent_name, [])
            for child in children:
                deleted += await delete_children(child)

            # Then delete this cost center if it exists in Frappe
            if parent_name in cost_center_mapping:
                try:
                    frappe_name = cost_center_mapping[parent_name]
                    client.delete("Cost Center", frappe_name)
                    logging.info(f"Deleted cost center: {parent_name} ({frappe_name})")
                    deleted += 1
                except Exception as e:
                    logging.error(f"Error deleting cost center {parent_name}: {e!s}")

            return deleted

        # Start deleting from the root (None parent) cost centers
        deleted_count = 0
        for cc_name in parent_to_children.get(None, []):
            deleted_count += await delete_children(cc_name)

        return deleted_count

    except Exception as e:
        logging.error(f"Error deleting cost centers: {e!s}")
        raise


async def insert_salary_structure_assignments():
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        fields=["employee", "designation", "company", "date_of_joining"],
        limit_page_length=settings.LIST_LIMIT,
    )
    salary_structures = client.get_list("Salary Structure", limit_page_length=settings.LIST_LIMIT)

    # Extract structure names and build a dictionary for quick lookup
    structure_names = {s["name"]: s["name"] for s in salary_structures}

    # Set default structure (used if no matching structure is found)
    default_structure = next(iter(structure_names.values())) if structure_names else "Entry-Level Staff"

    # Map keywords to structure categories
    structure_categories = {
        "senior": ["chief", "head", "ceo", "cfo", "cto", "coo", "director"],
        "manager": ["manager"],
        "sales": ["sales", "business development", "marketing"],
        "mid_level": ["consultant", "analyst", "engineer", "accountant", "developer"],
        "contractual": ["intern", "temporary", "contract", "part-time"],
        "entry": ["assistant", "associate", "representative", "clerk", "staff"],
    }

    for employee in employees:
        designation = employee.get("designation", "").lower()
        structure = None

        # Determine potential structure category based on keywords
        for category, keywords in structure_categories.items():
            if any(keyword in designation for keyword in keywords):
                if category == "senior" and any(s for s in structure_names if "senior" in s.lower() or "management" in s.lower()):
                    structure = next(
                        (s for s in structure_names if "senior" in s.lower() or "management" in s.lower()),
                        None,
                    )
                elif category == "manager" and any(s for s in structure_names if "management" in s.lower()):
                    structure = next((s for s in structure_names if "management" in s.lower()), None)
                elif category == "sales" and any(s for s in structure_names if "sales" in s.lower() or "target" in s.lower()):
                    structure = next(
                        (s for s in structure_names if "sales" in s.lower() or "target" in s.lower()),
                        None,
                    )
                elif category == "mid_level" and any(s for s in structure_names if "mid" in s.lower()):
                    structure = next((s for s in structure_names if "mid" in s.lower()), None)
                elif category == "contractual" and any(s for s in structure_names if "contract" in s.lower() or "temp" in s.lower()):
                    structure = next(
                        (s for s in structure_names if "contract" in s.lower() or "temp" in s.lower()),
                        None,
                    )
                elif category == "entry" and any(s for s in structure_names if "entry" in s.lower()):
                    structure = next((s for s in structure_names if "entry" in s.lower()), None)

                if structure:
                    break

        # If no matching structure found, use default
        if not structure:
            structure = default_structure

        doc = {
            "docstatus": 1,
            "employee": employee["employee"],
            "salary_structure": structure,
            "from_date": employee["date_of_joining"],
            "income_tax_slab": "US Federal Tab Slabs - FY 2024",
            "company": employee["company"],
            "doctype": "Salary Structure Assignment",
        }

        try:
            client.insert(doc)
            logging.info(f"Assigned {structure} to {employee['employee']} ({employee.get('designation', 'Unknown')})")
        except Exception as e:
            logging.error(f"Error assigning salary structure to {employee['employee']}: {e!s}")


async def insert_fiscal_years():
    """Insert fiscal years into Frappe for the last 8 years."""
    # Get the current year
    client = frappe_client.create_client()
    current_year = datetime.now().year
    company = get_default_company()

    # Create fiscal years for the last 8 years
    for year in range(current_year - 7, current_year + 1):
        doc = {
            "name": f"{year}",
            "docstatus": 0,
            "year": f"{year}",
            "year_start_date": f"{year}-01-01",
            "year_end_date": f"{year}-12-31",
            "auto_created": 0,
            "doctype": "Fiscal Year",
            "companies": [
                {
                    "company": company["name"],
                    "parent": f"{year}",
                    "parentfield": "companies",
                    "parenttype": "Fiscal Year",
                    "doctype": "Fiscal Year Company",
                }
            ],
        }
        try:
            client.insert(doc)
            logging.info(f"Inserted fiscal year: {year}")
        except Exception as e:
            logging.error(f"Error inserting fiscal year {year}: {e!s}")
            # Continue with next year instead of raising exception
            continue


async def insert_salary_slips():
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        fields=["employee", "designation", "company", "date_of_joining"],
        filters=[["Employee", "status", "=", "Active"]],  # must be active employees
        limit_page_length=settings.LIST_LIMIT,
    )

    for employee in employees:
        # Get the last day of the joining month
        joining_date = datetime.strptime(employee["date_of_joining"], "%Y-%m-%d")
        last_day = calendar.monthrange(joining_date.year, joining_date.month)[1]
        end_date = date(joining_date.year, joining_date.month, last_day)

        doc = {
            "docstatus": 0,
            "employee": employee["employee"],
            "company": employee["company"],
            "posting_date": "2025-04-23",
            "payroll_frequency": "Monthly",
            "start_date": employee["date_of_joining"],
            "end_date": end_date.strftime("%Y-%m-%d"),
            "doctype": "Salary Slip",
        }
        try:
            response = client.insert(doc)
            logging.info(f"Inserted salary slip for {employee['employee']}")

            if random.random() < 0.2:
                try:
                    client.update(
                        {
                            "doctype": "Salary Slip",
                            "name": response["name"],
                            "docstatus": 2,
                        }
                    )
                    logging.info(f"Updated salary slip for {employee['employee']}")
                except Exception as e:
                    logging.error(f"Error updating salary slip for {employee['employee']}: {e!s}")

        except Exception as e:
            logging.error(f"Error inserting salary slip for {employee['employee']}: {e!s}")


async def delete_salary_slips():
    """Delete all existing salary slips from Frappe."""
    client = frappe_client.create_client()
    salary_slips = client.get_list(
        "Salary Slip",
        fields=["name", "docstatus"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for slip in salary_slips:
        try:
            if slip["docstatus"] == 1:
                client.update(
                    {
                        "doctype": "Salary Slip",
                        "name": slip["name"],
                        "docstatus": 2,
                        "status": "Cancelled",
                    }
                )
            client.delete("Salary Slip", slip["name"])
            logging.info(f"Deleted salary slip: {slip['name']}")
        except Exception as e:
            logging.error(f"Error deleting salary slip {slip['name']}: {e!s}")


async def delete_payroll_entries():
    """Delete all existing payroll entries from Frappe."""
    client = frappe_client.create_client()
    payroll_entries = client.get_list(
        "Payroll Entry",
        fields=["name", "docstatus"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for entry in payroll_entries:
        try:
            if entry["docstatus"] == 1:
                client.update(
                    {
                        "doctype": "Payroll Entry",
                        "name": entry["name"],
                        "docstatus": 2,
                        "status": "Cancelled",
                    }
                )
            client.delete("Payroll Entry", entry["name"])
            logging.info(f"Deleted payroll entry: {entry['name']}")
        except Exception as e:
            logging.error(f"Error deleting payroll entry {entry['name']}: {e!s}")


async def insert_payroll_entries(from_date: date = "2023-01-01", to_date: date | None = None):
    """Insert payroll entries for a given date range."""
    client = frappe_client.create_client()
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")

    # Convert string dates to datetime objects
    from_date = datetime.strptime(from_date, "%Y-%m-%d") if isinstance(from_date, str) else from_date
    to_date = datetime.strptime(to_date, "%Y-%m-%d") if isinstance(to_date, str) else to_date
    company = get_default_company()

    # Get all months between from_date and to_date
    current_date = from_date
    month_list = []

    while current_date <= to_date:
        month_start = datetime(current_date.year, current_date.month, 1)
        # Get the last day of the month
        last_day = calendar.monthrange(current_date.year, current_date.month)[1]
        month_end = datetime(current_date.year, current_date.month, last_day)

        month_list.append((month_start, month_end))

        # Move to the next month
        if current_date.month == 12:  # noqa: SIM108
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)

    # For each month, get the list of active employees
    for month_start, month_end in month_list:
        logging.info(f"Getting active employees for month: {month_start.strftime('%B %Y')}")

        # Convert dates to string format for Frappe filters
        month_start_str = month_start.strftime("%Y-%m-%d")
        month_end_str = month_end.strftime("%Y-%m-%d")

        # Get all employees that joined before the end of this month
        all_employees = client.get_list(
            "Employee",
            fields=[
                "employee",
                "employee_name",
                "designation",
                "department",
                "date_of_joining",
                "relieving_date",
                "status",
            ],
            filters=[
                ["date_of_joining", "<=", month_end_str],
                ["status", "=", "Active"],
            ],
            limit_page_length=settings.LIST_LIMIT,
        )

        # Filter employees in Python code
        active_employees = []
        for employee in all_employees:
            # Check if employee has a relieving date
            has_relieving_date = employee["relieving_date"] and employee["relieving_date"] != ""

            # If employee has a relieving date, convert it to datetime
            if has_relieving_date:
                relieving_date = datetime.strptime(employee["relieving_date"], "%Y-%m-%d")
                # Include only if relieving date is on or after month_end
                if relieving_date >= month_end:
                    active_employees.append(employee)
            else:
                # Include employees with no relieving date
                active_employees.append(employee)

        payroll_entry = {
            "docstatus": 1,
            "posting_date": month_end_str,
            "exchange_rate": 1,
            "company": company["name"],
            "currency": "USD",
            "payroll_payable_account": f"Payroll Payable - {company['abbr']}",
            # "status": "Draft",
            "payroll_frequency": "Monthly",
            "start_date": month_start_str,
            "end_date": month_end_str,
            "validate_attendance": 0,
            "cost_center": f"Main - {company['abbr']}",
            "doctype": "Payroll Entry",
            "employees": [
                {
                    "docstatus": 0,
                    "employee": e["employee"],
                    "is_salary_withheld": 0,
                    "parentfield": "employees",
                    "parenttype": "Payroll Entry",
                    "doctype": "Payroll Employee Detail",
                }
                for e in active_employees
            ],
        }
        try:
            client.insert(payroll_entry)
            logging.info(f"Inserted payroll entry for {month_start.strftime('%B %Y')}")
            time.sleep(10)
        except Exception as e:
            logging.error(f"Error inserting payroll entry for {month_start.strftime('%B %Y')}: {e!s}")

    return month_list


async def update_salary_slips():
    client = frappe_client.create_client()
    slips = None
    previous_slip_count = 0
    current_slip_count = 0

    logger.info("Waiting for slips to be created. This can take a while if there are a lot of employees.")

    while current_slip_count == 0 or current_slip_count > previous_slip_count:
        previous_slip_count = current_slip_count
        slips = client.get_list(
            "Salary Slip",
            fields=["name", "docstatus", "employee"],
            filters=[["docstatus", "=", 0]],
            limit_page_length=settings.LIST_LIMIT,
        )
        current_slip_count = len(slips)
        logger.info(f"Still waiting for slips to be created. Found {current_slip_count} slips.")
        time.sleep(30)

    employees = client.get_list(
        "Employee",
        fields=["name", "employee_name", "ctc", "designation"],
        limit_page_length=settings.LIST_LIMIT,
    )

    slips = client.get_list(
        "Salary Slip",
        fields=["name", "docstatus", "employee"],
        limit_page_length=settings.LIST_LIMIT,
        filters=[["docstatus", "=", 0]],
    )
    # Join slips and employees based on employee["name"] and slip["employee"]
    employee_map = {employee["name"]: employee for employee in employees}

    # Create a list of slips with employee information
    for slip in slips:
        if slip["employee"] in employee_map:
            ctc = employee_map[slip["employee"]]["ctc"]
            slip["ctc"] = ctc if ctc else 0
            slip["designation"] = employee_map[slip["employee"]]["designation"]

    salary_components = client.get_list(
        "Salary Component",
        fields=[
            "name",
            "salary_component",
            "salary_component_abbr",
            "type",
            "is_tax_applicable",
        ],
        limit_page_length=settings.LIST_LIMIT,
    )
    salary_components = [client.get_doc("Salary Component", c["name"]) for c in salary_components]
    # Filter out components with no accounts or empty account array
    salary_components = [c for c in salary_components if "accounts" in c and isinstance(c["accounts"], list) and len(c["accounts"]) > 0]

    # Separate components into earnings and deductions
    earnings_components = [c for c in salary_components if c["type"] == "Earning" and not c.get("depends_on_payment_days", 0)]
    deduction_components = [c for c in salary_components if c["type"] == "Deduction"]

    # Find Basic Pay component
    basic_pay_component = next(
        (c for c in earnings_components if c["salary_component"] == "Basic Pay"),
        None,
    )

    for slip in slips:
        try:
            # Generate unique earnings for this employee
            earnings = []

            # Create a random seed based on employee ID to ensure consistency within a run
            employee_id = slip["employee"]
            random.seed(hash(employee_id) + int(time.time()))  # Add time to make it different each run

            # Calculate monthly salary as CTC/12
            monthly_salary = int(slip["ctc"] / 12) if slip["ctc"] else random.randint(3000, 8000)

            # Add Basic Pay (always include it)
            if basic_pay_component:
                # Basic pay will be 60-80% of monthly salary
                basic_pay_amount = int(monthly_salary * random.uniform(0.6, 0.8))
                earnings.append(
                    {
                        "doctype": "Salary Detail",
                        "parentfield": "earnings",
                        "parenttype": "Salary Slip",
                        "salary_component": basic_pay_component["salary_component"],
                        "abbr": basic_pay_component["salary_component_abbr"],
                        "amount": basic_pay_amount,
                        "is_tax_applicable": basic_pay_component["is_tax_applicable"],
                    }
                )

                # Calculate remaining amount for other components
                remaining_amount = monthly_salary - basic_pay_amount

                # Add other earnings (with lower probability)
                other_components = [c for c in earnings_components if c["salary_component"] != "Basic Pay"]
                if other_components and remaining_amount > 0:
                    # Distribute remaining amount among other components
                    num_components = random.randint(1, min(3, len(other_components)))  # Add 1-3 other components
                    selected_components = random.sample(other_components, num_components)

                    # Distribute remaining amount proportionally
                    for i, component in enumerate(selected_components):
                        if i == len(selected_components) - 1:
                            # Last component gets all remaining amount
                            amount = remaining_amount
                        else:
                            # Other components get a portion of remaining amount
                            portion = random.uniform(0.1, 0.3)  # 10-30% of remaining
                            amount = int(remaining_amount * portion)
                            remaining_amount -= amount

                        earnings.append(
                            {
                                "doctype": "Salary Detail",
                                "parentfield": "earnings",
                                "parenttype": "Salary Slip",
                                "salary_component": component["salary_component"],
                                "abbr": component["salary_component_abbr"],
                                "amount": amount,
                                "is_tax_applicable": component["is_tax_applicable"],
                            }
                        )

            # Generate deductions for this employee
            deductions = []

            # Calculate monthly salary for percentage-based deductions
            monthly_salary = sum(earning["amount"] for earning in earnings)

            # Get random deduction components (1-4 components)
            num_components = random.randint(1, min(4, len(deduction_components)))
            selected_components = random.sample(deduction_components, num_components)

            for component in selected_components:
                # Randomly decide between percentage or fixed amount
                if random.random() < 0.5:  # 50% chance for percentage-based
                    # Use 1-5% of monthly salary for percentage-based deductions
                    percent = random.uniform(0.01, 0.05)
                    amount = int(monthly_salary * percent)
                else:  # Fixed amount deductions
                    # Use fixed amounts between 50-200
                    amount = random.randint(50, 200)

                # 70% chance to include this deduction
                if random.random() < 0.7:
                    deductions.append(
                        {
                            "doctype": "Salary Detail",
                            "parentfield": "deductions",
                            "parenttype": "Salary Slip",
                            "salary_component": component["salary_component"],
                            "abbr": component["salary_component_abbr"],
                            "amount": amount,
                            "is_tax_applicable": component["is_tax_applicable"],
                        }
                    )

            client.update(
                {
                    "doctype": "Salary Slip",
                    "name": slip["name"],
                    "earnings": earnings,
                    "deductions": deductions,
                    "docstatus": 0,
                }
            )
            logging.info(f"Updated salary slip: {slip['name']}")
        except Exception as e:
            logging.error(f"Error updating salary slip {slip['name']}: {e!s}")

    # Reset random seed
    random.seed()


async def submit_payroll_entries():
    client = frappe_client.create_client()
    payroll_entries = client.get_list(
        "Payroll Entry",
        fields=["name", "docstatus"],
        limit_page_length=settings.LIST_LIMIT,
        filters=[["status", "=", "Submitted"]],
    )
    for entry in payroll_entries:
        try:
            doc = client.get_doc("Payroll Entry", entry["name"])
            client.session.post(
                client.url + "/api/method/run_doc_method",
                data={
                    "docs": json.dumps(doc),
                    "method": "submit_salary_slips",
                },
            )
            logger.info(f"Submitted payroll entry: {entry['name']}")
        except Exception as e:
            logging.error(f"Error submitting payroll entry: {e!s}")
