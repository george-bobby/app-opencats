import json
import random
import string
from datetime import datetime
from pathlib import Path

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


async def insert_users(target_count: int = 60):
    """
    Create user accounts in Frappe HR based on Employee information.
    This function fetches all employees without corresponding user accounts,
    creates user accounts for them, and links the accounts to the employee records.

    Args:
        target_count: Target number of users to create (between 50-70)
    """

    client = frappe_client.create_client()

    company = companies.get_default_company()
    company_name = company["name"]
    domain = company.get("name", "").replace(" ", "").lower() + ".com"

    # Define the path to the users JSON file
    users_file_path = Path("data/generated/users.json")

    # Ensure the directory exists
    users_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if cached user data exists
    cached_user_data = {}
    if users_file_path.exists():
        logger.info("Found existing users.json file, loading data from it")
        try:
            with users_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_company = data.get("company_name", "")

                # Use stored data if it's for the same company
                if stored_company == company_name:
                    cached_user_data = data.get("user_data", {})
                    logger.info(f"Loaded cached user data for {len(cached_user_data)} employees")
                else:
                    logger.info("Stored data is for different company, will generate new data")
        except Exception as e:
            logger.error(f"Failed to read users.json: {e!s}")
            logger.info("Falling back to new data generation")
    else:
        logger.info("users.json file not found, will generate new user data")

    # Get all active employees
    employees = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        fields=[
            "name",
            "first_name",
            "last_name",
            "company_email",
            "personal_email",
            "prefered_contact_email",
            "status",
            "designation",
            "employee_name",
        ],
        filters=[["status", "=", "Active"]],
    )

    if not employees:
        logger.warning("No active employees found")
        return

    logger.info(f"Found {len(employees)} active employees")

    # Get existing user emails to avoid duplicates
    existing_users = client.get_list("User", limit_page_length=settings.LIST_LIMIT, fields=["email", "name"])
    existing_emails = {user["email"].lower() for user in existing_users if "email" in user}

    # Map employee name to existing user ID if it exists
    existing_user_map = {}
    for user in existing_users:
        if "email" in user:
            existing_user_map[user["email"].lower()] = user["name"]

    users_created = 0
    users_skipped = 0
    processed_employees = []
    new_user_data = {}

    # Iterate through employees and create users
    for employee in employees:
        if users_created >= target_count:
            logger.info(f"Reached target of {target_count} users created, stopping")
            break

        employee_id = employee["name"]

        # Check if we have cached data for this employee
        if employee_id in cached_user_data:
            cached_info = cached_user_data[employee_id]
            email = cached_info.get("email")
            roles = cached_info.get("roles", [])
            password = cached_info.get("password")
            logger.info(f"Using cached user data for employee {employee_id}")
        else:
            # Generate new user data for this employee
            # Determine which email to use based on preferred_contact_email
            preferred = employee.get("prefered_contact_email", "").lower()

            if preferred == "company_email" and employee.get("company_email"):
                email = employee.get("company_email").lower()
            elif preferred == "personal_email" and employee.get("personal_email"):
                email = employee.get("personal_email").lower()
            elif employee.get("company_email"):
                email = employee.get("company_email").lower()
            elif employee.get("personal_email"):
                email = employee.get("personal_email").lower()
            else:
                # No valid email - generate one based on employee name and company domain
                name_parts = employee.get("employee_name", "").lower().split()
                if len(name_parts) > 1:  # noqa: SIM108
                    # Generate email from first and last name
                    email = f"{name_parts[0]}.{name_parts[-1]}@{domain}"
                else:
                    # Fallback to just the name
                    email = f"{name_parts[0]}@{domain}"
                logger.info(f"Generated email {email} for employee {employee['name']} with no email")

            # Determine user role based on designation
            designation = employee.get("designation", "").lower()
            roles = []

            # Assign roles based on position
            if "chief" in designation or "officer" in designation or "director" in designation:
                roles = ["HR Manager", "Employee", "Expense Approver", "Leave Approver"]
            elif "manager" in designation or "head" in designation:
                roles = ["HR User", "Employee", "Expense Approver", "Leave Approver"]
            else:
                roles = ["Employee"]

            # Generate a secure random password
            password = "".join(random.choices(string.ascii_letters + string.digits, k=10))

            # Store the new user data for caching
            new_user_data[employee_id] = {
                "email": email,
                "roles": roles,
                "password": password,
                "first_name": employee.get("first_name", ""),
                "last_name": employee.get("last_name", ""),
                "designation": employee.get("designation", ""),
            }

        # Check if user already exists
        existing_user_id = None
        if email in existing_emails:
            existing_user_id = existing_user_map.get(email)

            # If we found a user ID, update the employee record and skip user creation
            if existing_user_id and not employee.get("user_id"):
                try:
                    client.update(
                        {
                            "doctype": "Employee",
                            "name": employee["name"],
                            "user_id": existing_user_id,
                        }
                    )
                    logger.info(f"Linked existing user {existing_user_id} to employee {employee['name']}")
                    processed_employees.append(
                        {
                            "employee": employee["name"],
                            "user": existing_user_id,
                            "email": email,
                            "designation": employee.get("designation", ""),
                            "is_new": False,
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to link existing user to employee {employee['name']}: {e!s}")

            users_skipped += 1
            continue

        # Add email to set of existing emails to prevent duplicates in this run
        existing_emails.add(email)

        # Create user document
        user_doc = {
            "doctype": "User",
            "email": email,
            "first_name": employee.get("first_name", ""),
            "last_name": employee.get("last_name", ""),
            "send_welcome_email": 0,  # Disable automatic welcome email
            "user_type": "System User",
            "roles": [{"role": role} for role in roles],
            "new_password": password,
        }

        # Create the user
        try:
            response = client.insert(user_doc)
            logger.info(f"Created user: {response['name']} with roles: {roles}")

            # Update employee record with user id
            try:
                client.update(
                    {
                        "doctype": "Employee",
                        "name": employee["name"],
                        "user_id": response["name"],
                    }
                )
                logger.info(f"Linked user {response['name']} to employee {employee['name']}")
                users_created += 1

                processed_employees.append(
                    {
                        "employee": employee["name"],
                        "user": response["name"],
                        "email": email,
                        "designation": employee.get("designation", ""),
                        "is_new": True,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to link user to employee {employee['name']}: {e!s}")
        except Exception as e:
            logger.error(f"Failed to create user for employee {employee['name']}: {e!s}")

    # Save the user data to cache file (merge with existing data)
    if new_user_data or cached_user_data:
        all_user_data = {**cached_user_data, **new_user_data}
        users_cache_data = {
            "user_data": all_user_data,
            "company_name": company_name,
            "theme_subject": settings.DATA_THEME_SUBJECT,
            "last_updated": datetime.now().isoformat(),
            "total_cached_employees": len(all_user_data),
        }

        try:
            with users_file_path.open("w", encoding="utf-8") as f:
                json.dump(users_cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved user data for {len(all_user_data)} employees to {users_file_path}")
        except Exception as e:
            logger.error(f"Failed to save user data to file: {e!s}")

    logger.info(f"Created {users_created} users, skipped {users_skipped} employees")

    return users_created


async def create_user_groups():
    """
    Create user groups and assign users to them based on their roles and designations.
    Fetches employee and user data directly from Frappe.
    """

    client = frappe_client.create_client()

    # Fetch active employees with user links and designations
    employees = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "user_id", "designation"],
        filters=[["status", "=", "Active"], ["user_id", "!=", ""]],
    )

    if not employees:
        logger.warning("No employees with linked user accounts found for user group assignment")
        return

    logger.info(f"Found {len(employees)} employees with user accounts for group assignment")

    # Get all active system users
    users = client.get_list(
        "User",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "email", "first_name", "last_name"],
        filters=[["user_type", "=", "System User"], ["enabled", "=", 1]],
    )

    # Create a mapping of user IDs to users for quick lookup
    user_map = {user["name"]: user for user in users}

    # Define the user groups with their expected sizes
    user_groups = {
        "HR Manager": 0.03,  # 3% of total users
        "HR Executive": 0.05,  # 5% of total users
        "Department Manager": 0.08,  # 8% of total users
        "Team Lead": 0.1,  # 10% of total users
        "Finance Manager": 0.03,  # 3% of total users
        "Expense Approver": 0.07,  # 7% of total users
        "Employee": 1.0,  # 100% of total users (everyone)
        "System Administrator": 0.03,  # 3% of total users
        "Payroll Officer": 0.03,  # 3% of total users
        "Recruitment Coordinator": 0.05,  # 5% of total users
    }

    # Function to determine which groups a user should belong to based on designation
    def get_user_groups(designation: str) -> list[str]:
        designation = designation.lower() if designation else ""
        groups = []

        # Everyone is in the Employee group
        groups.append("Employee")

        # Assign to other groups based on keywords in designation
        if "chief" in designation or "director" in designation:
            groups.extend(["Department Manager", "Expense Approver"])
            if "hr" in designation:
                groups.append("HR Manager")
            if "finance" in designation or "financial" in designation:
                groups.append("Finance Manager")

        elif "manager" in designation:
            groups.append("Department Manager")
            if "hr" in designation:
                groups.append("HR Executive")
            if "finance" in designation:
                groups.append("Finance Manager")
            groups.append("Expense Approver")

        elif "lead" in designation or "senior" in designation:
            groups.append("Team Lead")
            groups.append("Expense Approver")

        # Specific role assignments
        if "admin" in designation or "it" in designation:
            groups.append("System Administrator")

        if "payroll" in designation:
            groups.append("Payroll Officer")

        if "recruitment" in designation or "talent" in designation:
            groups.append("Recruitment Coordinator")

        if "hr" in designation and "executive" in designation:
            groups.append("HR Executive")

        return groups

    # Assign users to groups based on their designation
    group_members = {group: [] for group in user_groups}

    # Assign users to groups based on their designation
    for emp in employees:
        user_id = emp.get("user_id")
        if not user_id or user_id not in user_map:
            continue

        designation = emp.get("designation", "")

        # Get groups this user should belong to
        assigned_groups = get_user_groups(designation)

        # Add user to those groups' member lists
        for group in assigned_groups:
            if group in group_members and user_id not in group_members[group]:
                group_members[group].append(user_id)

    # Second pass: ensure minimum members in each group
    for group, proportion in user_groups.items():
        current_size = len(group_members[group])
        total_users = len(employees)

        # Calculate target size based on proportion (minimum 1 member)
        target_size = max(1, int(total_users * proportion))

        # If group is Employee, everyone should be in it
        if group == "Employee":
            # Get all user IDs
            all_user_ids = [emp.get("user_id") for emp in employees if emp.get("user_id")]
            # Add any missing users to Employee group
            for user_id in all_user_ids:
                if user_id not in group_members[group]:
                    group_members[group].append(user_id)
            continue

        # If group is under target size, add more members
        if current_size < target_size:
            # Get users not already in this group
            available_users = [emp.get("user_id") for emp in employees if emp.get("user_id") and emp.get("user_id") not in group_members[group]]

            # Add random users until we reach target size or run out of users
            additional_needed = target_size - current_size
            if available_users and additional_needed > 0:
                additional_users = random.sample(available_users, min(additional_needed, len(available_users)))
                group_members[group].extend(additional_users)

        # If group is over target size and not Employee group, remove excess members
        elif current_size > target_size and group != "Employee":
            # Keep the target number of members (ensures important members stay in their groups)
            group_members[group] = group_members[group][:target_size]

    # Check for existing user groups
    existing_groups = client.get_list("User Group", limit_page_length=settings.LIST_LIMIT, fields=["name"])
    existing_group_names = {group["name"] for group in existing_groups}

    # Find the admin user for fallback membership
    admin_users = [u["name"] for u in users if u.get("name") and "admin" in u["name"].lower()]
    fallback_user = admin_users[0] if admin_users else users[0]["name"] if users else None

    # Create or update user groups
    for group_name, members in group_members.items():
        # Ensure we have at least one member
        if not members and fallback_user:
            members = [fallback_user]

        # Create user group with members if it doesn't exist
        if group_name not in existing_group_names:
            try:
                # Prepare user members
                user_group_members = [{"user": member} for member in members]

                group_doc = {
                    "doctype": "User Group",
                    "name": group_name,
                    "enabled": 1,
                    "user_group_members": user_group_members,
                }
                client.insert(group_doc)
                logger.info(f"Created user group: {group_name} with {len(members)} members")
            except Exception as e:
                logger.error(f"Failed to create user group {group_name}: {e!s}")
        else:
            # Update existing group
            try:
                # Get current group to update
                group_doc = client.get_doc("User Group", group_name)

                if group_doc:
                    # Prepare the user list
                    updated_users = [{"user": member} for member in members]

                    # Update the group with new user list
                    group_doc["user_group_members"] = updated_users
                    client.update(group_doc)

                    logger.info(f"Updated user group {group_name} with {len(members)} members")
            except Exception as e:
                logger.error(f"Failed to update user group {group_name}: {e!s}")

    # Log summary of user group assignments
    for group, members in group_members.items():
        logger.info(f"User group '{group}' has {len(members)} members")
