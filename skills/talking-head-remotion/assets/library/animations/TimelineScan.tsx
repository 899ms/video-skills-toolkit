import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * TimelineScan —— 三节点时间线 / 阶段推进镜头。
 *
 * 用法：复制到项目 src/library/，points[].appearAt 使用组件内相对秒数并对齐字幕 cue。
 * 曲线路径从第一个节点向第三个节点生长；每个节点按 cue 依次点亮。
 * SFX 卡点：每个 point 的 appearAt 适合轻 pop，路径到达末端适合确认 beep。
 *
 * 适合：版本变化、项目阶段、历史演进、发现—验证—复用。
 * 不适合：精确到比例的时间轴、四个以上密集节点、长段节点说明。
 */
export type TimelineScanPoint = {
  title: string;
  label?: string;
  appearAt: number;
};

export type TimelineScanTheme = {
  text: string;
  muted: string;
  accent: string;
  warm: string;
  line: string;
  white: string;
};

export type TimelineScanProps = {
  title?: string;
  meta?: string;
  titleAt?: number;
  points?: readonly [TimelineScanPoint, TimelineScanPoint, TimelineScanPoint];
  width?: number;
  height?: number;
  fontFamily?: string;
  metaFontFamily?: string;
  theme?: Partial<TimelineScanTheme>;
  style?: CSSProperties;
};

const defaultTheme: TimelineScanTheme = {
  text: "#2E2F3D",
  muted: "#7D7E8B",
  accent: "#9A8FDD",
  warm: "#D88E73",
  line: "rgba(46,47,61,0.14)",
  white: "#FFFFFF",
};

const defaultPoints: readonly [TimelineScanPoint, TimelineScanPoint, TimelineScanPoint] = [
  {title: "发现", label: "暴露盲区", appearAt: 0.55},
  {title: "验证", label: "用样片确认", appearAt: 1.45},
  {title: "复用", label: "沉淀成模板", appearAt: 2.35},
];

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const easeEditorial = Easing.bezier(0.45, 0, 0.55, 1);

export const TimelineScan = ({
  title = "一次完整的迭代路径",
  meta = "PROCESS / 01—03",
  titleAt = 0,
  points = defaultPoints,
  width = 1660,
  height = 620,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif',
  metaFontFamily = '"Space Grotesk", "SFMono-Regular", monospace',
  theme,
  style,
}: TimelineScanProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const colors = {...defaultTheme, ...theme};
  const titleIn = progress(t, titleAt, 0.5);
  const pathStart = points[0].appearAt + 0.15;
  const pathEnd = points[2].appearAt + 0.35;
  const pathP = interpolate(t, [pathStart, pathEnd], [0, 1], {
    ...clamp,
    easing: easeEditorial,
  });
  const positions = [
    {left: "1.5%", top: 82, alignItems: "flex-start" as const},
    {left: "47%", top: 68, alignItems: "center" as const},
    {left: "91%", top: 50, alignItems: "flex-end" as const},
  ];

  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 88,
        color: colors.text,
        fontFamily,
        ...style,
      }}
    >
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-end"}}>
        <div
          style={{
            fontSize: 78,
            fontWeight: 900,
            letterSpacing: "-0.045em",
            opacity: titleIn,
            translate: `0 ${interpolate(titleIn, [0, 1], [30, 0])}px`,
          }}
        >
          {title}
        </div>
        <div style={{color: colors.muted, fontFamily: metaFontFamily, fontSize: 26, opacity: titleIn}}>{meta}</div>
      </div>

      <div style={{position: "relative", height: 360}}>
        <svg viewBox="0 0 1600 220" style={{position: "absolute", left: 0, top: 0, width: "100%", height: 220, overflow: "visible"}}>
          <path
            d="M70 126 C340 18 470 205 790 112 S1260 16 1530 94"
            fill="none"
            stroke={colors.line}
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path
            d="M70 126 C340 18 470 205 790 112 S1260 16 1530 94"
            fill="none"
            stroke="url(#timeline-scan-gradient)"
            strokeWidth="8"
            strokeLinecap="round"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset={1 - pathP}
          />
          <defs>
            <linearGradient id="timeline-scan-gradient" x1="0" x2="1">
              <stop offset="0" stopColor={colors.accent} />
              <stop offset="1" stopColor={colors.warm} />
            </linearGradient>
          </defs>
        </svg>

        {points.map((point, index) => {
          const p = progress(t, point.appearAt, 0.46);
          const position = positions[index];
          const breathe = 1 + Math.sin(frame / 18 + index * 1.4) * 0.025;
          return (
            <div
              key={`${point.title}-${index}`}
              style={{
                position: "absolute",
                left: position.left,
                top: position.top,
                width: 160,
                display: "flex",
                flexDirection: "column",
                alignItems: position.alignItems,
                gap: 18,
                opacity: p,
                scale: (0.75 + p * 0.25) * breathe,
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: colors.white,
                  border: `9px solid ${index === 2 ? colors.warm : colors.accent}`,
                  boxShadow: `0 0 0 14px rgba(154,143,221,0.11), 0 16px 34px rgba(70,64,92,0.14)`,
                }}
              />
              <div style={{fontSize: 46, fontWeight: 900, whiteSpace: "nowrap"}}>{point.title}</div>
              {point.label ? <div style={{fontSize: 28, color: colors.muted, whiteSpace: "nowrap"}}>{point.label}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const progress = (time: number, start: number, duration: number) =>
  interpolate(time, [start, start + duration], [0, 1], {
    ...clamp,
    easing: easeOut,
  });
