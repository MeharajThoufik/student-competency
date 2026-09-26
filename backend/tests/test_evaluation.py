"""Smoke test of the P5 evaluation pipeline (skipped unless requirements-eval.txt is installed)."""

import json
import sys

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("matplotlib")


def test_quick_evaluation_run(tmp_path, monkeypatch):
    from app.evaluation import run

    monkeypatch.setattr(sys, "argv", ["run", "--out", str(tmp_path), "--quick"])
    run.main()
    results = json.loads((tmp_path / "results.json").read_text())
    for f in results["figures"]:
        assert (tmp_path / f).stat().st_size > 10_000
    assert 0 <= results["trend_default"]["balanced_accuracy"] <= 1
    assert set(results["clustering"]["feature_sets"]) >= {"competency_now", "activity_counts"}
    report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "## Key findings" in report and "## 6. Threats to validity" in report
