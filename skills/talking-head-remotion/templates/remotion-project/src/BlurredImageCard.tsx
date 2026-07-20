import type {CSSProperties} from "react";
import {Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";

export type BlurredImageCardProps = {
  src: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  maxWidth?: number;
  maxHeight?: number;
  borderRadius?: number;
  edgeBlur?: number;
  enterDelayInFrames?: number;
  style?: CSSProperties;
};

const resolveImageSource = (src: string) => /^(https?:|data:|blob:)/.test(src) ? src : staticFile(src.replace(/^\//, ""));

/** 尺寸跟随原图，只在图片本身的边缘增加柔和虚化。 */
export const BlurredImageCard = ({src, alt = "", width, height, maxWidth = 1440, maxHeight = 760, borderRadius = 18, edgeBlur = 18, enterDelayInFrames = 0, style}: BlurredImageCardProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const imageSrc = resolveImageSource(src);
  const imageStyle: CSSProperties = {display: "block", width: width ?? "auto", height: height ?? "auto", maxWidth, maxHeight, objectFit: "contain", borderRadius};

  return (
    <div style={{position: "relative", display: "inline-block", width: "fit-content", height: "fit-content", maxWidth, maxHeight, opacity: interpolate(frame, [enterDelayInFrames, enterDelayInFrames + 0.35 * fps], [0, 1], {easing: Easing.bezier(0.16, 1, 0.3, 1), extrapolateLeft: "clamp", extrapolateRight: "clamp"}), scale: interpolate(frame, [enterDelayInFrames, enterDelayInFrames + 0.5 * fps], [0.96, 1], {easing: Easing.bezier(0.16, 1, 0.3, 1), extrapolateLeft: "clamp", extrapolateRight: "clamp"}), ...style}}>
      <Img src={imageSrc} alt="" style={{...imageStyle, position: "absolute", inset: 0, filter: `blur(${edgeBlur}px)`, opacity: 0.58, scale: 1.015}} />
      <Img src={imageSrc} alt={alt} style={{...imageStyle, position: "relative", filter: "drop-shadow(0 14px 30px rgba(31, 38, 68, 0.24))"}} />
    </div>
  );
};
