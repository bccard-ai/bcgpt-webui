"""Lazy-initialising span processor for OpenTelemetry.

Provides :class:`LazyBatchSpanProcessor` which defers the background worker
thread until the first span is actually emitted, reducing idle resource
consumption in environments that may not generate telemetry traffic.
"""

from __future__ import annotations

import threading

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class LazyBatchSpanProcessor(BatchSpanProcessor):
    """A :class:`BatchSpanProcessor` that lazily starts its worker thread.

    On construction the parent's worker thread is immediately joined so
    that no resources are consumed while idle.  The thread is recreated
    on the first call to :meth:`on_end`.

    Args:
        *args: Positional arguments forwarded to :class:`BatchSpanProcessor`.
        **kwargs: Keyword arguments forwarded to :class:`BatchSpanProcessor`.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.done = True
        with self.condition:
            self.condition.notify_all()
        self.worker_thread.join()
        self.done = False
        self.worker_thread = None

    def on_end(self, span: ReadableSpan) -> None:
        """Process a completed span, starting the worker if necessary.

        Args:
            span: The finished :class:`ReadableSpan` to export.
        """
        if self.worker_thread is None:
            self.worker_thread = threading.Thread(
                name=self.__class__.__name__, target=self.worker, daemon=True
            )
            self.worker_thread.start()
        super().on_end(span)

    def shutdown(self) -> None:
        """Stop the worker thread and shut down the underlying exporter."""
        self.done = True
        with self.condition:
            self.condition.notify_all()
        if self.worker_thread:
            self.worker_thread.join()
        self.span_exporter.shutdown()
