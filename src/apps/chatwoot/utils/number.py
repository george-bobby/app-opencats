import random


def get_random_int(min_value: int, max_value: int) -> int:
    """
    Generate a random integer between min_value and max_value (inclusive).

    Args:
        min_value (int): The minimum value of the range.
        max_value (int): The maximum value of the range.

    Returns:
        int: A random integer within the specified range.
    """
    return random.randint(min_value, max_value)
