"""Allows .NET style subscribable events."""

from typing import Any, Callable


class SyncEvent:
    """Allows .NET style subscribable events."""

    def __init__(self) -> None:
        self._handlers: list[Callable[..., Any]] = []

    def __iadd__(self, handler: Callable[..., Any]) -> "SyncEvent":
        """Subscribe a handler through the '+=' operator."""
        if handler not in self._handlers:
            self._handlers.append(handler)

        return self

    def __isub__(self, handler: Callable[..., Any]) -> "SyncEvent":
        """Unsubscribe a handler through the '-=' operator."""
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass

        return self

    def fire(self, *args: Any, **kwargs: Any) -> None:
        """Call all subscribed handlers with given arguments."""
        for handler in self._handlers:
            handler(*args, **kwargs)

    def clear(self) -> None:
        """Remove all subscribed handlers"""
        self._handlers = []
