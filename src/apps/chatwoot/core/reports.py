from datetime import timedelta

from apps.chatwoot.utils.database import AsyncPostgresClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


async def fix_converstion_timestamps():
    query = "SELECT * FROM conversations ORDER BY id ASC"
    conversations = await AsyncPostgresClient.fetch(query)
    logger.start(f"Fixing timestamps for {len(conversations)} conversations")

    for conversation in conversations:
        conversation_id = conversation["id"]
        start_date = faker.date_time_between(start_date="-1y", end_date="-1w")

        update_query = "UPDATE conversations SET created_at = $1 WHERE id = $2"
        await AsyncPostgresClient.execute(update_query, start_date, conversation_id)

        first_reply_created_at = start_date + timedelta(hours=faker.random_int(0, 24), minutes=faker.random_int(0, 59))
        update_query = "UPDATE conversations SET first_reply_created_at = $1 WHERE id = $2"
        await AsyncPostgresClient.execute(update_query, first_reply_created_at, conversation_id)

        message_query = "SELECT * FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC"
        messages = await AsyncPostgresClient.fetch(message_query, conversation_id)

        # Categorize messages by type for proper chronological ordering
        # Type 0/1: Regular conversation messages (incoming/outgoing)
        # Type 2: System messages/notifications (should come after first message)
        # Type 3: CSAT feedback (should come last)
        type_3_message = None
        type_2_messages = []
        regular_messages = []

        for message in messages:
            if message.get("message_type") == 3 and message.get("content_attributes") is None:
                type_3_message = message
            elif message.get("message_type") == 2:
                type_2_messages.append(message)
            else:
                regular_messages.append(message)

                # Reorder messages: randomly insert type 2 messages after first/second/third regular messages
        reordered_messages = []

        if regular_messages and type_2_messages:
            # Randomly choose insert position after 1st, 2nd, or 3rd message
            insert_after_position = faker.random_int(min=1, max=min(3, len(regular_messages)))

            # Add regular messages up to insert position
            reordered_messages.extend(regular_messages[:insert_after_position])

            # Add all type 2 messages at the chosen position
            reordered_messages.extend(type_2_messages)

            # Add remaining regular messages
            reordered_messages.extend(regular_messages[insert_after_position:])

        else:
            # No type 2 messages to insert, just add regular messages
            reordered_messages.extend(regular_messages)

        # Always add type 3 message last (CSAT feedback)
        if type_3_message:
            reordered_messages.append(type_3_message)

        # Get conversation details once for all reporting events
        conv_query = "SELECT inbox_id, assignee_id FROM conversations WHERE id = $1"
        conv_result = await AsyncPostgresClient.fetchrow(conv_query, conversation_id)
        inbox_id = conv_result["inbox_id"] if conv_result else 1
        user_id = conv_result["assignee_id"] if conv_result else 1

        message_date = start_date
        first_response_date = start_date
        last_incoming_message_time = start_date  # Track when customer last sent a message

        for index, message in enumerate(reordered_messages):
            message_date = faker.normal_random_date(
                start_date=message_date,
                end_date=(message_date + timedelta(hours=18)),
            )
            if index == 1:
                first_response_date = message_date

            update_query = "UPDATE messages SET created_at = $1, updated_at = $1 WHERE id = $2"
            await AsyncPostgresClient.execute(update_query, message_date, message["id"])

            # Track customer wait time for each outgoing message
            message_type = message.get("message_type", 0)

            # If this is an outgoing message (type 1), calculate reply_time since last incoming message
            if message_type == 1:  # Outgoing message from agent
                wait_time = (message_date - last_incoming_message_time).total_seconds()

                # Only create reply_time event if there was actually a wait (> 0 seconds)
                if wait_time > 0:
                    reply_time_insert_query = """
                        INSERT INTO reporting_events (name, value, account_id, inbox_id, user_id, conversation_id, 
                                                    created_at, updated_at, value_in_business_hours, event_start_time, event_end_time)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """
                    await AsyncPostgresClient.execute(
                        reply_time_insert_query, "reply_time", wait_time, 1, inbox_id, user_id, conversation_id, message_date, message_date, 0, last_incoming_message_time, message_date
                    )

            # If this is an incoming message (type 0), update the last incoming message time
            elif message_type == 0:  # Incoming message from customer
                last_incoming_message_time = message_date
        end_time = message_date

        # Calculate reporting metrics (all values in seconds)
        first_response_time = (first_response_date - start_date).total_seconds()
        resolution_time = (end_time - start_date).total_seconds()

        # Event timing logic:
        # - first_response: start_date → first_response_date
        # - reply_time: Individual events for each outgoing message (calculated above)
        # - conversation_resolved: start_date → end_time

        # Insert first_response reporting event
        fr_insert_query = """
            INSERT INTO reporting_events (name, value, account_id, inbox_id, user_id, conversation_id, 
                                        created_at, updated_at, value_in_business_hours, event_start_time, event_end_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        await AsyncPostgresClient.execute(
            fr_insert_query, "first_response", first_response_time, 1, inbox_id, user_id, conversation_id, first_response_date, first_response_date, 0, start_date, first_response_date
        )

        # Insert conversation_resolved reporting event
        res_insert_query = """
            INSERT INTO reporting_events (name, value, account_id, inbox_id, user_id, conversation_id, 
                                        created_at, updated_at, value_in_business_hours, event_start_time, event_end_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        await AsyncPostgresClient.execute(res_insert_query, "conversation_resolved", resolution_time, 1, inbox_id, user_id, conversation_id, end_time, end_time, 0, start_date, end_time)

        # Update existing conversation_resolved events to use the last message timestamp
        update_resolved_query = """
            UPDATE reporting_events 
            SET created_at = $1, updated_at = $1, event_end_time = $1, value = $2
            WHERE conversation_id = $3 AND name = 'conversation_resolved'
        """
        await AsyncPostgresClient.execute(update_resolved_query, end_time, resolution_time, conversation_id)

        feedback_query = "UPDATE csat_survey_responses SET created_at = $1, updated_at = $1   WHERE conversation_id = $2"
        await AsyncPostgresClient.execute(feedback_query, end_time, conversation_id)

    logger.succeed("Fixed converstion timestamps")
