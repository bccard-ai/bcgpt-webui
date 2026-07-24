def __getattr__(name):
    _mapping = {
        "branch_labels": ".922e7a387820_add_group_table",
        "depends_on": ".922e7a387820_add_group_table",
        "down_revision": ".922e7a387820_add_group_table",
        "downgrade": ".c0fbf31ca0db_update_file_table",
        "revision": ".922e7a387820_add_group_table",
        "upgrade": ".c0fbf31ca0db_update_file_table",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
