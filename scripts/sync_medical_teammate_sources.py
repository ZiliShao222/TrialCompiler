from __future__ import annotations

import csv
import html
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "references" / "metadata" / "medical_teammate_source_index.tsv"
BASE = ROOT / "references" / "inbox" / "medical_teammate" / "原始资料"
STATUS = ROOT / "references" / "metadata" / "medical_teammate_download_status.csv"


def request_url(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> int:
    rows = list(csv.DictReader(INDEX.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    status_rows = []
    for row in rows:
        rel = row.get("本地相对路径", "").replace("\\", "/")
        out = BASE / rel
        exists_before = out.exists()
        result = "already_present" if exists_before else "not_attempted"
        if not exists_before and row.get("官方/原始链接"):
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                content = request_url(row["官方/原始链接"])
                out.write_bytes(content)
                result = "downloaded"
            except Exception as exc:  # noqa: BLE001 - record public-source access failures.
                placeholder = out.with_suffix(".html")
                placeholder.parent.mkdir(parents=True, exist_ok=True)
                placeholder.write_text(
                    "<!doctype html>\n<meta charset=\"utf-8\">\n"
                    f"<title>{html.escape(row.get('资料名称', row.get('ID', 'source')))}</title>\n"
                    f"<h1>{html.escape(row.get('资料名称', row.get('ID', 'source')))}</h1>\n"
                    "<p>Automatic download failed. Use the official link for manual review.</p>\n"
                    f"<p><a href=\"{html.escape(row['官方/原始链接'])}\">{html.escape(row['官方/原始链接'])}</a></p>\n"
                    f"<p>Error: {html.escape(type(exc).__name__ + ': ' + str(exc))}</p>\n",
                    encoding="utf-8",
                )
                result = f"placeholder:{type(exc).__name__}"
                out = placeholder
            time.sleep(0.4)
        final_path = out if out.exists() else BASE / rel
        status_rows.append(
            {
                "ID": row.get("ID", ""),
                "资料名称": row.get("资料名称", ""),
                "module": row.get("模块", ""),
                "result": result,
                "exists": str(final_path.exists()).lower(),
                "bytes": final_path.stat().st_size if final_path.exists() else 0,
                "local_path": str(final_path.relative_to(ROOT)).replace("\\", "/")
                if final_path.exists()
                else str((BASE / rel).relative_to(ROOT)).replace("\\", "/"),
                "url": row.get("官方/原始链接", ""),
            }
        )
        print(row.get("ID", ""), result)
    with STATUS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ID", "资料名称", "module", "result", "exists", "bytes", "local_path", "url"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(status_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
