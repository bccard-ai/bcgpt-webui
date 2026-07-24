def __getattr__(name):
    _mapping = {
        "EXA_API_BASE": ".exa",
        "ExaResult": ".exa",
        "RAG_WEB_LOADER_ENGINES": ".utils",
        "RateLimitMixin": ".utils",
        "SafeFireCrawlLoader": ".utils",
        "SafePlaywrightURLLoader": ".utils",
        "SafeTavilyLoader": ".utils",
        "SafeWebBaseLoader": ".utils",
        "SearchResult": ".main",
        "URLProcessingMixin": ".utils",
        "_is_blocked_ip": ".utils",
        "_parse_response": ".bocha",
        "extract_metadata": ".utils",
        "get_filtered_results": ".main",
        "get_web_loader": ".utils",
        "log": ".serply",
        "main": ".bing",
        "resolve_hostname": ".utils",
        "safe_validate_urls": ".utils",
        "search_bing": ".bing",
        "search_bocha": ".bocha",
        "search_brave": ".brave",
        "search_duckduckgo": ".duckduckgo",
        "search_exa": ".exa",
        "search_google_pse": ".google_pse",
        "search_jina": ".jina_search",
        "search_kagi": ".kagi",
        "search_mojeek": ".mojeek",
        "search_naver": ".naver",
        "search_perplexity": ".perplexity",
        "search_searchapi": ".searchapi",
        "search_searxng": ".searxng",
        "search_serpapi": ".serpapi",
        "search_serper": ".serper",
        "search_serply": ".serply",
        "search_serpstack": ".serpstack",
        "search_tavily": ".tavily",
        "validate_url": ".utils",
        "verify_ssl_cert": ".utils",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
