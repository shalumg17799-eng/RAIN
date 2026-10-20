"""Factory portal: start a run from a PRD (+ data), follow it stage by stage, read what each
agent produced, approve gates A/B/C and retry a blocked stage.

    python -m factory portal            # local: agents run as background threads
    (on Azure: the portal enqueues work; each agent is its own Container Apps Job)

Approvals are attributed to the signed-in user: on Azure Container Apps the built-in
authentication (Entra ID) adds X-MS-CLIENT-PRINCIPAL-NAME; locally the OS user name is used."""
from __future__ import annotations

import getpass
import io
import os
import re
import shutil
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from factory import coordinator
from factory.apppack import ID_RE, AppPack
from factory.config import APPPACKS_DIR
from factory.workqueue import LocalWorkers, enqueue

VIEWABLE = re.compile(r"^(manifest\.yaml|data_contract\.yaml|metrics\.yaml|ui\.json|run\.json|"
                      r"reports/[\w.-]+\.(md|json|log)|handoffs/[\w.-]+\.json|deploy/[\w.-]+)$")


def _user(request: Request) -> str:
    return request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or os.environ.get("FACTORY_LOCAL_USER") or getpass.getuser()


def create_portal(start_workers: bool | None = None) -> FastAPI:
    app = FastAPI(title="PRD-to-App Factory")
    local = not os.environ.get("FACTORY_QUEUE_CONNECTION")
    if start_workers if start_workers is not None else local:
        app.state.workers = LocalWorkers().start()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    @app.get("/api/runs")
    def runs():
        out = []
        for d in sorted(APPPACKS_DIR.glob("*/run.json")):
            s = AppPack(d.parent.name).read_json("run.json")
            report = AppPack(d.parent.name).read_json("reports/conformance.json", {})
            out.append({"app_id": s["app_id"], "stage": s["stage"], "status": s["status"],
                        "updated_at": s.get("updated_at"), "loops": s.get("loops", 0),
                        "conformance": f"{report['matched']}/{report['total_checkable']}" if report else None})
        return sorted(out, key=lambda r: r.get("updated_at") or "", reverse=True)

    @app.post("/api/runs")
    async def start(request: Request, app_id: str = Form(...), prd: UploadFile = File(...),
                    data: list[UploadFile] | None = File(None), auto_ab: bool = Form(False),
                    target: float = Form(0.95)):
        if not ID_RE.match(app_id):
            raise HTTPException(400, "app id: lower-case letters, digits and underscores, starting with a letter")
        if (APPPACKS_DIR / app_id / "run.json").exists():
            raise HTTPException(409, f"a run for {app_id} already exists")
        suffix = Path(prd.filename or "").suffix.lower()
        if suffix not in (".docx", ".md", ".txt"):
            raise HTTPException(400, "PRD must be .docx, .md or .txt")
        inbox = APPPACKS_DIR / "_uploads" / app_id
        shutil.rmtree(inbox, ignore_errors=True)
        (inbox / "data").mkdir(parents=True)
        prd_path = inbox / f"prd{suffix}"
        prd_path.write_bytes(await prd.read())
        data_dir = None
        for f in data or []:
            raw, name = await f.read(), Path(f.filename or "").name
            if not raw:
                continue
            if name.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    for member in z.namelist():
                        if member.lower().endswith(".csv") and not member.startswith("__MACOSX"):
                            (inbox / "data" / Path(member).name).write_bytes(z.read(member))
            elif name.lower().endswith(".csv"):
                (inbox / "data" / name).write_bytes(raw)
            else:
                raise HTTPException(400, f"{name}: data must be .csv files or a .zip of them")
            data_dir = inbox / "data"
        coordinator.start(app_id, str(prd_path), str(data_dir) if data_dir else None, target, 2,
                          ["A", "B"] if auto_ab else [])
        pack = AppPack(app_id)
        s = pack.read_json("run.json")
        s["history"].append({"at": s["created_at"], "event": "started", "by": _user(request)})
        pack.write_json("run.json", s)
        return coordinator.advance(app_id, dispatch=enqueue)

    @app.get("/api/runs/{app_id}")
    def run(app_id: str):
        pack = _pack(app_id)
        files = sorted(str(p.relative_to(pack.dir)).replace("\\", "/") for p in pack.dir.rglob("*") if p.is_file())
        return {"state": pack.read_json("run.json"), "gates": coordinator.GATES,
                "files": [f for f in files if VIEWABLE.match(f)]}

    @app.get("/api/runs/{app_id}/file", response_class=PlainTextResponse)
    def file(app_id: str, path: str):
        pack = _pack(app_id)
        if not VIEWABLE.match(path):
            raise HTTPException(403, "this file is not viewable here")
        target = pack.path(*path.split("/"))
        if not target.is_file():
            raise HTTPException(404, path)
        return target.read_text(encoding="utf-8", errors="replace")[:500_000]

    @app.post("/api/runs/{app_id}/gates/{gate}/approve")
    def approve(app_id: str, gate: str, request: Request, note: str = Form("")):
        _pack(app_id)
        if gate not in ("A", "B", "C"):
            raise HTTPException(400, "gate must be A, B or C")
        s = AppPack(app_id).read_json("run.json")
        if s["stage"] != f"gate:{gate}":
            raise HTTPException(409, f"the run is at {s['stage']}, not gate {gate}")
        coordinator.approve(app_id, gate, _user(request), note)
        return coordinator.advance(app_id, dispatch=enqueue)

    @app.post("/api/runs/{app_id}/retry")
    def retry(app_id: str, request: Request, note: str = Form("")):
        _pack(app_id)
        try:
            coordinator.retry(app_id, _user(request), note)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return coordinator.advance(app_id, dispatch=enqueue)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local workers" if local else "azure queues"}

    return app


def _pack(app_id: str) -> AppPack:
    if not ID_RE.match(app_id) or not (APPPACKS_DIR / app_id / "run.json").is_file():
        raise HTTPException(404, f"no run for {app_id}")
    return AppPack(app_id)
