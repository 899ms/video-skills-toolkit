import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/** NumberCounter —— 巨型数字计数器 + 环形刻度。适合累计数、里程碑；不适合多指标。 */
export type NumberCounterProps = {
  title?: string; targetValue?: number; prefix?: string; suffix?: string; note?: string;
  titleAt?: number; countAt?: number; countDuration?: number; noteAt?: number;
  width?: number; height?: number; locale?: string; fontFamily?: string; numberFontFamily?: string;
  theme?: Partial<typeof defaultTheme>; style?: CSSProperties;
};
const defaultTheme = {text: "#2E2F3D", muted: "#7D7E8B", accent: "#9A8FDD", warm: "#D88E73", line: "rgba(46,47,61,.14)", glass: "rgba(255,255,255,.72)", border: "rgba(255,255,255,.92)", shadow: "0 28px 80px rgba(70,64,92,.14)"};
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const NumberCounter = ({title = "累计用户数", targetValue = 1285000, prefix = "", suffix = "+", note = "突破百万里程碑，持续增长中", titleAt = 0, countAt = 0.42, countDuration = 3.2, noteAt = 1.72, width = 1360, height = 720, locale = "en-US", fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif', numberFontFamily = '"Space Grotesk", monospace', theme, style}: NumberCounterProps) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig(); const t = frame / fps; const c = {...defaultTheme, ...theme};
  const titleIn = enter(t, titleAt, .5); const ringIn = enter(t, countAt, .58);
  const count = interpolate(t, [countAt, countAt + countDuration], [0, targetValue], {...clamp, easing: Easing.out(Easing.cubic)});
  const noteIn = enter(t, noteAt, .46); const pulse = 1 + Math.sin(frame / 17) * .008;
  return <div style={{width, height, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: c.text, fontFamily, ...style}}>
    <div style={{fontSize: 78, fontWeight: 900, letterSpacing: "-.04em", opacity: titleIn, translate: `0 ${interpolate(titleIn,[0,1],[24,0])}px`}}>{title}</div>
    <div style={{position: "relative", width: 560, height: 470, display: "flex", alignItems: "center", justifyContent: "center"}}>
      <div style={{position: "absolute", width: 420, height: 420, borderRadius: "50%", border: `1px solid ${c.line}`, opacity: ringIn, scale: ringIn * pulse, rotate: `${frame / 8}deg`}} />
      <div style={{position: "absolute", width: 330, height: 330, borderRadius: "50%", background: c.glass, border: `1px solid ${c.border}`, boxShadow: c.shadow, opacity: ringIn, scale: .85 + ringIn * .15}} />
      <div style={{position: "relative", display: "flex", alignItems: "baseline", gap: 10, whiteSpace: "nowrap", fontFamily: numberFontFamily, fontVariantNumeric: "tabular-nums", opacity: ringIn, scale: pulse}}>
        <span style={{fontSize: 156, fontWeight: 700, letterSpacing: "-.07em"}}>{prefix}{Math.round(count).toLocaleString(locale)}</span><span style={{fontSize: 78, color: c.warm, fontWeight: 700}}>{suffix}</span>
      </div>
    </div>
    <div style={{padding: "14px 28px", borderRadius: 999, background: c.glass, border: `1px solid ${c.border}`, color: c.muted, fontSize: 34, opacity: noteIn, translate: `0 ${interpolate(noteIn,[0,1],[18,0])}px`}}>{note}</div>
  </div>;
};
const enter = (t: number, start: number, duration: number) => interpolate(t,[start,start+duration],[0,1],{...clamp,easing:ease});
