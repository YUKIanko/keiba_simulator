from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib import request


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM-based JSON extraction from PDF text.")
    parser.add_argument("pdf", type=Path, help="Path to PDF")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="Config JSON")
    parser.add_argument("--schema", type=Path, default=Path("schema.json"), help="Schema JSON")
    parser.add_argument("--output", type=Path, default=Path("llm_output.json"), help="Output JSON")
    args = parser.parse_args()

    config = _load_json(args.config)
    schema = _load_json(args.schema)
    text = _extract_text(args.pdf)

    payload = _build_payload(text, schema, config, repair=False)
    result = _post_json(config["base_url"].rstrip("/") + "/v1/chat/completions", payload)
    content = _extract_content(result)
    parsed = _parse_json_content(content)

    if parsed is None:
        retry_payload = _build_payload(text, schema, config, repair=True)
        retry_result = _post_json(config["base_url"].rstrip("/") + "/v1/chat/completions", retry_payload)
        retry_content = _extract_content(retry_result)
        parsed = _parse_json_content(retry_content)

    if parsed is None:
        raw_path = args.output.with_suffix(".raw.txt")
        raw_path.write_text(content, encoding="utf-8")
        raise ValueError(f"LLM output is invalid JSON. Raw output saved to {raw_path}")

    args.output.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"LLM output written to {args.output}")
    return 0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _build_payload(text: str, schema: dict, config: dict, repair: bool) -> dict:
    system = (
        "You are a data extraction engine. "
        "Return ONLY valid JSON that conforms to the provided schema. "
        "Do not include extra keys, markdown, or commentary."
    )
    if repair:
        system += " The previous response was invalid JSON; return a complete valid JSON object only."
    text_limit = int(config.get("text_limit", 60000))
    user = (
        "Extract race and horse data from the PDF text. "
        "If a field is missing, omit it or set to null. "
        f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"Text:\n{text[:text_limit]}"
    )
    return {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": int(config.get("max_tokens", 4096)),
    }


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_content(response: dict) -> str:
    choices = response.get("choices", [])
    if not choices:
        raise ValueError("No choices in response")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        raise ValueError("Empty response content")
    return content.strip()


def _parse_json_content(content: str) -> dict | None:
    cleaned = _strip_code_fence(content)
    for candidate in (_extract_json_object(cleaned), cleaned):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return content[start : end + 1]


if __name__ == "__main__":
    raise SystemExit(main())
