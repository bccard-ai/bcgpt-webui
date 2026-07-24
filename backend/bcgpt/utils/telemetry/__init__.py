def __getattr__(name):
    _mapping = {
        "Instrumentor": ".instrumentors",
        "LazyBatchSpanProcessor": ".exporters",
        "SPAN_DB_TYPE": ".constants",
        "SPAN_DURATION": ".constants",
        "SPAN_ERROR_TYPE": ".constants",
        "SPAN_REDIS_TYPE": ".constants",
        "SPAN_SQL_EXPLAIN": ".constants",
        "SPAN_SQL_STR": ".constants",
        "SpanAttributes": ".constants",
        "aiohttp_request_hook": ".instrumentors",
        "aiohttp_response_hook": ".instrumentors",
        "httpx_async_request_hook": ".instrumentors",
        "httpx_async_response_hook": ".instrumentors",
        "httpx_request_hook": ".instrumentors",
        "httpx_response_hook": ".instrumentors",
        "logger": ".instrumentors",
        "redis_request_hook": ".instrumentors",
        "requests_hook": ".instrumentors",
        "response_hook": ".instrumentors",
        "setup": ".setup",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
