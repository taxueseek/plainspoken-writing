"""AI 味检测引擎 —— 25 维图谱检测器（融合 dbs 意图层特征）。

核心职责：
1. 关键词快速扫描（覆盖 70% 常见 AI 味）
2. 全量 25 维诊断（根因优先 → 并发验证 → 独立信号）
3. 经验锚点分析
4. 作者声音保护区识别
5. 体裁识别

版本：v1.7.0 — 融合 dbs-ai-check 的 5 个意图层维度：
  #20 堵住所有反驳 / #21 概念命名仪式 / #22 身体替代论证
  #23 深刻过拟合 / #24 同义词刻意替换
"""

import math
import re
from typing import Optional

from .concentration import calc_concentration
from .rules_loader import load_dimension_configs

from .models import (
    AnchorPoint, AnchorType, ConcentrationLevel, ContentQualityDiagnosis,
    DetectionResult, DimensionConfig, EvidenceTag, FullAnalysis,
    Genre, VoiceSignature,
)


# ── 25 维默认配置（融合 dbs-ai-check 的意图层特征）──
# 与 rules/ai_patterns.yaml 完全对齐：yaml 加载失败时回退到本表，
# 两环境的检测行为必须一致（keywords / density / weight 逐项相同）。

_BUILTIN_DIMENSIONS: list[dict] = [
    # 根因型
    {"id": 6,  "name": "authoritative_tone",      "keywords": ["毫无疑问","不言而喻","显而易见","无需质疑","必然","一定是","100%","百分百确定"], "weight": 1.5, "is_root_cause": True,  "density": 3},
    {"id": 16, "name": "cliche_modifiers",         "keywords": ["在当今","随着.*的发展","至关重要","不可或缺","显著提升","在.*背景下","众所周知","不可忽视","显而易见的是","毋庸置疑的是","毋庸讳言","毋庸置疑","全面赋能","多维发力","多措并举","系统性重塑"], "weight": 1.5, "is_root_cause": True,  "density": 2},
    {"id": 10, "name": "translation_ese",          "keywords": ["被证明","被认为","被广泛应用于","这一现象可以被解释为","值得注意的是","可以被视为"], "weight": 1.5, "is_root_cause": True,  "density": 2},
    # 并发型
    {"id": 1,  "name": "structure_symmetry",       "keywords": ["首先","其次","此外","最后","第一","第二","第三","一方面","另一方面"],                    "weight": 1.0, "is_root_cause": False, "density": 2},
    {"id": 2,  "name": "generalization_overload",  "keywords": ["总的来说","综上所述","不难看出","显而易见","从某种意义上说","在很多情况下","大多数"],            "weight": 1.0, "is_root_cause": False, "density": 2},
    {"id": 3,  "name": "empty_emotion",            "keywords": ["令人深思","发人深省","意义深远","非常重要","令人振奋","令人感动","引人深思"],                "weight": 1.0, "is_root_cause": False, "density": 2},
    {"id": 4,  "name": "uniform_sentence_pattern", "keywords": ["不仅","而且","既","又","实现","推动","促进","赋能"],                               "weight": 1.0, "is_root_cause": False, "density": 3},
    {"id": 12, "name": "rlhf_template",            "keywords": [],                                                                                "weight": 1.0, "is_root_cause": False, "density": 3},
    {"id": 14, "name": "conversational_ai_traces", "keywords": ["很荣幸为您","感谢您的耐心","仅代表个人观点","不构成投资建议","让我们共同努力","携手共创","值得一提的是","值得注意","在一定程度","未来可期","前景广阔","希望对您有所启发","希望对你有启发","仅供参考","欢迎在评论区"], "weight": 1.0, "is_root_cause": False, "density": 2},
    # 独立型
    {"id": 5,  "name": "lack_of_detail",           "keywords": ["某个用户","某公司","研究表明","大部分人","很多人","在某些时候"],                 "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 7,  "name": "over_amplification",       "keywords": ["历史性时刻","高光时刻","决定性瞬间","分水岭","里程碑","转折点","划时代","史诗级"], "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 8,  "name": "negative_emotionalism",    "keywords": ["不仅仅","不只是","不是.*?而是","更是一种","更是一份","不仅是.*?更是","不单单是","不在于.*?而在于","真正的.*?是","与其说.*?不如说"], "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 9,  "name": "false_scope",              "keywords": ["从.*到","涵盖了","多个领域","全方位","全链路","一站式"],                         "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 11, "name": "platform_cliche",          "keywords": ["姐妹们谁懂","绝绝子","挖到宝了","家人们","最后一条最重要","点赞收藏","你品你细品","泻药","人在美国"],               "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 15, "name": "flowery_rhetoric",         "keywords": ["如流星划过","如沐春风","醍醐灌顶","时不我待","只争朝夕","温暖了时光","惊艳了岁月"],                        "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 17, "name": "perspective_shift",        "keywords": ["我","我们","你","大家"],                                                                                "weight": 0.8, "is_root_cause": False, "density": 3, "independent": True},
    {"id": 18, "name": "false_causal_link",        "keywords": ["因此","所以","从而","故而","然而","但是","由此可见"],                            "weight": 0.8, "is_root_cause": False, "density": 3, "independent": True},
    {"id": 19, "name": "fake_numbers",             "keywords": [],                                                                                "weight": 0.8, "is_root_cause": False, "density": 1, "independent": True},
    # ── dbs 融合维度（意图层特征, v1.7.0 新增）──
    {"id": 20, "name": "block_all_objections",     "keywords": ["有人可能会说","有人会说","可能有人会质疑","也许有人会问","你可能会觉得"],        "weight": 0.8, "is_root_cause": False, "density": 3, "independent": True},
    {"id": 21, "name": "concept_naming_ritual",    "keywords": ["这就是","我称之为","这就叫","我把这叫做","可以称之为","本质上就是"],             "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 22, "name": "body_substitute_argument", "keywords": ["身体知道答案","直觉告诉你","你的身体比你更","内心会告诉你","相信你的直觉"],      "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    {"id": 23, "name": "deepness_overfit",         "keywords": ["本质上","归根结底","说到底","往深了说","从本质上讲","追根溯源","从底层逻辑来看","底层逻辑","与其说是.*?不如说是","这绝非偶然","这背后折射出"], "weight": 0.8, "is_root_cause": False, "density": 3, "independent": True},
    {"id": 24, "name": "synonym_forced_swap",      "keywords": [],                                                                                "weight": 0.8, "is_root_cause": False, "density": 3, "independent": True},
    # ── taxue 融合维度（结构型AI痕迹 + 纯度, v1.7.0 新增）──
    {"id": 25, "name": "formulaic_structure",       "keywords": ["总结","写在最后","希望对你有帮助","希望对各位","一句话总结","路虽远.*行则将至","让我们拭目以待","未来已来","让我们共同期待"], "weight": 0.8, "is_root_cause": False, "density": 2, "independent": True},
    # 格式型
    {"id": 13, "name": "formatting_ai_traces",     "keywords": ["——"],                                                                           "weight": 0.3, "is_root_cause": False, "density": 3},
]

_LABEL_CN_MAP = {
    1: "结构对称", 2: "概括语言多", 3: "情绪词空洞", 4: "句式整齐",
    5: "缺乏细节", 6: "语气权威", 7: "过度拔高", 8: "否定式煽情",
    9: "虚假范围", 10: "翻译腔", 11: "平台套路", 12: "RLHF模板化",
    13: "格式型痕迹", 14: "交流型痕迹", 15: "口水话修辞", 16: "套话修饰",
    17: "视角混乱", 18: "伪逻辑连接", 19: "数字伪造",
    # dbs 融合维度
    20: "堵住所有反驳", 21: "概念命名仪式", 22: "身体替代论证",
    23: "深刻过拟合", 24: "同义词刻意替换",
    25: "公式化结构（总结/写在最后）",
}


# ── 预编译常量与工具函数 ────────────────────────────

_REGEX_METACHARS = set(".*+?[](){}|^$\\")
_FUNCTION_WORDS = "的着了被把将在"

_PERSPECTIVE_WO_RE = re.compile(r'(?<![^\n])\s*我[^们]')
_PERSPECTIVE_NI_RE = re.compile(r'(?<![的])\b你\b')

_SYNONYM_GROUPS: list[list[str]] = [
    ['方案', '计划', '策略', '路线', '途径'],
    ['方法', '方式', '手段', '手法', '模式'],
    ['核心', '关键', '本质', '根本', '精髓'],
    ['提升', '提高', '增强', '加强', '强化'],
    ['重要', '关键', '核心', '必要', '不可或缺'],
    ['问题', '痛点', '难点', '挑战', '困境'],
    ['价值', '意义', '重要性', '作用', '影响'],
    ['改变', '变革', '转变', '转型', '重塑'],
]

_PERCENT_NUMBER_RE = re.compile(r'\d+\.\d+\s*%')
_SOURCE_WORDS = ('来源', '数据', '报告', '统计', '调查', '据', '统计显示')

_DASH_RE = re.compile('——')
_CURVE_QUOTES_RE = re.compile(r'[""](.+?)[""]')
_EMOJI_RE = re.compile(r'[\U0001F300-\U0001F9FF🎉🔥💡✅❌📌⭐💪✨🎯🔑🚀]')

_PLATFORM_PATTERNS = [
    ("小红书", ["姐妹们谁懂","绝绝子","挖到宝了","谁懂啊","太好看了吧"]),
    ("抖音", ["家人们","最后一条最重要","点赞收藏","划走就找不到了"]),
    ("知乎", ["泻药","人在美国","刚下飞机","先问是不是","圈子太小"]),
    ("B站", ["众所周知","那么问题来了","你品你细品","三连"]),
]

_TIME_PATTERNS = [
    re.compile(r'(去年|今年|上个月|这个月|上周|这周|昨天|今天|周[一二三四五六日])'),
    re.compile(r'(\d{4})年'),
    re.compile(r'(\d{1,2})月(\d{1,2})日'),
]
_ACTION_PATTERNS = [
    re.compile(r'(打开|关掉|点开|输入|写了|跑了|问了|查了|试了|买了|见了|打了|去了|来了).{1,10}'),
]
_DATA_PATTERN = re.compile(r'(?:^|\s)([2-9]\d|[1-9]\d{2,})(?:岁|块|元|个|次|年|天|小时|分钟|%|人|家|万)')
_EMOTION_WORDS = ('懵了', '傻了', '慌了', '哭了', '笑了', '急了', '疯了', '麻了', '手抖', '停了一下')


def _count_keywords_compiled(
    text: str,
    compiled_patterns: Optional[list[tuple[str, re.Pattern]]],
    window: int = 200,
    text_lower: Optional[str] = None,
) -> tuple[int, Optional[str]]:
    """使用预编译正则列表统计 window 窗口内的最大出现次数。"""
    if not compiled_patterns:
        return 0, None
    if text_lower is None:
        text_lower = text.lower()
    first_match = None
    positions: list[int] = []
    for _, pat in compiled_patterns:
        matches = list(pat.finditer(text_lower))
        for m in matches:
            positions.append(m.start())
            if first_match is None:
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                first_match = text[start:end].strip()
    if not positions:
        return 0, None
    positions.sort()
    max_window_count = 0
    left = 0
    for right, pos in enumerate(positions):
        while pos - positions[left] > window:
            left += 1
        max_window_count = max(max_window_count, right - left + 1)
    return max_window_count, first_match


def _count_keywords(text: str, keywords: list[str], window: int = 200,
                    text_lower: Optional[str] = None) -> tuple[int, Optional[str]]:
    """向后兼容的关键词计数接口（未预编译时即时编译）。"""
    if text_lower is None:
        text_lower = text.lower()
    patterns = []
    for kw in keywords:
        if not kw:
            continue
        pat_str = kw if (_REGEX_METACHARS & set(kw)) else re.escape(kw)
        try:
            patterns.append((kw, re.compile(pat_str)))
        except re.error:
            continue
    return _count_keywords_compiled(text, patterns, window=window, text_lower=text_lower)


def _calc_sentence_length_stats(text: str) -> dict:
    """计算句长方差、均值、最长/最短等统计"""
    sentences = re.split(r'[。！？\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    if not sentences:
        return {"count": 0, "mean": 0, "variance": 0, "min": 0, "max": 0}
    lengths = [len(s) for s in sentences]
    n = len(lengths)
    mean = sum(lengths) / n
    variance = sum((x - mean) ** 2 for x in lengths) / n
    return {
        "count": n,
        "mean": round(mean, 1),
        "variance": round(variance, 1),
        "min": min(lengths),
        "max": max(lengths),
        "ratio_max_min": round(max(lengths) / max(1, min(lengths)), 1),
    }


def _detect_perspective_shift(text: str) -> tuple[int, Optional[str]]:
    """检测视角混乱 —— 人称在「我」「我们」「你」之间漂移"""
    segments = re.split(r'\n\n+', text)
    perspectives_found = set()
    for seg in segments:
        if _PERSPECTIVE_WO_RE.search(seg):
            perspectives_found.add("我")
        if '我们' in seg:
            perspectives_found.add("我们")
        if _PERSPECTIVE_NI_RE.search(seg):
            perspectives_found.add("你")
    return (len(perspectives_found), None) if len(perspectives_found) >= 3 else (0, None)


def _detect_synonym_forced_swap(text: str) -> tuple[int, Optional[str]]:
    """检测同义词刻意替换 —— 同一概念在短段落内用不同词重复说。

    优化算法：前置词种数剪枝（种类 < 3 直接跳过）+ 双指针滑窗。
    """
    total = 0
    first_match = None
    for group in _SYNONYM_GROUPS:
        occurrences = []
        words_found = set()
        for w in group:
            pos = 0
            while True:
                idx = text.find(w, pos)
                if idx == -1:
                    break
                occurrences.append((idx, w))
                words_found.add(w)
                pos = idx + len(w)
        if len(words_found) < 3:
            continue
        occurrences.sort(key=lambda x: x[0])
        left = 0
        window_words: dict[str, int] = {}
        for right, (r_pos, r_word) in enumerate(occurrences):
            window_words[r_word] = window_words.get(r_word, 0) + 1
            while r_pos - occurrences[left][0] > 300:
                l_word = occurrences[left][1]
                window_words[l_word] -= 1
                if window_words[l_word] == 0:
                    del window_words[l_word]
                left += 1
            if len(window_words) >= 3:
                total += len(window_words)
                if first_match is None:
                    start = max(0, occurrences[left][0] - 10)
                    first_match = text[start:start+50]
                break
    return min(total, 10), first_match


def _detect_fake_numbers(text: str) -> list[str]:
    """检测数字伪造 —— 精确到小数但无来源"""
    fake_candidates = []
    for m in _PERCENT_NUMBER_RE.finditer(text):
        start = max(0, m.start() - 15)
        prefix = text[start:m.start()]
        if any(src in prefix for src in _SOURCE_WORDS):
            continue
        suffix = text[m.end():m.end()+8]
        if any(src in suffix for src in _SOURCE_WORDS):
            continue
        fake_candidates.append(m.group())
    return fake_candidates


def _detect_rlhf_template(text: str, stats: dict) -> tuple[bool, float]:
    """检测 RLHF 模板化：句长方差过低 + 虚词密度异常"""
    if stats["count"] < 5:
        return False, 0.0
    variance_score = 0.0
    if stats["variance"] < 10:
        variance_score = 1.0
    elif stats["variance"] < 15:
        variance_score = 0.5
    function_words = sum(text.count(c) for c in _FUNCTION_WORDS)
    density = function_words / max(1, len(text))
    density_score = 0.0
    if density > 0.15:
        density_score = 1.0
    elif density > 0.12:
        density_score = 0.5
    score = (variance_score * 0.6 + density_score * 0.4)
    triggered = score >= 0.5
    return triggered, round(score, 2)


def _detect_formatting_traces(text: str) -> tuple[int, Optional[str]]:
    """检测格式型痕迹：破折号/粗体/弯引号/表情符号"""
    count = 0
    first = None
    dash_count = len(_DASH_RE.findall(text))
    if dash_count >= 3:
        count += dash_count
    curve_quotes = len(_CURVE_QUOTES_RE.findall(text))
    if curve_quotes >= 3:
        count += curve_quotes
    emoji = len(_EMOJI_RE.findall(text))
    if emoji >= 3:
        count += emoji
    return min(count, 10), first


def _detect_platform_cliche(text: str,
                              text_lower: Optional[str] = None) -> tuple[int, Optional[str]]:
    """检测平台套路"""
    total = 0
    first_match = None
    for platform, kws in _PLATFORM_PATTERNS:
        c, m = _count_keywords(text, kws, window=400, text_lower=text_lower)
        if c >= 2:
            total += c
            if first_match is None:
                first_match = m
    return total, first_match


def _find_anchors(text: str) -> list[AnchorPoint]:
    """寻找文本中的经验锚点"""
    anchors = []
    for pat in _TIME_PATTERNS:
        for m in pat.finditer(text):
            anchors.append(AnchorPoint(
                text=m.group(),
                anchor_type=AnchorType.TIME,
                confidence=0.8,
            ))
    for pat in _ACTION_PATTERNS:
        for m in pat.finditer(text):
            anchors.append(AnchorPoint(
                text=m.group().strip(),
                anchor_type=AnchorType.ACTION,
                confidence=0.7,
            ))
    for m in _DATA_PATTERN.finditer(text):
        anchors.append(AnchorPoint(
            text=m.group().strip(),
            anchor_type=AnchorType.DATA,
            confidence=0.75,
        ))
    for word in _EMOTION_WORDS:
        if word in text:
            anchors.append(AnchorPoint(
                text=word,
                anchor_type=AnchorType.EMOTION,
                confidence=0.85,
            ))
    seen = set()
    unique = []
    for a in anchors:
        if a.text not in seen:
            seen.add(a.text)
            unique.append(a)
    return unique
    # 数字锚点（大于 1 的具体数字）
    for m in re.finditer(r'(?:^|\s)([2-9]\d|[1-9]\d{2,})(?:岁|块|元|个|次|年|天|小时|分钟|%|人|家|万)', text):
        anchors.append(AnchorPoint(
            text=m.group().strip(),
            anchor_type=AnchorType.DATA,
            confidence=0.75,
        ))
    # 情绪锚点
    emotion_words = ['懵了', '傻了', '慌了', '哭了', '笑了', '急了', '疯了', '麻了', '手抖', '停了一下']
    for word in emotion_words:
        if word in text:
            anchors.append(AnchorPoint(
                text=word,
                anchor_type=AnchorType.EMOTION,
                confidence=0.85,
            ))
    # 去重（按 text 去重）
    seen = set()
    unique = []
    for a in anchors:
        if a.text not in seen:
            seen.add(a.text)
            unique.append(a)
    return unique


def _detect_genre(text: str) -> Genre:
    """体裁识别"""
    # 学术特征（通常篇幅较长）
    academic_signals = ['本文','研究','分析','文献','综述','方法论','数据来源','统计']
    academic_count = sum(1 for s in academic_signals if s in text)
    if academic_count >= 3 and len(text) > 500:
        return Genre.ACADEMIC
    # 营销特征（短文案也常见，优先于长度兜底）
    marketing_signals = ['立即','限时','独家','爆款','抢购','优惠','下单']
    marketing_count = sum(1 for s in marketing_signals if s in text)
    if marketing_count >= 3:
        return Genre.MARKETING
    # 工作文档
    business_signals = ['汇报','周报','项目','团队','进度','KPI','OKR']
    business_count = sum(1 for s in business_signals if s in text)
    if business_count >= 3:
        return Genre.BUSINESS
    if len(text) < 200:
        return Genre.TWEET
    return Genre.WECHAT


def _detect_content_quality(text: str, stats: dict,
                              anchors: Optional[list[AnchorPoint]] = None
                              ) -> ContentQualityDiagnosis:
    """内容质量前置诊断。anchors 由调用方传入，避免重复扫描全文。"""
    dia = ContentQualityDiagnosis()
    # 信息密度：句长 + 锚点数联合估算
    if stats["count"] > 0:
        # 锚点数作为信息密度的替代指标
        if anchors is None:
            anchors = _find_anchors(text)
        anchor_density = len(anchors) / max(1, stats["count"])
        dia.information_density = round(min(1.0, anchor_density * 3), 2)
    # 具体度：是否有具体数字和动作
    has_numbers = bool(re.search(r'\d+', text))
    has_actions = bool(re.search(r'(我|他|她|我们).{0,5}(了|过)', text))
    dia.specificity = 0.8 if (has_numbers and has_actions) else (0.4 if (has_numbers or has_actions) else 0.2)
    # 立场清晰度：是否有明确判断句
    stance_signals = ['我认为','我觉得','在我看来','我的判断','我坚持','我反对','我支持']
    stance_count = sum(1 for s in stance_signals if s in text)
    dia.stance_clarity = min(1.0, stance_count * 0.3 + 0.1)
    # 逻辑链：是否有因果词且有实际因果
    has_causal = bool(re.search(r'(因为|所以|因此|导致|源于)', text))
    dia.logic_chain = 0.7 if has_causal else 0.3
    # 素材匹配：检查标题/开头一致性（简化版：看第一句是不是废话）
    first_sentence = text.split('。')[0] if text else ''
    cliche_starters = ['在当今','随着','众所周知','近年来']
    dia.material_match = 0.3 if any(s in first_sentence for s in cliche_starters) else 0.7
    # 纯度（taxue 标题兑现度）：标题承诺与正文交付的匹配度
    # 简化版：第一段如果有「总结」「综上所述」等概括词 = 标题未兑现
    first_para = text.split('\n\n')[0] if '\n\n' in text else text[:200]
    summary_markers = ['总结','综上所述','总的来说','一句话总结','写在最后']
    dia.purity = 0.3 if any(s in first_para for s in summary_markers) else (
        0.5 if any(s in text for s in ['希望对你有帮助','希望对大家有帮助']) else 1.0
    )
    return dia


# ── 主检测器 ────────────────────────────────────────

class Detector:
    """AI 味检测器 —— 25 维图谱 + 锚点分析 + 体裁识别"""

    def __init__(self, dimension_configs: Optional[list[dict]] = None):
        # 优先用调用方传入的配置；否则读 rules/ai_patterns.yaml；
        # rules/ 缺失或损坏时回退到内置维度表，保证引擎独立可用。
        self.dimensions = (
            dimension_configs
            or load_dimension_configs()
            or [dict(d) for d in _BUILTIN_DIMENSIONS]
        )
        # 预编译每个维度的关键词正则，消除每次检测的重复编译开销
        self._compiled_patterns: dict[int, list[tuple[str, re.Pattern]]] = {}
        for cfg in self.dimensions:
            did = cfg["id"]
            patterns = []
            for kw in cfg.get("keywords", []):
                if not kw:
                    continue
                pat_str = kw if (_REGEX_METACHARS & set(kw)) else re.escape(kw)
                try:
                    patterns.append((kw, re.compile(pat_str)))
                except re.error:
                    continue
            self._compiled_patterns[did] = patterns

        # 策略分发表：将专用检测器解耦注册
        self._special_handlers = {
            17: self._handle_perspective_shift,
            19: self._handle_fake_numbers,
            12: self._handle_rlhf_template,
            24: self._handle_synonym_forced_swap,
            13: self._handle_formatting_traces,
            11: self._handle_platform_cliche,
        }

    def analyze(self, text: str) -> FullAnalysis:
        """对全文执行完整分析"""
        # 预处理
        text = text.strip()
        if not text:
            # 空文本：返回无浓度分析，不抛异常
            return FullAnalysis(text=text, genre=Genre.UNKNOWN)

        # 体裁识别
        genre = _detect_genre(text)
        stats = _calc_sentence_length_stats(text)
        text_lower = text.lower()

        # 经验锚点分析（只算一次，内容质量诊断复用）
        anchors = _find_anchors(text)

        # 内容质量诊断
        content_quality = _detect_content_quality(text, stats, anchors)

        # 根因优先 → 并发合并 → 独立信号 → 格式型
        detection_results: list[DetectionResult] = []
        for cfg in self.dimensions:
            result = self._detect_dimension(text, text_lower, stats, cfg)
            detection_results.append(result)

        # 作者声音保护
        voices = self._identify_voice(text, anchors)

        # 构建临时分析对象用于浓度计算
        temp_analysis = FullAnalysis(
            text=text,
            genre=genre,
            dimensions=detection_results,
            anchor_points=anchors,
            voice_signatures=voices,
            content_quality=content_quality,
            sentence_length_stats=stats,
        )

        # 浓度评分（使用 concentration.py 的统一公式）
        score = calc_concentration(temp_analysis)
        level = ConcentrationLevel.from_score(score)

        # 建议
        suggestions = self._generate_suggestions(detection_results, level, content_quality)

        return FullAnalysis(
            text=text,
            genre=genre,
            dimensions=detection_results,
            concentration=level,
            concentration_score=round(score, 3),
            anchor_points=anchors,
            voice_signatures=voices,
            content_quality=content_quality,
            sentence_length_stats=stats,
            suggestions=suggestions,
        )

    def _handle_perspective_shift(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        freq, _ = _detect_perspective_shift(text)
        trigger = freq >= 3
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=trigger,
            severity=min(1.0, freq / 5.0), frequency=freq,
            evidence_tag=EvidenceTag.ORIGINAL,
        )

    def _handle_fake_numbers(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        fakes = _detect_fake_numbers(text)
        trigger = len(fakes) > 0
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=trigger,
            severity=min(1.0, len(fakes) * 0.5), frequency=len(fakes),
            evidence_text=fakes[0] if fakes else None,
            suggestion=fakes[0] + " — 无来源精确数字，建议改模糊" if fakes else None,
            evidence_tag=EvidenceTag.ORIGINAL,
        )

    def _handle_rlhf_template(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        trigger, sev = _detect_rlhf_template(text, stats)
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=trigger, severity=sev,
            evidence_tag=EvidenceTag.LOGICAL,
        )

    def _handle_synonym_forced_swap(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        freq, first = _detect_synonym_forced_swap(text)
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=freq >= 3,
            severity=min(1.0, freq / 6.0), frequency=freq,
            evidence_text=first,
            suggestion="同一概念在短段落内用不同词重复表述，建议选定一个词重复使用" if freq >= 3 else None,
            evidence_tag=EvidenceTag.LOGICAL,
        )

    def _handle_formatting_traces(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        freq, _ = _detect_formatting_traces(text)
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=freq >= 3,
            severity=min(1.0, freq / 6.0), frequency=freq,
            evidence_tag=EvidenceTag.ORIGINAL,
        )

    def _handle_platform_cliche(
        self, text: str, text_lower: str, stats: dict, cfg: dict, label_cn: str
    ) -> DetectionResult:
        did = cfg["id"]
        freq, first = _detect_platform_cliche(text, text_lower)
        return DetectionResult(
            dimension_id=did, dimension_name=cfg["name"],
            label_cn=label_cn, triggered=freq >= 2,
            severity=min(1.0, freq / 4.0), frequency=freq,
            evidence_text=first,
            evidence_tag=EvidenceTag.ORIGINAL,
        )

    def _detect_dimension(
        self, text: str, text_lower: str, stats: dict, cfg: dict
    ) -> DetectionResult:
        """检测单一维度"""
        did = cfg["id"]
        label_cn = _LABEL_CN_MAP.get(did, cfg.get("name", ""))

        # 特殊维度策略分发
        handler = self._special_handlers.get(did)
        if handler is not None:
            return handler(text, text_lower, stats, cfg, label_cn)

        # 通用关键词检测（使用预编译缓存）
        compiled = self._compiled_patterns.get(did)
        density_thresh = cfg.get("density", 3)
        freq, first_match = _count_keywords_compiled(
            text, compiled, window=200, text_lower=text_lower
        )
        density_met = freq >= density_thresh
        trigger = density_met

        # 对根因型：出现即轻微标记（密度门放宽到 1 次）
        if cfg.get("is_root_cause", False) and freq >= 1:
            trigger = True
            severity = min(1.0, freq / max(1, density_thresh) * 0.8)
        elif cfg.get("independent", False):
            severity = min(1.0, freq / max(1, density_thresh))
        else:
            severity = min(1.0, freq / max(1, density_thresh))

        # 特殊情况：单次出现不算（密度原则）
        if freq == 1 and not cfg.get("is_root_cause", False):
            trigger = False
            severity = 0.1

        # 修法建议
        suggestion = None
        if trigger and first_match:
            suggestion = f"命中：{first_match[:40]}... — {cfg.get('fix', '建议修改')}"

        return DetectionResult(
            dimension_id=did,
            dimension_name=cfg["name"],
            label_cn=label_cn,
            triggered=trigger,
            severity=round(severity, 2),
            evidence_text=first_match[:80] if first_match else None,
            frequency=freq,
            density_satisfied=density_met,
            suggestion=suggestion,
            evidence_tag=EvidenceTag.ORIGINAL if first_match else EvidenceTag.LOGICAL,
        )
        trigger = density_met

        # 对根因型：出现即轻微标记（密度门放宽到 1 次）
        if cfg.get("is_root_cause", False) and freq >= 1:
            trigger = True
            severity = min(1.0, freq / max(1, density_thresh) * 0.8)
        elif cfg.get("independent", False):
            severity = min(1.0, freq / max(1, density_thresh))
        else:
            severity = min(1.0, freq / max(1, density_thresh))

        # 特殊情况：单次出现不算（密度原则）
        if freq == 1 and not cfg.get("is_root_cause", False):
            trigger = False
            severity = 0.1

        # 修法建议
        suggestion = None
        if trigger and first_match:
            suggestion = f"命中：{first_match[:40]}... — {cfg.get('fix', '建议修改')}"

        return DetectionResult(
            dimension_id=did,
            dimension_name=cfg["name"],
            label_cn=label_cn,
            triggered=trigger,
            severity=round(severity, 2),
            evidence_text=first_match[:80] if first_match else None,
            frequency=freq,
            density_satisfied=density_met,
            suggestion=suggestion,
            evidence_tag=EvidenceTag.ORIGINAL if first_match else EvidenceTag.LOGICAL,
        )

    def _identify_voice(self, text: str, anchors: list[AnchorPoint]) -> list[VoiceSignature]:
        """识别作者声音保护区"""
        voices = []
        # 从经验锚点中提取高质量的作者声音
        for a in anchors:
            if a.confidence >= 0.8:
                voices.append(VoiceSignature(
                    text=a.text,
                    reason=f"真实{_anchor_type_cn(a.anchor_type)}锚点 — 只有亲身经历者能写出",
                    category="fossil",
                ))
        # 不完美痕迹
        imperfection_patterns = [
            (r'不对[，,。]?\s*其实', '自我修正 — 真人写作的犹豫痕迹'),
            (r'我想想', '思考过程中的口语化停顿'),
            (r'说(不|不清|不准)', '认知谦逊 — 不确定的表达'),
            (r'可能\s*[是我]也不知道', '坦承不确定'),
        ]
        for pat, reason in imperfection_patterns:
            m = re.search(pat, text)
            if m:
                voices.append(VoiceSignature(
                    text=m.group(),
                    reason=reason,
                    category="imperfection",
                ))
        # 去重
        seen = set()
        return [v for v in voices if v.text not in seen and not seen.add(v.text)]  # type: ignore

    def _generate_suggestions(
        self, results: list[DetectionResult],
        level: ConcentrationLevel,
        quality: ContentQualityDiagnosis,
    ) -> list[str]:
        """生成下一步建议"""
        suggestions = []
        triggered = [r for r in results if r.triggered]

        if level == ConcentrationLevel.FATAL:
            suggestions.append("致命浓度：全文无真人在说话。暂停改写，先想清楚核心观点。")
            return suggestions

        if quality.passed_count <= 2:
            suggestions.append(f"内容质量告警：仅 {quality.passed_count}/5 项通过。建议先补充内容骨架再改表达。")

        if triggered:
            top = sorted(triggered, key=lambda r: r.severity, reverse=True)[:3]
            names = "、".join(r.label_cn for r in top)
            suggestions.append(f"优先处理：{names}（严重度最高）")

        if level in (ConcentrationLevel.SEVERE, ConcentrationLevel.FATAL):
            suggestions.append("建议走整体重写策略（严重浓度）")
        elif level == ConcentrationLevel.MODERATE:
            suggestions.append("建议走重点段落重写策略（中等浓度）")
        elif level == ConcentrationLevel.MILD:
            suggestions.append("建议走局部修改策略（轻微浓度）")

        return suggestions


def _anchor_type_cn(t: AnchorType) -> str:
    return {
        AnchorType.TIME: "时间", AnchorType.PLACE: "地点",
        AnchorType.PERSON: "人物", AnchorType.ACTION: "动作",
        AnchorType.EMOTION: "情绪", AnchorType.SENSORY: "感官",
        AnchorType.DATA: "数据", AnchorType.STORY: "叙事",
    }.get(t, "")
