import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * BarChartGrow —— 多柱数据依次生长。
 * 复制到 src/library/，叠在项目背景上；时间均为组件内相对秒数。
 * 适合季度/部门/阶段数据；不适合超过 8 组或需要精确坐标轴的分析图。
 */
export type BarChartGrowProps = {
  title?: string;
  subtitle?: string;
  labels?: readonly string[];
  values?: readonly number[];
  titleAt?: number;
  barsAt?: number;
  stagger?: number;
  width?: number;
  height?: number;
  fontFamily?: string;
  numberFontFamily?: string;
  colors?: readonly string[];
  theme?: Partial<typeof defaultTheme>;
  style?: CSSProperties;
};

const defaultTheme = {
  text: "#2E2F3D", muted: "#7D7E8B", weak: "#B5B2BE", accent: "#9A8FDD", warm: "#D88E73",
  line: "rgba(46,47,61,0.10)", glass: "rgba(255,255,255,0.76)", border: "rgba(255,255,255,0.92)",
  shadow: "0 28px 80px rgba(70,64,92,0.14), 0 4px 16px rgba(70,64,92,0.06)",
};
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const BarChartGrow = ({
  title = "2024 年度业绩", subtitle = "各阶段数据对比", labels = ["Q1", "Q2", "Q3", "Q4", "全年"],
  values = [45, 72, 58, 91, 85], titleAt = 0, barsAt = 0.48, stagger = 0.24, width = 1660, height = 720,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif', numberFontFamily = '"Space Grotesk", monospace',
  colors = ["#9A8FDD", "#D88E73", "#9A8FDD", "#D88E73", "#9A8FDD"], theme, style,
}: BarChartGrowProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const c = {...defaultTheme, ...theme};
  const rows = labels.slice(0, 8).map((label, i) => ({label, value: values[i] ?? 0}));
  const max = Math.max(1, ...rows.map((row) => row.value));
  const titleIn = enter(t, titleAt, 0.5);
  const shine = ((t - barsAt + 8) % 4.2) / 4.2;

  return <div style={{width, height, display: "flex", flexDirection: "column", gap: 30, color: c.text, fontFamily, ...style}}>
    <div style={{display: "flex", alignItems: "flex-end", justifyContent: "space-between", opacity: titleIn, translate: `0 ${interpolate(titleIn, [0, 1], [28, 0])}px`}}>
      <div style={{fontSize: 78, fontWeight: 900, letterSpacing: "-0.045em"}}>{title}</div>
      <div style={{maxWidth: 560, color: c.muted, fontSize: 34, textAlign: "right"}}>{subtitle}</div>
    </div>
    <div style={{position: "relative", flex: 1, minHeight: 0, padding: "52px 64px 38px", boxSizing: "border-box", borderRadius: 44, background: c.glass, border: `1px solid ${c.border}`, boxShadow: c.shadow, overflow: "hidden"}}>
      <div style={{position: "absolute", top: 42, bottom: 76, left: 64, right: 64}}>
        {[0.25, 0.5, 0.75, 1].map((n) => <div key={n} style={{position: "absolute", left: 0, right: 0, bottom: `${n * 100}%`, height: 1, background: c.line}} />)}
      </div>
      <div style={{position: "relative", height: "100%", display: "grid", gridTemplateColumns: `repeat(${rows.length}, minmax(0,1fr))`, alignItems: "end", gap: 34, borderBottom: `2px solid ${c.line}`}}>
        {rows.map((row, i) => {
          const p = enter(t, barsAt + i * stagger, 0.72);
          const labelIn = enter(t, barsAt + i * stagger + 0.24, 0.36);
          return <div key={`${row.label}-${i}`} style={{height: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center", gap: 18}}>
            <div style={{fontFamily: numberFontFamily, fontSize: 38, fontWeight: 700, opacity: labelIn}}>{Math.round(row.value * p)}</div>
            <div style={{width: "78%", height: `${Math.max(5, row.value / max * 78)}%`, borderRadius: "26px 26px 8px 8px", background: `linear-gradient(180deg, ${colors[i % colors.length]}, ${colors[i % colors.length]}88)`, scale: `1 ${p}`, transformOrigin: "center bottom", boxShadow: i === rows.length - 1 ? `0 18px 42px ${c.accent}35` : undefined}} />
            <div style={{height: 38, color: i === rows.length - 1 ? c.warm : c.muted, fontSize: 30, fontWeight: 700, opacity: labelIn}}>{row.label}</div>
          </div>;
        })}
      </div>
      <div style={{position: "absolute", top: -120, bottom: -120, left: `${shine * 115 - 15}%`, width: 120, rotate: "16deg", background: "linear-gradient(90deg,transparent,rgba(255,255,255,.58),transparent)", filter: "blur(14px)", opacity: 0.32}} />
    </div>
  </div>;
};

const enter = (t: number, start: number, duration: number) => interpolate(t, [start, start + duration], [0, 1], {...clamp, easing: ease});
