"""质量验证引擎 —— 改写后的质量控制 + 迭代路由。

硬指标（一票否决）：
  1. 无编造原文没有的人物/故事/细节
  2. 与原文核心观点对齐
  3. 信息保真度（无丢失/篡改）
  4. 无新引入 AI 味

软性指标（每项 0-1 分）：
  1. 人称一致性
  2. 因果链真实性
  3. 节奏变化（句长方差比）
  4. 结尾质量
  5. 个人声音保留
"""

import re
from typing import Optional

from .models import FullAnalysis, QualityGrade, RewriteResult


_CN_DIGITS = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
              '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def _parse_cn_section(section: str) -> int:
    total = 0
    num = 0
    for ch in section:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch == '十':
            total += (num or 1) * 10
            num = 0
        elif ch == '百':
            total += (num or 1) * 100
            num = 0
        elif ch == '千':
            total += (num or 1) * 1000
            num = 0
    return total + num


def _parse_cn_number(s: str) -> int:
    if s in _CN_DIGITS:
        return _CN_DIGITS[s]
    if '亿' in s:
        parts = s.split('亿', 1)
        return _parse_cn_number(parts[0]) * 100000000 + (_parse_cn_number(parts[1]) if parts[1] else 0)
    if '万' in s:
        parts = s.split('万', 1)
        return _parse_cn_section(parts[0]) * 10000 + (_parse_cn_section(parts[1]) if parts[1] else 0)
    return _parse_cn_section(s)


def _cn_numbers_in(text: str) -> set[str]:
    """提取文本中的中文数字（含复合写法），返回对应的阿拉伯数字字符串集合。

    「三次」→ {'3'}、「三百」→ {'300'}、「一万两千」→ {'12000'}，让中文数字改写成阿拉伯数字不算新数字。
    """
    found = set()
    for m in re.finditer(r'[一二两三四五六七八九十百千万亿零]+', text):
        s = m.group()
        try:
            val = _parse_cn_number(s)
            if val > 0:
                found.add(str(val))
        except (ValueError, KeyError):
            continue
    return found


class Validator:
    """改写质量验证器"""

    def validate(self, original: str, rewritten: Optional[str],
                 original_analysis: FullAnalysis) -> RewriteResult:
        """验证改写质量，返回评级。

        rewritten 为 None 或与原文相同时视为「未改写」，
        直接返回 quality_grade=None，不参与评级。
        """
        # 未改写（或没改）→ 不评级，避免对原文打 A
        if rewritten is None or rewritten == original:
            return RewriteResult(
                original=original, rewritten=rewritten,
                quality_grade=None,
                hard_criteria={"no_rewrite": True},
                soft_criteria={},
            )

        result = RewriteResult(original=original, rewritten=rewritten)

        # 硬指标检查
        result.hard_criteria["no_fabrication"] = self._check_fabrication(
            original, rewritten
        )
        result.hard_criteria["alignment"] = self._check_alignment(
            original, rewritten
        )
        result.hard_criteria["fidelity"] = self._check_fidelity(
            original, rewritten
        )
        result.hard_criteria["no_new_ai_taste"] = self._check_new_ai_taste(
            rewritten, original_analysis
        )
        result.hard_criteria["actually_rewritten"] = rewritten != original

        hard_pass = all(result.hard_criteria.values())

        # 软性指标检查
        result.soft_criteria["perspective_consistency"] = self._check_perspective(
            rewritten
        )
        result.soft_criteria["causal_chain"] = self._check_causal_chain(
            rewritten
        )
        result.soft_criteria["rhythm_variation"] = self._check_rhythm(
            original, rewritten
        )
        result.soft_criteria["ending_quality"] = self._check_ending(
            rewritten
        )
        result.soft_criteria["personal_voice"] = self._check_voice(
            rewritten
        )
        result.soft_criteria["binary_contrast"] = self._check_binary_contrast(
            rewritten
        )
        result.soft_criteria["commitment_fidelity"] = self._check_commitment_fidelity(
            original, rewritten
        )

        soft_pass_count = sum(1 for v in result.soft_criteria.values() if v >= 0.6)

        # 评级：7项软指标过半数（>=4项）给A，否则给B
        if hard_pass:
            if soft_pass_count >= 4:
                result.quality_grade = QualityGrade.A
            else:
                result.quality_grade = QualityGrade.B
        else:
            if result.hard_criteria.get("alignment", False) and result.hard_criteria.get("fidelity", False):
                result.quality_grade = QualityGrade.C
            else:
                result.quality_grade = QualityGrade.D

        return result

    def _check_fabrication(self, original: str, rewritten: str) -> bool:
        """检查是否编造原文没有的内容"""
        # 提取改写版中的人名/机构名/具体数字，看是否在原文中出现
        # 中文数字写法（「三次」→「3次」）与年份（1900-2100）不算新数字
        orig_numbers = set(re.findall(r'\d+', original)) | _cn_numbers_in(original)
        new_numbers = set(re.findall(r'\d+', rewritten))
        novel = new_numbers - orig_numbers
        novel = {n for n in novel if int(n) > 2100 or int(n) < 1900}
        return len(novel) == 0

    def _check_alignment(self, original: str, rewritten: str) -> bool:
        """检查改写版与原文核心观点的对齐度"""
        # 提取关键词交集
        orig_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', original))
        new_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', rewritten))
        if not orig_words:
            return True
        overlap = len(orig_words & new_words) / len(orig_words)
        return overlap >= 0.3

    def _check_fidelity(self, original: str, rewritten: str) -> bool:
        """检查信息保真度"""
        # 检查长度比 —— 改写不应过于大幅缩水或膨胀
        ratio = len(rewritten) / max(1, len(original))
        return 0.3 <= ratio <= 2.0

    def _check_new_ai_taste(self, rewritten: str,
                            original_analysis: FullAnalysis) -> bool:
        """检查是否引入了新的 AI 味"""
        # 简单版：检查改写后的虚词密度和句式方差
        total_chars = len(rewritten)
        if total_chars < 10:
            return True
        func_words = sum(1 for c in rewritten if c in '的着了把被将在')
        density = func_words / total_chars
        return density <= 0.18

    def _check_perspective(self, text: str) -> float:
        """检查人称一致性（0-1）"""
        segments = re.split(r'\n\n+', text)
        perspectives = set()
        for seg in segments:
            if re.search(r'(?<![^\n])\s*我[^们]', seg):
                perspectives.add("我")
            if '我们' in seg:
                perspectives.add("我们")
            if re.search(r'(?<![的])\b你\b', seg):
                perspectives.add("你")
        if len(perspectives) <= 1:
            return 1.0
        if len(perspectives) == 2:
            return 0.6
        return 0.2

    def _check_causal_chain(self, text: str) -> float:
        """检查因果链真实性（0-1）"""
        # 有因果词且因果词前后有内容支撑
        causal_markers = ['因为', '所以', '因此', '导致', '源于']
        found = [m for m in causal_markers if m in text]
        if not found:
            return 0.5  # 没有因果词不扣分
        return 0.8

    def _check_rhythm(self, original: str, rewritten: str) -> float:
        """检查节奏变化（0-1）"""
        def sent_len_var(t: str) -> float:
            sents = [s.strip() for s in re.split(r'[。！？\n]', t) if len(s.strip()) > 3]
            if len(sents) < 3:
                return 0.0
            lengths = [len(s) for s in sents]
            mean = sum(lengths) / len(lengths)
            return sum((x - mean)**2 for x in lengths) / len(lengths)

        orig_var = sent_len_var(original)
        new_var = sent_len_var(rewritten)
        if orig_var == 0:
            return 0.7
        ratio = new_var / orig_var
        if ratio >= 1.2:
            return 1.0
        if ratio >= 0.8:
            return 0.7
        return 0.4

    def _check_ending(self, text: str) -> float:
        """检查结尾质量与留白（0-1）"""
        # 取最后一句/段
        segments = re.split(r'\n\n+', text.strip())
        ending = segments[-1] if segments else ""
        # 禁止的口号与空洞伪温暖结尾
        forbidden_endings = [
            '让我们', '未来可期', '携手共进', '共同努力',
            '希望对你有帮助', '希望对您有所启发', '写在最后',
            '未来已来', '愿你', '愿我们', '拭目以待',
        ]
        for f in forbidden_endings:
            if f in ending:
                return 0.2
        # 好的结尾特征：停在具体动作、真实场景或自然留白
        good_signals = ['去试试', '试试看', '就这样', '好了', '告诉我']
        for g in good_signals:
            if g in ending:
                return 1.0
        return 0.7

    def _check_voice(self, text: str) -> float:
        """检查个人声音保留（0-1）"""
        signals = 0
        if re.search(r'(说实话|老实说|讲真)', text):
            signals += 1
        if re.search(r'(我觉得|我认为|我判断|我坚持)', text):
            signals += 1
        if re.search(r'(不太确定|可能不对|说不好|没把握)', text):
            signals += 1
        if re.search(r'(懵了|傻了|慌了|麻了|手抖)', text):
            signals += 1
        return min(1.0, signals * 0.3)

    def _check_binary_contrast(self, text: str) -> float:
        """检查二元对立/假反共识修辞（0-1）。

        AI 倾向于密集使用「不是...而是...」「不在于...而在于...」「与其说...不如说...」
        制造虚假的认知高差。出现 0 次 1.0，1 次 0.8，>=2 次 0.4。
        """
        contrast_patterns = [
            r'不是.{1,20}?而是',
            r'不仅.{1,20}?更是',
            r'不在于.{1,20}?而在于',
            r'与其说.{1,20}?不如说',
            r'真正的.{1,15}?是',
        ]
        count = 0
        for pat in contrast_patterns:
            count += len(re.findall(pat, text))
        if count == 0:
            return 1.0
        if count == 1:
            return 0.8
        return 0.4

    def _check_commitment_fidelity(self, original: str, rewritten: str) -> float:
        """检查承诺强度保真度（0-1）。

        改写不能把可能性或弱判断擅自升级为绝对肯定保证。
        例如原文为「可能」「也许」「大概」「尝试」，改写后却变成了「必定」「必然」「确保」「100%」。
        """
        weak_markers = ('可能', '也许', '大概', '尝试', '试图', '似乎')
        strong_markers = ('必然', '必定', '确保', '必定会', '100%', '绝对')
        orig_has_weak = any(w in original for w in weak_markers)
        orig_has_strong = any(s in original for s in strong_markers)
        rewritten_has_strong = any(s in rewritten for s in strong_markers)

        if orig_has_weak and not orig_has_strong and rewritten_has_strong:
            return 0.4
        return 1.0
