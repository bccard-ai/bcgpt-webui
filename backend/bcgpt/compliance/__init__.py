"""
AI Compliance Module — regulatory gap closure for Korean AI Basic Act,
FSC Financial AI Guidelines, EU AI Act, and ISO/IEC 42001.

Sub-packages:
  - ``models``:     DB tables (inventory, AIIA, incidents, fairness, provenance, vendor, DSAR)
  - ``routers``:    FastAPI admin/user endpoints
  - ``fairness``:   Bias-testing metrics (pure numpy, no sklearn dependency)
  - ``hitl``:       Human-in-the-loop approval gate for the DAG workflow engine
"""
