"""JSON CLI 回归测试：DSH 插件与外部宿主依赖这三个入口。"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(command: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), command],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(proc.stdout)


def test_cli_analyze_returns_concentration_and_dimensions():
    out = _run("analyze", {
        "text": "综上所述，在当今快速发展的AI领域，提示词工程已经成为一项至关重要的技能。",
    })
    assert out["concentration_score"] > 0
    assert out["triggered_count"] >= 1
    assert isinstance(out["dimensions"], list)


def test_cli_rewrite_strips_filler_without_leading_punctuation():
    out = _run("rewrite", {
        "text": "值得注意的是，综上所述，这个方案很重要。",
        "mode": "auto",
    })
    rewrite = out["rewrite"]
    assert rewrite["changed"] is True
    assert rewrite["rewritten"]
    assert not rewrite["rewritten"].startswith(("，", ",", "。", "；", ";"))


def test_cli_validate_blocks_commitment_upgrade():
    out = _run("validate", {
        "original": "这个方案可能会有用。",
        "rewritten": "这个方案必定有效，100%确保成功。",
    })
    assert out["passed"] is False
    assert out["quality_grade"] in ("C", "D")
