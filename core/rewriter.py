"""改写引擎 —— 机械预清理 + 如实标注。

重要：本引擎是程序库，不能调用 LLM。它能做的只有「机械预清理」
（删套话这类安全变换）；其余改写（打散排比、拆长句、补细节）
必须由 LLM 层完成。

因此本引擎绝不假装改写：
- 没有可机械清理的内容时，rewritten 返回 None，quality_grade 返回 None。
- 有机械清理时，只报告「改了什么」，不评 A/B/C/D（改写质量由 LLM 层判断）。
"""

import re

from .intent_prompts import get_prompt
from .models import (
    ConcentrationLevel, FullAnalysis, IntentPrompt,
    QualityGrade, RewriteMode, RewriteResult,
)
from .validator import Validator

# 可安全删除的套话：不承载结构信息，删掉不改变句意。
# 优先按长度降序匹配，防止较短子串截断较长短语。
# 结构性连接词（首先/其次/此外…）不在这里——它们影响句子流向，交给 LLM 层处理。
_FILLER_PHRASES = [
    "不可否认的是",
    "显而易见的是",
    "不言而喻的是",
    "毋庸置疑的是",
    "值得注意的是",
    "值得一提的是",
    "可以肯定的是",
    "系统性重塑",
    "全方位展现",
    "全面赋能",
    "深度链接",
    "多维发力",
    "多措并举",
    "不难看出",
    "不难发现",
    "显而易见",
    "众所周知",
    "毋庸置疑",
    "毋庸讳言",
    "综合来看",
    "总体而言",
    "总而言之",
    "总的来看",
    "客观而言",
    "深度赋能",
    "综上所述",
    "值得注意",
]


def _pre_clean(text: str) -> tuple[str, list[str]]:
    """机械预清理：删除已知套话，清理残留标点。返回 (清理后文本, 删除的词)。"""
    cleaned = text
    removed: list[str] = []
    for phrase in _FILLER_PHRASES:
        if phrase in cleaned:
            cleaned = cleaned.replace(phrase, "")
            removed.append(phrase)
    # 清理删除后可能残留的重复标点、前导标点和多余空格
    cleaned = re.sub(r"[，,]{2,}", "，", cleaned)
    cleaned = re.sub(r"。{2,}", "。", cleaned)
    cleaned = re.sub(r"^[，,。；;、\s]+", "", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = cleaned.strip()
    return cleaned, removed


class Rewriter:
    """改写执行器"""

    def __init__(self):
        self.validator = Validator()

    def rewrite(self, text: str, analysis: FullAnalysis,
                mode: RewriteMode = RewriteMode.AUTO) -> RewriteResult:
        """根据分析结果执行改写。

        Args:
            text: 原文
            analysis: 检测分析结果
            mode: 改写模式（auto / question_driven / hybrid）

        Returns:
            改写结果。未做改写时 rewritten=None、quality_grade=None。
        """
        level = analysis.concentration

        # 致命浓度 → 拦住
        if level == ConcentrationLevel.FATAL:
            return RewriteResult(
                original=text,
                rewritten=None,
                changes=[self._fatal_block_message(analysis)],
                quality_grade=QualityGrade.D,
                iteration=0,
            )

        # 追问驱动模式：只输出追问清单，不自动改写
        if mode == RewriteMode.QUESTION_DRIVEN:
            return self._question_driven_rewrite(text, analysis)

        # 混合模式：机械预清理 + 关键追问
        if mode == RewriteMode.HYBRID:
            result = self._mechanical_clean(text, analysis)
            questions = self._generate_questions(analysis)
            if questions:
                result.changes.append("\n【追问建议】")
                result.changes.extend(questions)
            return result

        # 默认自动改写（当前仅机械预清理）
        return self._mechanical_clean(text, analysis)

    def _mechanical_clean(self, text: str,
                          analysis: FullAnalysis) -> RewriteResult:
        """机械预清理：删套话。没有可清理内容时如实返回 None。"""
        cleaned, removed = _pre_clean(text)

        changes: list[str] = []
        if removed:
            changes.append("机械预清理（已删除套话）：" + "、".join(removed))

        # 其余建议需 LLM 层执行，这里只列出
        for d in analysis.top_dimensions(5):
            if d.suggestion:
                changes.append(f"来源{d.dimension_id}（{d.label_cn}）— {d.suggestion}")

        if cleaned == text:
            # 没有可机械清理的内容 —— 如实标注，不假装改写
            return RewriteResult(
                original=text, rewritten=None, changes=changes,
                quality_grade=None, iteration=0,
            )

        return RewriteResult(
            original=text, rewritten=cleaned, changes=changes,
            quality_grade=None, iteration=1,
        )

    def _question_driven_rewrite(self, text: str,
                                  analysis: FullAnalysis) -> RewriteResult:
        """追问驱动改写 —— 不对文本做任何修改，只输出追问清单"""
        triggered = [d for d in analysis.dimensions if d.triggered]
        questions = self._generate_questions(analysis)

        changes = [
            f"检测到 {len(triggered)} 个 AI 味来源。\n"
            f"「去AI味 ≠ 好内容。」先搞清楚你自己想怎么写。\n",
        ]
        if questions:
            changes.append("以下按严重度从高到低，每个特征对应一个问题：")
            changes.extend(questions)

        return RewriteResult(
            original=text,
            rewritten=None,  # 不改一字
            changes=changes,
            quality_grade=None,
        )

    def _generate_questions(self, analysis: FullAnalysis) -> list[str]:
        """生成追问列表，按严重度从高到低"""
        triggered = analysis.top_dimensions(5)
        questions = []
        for d in triggered:
            prompt = get_prompt(d.dimension_id)
            if prompt:
                questions.append(
                    f"\n【{d.label_cn}】\n"
                    f"原文：{d.evidence_text or '(整段模式)'}\n"
                    f"追问：{prompt.prompt}"
                )
        return questions

    def _fatal_block_message(self, analysis: FullAnalysis) -> str:
        """致命浓度拦截信息"""
        triggered = [d for d in analysis.dimensions if d.triggered]
        dim_names = "、".join(d.label_cn for d in triggered[:5])
        return (
            f"**问题**：AI 味致命浓度（{len(triggered)} 维触发：{dim_names}）\n"
            "整段没有一个具体的事实。这不仅仅是 AI 味的问题——"
            "是**没有人在说话**。\n\n"
            "**建议**：先想清楚核心观点和想传达的真实经历，"
            "然后带着具体内容回来改写。"
        )
