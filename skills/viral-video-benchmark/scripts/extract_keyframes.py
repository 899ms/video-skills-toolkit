#!/usr/bin/env python3
"""Extract stable 0s/2s/5s keyframes from a completed transcript run."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUESTED_TIMESTAMPS = (0, 2, 5)


def _load_summary(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("run-summary must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid run-summary: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("run-summary must contain a JSON object")
    return value


def _regular_file(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an existing regular file")
    return path.resolve()


def _run_directory(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("runDir must be a non-empty path")
    path = Path(value).expanduser()
    if path.is_symlink() or not path.is_dir():
        raise ValueError("runDir must be an existing directory")
    return path.resolve()


def _duration_seconds(media: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required")
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        duration = float(completed.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("ffprobe returned an invalid duration") from exc
    if duration <= 0:
        raise RuntimeError("media duration must be greater than zero")
    return duration


def _extract_nearest_frame(media: Path, destination: Path, start_at: float) -> float:
    actual = start_at
    while True:
        completed = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{actual:.3f}",
                "-i",
                str(media),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
            return actual
        destination.unlink(missing_ok=True)
        if actual == 0:
            raise RuntimeError(f"ffmpeg could not extract {destination.name}")
        actual = max(0.0, actual - 0.1)


def extract_frames(summary_path: Path) -> dict[str, Any]:
    summary = _load_summary(summary_path)
    run_dir = _run_directory(summary.get("runDir"))
    if summary_path.resolve().parent != run_dir:
        raise ValueError("run-summary must be located directly inside runDir")
    media = _regular_file(summary.get("mediaInput"), "mediaInput")
    transcript = _regular_file(summary.get("finalTranscriptTarget"), "final transcript")
    if run_dir not in transcript.parents:
        raise ValueError("final transcript must remain inside runDir")
    if transcript.stat().st_size == 0:
        raise ValueError("final transcript must not be empty")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required")

    duration = _duration_seconds(media)
    last_decodable = max(0.0, duration - min(0.05, duration / 2))
    output_dir = run_dir / "keyframes"
    if output_dir.is_symlink():
        raise ValueError("keyframes directory must not be a symbolic link")
    output_dir.mkdir(mode=0o700, exist_ok=True)
    if not output_dir.is_dir() or output_dir.resolve().parent != run_dir:
        raise ValueError("keyframes directory must remain inside runDir")

    frames = []
    for requested in REQUESTED_TIMESTAMPS:
        start_at = min(float(requested), last_decodable)
        destination = output_dir / f"frame-{requested * 1000:04d}ms.jpg"
        if destination.is_symlink():
            raise ValueError(f"{destination.name} must not be a symbolic link")
        actual = _extract_nearest_frame(media, destination, start_at)
        frames.append(
            {
                "requested_seconds": requested,
                "actual_seconds": round(actual, 3),
                "clamped": actual != float(requested),
                "path": str(destination.resolve()),
            }
        )

    return {
        "schema_version": 1,
        "duration_seconds": round(duration, 3),
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-summary", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = extract_frames(args.run_summary.expanduser())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
