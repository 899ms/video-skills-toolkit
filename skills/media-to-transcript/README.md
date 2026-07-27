# media-to-transcript

Codex Skill for converting audio/video URLs or local media into corrected Markdown transcripts.

Core route:

1. Reuse platform download/probe helpers for Bilibili, Douyin, Xiaohongshu, YouTube, or local media.
2. Extract/convert audio to 16 kHz mono mp3.
3. Upload local audio chunks to Cloudflare R2 so Volcengine can fetch them.
4. Submit Volcengine recording-file recognition 2.0 (`volc.seedasr.auc`) jobs.
5. Split media longer than 180 seconds into parallel ASR chunks, then merge utterances back onto the original timeline.
6. Generate `raw-transcript.md` and an AI correction prompt so the final output is a readable transcript, not subtitles.

## Install

Clone this repository into your Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/bozhouDev/media-to-transcript.git "${CODEX_HOME:-$HOME/.codex}/skills/media-to-transcript"
```

Run the doctor:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/media-to-transcript/scripts/media_to_transcript.py" --doctor
```

## Configuration

The script needs a Volcengine Speech API Key for recording-file recognition 2.0:

```bash
VOLCENGINE_SPEECH_API_KEY=your_api_key
```

Setup links:

- Enable recording-file recognition 2.0: https://console.volcengine.com/speech/new/setting/activate
- Create API Key: https://console.volcengine.com/speech/new/setting/apikeys

Local files also need Cloudflare R2 env vars because the AUC API accepts public audio URLs:

```bash
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ACCOUNT_ID=...
R2_BUCKET=...
R2_PUBLIC_BASE_URL=...
```

Keep these in your workspace `.env.r2`, `.env`, or shell environment. Do not commit secrets.

## Usage

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/media-to-transcript/scripts/media_to_transcript.py" \
  "https://www.douyin.com/video/xxx" \
  --topic "视频主题或关键词"
```

Enable utterance emotion labels only when needed:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/media-to-transcript/scripts/media_to_transcript.py" video.mp4 --emotion
```

## Outputs

Each run writes:

- `audio/` and `audio/chunks/`
- `asr/auc-result*.json`
- `asr/auc-result-combined.json` for multi-chunk runs
- `raw-transcript.md`
- `correction-prompt.md`
- `transcript.md`
- `run-summary.json`

The final user-facing artifact should be `transcript.md`.
