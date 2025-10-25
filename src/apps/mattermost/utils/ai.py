from logging import WARNING, getLogger

import instructor
from anthropic import APIError, AsyncAnthropic, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.mattermost.config.settings import settings
from common.logger import logger


getLogger("anthropic._base_client").setLevel(WARNING)


# Create the base client
base_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Create instructor client
instructor_client = instructor.from_anthropic(
    base_client,
    mode=instructor.Mode.ANTHROPIC_JSON,
)

# Store the original create method
original_create = instructor_client.chat.completions.create


# Create retry wrapper
@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=15),
    after=lambda retry_state: logger.warning(f"Claude API attempt {retry_state.attempt_number} failed. Trying again...") if retry_state.outcome and retry_state.outcome.failed else None,
)
async def create_with_retry(*args, **kwargs):
    """Create completion with retry logic."""
    return await original_create(*args, **kwargs)


# Replace the create method with retry-enabled version
instructor_client.chat.completions.create = create_with_retry
