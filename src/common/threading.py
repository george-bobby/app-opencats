import asyncio
import math
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TypeVar

from apps.odooinventory.config.settings import settings


T = TypeVar("T")


def get_optimal_thread_count(total_items: int, max_threads: int | None = None) -> int:
    """
    Determine optimal number of threads based on system capabilities and data size.

    Args:
        total_items: Total number of items to process
        max_threads: Maximum threads allowed (optional override)

    Returns:
        Optimal number of threads to use
    """
    if settings.DISABLE_THREADING:
        return 1

    # Get system CPU count, fallback to 2 if unable to determine
    cpu_count = os.cpu_count() or 2

    # Default max threads is CPU count, but not more than 4 to avoid overwhelming Odoo
    default_max = min(cpu_count, 4)
    actual_max = max_threads if max_threads is not None else default_max

    # Don't use more threads than items to process
    optimal_threads = min(actual_max, total_items)

    # Minimum of 1 thread, maximum of what we calculated
    return max(1, optimal_threads)


def split_into_chunks[T](items: list[T], num_chunks: int) -> list[list[T]]:
    """Split items list into equal chunks"""
    if num_chunks <= 1:
        return [items]

    chunk_size = math.ceil(len(items) / num_chunks)
    chunks = []

    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)

    return chunks


def run_async_in_thread(async_func: Callable, *args, **kwargs) -> Any:
    """
    Wrapper to run async function in a thread.

    Args:
        async_func: The async function to run
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the async function
    """
    try:
        return asyncio.run(async_func(*args, **kwargs))
    except Exception as e:
        raise ValueError(f"Thread execution failed: {e}")


async def process_in_parallel(items: list[T], async_processor: Callable[[list[T]], Any], max_threads: int | None = None, fallback_to_single: bool = True) -> list[Any]:
    """
    Process items in parallel using optimal threading with fallback.

    Args:
        items: List of items to process
        async_processor: Async function that processes a chunk (chunk) -> result
        max_threads: Maximum threads to use (None for auto-detect)
        fallback_to_single: Whether to fallback to single-threaded processing on error

    Returns:
        List of results from all processors
    """
    if not items:
        return []

    # Determine optimal number of threads
    optimal_threads = get_optimal_thread_count(len(items), max_threads)

    results = []

    if optimal_threads == 1:
        # Single-threaded processing
        try:
            result = await async_processor(items)
            results.append(result)
        except Exception as e:
            raise ValueError(f"Single-threaded processing failed: {e}")
    else:
        # Multi-threaded processing with fallback
        try:
            # Split items into optimal chunks
            chunks = split_into_chunks(items, num_chunks=optimal_threads)

            with ThreadPoolExecutor(max_workers=optimal_threads) as executor:
                # Submit all chunks for processing
                future_to_chunk = {executor.submit(run_async_in_thread, async_processor, chunk): (chunk, i) for i, chunk in enumerate(chunks)}

                # Collect results as they complete
                for future in as_completed(future_to_chunk):
                    chunk, chunk_id = future_to_chunk[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        raise ValueError(f"Thread {chunk_id}: Failed to process chunk: {e}")

        except Exception:
            if fallback_to_single:
                # Fallback to single-threaded processing
                try:
                    result = await async_processor(items)
                    results.append(result)
                except Exception as fallback_error:
                    raise ValueError(f"Fallback single-threaded processing also failed: {fallback_error}")
            else:
                raise

    return results
