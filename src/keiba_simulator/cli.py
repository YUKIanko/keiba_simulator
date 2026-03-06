from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keiba simulator (minimal pipeline).")
    parser.add_argument("pdf", type=Path, help="Path to a race PDF file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory to write JSON outputs",
    )
    parser.add_argument(
        "--trackdata",
        type=Path,
        default=Path("trackdata.json"),
        help="Course database JSON (trackdata.json)",
    )
    parser.add_argument(
        "--llm-check-config",
        type=Path,
        default=Path("llm_extract/config.json"),
        help="Config JSON for local LLM QA check (optional)",
    )
    parser.add_argument(
        "--score-weights",
        type=Path,
        default=Path("score_weights.json"),
        help="Optional JSON to override scoring component weights",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    llm_config = args.llm_check_config if args.llm_check_config.exists() else None
    score_weights = args.score_weights if args.score_weights.exists() else None
    run_pipeline(args.pdf, args.output, args.trackdata, llm_config, score_weights)
    print(f"Output written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
