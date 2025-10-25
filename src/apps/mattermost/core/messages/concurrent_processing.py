"""Shared concurrent processing utilities for message generation."""

import asyncio
from collections.abc import Callable
from typing import Any

from apps.mattermost.config.settings import settings
from common.logger import logger


async def process_batches_concurrently(items: list[Any], batch_processor: Callable, batch_size: int | None = None, max_concurrent: int | None = None) -> list[Any]:
    """
    Process items in batches with concurrency control.

    Args:
        items: List of items to process
        batch_processor: Async function to process each batch
        batch_size: Size of each batch (defaults to MAX_CONCURRENT_GENERATION_REQUESTS)
        max_concurrent: Maximum concurrent operations (defaults to MAX_CONCURRENT_GENERATION_REQUESTS)

    Returns:
        Flattened list of results from all batches
    """
    if batch_size is None:
        batch_size = settings.MAX_CONCURRENT_GENERATION_REQUESTS

    if max_concurrent is None:
        max_concurrent = settings.MAX_CONCURRENT_GENERATION_REQUESTS

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_batch_with_semaphore(batch: list[Any]) -> list[Any]:
        async with semaphore:
            return await batch_processor(batch)

    # Split items into batches
    tasks = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        tasks.append(_process_batch_with_semaphore(batch))

    # Execute all batches concurrently
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten results and handle exceptions
    all_results = []
    for i, batch_result in enumerate(batch_results):
        if isinstance(batch_result, Exception):
            logger.error(f"Batch {i} failed: {batch_result}")
            continue
        elif batch_result:
            all_results.extend(batch_result)

    return all_results


async def process_items_with_semaphore(items: list[Any], item_processor: Callable, max_concurrent: int | None = None) -> list[Any]:
    """
    Process individual items with concurrency control.

    Args:
        items: List of items to process
        item_processor: Async function to process each item
        max_concurrent: Maximum concurrent operations

    Returns:
        List of results from processing all items
    """
    if max_concurrent is None:
        max_concurrent = settings.MAX_CONCURRENT_GENERATION_REQUESTS

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_item_with_semaphore(item: Any) -> Any:
        async with semaphore:
            return await item_processor(item)

    # Create tasks for all items
    tasks = [_process_item_with_semaphore(item) for item in items]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions and log them
    successful_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Item {i} processing failed: {result}")
            continue
        elif result is not None:
            successful_results.append(result)

    return successful_results


class ConcurrentTaskManager:
    """
    Helper class for managing concurrent task execution with proper error handling.
    """

    def __init__(self, max_concurrent: int | None = None):
        self.max_concurrent = max_concurrent or settings.MAX_CONCURRENT_GENERATION_REQUESTS
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.tasks = []
        self.results = []

    async def add_task(self, coro) -> None:
        """Add a coroutine as a task with semaphore control."""

        async def _execute_with_semaphore():
            async with self.semaphore:
                return await coro

        self.tasks.append(_execute_with_semaphore())

    async def execute_all(self) -> list[Any]:
        """Execute all added tasks concurrently and return results."""
        if not self.tasks:
            return []

        logger.info(f"Executing {len(self.tasks)} tasks with max {self.max_concurrent} concurrent")

        # Execute all tasks
        results = await asyncio.gather(*self.tasks, return_exceptions=True)

        # Process results and handle exceptions
        successful_results = []
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {result}")
                failed_count += 1
            elif result is not None:
                successful_results.append(result)

        logger.info(f"Completed {len(successful_results)} tasks successfully, {failed_count} failed")

        # Clear tasks for next use
        self.tasks.clear()

        return successful_results

    def clear(self) -> None:
        """Clear all pending tasks."""
        self.tasks.clear()


async def gather_with_limit(coroutines: list, limit: int | None = None, return_exceptions: bool = True) -> list[Any]:
    """
    Execute coroutines with a concurrency limit.

    Args:
        coroutines: List of coroutines to execute
        limit: Maximum concurrent executions
        return_exceptions: Whether to return exceptions in results

    Returns:
        List of results from all coroutines
    """
    if limit is None:
        limit = settings.MAX_CONCURRENT_GENERATION_REQUESTS

    if len(coroutines) <= limit:
        # If we have fewer coroutines than the limit, execute all at once
        return await asyncio.gather(*coroutines, return_exceptions=return_exceptions)

    # Execute in chunks with the specified limit
    results = []

    for i in range(0, len(coroutines), limit):
        chunk = coroutines[i : i + limit]
        chunk_results = await asyncio.gather(*chunk, return_exceptions=return_exceptions)
        results.extend(chunk_results)

        # Small delay between chunks to prevent overwhelming the system
        if i + limit < len(coroutines):
            await asyncio.sleep(0.1)

    return results
