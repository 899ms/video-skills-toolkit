# Generated Music Registry

Use this registry as the workspace's reusable AI-music catalog. Before calling the ElevenLabs Music API, search the entries and audition any track with a compatible use case, mood, tempo, and density. Reuse the linked audio file when it fits; rerunning the same prompt is a new paid generation.

Keep every successful generation as a separate entry. Preserve raw API responses unchanged and list derived loop masters or previews separately.

## BGM-20260717-001 — IndexTTS2 technology explainer loop

- Status: user-approved for reuse; not yet substituted into the published IndexTTS2 video
- Generated: 2026-07-17
- Provider: ElevenLabs Music API
- Project/use case: `indextts2-voice-clone`; fast-paced Chinese technology explainer about local AI voice cloning
- Tags: `technology`, `minimal electronic`, `speech-friendly`, `instrumental`, `loopable`, `96 BPM`, `warm bass`, `digital plucks`
- Model: `music_v2`
- Requested duration: `15000 ms`
- Request settings: `force_instrumental=true`, `output_format=mp3_48000_192`
- Raw duration: `15.024 s` including MP3 container/encoder padding
- Loop-master duration: `14.250 s`
- Reuse guidance: Use under technology, AI-tool, coding, or product-explainer narration that needs a restrained pulse without a dominant melody. Start the mix quietly and duck under speech.

### Exact prompt

```text
Create a seamless loopable instrumental background music bed for a fast-paced Chinese technology explainer about local AI voice cloning. Exactly 15 seconds, 4/4 time at 96 BPM, six bars. Modern minimal electronic groove with warm rounded bass, tight muted kick, soft crisp percussion, subtle digital plucks and a restrained futuristic texture. Speech-friendly, confident, curious and lightly energetic. Keep the musical density and harmony stable from beginning to end so it can repeat indefinitely. The final beat must connect naturally back to the first beat. No intro, no ending, no fade, no breakdown, no build, no dramatic transition, no vocals, no spoken words, no choir, no cymbal crashes, no risers, no dominant lead melody, no harsh high frequencies.
```

### Files

- Immutable raw API output: `indextts2-voice-clone/work/music/elevenlabs/index-tts2-tech-loop-raw.mp3`
  - SHA-256: `cb252e2ed7f54c47d4834971e8e182e9bad291c68c97b8c005b8feca20c2e078`
- Lossless loop master: `indextts2-voice-clone/work/music/elevenlabs/index-tts2-tech-loop-master.wav`
  - SHA-256: `9e7b843e03b36433fcb03402b95a56e7f20e399f71fdb4fe8eb90cea193fc9f4`
- Three-repeat seam preview: `indextts2-voice-clone/work/music/elevenlabs/index-tts2-tech-loop-preview-3x.mp3`
  - SHA-256: `6e647ff58dea6c2633eb8f863f04d318d4bc1beb467b74cad443a53c639e7861`

### Processing notes

- Preserve the raw MP3 unchanged.
- Build the WAV master at 48 kHz stereo, 24-bit PCM.
- Create a circular `0.75 s` tail-to-head crossfade, producing a `14.25 s` loop.
- Create the MP3 preview locally by repeating the WAV master three times; it does not consume additional API generation credits.
