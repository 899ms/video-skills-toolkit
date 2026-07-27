#!/usr/bin/env python3
"""Validate an immutable evidence package before deep analysis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROUTES = {
    ("douyin", "video"): "douyin_video",
    ("xiaohongshu", "graphic"): "xiaohongshu_graphic",
    ("xiaohongshu", "video"): "xiaohongshu_video",
}
LOCATOR_TYPES = {
    "douyin": {"title", "body", "timestamp", "transcript", "frame", "comment", "metric"},
    "xiaohongshu": {"title", "cover", "page", "time", "body", "search", "comment", "metric"},
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
POST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "evidence_version",
    "source_is_untrusted",
    "analysis_mode",
    "identity",
    "content_format",
    "collected_at",
    "evidence",
    "confidence",
    "limitations",
}
REQUIRED_EVIDENCE_FIELDS = {
    "title",
    "body",
    "pages",
    "transcript",
    "timed_frames",
    "comments",
    "metrics",
    "search_context",
}


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _validate_string_list(value: Any, path: str) -> list[str]:
    items = _require_list(value, path)
    for index, item in enumerate(items):
        _require_string(item, f"{path}[{index}]")
    return items


def _validate_locator(value: Any, path: str, platform: str, expected_type: str | None = None) -> None:
    locator = _require_object(value, path)
    locator_type = _require_string(locator.get("type"), f"{path}.type")
    _require_string(locator.get("value"), f"{path}.value")
    if locator_type not in LOCATOR_TYPES[platform]:
        raise ValueError(f"{path}.type is not supported for {platform}: {locator_type}")
    if expected_type is not None and locator_type != expected_type:
        raise ValueError(f"{path}.type must be {expected_type}")


def _validate_confidence(value: Any, path: str) -> str:
    if value not in CONFIDENCE_LEVELS:
        raise ValueError(f"{path} must be one of: high, medium, low")
    return value


def _validate_text_evidence(
    value: Any,
    path: str,
    platform: str,
    warnings: set[str],
    expected_locator: str | None = None,
) -> None:
    item = _require_object(value, path)
    _require_string(item.get("text"), f"{path}.text")
    _validate_locator(item.get("locator"), f"{path}.locator", platform, expected_locator)
    confidence = _validate_confidence(item.get("confidence"), f"{path}.confidence")
    limitations = _validate_string_list(item.get("limitations"), f"{path}.limitations")
    if confidence == "low":
        if not limitations:
            raise ValueError(f"{path}.limitations must explain low-confidence evidence")
        warnings.add("low_confidence_evidence")


def _validate_identity(payload: dict[str, Any]) -> tuple[str, str]:
    identity = _require_object(payload.get("identity"), "identity")
    platform = identity.get("platform")
    if platform not in {"douyin", "xiaohongshu"}:
        raise ValueError("identity.platform must be douyin or xiaohongshu")
    post_id = _require_string(identity.get("post_id"), "identity.post_id")
    if not POST_ID_PATTERN.fullmatch(post_id):
        raise ValueError("identity.post_id contains unsafe characters")
    if identity.get("trust") != "verified":
        raise ValueError("identity.trust must be verified before formal analysis")

    canonical_url = _require_string(identity.get("canonical_url"), "identity.canonical_url")
    parsed = urlparse(canonical_url)
    expected_domain = "douyin.com" if platform == "douyin" else "xiaohongshu.com"
    host = (parsed.hostname or "").lower()
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if (
        parsed.scheme != "https"
        or not (host == expected_domain or host.endswith(f".{expected_domain}"))
        or post_id not in path_segments
    ):
        raise ValueError("identity.canonical_url must match the verified platform and post_id")
    return platform, post_id


def _validate_timestamp(value: Any, path: str) -> None:
    text = _require_string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{path} must include a timezone")


def _validate_title_body(
    evidence: dict[str, Any], platform: str, route: str, warnings: set[str]
) -> None:
    _validate_text_evidence(evidence.get("title"), "evidence.title", platform, warnings, "title")
    body = evidence.get("body")
    if route.startswith("xiaohongshu_"):
        _validate_text_evidence(body, "evidence.body", platform, warnings, "body")
    elif body is not None:
        _validate_text_evidence(body, "evidence.body", platform, warnings, "body")


def _validate_transcript(
    transcript_value: Any, platform: str, required: bool, warnings: set[str]
) -> None:
    transcript = _require_object(transcript_value, "evidence.transcript")
    status = transcript.get("status")
    is_complete = transcript.get("is_complete")
    segments = _require_list(transcript.get("segments"), "evidence.transcript.segments")
    if required and status != "available":
        raise ValueError("evidence.transcript.status must be available for video")
    if required and is_complete is not True:
        raise ValueError("evidence.transcript.is_complete must be true for video")
    if not required:
        if status != "not_applicable" or is_complete is not False or segments:
            raise ValueError(
                "graphic evidence transcript must be not_applicable, incomplete, and have no segments"
            )
        return
    if not segments:
        raise ValueError("evidence.transcript.segments must not be empty for video")

    expected_locator = "transcript" if platform == "douyin" else "time"
    covers_first_five_seconds = False
    previous_start = -1.0
    for index, segment_value in enumerate(segments):
        path = f"evidence.transcript.segments[{index}]"
        segment = _require_object(segment_value, path)
        _validate_text_evidence(segment, path, platform, warnings, expected_locator)
        start = segment.get("start_seconds")
        end = segment.get("end_seconds")
        if isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0:
            raise ValueError(f"{path}.start_seconds must be a non-negative number")
        if isinstance(end, bool) or not isinstance(end, (int, float)) or end <= start:
            raise ValueError(f"{path}.end_seconds must be greater than start_seconds")
        if start < previous_start:
            raise ValueError("evidence.transcript.segments must be ordered by start_seconds")
        previous_start = float(start)
        if start < 5:
            covers_first_five_seconds = True
    if not covers_first_five_seconds:
        raise ValueError("video transcript must include evidence from the first five seconds")


def _validate_timed_frames(
    frames_value: Any, platform: str, required: bool, warnings: set[str]
) -> None:
    frames = _require_list(frames_value, "evidence.timed_frames")
    if not required:
        if frames:
            raise ValueError("graphic evidence must not include timed_frames")
        return
    requested: set[int | float] = set()
    expected_locator = "frame" if platform == "douyin" else "time"
    for index, frame_value in enumerate(frames):
        path = f"evidence.timed_frames[{index}]"
        frame = _require_object(frame_value, path)
        requested_seconds = frame.get("requested_seconds")
        actual_seconds = frame.get("actual_seconds")
        if isinstance(requested_seconds, bool) or not isinstance(requested_seconds, (int, float)):
            raise ValueError(f"{path}.requested_seconds must be a number")
        if isinstance(actual_seconds, bool) or not isinstance(actual_seconds, (int, float)) or actual_seconds < 0:
            raise ValueError(f"{path}.actual_seconds must be a non-negative number")
        if not isinstance(frame.get("clamped"), bool):
            raise ValueError(f"{path}.clamped must be a boolean")
        asset_path = Path(_require_string(frame.get("asset_path"), f"{path}.asset_path"))
        if not asset_path.is_absolute():
            raise ValueError(f"{path}.asset_path must be absolute")
        _validate_locator(frame.get("locator"), f"{path}.locator", platform, expected_locator)
        observations = _require_list(frame.get("observations"), f"{path}.observations")
        if not observations:
            raise ValueError(f"{path}.observations must not be empty")
        for observation_index, observation in enumerate(observations):
            _validate_text_evidence(
                observation,
                f"{path}.observations[{observation_index}]",
                platform,
                warnings,
                expected_locator,
            )
        requested.add(requested_seconds)
    if not {0, 2, 5}.issubset(requested):
        raise ValueError("video evidence must include requested frames at 0, 2, and 5 seconds")


def _validate_pages(evidence: dict[str, Any], platform: str, required: bool, warnings: set[str]) -> None:
    pages = _require_list(evidence.get("pages"), "evidence.pages")
    if not required:
        if pages:
            raise ValueError("video evidence must not include graphic pages")
        if "declared_page_count" in evidence:
            raise ValueError("video evidence must not declare a graphic page count")
        return

    declared_count = evidence.get("declared_page_count")
    if isinstance(declared_count, bool) or not isinstance(declared_count, int) or declared_count < 1:
        raise ValueError("evidence.declared_page_count must be a positive integer")
    if len(pages) < 2:
        raise ValueError("xiaohongshu graphic requires at least two ordered pages, not cover-only evidence")
    if declared_count != len(pages):
        raise ValueError("evidence.declared_page_count must match collected pages")

    page_numbers: list[int] = []
    for index, page_value in enumerate(pages):
        path = f"evidence.pages[{index}]"
        page = _require_object(page_value, path)
        page_number = page.get("page_number")
        if isinstance(page_number, bool) or not isinstance(page_number, int):
            raise ValueError(f"{path}.page_number must be an integer")
        page_numbers.append(page_number)
        expected_locator = "cover" if index == 0 else "page"
        expected_role = "cover" if index == 0 else "content"
        if page.get("role") != expected_role:
            raise ValueError(f"{path}.role must be {expected_role}")
        asset_path = Path(_require_string(page.get("asset_path"), f"{path}.asset_path"))
        if not asset_path.is_absolute():
            raise ValueError(f"{path}.asset_path must be absolute")
        _validate_locator(page.get("locator"), f"{path}.locator", platform, expected_locator)
        ocr = _require_list(page.get("ocr"), f"{path}.ocr")
        observations = _require_list(page.get("visual_observations"), f"{path}.visual_observations")
        if not ocr and not observations:
            raise ValueError(f"{path} must include OCR or a visual observation")
        for evidence_name, items in (("ocr", ocr), ("visual_observations", observations)):
            for item_index, item in enumerate(items):
                _validate_text_evidence(
                    item,
                    f"{path}.{evidence_name}[{item_index}]",
                    platform,
                    warnings,
                    expected_locator,
                )
    if page_numbers != list(range(1, declared_count + 1)):
        raise ValueError("evidence.pages must be ordered and contiguous from page 1")


def _validate_comments(
    comments_value: Any, platform: str, warnings: set[str]
) -> bool:
    comments = _require_object(comments_value, "evidence.comments")
    status = comments.get("status")
    items = _require_list(comments.get("items"), "evidence.comments.items")
    limitation = comments.get("limitation")
    if status == "available":
        if not items:
            raise ValueError("available comments must include at least one anchored item")
        _require_string(limitation, "evidence.comments.limitation")
        for index, item in enumerate(items):
            _validate_text_evidence(
                item, f"evidence.comments.items[{index}]", platform, warnings, "comment"
            )
        return True
    if status == "unavailable":
        if items:
            raise ValueError("unavailable comments must not contain invented items")
        _require_string(limitation, "evidence.comments.limitation")
        warnings.add("comments_unavailable")
        return False
    raise ValueError("evidence.comments.status must be available or unavailable")


def _validate_metrics(metrics_value: Any, platform: str, warnings: set[str]) -> None:
    metrics = _require_list(metrics_value, "evidence.metrics")
    if not metrics:
        raise ValueError("evidence.metrics must not be empty")
    for index, metric_value in enumerate(metrics):
        path = f"evidence.metrics[{index}]"
        metric = _require_object(metric_value, path)
        _require_string(metric.get("name"), f"{path}.name")
        value_raw = metric.get("value_raw")
        if isinstance(value_raw, bool) or not isinstance(value_raw, (str, int, float)):
            raise ValueError(f"{path}.value_raw must preserve a visible raw value")
        if isinstance(value_raw, str) and not value_raw.strip():
            raise ValueError(f"{path}.value_raw must not be empty")
        _validate_locator(metric.get("locator"), f"{path}.locator", platform, "metric")
        confidence = _validate_confidence(metric.get("confidence"), f"{path}.confidence")
        limitations = _validate_string_list(metric.get("limitations"), f"{path}.limitations")
        if confidence == "low":
            if not limitations:
                raise ValueError(f"{path}.limitations must explain low-confidence evidence")
            warnings.add("low_confidence_evidence")


def _validate_search_context(value: Any, platform: str, warnings: set[str]) -> None:
    items = _require_list(value, "evidence.search_context")
    if platform == "douyin" and items:
        raise ValueError("douyin evidence does not use xiaohongshu search locators")
    for index, item in enumerate(items):
        _validate_text_evidence(
            item, f"evidence.search_context[{index}]", platform, warnings, "search"
        )


def _validate_package_confidence(
    value: Any, route: str, warnings: set[str], analysis_mode: str, limitations: list[str]
) -> None:
    confidence = _require_object(value, "confidence")
    overall = _validate_confidence(confidence.get("overall"), "confidence.overall")
    identity = _validate_confidence(confidence.get("identity"), "confidence.identity")
    ocr = confidence.get("ocr")
    if identity != "high":
        raise ValueError("confidence.identity must be high for formal analysis")
    if route == "xiaohongshu_graphic":
        _validate_confidence(ocr, "confidence.ocr")
    elif ocr != "not_applicable":
        raise ValueError("confidence.ocr must be not_applicable for video routes")
    if overall == "low":
        warnings.add("low_confidence_evidence")
    if warnings & {"low_confidence_evidence", "comments_unavailable"}:
        if analysis_mode != "limited":
            raise ValueError("missing or low-confidence evidence requires analysis_mode=limited")
        if not limitations:
            raise ValueError("limited analysis requires top-level limitations")
    elif analysis_mode == "limited" and not limitations:
        raise ValueError("limited analysis requires top-level limitations")


def validate(payload: Any) -> dict[str, Any]:
    """Validate without normalizing, mutating, or echoing untrusted evidence."""
    package = _require_object(payload, "evidence package")
    missing = sorted(REQUIRED_TOP_LEVEL - set(package))
    if missing:
        raise ValueError(f"evidence package missing fields: {', '.join(missing)}")
    if package.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    evidence_version = _require_string(package.get("evidence_version"), "evidence_version")
    if package.get("source_is_untrusted") is not True:
        raise ValueError("source_is_untrusted must be true")
    analysis_mode = package.get("analysis_mode")
    if analysis_mode not in {"complete", "limited"}:
        raise ValueError("analysis_mode must be complete or limited")
    _validate_timestamp(package.get("collected_at"), "collected_at")
    limitations = _validate_string_list(package.get("limitations"), "limitations")

    platform, post_id = _validate_identity(package)
    content_format = package.get("content_format")
    route = ROUTES.get((platform, content_format))
    if route is None:
        raise ValueError(
            f"unsupported platform/content_format combination: {platform}/{content_format}"
        )

    evidence = _require_object(package.get("evidence"), "evidence")
    missing_evidence = sorted(REQUIRED_EVIDENCE_FIELDS - set(evidence))
    if missing_evidence:
        raise ValueError(f"evidence missing fields: {', '.join(missing_evidence)}")
    warnings: set[str] = set()
    _validate_title_body(evidence, platform, route, warnings)
    is_video = content_format == "video"
    is_graphic = content_format == "graphic"
    _validate_pages(evidence, platform, is_graphic, warnings)
    _validate_transcript(evidence.get("transcript"), platform, is_video, warnings)
    _validate_timed_frames(evidence.get("timed_frames"), platform, is_video, warnings)
    _validate_comments(evidence.get("comments"), platform, warnings)
    _validate_metrics(evidence.get("metrics"), platform, warnings)
    _validate_search_context(evidence.get("search_context"), platform, warnings)
    _validate_package_confidence(
        package.get("confidence"), route, warnings, analysis_mode, limitations
    )

    return {
        "analysis_identity": f"{platform}:{post_id}",
        "analysis_mode": analysis_mode,
        "evidence_version": evidence_version,
        "route": route,
        "valid": True,
        "warnings": sorted(warnings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
