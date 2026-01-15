"""Event handling module."""

from app.events.consumer import EventConsumer, run_consumer

__all__ = [
    "EventConsumer",
    "run_consumer",
]
