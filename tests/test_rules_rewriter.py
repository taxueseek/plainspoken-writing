"""P0 修复回归测试：rules 接入 + 改写器诚实性 + 校验器不误判。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detector import Detector, _BUILTIN_DIMENSIONS
from core.models import RewriteMode
from core.rewriter import Rewriter
from core.rules_loader import load_dimension_configs
from core.validator import Validator

AI_TEXT = ("在当今快速发展的 AI 领域，提示词工程已经成为一项至关重要的技能。"
           "值得注意的是，掌握这项技能的人将在未来的职场中占据显著优势。")
HUMAN_TEXT = ("我用 AI 写了三年文案，前半年沉迷收集提示词模板。"
              "有个「万能文案公式」，我试了 20 次，产出的都是正确的废话。")


def test_rules_yaml_loads_and_aligns_with_builtin():
    cfgs = load_dimension_configs()
    assert cfgs is not None
    assert {c["id"] for c in cfgs} == {d["id"] for d in _BUILTIN_DIMENSIONS}
    # yaml 的 density_threshold 必须映射成 density
    c1 = [c for c in cfgs if c["id"] == 1][0]
    assert c1["density"] == 2
    assert "此外" in c1["keywords"]


def test_detector_uses_rules_yaml():
    d = Detector()
    assert len(d.dimensions) == 25


def test_rewriter_honest_when_nothing_to_clean():
    a = Detector().analyze(HUMAN_TEXT)
    r = Rewriter().rewrite(HUMAN_TEXT, a)
    assert r.rewritten is None
    assert r.quality_grade is None
    assert not r.passed


def test_rewriter_cleans_filler_and_does_not_claim_grade():
    a = Detector().analyze(AI_TEXT)
    r = Rewriter().rewrite(AI_TEXT, a)
    assert r.rewritten is not None
    assert r.rewritten != AI_TEXT
    assert "值得注意的是" not in r.rewritten
    # 引擎只做机械清理，不评改写质量
    assert r.quality_grade is None
    assert not r.passed


def test_rewriter_question_driven_does_not_rewrite():
    a = Detector().analyze(AI_TEXT)
    r = Rewriter().rewrite(AI_TEXT, a, mode=RewriteMode.QUESTION_DRIVEN)
    assert r.rewritten is None
    assert r.quality_grade is None


def test_validator_does_not_grade_unchanged_text():
    a = Detector().analyze(HUMAN_TEXT)
    v = Validator().validate(HUMAN_TEXT, HUMAN_TEXT, a)
    assert v.quality_grade is None
    assert v.hard_criteria.get("no_rewrite") is True


def test_validator_does_not_grade_none():
    a = Detector().analyze(HUMAN_TEXT)
    v = Validator().validate(HUMAN_TEXT, None, a)
    assert v.quality_grade is None
    assert v.hard_criteria.get("no_rewrite") is True


def test_builtin_dimensions_match_yaml_exactly():
    """内置维度表与 yaml 必须逐项对齐，两环境检测行为一致。"""
    cfgs = {c["id"]: c for c in load_dimension_configs()}
    builtin = {d["id"]: d for d in _BUILTIN_DIMENSIONS}
    assert set(cfgs) == set(builtin)
    for did in sorted(builtin):
        b, y = builtin[did], cfgs[did]
        assert set(b["keywords"]) == set(y["keywords"]), f"#{did} 关键词不一致"
        assert b.get("density") == y.get("density"), f"#{did} 密度阈值不一致"
        assert bool(b.get("is_root_cause")) == bool(y.get("is_root_cause")), f"#{did} 根因标记不一致"
        assert bool(b.get("independent")) == bool(y.get("independent")), f"#{did} 独立标记不一致"


def test_detector_counts_each_binary_contrast_occurrence():
    """同一句式重复出现要逐次计数，不能被贪婪正则吞成一次。"""
    text = "真正的答案是先活下去。" * 3
    dim8 = next(
        d for d in Detector().analyze(text).dimensions if d.dimension_id == 8
    )
    assert dim8.frequency == 3
    assert dim8.triggered


def test_validator_binary_contrast_penalizes_repeats():
    v = Validator()
    assert v._check_binary_contrast("上周我试了三次才把流程跑通。") == 1.0
    assert v._check_binary_contrast("真正的答案是先活下去。") == 0.8
    assert v._check_binary_contrast("真正的答案是先活下去。" * 2) == 0.4
    assert v._check_binary_contrast(
        "真正的答案是先活下去。与其说这是技术问题不如说是流程问题。"
    ) == 0.4


def test_validator_commitment_fidelity_blocks_strength_upgrade():
    v = Validator()
    assert v._check_commitment_fidelity(
        "这个方案可能会有用。", "这个方案必定有效，100%确保成功。"
    ) == 0.4
    assert v._check_commitment_fidelity(
        "这个方案可能会有用。", "这个方案可能有用。"
    ) == 1.0
    assert v._check_commitment_fidelity(
        "这个方案必然有效。", "这个方案必然有效。"
    ) == 1.0


def test_validator_ending_rejects_hollow_blessing():
    v = Validator()
    assert v._check_ending("流程就这样跑通了。愿你前程似锦。") == 0.2
    assert v._check_ending("流程就这样跑通了。") == 1.0
