from __future__ import annotations

import ast
import csv
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "sms_mobile_api_call"
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()[:24]
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
        raise ValueError("not a valid PNG")
    return struct.unpack(">II", raw[16:24])


def validate_manifest() -> dict:
    path = ADDON / "__manifest__.py"
    try:
        manifest = ast.literal_eval(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid manifest: {exc}")
        return {}
    for key in ("name", "version", "license", "depends", "data", "support"):
        if not manifest.get(key):
            fail(f"Manifest key is missing or empty: {key}")
    if len(str(manifest.get("name", ""))) > 25:
        fail("Manifest name exceeds the Odoo Apps 25-character limit")
    if not str(manifest.get("version", "")).startswith("17.0."):
        fail("Manifest version must start with 17.0.")
    if manifest.get("license") != "LGPL-3":
        fail("Expected LGPL-3 for this free open-source add-on")
    for relative in manifest.get("data", []) + manifest.get("images", []):
        if not (ADDON / relative).is_file():
            fail(f"Manifest file does not exist: {relative}")
    return manifest


def validate_sources() -> None:
    for path in ADDON.rglob("*"):
        if path.name == "__pycache__" or path.suffix == ".pyc":
            fail(f"Build artifact must not be published: {path.relative_to(ROOT)}")
        if path.suffix == ".py":
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except Exception as exc:
                fail(f"Python syntax error in {path.relative_to(ROOT)}: {exc}")
        if path.suffix == ".xml":
            try:
                ET.parse(path)
            except Exception as exc:
                fail(f"XML parse error in {path.relative_to(ROOT)}: {exc}")


def validate_access_csv() -> None:
    path = ADDON / "security" / "ir.model.access.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "id", "name", "model_id:id", "group_id:id", "perm_read",
            "perm_write", "perm_create", "perm_unlink",
        }
        if set(reader.fieldnames or []) != required:
            fail("Unexpected ir.model.access.csv header")
        for number, row in enumerate(reader, start=2):
            for key in ("perm_read", "perm_write", "perm_create", "perm_unlink"):
                if row.get(key) not in {"0", "1"}:
                    fail(f"Invalid {key} value on access CSV line {number}")


def validate_marketplace_assets() -> None:
    description = ADDON / "static" / "description"
    index = (description / "index.html").read_text(encoding="utf-8")
    if re.search(r'<a\s+[^>]*href=["\']https?://', index, flags=re.I):
        fail("Marketplace description contains a forbidden external HTTP link")
    if re.search(r"<script\b", index, flags=re.I):
        fail("Marketplace description must not contain JavaScript")
    expected = {
        "icon.png": (256, 256),
        "banner.png": (1200, 450),
        "screenshot_contact.png": (1280, 720),
        "screenshot_conversation.png": (1280, 720),
        "screenshot_inbox.png": (1280, 720),
        "screenshot_actions.png": (1280, 720),
        "screenshot_configuration.png": (1280, 720),
        "screenshot_calls.png": (1280, 720),
    }
    for filename, dimensions in expected.items():
        path = description / filename
        if not path.is_file():
            fail(f"Missing Marketplace image: {filename}")
            continue
        try:
            actual = png_size(path)
        except Exception as exc:
            fail(f"Invalid Marketplace image {filename}: {exc}")
            continue
        if actual != dimensions:
            fail(f"Unexpected dimensions for {filename}: {actual}, expected {dimensions}")


def validate_no_obvious_secrets() -> None:
    secret_patterns = {
        "OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "GitHub token": re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
    }
    for path in ADDON.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in secret_patterns.items():
            if pattern.search(content):
                fail(f"Potential {label} found in {path.relative_to(ROOT)}")


def main() -> int:
    validate_manifest()
    validate_sources()
    validate_access_csv()
    validate_marketplace_assets()
    validate_no_obvious_secrets()
    if ERRORS:
        print("Odoo Apps validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("Odoo Apps validation passed for sms_mobile_api_call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
