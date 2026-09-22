"""Runtime drivers only translate the common contract."""


class RuntimeFailure(Exception):
    """An expected runtime failure that Conductor may retry."""
