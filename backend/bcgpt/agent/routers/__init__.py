"""FastAPI routers for the agent subsystem.

Mounted in ``main.py``::

    app.include_router(agents.router,      prefix="/api/v1/agents", tags=["agents"])
    app.include_router(multi_agent.router, prefix="/api/v1/agents/multi-agent", tags=["multi-agent"])
    app.include_router(skills.router,      prefix="/api/v1/skills", tags=["skills"])
"""
