"""Shared timestamp generation utilities for messages."""

import datetime
import random

from apps.mattermost.utils.faker import faker
from common.logger import logger


def generate_conversation_timestamps(message_count: int, earliest_communication_date: int) -> list[int]:
    """
    Generate realistic timestamps for a conversation based on start date using Faker.

    Args:
        message_count: Number of timestamps to generate
        earliest_communication_date: Earliest timestamp in milliseconds

    Returns:
        List of timestamps in milliseconds, sorted chronologically
    """
    # Convert earliest communication date from milliseconds to datetime
    earliest_date = datetime.datetime.fromtimestamp(earliest_communication_date / 1000)

    # Create realistic historical timeframe (30 days to 6 months ago)
    now = datetime.datetime.now()
    thirty_days_ago = now - datetime.timedelta(days=30)
    six_months_ago = now - datetime.timedelta(days=180)

    # Determine conversation start window
    start_date = max(earliest_date, six_months_ago)
    end_date = thirty_days_ago

    if start_date >= end_date:
        # If the time window is too narrow, use a shorter historical period
        end_date = max(earliest_date + datetime.timedelta(days=7), thirty_days_ago)
        if start_date >= end_date:
            start_date = earliest_date
            end_date = earliest_date + datetime.timedelta(days=1)

    # Generate conversation start time using Faker
    conversation_start = faker.date_time_between(start_date=start_date, end_date=end_date)

    # Generate timestamps for all messages in the conversation
    timestamps = []
    current_msg_time = conversation_start

    for i in range(message_count):
        if i == 0:
            timestamps.append(int(conversation_start.timestamp() * 1000))
        else:
            # Add realistic gaps between messages using Faker's random_int
            # Generate gaps between 2 minutes and 8 hours
            gap_minutes = faker.random_int(min=2, max=480)  # 2 minutes to 8 hours
            current_msg_time += datetime.timedelta(minutes=gap_minutes)

            # Ensure we don't go beyond the historical period
            if current_msg_time > thirty_days_ago:
                current_msg_time = thirty_days_ago - datetime.timedelta(minutes=faker.random_int(min=1, max=60))

            timestamps.append(int(current_msg_time.timestamp() * 1000))

    return timestamps


def generate_thread_message_timestamps(thread_start_timestamp: int, thread_end_timestamp: int, message_count: int) -> list[int]:
    """
    Generate realistic message timestamps within a thread timeframe.

    Args:
        thread_start_timestamp: Thread start time in milliseconds
        thread_end_timestamp: Thread end time in milliseconds
        message_count: Number of timestamps to generate

    Returns:
        List of timestamps in milliseconds, sorted chronologically
    """
    if message_count <= 0:
        return []

    timestamps = []
    thread_duration = thread_end_timestamp - thread_start_timestamp

    for i in range(message_count):
        # Create more natural message spacing - messages appear in clusters with gaps
        if message_count == 1:
            # Single message gets the start timestamp
            timestamp = thread_start_timestamp
        else:
            # First message starts the thread
            if i == 0:
                timestamp = thread_start_timestamp
            else:
                # Subsequent messages have realistic delays
                # Early messages come faster, later ones have more gaps
                base_progress = i / (message_count - 1)

                # Add exponential factor for more realistic conversation flow
                # (quick initial responses, then longer delays)
                exponential_progress = base_progress**0.7

                timestamp = thread_start_timestamp + int(thread_duration * exponential_progress)

                # Add realistic randomness (5-120 minutes variation)
                min_jitter = 5 * 60 * 1000  # 5 minutes
                max_jitter = 120 * 60 * 1000  # 2 hours
                jitter = random.randint(min_jitter, max_jitter)

                # Ensure minimum gap between messages (at least 2 minutes)
                min_gap = 2 * 60 * 1000  # 2 minutes
                if i > 0:
                    previous_timestamp = timestamps[-1]
                    timestamp = max(timestamp, previous_timestamp + min_gap)

                timestamp += jitter

        # Ensure timestamp is within thread bounds
        timestamp = max(thread_start_timestamp, timestamp)
        timestamp = min(thread_end_timestamp, timestamp)

        timestamps.append(timestamp)

    # Sort to ensure chronological order
    timestamps.sort()
    return timestamps


def generate_thread_timestamps(thread_count: int, earliest_start_time: int, latest_end_time: int | None = None) -> list[int]:
    """
    Generate timestamps for multiple threads with realistic spacing.

    Args:
        thread_count: Number of thread timestamps to generate
        earliest_start_time: Earliest possible thread start time in milliseconds
        latest_end_time: Latest possible thread start time in milliseconds (optional)

    Returns:
        List of thread start timestamps in milliseconds, sorted chronologically
    """
    if thread_count <= 0:
        return []

    if latest_end_time is None:
        # Default to 30 days ago
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        latest_end_time = int(thirty_days_ago.timestamp() * 1000)

    if earliest_start_time >= latest_end_time:
        # If time window is too narrow, return single timestamp
        logger.warning("Thread timestamp window too narrow, using start time")
        return [earliest_start_time] * thread_count

    time_span = latest_end_time - earliest_start_time
    timestamps = []

    for _ in range(thread_count):
        # Use exponential distribution to bias towards earlier dates
        # (more activity when channel was newer)
        random_factor = random.random() ** 1.5  # Bias towards 0 (earlier times)

        # Calculate timestamp within available span
        time_offset = int(time_span * random_factor)
        timestamp = earliest_start_time + time_offset

        # Add some randomness to avoid clustering
        daily_variance = random.randint(-12 * 60 * 60 * 1000, 12 * 60 * 60 * 1000)  # ±12 hours
        timestamp += daily_variance

        # Ensure within bounds
        timestamp = max(earliest_start_time, timestamp)
        timestamp = min(latest_end_time, timestamp)

        timestamps.append(timestamp)

    # Sort chronologically
    timestamps.sort()

    # Ensure minimum spacing between threads (prevent clustering)
    min_spacing = 2 * 60 * 60 * 1000  # Minimum 2 hours between threads
    adjusted_timestamps = []

    for i, timestamp in enumerate(timestamps):
        if i == 0:
            adjusted_timestamps.append(timestamp)
        else:
            # Ensure minimum spacing from previous thread
            min_allowed_time = adjusted_timestamps[-1] + min_spacing
            if timestamp < min_allowed_time:
                # Adjust timestamp to maintain spacing
                adjusted_timestamp = min(min_allowed_time, latest_end_time)
                adjusted_timestamps.append(adjusted_timestamp)
            else:
                adjusted_timestamps.append(timestamp)

    return adjusted_timestamps
