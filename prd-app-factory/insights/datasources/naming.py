"""Names of the database objects the sample setup creates and the adapter selects.

One module, so the setup script and the adapter cannot drift apart. Every name derives from a role
in the app profile (a validated lower-case identifier), so none of them carries free text.
"""

GUC_PREFIX = "insights"
"""Session variables look like `insights.branch_id`: set by the adapter, read by RLS."""

PREDICATE_ROLE = "insights_sp_pred"


def per_user_role(app_role: str) -> str:
    return f"insights_{app_role}"


def per_user_view_schema(app_role: str) -> str:
    return f"v_{app_role}"


def views_role(app_role: str) -> str:
    return f"insights_sp_{app_role}"


def views_schema(app_role: str) -> str:
    return f"sp_{app_role}"


def guc(name: str) -> str:
    return f"{GUC_PREFIX}.{name}"
