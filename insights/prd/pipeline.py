"""Thin CLI for the PRD design graph. All orchestration lives in agents/prd-agent.yaml and
insights/prd/runner.py; every LLM call goes through the governed gateway (no provider SDK is
imported anywhere in the PRD path). `--resume <run_id>` continues an interrupted run from its
SQLite checkpoint under <output>/checkpoints/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from insights.config import environment
from insights.prd.runner import (  # noqa: F401  (re-exported for callers and the pilot tooling)
    DesignRuntime,
    PrdRunner,
    read_catalog_schema,
    read_csv_schema,
    read_document,
)

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="PRD .docx, .md, or .txt")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "prd-run")
    parser.add_argument("--csv-dir", type=Path, default=ROOT / "rain-api" / "rain_source_csvs_prd")
    parser.add_argument("--catalog", type=Path, default=ROOT / "apps" / "rain" / "catalog" / "snapshot.json")
    parser.add_argument("--existing-upper", type=Path, help="Existing upper-ontology JSON to reconcile")
    parser.add_argument(
        "--scenario-db-state", type=Path,
        help="Optional SYNTHETIC database-state YAML/JSON; the live database is never used",
    )
    parser.add_argument("--resume", metavar="RUN_ID", help="Resume an interrupted run from its checkpoint")
    args = parser.parse_args(argv)
    try:
        env_path = ROOT / ".env"
        if not env_path.is_file():
            env_path = ROOT / "rain-api" / ".env"
        runner = PrdRunner(environment(env_path))

        def stdout_event(event) -> None:
            # one JSON line per typed event; the API server relays these over SSE
            print("EVENT " + event.model_dump_json(), flush=True)

        report = runner.run(
            args.input.resolve(),
            args.output.resolve(),
            csv_dir=args.csv_dir.resolve(),
            catalog_path=args.catalog.resolve(),
            existing_upper_path=args.existing_upper.resolve() if args.existing_upper else None,
            db_state_path=args.scenario_db_state.resolve() if args.scenario_db_state else None,
            run_id=args.resume,
            resume=bool(args.resume),
            event_sink=stdout_event,
        )
    except Exception as exc:
        print(f"PRD pipeline failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    usage = report.get("llm_usage") or {}
    print(f"PRD artifacts written to {args.output.resolve()}")
    print(
        f"run {report['run_id']}: {'completed' if report['completed'] else 'FAILED'}; "
        f"gateway tokens {usage.get('total', 0):,} of {usage.get('run_token_budget', 0):,} budget"
    )
    if not report["completed"]:
        failure = report.get("failure") or {}
        print(
            f"failure: {failure.get('reason')} at {failure.get('step_id')}: {failure.get('message')}"
            if failure
            else "the run escalated; see run-report.json",
            file=sys.stderr,
        )
        print(f"resume with: python -m insights.prd.pipeline --input {args.input} "
              f"--output {args.output} --resume {report['run_id']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
