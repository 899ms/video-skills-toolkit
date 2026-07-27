#!/usr/bin/env python3
"""Validate an evidence-anchored eight-section benchmark analysis JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SECTIONS = (
    "基本信息",
    "开头拆解",
    "中段拆解",
    "结尾拆解",
    "爆款因子",
    "可复用点",
    "不能照搬",
    "本账号适配",
)
LEGACY_FIELDS = {
    "topic",
    "opening",
    "structure",
    "cases",
    "turns",
    "emotion",
    "ending",
    "virality_hypothesis",
    "reusable_structure",
    "non_copyable",
}
ROUTES = {
    ("douyin", "video"),
    ("xiaohongshu", "graphic"),
    ("xiaohongshu", "video"),
}
LOCATOR_TYPES = {
    ("douyin", "video"): {"title", "body", "timestamp", "transcript", "frame", "comment", "metric"},
    ("xiaohongshu", "graphic"): {"title", "cover", "page", "body", "search", "comment", "metric"},
    ("xiaohongshu", "video"): {"title", "cover", "page", "time", "body", "search", "comment", "metric"},
}
OPENING_ROUTE_FIELDS = {
    ("douyin", "video"): ("first_frame", "first_0_2_seconds", "first_2_5_seconds", "oral_rhythm"),
    ("xiaohongshu", "graphic"): ("title_promise", "cover_promise", "search_intent"),
    ("xiaohongshu", "video"): (
        "title_promise",
        "cover_promise",
        "search_intent",
        "first_5_seconds",
        "timing",
    ),
}
MIDDLE_ROUTE_FIELDS = {
    ("douyin", "video"): ("evidence_timing", "screen_text", "conversion"),
    ("xiaohongshu", "graphic"): (
        "ordered_pages_or_body_progression",
        "save_reason",
        "comment_demand",
        "trust_or_persona",
        "product_bridge",
    ),
    ("xiaohongshu", "video"): (
        "ordered_pages_or_body_progression",
        "save_reason",
        "comment_demand",
        "trust_or_persona",
        "product_bridge",
    ),
}
ACCOUNT_FIT_FIELDS = (
    "applicable_themes",
    "required_first_party_facts",
    "transfer_conditions",
    "risks",
)
DRAFTING_KEY_RE = re.compile(r"(?:script|caption|title|copy|draft|二创|脚本|逐字稿|文案|标题|成稿)", re.IGNORECASE)
DRAFTING_TEXT_RE = re.compile(
    r"(?:可直接发布|直接发布|平台可用成稿|完整脚本\s*[:：]|发布文案\s*[:：]|标题备选\s*[:：]|ready[ -]?copy)",
    re.IGNORECASE,
)


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _require_object_fields(value: Any, path: str, fields: tuple[str, ...], *, exact: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    missing = [field for field in fields if field not in value]
    if missing:
        raise ValueError(f"{path} missing fields: {', '.join(missing)}")
    if exact:
        extra = [field for field in value if field not in fields]
        if extra:
            raise ValueError(f"{path} has unexpected fields: {', '.join(extra)}")
    return value


def _validate_anchor(value: Any, path: str, route: tuple[str, str]) -> None:
    anchor = _require_object_fields(value, path, ("type", "value"))
    locator_type = _nonempty_string(anchor["type"], f"{path}.type")
    _nonempty_string(anchor["value"], f"{path}.value")
    if locator_type not in LOCATOR_TYPES[route]:
        allowed = ", ".join(sorted(LOCATOR_TYPES[route]))
        raise ValueError(f"{path} locator type {locator_type!r} is invalid for {route[0]}+{route[1]}; allowed: {allowed}")


def _validate_anchors(value: Any, path: str, route: tuple[str, str]) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a non-empty evidence anchor list")
    for index, item in enumerate(value):
        _validate_anchor(item, f"{path}[{index}]", route)


def _validate_claim(value: Any, path: str, route: tuple[str, str], extra_fields: tuple[str, ...] = ()) -> None:
    allowed = ("claim", "evidence", "status", "inspected_scope") + extra_fields
    item = _require_object_fields(value, path, ("claim", "evidence") + extra_fields, exact=False)
    extra = [field for field in item if field not in allowed]
    if extra:
        raise ValueError(f"{path} has unexpected fields: {', '.join(extra)}")
    text = _nonempty_string(item["claim"], f"{path}.claim")
    _validate_anchors(item["evidence"], f"{path}.evidence", route)
    status = item.get("status", "observed")
    if status not in {"observed", "not_observed", "unavailable"}:
        raise ValueError(f"{path}.status must be observed, not_observed, or unavailable")
    if "未观察到" in text and "status" not in item:
        raise ValueError(f"{path}.status must explicitly mark a not observed claim")
    if status != "observed":
        if "inspected_scope" not in item:
            raise ValueError(f"{path}.inspected_scope is required for {status}")
        _validate_anchors(item["inspected_scope"], f"{path}.inspected_scope", route)
    elif "inspected_scope" in item:
        _validate_anchors(item["inspected_scope"], f"{path}.inspected_scope", route)
    for field in extra_fields:
        if field != "order":
            _nonempty_string(item[field], f"{path}.{field}")


def _validate_claim_list(value: Any, path: str, route: tuple[str, str], extra_fields: tuple[str, ...] = ()) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a non-empty list")
    for index, item in enumerate(value):
        _validate_claim(item, f"{path}[{index}]", route, extra_fields)


def _validate_route_observations(value: Any, path: str, route: tuple[str, str], fields: tuple[str, ...]) -> None:
    observations = _require_object_fields(value, path, fields)
    for field in fields:
        _validate_claim(observations[field], f"{path}.{field}", route)


def _validate_basic_info(value: Any) -> tuple[str, str]:
    fields = (
        "platform",
        "post_id",
        "content_format",
        "evidence_version",
        "analysis_version",
        "title",
        "mother_topic",
        "target_reader",
        "content_promise",
        "evidence",
    )
    info = _require_object_fields(value, "基本信息", fields)
    for field in fields[:-1]:
        _nonempty_string(info[field], f"基本信息.{field}")
    route = (info["platform"], info["content_format"])
    if route not in ROUTES:
        raise ValueError(f"unsupported analysis route: {route[0]}+{route[1]}")
    _validate_anchors(info["evidence"], "基本信息.evidence", route)
    return route


def _validate_opening(value: Any, route: tuple[str, str]) -> None:
    fields = ("observations", "hook_types", "emotion_mechanism", "route_observations")
    opening = _require_object_fields(value, "开头拆解", fields)
    _validate_claim_list(opening["observations"], "开头拆解.observations", route)
    hook_types = opening["hook_types"]
    if not isinstance(hook_types, list) or not hook_types:
        raise ValueError("开头拆解.hook_types must be a non-empty list")
    for index, hook_type in enumerate(hook_types):
        _nonempty_string(hook_type, f"开头拆解.hook_types[{index}]")
    _validate_claim(opening["emotion_mechanism"], "开头拆解.emotion_mechanism", route)
    _validate_route_observations(
        opening["route_observations"],
        "开头拆解.route_observations",
        route,
        OPENING_ROUTE_FIELDS[route],
    )


def _validate_middle(value: Any, route: tuple[str, str]) -> None:
    fields = ("structure", "cases", "turns", "emotion", "route_observations")
    middle = _require_object_fields(value, "中段拆解", fields)
    _validate_claim_list(middle["structure"], "中段拆解.structure", route, ("order", "role"))
    for index, item in enumerate(middle["structure"]):
        if not isinstance(item["order"], int) or isinstance(item["order"], bool) or item["order"] < 1:
            raise ValueError(f"中段拆解.structure[{index}].order must be a positive integer")
    for field in ("cases", "turns", "emotion"):
        _validate_claim_list(middle[field], f"中段拆解.{field}", route)
    _validate_route_observations(
        middle["route_observations"],
        "中段拆解.route_observations",
        route,
        MIDDLE_ROUTE_FIELDS[route],
    )


def _validate_ending(value: Any, route: tuple[str, str]) -> None:
    fields = ("conclusion", "call_to_action", "follow_reason", "open_loop")
    ending = _require_object_fields(value, "结尾拆解", fields)
    for field in fields:
        _validate_claim(ending[field], f"结尾拆解.{field}", route)


def _validate_virality(value: Any, route: tuple[str, str]) -> None:
    fields = ("observed_mechanisms", "hypotheses", "correlations_only", "confidence_limits")
    virality = _require_object_fields(value, "爆款因子", fields)
    for field in fields:
        _validate_claim_list(virality[field], f"爆款因子.{field}", route)


def _validate_reuse(value: Any, route: tuple[str, str]) -> None:
    _validate_claim_list(value, "可复用点", route, ("transfer_method", "requirements"))


def _validate_non_copyable(value: Any, route: tuple[str, str]) -> None:
    _validate_claim_list(value, "不能照搬", route, ("reason",))


def _scan_for_drafting(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if DRAFTING_KEY_RE.search(str(key)):
                raise ValueError(f"{path}.{key} is a forbidden drafting field")
            _scan_for_drafting(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_for_drafting(child, f"{path}[{index}]")
    elif isinstance(value, str) and DRAFTING_TEXT_RE.search(value):
        raise ValueError(f"{path} contains platform-ready drafting content")


def _validate_account_fit(value: Any, route: tuple[str, str]) -> None:
    account_fit = _require_object_fields(value, "本账号适配", ACCOUNT_FIT_FIELDS)
    for field in ACCOUNT_FIT_FIELDS:
        _validate_claim_list(account_fit[field], f"本账号适配.{field}", route)
    _scan_for_drafting(account_fit, "本账号适配")


def _collect_locator_pairs(value: Any, allowed_types: set[str]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    if isinstance(value, dict):
        if set(value) == {"type", "value"} and value.get("type") in allowed_types:
            locator_value = value.get("value")
            if isinstance(locator_value, str) and locator_value.strip():
                pairs.add((value["type"], locator_value))
        for child in value.values():
            pairs.update(_collect_locator_pairs(child, allowed_types))
    elif isinstance(value, list):
        for child in value:
            pairs.update(_collect_locator_pairs(child, allowed_types))
    return pairs


def _validate_evidence_binding(
    payload: dict[str, Any], evidence_package: Any, route: tuple[str, str]
) -> None:
    evidence_package = _require_object_fields(
        evidence_package,
        "evidence_package",
        ("evidence_version", "identity", "content_format", "evidence"),
        exact=False,
    )
    identity = _require_object_fields(
        evidence_package["identity"],
        "evidence_package.identity",
        ("platform", "post_id"),
        exact=False,
    )
    info = payload["基本信息"]
    comparisons = (
        ("platform", identity["platform"], info["platform"]),
        ("post_id", identity["post_id"], info["post_id"]),
        ("content_format", evidence_package["content_format"], info["content_format"]),
        ("evidence_version", evidence_package["evidence_version"], info["evidence_version"]),
    )
    for name, evidence_value, analysis_value in comparisons:
        if evidence_value != analysis_value:
            raise ValueError(
                f"analysis {name} does not match immutable evidence package: "
                f"{analysis_value!r} != {evidence_value!r}"
            )

    allowed_types = LOCATOR_TYPES[route]
    available = _collect_locator_pairs(evidence_package["evidence"], allowed_types)
    evidence = evidence_package["evidence"]
    if isinstance(evidence, dict):
        comments = evidence.get("comments")
        if isinstance(comments, dict) and comments.get("status") in {"available", "unavailable"}:
            available.add(("comment", "evidence.comments.status"))
        if route[0] == "xiaohongshu" and isinstance(evidence.get("search_context"), list):
            available.add(("search", "evidence.search_context"))

    cited = _collect_locator_pairs(payload, allowed_types)
    missing = sorted(cited - available)
    if missing:
        formatted = ", ".join(f"{locator_type}:{value}" for locator_type, value in missing[:5])
        suffix = " ..." if len(missing) > 5 else ""
        raise ValueError(f"analysis cites anchors absent from immutable evidence package: {formatted}{suffix}")


def validate(payload: Any, evidence_package: Any | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("analysis must be a JSON object")
    if set(payload) == LEGACY_FIELDS:
        raise ValueError("legacy ten-field analysis is not accepted; explicitly migrate it to the eight-section contract")
    missing = [field for field in SECTIONS if field not in payload]
    extra = [field for field in payload if field not in SECTIONS]
    if missing:
        raise ValueError(f"analysis missing sections: {', '.join(missing)}")
    if extra:
        raise ValueError(f"analysis has unexpected sections: {', '.join(extra)}")
    if tuple(payload) != SECTIONS:
        raise ValueError(f"analysis sections must follow this exact order: {', '.join(SECTIONS)}")

    route = _validate_basic_info(payload["基本信息"])
    _validate_opening(payload["开头拆解"], route)
    _validate_middle(payload["中段拆解"], route)
    _validate_ending(payload["结尾拆解"], route)
    _validate_virality(payload["爆款因子"], route)
    _validate_reuse(payload["可复用点"], route)
    _validate_non_copyable(payload["不能照搬"], route)
    _validate_account_fit(payload["本账号适配"], route)
    if evidence_package is not None:
        _validate_evidence_binding(payload, evidence_package, route)

    return {
        "evidence_bound": evidence_package is not None,
        "route": f"{route[0]}+{route[1]}",
        "section_count": len(SECTIONS),
        "valid": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="already-validated immutable U1 evidence package; required before formal storage",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        evidence_package = (
            json.loads(args.evidence.read_text(encoding="utf-8")) if args.evidence else None
        )
        result = validate(payload, evidence_package)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
