"""基线报告生成器 —— 记录当前版本的检测性能指标，用于版本对比。"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import __version__
from tests.test_detector import test_all_dimensions, test_corpus_analysis


def generate_report() -> dict:
    """生成完整基线报告"""
    dim_results = test_all_dimensions()
    corpus_results = test_corpus_analysis()

    human_avg = corpus_results.get("human", {}).get("avg_concentration", 0)
    ai_avg = corpus_results.get("ai", {}).get("avg_concentration", 0)
    differentiation = round(ai_avg - human_avg, 3)

    report = {
        "version": __version__,
        "generated_at": datetime.now().isoformat(),
        "corpus_stats": {
            "total": 130,
            "human": corpus_results.get("human", {}).get("count", 0),
            "ai": corpus_results.get("ai", {}).get("count", 0),
            "mixed": corpus_results.get("mixed", {}).get("count", 0),
        },
        "unit_tests": {
            "tested": dim_results["tested"],
            "passed": dim_results["passed"],
            "failed": dim_results["failed"],
            "pass_rate": dim_results["pass_rate"],
            "details": [
                {
                    "dim_id": d["dim_id"],
                    "name": d["name"],
                    "status": d["status"],
                    "tp": d["tp"],
                    "fp": d["fp"],
                }
                for d in dim_results["details"]
            ],
        },
        "corpus_metrics": {},
        "differentiation": {
            "human_avg": human_avg,
            "ai_avg": ai_avg,
            "diff": differentiation,
            "target": 0.3,
            "passed": differentiation >= 0.3,
        },
    }

    for cat, r in corpus_results.items():
        report["corpus_metrics"][cat] = {
            "avg_concentration": r["avg_concentration"],
            "min": r["min"],
            "max": r["max"],
            "above_0_3": r["above_0_3"],
            "above_0_6": r["above_0_6"],
        }

    return report


def save_report(report: dict):
    """保存报告到文件"""
    report_dir = Path(__file__).parent
    report_dir.mkdir(exist_ok=True)

    # 保存 JSON
    json_path = report_dir / f"baseline_{report['version']}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Baseline report saved to {json_path}")

    # 打印摘要
    print(f"\n{'='*50}")
    print(f"  Say It Human v{report['version']} — 基线报告摘要")
    print(f"{'='*50}")
    print(f"  时间: {report['generated_at'][:19]}")
    print(f"  语料: {report['corpus_stats']['total']} 篇 "
          f"(human={report['corpus_stats']['human']}, "
          f"ai={report['corpus_stats']['ai']}, "
          f"mixed={report['corpus_stats']['mixed']})")
    print(f"  单元测试: {report['unit_tests']['passed']}/{report['unit_tests']['tested']} 通过 "
          f"({report['unit_tests']['pass_rate']}%)")

    for cat in ["human", "ai", "mixed"]:
        m = report["corpus_metrics"][cat]
        print(f"  [{cat}] avg={m['avg_concentration']:.3f}  "
              f">0.3={m['above_0_3']}  >0.6={m['above_0_6']}")

    diff = report["differentiation"]
    status = "✅" if diff["passed"] else "❌"
    print(f"  区分度: {status} {diff['diff']:.3f} (目标 ≥ {diff['target']})")
    print()

    return json_path


if __name__ == "__main__":
    report = generate_report()
    save_report(report)
