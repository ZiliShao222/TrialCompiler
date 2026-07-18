import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]


class ApiTests(unittest.TestCase):
    def test_health_and_review_run_in_fastapi_worker_threads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "memory.sqlite3")
            document = json.loads(
                (ROOT / "data/fixtures/synthetic_protocol_conflict.json").read_text(
                    encoding="utf-8"
                )
            )
            with TestClient(app) as client:
                health = client.get("/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["release_mode"], "review_only")

                review = client.post("/api/v1/review", json={"document": document})
                self.assertEqual(review.status_code, 200)
                payload = review.json()
                self.assertTrue(payload["quality"]["accepted"])
                self.assertEqual(len(payload["findings"]), 2)
                self.assertEqual(
                    [event["agent"] for event in payload["trace"]],
                    ["A", "B", "C", "D", "G", "E", "F"],
                )
                self.assertEqual(
                    payload["uncertainty_artifact"]["selected_action"],
                    "acquire_evidence",
                )
                self.assertFalse(
                    payload["uncertainty_artifact"]["numeric_probability_available"]
                )

    def test_feishu_payload_validation_is_exposed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "memory.sqlite3")
            intake = json.loads(
                (ROOT / "data/fixtures/feishu_aily_intake.json").read_text(encoding="utf-8")
            )
            with TestClient(app) as client:
                response = client.post("/api/v1/intake/feishu", json=intake)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["accepted"])


if __name__ == "__main__":
    unittest.main()
