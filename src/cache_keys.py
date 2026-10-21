def http_request_cache_key_builder(
    func, prefix, *, request, response, args, kwargs
) -> str:
    route = f"{func.__module__}.{func.__qualname__}"
    query = request.url.query if request is not None else ""
    path = request.url.path if request is not None else ""
    return f"{prefix}:{route}:{path}?{query}"
