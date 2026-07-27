# Skills

This directory contains ten core workflow packages plus three bundled support packages. Keep them as sibling directories because several handoffs and validation commands intentionally resolve adjacent skills.

| Skill | Stage |
|---|---|
| `viral-video-benchmark` | Benchmark discovery, scoring, evidence, analysis, archive |
| `media-to-transcript` | Platform media acquisition, Volcengine AUC ASR, correction handoff |
| `content-remix` | Evidence-bound benchmark mechanism transfer into original platform drafts |
| `minimax-voice-director` | Voice direction, approval, generation, take selection |
| `audio-to-subtitles` | Final-audio ASR and aligned subtitle delivery |
| `video-script` | Director treatment, Beat Graph, production contract |
| `talking-head-hyperframes` | HyperFrames fixed-stage template factory |
| `hyperframes-scene-animator` | HyperFrames scene execution and proof review |
| `music` | ElevenLabs BGM generation, loop mastering, registry |
| `douyin-cover` | Short-video cover diagnosis and generation |

Bundled support packages:

| Skill | Consumer |
|---|---|
| `video-transcript` | Downloader/probe compatibility helpers for `media-to-transcript` |
| `hook-writing` | Hook taxonomy and library for `viral-video-benchmark` |
| `obsidian-bases` | `.base` view contract for `viral-video-benchmark` |

Each package owns its `SKILL.md`, references, scripts, assets, evals, and tests. Read the package's `SKILL.md` before invoking its scripts directly.
