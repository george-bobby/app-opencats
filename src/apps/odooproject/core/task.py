import datetime
import random
from collections import OrderedDict

from faker import Faker

from apps.odooproject.config.constants import DEFAULT_ADMIN_USER_ID, MailModelName, ProjectModelName, ResModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.database import AsyncPostgresClient
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker("en_US")


async def insert_tasks():
    tasks: list[dict] = load_json(settings.DATA_PATH.joinpath("tasks.json"))

    logger.start(f"Inserting {len(tasks)} tasks...")

    async with OdooClient() as client:
        projects = await client.search_read(ProjectModelName.PROJECT_PROJECT.value, fields=["id", "name"])
        task_stages = await client.search_read(ProjectModelName.PROJECT_TASK_TYPE.value, fields=["id", "name"])
        personal_stages = await client.search_read(ProjectModelName.PROJECT_TASK_TYPE.value, [("user_id", "=", DEFAULT_ADMIN_USER_ID)], fields=["id", "name"])
        users = await client.search_read(ResModelName.RES_USERS.value, [("active", "=", True)], fields=["id", "name"])
        tags = await client.search_read(ProjectModelName.PROJECT_TAGS.value, fields=["id", "name"])
        activity_types = await client.search_read(MailModelName.MAIL_ACTIVITY_TYPE.value, fields=["id", "name"])
        project_task_model = await client.search_read("ir.model", [("model", "=", "project.task")], ["id"])

        project_lookup = {project["name"]: project["id"] for project in projects}
        stage_lookup = {stage["name"]: stage["id"] for stage in task_stages}
        tag_lookup = {tag["name"]: tag["id"] for tag in tags}
        activity_type_lookup = {activity_type["name"]: activity_type["id"] for activity_type in activity_types}

        for task in tasks:
            project_id = project_lookup.get(task["project"])

            # Filter out None values for tags and users
            valid_tag_ids = [tag_lookup.get(tag) for tag in task["tags"] if tag_lookup.get(tag) is not None]
            selected_users = random.sample(users, min(random.randint(1, 3), len(users)))
            valid_user_ids = [u["id"] for u in selected_users]

            stage = faker.random_element(
                OrderedDict(
                    todo=0.3,
                    in_progress=0.3,
                    done=0.2,
                    canceled=0.2,
                )
            )

            task_record = {
                "name": task["name"],
                "project_privacy_visibility": "followers",  # Make task public since it has sub-tasks
                "project_id": project_id,
                "description": task["description"],
                "priority": task["priority"],  # 0=normal, 1=high
                "date_deadline": task["date_deadline"],
                "email_cc": task["email_cc"],
                "color": random.randint(1, 11),  # Random color between 1 and 11
            }

            todo_date = faker.date_between(start_date="today", end_date="+60d")
            in_progress_date = faker.date_between(start_date="today", end_date="+60d")
            done_date = faker.date_between(start_date="-60d", end_date="today")
            canceled_date = faker.date_between(start_date="-60d", end_date="today")

            match stage:
                case "todo":
                    task_record["stage_id"] = stage_lookup.get("To Do")
                    task_record["state"] = random.choice(["02_changes_requested", "03_approved", "04_waiting_normal"])
                    date_deadline = todo_date
                case "in_progress":
                    task_record["stage_id"] = stage_lookup.get("In Progress")
                    task_record["state"] = "01_in_progress"
                    date_deadline = in_progress_date
                case "done":
                    task_record["stage_id"] = stage_lookup.get("Done")
                    task_record["state"] = "1_done"
                    date_deadline = done_date
                case "canceled":
                    task_record["stage_id"] = stage_lookup.get("Canceled")
                    task_record["state"] = "1_canceled"
                    date_deadline = canceled_date

            task_record["date_deadline"] = date_deadline.strftime("%Y-%m-%d") if date_deadline else None

            # Only add tag_ids if we have valid tags
            if valid_tag_ids:
                task_record["tag_ids"] = [(6, 0, valid_tag_ids)]

            # Only add user_ids if we have valid users
            if valid_user_ids:
                task_record["user_ids"] = [(6, 0, valid_user_ids)]
                if DEFAULT_ADMIN_USER_ID in valid_user_ids:
                    task_record["personal_stage_type_id"] = random.choice(personal_stages)["id"]

            task_id = await client.create(ProjectModelName.PROJECT_TASK.value, task_record)

            activity_record = {
                "res_id": task_id,
                "activity_type_id": activity_type_lookup.get(task["next_activity"]),
                "res_model": "project.task",
                "res_model_id": project_task_model[0]["id"],
                "user_id": random.choice(valid_user_ids),
                "date_deadline": (datetime.date.today() + datetime.timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d"),
            }

            await client.create(MailModelName.MAIL_ACTIVITY.value, activity_record)

            for block_task in task.get("blockers", []) or []:
                stage_id = stage_lookup.get(block_task["stage"])
                block_record = {
                    "name": block_task["name"],
                    "description": block_task["description"],
                    "project_id": project_id,
                    "stage_id": stage_id if stage_id else False,
                    "priority": random.choice(["0", "1"]),
                    "email_cc": task["email_cc"],
                    "dependent_ids": [(6, 0, [task_id])],
                    "user_ids": [(6, 0, [random.choice(users)["id"]])],
                    "project_privacy_visibility": "followers",
                    "tag_ids": [(6, 0, [tag_lookup.get(tag) for tag in block_task["tags"] if tag_lookup.get(tag) is not None])],
                    "color": random.randint(1, 11),  # Random color between 1 and 11
                }

                match block_task["stage"]:
                    case "Done":
                        block_record["state"] = "1_done"
                    case "Canceled":
                        block_record["state"] = "1_canceled"
                    case "In Progress":
                        block_record["state"] = "01_in_progress"
                    case "To Do":
                        block_record["state"] = random.choice(["02_changes_requested", "03_approved", "04_waiting_normal"])

                blocker_id = await client.create(ProjectModelName.PROJECT_TASK.value, [block_record])

                activity_record = {
                    "res_id": blocker_id,
                    "activity_type_id": activity_type_lookup.get(task["next_activity"]),
                    "res_model": "project.task",
                    "res_model_id": project_task_model[0]["id"],
                    "user_id": random.choice(valid_user_ids),
                    "date_deadline": (datetime.date.today() + datetime.timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d"),
                }

                await client.create(MailModelName.MAIL_ACTIVITY.value, activity_record)

            for child_task in task["children"]:
                stage_id = stage_lookup.get(child_task["stage"])
                child_record = {
                    "name": child_task["name"],
                    "description": child_task["description"],
                    "email_cc": task["email_cc"],
                    "project_id": project_id,
                    "stage_id": stage_id if stage_id else False,
                    "priority": random.choice(["0", "1"]),
                    "parent_id": task_id,
                    "project_privacy_visibility": "followers",
                    "user_ids": [(6, 0, random.sample(valid_user_ids, 1))],
                    "tag_ids": [(6, 0, [tag_lookup.get(tag) for tag in child_task["tags"] if tag_lookup.get(tag) is not None])],
                    "color": random.randint(1, 11),  # Random color between 1 and 11
                }

                if date_deadline > datetime.date.today():
                    child_record["date_deadline"] = faker.date_between(start_date="today", end_date=date_deadline).strftime("%Y-%m-%d")
                else:
                    child_record["date_deadline"] = child_task["date_deadline"]

                match child_task["stage"]:
                    case "Done":
                        child_record["state"] = "1_done"
                    case "Canceled":
                        child_record["state"] = "1_canceled"
                    case "In Progress":
                        child_record["state"] = "01_in_progress"
                    case "To Do":
                        child_record["state"] = random.choice(["02_changes_requested", "03_approved", "04_waiting_normal"])

                child_id = await client.create(ProjectModelName.PROJECT_TASK.value, [child_record])

                activity_record = {
                    "res_id": child_id,
                    "activity_type_id": activity_type_lookup.get(task["next_activity"]),
                    "res_model": "project.task",
                    "res_model_id": project_task_model[0]["id"],
                    "user_id": random.choice(valid_user_ids),
                    "date_deadline": (datetime.date.today() + datetime.timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d"),
                }

                await client.create(MailModelName.MAIL_ACTIVITY.value, activity_record)

        update_log_message_query = """
            DO $$
            DECLARE
                start_date DATE := (CURRENT_DATE - INTERVAL '1 month');
                parent_end_date DATE := (CURRENT_DATE - INTERVAL '7 days');
                child_end_date DATE := CURRENT_DATE;
                
                total_days INT;
                total_seconds_in_day INT := 24 * 60 * 60;
            BEGIN
                -- Recalculate date range for parent messages
                total_days := (parent_end_date - start_date);
                
                -- STEP 1: Update parent messages (parent_id IS NULL)
                -- Dates are now guaranteed to be at least 7 days before today.
                UPDATE mail_message
                SET
                    "date" = (
                        start_date +
                        (total_days * RANDOM())::INT * INTERVAL '1 day' +
                        (total_seconds_in_day * RANDOM())::INT * INTERVAL '1 second'
                    )::timestamp
                WHERE
                    model = 'project.task'
                    AND body LIKE '%A new task has been created%'
                    AND parent_id IS NULL;

                -- STEP 2: Update child messages (parent_id IS NOT NULL) using a JOIN.
                -- Each child's date is now calculated based on its specific parent's date.
                UPDATE mail_message AS child
                SET
                    "date" = (
                        parent."date" +
                        (RANDOM() * 2 + 1)::INT * INTERVAL '1 day' +
                        -- Add a random number of seconds to the new child start date.
                        (total_seconds_in_day * RANDOM())::INT * INTERVAL '1 second'
                    )::timestamp
                FROM mail_message AS parent
                WHERE
                    child.parent_id = parent.id
                    AND child.model = 'project.task'
                    AND parent.model = 'project.task'
                    AND parent.body LIKE '%A new task has been created%';
                    
            END $$;
        """
        update_author_id_query = """
            UPDATE mail_message
            SET author_id = (
                SELECT id
                FROM res_users
                WHERE active = True
                ORDER BY RANDOM()
                LIMIT 1
            )
            WHERE model = 'project.task';
        """
        await AsyncPostgresClient.execute(update_log_message_query)
        await AsyncPostgresClient.execute(update_author_id_query)
        logger.succeed(f"Inserted {len(tasks)} tasks successfully.")
