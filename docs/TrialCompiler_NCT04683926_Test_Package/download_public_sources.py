"""Download the official public source documents for the NCT04683926 test case."""
from __future__ import annotations

from pathlib import Path
import sys
import urllib.request

SOURCES = {
    "NCT04683926_Protocol_v1.2_2020-05-11.pdf": "https://cdn.clinicaltrials.gov/large-docs/26/NCT04683926/Prot_SAP_000.pdf",
    "NCT04683926_SAP_v1.0_2021-02-09.pdf": "https://cdn.clinicaltrials.gov/large-docs/26/NCT04683926/SAP_001.pdf",
    "NCT04683926_ICF_2020-07-29.pdf": "https://cdn.clinicaltrials.gov/large-docs/26/NCT04683926/ICF_002.pdf",
}


def main() -> int:
    target = Path(__file__).resolve().parent / "public_sources"
    target.mkdir(exist_ok=True)
    failures = 0
    for filename, url in SOURCES.items():
        destination = target / filename
        try:
            print(f"Downloading {filename} ...")
            request = urllib.request.Request(url, headers={"User-Agent": "TrialCompiler-Test-Package/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                destination.write_bytes(response.read())
            print(f"Saved: {destination}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR downloading {url}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
