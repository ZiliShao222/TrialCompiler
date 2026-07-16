import json
import unittest
from pathlib import Path

from trialcompiler.integrations.feishu import aily_acknowledgement, validate_aily_payload

ROOT = Path(__file__).resolve().parents[1]


class FeishuIntakeTests(unittest.TestCase):
    def test_fixture_is_accepted_and_routed(self) -> None:
        payload = json.loads(
            (ROOT / "data/fixtures/feishu_aily_intake.json").read_text(encoding="utf-8")
        )
        envelope = validate_aily_payload(payload)
        ack = aily_acknowledgement(envelope)
        self.assertTrue(ack["accepted"])
        self.assertEqual("start_trialcompiler_review", ack["next_step"])
        self.assertEqual("feishu_aily", ack["normalized_intake"]["source"])

    def test_missing_actor_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "actor_id"):
            validate_aily_payload(
                {
                    "request_id": "x",
                    "project_id": "p",
                    "user_request": "review this",
                }
            )


if __name__ == "__main__":
    unittest.main()
