#!/usr/bin/env python3
"""
Media to transcript pipeline.

Pipeline:
1. Reuse video-transcript download/probe helpers for platform URLs.
2. Convert video or unsupported audio into mp3 when needed.
3. Upload local audio to Cloudflare R2.
4. Call Volcengine AUC bigmodel recording-file ASR 2.0.
5. Convert ASR utterances into transcript-shaped Markdown.
6. Write an AI correction prompt for the final pass.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import hmac
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import ssl
except Exception:
    ssl = None  # type: ignore[assignment]


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = SKILL_DIR / "outputs"
MAX_CORRECTION_CONTEXT_CHARS = 12000
MAX_AUC_CONTEXT_CHARS = 500
DEFAULT_CHUNK_SECONDS = 180

AUC_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
AUC_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
AUC_RESOURCE_ID = "volc.seedasr.auc"
AUC_ACTIVATE_URL = "https://console.volcengine.com/speech/new/setting/activate"
AUC_API_KEYS_URL = "https://console.volcengine.com/speech/new/setting/apikeys"
AUC_SUCCESS = "20000000"
AUC_PROCESSING = {"20000001", "20000002"}

SUPPORTED_AUC_AUDIO_FORMATS = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".ogg": "ogg",
    ".pcm": "raw",
    ".raw": "raw",
}
AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".pcm",
    ".raw",
    ".wav",
}
VIDEO_EXTENSIONS = {
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ts",
    ".webm",
    ".wmv",
}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def path_ext(value: str) -> str:
    if is_url(value):
        try:
            return Path(urllib.parse.urlparse(value).path).suffix.lower()
        except Exception:
            return ""
    return Path(value).suffix.lower()


def slugify(value: str, fallback: str = "media") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return (cleaned or fallback)[:80]


def find_up(start: Path, filename: str) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / filename
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def find_vault_root() -> Path:
    candidates = [Path.cwd(), SKILL_DIR, SKILL_DIR.parent]
    for candidate in candidates:
        found = find_up(candidate, ".env.r2")
        if found:
            return found.parent
    return Path.cwd()


def load_env_file(path: Path, override: bool = False) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def load_project_env(vault_root: Path) -> list[Path]:
    loaded: list[Path] = []
    for env_path, override in [
        (Path.home() / ".skills" / ".env", False),
        (Path.home() / ".baoyu-skills" / ".env", False),
        (vault_root / ".env", False),
        (vault_root / ".skills" / ".env", False),
        (vault_root / ".baoyu-skills" / ".env", False),
        (vault_root / ".env.r2", True),
    ]:
        if env_path.exists():
            load_env_file(env_path, override=override)
            loaded.append(env_path)
    return loaded


def locate_skill(name: str) -> Path:
    candidates = [
        SKILL_DIR.parent / name,
        Path.cwd() / ".claude" / "skills" / name,
        Path.cwd() / ".codex" / "skills" / name,
        Path.home() / ".claude" / "skills" / name,
        Path.home() / ".codex" / "skills" / name,
    ]
    for candidate in candidates:
        if (candidate / "SKILL.md").exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Cannot locate required skill: {name}")


def load_legacy_video_module(video_skill_dir: Path) -> Any:
    script = video_skill_dir / "scripts" / "transcript.py"
    if not script.exists():
        raise FileNotFoundError(f"Missing video-transcript script: {script}")
    spec = importlib.util.spec_from_file_location("legacy_video_transcript", script)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot import {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def detect_platform(url: str, legacy: Any | None = None) -> str:
    if legacy and hasattr(legacy, "detect_platform"):
        return str(legacy.detect_platform(url))
    lower = url.lower()
    if "bilibili.com" in lower or "b23.tv" in lower:
        return "bilibili"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "xiaohongshu.com" in lower or "xhslink.com" in lower:
        return "xiaohongshu"
    if "douyin.com" in lower or "v.douyin.com" in lower:
        return "douyin"
    return "unknown"


def should_download(input_value: str, download_mode: str, legacy: Any | None = None) -> bool:
    if not is_url(input_value):
        return False
    if download_mode == "always":
        return True
    if download_mode == "never":
        return False
    platform = detect_platform(input_value, legacy)
    if platform in {"bilibili", "youtube", "xiaohongshu", "douyin"}:
        return True
    ext = path_ext(input_value)
    if ext in SUPPORTED_AUC_AUDIO_FORMATS:
        return False
    if ext in MEDIA_EXTENSIONS:
        return True
    return True


def infer_media_kind(value: str, forced: str, legacy: Any | None = None) -> str:
    if forced in {"audio", "video"}:
        return forced
    ext = path_ext(value)
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if is_url(value):
        platform = detect_platform(value, legacy)
        if platform in {"bilibili", "youtube", "xiaohongshu", "douyin"}:
            return "video"
    return "audio"


def format_time(seconds: float | int | None) -> str:
    safe = max(0, float(seconds or 0))
    total = int(round(safe))
    s = total % 60
    m_total = total // 60
    m = m_total % 60
    h = m_total // 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def human_duration(seconds: float | int | None) -> str:
    safe = int(float(seconds or 0))
    if safe <= 0:
        return "未知"
    if safe < 60:
        return f"{safe}秒"
    if safe < 3600:
        return f"{safe // 60}分{safe % 60:02d}秒"
    return f"{safe // 3600}小时{safe % 3600 // 60:02d}分"


def probe_and_download(input_value: str, args: argparse.Namespace, run_dir: Path, legacy: Any) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {}
    cached_info = None
    title = args.title

    if is_url(input_value):
        eprint("[Step 1/5] 探测媒体元信息...")
        try:
            meta = dict(legacy.probe_video(input_value))
            cached_info = meta.get("cached_info")
        except Exception as exc:
            eprint(f"[WARN] 探测失败, 将直接尝试下载或提交音频 URL: {exc}")
            meta = {"platform": detect_platform(input_value, legacy), "title": "", "duration": 0}

        if not title and meta.get("title"):
            title = str(meta["title"])

        platform = meta.get("platform") or detect_platform(input_value, legacy)
        eprint("═══════════════════════════════════════════════════════")
        eprint("  媒体探测")
        eprint("───────────────────────────────────────────────────────")
        eprint(f"  平台:      {platform}")
        eprint(f"  标题:      {title or '(未抓到标题)'}")
        eprint(f"  时长:      {human_duration(meta.get('duration'))}")
        eprint("  ASR:       火山录音文件识别 2.0 (volc.seedasr.auc)")
        eprint("═══════════════════════════════════════════════════════")

        if should_download(input_value, args.download, legacy):
            media_work_dir = run_dir / "media"
            media_work_dir.mkdir(parents=True, exist_ok=True)
            eprint("[Step 2/5] 下载媒体...")
            if hasattr(legacy, "is_browser_only_platform") and legacy.is_browser_only_platform(input_value):
                downloaded, detected_title = legacy.download_via_browser(
                    input_value,
                    output_dir=str(media_work_dir),
                    cached_info=cached_info,
                )
                if not title and detected_title:
                    title = detected_title
            else:
                downloaded = legacy.download_video(input_value, output_dir=str(media_work_dir))
            media_input = str(downloaded)
        else:
            eprint("[Step 2/5] 使用公开音频 URL, 跳过下载。")
            media_input = input_value
    else:
        path = Path(input_value).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file does not exist: {path}")
        media_input = str(path)
        if not title:
            title = path.stem
        eprint(f"[Step 1/5] 使用本地媒体: {path.name}")
        if shutil.which("ffprobe"):
            try:
                info = legacy.get_video_info(str(path))
                meta = {"platform": "local", "title": title, "duration": info.get("duration", 0)}
                eprint(f"[INFO] 时长: {human_duration(meta.get('duration'))}")
            except Exception:
                meta = {"platform": "local", "title": title, "duration": 0}
        else:
            meta = {"platform": "local", "title": title, "duration": 0}

    meta["title"] = title or meta.get("title") or Path(media_input).stem
    meta["source"] = input_value
    return media_input, meta


def run_process(command: list[str], cwd: Path | None = None) -> tuple[str, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        eprint(result.stderr.rstrip())
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n\nSTDOUT:\n"
            + result.stdout[-4000:]
            + "\n\nSTDERR:\n"
            + result.stderr[-4000:]
        )
    return result.stdout, result.stderr


def probe_media_duration_value(value: str | Path, timeout: int = 60) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(value),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except Exception:
        return None
    return duration if duration > 0 else None


def urlopen_with_cert_fallback(request: urllib.request.Request, timeout: int):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        if ssl is None or "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        eprint("[WARN] Python 证书链校验失败，使用本次请求的无证书校验兜底重试。")
        return urllib.request.urlopen(
            request,
            timeout=timeout,
            context=ssl._create_unverified_context(),
        )


def ensure_supported_audio_file(media_input: str, run_dir: Path) -> Path:
    path = Path(media_input).expanduser().resolve()
    ext = path.suffix.lower()
    if ext in SUPPORTED_AUC_AUDIO_FORMATS:
        return path
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to extract/convert audio before AUC ASR.")
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"{slugify(path.stem)}.mp3"
    eprint(f"[Step 3/5] 抽取/转换音频为 mp3: {out_path.name}")
    run_process(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            str(out_path),
        ]
    )
    return out_path


def download_direct_audio_url(url: str, run_dir: Path) -> Path:
    ext = path_ext(url) or ".mp3"
    if ext not in SUPPORTED_AUC_AUDIO_FORMATS:
        ext = ".mp3"
    media_dir = run_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    out_path = media_dir / f"direct-audio{ext}"
    eprint(f"[INFO] 下载公开音频 URL 以便分片: {out_path.name}")
    request = urllib.request.Request(url, headers={"User-Agent": "codex-media-to-transcript/1.0"})
    try:
        with urlopen_with_cert_fallback(request, timeout=600) as response:
            with out_path.open("wb") as target:
                shutil.copyfileobj(response, target)
    except Exception:
        if not shutil.which("curl"):
            raise
        result = subprocess.run(
            ["curl", "-L", "-f", "-sS", "-o", str(out_path), url],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Direct audio download failed: {result.stderr[-1000:]}")
    return out_path


def split_audio_file(audio_path: Path, chunk_seconds: int, run_dir: Path) -> list[dict[str, Any]]:
    duration = probe_media_duration_value(audio_path)
    if not duration or duration <= chunk_seconds:
        return [
            {
                "path": audio_path,
                "offset": 0.0,
                "duration": duration,
                "chunkIndex": 1,
                "chunkCount": 1,
            }
        ]
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to split long audio before AUC ASR.")

    chunk_dir = run_dir / "audio" / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    total = int((duration + chunk_seconds - 0.001) // chunk_seconds)
    eprint(f"[INFO] 音频时长 {human_duration(duration)}，按 {human_duration(chunk_seconds)} 切成 {total} 段。")
    chunks: list[dict[str, Any]] = []
    for index in range(total):
        start = float(index * chunk_seconds)
        segment_duration = min(float(chunk_seconds), max(0.0, duration - start))
        if segment_duration <= 0:
            continue
        out_path = chunk_dir / f"{slugify(audio_path.stem)}-part-{index + 1:03d}.mp3"
        run_process(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{segment_duration:.3f}",
                "-i",
                str(audio_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "64k",
                str(out_path),
            ]
        )
        actual_duration = probe_media_duration_value(out_path) or segment_duration
        chunks.append(
            {
                "path": out_path,
                "offset": start,
                "duration": actual_duration,
                "chunkIndex": index + 1,
                "chunkCount": total,
            }
        )
    return chunks


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key: bytes | str, data: str) -> bytes:
    if isinstance(key, str):
        key = key.encode("utf-8")
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()


def encode_path_for_s3(key: str) -> str:
    return "/".join(urllib.parse.quote(part, safe="") for part in key.split("/"))


def content_type_for_file(path: Path) -> str:
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".pcm": "application/octet-stream",
        ".raw": "application/octet-stream",
    }.get(path.suffix.lower(), "application/octet-stream")


def date_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def build_r2_key(file_path: Path, prefix: str | None) -> str:
    default_prefix = os.environ.get("R2_AUDIO_KEY_PREFIX") or f"audio/{date_stamp()}"
    normalized_prefix = (prefix or default_prefix).strip("/")
    unique = uuid.uuid4().hex[:8]
    safe_name = slugify(file_path.stem) + file_path.suffix.lower()
    return f"{normalized_prefix}/{int(time.time() * 1000)}-{unique}-{safe_name}"


def upload_to_r2(file_path: Path, object_key: str) -> dict[str, str]:
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    account_id = os.environ.get("R2_ACCOUNT_ID")
    bucket = os.environ.get("R2_BUCKET")
    public_url = os.environ.get("R2_PUBLIC_BASE_URL") or os.environ.get("R2_PUBLIC_URL")
    endpoint_override = os.environ.get("R2_ENDPOINT")

    if not access_key_id or not secret_access_key or not account_id or not bucket:
        raise RuntimeError("R2 credentials are missing. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, and R2_BUCKET.")
    if not public_url:
        raise RuntimeError("R2 public URL is missing. Set R2_PUBLIC_BASE_URL or R2_PUBLIC_URL.")

    file_data = file_path.read_bytes()
    content_type = content_type_for_file(file_path)
    if endpoint_override:
        endpoint_url = urllib.parse.urlparse(endpoint_override.rstrip("/"))
        host = endpoint_url.netloc
        endpoint = f"{endpoint_url.scheme}://{endpoint_url.netloc}"
    else:
        host = f"{account_id}.r2.cloudflarestorage.com"
        endpoint = f"https://{host}"

    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = now.strftime("%Y%m%d")
    payload_hash = sha256_hex(file_data)
    canonical_uri = f"/{bucket}/{encode_path_for_s3(object_key)}"
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        ["PUT", canonical_uri, "", canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{short_date}/auto/s3/aws4_request"
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, credential_scope, sha256_hex(canonical_request)]
    )
    k_date = hmac_sha256(f"AWS4{secret_access_key}", short_date)
    k_region = hmac_sha256(k_date, "auto")
    k_service = hmac_sha256(k_region, "s3")
    k_signing = hmac_sha256(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    upload_url = f"{endpoint}/{bucket}/{encode_path_for_s3(object_key)}"
    upload_headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    request = urllib.request.Request(
        upload_url,
        data=file_data,
        method="PUT",
        headers=upload_headers,
    )
    try:
        with urlopen_with_cert_fallback(request, timeout=300) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"R2 upload failed: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"R2 upload failed: HTTP {exc.code} {body}") from exc
    except Exception as exc:
        if not shutil.which("curl"):
            raise
        eprint("[WARN] Python HTTPS 上传 R2 失败，改用 curl 兜底。")
        command = ["curl", "-sS", "-f", "-X", "PUT"]
        for key, value in upload_headers.items():
            command.extend(["-H", f"{key}: {value}"])
        command.extend(["--data-binary", f"@{file_path}", upload_url])
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"R2 upload via curl failed: {result.stderr[-1000:] or result.stdout[-1000:]}") from exc

    base = public_url.rstrip("/")
    return {
        "url": f"{base}/{encode_path_for_s3(object_key)}",
        "key": object_key,
        "bucket": bucket,
    }


def verify_public_url(url: str) -> None:
    for attempt in range(6):
        for method, headers in [("HEAD", {}), ("GET", {"Range": "bytes=0-0"})]:
            request = urllib.request.Request(url, method=method, headers=headers)
            try:
                with urlopen_with_cert_fallback(request, timeout=30) as response:
                    if 200 <= response.status < 400:
                        return
            except Exception:
                continue
        if shutil.which("curl"):
            result = subprocess.run(
                ["curl", "-L", "-r", "0-0", "-f", "-sS", url],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                return
        if attempt < 5:
            time.sleep(2)
    raise RuntimeError(f"Uploaded audio URL is not publicly reachable: {url}")


def prepare_audio_inputs(media_input: str, args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
    if is_url(media_input):
        ext = path_ext(media_input)
        if ext not in SUPPORTED_AUC_AUDIO_FORMATS:
            raise RuntimeError("AUC recording-file ASR requires an audio URL. Allow download/conversion instead of --download never for video or unsupported audio URLs.")
        remote_duration = probe_media_duration_value(media_input)
        if remote_duration and remote_duration > args.chunk_seconds and args.download != "never":
            media_input = str(download_direct_audio_url(media_input, run_dir))
        else:
            if remote_duration and remote_duration > args.chunk_seconds:
                eprint("[WARN] 公开音频 URL 超过分片阈值，但 --download never 阻止本地分片，将作为单个 AUC 任务提交。")
            elif remote_duration is None:
                eprint("[INFO] 未能探测公开音频 URL 时长，将作为单个 AUC 任务提交。")
            else:
                eprint("[INFO] 公开音频 URL 未超过分片阈值，直接提交 AUC。")
            duration = remote_duration
            return [
                {
                    "audioUrl": media_input,
                    "audioFormat": SUPPORTED_AUC_AUDIO_FORMATS[ext],
                    "audioPath": None,
                    "uploaded": None,
                    "offset": 0.0,
                    "duration": duration,
                    "chunkIndex": 1,
                    "chunkCount": 1,
                }
            ]

    audio_path = ensure_supported_audio_file(media_input, run_dir)
    chunks = split_audio_file(audio_path, args.chunk_seconds, run_dir)
    if len(chunks) == 1:
        eprint("[Step 4/5] 上传音频到 R2...")
    else:
        eprint(f"[Step 4/5] 上传 {len(chunks)} 个音频分片到 R2...")

    audio_inputs: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_path = Path(chunk["path"])
        object_key = build_r2_key(chunk_path, args.r2_prefix)
        if len(chunks) > 1:
            eprint(f"[INFO] 上传分片 {chunk['chunkIndex']}/{chunk['chunkCount']}: {chunk_path.name}")
        uploaded = upload_to_r2(chunk_path, object_key)
        verify_public_url(uploaded["url"])
        audio_inputs.append(
            {
                "audioUrl": uploaded["url"],
                "audioFormat": SUPPORTED_AUC_AUDIO_FORMATS[chunk_path.suffix.lower()],
                "audioPath": str(chunk_path),
                "uploaded": uploaded,
                "offset": float(chunk.get("offset") or 0.0),
                "duration": chunk.get("duration"),
                "chunkIndex": int(chunk.get("chunkIndex") or 1),
                "chunkCount": int(chunk.get("chunkCount") or len(chunks)),
            }
        )
    return audio_inputs


def prepare_audio_url(media_input: str, args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    audio_inputs = prepare_audio_inputs(media_input, args, run_dir)
    if len(audio_inputs) != 1:
        raise RuntimeError("prepare_audio_url only supports single audio input; use prepare_audio_inputs.")
    return audio_inputs[0]


def speech_key_tutorial() -> str:
    return (
        "缺少火山录音文件识别 2.0 API Key。\n"
        f"1. 开通服务: {AUC_ACTIVATE_URL} ，开通“录音文件识别 2.0”。\n"
        f"2. 创建 API Key: {AUC_API_KEYS_URL} 。\n"
        "3. 建议写入当前工作区 .env.r2: VOLCENGINE_SPEECH_API_KEY=你的APIKey，或在 shell 环境变量中导出。\n"
        "也支持环境变量 VOLCENGINE_AUC_API_KEY、SEEDASR_API_KEY、AUC_API_KEY。"
    )


def resolve_auc_api_key() -> str:
    key = (
        os.environ.get("VOLCENGINE_SPEECH_API_KEY")
        or os.environ.get("VOLCENGINE_AUC_API_KEY")
        or os.environ.get("SEEDASR_API_KEY")
        or os.environ.get("AUC_API_KEY")
    )
    if not key:
        raise RuntimeError(speech_key_tutorial())
    return key


def auc_headers(api_key: str, task_id: str, sequence: bool = False) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": AUC_RESOURCE_ID,
        "X-Api-Request-Id": task_id,
    }
    if sequence:
        headers["X-Api-Sequence"] = "-1"
    return headers


def post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int = 300) -> tuple[dict[str, str], dict[str, Any]]:
    body_text = json.dumps(body, ensure_ascii=False)
    request = urllib.request.Request(
        url,
        data=body_text.encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urlopen_with_cert_fallback(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw.strip() else {}
            return dict(response.headers.items()), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AUC request failed: HTTP {exc.code} {raw}") from exc
    except Exception:
        if not shutil.which("curl"):
            raise
        return post_json_with_curl(url, headers, body_text, timeout)


def post_json_with_curl(url: str, headers: dict[str, str], body_text: str, timeout: int) -> tuple[dict[str, str], dict[str, Any]]:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as header_file:
        command = [
            "curl",
            "-sS",
            "-X",
            "POST",
            "-D",
            header_file.name,
            "-H",
            "Content-Type: application/json",
        ]
        for key, value in headers.items():
            if key.lower() == "content-type":
                continue
            command.extend(["-H", f"{key}: {value}"])
        command.extend(["--data-binary", "@-", url])
        result = subprocess.run(
            command,
            input=body_text,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl request failed: {result.stderr[-1000:]}")
        header_file.seek(0)
        parsed_headers = parse_curl_headers(header_file.read())
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return parsed_headers, payload


def parse_curl_headers(raw: str) -> dict[str, str]:
    blocks = [block for block in raw.replace("\r\n", "\n").split("\n\n") if block.strip()]
    block = blocks[-1] if blocks else ""
    headers: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def get_header(headers: dict[str, str], name: str, default: str = "") -> str:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return default


def compact_context_text(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip()


def first_meta_value(meta: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = meta.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_media_context(meta: dict[str, Any], source: str) -> str | None:
    lines: list[str] = []
    title = first_meta_value(meta, ["title"])
    platform = first_meta_value(meta, ["platform"])
    author = first_meta_value(meta, ["author", "nickname", "uploader", "owner", "creator"])
    description = first_meta_value(meta, ["description", "desc", "summary", "caption", "intro"])
    duration = meta.get("duration")

    if title:
        lines.append(f"标题: {title}")
    if platform:
        lines.append(f"平台: {platform}")
    if author:
        lines.append(f"作者: {author}")
    if duration:
        lines.append(f"时长: {human_duration(duration)}")
    if description and description != title:
        lines.append(f"简介: {description}")
    if source and len(source) <= 140:
        lines.append(f"来源: {source}")

    text = "\n".join(lines)
    return compact_context_text(text, MAX_AUC_CONTEXT_CHARS) if text.strip() else None


def build_auc_context(args: argparse.Namespace) -> str | None:
    chunks = []
    auto_context = getattr(args, "auto_context", None)
    if auto_context:
        chunks.append(str(auto_context))
    chunks.extend(args.topic)
    chunks.extend(args.context)
    for context_file in args.context_file:
        path = Path(context_file).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Context file does not exist: {path}")
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    text = "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    if not text:
        return None
    text = compact_context_text(text, MAX_AUC_CONTEXT_CHARS)
    return json.dumps(
        {
            "context_type": "dialog_ctx",
            "context_data": [{"text": text}],
        },
        ensure_ascii=False,
    )


def submit_auc_task(audio: dict[str, Any], args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    api_key = resolve_auc_api_key()
    task_id = str(uuid.uuid4())
    request_payload: dict[str, Any] = {
        "model_name": "bigmodel",
        "enable_itn": True,
        "enable_punc": True,
        "enable_ddc": False,
        "enable_speaker_info": bool(args.speaker),
        "show_utterances": True,
    }
    if args.emotion:
        request_payload["enable_emotion_detection"] = True
    if args.speaker:
        request_payload["ssd_version"] = "200"
    context = build_auc_context(args)
    if context:
        request_payload["corpus"] = {"context": context}

    body = {
        "user": {"uid": os.environ.get("VOLCENGINE_SPEECH_UID", "codex-media-to-transcript")},
        "audio": {
            "url": audio["audioUrl"],
            "format": audio["audioFormat"],
        },
        "request": request_payload,
    }
    if args.language:
        body["audio"]["language"] = normalize_auc_language(args.language)

    chunk_label = ""
    if int(audio.get("chunkCount") or 1) > 1:
        chunk_label = f" ({audio.get('chunkIndex')}/{audio.get('chunkCount')})"
    eprint(f"[Step 5/5] 提交火山录音文件识别 2.0 任务{chunk_label}...")
    headers, payload = post_json(AUC_SUBMIT_URL, auc_headers(api_key, task_id, sequence=True), body)
    status = get_header(headers, "X-Api-Status-Code")
    message = get_header(headers, "X-Api-Message")
    logid = get_header(headers, "X-Tt-Logid")
    if status != AUC_SUCCESS:
        raise RuntimeError(
            f"AUC submit failed: status={status} message={message} logid={logid}\n\n{speech_key_tutorial()}"
        )
    return task_id, {"headers": headers, "body": payload, "request": body}


def normalize_auc_language(language: str) -> str:
    normalized = language.strip()
    if normalized in {"zh", "cmn-Hans-CN"}:
        return "zh-CN"
    if normalized == "eng-US":
        return "en-US"
    return normalized


def query_auc_until_done(task_id: str, poll_interval: int, timeout_seconds: int) -> dict[str, Any]:
    api_key = resolve_auc_api_key()
    started = time.time()
    while time.time() - started <= timeout_seconds:
        headers, payload = post_json(AUC_QUERY_URL, auc_headers(api_key, task_id), {}, timeout=120)
        status = get_header(headers, "X-Api-Status-Code")
        message = get_header(headers, "X-Api-Message")
        if status == AUC_SUCCESS:
            payload["_headers"] = headers
            return payload
        if status in AUC_PROCESSING:
            eprint(f"[INFO] AUC task {task_id} still processing: status={status} message={message}")
            time.sleep(poll_interval)
            continue
        raise RuntimeError(f"AUC query failed: status={status} message={message} logid={get_header(headers, 'X-Tt-Logid')}")
    raise RuntimeError(f"AUC task timed out after {timeout_seconds}s: {task_id}")


def run_auc_asr(audio: dict[str, Any], args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    asr_dir = run_dir / "asr"
    asr_dir.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if int(audio.get("chunkCount") or 1) > 1:
        suffix = f"-{int(audio.get('chunkIndex') or 1):03d}"
    task_id, submit_payload = submit_auc_task(audio, args)
    submit_path = asr_dir / f"auc-submit{suffix}.json"
    submit_path.write_text(json.dumps(submit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result_payload = query_auc_until_done(task_id, args.poll_interval, args.timeout)
    result_path = asr_dir / f"auc-result{suffix}.json"
    result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "taskId": task_id,
        "submitJson": str(submit_path),
        "resultJson": str(result_path),
        "result": result_payload,
        "audio": audio,
        "chunkIndex": int(audio.get("chunkIndex") or 1),
        "chunkCount": int(audio.get("chunkCount") or 1),
        "offset": float(audio.get("offset") or 0.0),
        "duration": audio.get("duration"),
    }


def run_auc_asr_batch(audio_inputs: list[dict[str, Any]], args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
    if len(audio_inputs) <= 1:
        return [run_auc_asr(audio_inputs[0], args, run_dir)]

    workers = max(1, min(int(args.concurrency), len(audio_inputs)))
    eprint(f"[INFO] 并发处理 {len(audio_inputs)} 个 AUC 分片，最大并发 {workers}。")
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_auc_asr, audio, args, run_dir) for audio in audio_inputs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            eprint(f"[INFO] 分片 {result['chunkIndex']}/{result['chunkCount']} AUC 完成。")
            results.append(result)
    return sorted(results, key=lambda item: int(item.get("chunkIndex") or 1))


def segment_fields(segment: dict[str, Any]) -> dict[str, Any]:
    start = segment.get("start_time", segment.get("startTime", 0))
    end = segment.get("end_time", segment.get("endTime", start))
    text = segment.get("text", "")
    additions = segment.get("additions", {}) or {}
    speaker = (
        segment.get("speaker")
        or segment.get("speaker_id")
        or segment.get("speakerId")
        or additions.get("speaker")
    )
    emotion = segment.get("emotion") or additions.get("emotion")
    try:
        start_f = float(start or 0) / 1000.0
    except Exception:
        start_f = 0.0
    try:
        end_f = float(end or start_f) / 1000.0
    except Exception:
        end_f = start_f
    return {
        "start": start_f,
        "end": max(end_f, start_f),
        "text": str(text or "").strip(),
        "speaker": str(speaker).strip() if speaker is not None and str(speaker).strip() else "",
        "emotion": str(emotion).strip() if emotion is not None and str(emotion).strip() else "",
    }


def extract_auc_segments(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], float | None]:
    result = payload.get("result")
    if isinstance(result, list) and result and isinstance(result[0], dict):
        result = result[0]
    if not isinstance(result, dict):
        raise RuntimeError("AUC JSON does not contain result.")
    audio_info = payload.get("audio_info") if isinstance(payload.get("audio_info"), dict) else {}
    duration_ms = audio_info.get("duration")
    try:
        duration = float(duration_ms) / 1000.0 if duration_ms is not None else None
    except Exception:
        duration = None
    utterances = result.get("utterances")
    if isinstance(utterances, list) and utterances:
        return [segment_fields(x) for x in utterances if isinstance(x, dict)], duration
    text = str(result.get("text") or "").strip()
    if text:
        return [{"start": 0.0, "end": duration or 0.0, "text": text, "speaker": ""}], duration
    raise RuntimeError("AUC JSON does not contain result.utterances or result.text.")


def join_text(prev: str, current: str) -> str:
    if not prev:
        return current
    if not current:
        return prev
    if re.search(r"[A-Za-z0-9]$", prev) and re.match(r"[A-Za-z0-9]", current):
        return prev + " " + current
    return prev + current


def speaker_label(raw: str, speaker_map: dict[str, int]) -> str:
    if not raw:
        return ""
    if raw not in speaker_map:
        speaker_map[raw] = len(speaker_map) + 1
    return f"说话人 {speaker_map[raw]}："


def group_segments(segments: list[dict[str, Any]], include_speakers: bool) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_text = ""
    speaker_map: dict[str, int] = {}

    def flush() -> None:
        nonlocal current, current_text
        if not current or not current_text.strip():
            current = None
            current_text = ""
            return
        current["text"] = current_text.strip()
        groups.append(current)
        current = None
        current_text = ""

    for segment in segments:
        text = segment["text"]
        if not text:
            continue
        label = speaker_label(segment["speaker"], speaker_map) if include_speakers else ""
        text_with_speaker = f"{label}{text}" if label else text

        if current is None:
            current = {
                "start": segment["start"],
                "end": segment["end"],
                "speaker": segment["speaker"],
            }
            current_text = text_with_speaker
            continue

        gap = segment["start"] - float(current["end"])
        duration = segment["end"] - float(current["start"])
        long_enough = len(current_text) >= 320 or duration >= 75
        hard_limit = len(current_text) >= 700 or duration >= 135
        ends_sentence = bool(re.search(r"[。！？!?\.]$", current_text))
        speaker_changed = bool(include_speakers and segment["speaker"] and segment["speaker"] != current.get("speaker"))

        if gap > 2.0 or hard_limit or (long_enough and ends_sentence) or (speaker_changed and len(current_text) >= 80):
            flush()
            current = {
                "start": segment["start"],
                "end": segment["end"],
                "speaker": segment["speaker"],
            }
            current_text = text_with_speaker
        else:
            current["end"] = segment["end"]
            current_text = join_text(current_text, text_with_speaker)
    flush()
    return split_oversized_groups(groups)


def split_text_chunks(text: str, target_chars: int) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > target_chars:
        window = remaining[: min(len(remaining), target_chars + 160)]
        min_cut = max(120, int(target_chars * 0.55))
        cut = -1
        for pattern in ["。", "！", "？", "；", ";", ".", "!", "?", "，", ",", "、", " "]:
            idx = window.rfind(pattern)
            if idx >= min_cut:
                cut = idx + 1
                break
        if cut < min_cut:
            cut = target_chars
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def split_oversized_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resized: list[dict[str, Any]] = []
    for group in groups:
        text = str(group.get("text", "")).strip()
        start = float(group.get("start", 0))
        end = float(group.get("end", start))
        duration = max(0.0, end - start)
        target_parts = max(
            1,
            (len(text) + 899) // 900,
            int((duration + 149) // 150) if duration else 1,
        )
        if target_parts <= 1:
            resized.append(group)
            continue
        target_chars = max(300, int(len(text) / target_parts) + 1)
        chunks = split_text_chunks(text, target_chars)
        total_chars = sum(len(chunk) for chunk in chunks) or 1
        cursor = start
        consumed_chars = 0
        for index, chunk in enumerate(chunks):
            consumed_chars += len(chunk)
            if index == len(chunks) - 1:
                chunk_end = end
            else:
                chunk_end = start + duration * (consumed_chars / total_chars)
            resized.append(
                {
                    "start": cursor,
                    "end": max(cursor, chunk_end),
                    "speaker": group.get("speaker", ""),
                    "text": chunk,
                }
            )
            cursor = chunk_end
    return resized


def build_raw_transcript(
    title: str,
    source: str,
    duration: float | None,
    segments: list[dict[str, Any]],
    include_speakers: bool,
) -> str:
    groups = group_segments(segments, include_speakers=include_speakers)
    lines = [
        f"# {title}",
        "",
        f"> 时长 {format_time(duration or (segments[-1]['end'] if segments else 0))} | 来源: {source}",
        "",
    ]
    if not groups:
        lines.extend(["## 1. 逐字转写 [00:00 - 00:00]", "", "[无可用 ASR 文本]", ""])
        return "\n".join(lines)

    for index, group in enumerate(groups, start=1):
        lines.append(
            f"## {index}. 逐字转写 [{format_time(group['start'])} - {format_time(group['end'])}]"
        )
        lines.append("")
        lines.append(str(group["text"]).strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def read_context_files(paths: list[str]) -> list[str]:
    chunks: list[str] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Context file does not exist: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_CORRECTION_CONTEXT_CHARS:
            text = text[:MAX_CORRECTION_CONTEXT_CHARS] + "\n\n[context truncated]"
        chunks.append(f"### Context file: {path}\n\n{text}")
    return chunks


def build_correction_prompt(
    title: str,
    source: str,
    topics: list[str],
    contexts: list[str],
    context_files: list[str],
    raw_path: Path,
    final_target: Path,
) -> str:
    context_chunks = list(contexts) + read_context_files(context_files)
    context_text = "\n\n".join(x.strip() for x in context_chunks if x.strip()) or "(none)"
    topic_text = "\n".join(f"- {x}" for x in topics if x.strip()) or "- (none)"
    return f"""# AI Correction Prompt

You are correcting an ASR-generated transcript. Produce the final Markdown transcript, not subtitles and not a summary.

## Source

- Title: {title}
- Source: {source}
- Raw transcript file: {raw_path}
- Final output target: {final_target}

## Topic / Glossary Hints

{topic_text}

## Extra Context

{context_text}

## Hard Rules

- Preserve the speaker's meaning, order,口语词, repetitions, corrections, and uncertainty.
- Correct obvious ASR mistakes using the topic, glossary, and surrounding context.
- Do not summarize, turn it into article prose, invent missing content, or remove substantive speech.
- Convert ASR utterance fragments into readable transcript paragraphs.
- Rename generic section headings like "逐字转写" into short content-based headings.
- Keep section-level timestamps monotonic.
- Mark unresolved audio as `[听不清]` or `[疑似: 词语]` instead of guessing.

Now read `raw-transcript.md`, apply these rules, and write the corrected Markdown to `transcript.md`.
"""


def write_transcript_artifacts(
    asr_json_path: Path,
    title: str,
    source: str,
    args: argparse.Namespace,
    run_dir: Path,
    segments: list[dict[str, Any]],
    duration: float | None,
) -> dict[str, Any]:
    raw_path = run_dir / "raw-transcript.md"
    final_target = run_dir / "transcript.md"
    prompt_path = run_dir / "correction-prompt.md"

    raw_md = build_raw_transcript(
        title=title,
        source=source,
        duration=duration,
        segments=segments,
        include_speakers=bool(args.speaker),
    )
    raw_path.write_text(raw_md, encoding="utf-8")
    prompt_path.write_text(
        build_correction_prompt(
            title=title,
            source=source,
            topics=args.topic,
            contexts=args.context,
            context_files=args.context_file,
            raw_path=raw_path,
            final_target=final_target,
        ),
        encoding="utf-8",
    )
    return {
        "asrJson": str(asr_json_path),
        "rawTranscript": str(raw_path),
        "correctionPrompt": str(prompt_path),
        "finalTranscriptTarget": str(final_target),
        "segmentCount": len(segments),
        "duration": duration,
    }


def convert_auc_json(
    asr_json_path: Path,
    title: str,
    source: str,
    args: argparse.Namespace,
    run_dir: Path,
) -> dict[str, Any]:
    payload = json.loads(asr_json_path.read_text(encoding="utf-8"))
    segments, duration = extract_auc_segments(payload)
    return write_transcript_artifacts(asr_json_path, title, source, args, run_dir, segments, duration)


def text_from_result_payload(payload: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    result = payload.get("result")
    if isinstance(result, list) and result and isinstance(result[0], dict):
        result = result[0]
    if isinstance(result, dict):
        text = str(result.get("text") or "").strip()
        if text:
            return text
    text = ""
    for segment in segments:
        text = join_text(text, str(segment.get("text") or ""))
    return text


def combine_auc_results(asr_results: list[dict[str, Any]], run_dir: Path) -> tuple[Path, list[dict[str, Any]], float | None]:
    asr_dir = run_dir / "asr"
    asr_dir.mkdir(parents=True, exist_ok=True)
    combined_segments: list[dict[str, Any]] = []
    chunk_summaries: list[dict[str, Any]] = []
    text_chunks: list[str] = []
    max_duration = 0.0

    for item in sorted(asr_results, key=lambda value: int(value.get("chunkIndex") or 1)):
        payload = item["result"]
        offset = float(item.get("offset") or 0.0)
        segments, payload_duration = extract_auc_segments(payload)
        shifted_segments: list[dict[str, Any]] = []
        for segment in segments:
            shifted = dict(segment)
            shifted["start"] = float(segment.get("start") or 0.0) + offset
            shifted["end"] = float(segment.get("end") or 0.0) + offset
            shifted_segments.append(shifted)
        combined_segments.extend(shifted_segments)

        chunk_duration = item.get("duration") or payload_duration
        if not chunk_duration and shifted_segments:
            chunk_duration = max(float(segment.get("end") or offset) for segment in shifted_segments) - offset
        try:
            chunk_duration_f = float(chunk_duration or 0.0)
        except Exception:
            chunk_duration_f = 0.0
        if shifted_segments:
            max_duration = max(max_duration, max(float(segment.get("end") or 0.0) for segment in shifted_segments))
        max_duration = max(max_duration, offset + chunk_duration_f)
        text_chunks.append(text_from_result_payload(payload, segments))
        chunk_summaries.append(
            {
                "chunkIndex": item.get("chunkIndex"),
                "chunkCount": item.get("chunkCount"),
                "offset": offset,
                "duration": chunk_duration_f or None,
                "taskId": item.get("taskId"),
                "submitJson": item.get("submitJson"),
                "resultJson": item.get("resultJson"),
            }
        )

    combined_segments.sort(key=lambda segment: (float(segment.get("start") or 0.0), float(segment.get("end") or 0.0)))
    utterances = []
    for segment in combined_segments:
        additions: dict[str, Any] = {}
        if segment.get("speaker"):
            additions["speaker"] = segment["speaker"]
        if segment.get("emotion"):
            additions["emotion"] = segment["emotion"]
        utterance = {
            "start_time": int(round(float(segment.get("start") or 0.0) * 1000)),
            "end_time": int(round(float(segment.get("end") or 0.0) * 1000)),
            "text": str(segment.get("text") or ""),
        }
        if additions:
            utterance["additions"] = additions
        utterances.append(utterance)

    combined_payload = {
        "audio_info": {"duration": int(round(max_duration * 1000)) if max_duration else None},
        "result": {
            "text": "\n".join(chunk.strip() for chunk in text_chunks if chunk.strip()),
            "utterances": utterances,
        },
        "chunks": chunk_summaries,
    }
    combined_path = asr_dir / "auc-result-combined.json"
    combined_path.write_text(json.dumps(combined_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return combined_path, combined_segments, (max_duration or None)


def convert_auc_results(
    asr_results: list[dict[str, Any]],
    title: str,
    source: str,
    args: argparse.Namespace,
    run_dir: Path,
) -> dict[str, Any]:
    if len(asr_results) == 1:
        return convert_auc_json(Path(asr_results[0]["resultJson"]), title, source, args, run_dir)
    combined_path, segments, duration = combine_auc_results(asr_results, run_dir)
    return write_transcript_artifacts(combined_path, title, source, args, run_dir, segments, duration)


def check_command(name: str) -> bool:
    return shutil.which(name) is not None


def doctor() -> int:
    vault_root = find_vault_root()
    loaded_env = load_project_env(vault_root)
    print("=" * 55)
    print("  media-to-transcript doctor")
    print("=" * 55)
    issues: list[str] = []
    warnings: list[str] = []

    for command, required in [("python3", True), ("ffmpeg", True), ("ffprobe", True), ("yt-dlp", False)]:
        ok = check_command(command)
        mark = "✓" if ok else ("✗" if required else "⚠")
        print(f"  {mark} {command}")
        if required and not ok:
            issues.append(f"Install {command}")
        if not required and not ok:
            warnings.append(f"{command} missing; YouTube or generic URL download may fail")

    try:
        locate_skill("video-transcript")
        print("  ✓ video-transcript downloader skill")
    except Exception as exc:
        print(f"  ✗ video-transcript downloader skill: {exc}")
        issues.append("Install or restore video-transcript skill")

    try:
        import playwright.sync_api  # noqa: F401

        print("  ✓ playwright")
    except Exception:
        print("  ⚠ playwright missing; Douyin/XHS/Bilibili page extraction may fail")
        warnings.append("Install playwright and chromium for platform page downloads")

    speech_key_present = bool(
        os.environ.get("VOLCENGINE_SPEECH_API_KEY")
        or os.environ.get("VOLCENGINE_AUC_API_KEY")
        or os.environ.get("SEEDASR_API_KEY")
        or os.environ.get("AUC_API_KEY")
    )
    print(f"  {'✓' if speech_key_present else '✗'} Volcengine recording-file ASR 2.0 API key")
    if not speech_key_present:
        issues.append(speech_key_tutorial())

    r2_required = ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID", "R2_BUCKET"]
    missing_r2 = [name for name in r2_required if not os.environ.get(name)]
    public_ok = bool(os.environ.get("R2_PUBLIC_BASE_URL") or os.environ.get("R2_PUBLIC_URL"))
    print(f"  {'✓' if not missing_r2 else '✗'} R2 upload env")
    print(f"  {'✓' if public_ok else '✗'} R2 public URL env")
    if missing_r2:
        issues.append("Set missing R2 upload env vars")
    if not public_ok:
        issues.append("Set R2_PUBLIC_BASE_URL or R2_PUBLIC_URL")

    print(f"  ✓ vault root: {vault_root}")
    if loaded_env:
        print("  ✓ env files loaded:")
        for path in loaded_env:
            print(f"     - {path}")
    else:
        print("  ⚠ no env files loaded")

    print("=" * 55)
    if warnings:
        print("  Warnings:")
        for warning in warnings:
            print(f"     - {warning}")
    if issues:
        print(f"  Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"     - {issue}")
        return 1
    print("  Ready")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert media to corrected transcript artifacts.")
    parser.add_argument("input", nargs="?", help="Media URL or local audio/video path")
    parser.add_argument("--from-asr-json", default=None, help="Build transcript artifacts from existing AUC result JSON")
    parser.add_argument("--title", default=None, help="Override title")
    parser.add_argument("--source", default=None, help="Override source when using --from-asr-json")
    parser.add_argument("--topic", action="append", default=[], help="Topic or glossary hint for ASR/correction")
    parser.add_argument("--context", action="append", default=[], help="Extra ASR/correction context")
    parser.add_argument("--context-file", action="append", default=[], help="File with extra ASR/correction context")
    parser.add_argument("--language", default="zh-CN", help="ASR language, default zh-CN")
    parser.add_argument("--speaker", action="store_true", help="Request and preserve speaker labels")
    parser.add_argument("--emotion", action="store_true", help="Enable Volcengine utterance emotion detection")
    parser.add_argument("--media-kind", choices=["auto", "audio", "video"], default="auto")
    parser.add_argument("--download", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--chunk-seconds", type=int, default=DEFAULT_CHUNK_SECONDS, help="Split local/downloaded audio longer than this many seconds, default 180")
    parser.add_argument("--concurrency", type=int, default=3, help="Max parallel AUC chunk tasks, default 3")
    parser.add_argument("--out-dir", default=None, help="Output directory")
    parser.add_argument("--r2-prefix", default=None, help="R2 object prefix for uploaded local audio")
    parser.add_argument("--timeout", type=int, default=7200, help="AUC timeout seconds")
    parser.add_argument("--poll-interval", type=int, default=5, help="AUC poll interval seconds")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    parser.add_argument("--doctor", action="store_true", help="Check dependencies and env")
    args = parser.parse_args(argv)
    if not args.doctor and not args.input and not args.from_asr_json:
        parser.error("input or --from-asr-json is required unless --doctor is used")
    if args.chunk_seconds < 30:
        parser.error("--chunk-seconds must be at least 30")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    return args


def make_run_dir(title: str | None, out_dir: str | None) -> Path:
    if out_dir:
        run_dir = Path(out_dir).expanduser()
        if not run_dir.is_absolute():
            run_dir = (Path.cwd() / run_dir).resolve()
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = DEFAULT_OUTPUT_ROOT / f"{stamp}-{slugify(title or 'media')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.doctor:
        return doctor()

    vault_root = find_vault_root()
    load_project_env(vault_root)
    video_skill_dir = locate_skill("video-transcript")
    legacy = load_legacy_video_module(video_skill_dir)

    if args.from_asr_json:
        asr_json = Path(args.from_asr_json).expanduser()
        if not asr_json.is_absolute():
            asr_json = (Path.cwd() / asr_json).resolve()
        title = args.title or asr_json.stem
        run_dir = make_run_dir(title, args.out_dir)
        summary = {
            "success": True,
            "mode": "from-auc-json",
            "title": title,
            "source": args.source or str(asr_json),
            "runDir": str(run_dir),
            **convert_auc_json(asr_json, title, args.source or str(asr_json), args, run_dir),
        }
    else:
        input_value = str(args.input)
        source_value = args.source or input_value
        title_seed = args.title or (Path(input_value).stem if not is_url(input_value) else "media")
        run_dir = make_run_dir(title_seed, args.out_dir)
        media_input, meta = probe_and_download(input_value, args, run_dir, legacy)
        meta["source"] = source_value
        title = str(args.title or meta.get("title") or Path(media_input).stem)
        media_kind = infer_media_kind(media_input, args.media_kind, legacy)
        args.auto_context = build_media_context(meta, source_value)
        if args.auto_context:
            eprint(f"[INFO] AUC context: {args.auto_context}")
        audio_inputs = prepare_audio_inputs(media_input, args, run_dir)
        asr_results = run_auc_asr_batch(audio_inputs, args, run_dir)
        task_ids = [item["taskId"] for item in asr_results]
        converted = convert_auc_results(asr_results, title, source_value, args, run_dir)
        summary = {
            "success": True,
            "mode": "media",
            "title": title,
            "source": source_value,
            "mediaInput": media_input,
            "mediaKind": media_kind,
            "autoContext": args.auto_context,
            "emotionDetection": bool(args.emotion),
            "chunkSeconds": args.chunk_seconds,
            "concurrency": args.concurrency,
            "audio": audio_inputs[0] if len(audio_inputs) == 1 else audio_inputs,
            "audioChunks": audio_inputs,
            "runDir": str(run_dir),
            "asrOutputs": {
                "json": converted["asrJson"],
                "chunks": [item["resultJson"] for item in asr_results],
            },
            "taskId": task_ids[0] if len(task_ids) == 1 else None,
            "taskIds": task_ids,
            **converted,
        }

    summary_path = Path(summary["runDir"]) / "run-summary.json"
    summary["runSummary"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        eprint("[OK] 已生成粗逐字稿和纠错提示。")
        print("Done.")
        print(f"Run dir: {summary['runDir']}")
        print(f"Raw transcript: {summary['rawTranscript']}")
        print(f"Correction prompt: {summary['correctionPrompt']}")
        print(f"Final transcript target: {summary['finalTranscriptTarget']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
