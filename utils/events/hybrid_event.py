"""Allows .NET style subscribable events for both coroutines and blocking functions."""

import asyncio
from typing import Any, Callable

from .async_event import AsyncEvent
from .sync_event import SyncEvent


class HybridEvent:
    """Allows .NET style subscribable events for both coroutines and blocking functions."""

    def __init__(self) -> None:
        self._async_event = AsyncEvent()
        self._sync_event = SyncEvent()

    def __iadd__(self, handler: Callable[..., Any]) -> "HybridEvent":
        """Subscribe a handler through the '+=' operator."""
        if asyncio.iscoroutinefunction(handler):
            self._async_event += handler

        else:
            self._sync_event += handler

        return self

    def __isub__(self, handler: Callable[..., Any]) -> "HybridEvent":
        """Unsubscribe a handler through the '-=' operator."""
        if asyncio.iscoroutinefunction(handler):
            self._async_event -= handler

        else:
            self._sync_event -= handler

        return self

    async def fire(self, *args: Any, **kwargs: Any) -> None:
        """Call all subscribed handlers with given arguments."""
        self._sync_event.fire(*args, **kwargs)
        await self._async_event.fire(*args, **kwargs)

    def clear(self) -> None:
        """Remove all subscribed handlers"""
        self._sync_event.clear()
        self._async_event.clear()
