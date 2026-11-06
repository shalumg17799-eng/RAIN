"""Cross-platform entry point: `python -m insights.cli test|lint|eval|run|verify`.

`make` is not assumed anywhere. A Makefile may wrap these commands, nothing more.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any

EXIT_NOT_IMPLEMENTED = 3
EXIT_TIMEOUT = 124
DEFAULT_SLOW_SECONDS = 300
"""Past this, `test` warns that the run is slow. It keeps waiting while output still arrives."""
DEFAULT_STALL_SECONDS = 120
"""No output for this long stops the run. pytest's faulthandler dumps stacks after 120 s on one
test, and that dump is output, so a hanging test is reported before it is stopped."""
SLOWEST_TESTS = 10
WARN_EVERY_SECONDS = 60.0


def repo_root() -> Path:
    """Find the project root from either a conventional package or this flat checkout."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() or all(
            (candidate / name).is_dir() for name in ("insights", "agents", "skills")
        ):
            return candidate
    raise RuntimeError("not a source checkout: project metadata and runtime directories are missing")


def _run(
    cmd: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> int:
    """Run a command. Raises subprocess.TimeoutExpired (after killing it) if `timeout` passes."""
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd or repo_root(), env=env, check=False, timeout=timeout
    ).returncode


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _pump(stream: IO[bytes], sink: Any, seen: list[float]) -> None:
    """Copy a child's output to ours as it arrives, noting when the last bytes came."""
    encoding = getattr(sink, "encoding", None) or "utf-8"
    while True:
        chunk = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
        if not chunk:
            break
        seen[0] = time.monotonic()
        sink.write(chunk.decode(encoding, errors="replace"))
        sink.flush()


def run_watched(
    cmd: Sequence[str | Path],
    *,
    slow_after: float | None,
    stall_after: float | None,
    cwd: Path | None = None,
    warn_every: float = WARN_EVERY_SECONDS,
) -> int:
    """Run a command with its output passed through. Warn when slow; stop it only when it stalls.

    After `slow_after` seconds a warning is printed (and again every `warn_every` seconds), but the
    run goes on as long as output keeps arriving. After `stall_after` seconds without any output
    the command is killed and EXIT_TIMEOUT returned. None disables either.
    """
    started = time.monotonic()
    seen = [started]
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        cwd=cwd or repo_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # stdout/stderr are PIPEs, so neither is None; the threads copy them through as output arrives.
    pumps = [
        threading.Thread(target=_pump, args=(proc.stdout, sys.stdout, seen), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, sys.stderr, seen), daemon=True),
    ]
    for pump in pumps:
        pump.start()
    warned_at: float | None = None
    try:
        while True:
            try:
                code = proc.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                pass
            now = time.monotonic()
            elapsed, quiet = now - started, now - seen[0]
            if stall_after and quiet >= stall_after:
                proc.kill()
                proc.wait()
                print(
                    f"test: STOPPED after {elapsed:.0f}s: no output for {quiet:.0f}s. Something is "
                    "hanging; do not wait for it (see the faulthandler output above, if any).",
                    file=sys.stderr,
                )
                return EXIT_TIMEOUT
            if (
                slow_after
                and elapsed >= slow_after
                and (warned_at is None or now - warned_at >= warn_every)
            ):
                print(
                    f"test: SLOW: {elapsed:.0f}s elapsed, past the {slow_after:.0f}s mark, but "
                    f"output arrived {quiet:.0f}s ago: still progressing, not stopping it",
                    file=sys.stderr,
                )
                warned_at = now
    finally:
        for pump in pumps:
            pump.join(timeout=5)
    return code


def cmd_test(args: argparse.Namespace) -> int:
    """Run pytest listing the slowest tests; warn when slow, stop only when nothing happens."""
    cmd: list[str] = [sys.executable, "-m", "pytest", *args.extra]
    if not any(str(a).startswith("--durations") for a in args.extra):
        cmd.append(f"--durations={SLOWEST_TESTS}")
    started = time.monotonic()
    code = run_watched(
        cmd, slow_after=args.max_seconds or None, stall_after=args.stall_seconds or None
    )
    elapsed = time.monotonic() - started
    slow = f"slow after {args.max_seconds}s" if args.max_seconds else "no slow mark"
    stall = (
        f"stopped after {args.stall_seconds}s of silence" if args.stall_seconds else "never stopped"
    )
    print(f"test: total wall-clock time {elapsed:.1f}s ({slow}; {stall})")
    return code


def cmd_lint(args: argparse.Namespace) -> int:
    check = [sys.executable, "-m", "ruff", "check", "."]
    fmt = [sys.executable, "-m", "ruff", "format", "."]
    if args.fix:
        check.append("--fix")
    else:
        fmt.append("--check")
    return _run(check) or _run(fmt)


def cmd_eval(args: argparse.Namespace) -> int:
    """Report the NFCU measurements and say plainly what did not run; --gate fails without a model.
    The safety suites and the DB-isolation proof run under `python -m insights.cli test`."""
    from insights.eval.cli import main as eval_main

    return eval_main(args.extra)


def cmd_run(args: argparse.Namespace) -> int:
    """Start the HTTP server. Refuses to start without API keys (exit 2); there is no open mode."""
    from insights.api.server import serve

    return serve(host=args.host, port=args.port)


def cmd_verify(_: argparse.Namespace) -> int:
    """Lint and test inside a brand-new venv built only from requirements-dev.lock."""
    root = repo_root()
    tmp = Path(tempfile.mkdtemp(prefix="insights-verify-"))
    try:
        venv = tmp / "venv"
        py = _venv_python(venv)
        env = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        steps: list[list[str | Path]] = [
            [sys.executable, "-m", "venv", venv],
            [py, "-m", "pip", "install", "--quiet", "-r", root / "requirements-dev.lock"],
            [py, "-m", "pip", "install", "--quiet", "--no-deps", "-e", root],
            [py, "-m", "insights.cli", "lint"],
            [py, "-m", "insights.cli", "test"],
        ]
        for step in steps:
            rc = _run(step, env=env)
            if rc:
                print(f"verify: FAILED at: {' '.join(str(s) for s in step)}", file=sys.stderr)
                return rc
        print("verify: clean-venv lint and test passed")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m insights.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_test = sub.add_parser("test", help="run pytest (extra arguments are passed through)")
    p_test.add_argument(
        "--max-seconds",
        type=int,
        default=DEFAULT_SLOW_SECONDS,
        help=(
            f"warn that the run is slow after N seconds (default {DEFAULT_SLOW_SECONDS}; "
            "0 = never); the run goes on while output keeps arriving"
        ),
    )
    p_test.add_argument(
        "--stall-seconds",
        type=int,
        default=DEFAULT_STALL_SECONDS,
        help=(
            f"stop the run after N seconds without any output (default {DEFAULT_STALL_SECONDS}; "
            f"0 = never); exit code {EXIT_TIMEOUT}"
        ),
    )
    p_test.set_defaults(func=cmd_test)

    p_lint = sub.add_parser("lint", help="ruff check and ruff format --check")
    p_lint.add_argument("--fix", action="store_true", help="apply fixes and reformat")
    p_lint.set_defaults(func=cmd_lint)

    sub.add_parser("eval", help="golden set, adversarial and leakage suites, gates").set_defaults(
        func=cmd_eval
    )
    p_run = sub.add_parser("run", help="start the API server (refuses to start without API keys)")
    p_run.add_argument("--host", default=None, help="default INSIGHTS_HOST or 127.0.0.1")
    p_run.add_argument("--port", type=int, default=None, help="default INSIGHTS_PORT or 8080")
    p_run.set_defaults(func=cmd_run)
    sub.add_parser("verify", help="lint and test in a fresh venv from the lock file").set_defaults(
        func=cmd_verify
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra and args.command not in ("test", "eval"):
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.extra = extra
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
