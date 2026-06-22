"""Application-specific exceptions with safe, manager-facing semantics."""


class CopilotError(Exception):
    """Base error for failures that the API can translate safely."""


class DriverNotFoundError(CopilotError):
    """Raised when a driver cannot be resolved from an ID, name, or conversation state."""


class AmbiguousDriverError(CopilotError):
    """Raised when a name query matches more than one driver."""


class ToolUnavailableError(CopilotError):
    """Raised when a required data or incentive tool cannot provide trustworthy evidence."""


class ConfigurationError(CopilotError):
    """Raised when a selected integration lacks mandatory configuration."""
