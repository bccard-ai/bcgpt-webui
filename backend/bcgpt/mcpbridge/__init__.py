"""MCP (Model Context Protocol) integration — Streamable HTTP client + bridge.

Security posture (locked by design):
- HTTP/SSE remote only (NO stdio; no process spawning).
- Sampling stays at the SDK default-refuse (we never pass sampling_callback or
  sampling_capabilities to ClientSession).
- Outbound server URLs must pass the admin MCP_ALLOWED_HOSTS allow-host.
- Built-in servers run in-process (mounted ASGI sub-apps), loopback only.
"""
