from trialcompiler.generation.workflow import ProtocolGenerationWorkflow


def test_quality_output_governs_list_shaped_tbd_compliance() -> None:
    output = ProtocolGenerationWorkflow._govern_quality_output(
        {
            "gate_status": "revise_before_human_review",
            "findings": [],
            "unsupported_claims": [],
            "tbd_compliance": [
                "TBD items are listed.",
                "However, declarative text violates the TBD boundary.",
            ],
            "limitations": [],
        }
    )
    assert output["tbd_compliance"]["compliant"] is False
    assert len(output["tbd_compliance"]["issues"]) == 2
