"""`python -m insights.cli eval`: report what can be measured, and say plainly what cannot.

There is no replay and no fake answer here. Until a model is configured every model-dependent
result is reported as "not run: no model", never simulated. The real NFCU measurements -- router
accuracy on the data questions, KAG-vs-bypass sliver recall@k, and execution of the Data Factory's
SQL through our executor against its verified figures -- are implemented in P2/P3. The adversarial
and leakage safety suites, and the 245-probe NFCU database isolation proof, run as part of
`python -m insights.cli test` (see tests/fixtures/suites and tests/datasources/test_nfcu_*).

`--gate` is honest: because no model-dependent measurement actually runs without a model, the gate
CANNOT pass and exits non-zero. A passing gate must never be readable as evidence of safety; the
safety gates are the suites under `python -m insights.cli test`, not this command.

Exit codes: 0 the report was produced (no --gate); 1 --gate but the gate could not pass (nothing
model-dependent ran); 2 the app or its configuration could not be loaded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from insights.catalog.snapshot import CatalogError, load_snapshot
from insights.cli import repo_root
from insights.config import environment
from insights.contracts.profile import ProfileError, load_app_profile
from insights.gateway.config import GatewayConfig

NOT_RUN = "not run: no model"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m insights.cli eval", description=__doc__)
    parser.add_argument("--app", default="nfcu")
    parser.add_argument("--split", default="all", choices=["dev", "held_out", "all"])
    parser.add_argument(
        "--suite", default="all", choices=["all", "golden", "adversarial", "leakage"]
    )
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    out = sys.stdout

    root = repo_root()
    environ = environment(root / ".env")
    try:
        app = load_app_profile(root / "apps" / args.app / "app.yaml")
        load_snapshot(root / "apps" / args.app / app.catalog.path)
    except (ProfileError, CatalogError, FileNotFoundError, ValueError) as exc:
        out.write(f"eval: cannot load app {args.app!r}: {type(exc).__name__}: {exc}\n")
        return 2

    provider = GatewayConfig.from_env(environ).provider
    out.write(f"== evaluation: app {app.id}\n")
    out.write(f"model provider: {provider}\n")
    out.write(f"router accuracy (data questions):           {NOT_RUN}\n")
    out.write(f"SQL generation / execution accuracy:        {NOT_RUN}\n")
    out.write(f"judge / narrative:                          {NOT_RUN}\n")
    out.write(
        "sliver recall@k (KAG vs bypass):            implemented in P2 (needs the NFCU graph)\n"
    )
    out.write(
        "adversarial + leakage safety suites:        run under `python -m insights.cli test` "
        "(tests/fixtures/suites)\n"
    )
    out.write(
        "NFCU database isolation (245 probes):       run under `python -m insights.cli test` "
        "(tests/datasources/test_nfcu_isolation.py)\n"
    )
    # a model-dependent measurement actually ran only if a model is configured AND the live
    # evaluation is wired; neither is true yet, so nothing model-dependent ran.
    ran_model_evaluation = False
    if provider != "none":
        out.write("\nA model is configured; the real NFCU measurements are implemented in P2/P3.\n")
    if args.gate:
        if not ran_model_evaluation:
            out.write(
                "\nGATE: FAILED -- no model-dependent measurement ran"
                f" ({NOT_RUN if provider == 'none' else 'live evaluation pending'}). "
                "A passing gate here is never evidence of safety; the safety gates are the suites "
                "under `python -m insights.cli test`.\n"
            )
            return 1
        out.write("\nGATE: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
