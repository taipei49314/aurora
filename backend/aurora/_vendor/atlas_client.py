"""Frontier Atlas module SDK -- pure standard library, single file, no deps.

Fleet modules vendor this file (copy it in; there is no package to install) and
use it to submit their findings to the mothership. See MOTHERSHIP.md for the
contract this implements.

    from atlas_client import AtlasClient, RunReport

    report = RunReport("github-radar", code_revision="c1bb9a5",
                       inputs="discover --days 90 --topic llm")
    report.add_finding("agent-zero gained 4,200 stars in the last 90 days.")
    report.add_finding("Three of the top ten new LLM repos vendor llama.cpp.")

    atlas = AtlasClient()
    ws = atlas.ensure_workspace("Fleet")
    run = atlas.submit_run(ws, report)
    cited = atlas.cite_finding(run["module_run_id"], 1,
                              "agent-zero is gaining adoption.")

Nothing here assumes a response field exists just because it should: every
value read off the wire is checked, and a malformed reply raises rather than
propagating a None into the caller's logic.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class AtlasError(RuntimeError):
    """A request was refused, or the reply did not have the promised shape."""

    def __init__(self, message: str, *, status: int | None = None,
                 detail: object = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class RunReport:
    """Builds a contract-shaped run report.

    Findings are validated here as well as server-side. Failing in the module's
    own process, on the line that added the bad finding, is far easier to fix
    than a 422 from an HTTP call three functions away.
    """

    def __init__(self, module_id: str, *, module_version: str = "",
                 code_revision: str = "", inputs: str = "",
                 run_started_at: str | None = None) -> None:
        if not module_id:
            raise ValueError("module_id is required")
        self.module_id = module_id
        self.module_version = module_version
        self.code_revision = code_revision
        self.inputs = inputs
        self.run_started_at = run_started_at or utcnow_iso()
        self._findings: list[str] = []

    def add_finding(self, text: str) -> int:
        """Add one finding. Returns its 1-based index."""
        cleaned = " ".join(str(text).split())
        if not cleaned:
            raise ValueError("a finding cannot be empty")
        if cleaned in self._findings:
            raise ValueError(f"duplicate finding: {cleaned!r}")
        self._findings.append(cleaned)
        return len(self._findings)

    def __len__(self) -> int:
        return len(self._findings)

    @property
    def findings(self) -> list[str]:
        return list(self._findings)

    def render(self) -> str:
        if not self._findings:
            raise ValueError("a run report needs at least one finding")
        lines = [f"# {self.module_id} run", ""]
        lines.append(f"- module_id: {self.module_id}")
        if self.module_version:
            lines.append(f"- module_version: {self.module_version}")
        if self.code_revision:
            lines.append(f"- code_revision: {self.code_revision}")
        lines.append(f"- run_started_at: {self.run_started_at}")
        if self.inputs:
            lines.append(f"- inputs: {self.inputs}")
        lines += ["", "## Findings", ""]
        lines += [f"FINDING {i}: {t}" for i, t in enumerate(self._findings, start=1)]
        return "\n".join(lines) + "\n"


class AtlasClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- transport ---------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None) -> object:
        url = f"{self.base_url}/api{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except (json.JSONDecodeError, AttributeError):
                detail = raw
            raise AtlasError(f"{method} {path} refused ({exc.code}): {detail}",
                             status=exc.code, detail=detail) from exc
        except urllib.error.URLError as exc:
            raise AtlasError(
                f"cannot reach Frontier Atlas at {self.base_url}: {exc.reason}. "
                f"Is the server running?") from exc
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise AtlasError(f"{method} {path} returned non-JSON: {body[:200]!r}") from exc

    @staticmethod
    def _field(result: object, key: str, context: str):
        """Read a required field, or fail loudly. Never returns None silently."""
        if not isinstance(result, dict) or key not in result or result[key] is None:
            raise AtlasError(f"{context}: reply is missing {key!r}", detail=result)
        return result[key]

    # -- workspaces --------------------------------------------------------

    def health(self) -> dict:
        result = self._request("GET", "/health")
        if not isinstance(result, dict):
            raise AtlasError("health check returned an unexpected shape", detail=result)
        return result

    def ensure_workspace(self, name: str, *, description: str = "",
                         scope: str = "") -> str:
        """Return the id of the workspace with this name, creating it if absent."""
        existing = self._request("GET", "/workspaces")
        if isinstance(existing, list):
            for workspace in existing:
                if isinstance(workspace, dict) and workspace.get("name") == name:
                    return self._field(workspace, "id", "workspace lookup")
        created = self._request("POST", "/workspaces",
                                {"name": name, "description": description,
                                 "scope": scope})
        return self._field(created, "id", "workspace creation")

    # -- runs --------------------------------------------------------------

    def submit_run(self, workspace_id: str, report: RunReport) -> dict:
        """Submit a run report. Raises AtlasError with status 409 if unchanged."""
        result = self._request(
            "POST", f"/workspaces/{workspace_id}/modules/{report.module_id}/runs",
            {"report_markdown": report.render(),
             "run_started_at": report.run_started_at,
             "module_version": report.module_version,
             "code_revision": report.code_revision,
             "inputs": report.inputs})
        self._field(result, "module_run_id", "run submission")
        self._field(result, "source_id", "run submission")
        return result  # type: ignore[return-value]

    def cite_finding(self, module_run_id: str, finding_index: int, claim_text: str,
                     *, direction: str = "supports", claim_id: str | None = None,
                     claim_type: str = "factual", notes: str = "") -> dict:
        """Attach a finding to a claim as verbatim evidence.

        Pass `claim_id` to cite an existing claim instead of creating one, so
        several modules can converge on the same statement.
        """
        payload = {"finding_index": int(finding_index), "claim_text": claim_text,
                   "direction": direction, "claim_type": claim_type, "notes": notes}
        if claim_id:
            payload["claim_id"] = claim_id
        result = self._request("POST", f"/module-runs/{module_run_id}/claims", payload)
        self._field(result, "claim_id", "citing a finding")
        self._field(result, "evidence_id", "citing a finding")
        return result  # type: ignore[return-value]

    # -- predictions -------------------------------------------------------

    def register_prediction(self, module_run_id: str, claim_id: str, *,
                            statement: str, resolution_rule: str, null_model: str,
                            horizon_days: int) -> dict:
        """Register a prediction. These fields are frozen once accepted."""
        result = self._request(
            "POST", f"/module-runs/{module_run_id}/predictions",
            {"claim_id": claim_id, "statement": statement,
             "resolution_rule": resolution_rule, "null_model": null_model,
             "horizon_days": int(horizon_days)})
        self._field(result, "id", "prediction registration")
        return result  # type: ignore[return-value]

    def resolve_prediction(self, prediction_id: str, *, outcome: str,
                           evidence_id: str, note: str = "") -> dict:
        """Resolve a prediction. Refused before its horizon, and only once."""
        result = self._request("POST", f"/predictions/{prediction_id}/resolutions",
                               {"outcome": outcome, "evidence_id": evidence_id,
                                "note": note})
        self._field(result, "id", "prediction resolution")
        return result  # type: ignore[return-value]

    def due_predictions(self, workspace_id: str) -> list[dict]:
        """Open predictions, soonest horizon first."""
        result = self._request("GET",
                               f"/workspaces/{workspace_id}/predictions?status=open")
        if not isinstance(result, list):
            raise AtlasError("prediction listing returned an unexpected shape",
                             detail=result)
        return result

    # -- read-only views ---------------------------------------------------

    def fleet(self, workspace_id: str) -> list[dict]:
        result = self._request("GET", f"/workspaces/{workspace_id}/fleet")
        if not isinstance(result, list):
            raise AtlasError("fleet summary returned an unexpected shape",
                             detail=result)
        return result

    def runs(self, workspace_id: str, module_id: str = "") -> list[dict]:
        path = f"/workspaces/{workspace_id}/module-runs"
        if module_id:
            path += "?" + urllib.parse.urlencode({"module_id": module_id})
        result = self._request("GET", path)
        if not isinstance(result, list):
            raise AtlasError("run listing returned an unexpected shape", detail=result)
        return result
