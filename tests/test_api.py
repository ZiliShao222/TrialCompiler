import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app import create_app
from trialcompiler.evidence import workflow_evidence_digest

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

    def test_review_api_consumes_governed_workflow_observation_without_echoing_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "memory.sqlite3")
            document = json.loads(
                (ROOT / "data/fixtures/synthetic_protocol_conflict.json").read_text(
                    encoding="utf-8"
                )
            )
            observation = {
                "status": "completed",
                "model": "frozen-api-test",
                "result": {
                    "summary": "SENSITIVE OBSERVATION CONTENT",
                    "semantic_findings": [],
                    "review_questions": [],
                    "limitations": [],
                },
            }
            catalog = [
                {
                    "evidence_id": "EV-API-1",
                    "source_id": "SRC-API-1",
                    "project_id": document["project_id"],
                    "document_id": document["document_id"],
                    "observation_type": "semantic_review",
                    "payload": observation,
                    "payload_digest": workflow_evidence_digest(observation),
                }
            ]
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/review",
                    json={
                        "document": document,
                        "evidence_catalog": catalog,
                        "max_acquisitions": 1,
                    },
                )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["acquired_evidence"][0]["evidence_id"], "EV-API-1")
            self.assertEqual(payload["evidence_catalog"], [])

    def test_review_api_executes_governed_acquisition_without_bypassing_recheck(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "memory.sqlite3")
            document = json.loads(
                (ROOT / "data/fixtures/synthetic_protocol_conflict.json").read_text(
                    encoding="utf-8"
                )
            )
            acquisition = json.loads(
                (ROOT / "data/fixtures/evidence_acquisition_demo.json").read_text(
                    encoding="utf-8"
                )
            )
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/review",
                    json={"document": document, "evidence_acquisition": acquisition},
                )
                self.assertEqual(response.status_code, 200)
                artifact = response.json()["uncertainty_artifact"]
                self.assertEqual(artifact["selected_action"], "deliberate")
                self.assertEqual(
                    artifact["acquisition_loop"]["final_decision"]["action"],
                    "commit_candidate",
                )
                self.assertIn("cannot bypass", artifact["governance_note"])
                self.assertEqual(
                    response.json()["evidence_acquisition"],
                    {"provided": True, "raw_content_retained": False},
                )
                self.assertNotIn(
                    "Synthetic demonstration evidence",
                    json.dumps(response.json(), ensure_ascii=False),
                )


if __name__ == "__main__":
    unittest.main()
