"""The vendored Frontier Atlas SDK must stay identical to its upstream copy.

`_vendor/atlas_client.py` is a copy of `frontier-atlas/sdk/atlas_client.py`, not
a dependency: the engine stays stdlib-only and there is no package to install.
Its own banner says "do not edit here", but nothing enforced that. A "quick fix"
applied to the vendored file — a reworded error, an accidental reformat — would
silently fork the wire contract AURORA submits under, and the fork would only
surface later as a 422 from the mothership, far from the edit that caused it.

The digest is taken after normalizing line endings to LF. A Windows checkout
with `core.autocrlf=true` rewrites CRLF on the way out of git; that is not drift
and must not fail this test.

This pins the copy, not upstream: it cannot see the mothership repo, so it
catches edits made here, not an upstream change AURORA has not picked up yet.
When upstream does change on purpose, re-copy the file and update
`UPSTREAM_SHA256` in the same commit, so the pin records a decision.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# sha256 of frontier-atlas/sdk/atlas_client.py, line endings normalized to LF.
UPSTREAM_SHA256 = "f4d173d45f41ddb081141b7c6a75620893c16cebeaddc8e885f7fe0213ed300e"

VENDORED = (
    Path(__file__).resolve().parents[1]
    / "backend" / "aurora" / "_vendor" / "atlas_client.py"
)


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_vendored_sdk_is_present():
    assert VENDORED.is_file(), f"vendored Frontier Atlas SDK is missing: {VENDORED}"


def test_vendored_sdk_matches_pinned_upstream():
    actual = normalized_sha256(VENDORED)
    assert actual == UPSTREAM_SHA256, (
        "Vendored Frontier Atlas SDK has drifted from the pinned upstream copy.\n"
        f"  file     : {VENDORED}\n"
        f"  expected : {UPSTREAM_SHA256}\n"
        f"  actual   : {actual}\n"
        "Do not edit the vendored file. Re-copy frontier-atlas/sdk/atlas_client.py "
        "over it.\n"
        "If upstream changed on purpose, update UPSTREAM_SHA256 in this test in the "
        "same commit."
    )


def test_vendored_package_still_warns_against_editing():
    """The banner is the only in-repo signal a reader gets before editing."""
    init = VENDORED.parent / "__init__.py"
    assert "Do not edit here" in init.read_text(encoding="utf-8-sig")
