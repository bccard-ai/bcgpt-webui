def __getattr__(name):
    _mapping = {
        "migrate": ".004_add_archived",
        "migrate_external": ".001_initial_schema",
        "migrate_modelfile_to_model": ".010_migrate_modelfiles_to_models",
        "migrate_sqlite": ".001_initial_schema",
        "move_data_back_to_modelfile": ".010_migrate_modelfiles_to_models",
        "recreate_modelfile_table": ".010_migrate_modelfiles_to_models",
        "rollback": ".004_add_archived",
        "rollback_external": ".005_add_updated_at",
        "rollback_sqlite": ".005_add_updated_at",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
