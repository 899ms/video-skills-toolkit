import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * BeforeAfterStat —— 前后数据对比镜头。
 *
 * 用法：复制到项目 src/library/，包在场景 <Sequence> 内；时间均为组件内相对秒数。
 * 先出现 before，再连接到 after，最后用 result 给出结论。
 * SFX 卡点：beforeAt / afterAt 适合轻 pop，resultAt 适合确认 beep。
 *
 * 适合：旧方法 vs 新方法、优化前后、时间/成本/错误率变化。
 * 不适合：三个以上对象的横向排名，或两侧指标口径不一致的比较。
 */
export type BeforeAfterStatTheme = {
  text: string;
  muted: string;
  weak: string;
  accent: string;
  warm: string;
  line: string;
  glass: string;
  glassStrong: string;
  glassBorder: string;
  shadow: string;
};

export type BeforeAfterStatProps = {
  title?: string;
  beforeLabel?: string;
  beforeValue?: string;
  afterLabel?: string;
  afterValue?: string;
  result?: string;
  titleAt?: number;
  beforeAt?: number;
  afterAt?: number;
  resultAt?: number;
  width?: number;
  height?: number;
  fontFamily?: string;
  numberFontFamily?: string;
  theme?: Partial<BeforeAfterStatTheme>;
  style?: CSSProperties;
};

const defaultTheme: BeforeAfterStatTheme = {
  text: "#2E2F3D",
  muted: "#7D7E8B",
  weak: "#B5B2BE",
  accent: "#9A8FDD",
  warm: "#D88E73",
  line: "rgba(46,47,61,0.14)",
  glass: "rgba(255,255,255,0.56)",
  glassStrong: "rgba(255,255,255,0.86)",
  glassBorder: "rgba(255,255,255,0.92)",
  shadow: "0 28px 80px rgba(70,64,92,0.14), 0 4px 16px rgba(70,64,92,0.06)",
};

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

export const BeforeAfterStat = ({
  title = "从反复返工，到一次说清",
  beforeLabel = "过去",
  beforeValue = "3 次",
  afterLabel = "现在",
  afterValue = "1 次",
  result = "返工减少 67%",
  titleAt = 0,
  beforeAt = 0.42,
  afterAt = 1.08,
  resultAt = 1.72,
  width = 1660,
  height = 660,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif',
  numberFontFamily = '"Space Grotesk", "SFMono-Regular", monospace',
  theme,
  style,
}: BeforeAfterStatProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const colors = {...defaultTheme, ...theme};
  const titleIn = progress(t, titleAt, 0.5);
  const beforeIn = progress(t, beforeAt, 0.5);
  const bridgeIn = progress(t, beforeAt + 0.48, 0.42);
  const afterIn = progress(t, afterAt, 0.5);
  const resultIn = progress(t, resultAt, 0.42);

  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 52,
        color: colors.text,
        fontFamily,
        ...style,
      }}
    >
      <div
        style={{
          textAlign: "center",
          fontSize: 76,
          fontWeight: 900,
          letterSpacing: "-0.04em",
          opacity: titleIn,
          translate: `0 ${interpolate(titleIn, [0, 1], [32, 0])}px`,
        }}
      >
        {title}
      </div>

      <div style={{display: "grid", gridTemplateColumns: "1fr 150px 1fr", alignItems: "center", gap: 24}}>
        <ComparePanel
          label={beforeLabel}
          value={beforeValue}
          tone="muted"
          progress={beforeIn}
          fontFamily={numberFontFamily}
          colors={colors}
        />
        <div style={{display: "flex", alignItems: "center", justifyContent: "center", opacity: bridgeIn, scale: 0.75 + bridgeIn * 0.25}}>
          <div style={{width: 92, height: 3, background: `linear-gradient(90deg,${colors.weak},${colors.accent})`, borderRadius: 99}} />
          <div
            style={{
              width: 18,
              height: 18,
              borderTop: `3px solid ${colors.accent}`,
              borderRight: `3px solid ${colors.accent}`,
              rotate: "45deg",
              marginLeft: -15,
            }}
          />
        </div>
        <ComparePanel
          label={afterLabel}
          value={afterValue}
          tone="accent"
          progress={afterIn}
          fontFamily={numberFontFamily}
          colors={colors}
        />
      </div>

      <div
        style={{
          alignSelf: "center",
          padding: "16px 30px",
          borderRadius: 999,
          color: colors.accent,
          background: "rgba(255,255,255,0.74)",
          border: `1px solid ${colors.glassBorder}`,
          boxShadow: "0 14px 36px rgba(70,64,92,0.10)",
          fontSize: 32,
          fontWeight: 800,
          opacity: resultIn,
          translate: `0 ${interpolate(resultIn, [0, 1], [18, 0])}px`,
        }}
      >
        {result}
      </div>
    </div>
  );
};

const ComparePanel = ({
  label,
  value,
  tone,
  progress: p,
  fontFamily,
  colors,
}: {
  label: string;
  value: string;
  tone: "muted" | "accent";
  progress: number;
  fontFamily: string;
  colors: BeforeAfterStatTheme;
}) => (
  <div
    style={{
      height: 370,
      padding: "46px 58px",
      borderRadius: 42,
      background: tone === "accent" ? colors.glassStrong : colors.glass,
      border: `1px solid ${colors.glassBorder}`,
      boxShadow: tone === "accent" ? colors.shadow : "0 20px 55px rgba(70,64,92,0.08)",
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between",
      boxSizing: "border-box",
      opacity: p,
      translate: `${interpolate(p, [0, 1], [tone === "accent" ? 54 : -54, 0])}px 0`,
      scale: 0.94 + p * 0.06,
    }}
  >
    <span style={{color: tone === "accent" ? colors.accent : colors.muted, fontSize: 34, fontWeight: 800}}>{label}</span>
    <span
      style={{
        fontFamily,
        color: tone === "accent" ? colors.text : colors.muted,
        fontSize: 152,
        fontWeight: 700,
        letterSpacing: "-0.07em",
        lineHeight: 1,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {value}
    </span>
    <div
      style={{
        height: 8,
        borderRadius: 99,
        background: tone === "accent" ? `linear-gradient(90deg,${colors.accent},${colors.warm})` : colors.line,
        scale: `${p} 1`,
        transformOrigin: "left center",
      }}
    />
  </div>
);

const progress = (time: number, start: number, duration: number) =>
  interpolate(time, [start, start + duration], [0, 1], {
    ...clamp,
    easing: easeOut,
  });
