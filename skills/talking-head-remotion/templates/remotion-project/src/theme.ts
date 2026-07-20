import {staticFile} from "remotion";

const fontFiles = [
  {family: "Noto Sans SC", file: "assets/fonts/NotoSansSC-400.ttf", weight: "400"},
  {family: "Noto Sans SC", file: "assets/fonts/NotoSansSC-700.ttf", weight: "700"},
  {family: "Noto Sans SC", file: "assets/fonts/NotoSansSC-900.ttf", weight: "900"},
  {family: "Space Grotesk", file: "assets/fonts/SpaceGrotesk-400.ttf", weight: "400"},
  {family: "Space Grotesk", file: "assets/fonts/SpaceGrotesk-700.ttf", weight: "700"},
] as const;

if (typeof document !== "undefined" && !document.getElementById("studio-font-faces")) {
  const style = document.createElement("style");
  style.id = "studio-font-faces";
  style.textContent = fontFiles
    .map(
      (font) => `@font-face {
  font-family: "${font.family}";
  src: url("${staticFile(font.file)}") format("truetype");
  font-weight: ${font.weight};
  font-style: normal;
  font-display: swap;
}`,
    )
    .join("\n");
  document.head.appendChild(style);
}

// 「乳白瓦楞玻璃」视觉体系：冷调乳白底 + 暖桃光透 + 淡紫冰蓝呼吸
export const colors = {
  canvas: "#f4f4f7", // 乳白底色（偏冷灰紫，像磨砂陶瓷）
  ink: "#1f2430", // 主文字：石板蓝黑
  muted: "#7a7f8e", // 次级文字：冷灰
  weak: "#b8bcc8", // 弱文字
  line: "rgba(31,36,48,0.10)",
  lineStrong: "rgba(31,36,48,0.14)",
  accent: "#5b6cff", // 强调色：柔和长春花蓝（配合 pastel 体系）
  peach: "#f07a4a", // 前景暖橙：柔和珊瑚橙（呼应背景暖光）
  glow: "rgba(255,152,92,0.52)", // 背景暖桃光晕
  lilac: "rgba(196,186,238,0.22)", // 淡紫呼吸
  iceBlue: "rgba(168,196,236,0.20)", // 冰蓝呼吸
  topbar: "rgba(252,252,254,0.86)", // 顶栏：磨砂浅玻璃
  topbarMuted: "rgba(31,36,48,0.42)", // 顶栏未播章节文字
  topbarSeparator: "rgba(31,36,48,0.20)", // 顶栏章节分隔
  glass: "rgba(255,255,255,0.66)", // 磨砂玻璃卡片底
  glassBorder: "rgba(255,255,255,0.85)", // 玻璃卡片描边
  darkPanel: "#1b1f2a", // 深色代码卡（体系内唯一深色，做对比锚点）
  white: "#ffffff",
};

export const fonts = {
  sans: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  mono: '"Space Grotesk", "SFMono-Regular", "Menlo", "Consolas", monospace',
};

export const layout = {
  width: 1920,
  height: 1080,
  fps: 30,
  topbarHeight: 68,
  safeTop: 196,
  safeX: 120,
  safeBottom: 196,
  pipSize: 206,
  pipRight: 104,
  pipBottom: 150,
  captionBottom: 96,
};
