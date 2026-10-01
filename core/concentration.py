"""浓度量化引擎 —— 将 AI 味检测结果转化为可比较的数值评分。

核心公式：
  浓度得分 = ∑(检测到的来源 × 权重因子) ÷ 文本长度 × 密度因子

其中：
- 权重因子：根因型 1.5 / 并发型 1.0 / 独立型 0.8 / 格式型 0.3
- 密度因子：基于句长方差、保护区覆盖度等调节
"""

from .models import ConcentrationLevel, FullAnalysis, DetectionResult


def calc_concentration(analysis: FullAnalysis) -> float:
    """计算 AI 味浓度评分（0.0 ~ 1.5+）

    方法：按触发维度类型加权计数，不按权重归一化。

    每类贡献值：
    - 根因型（#6 权威语气 / #16 套话 / #10 翻译腔）：每个 0.25
    - 并发型（#1 对称 / #4 整齐 / #12 RLHF / #14 交流型 / #2 概括 / #3 空洞）：每个 0.12
    - 独立型（#5 缺细节 / #7 拔高 / #8 / #9 / #11 / #15 / #17 / #18 / #19）：每个 0.06
    - 格式型（#13）：每个 0.03

    密度调节：
    - 句长方差 < 10: 乘 1.5（节奏单调加重）
    - 锚点密度 > 0.3: 乘 0.7（经验锚点多 → 降低浓度）
    - 保护区覆盖 > 30%: 乘 0.5
    """
    triggered = [d for d in analysis.dimensions if d.triggered]
    if not triggered:
        return 0.0

    # 按类型计分
    score = 0.0
    for d in triggered:
        did = d.dimension_id
        if did in (6, 16, 10):
            score += 0.25 * d.severity      # 根因型
        elif did in (1, 2, 3, 4, 12, 14):
            score += 0.12 * d.severity      # 并发型
        elif did in (5, 7, 8, 9, 11, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25):
            score += 0.06 * d.severity      # 独立型
        elif did == 13:
            score += 0.03 * d.severity      # 格式型

    # 密度调节
    stats = analysis.sentence_length_stats
    sent_count = max(1, stats.get("count", 1))

    # 句长方差 < 10 → 节奏单调加重
    if stats.get("variance", 999) < 10 and sent_count > 3:
        score *= 1.5

    # 经验锚点密度高 → 降低浓度
    anchor_density = len(analysis.anchor_points) / sent_count
    if anchor_density > 0.3:
        score *= 0.7

    # 保护区覆盖
    if analysis.voice_signatures:
        coverage = len(analysis.voice_signatures) / sent_count
        if coverage > 0.3:
            score *= 0.5

    return round(min(2.0, score), 3)


def calc_dimension_severity(d: DetectionResult, analysis: FullAnalysis) -> float:
    """计算单个维度的最终严重度（含体裁调整）"""
    base = d.severity
    # 根因型维度触发后加重
    if d.dimension_id in (6, 16, 10) and d.triggered:
        base *= 1.2
    return round(min(1.0, base), 2)


def rank_dimensions(analysis: FullAnalysis, top_n: int = 3) -> list[DetectionResult]:
    """按严重度排序，返回最需要处理的 N 个维度"""
    triggered = [d for d in analysis.dimensions if d.triggered]
    # 根因优先（同等严重度下根因型排前面）
    def sort_key(d: DetectionResult) -> tuple:
        is_root = -1 if d.dimension_id in (6, 16, 10) else 0
        return (-d.severity, is_root, d.dimension_id)
    triggered.sort(key=sort_key)
    return triggered[:top_n]
