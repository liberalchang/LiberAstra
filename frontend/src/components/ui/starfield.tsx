import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";
import { buildGalaxy, projectGalaxy, randomGalaxyShape, type GalaxyStar } from "./galaxy";

/**
 * 「银河」画布：星点分布在带核球的双旋臂盘里，绕盘心缓慢自转，
 * 透视投影带来近大远小；盘心叠一层主题色星云，亮星之间偶现星座细线。
 * 颜色取自主题 token，随明暗主题换天；prefers-reduced-motion 下渲染静态一帧；
 * 页面隐藏时暂停。
 */

interface Meteor {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
}

function hexToRgb(hex: string): [number, number, number] | null {
  const m = hex.trim().match(/^#([0-9a-f]{6})$/i);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const GALAXY_RADIUS = 0.62;
const FOCAL = 2.8;
const TILT = 1.02;
const ROTATION_SPEED = 0.000075;
const ANCHOR_STEP = 29;

export function Starfield({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let raf = 0;
    let w = 0;
    let h = 0;
    let ready = false;
    let seeded = false;
    let stars: GalaxyStar[] = [];
    let anchors: GalaxyStar[] = [];
    let meteors: Meteor[] = [];
    let nextMeteorAt = 3000;
    // 每次进入换一个旋转方向与略不同的俯角
    const spin = Math.random() < 0.5 ? -1 : 1;
    const baseTilt = TILT + (Math.random() - 0.5) * 0.12;
    let flareStar: GalaxyStar | null = null;
    let flareEnd = 0;
    let nextFlareAt = 5000;
    let constellationEnd = 0;
    let nextConstellationAt = 9000;

    // 主题色：读计算后的 CSS 变量，主题切换时重读
    let ink = "#fafafa";
    let primary = "#7c3aed";
    let accent = "#e11d48";
    let dark = true;
    const readTheme = () => {
      const style = getComputedStyle(document.documentElement);
      dark = document.documentElement.classList.contains("dark");
      ink = style.getPropertyValue("--foreground").trim() || ink;
      primary = style.getPropertyValue("--primary").trim() || primary;
      accent = style.getPropertyValue("--accent").trim() || accent;
      // 静态帧模式下主题切换后重绘一次，否则银河停留在旧主题色
      if (reduced.matches && w > 0) draw(4000, false);
    };
    readTheme();
    const themeObserver = new MutationObserver(readTheme);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    const seed = () => {
      const count = Math.min(1500, Math.max(520, Math.round((w * h) / 1050)));
      stars = buildGalaxy(count, Math.random, randomGalaxyShape());
      anchors = stars.filter((_, index) => index % ANCHOR_STEP === 0).slice(0, 34);
      seeded = true;
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!seeded && w > 0 && h > 0) seed();
      // 静态帧模式下 resize 会清空画布，补绘一次
      if (ready && reduced.matches) draw(4000, false);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const paintSky = () => {
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      if (dark) {
        sky.addColorStop(0, "#0d0c10");
        sky.addColorStop(0.55, "#120f18");
        sky.addColorStop(1, "#17121f");
      } else {
        sky.addColorStop(0, "#f3f4f6");
        sky.addColorStop(1, "#eae6f4");
      }
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
    };

    const paintNebula = (
      cx: number,
      cy: number,
      radius: number,
      primaryRgb: [number, number, number],
      accentRgb: [number, number, number],
    ) => {
      ctx.save();
      ctx.globalCompositeOperation = dark ? "lighter" : "source-over";
      ctx.translate(cx, cy);
      ctx.scale(1, 0.52);

      const halo = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 0.96);
      halo.addColorStop(0, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${dark ? 0.3 : 0.12})`);
      halo.addColorStop(0.35, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${dark ? 0.15 : 0.065})`);
      halo.addColorStop(0.72, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${dark ? 0.06 : 0.025})`);
      halo.addColorStop(1, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},0)`);
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(0, 0, radius * 0.96, 0, Math.PI * 2);
      ctx.fill();

      const core = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 0.36);
      core.addColorStop(0, `rgba(${accentRgb[0]},${accentRgb[1]},${accentRgb[2]},${dark ? 0.18 : 0.06})`);
      core.addColorStop(0.55, `rgba(${accentRgb[0]},${accentRgb[1]},${accentRgb[2]},${dark ? 0.07 : 0.025})`);
      core.addColorStop(1, `rgba(${accentRgb[0]},${accentRgb[1]},${accentRgb[2]},0)`);
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(0, 0, radius * 0.36, 0, Math.PI * 2);
      ctx.fill();

      ctx.translate(radius * 0.36, -radius * 0.12);
      const armGlow = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 0.44);
      armGlow.addColorStop(0, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${dark ? 0.1 : 0.04})`);
      armGlow.addColorStop(1, `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},0)`);
      ctx.fillStyle = armGlow;
      ctx.beginPath();
      ctx.arc(0, 0, radius * 0.44, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    };

    const draw = (t: number, animate: boolean) => {
      paintSky();
      const inkRgb = hexToRgb(ink) ?? [250, 250, 250];
      const primaryRgb = hexToRgb(primary) ?? [124, 58, 237];
      const accentRgb = hexToRgb(accent) ?? [225, 29, 72];
      const palette = [inkRgb, primaryRgb, accentRgb];
      const starAlpha = dark ? 1 : 0.48;

      const cx = w * 0.5;
      const cy = h * 0.5;
      const radius = Math.min(w, h) * GALAXY_RADIUS;
      const angle = animate ? t * ROTATION_SPEED * spin : 1.35 * spin;
      const tilt = baseTilt + (animate ? Math.sin(t * 0.000035) * 0.035 : 0);

      if (animate) {
        if (t > nextFlareAt) {
          flareStar = stars[Math.floor(Math.random() * stars.length)] ?? null;
          flareEnd = t + 1200 + Math.random() * 900;
          nextFlareAt = t + 9000 + Math.random() * 12000;
        }
        if (t > nextConstellationAt) {
          constellationEnd = t + 2600 + Math.random() * 1200;
          nextConstellationAt = t + 16000 + Math.random() * 14000;
        }
      }
      const constellationActive = t < constellationEnd;
      const flareActive = flareStar !== null && t < flareEnd;

      paintNebula(cx, cy, radius, primaryRgb, accentRgb);

      // 每颗星有轻微差速与本轮摆动，盘面整体仍保持旋臂形状
      const projectStar = (star: GalaxyStar) => {
        const r = Math.hypot(star.x, star.z);
        const omega = 0.96 + 0.06 / (0.35 + r);
        const wobble =
          Math.sin(t * (0.00028 + (star.phase % 1) * 0.00018) + star.phase) *
          (0.008 + (star.phase % 1) * 0.008);
        return projectGalaxy(star, angle * omega + wobble, tilt, FOCAL, radius, cx, cy);
      };
      const projected = stars.map((star) => ({ star, p: projectStar(star) }));
      projected.sort((a, b) => a.p.depth - b.p.depth);

      // 星座连线：只取少量亮星作为锚点，避免 O(n²) 拖慢
      const anchorPoints = anchors.map(projectStar);
      const linkDist = radius * (constellationActive ? 0.26 : 0.2);
      const lineAlpha = (dark ? 0.15 : 0.075) * (constellationActive ? 2.1 : 1);
      ctx.lineWidth = 0.55;
      for (let i = 0; i < anchorPoints.length; i += 1) {
        for (let j = i + 1; j < anchorPoints.length; j += 1) {
          const a = anchorPoints[i];
          const b = anchorPoints[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 >= linkDist * linkDist) continue;
          const alpha = (1 - Math.sqrt(d2) / linkDist) * lineAlpha;
          ctx.strokeStyle = `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${alpha.toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      // 星点：远星先画，近星后画；亮星带一圈很淡的光晕
      ctx.save();
      ctx.globalCompositeOperation = dark ? "lighter" : "source-over";
      for (const { star, p } of projected) {
        const flare = flareActive && star === flareStar;
        const twinkle = 0.68 + 0.32 * Math.sin(t * 0.0011 + star.phase);
        const depthAlpha = Math.min(1.15, Math.max(0.22, 0.45 + p.scale * 0.4));
        const alpha = Math.min(1, twinkle * depthAlpha * starAlpha * (flare ? 1.7 : 1));
        const [r, g, b] = palette[star.tint];
        const size = Math.max(0.35, star.size * p.scale * 1.05) * (flare ? 1.35 : 1);
        if (flare) {
          ctx.fillStyle = `rgba(${r},${g},${b},0.28)`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, size * 8, 0, Math.PI * 2);
          ctx.fill();
        } else if (star.size > 2.15) {
          ctx.fillStyle = `rgba(${r},${g},${b},${(alpha * 0.2).toFixed(3)})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, size * 3.6, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // 流星：强调色，每隔数秒一颗
      if (animate) {
        if (t > nextMeteorAt) {
          nextMeteorAt = t + 8000 + Math.random() * 9000;
          meteors.push({
            x: Math.random() * w * 0.8 + w * 0.1,
            y: Math.random() * h * 0.3,
            vx: -(2.2 + Math.random() * 1.6),
            vy: 1.1 + Math.random() * 0.8,
            life: 1,
          });
        }
        meteors = meteors.filter((m) => m.life > 0);
        for (const m of meteors) {
          m.x += m.vx;
          m.y += m.vy;
          m.life -= 0.012;
          const grad = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 18, m.y - m.vy * 18);
          grad.addColorStop(0, `rgba(${accentRgb[0]},${accentRgb[1]},${accentRgb[2]},${(0.7 * m.life * starAlpha).toFixed(3)})`);
          grad.addColorStop(1, "rgba(0,0,0,0)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(m.x, m.y);
          ctx.lineTo(m.x - m.vx * 18, m.y - m.vy * 18);
          ctx.stroke();
        }
      }
    };

    const loop = (t: number) => {
      draw(t, true);
      raf = requestAnimationFrame(loop);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      if (reduced.matches) {
        draw(4000, false);
      } else {
        raf = requestAnimationFrame(loop);
      }
    };
    const onVisibility = () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else start();
    };
    const onMotionChange = () => start();
    ready = true;
    start();
    document.addEventListener("visibilitychange", onVisibility);
    reduced.addEventListener("change", onMotionChange);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      themeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      reduced.removeEventListener("change", onMotionChange);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden className={cn("block h-full w-full", className)} />;
}
