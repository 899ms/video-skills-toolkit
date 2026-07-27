#!/usr/bin/env python3
"""Scan an author's recent posts with the deterministic virality calculator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


CALCULATOR_PATH = Path(__file__).with_name("calculate_virality.py")
GRADE_ORDER = ("普通", "小爆", "爆款", "现象级", "未判级")


def _load_calculator():
    spec = importlib.util.spec_from_file_location("viral_video_calculator", CALCULATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load calculate_virality.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calculator = _load_calculator()


def _canonical_url(platform: str, post_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", post_id) is None:
        raise ValueError("post_id contains characters that cannot form a canonical URL")
    if platform == "douyin":
        return f"https://www.douyin.com/video/{post_id}"
    return f"https://www.xiaohongshu.com/explore/{post_id}"


def _select_window(payload: dict[str, Any], platform: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    recent_posts = payload.get("recent_posts")
    if not isinstance(recent_posts, list):
        raise ValueError("recent_posts must be a list")

    prepared: list[tuple[int, dict[str, Any], str]] = []
    pinned_ids: set[str] = set()
    for index, post in enumerate(recent_posts):
        if not isinstance(post, dict):
            raise ValueError(f"recent_posts[{index}] must be an object")
        post_id = calculator._post_id(post, f"recent_posts[{index}]")
        prepared.append((index, post, post_id))
        if post.get("pinned") is True:
            pinned_ids.add(post_id)

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, post, post_id in prepared:
        if post_id in pinned_ids:
            reason = "pinned" if post.get("pinned") is True else "pinned_duplicate"
            excluded.append({"post_id": post_id, "reason": reason})
            continue
        if post_id in seen:
            excluded.append({"post_id": post_id, "reason": "duplicate"})
            continue
        seen.add(post_id)
        if len(selected) >= 20:
            excluded.append({"post_id": post_id, "reason": "beyond_latest_20"})
            continue
        metrics = calculator._post_metrics(post, platform, f"recent_posts[{index}]")
        selected.append(
            {
                "post_id": post_id,
                "title": post.get("title") if isinstance(post.get("title"), str) else "",
                "url": _canonical_url(platform, post_id),
                "likes_raw": post.get("likes_raw"),
                "collects_raw": post.get("collects_raw"),
                "views_raw": post.get("views_raw"),
                "likes": metrics["likes"],
                "collects": metrics["collects"],
            }
        )
    return selected, excluded


def scan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    platform = calculator._normalize_platform(payload.get("platform"))
    followers = calculator.parse_count(payload.get("followers_raw"), "followers_raw")
    account_pool = calculator.benchmark_account_pool(payload.get("benchmark_context"), followers.value)
    selected, excluded = _select_window(payload, platform)

    results = []
    for candidate in selected:
        target = {
            "post_id": candidate["post_id"],
            "likes_raw": candidate["likes_raw"],
            "views_raw": candidate["views_raw"],
        }
        if platform == "xiaohongshu":
            target["collects_raw"] = candidate["collects_raw"]

        baseline_posts = []
        for other in selected:
            if other["post_id"] == candidate["post_id"]:
                continue
            baseline = {"post_id": other["post_id"], "likes_raw": other["likes_raw"]}
            if platform == "xiaohongshu":
                baseline["collects_raw"] = other["collects_raw"]
            baseline_posts.append(baseline)

        classification = calculator.calculate(
            {
                "schema_version": 1,
                "platform": platform,
                "followers_raw": payload.get("followers_raw"),
                "benchmark_context": payload.get("benchmark_context"),
                "target": target,
                "recent_posts": baseline_posts,
            }
        )
        results.append(
            {
                "post_id": candidate["post_id"],
                "title": candidate["title"],
                "url": candidate["url"],
                "likes_raw": candidate["likes_raw"],
                "likes": classification["target"]["likes"],
                "collects_raw": candidate["collects_raw"],
                "collects": classification["target"]["collects"],
                "views_raw": candidate["views_raw"],
                "views": classification["target"]["views"],
                "baseline_median": classification["baseline"]["median"],
                "baseline_sample_count": classification["baseline"]["sample_count"],
                "baseline_confidence": classification["baseline"]["confidence"],
                "baseline_post_ids": [post["post_id"] for post in classification["baseline"]["included"]],
                "R": classification["scores"]["R"],
                "M": classification["scores"]["M"],
                "grade": classification["grade"],
                "reason": classification["reason"],
                "view_breakout": classification["benchmark"]["view_breakout"],
                "benchmark_candidate_status": classification["benchmark"]["candidate_status"],
                "eligible_for_deep_process": classification["eligible_for_deep_process"],
                "requires_confirmation": classification["requires_confirmation"],
                "deep_process": classification["deep_process"],
                "source_precision": classification["source_precision"],
            }
        )

    counts = {grade: 0 for grade in GRADE_ORDER}
    for result in results:
        counts[result["grade"] if result["grade"] is not None else "未判级"] += 1

    return {
        "schema_version": 1,
        "platform": platform,
        "followers_raw": payload.get("followers_raw"),
        "account_pool": account_pool,
        "scan_sample_count": len(selected),
        "comparison_method": "each_candidate_against_other_posts_in_fixed_window",
        "requires_user_selection_for_deep_process": True,
        "grade_counts": counts,
        "qualifying": [result for result in results if result["eligible_for_deep_process"]],
        "benchmark_candidates": [
            result for result in results if result["benchmark_candidate_status"] == "main_pool_candidate"
        ],
        "inspiration_candidates": [
            result for result in results if result["benchmark_candidate_status"] == "inspiration_pool_candidate"
        ],
        "view_filter_rejected": [
            result for result in results if result["benchmark_candidate_status"] == "rejected_by_view_filter"
        ],
        "small_hits": [result for result in results if result["grade"] == "小爆"],
        "results": results,
        "excluded": excluded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = scan(payload)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
