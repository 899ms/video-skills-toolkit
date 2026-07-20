import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * KeyPointMarker —— 重点句 / 金句标注镜头。
 *
 * 用法：复制到项目 src/library/，包在场景 <Sequence> 内；时间均为组件内相对秒数。
 * markerAt 控制紫—暖桃下划线扫入，组件在场期间保留缓慢玻璃扫光。
 * SFX 卡点：appearAt 适合轻 pop，markerAt 适合轻 sweep。
 *
 * 适合：结论、提醒、方法原则、章节转折金句。
 * 不适合：超过两行的长段落、普通字幕、需要同时展示多条要点的列表。
 */
export type KeyPointMarkerTheme = {
  text: string;
  muted: string;
  accent: string;
  warm: string;
  glass: string;
  glassBorder: string;
  shadow: string;
};

export type KeyPointMarkerProps = {
  kicker?: string;
  text?: string;
  detail?: string;
  appearAt?: number;
  textAt?: number;
  markerAt?: number;
  detailAt?: number;
  width?: number;
  minHeight?: number;
  fontFamily?: string;
  theme?: Partial<KeyPointMarkerTheme>;
  style?: CSSProperties;
};

const defaultTheme: KeyPointMarkerTheme = {
  text: "#2E2F3D",
  muted: "#7D7E8B",
  accent: "#9A8FDD",
  warm: "#D88E73",
  glass: "rgba(255,255,255,0.88)",
  glassBorder: "rgba(255,255,255,0.92)",
  shadow: "0 28px 80px rgba(70,64,92,0.14), 0 4px 16px rgba(70,64,92,0.06)",
};

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const easeEditorial = Easing.bezier(0.45, 0, 0.55, 1);

export const KeyPointMarker = ({
  kicker = "记住这一点",
  text = "先让问题暴露，再开始执行",
  detail = "不知道自己不知道什么，才是最大的返工来源。",
  appearAt = 0,
  textAt = 0.45,
  markerAt = 1.15,
  detailAt = 1.4,
  width = 1370,
  minHeight = 480,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif',
  theme,
  style,
}: KeyPointMarkerProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const colors = {...defaultTheme, ...theme};
  const cardIn = progress(t, appearAt, 0.62);
  const kickerIn = progress(t, appearAt + 0.24, 0.4);
  const textIn = progress(t, textAt, 0.56);
  const detailIn = progress(t, detailAt, 0.42);
  const underline = interpolate(t, [markerAt, markerAt + 0.7], [0, 1], {
    ...clamp,
    easing: easeEditorial,
  });
  const scan = ((t - appearAt) % 5.2) / 5.2;

  return (
    <div
      style={{
        position: "relative",
        width,
        minHeight,
        borderRadius: 48,
        padding: "62px 76px 68px",
        boxSizing: "border-box",
        background: colors.glass,
        border: `1px solid ${colors.glassBorder}`,
        boxShadow: colors.shadow,
        color: colors.text,
        fontFamily,
        overflow: "hidden",
        opacity: cardIn,
        scale: 0.94 + cardIn * 0.06,
        translate: `0 ${interpolate(cardIn, [0, 1], [36, 0])}px`,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: `${scan * 120 - 20}%`,
          top: -100,
          width: 140,
          height: 760,
          rotate: "18deg",
          background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.72),transparent)",
          filter: "blur(18px)",
          opacity: 0.5,
        }}
      />

      <div style={{position: "relative", display: "flex", flexDirection: "column", gap: 32}}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
            color: colors.warm,
            fontSize: 30,
            fontWeight: 800,
            opacity: kickerIn,
          }}
        >
          <span style={{width: 42, height: 4, borderRadius: 99, background: colors.warm, scale: `${kickerIn} 1`, transformOrigin: "left"}} />
          {kicker}
        </div>

        <div style={{position: "relative", width: "fit-content", maxWidth: width - 152}}>
          <div
            style={{
              fontSize: 86,
              lineHeight: 1.28,
              fontWeight: 900,
              letterSpacing: "-0.045em",
              opacity: textIn,
              translate: `0 ${interpolate(textIn, [0, 1], [34, 0])}px`,
            }}
          >
            {text}
          </div>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: -14,
              height: 16,
              borderRadius: 99,
              background: `linear-gradient(90deg,${colors.accent},${colors.warm})`,
              opacity: 0.62,
              scale: `${underline} 1`,
              transformOrigin: "left center",
            }}
          />
        </div>

        {detail ? (
          <div
            style={{
              color: colors.muted,
              fontSize: 34,
              lineHeight: 1.5,
              opacity: detailIn,
              translate: `0 ${interpolate(detailIn, [0, 1], [24, 0])}px`,
            }}
          >
            {detail}
          </div>
        ) : null}
      </div>
    </div>
  );
};

const progress = (time: number, start: number, duration: number) =>
  interpolate(time, [start, start + duration], [0, 1], {
    ...clamp,
    easing: easeOut,
  });
