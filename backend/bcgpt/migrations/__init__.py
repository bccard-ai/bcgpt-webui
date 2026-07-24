def __getattr__(name):
    _mapping = {
        "DB_URL": ".env",
        "config": ".env",
        "get_existing_tables": ".util",
        "get_revision_id": ".util",
        "run_migrations_offline": ".env",
        "run_migrations_online": ".env",
        "target_metadata": ".env",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
