"""Project-specific exceptions."""


class ConfigurationError(ValueError):
    """Raised when required project configuration is invalid or unavailable."""


class SourceRetrievalError(RuntimeError):
    """Raised when an approved external source cannot be retrieved."""


class SourceResponseError(ValueError):
    """Raised when a source response cannot be parsed into its documented contract."""


class PersistenceError(RuntimeError):
    """Raised when validated raw observations cannot be stored."""


class SchemaMigrationError(RuntimeError):
    """Raised when a schema migration would risk existing research lineage."""


class ProcessingValidationError(ValueError):
    """Raised when a raw observation cannot satisfy a processing contract."""


class ProcessingPersistenceError(RuntimeError):
    """Raised when a processed observation and its lineage cannot be stored."""


class DashboardReadError(RuntimeError):
    """Raised when a read-only dashboard projection cannot query the database."""


class DashboardLineageError(RuntimeError):
    """Raised when dashboard selection finds incomplete or ambiguous lineage."""
