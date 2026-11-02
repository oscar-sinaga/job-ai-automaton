"""Create a private HTTP Shortcuts import for Android share-to-OSCAR (ADR-020)."""

from __future__ import annotations

import argparse
import json
import os
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse


def identifier(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://oscar.local/android-shortcut/{name}"))


def reference(name: str) -> str:
    return f"/*[variable]*/{json.dumps(identifier(name))}/*[/variable]*/"


def placeholder(name: str) -> str:
    return "{{" + identifier(name) + "}}"


def build_import(api_base: str, api_key: str) -> dict:
    parsed = urlparse(api_base)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not (
            parsed.scheme == "https"
            or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"})
        )
    ):
        raise ValueError("Use a private HTTPS API URL; HTTP is allowed only for loopback tests")
    if not api_key or any(character in api_key for character in "\r\n"):
        raise ValueError("OSCAR_API_KEY must contain one non-empty line")

    before = f"""
const text = getVariable({reference("shared_text")});
let title = getVariable({reference("shared_title")});
if (title === text) title = '';
const match = text.match(/https?:\\/\\/[^\\s<>\"']+/i);
if (!match) throw new Error('No URL found. Share the job link again.');
const url = match[0].replace(/[),.;]+$/, '');
const identity = JSON.stringify([url, title, text]);
if (getVariable({reference("last_share")}) !== identity ||
    !getVariable({reference("capture_key")})) {{
  const key = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {{
    const value = Math.floor(Math.random() * 16);
    return (c === 'x' ? value : ((value & 3) | 8)).toString(16);
  }});
  setVariable({reference("last_share")}, identity);
  setVariable({reference("capture_key")}, key);
}}
setVariable({reference("request_body")}, JSON.stringify({{
  url, page_title: title || undefined, shared_text: text,
  capture_method: 'mobile_share', captured_at: new Date().toISOString()
}}));
""".strip()
    variables = []
    for name in (
        "shared_text",
        "shared_title",
        "last_share",
        "capture_key",
        "request_body",
        "api_key",
    ):
        variables.append(
            {
                "id": identifier(name),
                "key": f"oscar_{name}",
                "type": "constant",
                "value": api_key if name == "api_key" else "",
                "isShareText": name == "shared_text",
                "isShareTitle": name == "shared_title",
                "isSecret": name == "api_key",
                "isExcludeValueFromExport": True,
            }
        )
    shortcut = {
        "id": identifier("shortcut"),
        "name": "Save to OSCAR",
        "description": "Save a shared job link to your private OSCAR inbox.",
        "iconName": "flat_color_star",
        "method": "POST",
        "url": api_base.rstrip("/") + "/jobs/capture",
        "requestBodyType": "custom_text",
        "contentType": "application/json",
        "bodyContent": placeholder("request_body"),
        "headers": [
            {"key": "X-API-Key", "value": placeholder("api_key")},
            {"key": "Idempotency-Key", "value": placeholder("capture_key")},
        ],
        "timeout": 15000,
        "waitForInternet": False,
        "codeOnPrepare": before,
        "codeOnSuccess": (
            "const saved = JSON.parse(response.body); "
            "alert('Saved as ' + saved.ref + '\\nOpen OSCAR later to complete the description.');"
        ),
        "codeOnFailure": (
            "alert('Not saved. Check that OSCAR is reachable, then retry this shortcut.');"
        ),
        "responseHandling": {
            "uiType": "dialog",
            "successOutput": "none",
            "failureOutput": "simple",
        },
    }
    return {
        "version": 92,
        "compatibilityVersion": 90,
        "categories": [{"id": identifier("category"), "name": "OSCAR", "shortcuts": [shortcut]}],
        "variables": variables,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.pilot"))
    parser.add_argument("--api-base-url", required=True, help="Private HTTPS URL ending in /api/v1")
    parser.add_argument(
        "--output", type=Path, required=True, help="Private ZIP containing your API key"
    )
    args = parser.parse_args()
    values = dict(
        line.split("=", 1)
        for line in args.env_file.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    document = build_import(args.api_base_url, values.get("OSCAR_API_KEY", ""))
    args.output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with (
        os.fdopen(descriptor, "wb") as handle,
        zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        archive.writestr("shortcuts.json", json.dumps(document, ensure_ascii=False))
    print(f"Created private Android shortcut: {args.output}")


if __name__ == "__main__":
    main()
