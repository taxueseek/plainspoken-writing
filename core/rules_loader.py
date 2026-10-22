"""规则配置加载器 —— 把 rules/*.yaml 读成引擎可用的结构。

引擎默认读 rules/ai_patterns.yaml；文件缺失或损坏时返回 None，
由调用方回退到内置维度表，保证没有 rules/ 的环境也能跑。

注意字段映射：yaml 用 density_threshold，Detector 读 density。
"""

from __future__ import annotations

import copy
import functools
import os
from typing import Optional

import yaml

_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules"
)


def _map_dimension(raw: dict) -> dict:
    """把 yaml 的维度结构映射成 Detector 期望的字段。"""
    return {
        "id": raw["id"],
        "name": raw.get("name", ""),
        "label_cn": raw.get("label_cn", ""),
        "weight": raw.get("weight", 1.0),
        "keywords": raw.get("keywords", []),
        "density": raw.get("density_threshold", 3),
        "is_root_cause": raw.get("is_root_cause", False),
        "independent": raw.get("is_independent", False),
        "fix": raw.get("fix", "建议修改"),
    }


@functools.lru_cache(maxsize=8)
def _cached_raw_dimension_configs(path: str) -> Optional[tuple[dict, ...]]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return None
    dims = tuple(_map_dimension(d) for d in data.get("dimensions", []))
    return dims or None


def load_dimension_configs(path: Optional[str] = None) -> Optional[list[dict]]:
    """加载维度配置。成功返回列表副本，失败返回 None（调用方回退内置表）。"""
    p = path or os.path.join(_RULES_DIR, "ai_patterns.yaml")
    cached = _cached_raw_dimension_configs(p)
    if cached is None:
        return None
    return copy.deepcopy(list(cached))


@functools.lru_cache(maxsize=8)
def _cached_thresholds(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def load_thresholds(path: Optional[str] = None) -> dict:
    p = path or os.path.join(_RULES_DIR, "thresholds.yaml")
    return copy.deepcopy(_cached_thresholds(p))


@functools.lru_cache(maxsize=8)
def _cached_genres(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("genres", [])
    except (OSError, yaml.YAMLError):
        return []


def load_genres(path: Optional[str] = None) -> list[dict]:
    p = path or os.path.join(_RULES_DIR, "genres.yaml")
    return copy.deepcopy(_cached_genres(p))
