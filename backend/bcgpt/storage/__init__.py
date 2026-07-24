def __getattr__(name):
    _mapping = {
        "AzureStorageProvider": ".provider",
        "GCSStorageProvider": ".provider",
        "LocalStorageProvider": ".provider",
        "S3StorageProvider": ".provider",
        "Storage": ".provider",
        "StorageProvider": ".provider",
        "get_storage_provider": ".provider",
        "log": ".provider",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
