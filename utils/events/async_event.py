"""Allows .NET style subscribable events for coroutines."""

import asyncio
from typing import Any, Callable


class AsyncEvent:
    """Allows .NET style subscribable events for coroutines."""

    def __init__(self) -> None:
        self._handlers: list[Callable[..., Any]] = []

    def __iadd__(self, handler: Callable[..., Any]) -> "AsyncEvent":
        """Subscribe a handler through the '+=' operator."""
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError("Sync handler provided to AsyncEvent")

        if handler not in self._handlers:
            self._handlers.append(handler)

        return self

    def __isub__(self, handler: Callable[..., Any]) -> "AsyncEvent":
        """Unsubscribe a handler through the '-=' operator."""
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass

        return self

    async def fire(self, *args: Any, **kwargs: Any) -> None:
        """Call all subscribed handlers with given arguments."""
        if not self._handlers:
            return None

        await asyncio.gather(*(handler(*args, **kwargs) for handler in self._handlers))

    def clear(self) -> None:
        """Remove all subscribed handlers"""
        self._handlers = []
