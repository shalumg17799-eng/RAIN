"""The HITL review API: a held run is listed, decided over HTTP, and resumes with the verdict."""

import hashlib
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from insights.api.app import create_app
from insights.api.settings import ServerSettings
from insights.catalog.provider import DirectoryCatalogs
from insights.runtime.test_skill_agent import FakeGateway
from insights.skills_core.protocols import Services
from insights.test_nlq_flow import SQL_ENVELOPE, FakeAdapter, FakeData

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "test-token-hitl"


def build_client() -> TestClient:
    tmp = tempfile.mkdtemp()
    keys_path = Path(tmp) / "keys.yaml"
    keys_path.write_text(
        "version: 1\n"
        "keys:\n"
        "  - id: test-key\n"
        f"    key_sha256: {hashlib.sha256(TOKEN.encode()).hexdigest()}\n"
        "    subject: maria\n"
        "    tenant: rain\n"
        "    roles: [maria]\n",
        encoding="utf-8",
    )
    settings = ServerSettings.from_env({"INSIGHTS_API_KEYS_FILE": str(keys_path)})
    app = create_app(settings, gateway=FakeGateway([SQL_ENVELOPE] * 4))
    state = app.state.insights
    state.runtime.services = Services(
        catalogs=DirectoryCatalogs(ROOT / "apps"),
        data=FakeData({"main": FakeAdapter()}),
        hitl=state.hitl,
    )
    return TestClient(app)


AUTH = {"authorization": f"Bearer {TOKEN}"}


class HitlReviewApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = build_client()

    def test_pending_requires_a_bearer_key(self):
        self.assertEqual(self.client.get("/v1/hitl/pending").status_code, 401)

    def test_deciding_an_unknown_run_is_404(self):
        response = self.client.post(
            "/v1/hitl/nonexistent", json={"action": "approve"}, headers=AUTH
        )
        self.assertEqual(response.status_code, 404)

    def test_an_edit_without_narrative_is_rejected(self):
        response = self.client.post(
            "/v1/hitl/whatever", json={"action": "edit"}, headers=AUTH
        )
        self.assertEqual(response.status_code, 422)

    def test_a_held_run_is_listed_decided_and_resumes_approved(self):
        outcome: dict = {}

        def ask():
            outcome["response"] = self.client.post(
                "/v1/apps/rain/ask",
                json={
                    "request_id": str(uuid.uuid4()),
                    "query": "How many patients are currently enrolled?",
                },
                headers=AUTH,
            )

        thread = threading.Thread(target=ask, daemon=True)
        thread.start()

        pending = []
        import time

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not pending:
            listing = self.client.get("/v1/hitl/pending", headers=AUTH)
            self.assertEqual(listing.status_code, 200)
            pending = listing.json()["pending"]
            time.sleep(0.02)
        self.assertTrue(pending, "the run never reached the HITL gate")
        review = pending[0]
        self.assertEqual(review["reason"], "low_confidence")
        self.assertIn("patients", review["question"])
        self.assertTrue(review["sql"])

        decided = self.client.post(
            f"/v1/hitl/{review['run_id']}", json={"action": "approve"}, headers=AUTH
        )
        self.assertEqual(decided.status_code, 200)
        self.assertTrue(decided.json()["resolved"])

        thread.join(timeout=30)
        self.assertFalse(thread.is_alive(), "the ask never finished")
        response = outcome["response"]
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "answered", payload)
        self.assertEqual(payload["confidence"]["signals"].get("hitl"), "approved")


if __name__ == "__main__":
    unittest.main()
