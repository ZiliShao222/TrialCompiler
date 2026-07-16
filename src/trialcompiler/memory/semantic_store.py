"""Auditable semantic-element store with coarse retrieval and fine validation.

The MVP uses SQLite FTS5 for the high-recall stage so it runs without a vector
service. The interface deliberately leaves a seam for an ANN backend later.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def normalize_key(text: str) -> str:
    return " ".join(TOKEN_PATTERN.findall(text.lower()))


def lexical_tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class SemanticElement:
    element_id: str
    namespace: str
    semantic_key: str
    value: dict[str, Any]
    element_type: str
    normalized_key: str = ""
    document_type: str = "any"
    section_type: str = "any"
    jurisdiction: str = "any"
    therapeutic_area: str = "any"
    authority: str = "project"
    approval_status: str = "draft"
    valid_from: str | None = None
    valid_until: str | None = None
    source_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    staticity: float = 5.0
    frequency: int = 0
    fetch_cost: float = 0.0
    size_tokens: int = 0
    latency_ms: float = 0.0
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    last_accessed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.normalized_key:
            self.normalized_key = normalize_key(self.semantic_key)
        if not self.size_tokens:
            self.size_tokens = max(1, len(json.dumps(self.value, ensure_ascii=False)) // 4)


@dataclass(slots=True)
class RetrievalQuery:
    text: str
    namespace: str
    element_types: list[str] = field(default_factory=list)
    document_type: str | None = None
    section_type: str | None = None
    jurisdiction: str | None = None
    therapeutic_area: str | None = None
    approval_statuses: list[str] = field(default_factory=lambda: ["approved"])
    top_k: int = 6
    coarse_k: int = 24


@dataclass(slots=True)
class RetrievalHit:
    element: SemanticElement
    coarse_score: float
    fine_score: float
    admitted: bool
    reasons: list[str]


FineJudge = Callable[[RetrievalQuery, SemanticElement, float], tuple[bool, float, list[str]]]


def synchronized(method):
    """Serialize access to the shared SQLite connection used by the API."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


class SemanticElementStore:
    """SQLite-backed semantic elements with deterministic audit behavior."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._fts_enabled = True
        self._create_schema()

    @synchronized
    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS semantic_elements (
                element_id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                semantic_key TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                element_type TEXT NOT NULL,
                document_type TEXT NOT NULL,
                section_type TEXT NOT NULL,
                jurisdiction TEXT NOT NULL,
                therapeutic_area TEXT NOT NULL,
                authority TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                valid_from TEXT,
                valid_until TEXT,
                source_ids_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                staticity REAL NOT NULL,
                frequency INTEGER NOT NULL,
                fetch_cost REAL NOT NULL,
                size_tokens INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_accessed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_semantic_exact
                ON semantic_elements(namespace, normalized_key);
            CREATE INDEX IF NOT EXISTS idx_semantic_scope
                ON semantic_elements(namespace, element_type, approval_status);
            CREATE TABLE IF NOT EXISTS retrieval_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                namespace TEXT NOT NULL,
                element_id TEXT,
                outcome TEXT NOT NULL,
                coarse_score REAL,
                fine_score REAL,
                created_at TEXT NOT NULL
            );
            """
        )
        try:
            self.connection.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS semantic_fts USING fts5(
                element_id UNINDEXED, semantic_key, tags, value_text
                )"""
            )
        except sqlite3.OperationalError:
            self._fts_enabled = False
        self.connection.commit()

    @synchronized
    def upsert(self, element: SemanticElement) -> None:
        values = asdict(element)
        values["value_json"] = json.dumps(values.pop("value"), ensure_ascii=False)
        values["source_ids_json"] = json.dumps(values.pop("source_ids"), ensure_ascii=False)
        values["tags_json"] = json.dumps(values.pop("tags"), ensure_ascii=False)
        columns = list(values)
        assignments = ", ".join(
            f"{name}=excluded.{name}" for name in columns if name != "element_id"
        )
        placeholders = ", ".join(f":{name}" for name in columns)
        self.connection.execute(
            f"""INSERT INTO semantic_elements ({', '.join(columns)})
            VALUES ({placeholders}) ON CONFLICT(element_id) DO UPDATE SET {assignments}""",
            values,
        )
        if self._fts_enabled:
            self.connection.execute(
                "DELETE FROM semantic_fts WHERE element_id = ?", (element.element_id,)
            )
            self.connection.execute(
                "INSERT INTO semantic_fts(element_id, semantic_key, tags, value_text) "
                "VALUES (?, ?, ?, ?)",
                (
                    element.element_id,
                    element.semantic_key,
                    " ".join(element.tags),
                    json.dumps(element.value, ensure_ascii=False),
                ),
            )
        self.connection.commit()

    @synchronized
    def get(self, element_id: str) -> SemanticElement | None:
        row = self.connection.execute(
            "SELECT * FROM semantic_elements WHERE element_id = ?", (element_id,)
        ).fetchone()
        return self._row_to_element(row) if row else None

    @synchronized
    def retrieve(
        self,
        query: RetrievalQuery,
        *,
        fine_judge: FineJudge | None = None,
    ) -> list[RetrievalHit]:
        fine_judge = fine_judge or deterministic_fine_judge
        exact = self.connection.execute(
            """SELECT * FROM semantic_elements
            WHERE namespace = ? AND normalized_key = ?""",
            (query.namespace, normalize_key(query.text)),
        ).fetchall()
        candidates: dict[str, tuple[SemanticElement, float]] = {
            row["element_id"]: (self._row_to_element(row), 1.0) for row in exact
        }
        for element, score in self._coarse_candidates(query):
            candidates.setdefault(element.element_id, (element, score))

        hits: list[RetrievalHit] = []
        for element, coarse_score in candidates.values():
            gate_reasons = self._metadata_gate(query, element)
            if gate_reasons:
                hit = RetrievalHit(element, coarse_score, 0.0, False, gate_reasons)
            else:
                admitted, fine_score, reasons = fine_judge(query, element, coarse_score)
                hit = RetrievalHit(element, coarse_score, fine_score, admitted, reasons)
            hits.append(hit)
            self._record_retrieval(query, hit)

        admitted_hits = [hit for hit in hits if hit.admitted]
        admitted_hits.sort(
            key=lambda hit: (
                hit.fine_score,
                hit.coarse_score,
                authority_weight(hit.element.authority),
            ),
            reverse=True,
        )
        for hit in admitted_hits[: query.top_k]:
            self._touch(hit.element.element_id)
        return admitted_hits[: query.top_k]

    def _coarse_candidates(self, query: RetrievalQuery) -> list[tuple[SemanticElement, float]]:
        rows: list[sqlite3.Row] = []
        if self._fts_enabled:
            terms = [token for token in lexical_tokens(query.text) if len(token) > 1]
            if terms:
                fts_query = " OR ".join(f'"{term}"' for term in sorted(terms))
                try:
                    rows = self.connection.execute(
                        """SELECT s.*, bm25(semantic_fts) AS rank
                        FROM semantic_fts JOIN semantic_elements s USING(element_id)
                        WHERE semantic_fts MATCH ? AND s.namespace = ?
                        ORDER BY rank LIMIT ?""",
                        (fts_query, query.namespace, query.coarse_k),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
        if not rows:
            rows = self.connection.execute(
                "SELECT * FROM semantic_elements WHERE namespace = ? LIMIT ?",
                (query.namespace, query.coarse_k * 4),
            ).fetchall()
        query_tokens = lexical_tokens(query.text)
        ranked: list[tuple[SemanticElement, float]] = []
        for row in rows:
            element = self._row_to_element(row)
            candidate_tokens = lexical_tokens(
                element.semantic_key + " " + " ".join(element.tags)
            )
            overlap = len(query_tokens & candidate_tokens) / max(
                1, len(query_tokens | candidate_tokens)
            )
            ranked.append((element, overlap))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[: query.coarse_k]

    def _metadata_gate(self, query: RetrievalQuery, element: SemanticElement) -> list[str]:
        reasons: list[str] = []
        if query.element_types and element.element_type not in query.element_types:
            reasons.append("element_type_mismatch")
        if query.approval_statuses and element.approval_status not in query.approval_statuses:
            reasons.append("not_human_approved")
        for field_name in (
            "document_type",
            "section_type",
            "jurisdiction",
            "therapeutic_area",
        ):
            requested = getattr(query, field_name)
            stored = getattr(element, field_name)
            if requested and stored not in ("any", requested):
                reasons.append(f"{field_name}_mismatch")
        if element.valid_until:
            try:
                expiry = datetime.fromisoformat(element.valid_until)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=UTC)
                if expiry < datetime.now(UTC):
                    reasons.append("expired")
            except ValueError:
                reasons.append("invalid_expiry")
        return reasons

    def _record_retrieval(self, query: RetrievalQuery, hit: RetrievalHit) -> None:
        self.connection.execute(
            """INSERT INTO retrieval_events(
            query_text, namespace, element_id, outcome, coarse_score, fine_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                query.text,
                query.namespace,
                hit.element.element_id,
                "hit" if hit.admitted else "rejected",
                hit.coarse_score,
                hit.fine_score,
                now_iso(),
            ),
        )
        self.connection.commit()

    def _touch(self, element_id: str) -> None:
        self.connection.execute(
            """UPDATE semantic_elements SET frequency = frequency + 1,
            last_accessed_at = ? WHERE element_id = ?""",
            (now_iso(), element_id),
        )
        self.connection.commit()

    @synchronized
    def evict(self, max_elements: int) -> list[str]:
        """Evict low-value entries using an LCFU-inspired utility score."""
        rows = self.connection.execute("SELECT * FROM semantic_elements").fetchall()
        if len(rows) <= max_elements:
            return []
        now = datetime.now(UTC)
        scored: list[tuple[float, str]] = []
        for row in rows:
            element = self._row_to_element(row)
            last = datetime.fromisoformat(element.last_accessed_at or element.created_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            age_days = max(0.0, (now - last).total_seconds() / 86400)
            utility = (
                math.log1p(element.frequency) * 2.0
                + element.fetch_cost * 4.0
                + element.latency_ms / 1000.0
                + element.staticity / 5.0
                + authority_weight(element.authority)
                - age_days / 30.0
                - element.size_tokens / 20000.0
            )
            if (
                element.approval_status == "approved"
                and element.authority in {"regulatory", "enterprise"}
            ):
                utility += 10.0
            scored.append((utility, element.element_id))
        scored.sort()
        remove = [element_id for _, element_id in scored[: len(rows) - max_elements]]
        self.connection.executemany(
            "DELETE FROM semantic_elements WHERE element_id = ?", [(item,) for item in remove]
        )
        if self._fts_enabled:
            self.connection.executemany(
                "DELETE FROM semantic_fts WHERE element_id = ?", [(item,) for item in remove]
            )
        self.connection.commit()
        return remove

    @synchronized
    def metrics(self) -> dict[str, Any]:
        total = self.connection.execute("SELECT COUNT(*) FROM retrieval_events").fetchone()[0]
        hits = self.connection.execute(
            "SELECT COUNT(*) FROM retrieval_events WHERE outcome = 'hit'"
        ).fetchone()[0]
        elements = self.connection.execute("SELECT COUNT(*) FROM semantic_elements").fetchone()[0]
        return {
            "elements": elements,
            "retrieval_events": total,
            "semantic_hits": hits,
            "hit_rate": hits / total if total else 0.0,
            "coarse_backend": "sqlite_fts5" if self._fts_enabled else "lexical_scan",
        }

    @staticmethod
    def _row_to_element(row: sqlite3.Row) -> SemanticElement:
        data = dict(row)
        data.pop("rank", None)
        data["value"] = json.loads(data.pop("value_json"))
        data["source_ids"] = json.loads(data.pop("source_ids_json"))
        data["tags"] = json.loads(data.pop("tags_json"))
        return SemanticElement(**data)


def authority_weight(authority: str) -> float:
    return {
        "regulatory": 4.0,
        "enterprise": 3.0,
        "human_review": 2.5,
        "project": 2.0,
        "literature": 1.5,
        "generated": 0.0,
    }.get(authority, 1.0)


def deterministic_fine_judge(
    query: RetrievalQuery,
    element: SemanticElement,
    coarse_score: float,
) -> tuple[bool, float, list[str]]:
    """Conservative local validator used for tests and offline demonstrations."""
    query_tokens = lexical_tokens(query.text)
    key_tokens = lexical_tokens(element.semantic_key + " " + " ".join(element.tags))
    coverage = len(query_tokens & key_tokens) / max(1, len(query_tokens))
    exact = normalize_key(query.text) == element.normalized_key
    source_bonus = min(0.15, authority_weight(element.authority) * 0.03)
    score = min(
        1.0,
        (0.65 if exact else 0.0) + coverage * 0.7 + coarse_score * 0.15 + source_bonus,
    )
    admitted = exact or (coverage >= 0.45 and score >= 0.58)
    reasons = [f"query_coverage={coverage:.3f}", f"authority={element.authority}"]
    if not admitted:
        reasons.append("semantic_equivalence_not_established")
    return admitted, score, reasons


def ingest_elements(store: SemanticElementStore, elements: Iterable[SemanticElement]) -> None:
    for element in elements:
        store.upsert(element)
