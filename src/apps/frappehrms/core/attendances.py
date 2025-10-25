import json
import random
from datetime import datetime, timedelta

from faker import Faker

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


fake = Faker()

# Constants for attendance status
ATTENDANCE_STATUS = ["Present", "Absent", "On Leave", "Half Day", "Work From Home"]
# Additional status flags
ADDITIONAL_STATUS = ["", "Late Entry", "Early Exit"]
# Weights for different statuses (making Present more common)
STATUS_WEIGHTS = {
    "Present": 0.65,
    "Absent": 0.1,
    "On Leave": 0.1,
    "Half Day": 0.05,
    "Work From Home": 0.1,
}


async def insert_attendances(number_of_employees=60):
    """
    Generate and insert attendance records for a specified number of employees.

    Args:
        number_of_employees (int): Number of employees to generate attendance for

    This function creates 1 month of diverse attendance logs with various statuses,
    including Present, Absent, On Leave, Half Day, Work From Home, Late Entry,
    and Early Exit entries. The records are randomized with Draft, Submitted,
    and Cancelled statuses.
    """
    logger.info(f"Starting attendance generation for {number_of_employees} employees")

    client = frappe_client.create_client()

    # Get company info
    company = companies.get_default_company()
    company_name = company["name"]

    # Get active employees
    employees = client.get_list(
        "Employee",
        limit_page_length=number_of_employees,
        fields=["name", "employee_name", "date_of_joining"],
        filters=[["status", "=", "Active"]],
    )

    if not employees:
        logger.warning("No active employees found")
        return

    logger.info(f"Found {len(employees)} active employees")

    # Generate one month of attendance data (30 days from today backwards)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)

    # Function to parse date whether it's in YYYY-MM-DD or MM-DD-YYYY format
    def parse_date(date_str):
        try:
            # Try YYYY-MM-DD format (standard ISO format)
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                # Try MM-DD-YYYY format (as seen in the error message)
                return datetime.strptime(date_str, "%m-%d-%Y").date()
            except ValueError:
                logger.warning(f"Could not parse date: {date_str}")
                return None

    # Track the number of records created
    total_records = 0
    batch_size = 50  # Insert in batches to avoid timeouts
    attendance_records = []

    # Generate attendance for each day in the last month
    current_date = start_date
    while current_date <= end_date:
        # Skip weekends (assuming Saturday and Sunday are weekends)
        if current_date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            current_date += timedelta(days=1)
            continue

        logger.info(f"Generating attendance for date: {current_date.strftime('%Y-%m-%d')}")

        # Create attendance for each employee for this date
        for employee in employees:
            # Skip if no joining date or if current date is before joining date
            joining_date = employee.get("date_of_joining")
            if joining_date:
                joining_date = parse_date(joining_date)
                if not joining_date or joining_date > current_date:
                    logger.debug(f"Skipping employee {employee['name']} - joined after {current_date}")
                    continue
            else:
                logger.debug(f"Skipping employee {employee['name']} - no joining date")
                continue

            # Randomly determine if we should create attendance for this employee on this day
            if random.random() > 0.95:  # 5% chance to skip creating attendance
                continue

            # Select a random attendance status based on weights
            status = random.choices(list(STATUS_WEIGHTS.keys()), weights=list(STATUS_WEIGHTS.values()), k=1)[0]

            # Determine additional status (Late Entry, Early Exit, or none)
            additional_status = ""
            if status == "Present" or status == "Work From Home":
                additional_status = random.choices(
                    ADDITIONAL_STATUS,
                    weights=[0.6, 0.2, 0.2],  # 60% chance of no additional status
                    k=1,
                )[0]

            # Generate work hours (8-10 hours for Present, 4-5 for Half Day, etc.)
            working_hours = 0
            if status == "Present" or status == "Work From Home":
                working_hours = round(random.uniform(7.5, 10.0), 1)  # Round to 1 decimal
            elif status == "Half Day":
                working_hours = round(random.uniform(3.5, 5.0), 1)

            # Generate randomized check-in/check-out times
            check_in_time = datetime.combine(
                current_date,
                datetime.strptime(f"{random.randint(8, 10)}:{random.randint(0, 59)}", "%H:%M").time(),
            )
            check_out_time = check_in_time + timedelta(hours=working_hours)

            # Create the attendance record
            attendance_record = {
                "doctype": "Attendance",
                "employee": employee["name"],
                "employee_name": employee["employee_name"],
                "status": status,
                "attendance_date": current_date.strftime("%Y-%m-%d"),
                "company": company_name,
                "working_hours": working_hours if working_hours > 0 else None,
                "docstatus": random.choices(
                    [0, 1],
                    weights=[0.2, 0.8],  # 80% Submitted, 10% Draft
                    k=1,
                )[0],
            }

            # Add additional status flags if applicable
            if additional_status:
                attendance_record[additional_status.lower().replace(" ", "_")] = 1

            # Add check-in and check-out times if applicable
            if working_hours > 0:
                attendance_record["in_time"] = check_in_time.strftime("%Y-%m-%d %H:%M:%S")
                attendance_record["out_time"] = check_out_time.strftime("%Y-%m-%d %H:%M:%S")

            # Add to batch
            attendance_records.append(attendance_record)

            # Insert if batch is full
            if len(attendance_records) >= batch_size:
                try:
                    client.insert_many(attendance_records)
                    total_records += len(attendance_records)
                    logger.info(f"Inserted {len(attendance_records)} attendance records (total: {total_records})")
                except Exception as e:
                    logger.error(f"Error inserting attendance records: {e!s}")

                    # If there's an error, try inserting one by one to identify which record is causing the issue
                    for record in attendance_records:
                        try:
                            client.insert(record)
                            total_records += 1
                        except Exception as individual_error:
                            logger.error(f"Error inserting individual record: {individual_error!s}")
                            logger.error(f"Problematic record: {json.dumps(record)}")

                # Clear the batch
                attendance_records = []

        # Move to next day
        current_date += timedelta(days=1)

    # Insert any remaining records
    if attendance_records:
        try:
            client.insert_many(attendance_records)
            total_records += len(attendance_records)
            logger.info(f"Inserted {len(attendance_records)} attendance records (total: {total_records})")
        except Exception as e:
            logger.error(f"Error inserting remaining attendance records: {e!s}")

            # If there's an error, try inserting one by one
            for record in attendance_records:
                try:
                    client.insert(record)
                    total_records += 1
                except Exception as individual_error:
                    logger.error(f"Error inserting individual record: {individual_error!s}")
                    logger.error(f"Problematic record: {json.dumps(record)}")

    logger.info(f"Completed attendance generation with {total_records} total records")


async def delete_all_attendances():
    """Delete all attendance records from the system."""

    client = frappe_client.create_client()

    try:
        # Get all attendance records
        attendance_records = client.get_list(
            "Attendance",
            limit_page_length=settings.LIST_LIMIT,
            fields=["name", "docstatus"],
        )

        if not attendance_records:
            logger.info("No attendance records found to delete")
            return

        # Delete each record
        for record in attendance_records:
            try:
                if record["docstatus"] == 1:
                    client.update(
                        {
                            "doctype": "Attendance",
                            "name": record["name"],
                            "docstatus": 2,
                        },
                    )
                    logger.info(f"Cancelled attendance {record['name']} with docstatus {record['docstatus']}")
                else:
                    client.delete("Attendance", record["name"])
                    logger.info(f"Deleted attendance {record['name']}")
            except Exception as e:
                logger.error(f"Error deleting attendance {record['name']}: {e!s}")

        logger.info(f"Deleted {len(attendance_records)} attendance records")
    except Exception as e:
        logger.error(f"Error in delete_all_attendances: {e!s}")
