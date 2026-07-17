"""Document parsing, fact extraction, graphs, and change impact."""

from trialcompiler.documents.graph import ClinicalDocumentGraph
from trialcompiler.documents.repairs import compose_repair_proposals, proposal_to_operations

__all__ = ["ClinicalDocumentGraph", "compose_repair_proposals", "proposal_to_operations"]
