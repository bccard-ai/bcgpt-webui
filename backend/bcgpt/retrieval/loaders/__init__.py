def __getattr__(name):
    _mapping = {
        "ALLOWED_NETLOCS": ".youtube",
        "ALLOWED_SCHEMES": ".youtube",
        "DoclingLoader": ".main",
        "Loader": ".main",
        "TavilyLoader": ".tavily",
        "TikaLoader": ".main",
        "YoutubeLoader": ".youtube",
        "_parse_video_id": ".youtube",
        "known_source_ext": ".main",
        "log": ".main",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
