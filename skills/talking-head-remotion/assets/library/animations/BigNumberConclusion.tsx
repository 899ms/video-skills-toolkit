import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * BigNumberConclusion —— 大数字结论镜头。
 *
 * 用法：复制到项目 src/library/，包在场景 <Sequence> 内；所有时间均为组件内相对秒数。
 * 组件只渲染前景内容，默认叠在项目的 FlutedGlassBackground 上。
 * SFX 卡点：valueAt 数字落位帧适合轻 hit / pop；emphasizeAt 适合二次强调。
 *
 * 适合：倍数、比例、增长、耗时、核心 KPI 的单项结论。
 * 不适合：没有数据依据的装饰数字，或需要同时解释多个指标的场景。
 */
export type BigNumberConclusionTheme = {
  text: string;
  muted: string;
  accent: string;
  warm: string;
  line: string;
  glass: string;
  glassBorder: string;
  shadow: string;
};

export type BigNumberConclusionProps = {
  eyebrow?: string;
  title?: string;
  value?: string;
  unit?: string;
  note?: string;
  appearAt?: number;
  valueAt?: number;
  noteAt?: number;
  emphasizeAt?: number;
  width?: number;
  height?: number;
  fontFamily?: string;
  numberFontFamily?: string;
  theme?: Partial<BigNumberConclusionTheme>;
  style?: CSSProperties;
};

const defaultTheme: BigNumberConclusionTheme = {
  text: "#2E2F3D",
  muted: "#7D7E8B",
  accent: "#9A8FDD",
  warm: "#D88E73",
  line: "rgba(46,47,61,0.14)",
  glass: "rgba(255,255,255,0.76)",
  glassBorder: "rgba(255,255,255,0.92)",
  shadow: "0 28px 80px rgba(70,64,92,0.14), 0 4px 16px rgba(70,64,92,0.06)",
};

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

export const BigNumberConclusion = ({
  eyebrow = "核心结论",
  title = "效率提升",
  value = "3.2",
  unit = "×",
  note = "同样的工作，一次完成",
  appearAt = 0,
  valueAt = 0.48,
  noteAt = 1.08,
  emphasizeAt,
  width = 1500,
  height = 620,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif',
  numberFontFamily = '"Space Grotesk", "SFMono-Regular", monospace',
  theme,
  style,
}: BigNumberConclusionProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const colors = {...defaultTheme, ...theme};
  const titleIn = progress(t, appearAt, 0.54);
  const numberIn = progress(t, valueAt, 0.66);
  const noteIn = progress(t, noteAt, 0.46);
  const emphasisLocal = emphasizeAt === undefined ? 999 : t - emphasizeAt;
  const emphasis =
    emphasisLocal >= 0 && emphasisLocal < 0.5
      ? interpolate(emphasisLocal, [0, 0.18, 0.5], [1, 1.06, 1], {...clamp, easing: easeOut})
      : 1;
  const breathe = 1 + Math.sin(frame / 18) * 0.008;

  return (
    <div
      style={{
        width,
        height,
        display: "grid",
        gridTemplateColumns: "0.86fr 1.14fr",
        alignItems: "center",
        gap: 84,
        color: colors.text,
        fontFamily,
        ...style,
      }}
    >
      <div style={{display: "flex", flexDirection: "column", justifyContent: "center", gap: 32}}>
        <div
          style={{
            color: colors.warm,
            fontSize: 30,
            fontWeight: 700,
            letterSpacing: "0.04em",
            opacity: titleIn,
            translate: `0 ${interpolate(titleIn, [0, 1], [28, 0])}px`,
          }}
        >
          {eyebrow}
        </div>
        <div
          style={{
            fontSize: 102,
            lineHeight: 1.08,
            letterSpacing: "-0.05em",
            fontWeight: 900,
            opacity: titleIn,
            translate: `0 ${interpolate(titleIn, [0, 1], [44, 0])}px`,
          }}
        >
          {title}
        </div>
        <div
          style={{
            maxWidth: 620,
            color: colors.muted,
            fontSize: 38,
            lineHeight: 1.48,
            opacity: noteIn,
            translate: `0 ${interpolate(noteIn, [0, 1], [28, 0])}px`,
          }}
        >
          {note}
        </div>
      </div>

      <div style={{position: "relative", display: "flex", alignItems: "center", justifyContent: "center", height: "100%"}}>
        <div
          style={{
            position: "absolute",
            width: 590,
            height: 590,
            borderRadius: "50%",
            border: `1px solid ${colors.line}`,
            scale: numberIn * breathe,
            opacity: numberIn * 0.72,
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 470,
            height: 470,
            borderRadius: "50%",
            background: colors.glass,
            border: `1px solid ${colors.glassBorder}`,
            boxShadow: colors.shadow,
            backdropFilter: "blur(22px)",
            scale: (0.8 + numberIn * 0.2) * emphasis,
            opacity: numberIn,
          }}
        />
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "flex-end",
            gap: 18,
            opacity: numberIn,
            scale: (0.7 + numberIn * 0.3) * emphasis,
          }}
        >
          <span
            style={{
              fontFamily: numberFontFamily,
              color: colors.accent,
              fontSize: 230,
              fontWeight: 700,
              letterSpacing: "-0.08em",
              lineHeight: 0.85,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {value}
          </span>
          <span style={{fontFamily: numberFontFamily, color: colors.warm, fontSize: 82, fontWeight: 700, paddingBottom: 24}}>
            {unit}
          </span>
        </div>
      </div>
    </div>
  );
};

const progress = (time: number, start: number, duration: number) =>
  interpolate(time, [start, start + duration], [0, 1], {
    ...clamp,
    easing: easeOut,
  });
