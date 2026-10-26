import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * 「聚星」画布：程序化星空，星点被缓慢移动的重力中心聚拢（聚合），
 * 相邻星之间浮现细线（编排/星座），偶有流星。颜色取自主题 token，
 * 随明暗主题换天；prefers-reduced-motion 下渲染静态一帧；页面隐藏时暂停。
 */

interface Star {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  phase: number;
  tint: number; // 0 = 前景色, 1 = 主色, 2 = 强调色
}

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
    // draw 定义之前 resize/readTheme 可能被首次调用,用 ready 挡静态重绘
    let ready = false;
    let stars: Star[] = [];
    let meteors: Meteor[] = [];
    let nextMeteorAt = 0;
    // 重力中心:缓慢利萨如轨迹
    const attractors = [
      { ax: 0.3, ay: 0.35, fx: 0.00013, fy: 0.00021, px: 0, py: 1.3 },
      { ax: 0.72, ay: 0.6, fx: 0.00017, fy: 0.00011, px: 2.1, py: 4.0 },
    ];

    // 主题色:读计算后的 CSS 变量,主题切换时重读
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
      // 静态帧模式下主题切换后重绘一次,否则星空停留在旧主题色
      if (reduced.matches && w > 0) draw(4000, false);
    };
    readTheme();
    const themeObserver = new MutationObserver(readTheme);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    const seed = () => {
      const count = Math.min(220, Math.max(80, Math.round((w * h) / 11000)));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.08,
        vy: (Math.random() - 0.5) * 0.08,
        r: 0.6 + Math.random() * 1.3,
        phase: Math.random() * Math.PI * 2,
        tint: Math.random() < 0.14 ? 1 : Math.random() < 0.06 ? 2 : 0,
      }));
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (stars.length === 0) seed();
      // 静态帧模式下 resize 会清空画布,补绘一次
      if (ready && reduced.matches) draw(4000, false);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const paintSky = () => {
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      if (dark) {
        // 墨紫黑夜空:底部沉一点紫
        sky.addColorStop(0, "#0d0c10");
        sky.addColorStop(1, "#16121f");
      } else {
        // 白昼星空:低对比,不喧宾夺主
        sky.addColorStop(0, "#f3f4f6");
        sky.addColorStop(1, "#eae6f4");
      }
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
    };

    const draw = (t: number, animate: boolean) => {
      paintSky();
      const inkRgb = hexToRgb(ink) ?? [250, 250, 250];
      const primaryRgb = hexToRgb(primary) ?? [124, 58, 237];
      const accentRgb = hexToRgb(accent) ?? [225, 29, 72];
      const palette = [inkRgb, primaryRgb, accentRgb];
      const starAlpha = dark ? 1 : 0.55;

      // 重力中心当前位置
      const wells = attractors.map((a) => ({
        x: (a.ax + Math.sin(t * a.fx + a.px) * 0.08) * w,
        y: (a.ay + Math.cos(t * a.fy + a.py) * 0.08) * h,
      }));

      // 星座连线:距离阈值内浮线(编排的隐喻)
      const linkDist = Math.min(w, h) * 0.11;
      ctx.lineWidth = 0.6;
      for (let i = 0; i < stars.length; i++) {
        for (let j = i + 1; j < stars.length; j++) {
          const a = stars[i];
          const b = stars[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < linkDist * linkDist) {
            const alpha = (1 - Math.sqrt(d2) / linkDist) * (dark ? 0.16 : 0.1);
            ctx.strokeStyle = `rgba(${primaryRgb[0]},${primaryRgb[1]},${primaryRgb[2]},${alpha})`;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // 星点:漂移 + 被重力中心轻拉 + 闪烁
      for (const s of stars) {
        if (animate) {
          s.x += s.vx;
          s.y += s.vy;
          for (const well of wells) {
            const dx = well.x - s.x;
            const dy = well.y - s.y;
            const d2 = dx * dx + dy * dy;
            const range = Math.min(w, h) * 0.4;
            if (d2 < range * range && d2 > 1) {
              const f = 0.35 / Math.sqrt(d2);
              s.vx += dx * f * 0.01;
              s.vy += dy * f * 0.01;
            }
          }
          // 阻尼与限速,防止加速失控
          s.vx *= 0.995;
          s.vy *= 0.995;
          const speed = Math.hypot(s.vx, s.vy);
          if (speed < 0.05) {
            s.vx += (Math.random() - 0.5) * 0.01;
            s.vy += (Math.random() - 0.5) * 0.01;
          }
          if (s.x < -10) s.x = w + 10;
          if (s.x > w + 10) s.x = -10;
          if (s.y < -10) s.y = h + 10;
          if (s.y > h + 10) s.y = -10;
        }
        const twinkle = 0.55 + 0.45 * Math.sin(t * 0.0012 + s.phase);
        const [r, g, b] = palette[s.tint];
        ctx.fillStyle = `rgba(${r},${g},${b},${(twinkle * starAlpha).toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }

      // 流星:强调色,每隔数秒一颗
      if (animate) {
        if (t > nextMeteorAt) {
          nextMeteorAt = t + 5000 + Math.random() * 7000;
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
        draw(4000, false); // 静态星空一帧
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
