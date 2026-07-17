"""Build the canonical, auditable TrialCompiler reference catalog.

The script is intentionally non-destructive: source files remain in their
current locations while duplicate IDs and local copies are reconciled into one
logical source record. Generated files under ``references/catalog`` are the
only source register that downstream tooling should consume.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = REPO_ROOT / "references"
METADATA = REFERENCES / "metadata"
CATALOG = REFERENCES / "catalog"
ATTACHMENTS = REPO_ROOT / "docs" / "attachments"


@dataclass
class SourceRecord:
    source_id: str
    title: str
    organization: str
    year: str
    collection: str
    source_type: str
    evidence_tier: str
    authority_level: str
    intended_use: str
    source_url: str = ""
    access_status: str = "unknown"
    lifecycle_status: str = "active"
    local_paths: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sha256: list[str] = field(default_factory=list)

    def merge(self, other: SourceRecord) -> None:
        self.local_paths = unique(self.local_paths + other.local_paths)
        self.aliases = unique(self.aliases + [other.source_id] + other.aliases)
        self.notes = unique(self.notes + other.notes)
        self.sha256 = unique(self.sha256 + other.sha256)
        if evidence_rank(other.evidence_tier) < evidence_rank(self.evidence_tier):
            self.evidence_tier = other.evidence_tier
            self.authority_level = other.authority_level
        if not self.intended_use and other.intended_use:
            self.intended_use = other.intended_use

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "organization": self.organization,
            "year": self.year,
            "collection": self.collection,
            "source_type": self.source_type,
            "evidence_tier": self.evidence_tier,
            "authority_level": self.authority_level,
            "intended_use": self.intended_use,
            "source_url": self.source_url,
            "access_status": self.access_status,
            "lifecycle_status": self.lifecycle_status,
            "local_paths": self.local_paths,
            "aliases": self.aliases,
            "notes": self.notes,
            "sha256": self.sha256,
        }


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def clean(value: str | None) -> str:
    return (value or "").strip()


def repo_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def normalize_url(url: str) -> str:
    url = clean(url)
    if not url:
        return ""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_rank(tier: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3, "INTERNAL": 4}.get(tier, 9)


def apply_quality_overrides(records: list[SourceRecord]) -> None:
    """Apply human-reviewed source quality decisions after metadata ingestion."""
    path = METADATA / "source_quality_overrides.tsv"
    if not path.is_file():
        return
    by_id = {record.source_id: record for record in records}
    for row in read_tsv(path):
        source_id = clean(row.get("source_id"))
        record = by_id.get(source_id)
        if record is None:
            raise ValueError(f"Unknown source_id in quality override: {source_id}")
        for field_name in ("access_status", "lifecycle_status"):
            value = clean(row.get(field_name))
            if value:
                setattr(record, field_name, value)
        note = clean(row.get("review_note"))
        if note:
            record.notes = unique(record.notes + [note])


def classify(category: str, source_type: str, organization: str) -> tuple[str, str, str]:
    category = category.lower()
    source_type = source_type.lower()
    organization_lc = organization.lower()
    regulatory_types = {
        "regulatory_guideline",
        "regulatory_guidance",
        "guidance_pdf",
        "guideline_statement",
        "regulatory_page",
    }
    standards_markers = {"ich", "fda", "ema", "nmpa", "cde", "who", "cdisc", "spirit"}
    if "template" in source_type or category in {
        "associated_documents",
        "schedule_of_activities",
    }:
        return "02_templates_and_associated_documents", "B", "institutional"
    if source_type in regulatory_types or category in {
        "medical",
        "china_regulatory",
        "regulatory_constraints",
    }:
        collection = "01_regulatory_and_ethics"
        tier = "A" if any(marker in organization_lc for marker in standards_markers) else "B"
        return collection, tier, "regulatory" if tier == "A" else "institutional"
    if category == "standards":
        return "03_data_standards_and_structured_protocols", "A", "standards_body"
    if category in {"ai_protocol_authoring", "ai_governance"}:
        return "04_ai_methods_and_governance", "C", "literature"
    if category in {"business", "burden"}:
        return "05_industry_competitors_and_value", "D", "industry"
    if category == "feishu":
        return "06_platform_and_integration", "D", "vendor_documentation"
    return "07_other_public_evidence", "C", "public_reference"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def public_records() -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for row in read_tsv(METADATA / "public_source_index.tsv"):
        collection, tier, authority = classify(
            clean(row["category"]), clean(row["source_type"]), clean(row["organization"])
        )
        local_path = clean(row["local_path"])
        path = REPO_ROOT / local_path if local_path else None
        records.append(
            SourceRecord(
                source_id=clean(row["source_id"]),
                title=clean(row["title"]),
                organization=clean(row["organization"]),
                year=clean(row["year"]),
                collection=collection,
                source_type=clean(row["source_type"]),
                evidence_tier=tier,
                authority_level=authority,
                intended_use=clean(row["primary_use"]),
                source_url=clean(row["url"]),
                access_status=clean(row["access_status"]),
                local_paths=[local_path] if local_path else [],
                aliases=[],
                notes=[],
                sha256=[file_hash(path)] if path and path.is_file() else [],
            )
        )
    return records


def find_teammate_file(source_id: str) -> Path | None:
    root = REFERENCES / "inbox" / "medical_teammate"
    matches = [path for path in root.rglob(f"{source_id}_*") if path.is_file()]
    return sorted(matches)[0] if matches else None


def teammate_records() -> list[SourceRecord]:
    path = METADATA / "medical_teammate_source_index.tsv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    records: list[SourceRecord] = []
    for row in rows[1:]:
        if len(row) < 14:
            continue
        (
            source_id,
            module,
            title,
            organization,
            version,
            file_status,
            file_type,
            language,
            url,
            download_status,
            _size,
            _relative_path,
            purpose,
            usage_note,
        ) = map(clean, row[:14])
        local = find_teammate_file(source_id)
        source_type = "template" if module.startswith("M4") else "regulatory_guideline"
        if module.startswith("M3"):
            source_type = "governance_or_benchmark"
        collection, tier, authority = classify("medical", source_type, organization)
        if module.startswith("M2"):
            collection = "01_regulatory_and_ethics"
        elif module.startswith("M3"):
            collection, tier, authority = "04_ai_methods_and_governance", "C", "literature"
        elif module.startswith("M4"):
            collection, tier, authority = (
                "02_templates_and_associated_documents",
                "B",
                "institutional",
            )
        records.append(
            SourceRecord(
                source_id=source_id,
                title=title,
                organization=organization,
                year=version[:4],
                collection=collection,
                source_type=source_type,
                evidence_tier=tier,
                authority_level=authority,
                intended_use=purpose,
                source_url=url,
                access_status=download_status,
                local_paths=[repo_path(local)] if local else [],
                notes=unique([file_status, language, usage_note]),
                sha256=[file_hash(local)] if local else [],
            )
        )
    return records


def internal_attachment_records() -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for index, path in enumerate(sorted(ATTACHMENTS.rglob("*")), start=1):
        if not path.is_file() or path.name.lower() == "readme.md":
            continue
        records.append(
            SourceRecord(
                source_id=f"INTERNAL-{index:03d}",
                title=path.stem,
                organization="TrialCompiler project team",
                year="2026",
                collection="08_internal_project_materials",
                source_type="team_attachment",
                evidence_tier="INTERNAL",
                authority_level="project",
                intended_use="Internal synthesis, planning, or competition submission support",
                access_status="project_internal",
                local_paths=[repo_path(path)],
                notes=["Not an external authority; do not cite as regulatory evidence."],
                sha256=[file_hash(path)],
            )
        )
    return records


def uncatalogued_reference_records(known_paths: set[str]) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    index = 1
    for path in sorted((REFERENCES / "inbox").rglob("*")):
        if not path.is_file() or repo_path(path) in known_paths:
            continue
        is_admin_file = path.name.lower().startswith("readme") or path.suffix.lower() in {
            ".xlsx",
            ".csv",
            ".tsv",
        }
        if is_admin_file:
            records.append(
                SourceRecord(
                    source_id=f"LOCAL-{index:03d}",
                    title=path.stem,
                    organization="TrialCompiler project team",
                    year="2026",
                    collection="08_internal_project_materials",
                    source_type="local_support_file",
                    evidence_tier="INTERNAL",
                    authority_level="project",
                    intended_use="Source-package administration or internal documentation",
                    access_status="project_internal",
                    local_paths=[repo_path(path)],
                    notes=["Administrative file; not a citable external source."],
                    sha256=[file_hash(path)],
                )
            )
            index += 1
    return records


def reconcile(
    records: list[SourceRecord],
) -> tuple[list[SourceRecord], list[dict[str, str]], list[dict[str, str]]]:
    canonical: list[SourceRecord] = []
    by_url: dict[str, SourceRecord] = {}
    alias_rows: list[dict[str, str]] = []
    for record in records:
        key = normalize_url(record.source_url)
        if key and key in by_url:
            target = by_url[key]
            alias_rows.append(
                {
                    "alias_id": record.source_id,
                    "canonical_id": target.source_id,
                    "reason": "same_normalized_url",
                }
            )
            target.merge(record)
            continue
        canonical.append(record)
        if key:
            by_url[key] = record

    by_hash: dict[str, SourceRecord] = {}
    duplicate_files: list[dict[str, str]] = []
    for record in canonical:
        for digest in record.sha256:
            if digest in by_hash and by_hash[digest] is not record:
                target = by_hash[digest]
                duplicate_files.append(
                    {
                        "source_id": record.source_id,
                        "same_content_as": target.source_id,
                        "sha256": digest,
                        "review_status": (
                            "confirmed_local_snapshot_mismatch"
                            if record.access_status == "local_snapshot_mismatch"
                            else "needs_manual_review"
                        ),
                    }
                )
                record.notes.append(f"File content duplicates {target.source_id}.")
            else:
                by_hash[digest] = record
    return canonical, alias_rows, duplicate_files


def write_csv(records: list[SourceRecord], path: Path) -> None:
    fields = [
        "source_id",
        "title",
        "organization",
        "year",
        "collection",
        "source_type",
        "evidence_tier",
        "authority_level",
        "intended_use",
        "source_url",
        "access_status",
        "lifecycle_status",
        "local_paths",
        "aliases",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = record.as_dict()
            for key in ("local_paths", "aliases", "notes"):
                row[key] = " | ".join(row[key])
            row.pop("sha256", None)
            writer.writerow(row)


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_markdown(records: list[SourceRecord], aliases: list[dict[str, str]]) -> None:
    counts = Counter(record.collection for record in records)
    tier_counts = Counter(record.evidence_tier for record in records)
    lines = [
        "# TrialCompiler 资料来源总账",
        "",
        "> 本文件由 `scripts/build_reference_catalog.py` 自动生成。比赛报告、方案说明和 "
        "Agent 知识入库应优先引用本总账中的 canonical `source_id`。",
        "",
        "## 使用规则",
        "",
        "- A 级：监管机构、国际标准组织或正式指南，可作为规则与合规依据。",
        "- B 级：公共机构模板、注册平台定义或行业标准模板，可作为结构与检查依据。",
        "- C 级：同行评议论文、开放研究和方法资料，可作为研究与技术依据。",
        "- D 级：厂商页面、行业文章和新闻，只能用于竞品、需求与市场背景。",
        "- INTERNAL：团队附件和内部整理，只能说明项目过程，不能冒充外部证据。",
        "",
        "## 总览",
        "",
        f"- Canonical sources: **{len(records)}**",
        f"- Reconciled aliases: **{len(aliases)}**",
        "- Evidence tiers: "
        + ", ".join(f"{key}={value}" for key, value in sorted(tier_counts.items())),
        "",
        "| 资料集合 | 数量 |",
        "| --- | ---: |",
    ]
    for collection, count in sorted(counts.items()):
        lines.append(f"| `{collection}` | {count} |")

    grouped: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.collection].append(record)
    for collection, items in sorted(grouped.items()):
        lines.extend(
            [
                "",
                f"## {collection}",
                "",
                "| ID | 资料名称 | 来源机构 | 年份 | 等级 | 状态 | 类型 | 用途 | URL / 本地文件 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for record in sorted(items, key=lambda item: item.source_id):
            location = record.source_url or (record.local_paths[0] if record.local_paths else "-")
            if record.source_url:
                location = f"[source]({record.source_url})"
                if record.local_paths:
                    location += f"<br>`{md_escape(record.local_paths[0])}`"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{record.source_id}`",
                        md_escape(record.title),
                        md_escape(record.organization),
                        md_escape(record.year),
                        record.evidence_tier,
                        md_escape(f"{record.lifecycle_status} / {record.access_status}"),
                        md_escape(record.source_type),
                        md_escape(record.intended_use),
                        location,
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## 重复 ID 与合并记录",
            "",
            "| Alias ID | Canonical ID | 合并原因 |",
            "| --- | --- | --- |",
        ]
    )
    for row in aliases:
        lines.append(f"| `{row['alias_id']}` | `{row['canonical_id']}` | {row['reason']} |")
    (CATALOG / "SOURCE_REGISTER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_collection_readmes(records: list[SourceRecord]) -> None:
    root = CATALOG / "collections"
    root.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.collection].append(record)
    for collection, items in grouped.items():
        lines = [
            f"# {collection}",
            "",
            "This is a logical collection. Original files remain at the paths recorded below.",
            "",
        ]
        for item in sorted(items, key=lambda value: value.source_id):
            lines.append(f"- `{item.source_id}` {item.title}")
        (root / f"{collection}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    CATALOG.mkdir(parents=True, exist_ok=True)
    records = public_records() + teammate_records() + internal_attachment_records()
    known_paths = {path for record in records for path in record.local_paths}
    records += uncatalogued_reference_records(known_paths)
    apply_quality_overrides(records)
    canonical, aliases, duplicate_files = reconcile(records)
    canonical.sort(key=lambda item: (item.collection, item.source_id))

    with (CATALOG / "sources.jsonl").open("w", encoding="utf-8") as handle:
        for record in canonical:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
    write_csv(canonical, CATALOG / "source_register.csv")
    with (CATALOG / "source_aliases.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["alias_id", "canonical_id", "reason"])
        writer.writeheader()
        writer.writerows(aliases)
    with (CATALOG / "duplicate_files_to_review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = ["source_id", "same_content_as", "sha256", "review_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(duplicate_files)
    write_markdown(canonical, aliases)
    write_collection_readmes(canonical)

    missing = [
        path
        for record in canonical
        for path in record.local_paths
        if not (REPO_ROOT / path).is_file()
    ]
    summary = {
        "canonical_sources": len(canonical),
        "aliases_reconciled": len(aliases),
        "duplicate_files_to_review": len(duplicate_files),
        "local_paths": sum(len(record.local_paths) for record in canonical),
        "missing_local_paths": len(missing),
        "collections": dict(sorted(Counter(r.collection for r in canonical).items())),
        "evidence_tiers": dict(sorted(Counter(r.evidence_tier for r in canonical).items())),
    }
    (CATALOG / "catalog_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
