def __getattr__(name):
    _mapping = {
        "Base": ".db",
        "CustomReconnectMixin": ".wrappers",
        "JSONField": ".db",
        "PeeweeConnectionState": ".wrappers",
        "ReconnectingPostgresqlDatabase": ".wrappers",
        "SQLALCHEMY_DATABASE_URL": ".db",
        "Session": ".db",
        "SessionLocal": ".db",
        "db_state": ".wrappers",
        "db_state_default": ".wrappers",
        "engine": ".db",
        "get_db": ".db",
        "get_session": ".db",
        "handle_peewee_migration": ".db",
        "log": ".wrappers",
        "metadata_obj": ".db",
        "register_connection": ".wrappers",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
