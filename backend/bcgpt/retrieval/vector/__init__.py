def __getattr__(name):
    _mapping = {
        "GetResult": ".main",
        "SearchResult": ".main",
        "VectorItem": ".main",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
