# Template Handoff

- Project: HyperFrames proof fixture
- Status: `READY_FOR_EXECUTION`
- Duration: `4s` at `30fps`
- Fixed stage: `studio-warm-white-fixed-stage-v3` (background / content / caption / voice)
- PIP contract: frame `206px @ right 104 / bottom 150`; media `190px @ right 112 / bottom 158`; crop `66.7% 50%`; background `opaque #f2f6f8`.
- DESIGN.md: `f0b16ac642540fcb646a9e4a4813e6e707f45dc92cb9dce4d040298caeccff63`
- Content motion default: `none`; global scene transition: `none`.

## Locked inputs

| Input | Project path | SHA-256 | Source path |
|---|---|---|---|
| Director script | `inputs/视频脚本.md` | `f4da87e28a69affde92067471c3322efd9602f650b63829f191e16c9645daf95` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/inputs/视频脚本.md` |
| Production spec | `inputs/制作规格.md` | `6ac773a2da328a9aad5530362355c655249c372b16d0c9257b967df82aecf5de` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/inputs/制作规格.md` |
| Asset plan | `inputs/素材计划.md` | `24da6a7fb95a0573011a7b10458c14ab68b1c0e95e09bbe0947933bba8b06a24` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/inputs/素材计划.md` |
| Motion contract | `inputs/motion-contract.json` | `cb859f0bdf466d23493ab70f7b850f37eae6f60094973979d2d26e381fefb0c6` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/inputs/motion-contract.json` |
| Voice audio | `assets/audio/voice/voice.mp3` | `bb26c05f469233f15412d1f6fc0ebc15bc69d380b3cee07b8db89b2ba29ee33f` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/assets/audio/voice/voice.mp3` |
| Aligned captions | `inputs/captions/captions_aligned.json` | `967d3e26c3c89aa6d6dcd5a131c8babb0a7ee24007f91170795e19a9bcc0c1ea` | `/Users/bozhou/my/视频工程/.claude/skills/hyperframes-scene-animator/evals/fixtures/ready-project/inputs/captions/captions_aligned.json` |
| SRT captions | MISSING | — | — |
| VTT captions | MISSING | — | — |
| Talking-head video | MISSING | — | — |

## Fixed boundary

The factory owns the fixed background, root mounts, caption overlay, optional stable PIP, voice mount, DESIGN.md, manifest, and template checks. `content.html`, `compositions/scenes/`, semantic motion, transitions, sound design, proof, and review execution belong downstream.

## Next step

Invoke `hyperframes-scene-animator`. It is the sole owner of shot implementation, scene motion, transitions, sound, proof, review, and revisions.
