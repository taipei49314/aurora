"""Small release contracts that keep schema and frontend identities aligned."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[1]


def test_source_provenance_aliases_are_documented_on_source_metadata() -> None:
    schema = json.loads(
        (ROOT / "examples" / "schemas" / "import-package.schema.json").read_text(
            encoding="utf-8"
        )
    )
    entity_description = schema["$defs"]["entity"]["properties"]["metadata"].get(
        "description", ""
    )
    source_description = schema["$defs"]["source"]["properties"]["metadata"].get(
        "description", ""
    )
    assert "provenance_aliases" not in entity_description
    assert "provenance_aliases" in source_description


def test_stats_queries_are_keyed_by_full_manifest_identity() -> None:
    dashboard = (ROOT / "frontend" / "src" / "pages" / "Dashboard.tsx").read_text(
        encoding="utf-8"
    )
    explorer = (
        ROOT / "frontend" / "src" / "pages" / "DataExplorer.tsx"
    ).read_text(encoding="utf-8")
    api_client = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")

    for source in (dashboard, explorer):
        assert 'queryKey: ["stats", statsManifest]' in source
        assert "getStats(statsManifest)" in source
        assert "enabled: !!statsManifest" in source
    assert "input_manifest_hash: string" in api_client
    assert "result.input_manifest_hash !== expectedManifestHash" in api_client
