# Executor report v1

Executor: `proof-fixture-executor`  
Proof version: `v1` with same-owner recheck `v2`

| Item | Status | Evidence | Result |
| --- | --- | --- | --- |
| Locked manifest, source hashes and DESIGN hash | PASS | `manifest.json`, `review/cli/inputs.txt` | READY inputs remain hash-locked. |
| Runtime adaptation and registered paused timeline | PASS | `runtime-adaptation.json`, `compositions/content.html` | 3 beats map to 2 scenes; every source acceptance point is traced. |
| Fixed stage boundary | PASS | `review/cli/fixed-stage.txt` | Root background/content/caption/audio topology and geometry remain valid. |
| Pinned lint, validate, inspect and aggregate check | PASS | `review/cli/lint.txt`, `review/cli/validate.txt`, `review/cli/inspect.txt`, `review/cli/check.txt` | No lint, runtime, layout, motion or contrast failure remains. |
| Source acceptance snapshots | PASS | `snapshots/acceptance/frame-00-at-0.1s.png` through `frame-11-at-3.56s.png` | All 12 mapped source states exist. |
| Cue before / cue after | PASS | `snapshots/acceptance/frame-01-at-0.42s.png`, `frame-02-at-1.05s.png`, `frame-09-at-2.72s.png`, `frame-10-at-3.12s.png` | Neither verified evidence nor PASS appears before its cue. |
| Chapter and density states | PASS | `snapshots/acceptance/frame-03-at-1.42s.png`, `frame-11-at-3.56s.png` | Provenance and validation chapters have distinct information structures. |
| Widest caption and safe area | PASS | `snapshots/acceptance/frame-09-at-2.72s.png`, `review/cli/inspect.txt` | The longest caption is visible, single-line, centered and unobstructed. |
| PIP crop | NOT_APPLICABLE | `manifest.json`, this report | No talking-head/PIP input was supplied; the PIP mount is absent. |
| First and last audio regions | PASS | `review/media-analysis-v1.json`, `review/media/audio-first-region.txt`, `review/media/audio-last-region.txt` | Both boundary regions contain audible locked voice. |
| Black and silent tail | PASS | `review/media-analysis-v1.json`, `review/media/black-tail.txt`, `review/media/silent-tail.txt` | No black interval or disallowed silent tail was detected. |
| Readable hold | PASS | `snapshots/acceptance/frame-06-at-1.95s.png`, `review/animation-map-v1/animation-map.json` | Foreground evidence remains static from 1.60s to 2.18s. |
| Semantic transition midpoint | PASS | `snapshots/acceptance/frame-07-at-2.35s.png` | The evidence remains readable while the validation world enters; there is no empty reset. |
| Animation map | PASS | `review/animation-map-v1/animation-map.json` | 9 mapped tweens, no dead zones; two scene-container offscreen flags are the explicit 2.20–2.60s handoff. |
| Montage contact sheet | PASS | `review/executor-contact-sheet-v1.png` | Progression is visible without reading captions. |
| Full internal preview | PASS | `renders/internal-preview-v1.mp4`, `review/motion-watch-v1.md` | Full preview watched and all 120 frames decoded. |
| Anti-PPT / AI-tell hard gate | PASS | `review/executor-contact-sheet-v1.png`, `review/motion-watch-v1.md` | No repeated generic entrance, ambient foreground loop, unanchored decoration, generic AI filler, empty reset or unreadable midpoint. |
| Formal release render | NOT_APPLICABLE | `inputs/制作规格.md`, this report | Deferred; this unit stops at reviewed preview-v1. |

The only revision was MINOR-001. It returned to `proof-fixture-executor`; only the affected check/snapshot/render proof was rerun.
