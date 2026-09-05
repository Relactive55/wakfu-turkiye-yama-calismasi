class AutomationError(RuntimeError):
    """An expected safety failure. Callers must stop without changing state."""


class VerificationError(AutomationError):
    """Downloaded or parsed upstream data did not match its declared integrity data."""


class TranslationProviderUnavailable(AutomationError):
    """A required translation provider could not be loaded; stop fail-closed."""


class SchemaError(AutomationError):
    """The CDN manifest did not have the narrowly supported shape."""
