"""Stage-isolated ingestion for generative protocol benchmark packages.

The benchmark directory is treated as hostile input: files are selected from the
actual directory tree, not from a package-provided manifest, and hidden evaluator
materials can never be returned by a phase-one or phase-two view.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

VISIBLE_DIRECTORIES = {
    "phase1": ("01_AI_VISIBLE_PHASE1",),
    "phase2": ("01_AI_VISIBLE_PHASE1", "02_AI_VISIBLE_PHASE2"),
}
HIDDEN_DIRECTORY = "03_EVALUATOR_ONLY"
LEAKAGE_KEYS = {"phase2_confirmed_decisions", "gold_standard", "reference_answers"}
LEAKAGE_TERMS = (
    "NCT05132439",
    "MOBILE IC",
    "PMC9862509",
    "03_EVALUATOR_ONLY",
)
TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv"}


@dataclass(slots=True)
class PackageFile:
    path: str
    sha256: str
    size_bytes: int
    text: str
    sanitization_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PackageAudit:
    package_root: str
    stage: str
    passed: bool
    visible_files: list[str]
    findings: list[dict[str, Any]]
    sanitization_events: list[str]
    hidden_directory_present: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GenerativeCasePackage:
    """Read an extracted benchmark package through an explicit stage boundary."""

    def __init__(self, root: str | Path) -> None:
        candidate = Path(root).resolve()
        self.root = self._locate_root(candidate)

    @staticmethod
    def _locate_root(candidate: Path) -> Path:
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        if candidate.is_file():
            raise ValueError("Extract the benchmark ZIP before ingestion")
        if (candidate / "01_AI_VISIBLE_PHASE1").is_dir():
            return candidate
        matches = [path.parent for path in candidate.rglob("01_AI_VISIBLE_PHASE1") if path.is_dir()]
        unique = sorted(set(matches))
        if len(unique) != 1:
            raise ValueError(
                "Could not identify one benchmark root containing 01_AI_VISIBLE_PHASE1"
            )
        return unique[0]

    def visible_paths(self, stage: str) -> list[Path]:
        if stage not in VISIBLE_DIRECTORIES:
            raise ValueError("stage must be phase1 or phase2")
        paths: list[Path] = []
        for directory in VISIBLE_DIRECTORIES[stage]:
            base = self.root / directory
            if not base.is_dir():
                raise FileNotFoundError(base)
            paths.extend(path for path in base.rglob("*") if path.is_file())
        return sorted(paths)

    def materialize(self, stage: str, *, strict: bool = True) -> list[PackageFile]:
        files: list[PackageFile] = []
        for path in self.visible_paths(stage):
            text, events = extract_document_text(path)
            if path.suffix.lower() == ".json":
                text, json_events = _sanitize_json(text)
                events.extend(json_events)
            text, redaction_events = _redact_hidden_terms(text)
            events.extend(redaction_events)
            files.append(
                PackageFile(
                    path=path.relative_to(self.root).as_posix(),
                    sha256=_sha256(path),
                    size_bytes=path.stat().st_size,
                    text=text,
                    sanitization_events=events,
                )
            )
        audit = self.audit(stage, files=files)
        if strict and not audit.passed:
            details = "; ".join(item["message"] for item in audit.findings)
            raise ValueError(f"Benchmark package leakage audit failed: {details}")
        return files

    def audit(
        self,
        stage: str,
        *,
        files: list[PackageFile] | None = None,
    ) -> PackageAudit:
        if files is None:
            files = self.materialize(stage, strict=False)
        findings: list[dict[str, Any]] = []
        events = [event for item in files for event in item.sanitization_events]
        for item in files:
            if item.path.startswith(HIDDEN_DIRECTORY + "/"):
                findings.append(
                    {
                        "severity": "critical",
                        "path": item.path,
                        "message": "Evaluator-only file crossed the generation boundary",
                    }
                )
            for term in LEAKAGE_TERMS:
                if term.casefold() in item.text.casefold():
                    findings.append(
                        {
                            "severity": "critical",
                            "path": item.path,
                            "message": f"Hidden reference term detected: {term}",
                        }
                    )
        return PackageAudit(
            package_root=str(self.root),
            stage=stage,
            passed=not findings,
            visible_files=[item.path for item in files],
            findings=findings,
            sanitization_events=events,
            hidden_directory_present=(self.root / HIDDEN_DIRECTORY).is_dir(),
        )

    def prompt_payload(self, stage: str, *, strict: bool = True) -> dict[str, Any]:
        files = self.materialize(stage, strict=strict)
        return {
            "benchmark_stage": stage,
            "visibility_policy": {
                "visible_directories": list(VISIBLE_DIRECTORIES[stage]),
                "evaluator_materials_visible": False,
                "unconfirmed_values_must_be_tbd": True,
            },
            "source_documents": [asdict(item) for item in files],
        }


def _sanitize_json(text: str) -> tuple[str, list[str]]:
    events: list[str] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text, events

    def visit(value: Any, pointer: str = "$") -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).casefold() in LEAKAGE_KEYS:
                    events.append(f"Removed hidden key {pointer}.{key}")
                    continue
                cleaned[key] = visit(item, f"{pointer}.{key}")
            return cleaned
        if isinstance(value, list):
            return [visit(item, f"{pointer}[{index}]") for index, item in enumerate(value)]
        return value

    return json.dumps(visit(payload), ensure_ascii=False, indent=2), events


def _redact_hidden_terms(text: str) -> tuple[str, list[str]]:
    events: list[str] = []
    for term in LEAKAGE_TERMS:
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        count = len(pattern.findall(text))
        if count:
            text = pattern.sub("[REDACTED_HIDDEN_REFERENCE]", text)
            events.append(f"Redacted hidden reference {term} ({count} occurrence(s))")
    return text, events


def extract_document_text(path: Path) -> tuple[str, list[str]]:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace"), []
    if suffix == ".docx":
        return _docx_text(path), []
    if suffix == ".xlsx":
        return _xlsx_text(path), []
    return "", [f"Metadata-only ingestion for unsupported file type {suffix or '<none>'}"]


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for paragraph in root.iter():
        if paragraph.tag.endswith("}p"):
            text = "".join(
                node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
            ).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _xlsx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root:
                shared.append(
                    "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                )
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheets: list[tuple[str, str]] = []
        for sheet in workbook.iter():
            if not sheet.tag.endswith("}sheet"):
                continue
            relation_id = next(
                (value for key, value in sheet.attrib.items() if key.endswith("}id")),
                "",
            )
            target = relation_map.get(relation_id, "")
            if target:
                target = target.lstrip("/")
                if not target.startswith("xl/"):
                    target = "xl/" + target
                sheets.append((sheet.attrib.get("name", "Sheet"), target))
        lines: list[str] = []
        for name, target in sheets:
            lines.append(f"## Sheet: {name}")
            root = ET.fromstring(archive.read(target))
            for row in root.iter():
                if not row.tag.endswith("}row"):
                    continue
                values: list[str] = []
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    cell_type = cell.attrib.get("t")
                    raw = next(
                        (node.text or "" for node in cell if node.tag.endswith("}v")),
                        "",
                    )
                    if cell_type == "s" and raw.isdigit() and int(raw) < len(shared):
                        raw = shared[int(raw)]
                    if cell_type == "inlineStr":
                        raw = "".join(
                            node.text or "" for node in cell.iter() if node.tag.endswith("}t")
                        )
                    values.append(re.sub(r"\s+", " ", raw).strip())
                if any(values):
                    lines.append("\t".join(values))
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
