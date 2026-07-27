---
name: video-transcript
description: Deprecated compatibility package. Do not use this skill for transcription. For any audio/video transcript, 逐字稿, 视频转文字, 音频转文字, 听写, or 提取视频文案 request, use media-to-transcript instead. The remaining scripts are kept only as downloader/probe helpers imported by media-to-transcript.
---

# Deprecated Video Transcript

Do not run the old transcription workflow from this skill. The previous direct model transcription path has been retired.

For all transcript work, use:

```bash
MEDIA_SKILL_DIR="<SKILL_ROOT>/media-to-transcript"
rtk python3 "$MEDIA_SKILL_DIR/scripts/media_to_transcript.py" "<URL或本地媒体路径>" --topic "主题或关键词"
```

This folder remains only because `media-to-transcript` imports the existing downloader and platform probing helpers for Bilibili, Douyin, Xiaohongshu, and YouTube.
