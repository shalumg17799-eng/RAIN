"""Build the new UI's test data: frontend/ultra-rain-v2/src/test/fixtures/rain_v4_ui2_data.json.

The app reads every value from GET /api/v4/ui2/data at boot (rain-api/ui2_v4.py: the computed v0.4 data plus the
new UI's extras). Its unit tests run without a backend, so they hydrate the same shape from the backend's SEED, the
way frontend/rain-app's tests hydrate from rain-api/seed/rain_v4_ui_data.json: the v0.4 seed sections (the PRD's
spec numbers) passed through the same overlay the endpoint applies (ui2_v4.apply_overlay, with
rain-api/seed/rain_v4_ui2_overlay.json). So the tests check the UI against the spec story, and
rain-api/test_ui2_v4.py checks the live endpoint.

Usage (repo root):  python scripts/e2e/make_ui2_test_fixture.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rain-api"))
import ui2_v4  # noqa: E402

SEED = ROOT / "rain-api/seed/rain_v4_ui_data.json"
OVERLAY = ROOT / "rain-api/seed/rain_v4_ui2_overlay.json"
OUT = ROOT / "frontend/ultra-rain-v2/src/test/fixtures/rain_v4_ui2_data.json"


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    sections, changes = ui2_v4.apply_overlay(seed["sections"], overlay["sections"])
    body = {
        "meta": {
            "source": "rain-api seed",
            "snapshotOf": "/api/v4/ui2/data?clientId=rain, built from the seed (no database)",
            "built": "scripts/e2e/make_ui2_test_fixture.py: ui2_v4.apply_overlay(rain_v4_ui_data.json, rain_v4_ui2_overlay.json)",
            "uiOverrides": changes,
        },
        "sections": sections,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(body, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{k} {len(v)}" for k, v in sections.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
