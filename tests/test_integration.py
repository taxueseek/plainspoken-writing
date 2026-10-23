"""集成测试 —— 端到端检测 + 浓度 + 改写 + 验证全流程。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.detector import Detector
from core.concentration import calc_concentration, rank_dimensions
from core.rewriter import Rewriter
from core.validator import Validator
from core.models import ConcentrationLevel, FullAnalysis


detector = Detector()
rewriter = Rewriter()
validator = Validator()


def test_full_pipeline():
    """完整流水线测试：检测 → 浓度 → 改写 → 验证"""
    # ── AI 味文本（关键词密集版） ──
    ai_text = (
        "在当今数字化转型的大背景下，数据分析能力已经成为职场人的核心竞争力。"
        "值得注意的是，不仅技术人员需要掌握这项技能，非技术岗位同样不可或缺。"
        "综上所述，掌握数据分析，就是掌握了通向未来的钥匙。"
        "在当今这个知识经济时代，数据素养已经成为推动个人职业发展的重要驱动力。"
        "毫无疑问，这已经成为每一个职场人士的必修课。"
        "首先，要掌握基本的数据处理能力；其次，要学会数据可视化；"
        "最后，要培养数据思维。这三者环环相扣，缺一不可。"
    )

    analysis = detector.analyze(ai_text)
    assert isinstance(analysis, FullAnalysis), "分析应返回 FullAnalysis"
    assert analysis.concentration in (
        ConcentrationLevel.MILD,
        ConcentrationLevel.MODERATE,
    ), f"AI文本浓度应为轻微或中等, 实际为 {analysis.concentration}"

    triggered = [d for d in analysis.dimensions if d.triggered]
    assert len(triggered) >= 1, f"AI 文本应至少触发 1 个维度, 实际触发 {len(triggered)}"
    print(f"  [AI text] 浓度={analysis.concentration_score:.3f} "
          f"({analysis.concentration.label_cn()}), "
          f"触发 {len(triggered)} 维: {[d.label_cn for d in triggered[:3]]}")

    # ── 改写 + 验证 ──
    result = rewriter.rewrite(ai_text, analysis)
    assert result.rewritten is not None, "改写结果不应为空"
    assert result.changes is not None, "应包含改写说明"
    print(f"  [Rewrite] 迭代={result.iteration}, 等级={result.quality_grade.value if result.quality_grade else 'N/A'}")

    validation = validator.validate(ai_text, result.rewritten, analysis)
    assert validation.hard_criteria is not None
    assert validation.soft_criteria is not None
    print(f"  [Validate] 硬指标={all(validation.hard_criteria.values())}, "
          f"软指标达标={sum(1 for v in validation.soft_criteria.values() if v >= 0.6)}/5")

    # ── 人写文本 ──
    human_text = (
        "今天去菜市场买菜，发现猪肉又涨价了。五花肉从去年的二十四涨到了三十五。"
        "卖肉的大姐说：没办法，饲料贵了。我想了想，买了半斤。"
        "出来的时候碰见邻居，她说她准备改吃鸡了。"
    )

    human_analysis = detector.analyze(human_text)
    assert human_analysis.concentration == ConcentrationLevel.NONE, \
        f"人写文本浓度应为无, 实际为 {human_analysis.concentration}"
    print(f"  [Human text] 浓度={human_analysis.concentration_score:.3f} "
          f"({human_analysis.concentration.label_cn()})")

    # ── 高浓度 AI 文本 ──
    heavy_ai_text = (
        "在当今数字化转型的大背景下，数据分析能力已经成为职场人的核心竞争力。"
        "毫无疑问，掌握数据分析技能对于每一个职场人士来说都至关重要。"
        "值得注意的是，这不仅是一项技能，更是一种思维方式。"
        "综上所述，在当今这个充满机遇的时代，数据分析已经不可或缺。"
        "首先，数据处理能力是基础；其次，可视化分析是工具；最后，数据思维是关键。"
        "这三者缺一不可，共同构成了完整的数据分析能力体系。"
        "在当今激烈的职场竞争中，掌握数据分析意味着掌握了通向未来的钥匙。"
    )

    heavy_analysis = detector.analyze(heavy_ai_text)
    # 至少达到轻微浓度
    assert heavy_analysis.concentration.value in ("mild", "moderate", "severe", "fatal"), \
        f"高浓度文本应至少为轻微, 实际为 {heavy_analysis.concentration}"
    triggered_count = len([d for d in heavy_analysis.dimensions if d.triggered])
    print(f"  [Heavy AI text] 浓度={heavy_analysis.concentration_score:.3f} "
          f"({heavy_analysis.concentration.label_cn()}), "
          f"触发 {triggered_count} 维")

    # ── 排名测试 ──
    top = rank_dimensions(analysis)
    assert len(top) <= 3, "rank_dimensions 应返回最多 3 个"
    assert all(t.triggered for t in top), "排名结果应都是触发的维度"


def test_content_quality():
    """内容质量前置诊断测试"""
    poor_text = (
        "这是一个非常重要的问题。我们需要注意一些关键的因素。"
        "总之，这个问题很复杂。"
    )
    analysis = detector.analyze(poor_text)
    cq = analysis.content_quality
    assert cq is not None, "应有内容质量诊断"
    # 这篇 quality 应该不高
    print(f"  [Content quality] 信息={cq.information_density:.2f} "
          f"具体度={cq.specificity:.2f} 立场={cq.stance_clarity:.2f} "
          f"逻辑={cq.logic_chain:.2f} 匹配={cq.material_match:.2f}")


def test_voice_protection():
    """作者声音保护区测试"""
    text_with_voice = (
        "说实话，我对这个方案没什么把握。"
        "不对，其实我想说的是另一回事——这个方案看起来不错但风险太大了。"
        "我也不知道该怎么说，就是觉得不太对劲。"
    )
    analysis = detector.analyze(text_with_voice)
    assert len(analysis.voice_signatures) > 0, \
        f"有口头禅的文本应触发作者声音保护, 实际 {len(analysis.voice_signatures)} 个"
    print(f"  [Voice] 识别到 {len(analysis.voice_signatures)} 个保护区:")
    for v in analysis.voice_signatures[:3]:
        print(f"    - 「{v.text}」({v.reason})")


if __name__ == "__main__":
    print("=" * 50)
    print("  Plainspoken Writing — 集成测试")
    print("=" * 50)

    tests = [
        ("完整流水线", test_full_pipeline),
        ("内容质量诊断", test_content_quality),
        ("声音保护", test_voice_protection),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")

    total = len(tests)
    print(f"\n  通过 {passed}/{total}")
    assert passed == total, f"集成测试: {passed}/{total} 通过"
    print("  全部通过 ✅")
