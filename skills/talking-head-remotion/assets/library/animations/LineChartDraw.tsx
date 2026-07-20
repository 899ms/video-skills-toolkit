import type {CSSProperties} from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";

/** LineChartDraw —— 折线从左到右绘制，节点依次点亮。适合趋势；不适合精确分析仪表。 */
export type LineChartDrawProps = {title?: string; subtitle?: string; values?: readonly number[]; labels?: readonly string[]; titleAt?: number; drawAt?: number; drawDuration?: number; width?: number; height?: number; fontFamily?: string; numberFontFamily?: string; theme?: Partial<typeof defaultTheme>; style?: CSSProperties};
const defaultTheme = {text:"#2E2F3D",muted:"#7D7E8B",weak:"#B5B2BE",accent:"#9A8FDD",warm:"#D88E73",line:"rgba(46,47,61,.12)",glass:"rgba(255,255,255,.74)",border:"rgba(255,255,255,.92)",shadow:"0 28px 80px rgba(70,64,92,.14)"};
const clamp={extrapolateLeft:"clamp",extrapolateRight:"clamp"} as const;
export const LineChartDraw=({title="月活跃用户增长趋势",subtitle="2024.01—2024.12",values=[34,39,43,51,49,58,64,68,76,81,89,96],labels=["01","02","03","04","05","06","07","08","09","10","11","12"],titleAt=0,drawAt=.72,drawDuration=3.2,width=1660,height=700,fontFamily='"Noto Sans SC", "PingFang SC", sans-serif',numberFontFamily='"Space Grotesk", monospace',theme,style}:LineChartDrawProps)=>{
  const frame=useCurrentFrame();const{fps}=useVideoConfig();const t=frame/fps;const c={...defaultTheme,...theme};
  const data=(values.length>=2?values:[0,1]).slice(0,16);const min=Math.min(...data);const max=Math.max(...data,min+1);
  const pts=data.map((v,i)=>({x:70+i/(data.length-1)*1450,y:500-(v-min)/(max-min)*390}));
  const path=pts.map((p,i)=>`${i?"L":"M"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const draw=interpolate(t,[drawAt,drawAt+drawDuration],[0,1],{...clamp,easing:Easing.bezier(.22,.72,.18,1)});const titleIn=enter(t,titleAt,.5);
  return <div style={{width,height,display:"flex",flexDirection:"column",gap:28,color:c.text,fontFamily,...style}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",opacity:titleIn}}><div><div style={{fontSize:76,fontWeight:900,letterSpacing:"-.045em"}}>{title}</div><div style={{marginTop:10,color:c.muted,fontFamily:numberFontFamily,fontSize:30}}>{subtitle}</div></div><div style={{color:c.muted,fontSize:28}}>TREND</div></div>
    <div style={{flex:1,minHeight:0,padding:"26px 42px",boxSizing:"border-box",borderRadius:44,background:c.glass,border:`1px solid ${c.border}`,boxShadow:c.shadow}}>
      <svg viewBox="0 0 1590 580" style={{width:"100%",height:"100%",overflow:"visible"}}>
        <defs><linearGradient id="lc-stroke" x1="0" x2="1"><stop stopColor={c.accent}/><stop offset="1" stopColor={c.warm}/></linearGradient></defs>
        {[0,1,2,3].map(i=><line key={i} x1="70" x2="1520" y1={110+i*130} y2={110+i*130} stroke={c.line} strokeDasharray="7 13"/>)}
        <path d={path} fill="none" stroke={c.accent} strokeOpacity={.16} strokeWidth={20} pathLength={1} strokeDasharray={1} strokeDashoffset={1-draw}/>
        <path d={path} fill="none" stroke="url(#lc-stroke)" strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1-draw}/>
        {pts.map((p,i)=>{const q=enter(t,drawAt+i*(drawDuration/(pts.length-1))-.08,.3);return <g key={i} opacity={q} style={{scale:`${q*(i===pts.length-1?1+Math.sin(frame/13)*.08:1)}`,transformOrigin:`${p.x}px ${p.y}px`}}><circle cx={p.x} cy={p.y} r={i===pts.length-1?12:7} fill="#fff" stroke={i===pts.length-1?c.warm:c.accent} strokeWidth={5}/></g>})}
        {pts.map((p,i)=>i%Math.max(1,Math.floor(pts.length/5))===0||i===pts.length-1?<text key={`l${i}`} x={p.x} y="552" textAnchor="middle" fill={c.muted} fontFamily={numberFontFamily} fontSize="24">{labels[i]??i+1}</text>:null)}
      </svg>
    </div>
  </div>;
};
const enter=(t:number,start:number,duration:number)=>interpolate(t,[start,start+duration],[0,1],{...clamp,easing:Easing.bezier(.16,1,.3,1)});
