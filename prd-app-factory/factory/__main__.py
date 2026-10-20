"""PRD-to-App Factory command line.

  python -m factory run      --app <id> --prd <file.docx|.md> [--data <csv folder>] [--auto-approve]
  python -m factory status   --app <id>
  python -m factory approve  --app <id> --gate A|B|C [--by NAME] [--note TEXT]
  python -m factory retry    --app <id> [--by NAME] [--note TEXT]     # re-run a blocked stage
  python -m factory resume   --app <id>
  python -m factory serve    --app <id> [--port 8080]                 # the generated app
  python -m factory portal   [--port 8090]                            # upload PRDs, follow runs, approve gates
  python -m factory worker   --agent requirements|data|knowledge|app|release [--loop]
  python -m factory provision --app <id>                              # load data + governance into PG_*
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os

from factory import coordinator
from factory.apppack import AppPack


def main() -> None:
    p = argparse.ArgumentParser(prog="factory", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--app", required=True)
    run.add_argument("--prd", required=True)
    run.add_argument("--data")
    run.add_argument("--target", type=float, default=0.95, help="conformance rate needed before gate C")
    run.add_argument("--max-loops", type=int, default=2)
    run.add_argument("--auto-approve", action="store_true", help="approve gates A and B automatically (never C)")
    for name in ("status", "resume", "serve", "provision"):
        sp = sub.add_parser(name)
        sp.add_argument("--app", required=True)
        if name == "serve":
            sp.add_argument("--port", type=int, default=8080)
    for name in ("approve", "retry"):
        sp = sub.add_parser(name)
        sp.add_argument("--app", required=True)
        if name == "approve":
            sp.add_argument("--gate", required=True, choices=["A", "B", "C"])
        sp.add_argument("--by", default=getpass.getuser())
        sp.add_argument("--note", default="")
    portal = sub.add_parser("portal")
    portal.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8090")))
    portal.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    worker = sub.add_parser("worker")
    worker.add_argument("--agent", required=True, choices=["requirements", "data", "knowledge", "app", "release"])
    worker.add_argument("--loop", action="store_true", help="keep polling (default: process one message and exit)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")

    if a.cmd == "run":
        coordinator.start(a.app, a.prd, a.data, a.target, a.max_loops, ["A", "B"] if a.auto_approve else [])
        s = coordinator.advance(a.app)
    elif a.cmd == "resume":
        s = coordinator.advance(a.app)
    elif a.cmd == "approve":
        coordinator.approve(a.app, a.gate, a.by, a.note)
        print(f"gate {a.gate} approved by {a.by}; continue with: python -m factory resume --app {a.app}")
        return
    elif a.cmd == "retry":
        coordinator.retry(a.app, a.by, a.note)
        print(f"cleared; continue with: python -m factory resume --app {a.app}")
        return
    elif a.cmd == "status":
        s = AppPack(a.app).read_json("run.json")
    elif a.cmd == "serve":
        import uvicorn
        from factory.runtime_app.server import create_app
        uvicorn.run(create_app(a.app), host="127.0.0.1", port=a.port)
        return
    elif a.cmd == "portal":
        import uvicorn
        from factory.portal.server import create_portal
        uvicorn.run(create_portal(), host=a.host, port=a.port)
        return
    elif a.cmd == "worker":
        from factory.workqueue import work_once
        import time
        while True:
            result = work_once(a.agent)
            print(json.dumps(result or {"idle": True}))
            if not a.loop:
                return
            if result is None:
                time.sleep(5)
    elif a.cmd == "provision":
        from factory.provision import provision
        print(json.dumps(provision(a.app), indent=2))
        return
    print(json.dumps({k: s.get(k) for k in ("app_id", "stage", "status", "loops", "gates", "usage")}, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
