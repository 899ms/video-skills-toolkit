# Lead review v1

## Four passes

| Pass | Status | Required evidence | Review result |
| --- | --- | --- | --- |
| Montage | PASS | `review/executor-contact-sheet-v1.png` | Reviewed only the ordered contact sheet without reading captions. The film progresses from question → source trace → readable proof → anchored transfer → validator lock, rather than resetting as PPT pages. |
| Static | PASS | `snapshots/acceptance/`, `review/cli/inspect.txt` | Composition, typography, real hash evidence, single-line captions and safe areas hold at every acceptance state. PIP is explicitly not applicable. |
| Motion | PASS | `renders/internal-preview-v1.mp4`, `review/motion-watch-v1.md` | The full preview was watched. Motion changes state, pauses for reading, keeps a readable transition midpoint and lands with the voice. Static frames were not used as a substitute. |
| Delivery | PASS | `review/cli/check.txt`, `review/media-analysis-v1.json`, `review/media/full-watch-decode.txt` | Assets resolve; output is decodable 1920×1080 at 30fps with voice through the ending and no black/silent tail. |

## Anti-PPT / AI-tell gate

| Rejection | Status | Evidence |
| --- | --- | --- |
| Repeated generic entrance | PASS | `review/animation-map-v1/animation-map.json` |
| Decorative continuous foreground motion | PASS | `runtime-adaptation.json`, `review/animation-map-v1/animation-map.json` |
| Unanchored connector or decoration | PASS | `compositions/content.html`, `snapshots/acceptance/frame-03-at-1.42s.png` |
| Generic AI filler | PASS | `review/executor-contact-sheet-v1.png` |
| Empty reset transition | PASS | `snapshots/acceptance/frame-07-at-2.35s.png` |
| Unreadable transition midpoint | PASS | `snapshots/acceptance/frame-07-at-2.35s.png` |

## Findings and closure

| Severity | Status | Time | Evidence | Required fix | Owner | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| MINOR | CLOSED | Static gate | `review/rechecks/minor-001-contrast.md` | Raise small label contrast without changing fixed-stage identity. | `proof-fixture-executor` | PASS — `review/cli/check.txt` |

No open BLOCKER, MAJOR, or first-impression-blocking MINOR remains. Preview-v1 promotion is approved; formal release remains deferred.
