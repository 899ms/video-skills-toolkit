import type {CSSProperties, ReactNode} from "react";
import {Audio, Video} from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {colors, fonts, layout} from "./theme";
import {BlurredImageCard} from "./BlurredImageCard";

type Tone = "accent" | "white" | "muted";

export type RichTextPart = {
  text: string;
  tone?: Tone;
};

export type Chapter = {
  label: string;
  start: number;
};

export type Caption = {
  start: number;
  end: number;
  parts: RichTextPart[];
};

export type SfxCue = {
  id: string;
  start: number;
  duration: number;
  file: string;
  volume: number;
};

type CoverScene = {
  kind: "cover";
  start: number;
  eyebrow: string;
  titleLines: RichTextPart[][];
  subtitle: string;
};

type ListScene = {
  kind: "list";
  start: number;
  eyebrow: string;
  heading: string;
  items: Array<{
    index: string;
    label: string;
    value: string;
    tone?: Tone;
    /** 进场时刻（场景内相对秒数），来自口播说到该行内容的字幕起点 */
    appearAt?: number;
  }>;
};

type StatScene = {
  kind: "stat";
  start: number;
  eyebrow: string;
  number: string;
  unit: string;
  title: RichTextPart[];
  metrics: Array<{
    label: string;
    value: string;
    tone?: Tone;
    /** 进场时刻（场景内相对秒数），来自口播说到该指标的字幕起点 */
    appearAt?: number;
  }>;
};

type CompareScene = {
  kind: "compare";
  start: number;
  eyebrow: string;
  heading: string;
  choices: Array<{
    code: string;
    title: string;
    subtitle: string;
    tone?: Tone;
    /** 进场时刻（场景内相对秒数），来自口播说到该选项的字幕起点 */
    appearAt?: number;
  }>;
};

type OutroScene = {
  kind: "outro";
  start: number;
  eyebrow: string;
  title: string;
  subtitle: string;
};

export type ImageScene = {
  kind: "image";
  start: number;
  /** public/ 目录下的相对路径，或者完整 URL */
  src: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  edgeBlur?: number;
  borderRadius?: number;
};

export type StudioScene = CoverScene | ListScene | StatScene | CompareScene | OutroScene | ImageScene;

export type StudioTalkingHeadProps = {
  title: string;
  fps: number;
  durationSeconds: number;
  voiceAudio?: string;
  talkingHeadVideo?: string;
  chapters: Chapter[];
  scenes: StudioScene[];
  captions: Caption[];
  sfxCues?: SfxCue[];
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const frameFromSeconds = (seconds: number, fps: number) => Math.round(seconds * fps);

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const progress = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: ease,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const enterStyle = (
  frame: number,
  fps: number,
  delaySeconds: number,
  durationSeconds: number,
  y: number,
): CSSProperties => {
  const p = progress(frame, delaySeconds * fps, durationSeconds * fps);
  return {
    opacity: p,
    transform: `translateY(${(1 - p) * y}px)`,
  };
};

const toneColor = (tone?: Tone) => {
  if (tone === "accent") {
    return colors.accent;
  }
  // 画布是浅色的，"white" 强调渲染为黑色加粗才可读
  if (tone === "white") {
    return colors.ink;
  }
  if (tone === "muted") {
    return colors.muted;
  }
  return colors.ink;
};

const RichText = ({
  parts,
  strong = false,
  preserveLineBreaks = false,
  defaultColor = colors.ink,
}: {
  parts: RichTextPart[];
  strong?: boolean;
  preserveLineBreaks?: boolean;
  defaultColor?: string;
}) => (
  <>
    {parts.map((part, index) => (
      <span
        key={`${part.text}-${index}`}
        style={{
          color: part.tone ? toneColor(part.tone) : defaultColor,
          fontWeight: part.tone || strong ? 700 : undefined,
          whiteSpace: preserveLineBreaks ? "pre-line" : undefined,
        }}
      >
        {part.text}
      </span>
    ))}
  </>
);

export const StudioTalkingHead = ({
  durationSeconds,
  voiceAudio,
  talkingHeadVideo,
  chapters,
  scenes,
  captions,
  sfxCues = [],
}: StudioTalkingHeadProps) => {
  const {fps} = useVideoConfig();
  const transitionFrames = Math.round(0.42 * fps);

  return (
    <AbsoluteFill style={stageStyle}>
      <FlutedGlassBackground />
      {voiceAudio ? <Audio src={staticFile(voiceAudio)} volume={1} /> : null}
      {sfxCues.map((cue) => (
        <Sequence
          key={cue.id}
          from={frameFromSeconds(cue.start, fps)}
          durationInFrames={Math.max(1, frameFromSeconds(cue.duration, fps))}
          premountFor={fps}
        >
          <Audio src={staticFile(cue.file)} volume={cue.volume} />
        </Sequence>
      ))}
      {scenes.map((scene, index) => {
        const nextStart = scenes[index + 1]?.start ?? durationSeconds;
        const sceneStart = frameFromSeconds(scene.start, fps);
        const baseDuration = frameFromSeconds(nextStart - scene.start, fps);
        const isLast = index === scenes.length - 1;
        const durationInFrames = Math.max(1, baseDuration + (isLast ? 0 : transitionFrames));
        return (
          <Sequence
            key={`${scene.kind}-${scene.start}`}
            from={sceneStart}
            durationInFrames={durationInFrames}
            premountFor={fps}
          >
            <SceneRenderer scene={scene} durationInFrames={durationInFrames} isLast={isLast} />
          </Sequence>
        );
      })}
      <PipFrame talkingHeadVideo={talkingHeadVideo} />
      <CaptionLayer captions={captions} />
      <TopBar chapters={chapters} durationSeconds={durationSeconds} />
    </AbsoluteFill>
  );
};

// 「乳白瓦楞玻璃」背景：暖桃光晕在瓦楞玻璃（fluted glass）后缓慢漂移，
// 静谧展厅质感——彻底取代旧版上下双层镜像透视网格。
const FlutedGlassBackground = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;

  return (
    <AbsoluteFill style={premiumBackgroundStyle}>
      {/* 底层：乳白渐变 + 淡紫/冰蓝角落呼吸 */}
      <AbsoluteFill style={ambientWashStyle(seconds)} />
      {/* 暖桃光团：藏在两侧玻璃后面，缓慢漂移与呼吸 */}
      <div style={warmGlowStyle(seconds, "left")} />
      <div style={warmGlowStyle(seconds, "right")} />
      {/* 左右两排竖向瓦楞玻璃棱线：棱线本身持续横向流动，是最直观的动效 */}
      <div style={flutedPanelStyle("left", seconds)} />
      <div style={flutedPanelStyle("right", seconds)} />
      {/* 高光扫带：一条柔焦对角光带缓慢横扫全屏，是主要的"看得出在动"的动效 */}
      <div style={lightSweepStyle(seconds)} />
      {/* 漂浮光斑：几颗大而柔的玻璃光斑缓慢上浮漂移，增加空气感 */}
      {bokehOrbs.map((orb, index) => (
        <div key={index} style={bokehOrbStyle(orb, seconds)} />
      ))}
      {/* 中央留白帷幕：保证字幕与内容区可读性 */}
      <AbsoluteFill style={centerVeilStyle} />
      {/* 细噪点：消除渐变色带，增加胶片质感 */}
      <AbsoluteFill style={grainStyle(seconds)} />
    </AbsoluteFill>
  );
};

const SceneRenderer = ({
  scene,
  durationInFrames,
  isLast,
}: {
  scene: StudioScene;
  durationInFrames: number;
  isLast: boolean;
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = progress(frame, 0, 0.42 * fps);
  const exit = isLast ? 0 : progress(frame, durationInFrames - 0.42 * fps, 0.42 * fps);
  const opacity = clamp(enter - exit, 0, 1);

  return (
    <AbsoluteFill style={{...sceneShellStyle, opacity}}>
      {scene.kind === "cover" ? <CoverSceneView scene={scene} /> : null}
      {scene.kind === "list" ? <ListSceneView scene={scene} /> : null}
      {scene.kind === "stat" ? <StatSceneView scene={scene} /> : null}
      {scene.kind === "compare" ? <CompareSceneView scene={scene} /> : null}
      {scene.kind === "outro" ? <OutroSceneView scene={scene} /> : null}
      {scene.kind === "image" ? <ImageSceneView scene={scene} /> : null}
    </AbsoluteFill>
  );
};

const ImageSceneView = ({scene}: {scene: ImageScene}) => (
  <div style={{...sceneContentStyle, alignItems: "center", justifyContent: "center"}}>
    <BlurredImageCard
      src={scene.src}
      alt={scene.alt}
      width={scene.width}
      height={scene.height}
      edgeBlur={scene.edgeBlur}
      borderRadius={scene.borderRadius}
    />
  </div>
);

const Eyebrow = ({children, style}: {children: ReactNode; style?: CSSProperties}) => (
  <div style={{...eyebrowStyle, ...style}}>
    <span style={eyebrowRuleStyle} />
    <span>{children}</span>
  </div>
);

const CoverSceneView = ({scene}: {scene: CoverScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{...sceneContentStyle, justifyContent: "center"}}>
      <Eyebrow style={enterStyle(frame, fps, 0.14, 0.42, 18)}>{scene.eyebrow}</Eyebrow>
      <h1 style={{...coverTitleStyle, ...enterStyle(frame, fps, 0.25, 0.56, 42)}}>
        {scene.titleLines.map((line, index) => (
          <span key={index} style={{display: "block"}}>
            <RichText parts={line} strong />
          </span>
        ))}
      </h1>
      <div style={{...subtitleStyle, ...enterStyle(frame, fps, 0.52, 0.44, 24)}}>{scene.subtitle}</div>
    </div>
  );
};

const ListSceneView = ({scene}: {scene: ListScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{...sceneContentStyle, ...splitLayoutStyle}}>
      <div style={sectionTitleRailStyle}>
        <span style={{...smallRuleStyle, ...scaleXStyle(frame, fps, 0.1, 0.28)}} />
        <div style={{...sectionLabelStyle, ...enterStyle(frame, fps, 0.16, 0.34, 16)}}>{scene.eyebrow}</div>
        <div style={{...sectionHeadingStyle, ...enterStyle(frame, fps, 0.24, 0.44, 28)}}>{scene.heading}</div>
      </div>
      <div style={rowsStyle}>
        {scene.items.map((item, index) => (
          <div key={item.index} style={{...rowStyle, ...enterStyle(frame, fps, item.appearAt ?? 0.28 + index * 0.1, 0.38, 24)}}>
            <span style={rowIndexStyle}>{item.index}</span>
            <span style={rowLabelStyle}>{item.label}</span>
            <span style={{...rowValueStyle, color: toneColor(item.tone)}}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const StatSceneView = ({scene}: {scene: StatScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{...sceneContentStyle, ...statLayoutStyle}}>
      <div style={bigStatStyle}>
        <div style={{...sectionLabelStyle, ...enterStyle(frame, fps, 0.08, 0.34, 0)}}>{scene.eyebrow}</div>
        <div style={{...statNumberWrapStyle, ...enterStyle(frame, fps, 0.16, 0.48, 34)}}>
          <span style={statNumberStyle}>{scene.number}</span>
          <span style={statUnitStyle}>{scene.unit}</span>
        </div>
        <span style={{...statRuleStyle, ...scaleXStyle(frame, fps, 0.48, 0.32)}} />
      </div>
      <div style={{...statDetailStyle, ...enterStyle(frame, fps, 0.28, 0.48, 0)}}>
        <div style={detailTitleStyle}>
          <RichText parts={scene.title} strong preserveLineBreaks />
        </div>
        <div style={miniStatsStyle}>
          {scene.metrics.map((metric, index) => (
            <div key={metric.label} style={{...miniRowStyle, ...enterStyle(frame, fps, metric.appearAt ?? 0.52 + index * 0.08, 0.28, 18)}}>
              <span>{metric.label}</span>
              <span style={{color: toneColor(metric.tone), fontFamily: fonts.mono}}>{metric.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const CompareSceneView = ({scene}: {scene: CompareScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{...sceneContentStyle, justifyContent: "flex-start"}}>
      <span style={{...smallRuleStyle, ...scaleXStyle(frame, fps, 0.1, 0.28)}} />
      <div style={{...sectionLabelStyle, ...enterStyle(frame, fps, 0.16, 0.34, 16)}}>{scene.eyebrow}</div>
      <div style={{...sectionHeadingStyle, fontSize: 88, ...enterStyle(frame, fps, 0.24, 0.44, 28)}}>{scene.heading}</div>
      <div style={compareGridStyle}>
        {scene.choices.map((choice, index) => (
          <div key={choice.code} style={{...choiceStyle(index), ...enterStyle(frame, fps, choice.appearAt ?? 0.38 + index * 0.12, 0.44, 28)}}>
            <span style={{...choiceCodeStyle, color: toneColor(choice.tone)}}>{choice.code}</span>
            <div style={choiceTitleStyle}>{choice.title}</div>
            <div style={choiceSubtitleStyle}>{choice.subtitle}</div>
          </div>
        ))}
        <div style={{...dividerStyle, ...scaleYStyle(frame, fps, 0.34, 0.36)}} />
      </div>
    </div>
  );
};

const OutroSceneView = ({scene}: {scene: OutroScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{...sceneContentStyle, alignItems: "center", justifyContent: "center", textAlign: "center"}}>
      <span style={{...outroRuleStyle, ...scaleXStyle(frame, fps, 0.08, 0.3)}} />
      <div style={{...sectionLabelStyle, ...enterStyle(frame, fps, 0.16, 0.34, 16)}}>{scene.eyebrow}</div>
      <div style={{...outroTitleStyle, ...enterStyle(frame, fps, 0.24, 0.5, 34)}}>{scene.title}</div>
      <div style={{...outroSubtitleStyle, ...enterStyle(frame, fps, 0.48, 0.4, 22)}}>{scene.subtitle}</div>
    </div>
  );
};

const CaptionLayer = ({captions}: {captions: Caption[]}) => {
  return (
    <AbsoluteFill style={captionLayerStyle}>
      {captions.map((caption, index) => (
        <CaptionPill key={`${caption.start}-${index}`} caption={caption} />
      ))}
    </AbsoluteFill>
  );
};

const CaptionPill = ({caption}: {caption: Caption}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const start = frameFromSeconds(caption.start, fps);
  const end = frameFromSeconds(caption.end, fps);

  if (frame < start - 1 || frame > end) {
    return null;
  }

  const enter = progress(frame, start, 0.16 * fps);
  const exit = progress(frame, Math.max(start, end - 0.12 * fps), 0.12 * fps);
  const visible = clamp(enter - exit, 0, 1);

  return (
    <div
      style={{
        ...captionStyle,
        opacity: visible,
        transform: `translate(-50%, ${(1 - visible) * 18}px) scale(${0.98 + visible * 0.02})`,
      }}
    >
      <RichText parts={caption.parts} defaultColor={colors.ink} />
    </div>
  );
};

// PIP 头像：悬浮圆形玻璃卡——磨砂白包边 + 上下轻浮动，
// 影子随浮动反向缩放，强化"悬在页面上方"的感觉
const PipFrame = ({talkingHeadVideo}: {talkingHeadVideo?: string}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;
  const p = progress(frame, 0.7 * fps, 0.45 * fps);
  // 悬浮动画：约 4.2 秒一个起伏周期
  const bob = Math.sin(seconds * 1.5);
  const floatY = bob * 7;
  // 卡片浮得越高，影子越大越淡（视差暗示高度）
  const shadowLift = (1 - bob) * 0.5;

  return (
    <div
      style={{
        ...pipFrameStyle,
        opacity: p,
        transform: `translateX(${(1 - p) * 18}px) translateY(${floatY}px) scale(${0.9 + p * 0.1})`,
        boxShadow: `0 ${26 + shadowLift * 16}px ${58 + shadowLift * 26}px rgba(31,38,68,${0.2 - shadowLift * 0.06}), 0 4px 14px rgba(31,38,68,0.08)`,
      }}
    >
      <div style={pipInnerStyle}>
        <div style={pipMaskStyle}>
          {talkingHeadVideo ? (
            <Video
              src={staticFile(talkingHeadVideo)}
              muted
              style={{
                width: 366,
                height: 206,
                transform: "translateX(-80px)",
                objectFit: "cover",
              }}
            />
          ) : (
            <AvatarPlaceholder />
          )}
        </div>
      </div>
    </div>
  );
};

const AvatarPlaceholder = () => (
  <div style={avatarWrapStyle}>
    <div style={avatarHeadStyle} />
    <div style={avatarBodyStyle} />
  </div>
);

const TopBar = ({chapters, durationSeconds}: {chapters: Chapter[]; durationSeconds: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const progressWidth = interpolate(time, [0, durationSeconds], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const currentChapterIndex = chapters.reduce((activeIndex, chapter, index) => (time >= chapter.start ? index : activeIndex), 0);
  const renderChapterLabels = (
    colorForChapter: (index: number) => string,
    weightForChapter: (index: number) => number = () => 600,
  ) => (
    <>
      {chapters.map((chapter, index) => {
        const centerPct = ((index + 0.5) / chapters.length) * 100;
        return (
          <span
            key={chapter.label}
            style={{
              ...chapterLabelStyle,
              left: `${centerPct}%`,
              color: colorForChapter(index),
              fontWeight: weightForChapter(index),
            }}
          >
            {chapter.label}
          </span>
        );
      })}
      {chapters.slice(0, -1).map((chapter, index) => (
        <span key={`${chapter.label}-boundary`} style={{...chapterBoundaryStyle, left: `${((index + 1) / chapters.length) * 100}%`}}>
          |
        </span>
      ))}
    </>
  );

  return (
    <div style={topbarStyle}>
      <div style={chapterTrackStyle}>
        {renderChapterLabels(
          (index) => (index === currentChapterIndex ? colors.ink : colors.topbarMuted),
          (index) => (index === currentChapterIndex ? 700 : 500),
        )}
      </div>
      <div style={{...navFillStyle, width: `${progressWidth}%`}} />
      <div style={{...filledChapterMaskStyle, width: `${progressWidth}%`}}>
        <div style={filledChapterTrackStyle}>{renderChapterLabels(() => colors.white, () => 600)}</div>
      </div>
    </div>
  );
};

const scaleXStyle = (frame: number, fps: number, delaySeconds: number, durationSeconds: number): CSSProperties => ({
  transform: `scaleX(${progress(frame, delaySeconds * fps, durationSeconds * fps)})`,
  transformOrigin: "left center",
});

const scaleYStyle = (frame: number, fps: number, delaySeconds: number, durationSeconds: number): CSSProperties => ({
  transform: `scaleY(${progress(frame, delaySeconds * fps, durationSeconds * fps)})`,
  transformOrigin: "center center",
});

const stageStyle: CSSProperties = {
  backgroundColor: colors.canvas,
  color: colors.ink,
  fontFamily: fonts.sans,
  overflow: "hidden",
};

const premiumBackgroundStyle: CSSProperties = {
  backgroundColor: colors.canvas,
  pointerEvents: "none",
  overflow: "hidden",
};

// 底层乳白渐变：中间偏暖白、四角淡紫/冰蓝极浅呼吸（缓慢漂移）
const ambientWashStyle = (seconds: number): CSSProperties => ({
  background: [
    `radial-gradient(900px 640px at ${16 + Math.sin(seconds * 0.2) * 3}% ${86 + Math.cos(seconds * 0.17) * 3}%, ${colors.lilac}, transparent 68%)`,
    `radial-gradient(860px 600px at ${86 + Math.cos(seconds * 0.18) * 3}% ${12 + Math.sin(seconds * 0.16) * 3}%, ${colors.iceBlue}, transparent 66%)`,
    "linear-gradient(165deg, #fafafc 0%, #f1f1f6 44%, #f6f4f4 100%)",
  ].join(", "),
});

// 暖桃光团：模拟透过玻璃渗出来的暖橙光，左右各一团、相位错开
const warmGlowStyle = (seconds: number, side: "left" | "right"): CSSProperties => {
  const phase = side === "left" ? 0 : 2.4; // 两侧呼吸错开，避免同频闪烁感
  const breathe = 0.72 + Math.sin(seconds * 0.42 + phase) * 0.28;
  const drift = Math.sin(seconds * 0.2 + phase) * 130;
  return {
    position: "absolute",
    top: side === "left" ? 40 + drift : undefined,
    bottom: side === "right" ? 60 - drift : undefined,
    [side]: -180,
    width: 980,
    height: 860,
    borderRadius: "50%",
    background: `radial-gradient(closest-side, ${colors.glow}, rgba(255,188,138,0.22) 52%, transparent 76%)`,
    opacity: breathe,
    filter: "blur(4px)",
  };
};

// 竖向瓦楞玻璃板：重复渐变模拟棱线明暗，棱线随时间持续横向流动（外侧向内滚动），
// backdrop blur 把身后的光团折射成柔焦光带，mask 让棱线向画面中心渐隐
const flutedPanelStyle = (side: "left" | "right", seconds: number): CSSProperties => {
  const fade = side === "left" ? "to right" : "to left";
  // 两侧向相反方向流动，速度约 22px/s，肉眼可明确感知
  const flow = seconds * 22 * (side === "left" ? 1 : -1);
  return {
    position: "absolute",
    top: 0,
    bottom: 0,
    [side]: 0,
    width: 470,
    background: [
      `repeating-linear-gradient(90deg, rgba(255,255,255,0) 0px, rgba(255,255,255,0.72) 16px, rgba(172,176,198,0.34) 34px, rgba(255,255,255,0.14) 46px, rgba(255,255,255,0) 52px)`,
    ].join(", "),
    backgroundPosition: `${flow}px 0`,
    backdropFilter: "blur(26px) saturate(1.2)",
    WebkitBackdropFilter: "blur(26px) saturate(1.2)",
    maskImage: `linear-gradient(${fade}, rgba(0,0,0,0.9), rgba(0,0,0,0.55) 55%, transparent 100%)`,
    WebkitMaskImage: `linear-gradient(${fade}, rgba(0,0,0,0.9), rgba(0,0,0,0.55) 55%, transparent 100%)`,
  };
};

// 高光扫带：一条倾斜的柔焦白光带，约 11 秒横扫一次全屏（含屏外余量）
const lightSweepStyle = (seconds: number): CSSProperties => {
  const period = 11; // 一轮扫过的周期（秒）
  const progressValue = (seconds % period) / period;
  const x = -900 + progressValue * 3700; // 从屏左外扫到屏右外
  return {
    position: "absolute",
    top: -200,
    bottom: -200,
    left: x,
    width: 720,
    background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.85) 42%, rgba(255,214,178,0.6) 58%, transparent)",
    transform: "rotate(14deg)",
    filter: "blur(26px)",
    opacity: 0.75,
    mixBlendMode: "soft-light",
  };
};

// 漂浮光斑参数：大小/水平位置/相位/漂速各不相同（写死避免随机数破坏渲染确定性）
const bokehOrbs = [
  {size: 190, x: 12, phase: 0.0, speed: 0.075, opacity: 0.72},
  {size: 120, x: 26, phase: 2.1, speed: 0.1, opacity: 0.58},
  {size: 240, x: 72, phase: 4.2, speed: 0.065, opacity: 0.62},
  {size: 100, x: 86, phase: 1.3, speed: 0.115, opacity: 0.54},
  {size: 150, x: 55, phase: 3.4, speed: 0.085, opacity: 0.46},
];

// 漂浮光斑：柔焦玻璃泡缓慢上浮 + 轻微左右摆动，循环往复
const bokehOrbStyle = (orb: (typeof bokehOrbs)[number], seconds: number): CSSProperties => {
  const travel = 1080 + orb.size * 2; // 从屏下浮到屏上的总行程
  const y = 1080 + orb.size - ((seconds * orb.speed * travel + orb.phase * 300) % travel);
  const sway = Math.sin(seconds * 0.4 + orb.phase) * 26;
  return {
    position: "absolute",
    left: `calc(${orb.x}% + ${sway}px)`,
    top: y,
    width: orb.size,
    height: orb.size,
    borderRadius: "50%",
    background: "radial-gradient(circle at 34% 30%, rgba(255,255,255,0.75), rgba(255,255,255,0.16) 58%, transparent 74%)",
    boxShadow: "inset 0 0 30px rgba(255,255,255,0.35)",
    filter: "blur(7px)",
    opacity: orb.opacity,
  };
};

// 中央留白帷幕：让字幕/内容区落在干净的乳白上
const centerVeilStyle: CSSProperties = {
  background: "linear-gradient(180deg, transparent 0%, rgba(244,244,247,0.08) 16%, rgba(244,244,247,0.82) 37%, rgba(244,244,247,0.92) 50%, rgba(244,244,247,0.82) 63%, rgba(244,244,247,0.08) 84%, transparent 100%)",
};

const grainStyle = (seconds: number): CSSProperties => ({
  opacity: 0.045,
  backgroundImage: "radial-gradient(rgba(31,36,48,0.35) 0.7px, transparent 0.7px)",
  backgroundSize: "4px 4px",
  backgroundPosition: `${Math.round(seconds * 3) % 4}px ${Math.round(seconds * 2) % 4}px`,
});

const sceneShellStyle: CSSProperties = {
  padding: `${layout.safeTop}px ${layout.safeX}px ${layout.safeBottom}px`,
};

const sceneContentStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  display: "flex",
  flexDirection: "column",
};

const eyebrowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 20,
  marginBottom: 40,
  color: colors.accent,
  fontFamily: fonts.mono,
  fontSize: 24,
  fontWeight: 600,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const eyebrowRuleStyle: CSSProperties = {
  width: 52,
  height: 2,
  backgroundColor: colors.accent,
  flex: "none",
};

const coverTitleStyle: CSSProperties = {
  maxWidth: 1400,
  margin: 0,
  color: colors.ink,
  fontSize: 112,
  fontWeight: 800,
  lineHeight: 1.14,
  letterSpacing: 0,
};

const subtitleStyle: CSSProperties = {
  marginTop: 46,
  color: colors.muted,
  fontSize: 38,
  fontWeight: 300,
  letterSpacing: 0,
};

const splitLayoutStyle: CSSProperties = {
  flexDirection: "row",
  alignItems: "center",
  gap: 100,
};

const sectionTitleRailStyle: CSSProperties = {
  width: 420,
  flex: "none",
};

const smallRuleStyle: CSSProperties = {
  width: 48,
  height: 2,
  backgroundColor: colors.accent,
  display: "block",
  marginBottom: 30,
};

const sectionLabelStyle: CSSProperties = {
  color: colors.accent,
  fontFamily: fonts.mono,
  fontSize: 24,
  fontWeight: 600,
  letterSpacing: 0,
  textTransform: "uppercase",
  marginBottom: 20,
};

const sectionHeadingStyle: CSSProperties = {
  color: colors.ink,
  fontSize: 96,
  fontWeight: 800,
  lineHeight: 1.08,
  letterSpacing: 0,
};

const rowsStyle: CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
};

const rowStyle: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: 46,
  padding: "42px 0",
  borderTop: `1px solid ${colors.line}`,
};

const rowIndexStyle: CSSProperties = {
  width: 74,
  flex: "none",
  color: colors.weak,
  fontFamily: fonts.mono,
  fontSize: 40,
  fontWeight: 500,
};

const rowLabelStyle: CSSProperties = {
  width: 150,
  flex: "none",
  color: colors.muted,
  fontSize: 27,
  fontWeight: 400,
  letterSpacing: 0,
};

const rowValueStyle: CSSProperties = {
  color: colors.ink,
  fontSize: 56,
  fontWeight: 600,
  lineHeight: 1.2,
};

const statLayoutStyle: CSSProperties = {
  flexDirection: "row",
  alignItems: "center",
  gap: 110,
};

const bigStatStyle: CSSProperties = {
  flex: "none",
};

const statNumberWrapStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
};

const statNumberStyle: CSSProperties = {
  color: colors.ink,
  fontFamily: fonts.mono,
  fontSize: 420,
  fontWeight: 700,
  lineHeight: 0.82,
  letterSpacing: 0,
};

const statUnitStyle: CSSProperties = {
  marginTop: 54,
  color: colors.muted,
  fontFamily: fonts.mono,
  fontSize: 72,
  fontWeight: 500,
};

const statRuleStyle: CSSProperties = {
  display: "block",
  width: 380,
  height: 3,
  marginTop: 6,
  backgroundColor: colors.accent,
};

const statDetailStyle: CSSProperties = {
  flex: 1,
  borderLeft: `1px solid ${colors.line}`,
  padding: "18px 0 18px 88px",
};

const detailTitleStyle: CSSProperties = {
  color: colors.ink,
  fontSize: 54,
  fontWeight: 700,
  lineHeight: 1.28,
};

const miniStatsStyle: CSSProperties = {
  maxWidth: 540,
  marginTop: 48,
};

const miniRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  padding: "24px 0",
  borderTop: `1px solid ${colors.line}`,
  color: colors.muted,
  fontSize: 32,
};

const compareGridStyle: CSSProperties = {
  flex: 1,
  display: "grid",
  gridTemplateColumns: "1fr 1px 1fr",
  alignItems: "stretch",
  marginTop: 60,
};

const choiceStyle = (index: number): CSSProperties => ({
  gridColumn: index === 0 ? 1 : 3,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
  padding: index === 0 ? "12px 90px 12px 0" : "12px 0 12px 90px",
});

const choiceCodeStyle: CSSProperties = {
  color: colors.weak,
  fontFamily: fonts.mono,
  fontSize: 40,
  fontWeight: 600,
};

const choiceTitleStyle: CSSProperties = {
  margin: "16px 0 30px",
  color: colors.ink,
  fontSize: 84,
  fontWeight: 800,
  letterSpacing: 0,
};

const choiceSubtitleStyle: CSSProperties = {
  color: colors.muted,
  fontSize: 40,
  fontWeight: 300,
  letterSpacing: 0,
};

const dividerStyle: CSSProperties = {
  gridColumn: 2,
  width: 1,
  backgroundColor: colors.lineStrong,
};

const outroRuleStyle: CSSProperties = {
  width: 70,
  height: 2,
  backgroundColor: colors.accent,
  marginBottom: 38,
};

const outroTitleStyle: CSSProperties = {
  color: colors.ink,
  fontSize: 172,
  fontWeight: 800,
  lineHeight: 1,
  letterSpacing: 0,
};

const outroSubtitleStyle: CSSProperties = {
  marginTop: 42,
  color: colors.muted,
  fontSize: 40,
  fontWeight: 300,
  letterSpacing: 0,
};

const captionLayerStyle: CSSProperties = {
  zIndex: 100,
  pointerEvents: "none",
};

// 字幕：磨砂玻璃药丸底，保证在光晕/玻璃棱线上依然干净可读
const captionStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  bottom: layout.captionBottom,
  maxWidth: 1180,
  color: colors.ink,
  fontSize: 40,
  fontWeight: 500,
  lineHeight: 1.25,
  textAlign: "center",
  letterSpacing: 0,
  padding: "14px 38px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.58)",
  border: `1px solid ${colors.glassBorder}`,
  backdropFilter: "blur(18px)",
  WebkitBackdropFilter: "blur(18px)",
  boxShadow: "0 12px 36px rgba(31,38,68,0.08)",
};

// PIP 悬浮头像外框：圆形玻璃卡（阴影在组件内随浮动动态计算）
const pipFrameStyle: CSSProperties = {
  position: "absolute",
  right: layout.pipRight,
  bottom: layout.pipBottom,
  zIndex: 90,
  width: layout.pipSize,
  height: layout.pipSize,
  borderRadius: "50%",
};

// 白色玻璃包边层
const pipInnerStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  borderRadius: "50%",
  padding: 7,
  backgroundColor: "rgba(255,255,255,0.92)",
  border: `1px solid ${colors.glassBorder}`,
  overflow: "hidden",
};

const pipMaskStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  borderRadius: "50%",
  overflow: "hidden",
  background: "#dcdce2",
  display: "flex",
  alignItems: "flex-end",
  justifyContent: "center",
};

const avatarWrapStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "100%",
};

const avatarHeadStyle: CSSProperties = {
  position: "absolute",
  left: 75,
  top: 44,
  width: 56,
  height: 56,
  borderRadius: "50%",
  backgroundColor: "#a9a9a3",
};

const avatarBodyStyle: CSSProperties = {
  position: "absolute",
  left: 43,
  bottom: -16,
  width: 120,
  height: 88,
  borderRadius: "58px 58px 24px 24px",
  backgroundColor: "#a9a9a3",
};

// 顶栏：悬浮玻璃胶囊——不再贴边，四周留空 + 全圆角 + 悬浮阴影
const topbarStyle: CSSProperties = {
  position: "absolute",
  top: 18,
  left: 28,
  right: 28,
  height: layout.topbarHeight - 14,
  zIndex: 120,
  backgroundColor: colors.topbar,
  backdropFilter: "blur(20px) saturate(1.2)",
  WebkitBackdropFilter: "blur(20px) saturate(1.2)",
  border: `1px solid ${colors.glassBorder}`,
  borderRadius: 999,
  boxShadow: "0 14px 40px rgba(31,38,68,0.14), 0 2px 8px rgba(31,38,68,0.06)",
  overflow: "hidden",
};

// 进度填充：墨色胶囊，跟随外框全圆角
const navFillStyle: CSSProperties = {
  position: "absolute",
  top: 6,
  bottom: 6,
  left: 6,
  zIndex: 2,
  backgroundColor: colors.ink,
  borderRadius: 999,
};

const chapterTrackStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  fontSize: 22,
  lineHeight: 1,
  whiteSpace: "nowrap",
  zIndex: 1,
};

const filledChapterMaskStyle: CSSProperties = {
  position: "absolute",
  top: 0,
  bottom: 0,
  left: 0,
  zIndex: 3,
  overflow: "hidden",
  pointerEvents: "none",
};

// 填充层轨道宽度 = 胶囊内宽（1920 - 左右各 28 边距），保证与底层文字逐像素对齐
const filledChapterTrackStyle: CSSProperties = {
  ...chapterTrackStyle,
  width: layout.width - 56,
  zIndex: 3,
};

const chapterLabelStyle: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translate(-50%, -50%)",
  fontWeight: 500,
  letterSpacing: 0,
  textAlign: "center",
};

const chapterBoundaryStyle: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translate(-50%, -50%)",
  color: colors.topbarSeparator,
};
