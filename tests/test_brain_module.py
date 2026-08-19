"""md-brain ingest wiring. Offline: never calls a real mdbrain binary."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aurora import atlas, brain
from aurora.cli import build_parser, push_to_atlas, push_to_brain


def hypothesis(**kw):
    base = dict(
        hypothesis_id="hyp_test",
        generated_name="test-cluster",
        status="INDUSTRY_CANDIDATE",
        summary="meets candidate thresholds",
        overall_score=72.3,
        confidence_band="MEDIUM",
        entity_ids=["ent_a", "ent_b", "ent_c"],
        existing_industry_similarity={"similarity": 0.0},
        missing_evidence=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def research_run(hypotheses=None):
    return SimpleNamespace(
        run_id="run_test",
        snapshot_id="snap_test",
        cutoff_date=None,
        engine_version="0.1.47",
        feature_version="1",
        taxonomy_version="1",
        created_at="2026-07-27T04:00:00+00:00",
        result_manifest_hash="deadbeef",
        hypotheses=list(hypotheses or [hypothesis()]),
        leakage_manifest={
            "cutoff_date": None,
            "included_observation_count": 10,
            "excluded_future_observation_count": 0,
            "excluded_undated_observation_count": 0,
        },
    )


class FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.mark.unit
def test_fleet_report_is_the_atlas_contract(tmp_path):
    path = brain.write_fleet_report(research_run(), directory=tmp_path, inputs="demo --scale 1")
    text = path.read_text(encoding="utf-8")
    assert path.name.endswith(".fleet.md")
    assert "- module_id: aurora" in text
    assert "FINDING 1:" in text
    assert "test-cluster" in text
    assert "正在成形" not in text


@pytest.mark.unit
def test_empty_findings_are_refused(tmp_path, monkeypatch):
    class Empty:
        def __len__(self):
            return 0

    monkeypatch.setattr(brain.atlas, "build_report", lambda *a, **k: Empty())
    with pytest.raises(brain.BrainError, match="empty report"):
        brain.write_fleet_report(research_run(), directory=tmp_path)


@pytest.mark.unit
def test_argv_calls_mdbrain_ingest_not_atlas(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    binary = tmp_path / "mdbrain.exe"
    binary.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv, **_kwargs):
        calls.append(list(argv))
        return FakeProc(
            stdout='{"id":"abc123abc123","status":"proposed","target_path":"memory/episodic/x.md"}'
        )

    pushed = brain.ingest_run(
        research_run(),
        vault=vault,
        mdbrain_bin=str(binary),
        report_dir=tmp_path / "reports",
        inputs="demo",
        runner=runner,
    )
    assert pushed["proposal_id"] == "abc123abc123"
    argv = calls[0]
    assert argv[0] == str(binary)
    assert "ingest" in argv
    assert "--module" in argv
    assert "aurora" in argv
    assert "github-radar" not in argv
    assert "--vault" in argv
    assert str(vault.resolve()) in argv
    assert any(item.endswith(".fleet.md") for item in argv)


@pytest.mark.unit
def test_missing_vault_fails_closed(tmp_path):
    with pytest.raises(brain.BrainError, match="not a directory"):
        brain.ingest_run(
            research_run(),
            vault=tmp_path / "nope",
            mdbrain_bin=str(tmp_path / "mdbrain.exe"),
        )


@pytest.mark.unit
def test_mdbrain_nonzero_exit_is_brain_error(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    binary = tmp_path / "mdbrain.exe"
    binary.write_text("", encoding="utf-8")

    def runner(_argv, **_kwargs):
        return FakeProc(returncode=1, stdout="already ingested\n")

    with pytest.raises(brain.BrainError, match="already ingested"):
        brain.ingest_run(
            research_run(),
            vault=vault,
            mdbrain_bin=str(binary),
            report_dir=tmp_path / "reports",
            runner=runner,
        )


@pytest.mark.unit
def test_non_json_stdout_fails_closed(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    binary = tmp_path / "mdbrain.exe"
    binary.write_text("", encoding="utf-8")

    def runner(_argv, **_kwargs):
        return FakeProc(stdout="not-json")

    with pytest.raises(brain.BrainError, match="JSON"):
        brain.ingest_run(
            research_run(),
            vault=vault,
            mdbrain_bin=str(binary),
            report_dir=tmp_path / "reports",
            runner=runner,
        )


@pytest.mark.unit
def test_parser_exposes_brain_flags():
    args = build_parser().parse_args(["--brain", r"C:\vaults\nelson"])
    assert args.brain == r"C:\vaults\nelson"
    assert args.brain_bin is None


@pytest.mark.unit
def test_push_failure_does_not_raise(tmp_path, capsys):
    args = SimpleNamespace(brain=str(tmp_path / "missing-vault"), brain_bin=None, brain_report_dir=None)
    push_to_brain(research_run(), None, args)
    err = capsys.readouterr().err
    assert "[brain]" in err
    assert "Vault ingest failed" in err


@pytest.mark.unit
def test_parser_exposes_atlas_flags():
    bare = build_parser().parse_args(["--atlas"])
    assert bare.atlas == "http://127.0.0.1:8000"
    assert bare.atlas_workspace == "Fleet"
    named = build_parser().parse_args(["--atlas", "http://x", "--atlas-workspace", "Lab"])
    assert named.atlas == "http://x"
    assert named.atlas_workspace == "Lab"
    both = build_parser().parse_args(["--atlas", "--brain", r"C:\vaults\nelson"])
    assert both.atlas == "http://127.0.0.1:8000"
    assert both.brain == r"C:\vaults\nelson"


@pytest.mark.unit
def test_atlas_push_failure_does_not_raise(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise atlas.AtlasError("down")

    monkeypatch.setattr(atlas, "push_run", boom)
    args = SimpleNamespace(atlas="http://x", atlas_workspace="Fleet")
    push_to_atlas(research_run(), None, args)
    err = capsys.readouterr().err
    assert "[atlas]" in err
    assert "submit failed" in err


@pytest.mark.unit
def test_atlas_push_reports_findings_without_inventing_baseline(monkeypatch, capsys):
    def fake_push(*_a, **_k):
        return {
            "findings": 2,
            "module_run_id": "mr_abcdef12",
            "report_hash": "0123456789ab",
            "predictions": [],
            "predictions_skipped_reason": "沒有經驗基準率",
        }

    monkeypatch.setattr(atlas, "push_run", fake_push)
    args = SimpleNamespace(atlas="http://x", atlas_workspace="Fleet")
    push_to_atlas(research_run(), None, args)
    out = capsys.readouterr().out
    assert "[atlas] submitted 2 findings" in out
    assert "predictions skipped" in out
    assert "mr_abcde" in out
