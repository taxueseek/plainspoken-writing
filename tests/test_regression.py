"""回归测试 —— 对比两个版本的基线指标，确保性能不退化。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.baseline_report import generate_report


def run_regression(previous_baseline_path: str | None = None) -> dict:
    """运行回归测试：生成当前基线，与之前版本对比"""
    current = generate_report()

    if previous_baseline_path and Path(previous_baseline_path).exists():
        with open(previous_baseline_path) as f:
            previous = json.load(f)

        regression = {
            "current_version": current["version"],
            "previous_version": previous["version"],
            "generated_at": current["generated_at"],
        }

        failures = []

        # 1. 单元测试不退化
        prev_pass = previous["unit_tests"]["pass_rate"]
        curr_pass = current["unit_tests"]["pass_rate"]
        regression["unit_test_pass_rate"] = {
            "previous": prev_pass,
            "current": curr_pass,
            "delta": round(curr_pass - prev_pass, 1),
            "regression": curr_pass < prev_pass,
        }
        if curr_pass < prev_pass:
            failures.append(f"单元测试通过率从 {prev_pass}% 降为 {curr_pass}%")

        # 2. 区分度不退化
        prev_diff = previous["differentiation"]["diff"]
        curr_diff = current["differentiation"]["diff"]
        regression["differentiation"] = {
            "previous": prev_diff,
            "current": curr_diff,
            "delta": round(curr_diff - prev_diff, 3),
            "regression": curr_diff < prev_diff - 0.05,
        }
        if curr_diff < prev_diff - 0.05:
            failures.append(f"区分度从 {prev_diff} 降为 {curr_diff}")

        # 3. 人工文本误报率不增加
        prev_human_max = previous["corpus_metrics"]["human"]["max"]
        curr_human_max = current["corpus_metrics"]["human"]["max"]
        regression["human_false_positive"] = {
            "previous_max": prev_human_max,
            "current_max": curr_human_max,
            "regression": curr_human_max > max(prev_human_max, 0.15),
        }
        if curr_human_max > max(prev_human_max, 0.15):
            failures.append(f"人工文本误报浓度从 {prev_human_max} 升为 {curr_human_max}")

        # 4. AI 文本召回不退化
        prev_ai_above_03 = previous["corpus_metrics"]["ai"]["above_0_3"]
        curr_ai_above_03 = current["corpus_metrics"]["ai"]["above_0_3"]
        regression["ai_recall"] = {
            "previous_above_0_3": prev_ai_above_03,
            "current_above_0_3": curr_ai_above_03,
            "regression": curr_ai_above_03 < prev_ai_above_03 - 3,
        }
        if curr_ai_above_03 < prev_ai_above_03 - 3:
            failures.append(f"AI文本>0.3的数量从 {prev_ai_above_03} 降为 {curr_ai_above_03}")

        # 5. mixed 边界语料召回不退化（v2.2.0 新增门）
        prev_mixed_avg = previous["corpus_metrics"]["mixed"].get("avg_concentration", 0)
        curr_mixed_avg = current["corpus_metrics"]["mixed"].get("avg_concentration", 0)
        regression["mixed_recall"] = {
            "previous_avg": prev_mixed_avg,
            "current_avg": curr_mixed_avg,
            "regression": curr_mixed_avg < prev_mixed_avg - 0.05,
        }
        if curr_mixed_avg < prev_mixed_avg - 0.05:
            failures.append(f"mixed语料平均浓度从 {prev_mixed_avg} 降为 {curr_mixed_avg}")

        regression["passed"] = len(failures) == 0
        regression["failures"] = failures

    else:
        # 首次运行，无基线可对比
        regression = {
            "current_version": current["version"],
            "previous_version": None,
            "note": "首次基线，无历史对比",
            "passed": True,
        }

    return {
        "current_baseline": current,
        "regression": regression,
    }


def save_regression_report(result: dict):
    """保存回归报告"""
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)

    ver = result["current_baseline"]["version"]
    path = report_dir / f"regression_{ver}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Regression report saved to {path}")

    reg = result["regression"]
    if reg.get("previous_version"):
        print(f"  对比: v{reg['previous_version']} → v{reg['current_version']}")
        for key in ["unit_test_pass_rate", "differentiation", "human_false_positive", "ai_recall"]:
            if key in reg:
                r = reg[key]
                icon = "✅" if not r.get("regression") else "❌"
                print(f"  {icon} {key}: {r.get('previous','?')} → {r.get('current','?')}")

    if reg.get("passed"):
        print("  回归判定: ✅ 全部通过")
    else:
        print(f"  回归判定: ❌ 以下项失败:")
        for f in reg.get("failures", []):
            print(f"    - {f}")

    return path


if __name__ == "__main__":
    # 查找前一个基线（排除当前版本，避免自己对比自己）
    report_dir = Path(__file__).parent.parent / "reports"
    from core import __version__
    baselines = sorted(
        p for p in report_dir.glob("baseline_*.json")
        if p.stem != f"baseline_{__version__}"
    )
    prev = str(baselines[-1]) if baselines else None

    result = run_regression(prev)
    save_regression_report(result)
