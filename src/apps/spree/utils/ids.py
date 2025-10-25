class GlobalIdGenerator:
    _counters = {}  # Class variable to store global state  # noqa: RUF012

    def __init__(self, string):
        self._string = string
        # Don't initialize counter here - wait for get_next_id()

    def get_next_id(self):
        """Get the next incremental ID for this string."""
        # Initialize counter only when first called
        if self._string not in GlobalIdGenerator._counters:
            GlobalIdGenerator._counters[self._string] = 0

        GlobalIdGenerator._counters[self._string] += 1
        return GlobalIdGenerator._counters[self._string]

    def get_current_count(self):
        """Get current count without incrementing."""
        return GlobalIdGenerator._counters.get(self._string, 0)

    def reset(self):
        """Reset the counter for this string back to 0."""
        if self._string in GlobalIdGenerator._counters:
            GlobalIdGenerator._counters[self._string] = 0

    def get_string(self):
        """Get the string this generator is bound to."""
        return self._string

    @classmethod
    def reset_all(cls):
        """Reset all counters for all strings."""
        cls._counters.clear()

    @classmethod
    def get_all_counters(cls):
        """Get a copy of all current counters."""
        return cls._counters.copy()
