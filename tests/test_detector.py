"""19 维 AI 味检测单元测试 —— 每个维度独立验证。

测试策略：
- 每个维度至少 2 个用例：一个正例（应该触发），一个反例（不应该触发）
- 正例检测 TP（该触发时触发了）
- 反例检测 FP（不该触发时没触发）
"""

import json
import sys
from pathlib import Path

# 添加项目根到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import DetectionResult, EvidenceTag
from core.detector import Detector


detector = Detector()


def _load_corpus(category: str) -> list[dict]:
    path = Path(__file__).parent / "corpus" / category / "corpus.json"
    with open(path) as f:
        return json.load(f)


# ── 检测函数 ──────────────────────────────────────

def _test_dimension(dim_id: int, trigger_text: str, no_trigger_text: str) -> dict:
    """测试单一维度：正例触发，反例不触发"""
    trigger_result = detector.analyze(trigger_text)
    no_trigger_result = detector.analyze(no_trigger_text)

    dim_trigger = next(d for d in trigger_result.dimensions if d.dimension_id == dim_id)
    dim_no = next(d for d in no_trigger_result.dimensions if d.dimension_id == dim_id)

    return {
        "dim_id": dim_id,
        "name": dim_trigger.label_cn,
        "tp": dim_trigger.triggered,           # 正例：应该触发
        "fp": dim_no.triggered,                 # 反例：不应该触发
        "tp_severity": dim_trigger.severity,
        "trigger_evidence": dim_trigger.evidence_text,
    }


# ── 测试数据 ──────────────────────────────────────

# 每个维度的正例/反例
_DIMENSION_TESTS = [
    # id 1: 结构对称
    (1,
     "首先，要制定计划。其次，要严格执行。最后，要复盘总结。",
     "他想先制定计划，但执行的时候发现计划赶不上变化。"),
    # id 2: 概括语言多
    (2,
     "总的来说，这个问题很复杂。综上所述，我们需要认真对待。不难看出，这是一个系统工程。从某种意义上说，需要多方协同。",
     "这个问题卡了我三天。后来发现是个参数配错了。"),
    # id 3: 情绪词空洞
    (3,
     "这个故事令人深思，发人深省，意义深远。每一个细节都令人感动，令人振奋。",
     "那天晚上我翻来覆去睡不着，脑子里全是这件事。"),
    # id 4: 句式整齐
    (4,
     "我们不仅要实现经济增长，还要推动社会进步，促进公平正义，赋能每一个人。既要有速度，又要有质量，还要有温度。",
     "他说完了。会议室安静了大概五秒。没人说话。"),
    # id 5: 缺乏细节
    (5,
     "研究表明，大部分人都在某些时候遇到过这种情况。某个用户反馈说体验很好。某公司的案例证明了这一点。",
     "上个月我采访了7个用户，6个说这个功能没用。只有一个说还行——他是个老客户。"),
    # id 6: 语气权威
    (6,
     "毫无疑问，这个方案是正确的。不言而喻，结果必然如此。显而易见，这是唯一的选择。百分之百确定这条路走得通。",
     "这个方案我觉得行，但也有可能是我没考虑到的地方。我试过类似的做法，效果还行，但不一定对所有人都适用。"),
    # id 7: 过度拔高
    (7,
     "这是一个历史性时刻，是高光时刻，是决定性瞬间。它标志着分水岭的到来，是里程碑式的转折点。划时代的突破。史诗级的成就。",
     "那天我点了确认键，手抖了一下。从那天起，事情开始变得不一样了。"),
    # id 8: 否定式煽情
    (8,
     "这不仅仅是一本书，更是一种生活方式。他不只是一个老师，更是人生的引路人。这不只是一份工作，更是一份使命。",
     "这双跑鞋重210克，鞋底有缓震胶，后跟带反光条。穿着它跑了半年，膝盖不疼了。"),
    # id 9: 虚假范围
    (9,
     "从企业管理到家庭生活，从职业发展到个人成长，涵盖了多个领域。一站式解决方案，全链路服务，全方位支持。",
     "我们只做一件事——帮餐厅做外卖运营。不做别的。"),
    # id 10: 翻译腔
    (10,
     "这一现象可以被解释为多因素共同作用的结果。它被广泛认为是重要的。值得注意的是，这一发现可以被应用于多个领域。",
     "造成这现象的原因有好几个，我来一个一个说。大家公认这事挺重要的。特别要说的是，这个发现能用在不同地方。"),
    # id 11: 平台套路
    (11,
     "姐妹们谁懂啊！绝绝子！挖到宝了！家人们，最后一条最重要，点赞收藏。你品你细品。",
     "分享一个最近发现的还不错的店铺。东西挺好，价格也合适。"),
    # id 13: 格式型痕迹
    (13,
     "第一——做好准备。第二——开始执行。第三——复盘总结。这三步中——最关键的是第二步。",
     "先做好准备，然后开始执行，最后复盘总结。"),
    # id 14: 交流型痕迹
    (14,
     "很荣幸为您介绍我们的产品。感谢您的耐心阅读。不构成投资建议。让我们共同努力，携手共创。未来可期，前景广阔。值得一提的是，数据表现很好。",
     "给你看看我们这个产品。数据表现不错，尤其在获客方面。"),
    # id 15: 口水话修辞
    (15,
     "时光如流星划过，让人如沐春风。醍醐灌顶的感觉，霎时间温暖了时光，惊艳了岁月。时不我待，只争朝夕。",
     "那个下午我突然想通了一件事。之前纠结了好几个月的问题，其实答案很简单。"),
    # id 16: 套话修饰
    (16,
     "在当今数字化转型的背景下，战略规划至关重要。用户增长不可或缺，品牌建设显著提升。在激烈的市场竞争中，品牌价值不可忽视。众所周知，用户体验是核心。",
     "数字化转型这事我们去年就开始做了。走了不少弯路，但效果确实有——用户量翻了一倍。"),
    # id 18: 伪逻辑连接
    (18,
     "今天下雨了，因此股票跌了。他吃了碗面，所以项目进度推迟了。因此，结论很明显。由此可见，事情没那么简单。",
     "因为支付接口的文档写得不清不楚，对接花了一天时间。后来又发现对方的测试环境不稳定，所以又耽误了半天。"),
    # id 19: 数字伪造
    (19,
     "89.7%的用户对此表示满意。较上季度提升了12.3%。调查显示76.4%的人认同这个观点。",
     "上个月的NPS得分是67，比上个季度涨了5分。数据来自我们自己的后台统计。" ),
    # ── dbs 融合维度（v1.7.0 新增）──
    # id 20: 堵住所有反驳
    (20,
     "有人可能会说这个方案成本太高。有人会说执行难度太大。可能有人会质疑这个效果。你可能会觉得不靠谱。",
     "这个方案我做过三次了，每次都踩不同的坑。第一次预算超了，第二次人手不够。"),
    # id 21: 概念命名仪式
    (21,
     "这就是「增长飞轮效应」。我称之为「内容复利法则」。这就叫「认知差红利」。我把这叫做「流量杠杆」。",
     "这个模式就是持续发内容，然后内容带来更多流量。就这么简单。"),
    # id 22: 身体替代论证
    (22,
     "身体知道答案。你的直觉会告诉你该怎么做。相信你的直觉，你的身体比你更了解什么是对的。内心会告诉你正确的方向。",
     "这事我反复想了三天，最后还是觉得不行。不是因为数据不对，是感觉不对。"),
    # id 23: 深刻过拟合
    (23,
     "本质上，这是一个关于人性的问题。归根结底，所有商业都是信任的变现。说到底，人生的意义在于连接。往深了说，这是一场修行。",
     "这事没那么复杂。用户想要便宜、质量好、送货快。三个都做到，生意就好了。"),
    # id 24: 同义词刻意替换
    (24,
     "我们已经制定了详细的方案。这个计划涵盖了所有关键环节。我们的策略是以用户为核心。这个路线图分为三个阶段。",
     "我们定了三个目标：第一，把用户量翻一倍；第二，把转化率提到5%；第三，把成本降下来。"),
    # ── taxue 融合维度（v1.7.0 新增）──
    # id 25: 公式化结构（总结/写在最后）
    (25,
     "内容就是这样。总结一下，核心观点有三点。写在最后，希望对你有帮助。",
     "内容就是这些。去试试，回来告诉我怎么样。"),
]


# ── 测试执行 ──────────────────────────────────────

def run_all_dimensions() -> dict:
    """运行全部 25 维测试（含 dbs + taxue 融合特征），返回详细统计结果。"""
    results = []
    passed = 0
    failed = 0

    for dim_id, trigger_text, no_trigger_text in _DIMENSION_TESTS:
        r = _test_dimension(dim_id, trigger_text, no_trigger_text)
        tp = r["tp"]
        fp = r["fp"]
        status = "PASS" if (tp and not fp) else ("PARTIAL" if tp else "FAIL")
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        r["status"] = status
        results.append(r)

    return {
        "tested": len(_DIMENSION_TESTS),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / max(1, len(_DIMENSION_TESTS)) * 100, 1),
        "details": results,
    }


def test_all_dimensions():
    """单元测试：验证全部 25 维检测准确性。"""
    res = run_all_dimensions()
    assert res["pass_rate"] == 100.0, f"通过率应为 100%，实际为 {res['pass_rate']}%"


def run_corpus_analysis() -> dict:
    """在全量语料上运行检测，统计分布，返回统计结果。"""
    all_results = {}
    for category in ["human", "ai", "mixed"]:
        texts = _load_corpus(category)
        concentrations = []
        for item in texts:
            try:
                analysis = detector.analyze(item["text"])
                concentrations.append(analysis.concentration_score)
            except Exception:
                pass
        avg = sum(concentrations) / max(1, len(concentrations))
        all_results[category] = {
            "count": len(concentrations),
            "avg_concentration": round(avg, 3),
            "min": round(min(concentrations), 3) if concentrations else 0,
            "max": round(max(concentrations), 3) if concentrations else 0,
            "above_0_3": sum(1 for c in concentrations if c > 0.3),
            "above_0_6": sum(1 for c in concentrations if c > 0.6),
        }
    return all_results


def test_corpus_analysis():
    """单元测试：验证语料库检测统计与基线。"""
    res = run_corpus_analysis()
    assert res["human"]["avg_concentration"] < 0.1, "人工语料平均浓度应极低"
    assert res["ai"]["avg_concentration"] > 0.4, "AI 语料平均浓度应显著偏高"


def print_report():
    """打印完整测试报告"""
    dim_results = run_all_dimensions()
    corpus_results = run_corpus_analysis()

    print("=" * 60)
    print("  Plainspoken Writing — v1.6.0 检测基线报告")
    print("=" * 60)

    print(f"\n## 单元测试：19 维检测精确性")
    print(f"  测试维度：{dim_results['tested']}")
    print(f"  通过：{dim_results['passed']} / 失败：{dim_results['failed']}")
    print(f"  通过率：{dim_results['pass_rate']}%")
    print()
    for d in dim_results["details"]:
        icon = "✅" if d["status"] == "PASS" else ("⚠️" if d["status"] == "PARTIAL" else "❌")
        print(f"  {icon} #{d['dim_id']} {d['name']:8s} TP={d['tp']} FP={d['fp']}")

    print(f"\n## 语料库检测结果")
    total = sum(c["count"] for c in corpus_results.values())
    print(f"  总文本数：{total}")
    for cat, r in corpus_results.items():
        print(f"\n  [{cat}]")
        print(f"    数量：{r['count']}")
        print(f"    平均浓度：{r['avg_concentration']}")
        print(f"    范围：{r['min']} ~ {r['max']}")
        print(f"    浓度 > 0.3：{r['above_0_3']} 篇")
        print(f"    浓度 > 0.6：{r['above_0_6']} 篇")

    # 区分度评估
    human_avg = corpus_results.get("human", {}).get("avg_concentration", 0)
    ai_avg = corpus_results.get("ai", {}).get("avg_concentration", 0)
    diff = ai_avg - human_avg
    print(f"\n## 区分度评估（关键指标）")
    print(f"  人工文本平均浓度：{human_avg}")
    print(f"  AI文本平均浓度：{ai_avg}")
    print(f"  区分度（差异）：{diff:.3f}")
    if diff >= 0.3:
        print(f"  判定：✅ 区分度良好（目标 > 0.3）")
    elif diff >= 0.2:
        print(f"  判定：⚠️ 区分度一般（目标 > 0.3）")
    else:
        print(f"  判定：❌ 区分度不足")

    # 浓度分级分布
    print(f"\n## 浓度分级分布")
    for cat, r in corpus_results.items():
        mild = r["above_0_3"] - r["above_0_6"]
        severe = r["above_0_6"]
        none_count = r["count"] - r["above_0_3"]
        print(f"  [{cat}] 无/轻微={none_count}  中等={mild}  严重/致命={severe}")

    return dim_results, corpus_results


if __name__ == "__main__":
    print_report()
