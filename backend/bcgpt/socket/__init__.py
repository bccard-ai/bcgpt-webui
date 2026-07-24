def __getattr__(name):
    _mapping = {
        "RedisDict": ".utils",
        "RedisLock": ".utils",
        "TIMEOUT_DURATION": ".main",
        "app": ".main",
        "channel_events": ".main",
        "connect": ".main",
        "disconnect": ".main",
        "get_active_status_by_user_id": ".main",
        "get_event_call": ".main",
        "get_event_caller": ".main",
        "get_event_emitter": ".main",
        "get_models_in_use": ".main",
        "get_user_id_from_session_pool": ".main",
        "get_user_ids_from_room": ".main",
        "join_channel": ".main",
        "log": ".main",
        "periodic_usage_pool_cleanup": ".main",
        "sio": ".main",
        "usage": ".main",
        "user_join": ".main",
        "user_list": ".main",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
