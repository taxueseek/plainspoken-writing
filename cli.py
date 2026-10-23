#!/usr/bin/env python3
"""Plainspoken Writing 的 JSON CLI。

给 DSH 插件、编辑器插件或其它宿主调用。只用标准库 + 项目自带规则，
输入 JSON 走 stdin（也支持 --text），输出 JSON 走 stdout。

用法：
    echo '{"text":"综上所述……"}' | python3 cli.py analyze
    echo '{"text":"……","mode":"auto"}' | python3 cli.py rewrite
    echo '{"original":"……","rewritten":"……"}' | python3 cli.py validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.detector import Detector  # noqa: E402
from core.models import RewriteMode  # noqa: E402
from core.rewriter import Rewriter  # noqa: E402
from core.validator import Validator  # noqa: E402


def _dimension_payload(d) -> dict:
    return {
        "id": d.dimension_id,
        "name": d.dimension_name,
        "label_cn": d.label_cn,
        "triggered": d.triggered,
        "severity": round(d.severity, 3),
        "frequency": d.frequency,
        "evidence": d.evidence_text,
        "suggestion": d.suggestion,
        "evidence_tag": d.evidence_tag.value,
    }


def _analysis_payload(analysis) -> dict:
    triggered = analysis.triggered_dimensions()
    return {
        "concentration": analysis.concentration.value,
        "concentration_label": analysis.concentration.label_cn(),
        "concentration_score": analysis.concentration_score,
        "genre": analysis.genre.value,
        "triggered_count": len(triggered),
        "dimensions": [
            _dimension_payload(d)
            for d in sorted(triggered, key=lambda x: x.severity, reverse=True)
        ],
        "anchors": [
            {
                "text": a.text,
                "type": a.anchor_type.value,
                "confidence": a.confidence,
                "protected": a.is_protected,
            }
            for a in analysis.anchor_points
        ],
        "content_quality": (
            {
                "information_density": analysis.content_quality.information_density,
                "specificity": analysis.content_quality.specificity,
                "stance_clarity": analysis.content_quality.stance_clarity,
                "logic_chain": analysis.content_quality.logic_chain,
                "material_match": analysis.content_quality.material_match,
                "purity": analysis.content_quality.purity,
                "passed_count": analysis.content_quality.passed_count,
                "should_proceed": analysis.content_quality.should_proceed,
            }
            if analysis.content_quality
            else None
        ),
        "suggestions": analysis.suggestions,
    }


def _rewrite_payload(result) -> dict:
    return {
        "original": result.original,
        "rewritten": result.rewritten,
        "changed": result.rewritten is not None and result.rewritten != result.original,
        "changes": result.changes,
        "quality_grade": result.quality_grade.value if result.quality_grade else None,
        "passed": result.passed,
        "iteration": result.iteration,
        "hard_criteria": result.hard_criteria,
        "soft_criteria": result.soft_criteria,
    }


def cmd_analyze(payload: dict) -> dict:
    text = payload.get("text", "")
    return _analysis_payload(Detector().analyze(text))


def cmd_rewrite(payload: dict) -> dict:
    text = payload.get("text", "")
    mode_name = payload.get("mode", "auto")
    mode = {
        "auto": RewriteMode.AUTO,
        "question": RewriteMode.QUESTION_DRIVEN,
        "hybrid": RewriteMode.HYBRID,
    }.get(mode_name, RewriteMode.AUTO)
    analysis = Detector().analyze(text)
    result = Rewriter().rewrite(text, analysis, mode)
    return {
        "analysis": _analysis_payload(analysis),
        "rewrite": _rewrite_payload(result),
    }


def cmd_validate(payload: dict) -> dict:
    original = payload.get("original", "")
    rewritten = payload.get("rewritten")
    analysis = Detector().analyze(original)
    result = Validator().validate(original, rewritten, analysis)
    return _rewrite_payload(result)


COMMANDS = {
    "analyze": cmd_analyze,
    "rewrite": cmd_rewrite,
    "validate": cmd_validate,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Plainspoken Writing JSON CLI")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--text", default=None, help="直接传文本，省略则从 stdin 读 JSON")
    parser.add_argument("--mode", default="auto", choices=["auto", "question", "hybrid"])
    args = parser.parse_args()

    try:
        if args.text is not None:
            payload = {"text": args.text, "mode": args.mode}
        else:
            raw = sys.stdin.read().strip()
            payload = json.loads(raw) if raw else {}
        result = COMMANDS[args.command](payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # 宿主需要可解析的错误，而不是 traceback
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
