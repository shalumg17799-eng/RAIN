"""Contracts as code: pydantic models for every boundary in the Insights Server.

request/response (wire), principal and app profile (server-side only), run state, events and audit,
skill manifest and agent definition (configuration), gateway seam. JSON Schemas are exported to
docs/contracts/ by `python -m insights.contracts.export`.
"""
