def __getattr__(name):
    _mapping = {
        "ComfyUIGenerateImageForm": ".comfyui",
        "ComfyUINodeInput": ".comfyui",
        "ComfyUIWorkflow": ".comfyui",
        "comfyui_generate_image": ".comfyui",
        "default_headers": ".comfyui",
        "get_history": ".comfyui",
        "get_image": ".comfyui",
        "get_image_url": ".comfyui",
        "get_images": ".comfyui",
        "log": ".comfyui",
        "queue_prompt": ".comfyui",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
