"""Build an app's catalog snapshot from its data source:  python -m insights.catalog.build [app]

Run by an operator with the admin login (never at request time). It writes the file named by the
app profile (`catalog.path`) and, if one already exists, lists what changed since: that list is the
catalog-drift report (design report 5.2, "nightly diff against the source catalog").
"""

import sys

import psycopg

from insights.catalog.snapshot import (
    CatalogError,
    diff_snapshots,
    introspect_postgres,
    load_snapshot,
    make_snapshot,
    write_snapshot,
)
from insights.config import environment
from insights.contracts.profile import load_app_profile
from insights.datasources.pg_setup import SetupError, admin_connection


def main(argv: list[str]) -> int:
    from insights.cli import repo_root

    root = repo_root()
    app_dir = root / "apps" / (argv[0] if argv else "nfcu")
    app = load_app_profile(app_dir / "app.yaml")
    source = app.datasources[0]
    if source.kind != "postgres":
        sys.stderr.write("only PostgreSQL introspection is implemented so far\n")
        return 2
    try:
        with admin_connection(app, environment(root / ".env")) as conn:
            tables = introspect_postgres(conn, source.default_schema or "public")
    except (psycopg.Error, SetupError) as exc:
        sys.stderr.write(f"could not read the catalog: {type(exc).__name__}\n")
        return 1
    snapshot = make_snapshot(
        source_id=source.id,
        dialect=app.dialect,
        schema_name=source.default_schema or "public",
        tables=tables,
    )
    target = app_dir / app.catalog.path
    if target.exists():
        try:
            changes = diff_snapshots(load_snapshot(target), snapshot)
        except CatalogError:
            changes = ["the existing snapshot was unreadable"]
        sys.stdout.write(
            "changes since the last snapshot: " + (", ".join(changes) or "none") + "\n"
        )
    write_snapshot(snapshot, target)
    sys.stdout.write(
        f"wrote {target.relative_to(root)} (version {snapshot.version}, "
        f"{len(snapshot.tables)} tables)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
