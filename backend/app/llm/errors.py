class LLMUnavailableError(RuntimeError):
    """The configured LLM / embedding service cannot be reached or failed."""


class LLMRateLimitedError(LLMUnavailableError):
    """The hosted LLM provider rejected the request because of rate limits."""
