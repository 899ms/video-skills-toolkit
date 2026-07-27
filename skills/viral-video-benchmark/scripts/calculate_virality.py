#!/usr/bin/env python3
"""Deterministically classify a Douyin or Xiaohongshu video."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NamedTuple


SCHEMA_VERSION = 1
PLATFORM_ALIASES = {
    "douyin": "douyin",
    "xhs": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
}
TIER_RULES = (
    (10_000, "S", Decimal("0.30")),
    (100_000, "A", Decimal("0.15")),
    (1_000_000, "B", Decimal("0.08")),
    (None, "C", Decimal("0.04")),
)
BENCHMARK_ACCOUNT_MULTIPLIER = 20
VIEW_BREAKOUT_MULTIPLIER = Decimal("20")
MINIMUM_BREAKOUT_VIEWS = 10_000


class ParsedCount(NamedTuple):
    value: int
    rounded_source: bool


def parse_count(raw: Any, field: str) -> ParsedCount:
    if isinstance(raw, bool) or raw is None:
        raise ValueError(f"{field} must be a visible numeric count")
    if isinstance(raw, int):
        if raw < 0:
            raise ValueError(f"{field} must not be negative")
        return ParsedCount(raw, False)
    if isinstance(raw, float):
        if raw < 0 or not raw.is_integer():
            raise ValueError(f"{field} must be an integer count")
        return ParsedCount(int(raw), False)
    if not isinstance(raw, str):
        raise ValueError(f"{field} must be a string or integer")

    text = raw.strip().replace(",", "").replace(" ", "")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(万|[wW])?(\+)?", text)
    if not match:
        raise ValueError(f"{field} has unsupported count format: {raw!r}")

    number_text, suffix, plus = match.groups()
    if suffix is None and "." in number_text:
        raise ValueError(f"{field} cannot use a decimal without 万/w")
    try:
        number = Decimal(number_text)
    except InvalidOperation as exc:
        raise ValueError(f"{field} has invalid numeric content") from exc

    multiplier = Decimal(10_000) if suffix else Decimal(1)
    value = number * multiplier
    if value != value.to_integral_value() or value < 0:
        raise ValueError(f"{field} must normalize to a non-negative integer")
    return ParsedCount(int(value), suffix is not None or plus is not None)


def follower_tier(followers: int) -> tuple[str, Decimal]:
    if followers <= 0:
        raise ValueError("followers must be greater than zero")
    for upper_bound, tier, base in TIER_RULES:
        if upper_bound is None or followers < upper_bound:
            return tier, base
    raise AssertionError("unreachable tier")


def _normalize_platform(raw: Any) -> str:
    if not isinstance(raw, str) or raw.strip().lower() not in PLATFORM_ALIASES:
        raise ValueError("platform must be douyin, xhs, or xiaohongshu")
    return PLATFORM_ALIASES[raw.strip().lower()]


def _post_id(post: dict[str, Any], field: str) -> str:
    value = post.get("post_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}.post_id must be a non-empty string")
    return value.strip()


def _post_metrics(post: dict[str, Any], platform: str, field: str) -> dict[str, Any]:
    likes = parse_count(post.get("likes_raw"), f"{field}.likes_raw")
    if platform == "xiaohongshu":
        collects = parse_count(post.get("collects_raw"), f"{field}.collects_raw")
    elif post.get("collects_raw") is not None:
        collects = parse_count(post.get("collects_raw"), f"{field}.collects_raw")
    else:
        collects = ParsedCount(0, False)
    core_metric = likes.value if platform == "douyin" else likes.value + collects.value
    return {
        "likes": likes.value,
        "collects": collects.value,
        "core_metric": core_metric,
        "rounded_source": likes.rounded_source or collects.rounded_source,
    }


def _grade(r_score: Decimal, m_score: Decimal, m_base: Decimal) -> str:
    thresholds = (
        ("现象级", Decimal("8"), m_base * Decimal("3")),
        ("爆款", Decimal("4"), m_base * Decimal("1.5")),
        ("小爆", Decimal("2"), m_base),
    )
    for grade, minimum_r, minimum_m in thresholds:
        if r_score >= minimum_r and m_score >= minimum_m:
            return grade
    return "普通"


def _rounded_decimal(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.0001")))


def benchmark_account_pool(context: Any, author_followers: int) -> dict[str, Any]:
    if context is None:
        return {
            "status": "not_evaluated",
            "own_followers": None,
            "own_followers_raw": None,
            "own_followers_observed_at": None,
            "author_followers": author_followers,
            "account_multiplier": BENCHMARK_ACCOUNT_MULTIPLIER,
            "main_pool_max_followers": None,
            "rounded_source": False,
            "reason": "未提供本账号实时粉丝数，未判断主对标池或跨级灵感池",
        }
    if not isinstance(context, dict):
        raise ValueError("benchmark_context must be an object")

    own_followers = parse_count(context.get("own_followers_raw"), "benchmark_context.own_followers_raw")
    if own_followers.value <= 0:
        raise ValueError("benchmark_context.own_followers_raw must be greater than zero")
    observed_at = context.get("own_followers_observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError("benchmark_context.own_followers_observed_at must be a non-empty string")

    maximum = own_followers.value * BENCHMARK_ACCOUNT_MULTIPLIER
    status = "main_pool" if author_followers <= maximum else "inspiration_pool"
    reason = (
        "作者粉丝数未超过本账号实时粉丝数的 20 倍"
        if status == "main_pool"
        else "作者粉丝数超过本账号实时粉丝数的 20 倍，仅进入跨级灵感池"
    )
    return {
        "status": status,
        "own_followers": own_followers.value,
        "own_followers_raw": context.get("own_followers_raw"),
        "own_followers_observed_at": observed_at.strip(),
        "author_followers": author_followers,
        "account_multiplier": BENCHMARK_ACCOUNT_MULTIPLIER,
        "main_pool_max_followers": maximum,
        "rounded_source": own_followers.rounded_source,
        "reason": reason,
    }


def view_breakout_filter(target: dict[str, Any], author_followers: int) -> dict[str, Any]:
    raw = target.get("views_raw")
    if raw is None:
        return {
            "status": "unavailable",
            "views": None,
            "views_raw": None,
            "view_to_follower_ratio": None,
            "required_view_to_follower_ratio": float(VIEW_BREAKOUT_MULTIPLIER),
            "minimum_views": MINIMUM_BREAKOUT_VIEWS,
            "meets_ratio": None,
            "meets_minimum_views": None,
            "rounded_source": False,
            "reason": "未提供可信播放量，跳过播放初筛并回退到 R + M 判定",
        }

    views = parse_count(raw, "target.views_raw")
    ratio = Decimal(views.value) / Decimal(author_followers)
    meets_ratio = ratio >= VIEW_BREAKOUT_MULTIPLIER
    meets_minimum = views.value >= MINIMUM_BREAKOUT_VIEWS
    passed = meets_ratio and meets_minimum
    if passed:
        reason = "播放量同时达到 1 万绝对门槛和作者粉丝数的 20 倍"
    elif not meets_ratio and not meets_minimum:
        reason = "播放量未达到 1 万绝对门槛，也未达到作者粉丝数的 20 倍"
    elif not meets_ratio:
        reason = "播放量达到 1 万，但未达到作者粉丝数的 20 倍"
    else:
        reason = "播放量达到作者粉丝数的 20 倍，但未达到 1 万绝对门槛"
    return {
        "status": "passed" if passed else "failed",
        "views": views.value,
        "views_raw": raw,
        "view_to_follower_ratio": _rounded_decimal(ratio),
        "required_view_to_follower_ratio": float(VIEW_BREAKOUT_MULTIPLIER),
        "minimum_views": MINIMUM_BREAKOUT_VIEWS,
        "meets_ratio": meets_ratio,
        "meets_minimum_views": meets_minimum,
        "rounded_source": views.rounded_source,
        "reason": reason,
    }


def _benchmark_candidate_status(
    eligible: bool, account_pool: dict[str, Any], view_breakout: dict[str, Any]
) -> str:
    if not eligible:
        return "not_eligible_by_R_M"
    if view_breakout["status"] == "failed":
        return "rejected_by_view_filter"
    if account_pool["status"] == "main_pool":
        return "main_pool_candidate"
    if account_pool["status"] == "inspiration_pool":
        return "inspiration_pool_candidate"
    return "unclassified_candidate"


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")

    platform = _normalize_platform(payload.get("platform"))
    followers_count = parse_count(payload.get("followers_raw"), "followers_raw")
    tier, m_base = follower_tier(followers_count.value)

    target = payload.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    target_id = _post_id(target, "target")
    target_metrics = _post_metrics(target, platform, "target")
    account_pool = benchmark_account_pool(payload.get("benchmark_context"), followers_count.value)
    view_breakout = view_breakout_filter(target, followers_count.value)

    recent_posts = payload.get("recent_posts")
    if not isinstance(recent_posts, list):
        raise ValueError("recent_posts must be a list")

    prepared: list[tuple[int, dict[str, Any], str]] = []
    pinned_ids: set[str] = set()
    for index, post in enumerate(recent_posts):
        if not isinstance(post, dict):
            raise ValueError(f"recent_posts[{index}] must be an object")
        post_id = _post_id(post, f"recent_posts[{index}]")
        prepared.append((index, post, post_id))
        if post.get("pinned") is True:
            pinned_ids.add(post_id)

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, post, post_id in prepared:
        if post_id in pinned_ids:
            reason = "pinned" if post.get("pinned") is True else "pinned_duplicate"
            excluded.append({"post_id": post_id, "reason": reason})
            continue
        if post_id == target_id:
            excluded.append({"post_id": post_id, "reason": "target_post"})
            continue
        if post_id in seen:
            excluded.append({"post_id": post_id, "reason": "duplicate"})
            continue
        seen.add(post_id)
        if len(included) >= 20:
            excluded.append({"post_id": post_id, "reason": "beyond_latest_20"})
            continue
        metrics = _post_metrics(post, platform, f"recent_posts[{index}]")
        included.append({"post_id": post_id, **metrics})

    sample_count = len(included)
    confidence = "normal" if sample_count >= 10 else "low" if sample_count >= 5 else "insufficient"
    core_values = [post["core_metric"] for post in included]
    median_value = statistics.median(core_values) if core_values else None
    if median_value == 0:
        raise ValueError("baseline median must be greater than zero")

    m_score = Decimal(target_metrics["likes"]) / Decimal(followers_count.value)
    if confidence == "insufficient":
        r_score = None
        grade = None
        reason = "有效基线少于 5 条，不能输出正式等级"
    else:
        r_score = Decimal(target_metrics["core_metric"]) / Decimal(str(median_value))
        grade = _grade(r_score, m_score, m_base)
        if grade == "普通" and r_score >= Decimal("2") and m_score < m_base:
            reason = "账号内表现异常，但赞粉比未破圈"
        elif grade == "普通":
            reason = "R 和 M 未同时达到小爆门槛"
        else:
            reason = f"R 和 M 共同达到{grade}门槛"

    eligible = grade in {"爆款", "现象级"}
    requires_confirmation = eligible and confidence == "low"
    deep_process = eligible and confidence == "normal"
    rounded_source = (
        followers_count.rounded_source
        or target_metrics["rounded_source"]
        or account_pool["rounded_source"]
        or view_breakout["rounded_source"]
        or any(post["rounded_source"] for post in included)
    )
    candidate_status = _benchmark_candidate_status(eligible, account_pool, view_breakout)

    return {
        "schema_version": SCHEMA_VERSION,
        "platform": platform,
        "followers": followers_count.value,
        "followers_raw": payload.get("followers_raw"),
        "tier": tier,
        "m_base": float(m_base),
        "source_precision": "contains_rounded_values" if rounded_source else "exact_display_values",
        "target": {
            "post_id": target_id,
            "likes": target_metrics["likes"],
            "collects": target_metrics["collects"],
            "core_metric": target_metrics["core_metric"],
            "likes_raw": target.get("likes_raw"),
            "collects_raw": target.get("collects_raw"),
            "views": view_breakout["views"],
            "views_raw": view_breakout["views_raw"],
            "rounded_source": target_metrics["rounded_source"],
        },
        "baseline": {
            "sample_count": sample_count,
            "confidence": confidence,
            "median": float(median_value) if median_value is not None else None,
            "included": included,
            "excluded": excluded,
        },
        "scores": {
            "R": _rounded_decimal(r_score) if r_score is not None else None,
            "M": _rounded_decimal(m_score),
        },
        "grade": grade,
        "reason": reason,
        "benchmark": {
            "account_pool": account_pool,
            "view_breakout": view_breakout,
            "candidate_status": candidate_status,
        },
        "eligible_for_deep_process": eligible,
        "requires_confirmation": requires_confirmation,
        "deep_process": deep_process,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Path to input JSON")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = calculate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
