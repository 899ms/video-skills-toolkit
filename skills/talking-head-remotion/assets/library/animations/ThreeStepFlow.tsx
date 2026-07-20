import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/**
 * ThreeStepFlow —— 三步 SOP / 方法流程镜头。
 *
 * 用法：复制到项目 src/library/，steps[].appearAt 使用组件内相对秒数并对齐字幕 cue。
 * 组件只负责三节点横向流程；更多节点或复杂分支请改用 FlowDiagram。
 * SFX 卡点：每个 step 的 appearAt 适合轻 pop，连线抵达下一节点时适合轻 sweep。
 *
 * 适合：三步方法、教程、输入—处理—输出、发现—验证—沉淀。
 * 不适合：四步以上流程、长文案节点、带分支的架构图。
 */
export type ThreeStepFlowItem = {
  title: string;
  description?: string;
  appearAt: number;
};

export type ThreeStepFlowTheme = {
  text: string;
  muted: string;
  accent: string;
  warm: string;
  line: string;
  glass: string;
  glassBorder: string;
  shadow: string;
};

export type ThreeStepFlowProps = {
  title?: string;
  titleAt?: number;
  steps?: readonly [ThreeStepFlowItem, ThreeStepFlowItem, ThreeStepFlowItem];
  width?: number;
  height?: number;
  fontFamily?: string;
  numberFontFamily?: string;
  theme?: Partial<ThreeStepFlowTheme>;
  style?: CSSProperties;
};

const defaultTheme: ThreeStepFlowTheme = {
  text: "#2E2F3D",
  muted: "#7D7E8B",
  accent: "#9A8FDD",
  warm: "#D88E73",
  line: "rgba(46,47,61,0.14)",
  glass: "rgba(255,255,255,0.76)",
  glassBorder: "rgba(255,255,255,0.92)",
  shadow: "0 24px 60px rgba(70,64,92,0.12), 0 4px 14px rgba(70,64,92,0.05)",
};

const defaultSteps: readonly [ThreeStepFlowItem, ThreeStepFlowItem, ThreeStepFlowItem] = [
  {title: "拆解", description: "看清问题结构", appearAt: 0.45},
  {title: "执行", description: "逐步验证结果", appearAt: 1.2},
  {title: "沉淀", description: "放回素材库", appearAt: 1.95},
];

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const easeEditorial = Easing.bezier(0.45, 0, 0.55, 1);

export const ThreeStepFlow = ({
  title = "把复杂任务变成可复用流程",
  titleAt = 0,
  steps = defaultSteps,
  width = 1660,
  height = 620,
  fontFamily = '"Noto Sans SC", "PingFang SC", sans-serif',
  numberFontFamily = '"Space Grotesk", "SFMono-Regular", monospace',
  theme,
  style,
}: ThreeStepFlowProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const colors = {...defaultTheme, ...theme};
  const titleIn = progress(t, titleAt, 0.5);
  const lineStart = steps[0].appearAt + 0.25;
  const lineEnd = steps[2].appearAt + 0.35;
  const lineP = interpolate(t, [lineStart, lineEnd], [0, 1], {
    ...clamp,
    easing: easeEditorial,
  });

  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 72,
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
          letterSpacing: "-0.045em",
          opacity: titleIn,
          translate: `0 ${interpolate(titleIn, [0, 1], [30, 0])}px`,
        }}
      >
        {title}
      </div>

      <div style={{position: "relative", display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 62, alignItems: "center"}}>
        <div style={{position: "absolute", left: "13%", right: "13%", top: 104, height: 3, background: colors.line}} />
        <div
          style={{
            position: "absolute",
            left: "13%",
            top: 104,
            width: `${lineP * 74}%`,
            height: 3,
            background: `linear-gradient(90deg,${colors.accent},${colors.warm})`,
            borderRadius: 99,
          }}
        />

        {steps.map((step, index) => {
          const p = progress(t, step.appearAt, 0.5);
          const glow = index === 2 ? 0.12 + Math.sin(frame / 16) * 0.04 : 0.06;
          return (
            <div
              key={`${step.title}-${index}`}
              style={{
                position: "relative",
                zIndex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 22,
                opacity: p,
                translate: `0 ${interpolate(p, [0, 1], [54, 0])}px`,
              }}
            >
              <div
                style={{
                  width: 118,
                  height: 118,
                  borderRadius: 34,
                  background: colors.glass,
                  border: `1px solid ${colors.glassBorder}`,
                  boxShadow: `0 24px 60px rgba(70,64,92,${glow})`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: index === 2 ? colors.warm : colors.accent,
                  fontFamily: numberFontFamily,
                  fontSize: 42,
                  fontWeight: 700,
                  rotate: `${interpolate(p, [0, 1], [-7, 0])}deg`,
                  scale: 0.78 + p * 0.22,
                }}
              >
                0{index + 1}
              </div>
              <div style={{fontSize: 54, fontWeight: 900}}>{step.title}</div>
              {step.description ? <div style={{color: colors.muted, fontSize: 30}}>{step.description}</div> : null}
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
