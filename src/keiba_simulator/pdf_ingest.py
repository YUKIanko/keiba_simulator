from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import List


@dataclass
class PdfIngestResult:
    text: str
    warnings: List[str]


def extract_text(pdf_path: Path) -> PdfIngestResult:
    warnings: List[str] = []
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    tool = which("pdftotext")
    if tool is None:
        warnings.append("pdftotext not found; PDF text extraction skipped.")
        return PdfIngestResult(text="", warnings=warnings)

    try:
        # Use pdftotext for a quick, dependency-free extraction path.
        proc = subprocess.run(
            [tool, "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return PdfIngestResult(text=proc.stdout, warnings=warnings)
    except subprocess.CalledProcessError as exc:
        warnings.append(f"pdftotext failed: {exc}")
        return PdfIngestResult(text="", warnings=warnings)
