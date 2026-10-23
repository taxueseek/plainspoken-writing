"""数据模型 —— Plainspoken Writing 全系统的类型定义。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── 枚举 ─────────────────────────────────────────────

class ConcentrationLevel(Enum):
    """AI 味浓度等级（量化分级）"""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    FATAL = "fatal"

    @classmethod
    def from_score(cls, score: float) -> "ConcentrationLevel":
        if score <= 0.0:
            return cls.NONE
        if score <= 0.3:
            return cls.MILD
        if score <= 0.6:
            return cls.MODERATE
        if score <= 1.0:
            return cls.SEVERE
        return cls.FATAL

    def label_cn(self) -> str:
        return {
            "none": "无",
            "mild": "轻微",
            "moderate": "中等",
            "severe": "严重",
            "fatal": "致命",
        }[self.value]


class QualityGrade(Enum):
    """改写质量等级"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class EvidenceTag(Enum):
    """诊断依据标签 —— 让用户快速判断诊断可靠度"""
    ORIGINAL = "原文"       # 直接引用或概括原文中的具体内容
    LOGICAL = "逻辑"         # 基于前提推导出的结论
    EXPERIENCE = "经验"     # 基于中文写作/阅读经验的判断
    SPECULATION = "推测"    # 可能但不确定的判断
    UNKNOWN = "未知"        # 信息不足无法判断


class AnchorType(Enum):
    """经验锚点类型"""
    TIME = "time"           # 具体时间
    PLACE = "place"         # 具体地点
    PERSON = "person"       # 具体人物
    ACTION = "action"       # 具体动作/行为
    EMOTION = "emotion"     # 具体情绪反应
    SENSORY = "sensory"     # 感官细节
    DATA = "data"           # 具体数据/数字
    STORY = "story"         # 具体叙事片段


class RewriteMode(Enum):
    """改写模式"""
    AUTO = "auto"                    # 自动替换（plainspoken-writing 默认）
    QUESTION_DRIVEN = "question"     # 追问驱动（dbs 风格）
    HYBRID = "hybrid"                # 自动改写 + 关键特征追问


class Genre(Enum):
    """体裁类型"""
    TWEET = "tweet"                    # 个人随笔/推文/短视频文案
    WECHAT = "wechat"                  # 公众号/专栏文章
    ACADEMIC = "academic"              # 学术/正式文体
    BUSINESS = "business"              # 商业报告/工作文档
    MARKETING = "marketing"            # 营销文案
    UNKNOWN = "unknown"                # 未识别


# ── 核心数据类 ────────────────────────────────────────

@dataclass
class DetectionResult:
    """单一 AI 味维度的检测结果"""
    dimension_id: int
    dimension_name: str
    label_cn: str                      # 中文名称，如「结构对称」
    triggered: bool
    severity: float = 0.0              # 0.0 - 1.0
    evidence_text: Optional[str] = None       # 命中的原文片段
    position: Optional[str] = None           # 位置描述
    frequency: int = 0                       # 200字内出现次数
    density_satisfied: bool = False          # 密度条件是否满足
    suggestion: Optional[str] = None
    evidence_tag: EvidenceTag = EvidenceTag.EXPERIENCE

    def __post_init__(self):
        if self.triggered and self.severity == 0.0:
            self.severity = min(1.0, self.frequency / 5.0)


@dataclass
class AnchorPoint:
    """经验锚点 —— 文本中发现的真实经历痕迹"""
    text: str
    anchor_type: AnchorType
    confidence: float = 0.8
    is_protected: bool = False

    def __post_init__(self):
        self.is_protected = self.confidence >= 0.7


@dataclass
class VoiceSignature:
    """作者声音标记 —— 保护区候选"""
    text: str
    reason: str
    category: str      # fossil / emotion / imperfection
    protected: bool = True


@dataclass
class IntentPrompt:
    """追问驱动的改写引导 —— 每个特征对应一个追问方向"""
    dimension_id: int
    prompt: str                        # 追问内容
    intent_desc: str                   # 这个特征背后的可能意图
    self_check: str                    # 追问自检：避免追问本身犯AI特征


@dataclass
class DimensionConfig:
    """AI 味维度的配置（权重、阈值、信号列表）"""
    dimension_id: int
    name: str
    label_cn: str
    weight: float                      # 根因权重 1.5, 并发 1.0, 独立 0.8, 格式 0.3
    keywords: list[str] = field(default_factory=list)
    density_threshold: int = 3         # 200字内触发次数阈值
    is_root_cause: bool = False        # 是否是根因型
    is_independent: bool = False       # 是否是独立信号


@dataclass
class ContentQualityDiagnosis:
    """内容质量前置诊断结果"""
    information_density: float = 0.0     # 0-1
    specificity: float = 0.0
    stance_clarity: float = 0.0
    logic_chain: float = 0.0
    material_match: float = 0.0
    purity: float = 1.0                  # 标题兑现度（taxue 纯度概念）

    @property
    def passed_count(self) -> int:
        return sum(1 for v in [
            self.information_density,
            self.specificity,
            self.stance_clarity,
            self.logic_chain,
            self.material_match,
            self.purity,
        ] if v >= 0.6)

    @property
    def should_proceed(self) -> bool:
        """0-2 项过 → 暂停改写"""
        return self.passed_count >= 3


@dataclass
class FullAnalysis:
    """全文分析结果"""
    text: str
    genre: Genre = Genre.UNKNOWN
    dimensions: list[DetectionResult] = field(default_factory=list)
    concentration: ConcentrationLevel = ConcentrationLevel.NONE
    concentration_score: float = 0.0
    anchor_points: list[AnchorPoint] = field(default_factory=list)
    voice_signatures: list[VoiceSignature] = field(default_factory=list)
    content_quality: Optional[ContentQualityDiagnosis] = None
    sentence_length_stats: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    rewrite_mode: RewriteMode = RewriteMode.AUTO       # 默认自动改写

    def triggered_dimensions(self) -> list[DetectionResult]:
        return [d for d in self.dimensions if d.triggered]

    def top_dimensions(self, n: int = 3) -> list[DetectionResult]:
        return sorted(
            self.triggered_dimensions(),
            key=lambda d: d.severity,
            reverse=True,
        )[:n]


@dataclass
class RewriteResult:
    """改写结果"""
    original: str
    rewritten: str
    changes: list[str] = field(default_factory=list)
    quality_grade: Optional[QualityGrade] = None
    hard_criteria: dict = field(default_factory=dict)
    soft_criteria: dict = field(default_factory=dict)
    iteration: int = 1

    @property
    def passed(self) -> bool:
        return self.quality_grade in (QualityGrade.A, QualityGrade.B)
