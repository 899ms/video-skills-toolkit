# Video Skills Toolkit

这是一套面向自媒体视频创作的 Agent Skills 工具包。当前版本围绕“爆款拆解 → 配音与字幕 → 导演稿 → HyperFrames 口播成片 → 抖音封面”重新组织，不再包含旧的 `talking-head-remotion` 和 `sketch-story-remotion`。

## Seven Core Skills

| Skill | Responsibility |
|---|---|
| [`viral-video-benchmark`](skills/viral-video-benchmark/) | 扫描抖音/小红书账号近期作品，用确定性规则判断爆款，建立证据包，拆解并归档。 |
| [`minimax-voice-director`](skills/minimax-voice-director/) | 为锁定逐字稿制作可审批的 MiniMax 声音导演稿，生成、选 Take 并发布最终人声。 |
| [`audio-to-subtitles`](skills/audio-to-subtitles/) | 把最终音频/视频转成 SRT、VTT 和对齐 JSON；也保留轻量 MiniMax TTS 兼容入口。 |
| [`video-script`](skills/video-script/) | 使用锁定音频和字幕生成管线无关的导演契约、Beat Graph、制作规格和 motion contract。 |
| [`talking-head-hyperframes`](skills/talking-head-hyperframes/) | 生成并验证 HyperFrames 口播项目的固定舞台、PIP、输入归档、manifest 与执行交接。 |
| [`hyperframes-scene-animator`](skills/hyperframes-scene-animator/) | 实现逐镜静态页、语义动效、转场、声音 cue、proof 和预览审查闭环。 |
| [`douyin-cover`](skills/douyin-cover/) | 诊断、生成和改版抖音、视频号、小红书等平台的短视频封面。 |

## Workflow

```text
viral-video-benchmark
  → 选题与已确认逐字稿
  → minimax-voice-director
  → audio-to-subtitles
  → video-script
  → talking-head-hyperframes
  → hyperframes-scene-animator
  → douyin-cover
```

关键边界：

- `viral-video-benchmark` 负责找对标、判断、证据和拆解，不自动生成二创成稿。
- 正式配音前必须有已确认的逐字稿；本工具包不把“边写稿边做分镜”当作正式流程。
- `minimax-voice-director` 产出并审批最终人声；`audio-to-subtitles` 只从定稿音频建立时间轴。
- `video-script` 只做导演规划，不写场景代码。
- `talking-head-hyperframes` 只建固定舞台与执行交接；真正的镜头实现属于 `hyperframes-scene-animator`。
- `douyin-cover` 在标题与发布方向锁定后执行，可与成片收尾并行。

## Install

克隆仓库：

```bash
git clone https://github.com/bozhouDev/video-skills-toolkit.git
cd video-skills-toolkit
```

将 7 个目录保持为同级兄弟目录，复制到你的 Agent Skill 根目录。例如：

```bash
mkdir -p ~/.agents/skills
cp -R skills/* ~/.agents/skills/
```

也可放入项目级 `.agents/skills/`、`.claude/skills/` 或当前 Agent 平台的对应 Skill 目录。不要只复制单个 `SKILL.md`；脚本、references、assets 和测试夹具都是包的一部分。

## Runtime Requirements

| Area | Requirements |
|---|---|
| HyperFrames | Node.js, `npx`, FFmpeg/FFprobe, Chrome/Chromium；模板当前固定使用 `hyperframes@0.7.65` |
| MiniMax voice | Python 3, `requests`, `PyYAML`, FFmpeg/FFprobe, `MINIMAX_API_KEY`, `MINIMAX_VOICE_ID` |
| Subtitles | Bun/Node.js, MediaKit API 凭证；本地文件上传还需 Cloudflare R2 凭证 |
| Viral benchmark | 可读取已登录抖音/小红书页面的浏览器自动化能力 |
| Cover generation | 当前 Agent 环境中的 `imagegen` / `image_gen` 能力 |

还会按需路由到下列外部 Skills，它们不计入本仓库的 7 个核心 Skill：

- HyperFrames 基础能力：`hyperframes`、`hyperframes-core`、`hyperframes-animation`、`hyperframes-cli`。
- 爆款证据采集：`computer-use`、`media-to-transcript`、`hook-writing`、`obsidian-bases`。
- 封面生成：`imagegen`。
- 音乐任务：`minimax-music-gen`（可选）。

## Verification

```bash
# HyperFrames template factory
node skills/talking-head-hyperframes/scripts/test_scaffold.mjs

# HyperFrames executor contracts and proof pipeline
node skills/hyperframes-scene-animator/scripts/test_contract_adapter.mjs
node skills/hyperframes-scene-animator/scripts/test_proof_pipeline.mjs

# MiniMax voice workflow
python3 -m unittest discover \
  -s skills/minimax-voice-director/tests -p 'test_*.py'

# Viral benchmark scoring and evidence contracts
python3 -m unittest discover \
  -s skills/viral-video-benchmark/tests -p 'test_*.py'
```

这些测试不会调用真实 MiniMax API、写入平台数据或发布作品。HyperFrames proof 测试会读取仓库内的已锁定小型夹具。

## Public Repository Safety

- 不提交 API Key、Cookie、`.env` 或平台登录信息。
- 文档和可执行代码使用 `<VIDEO_WORKSPACE>`、`<SKILL_ROOT>`、`<NOTES_VAULT>` 等占位符，不依赖创作者本机路径。
- `douyin-cover/assets/` 中的泊舟 IP 图像是该 Skill 的创作者身份参考；其他创作者使用时应替换为自己有权使用的参考图，并同步修改 `references/ip-persona.md`。
- 字体不适用根目录 MIT License；详见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

## License

代码与文档使用 [MIT License](LICENSE)。内置字体保留原 SIL Open Font License 1.1。
