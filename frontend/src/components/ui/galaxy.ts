export type GalaxyStar = {
  x: number;
  y: number;
  z: number;
  size: number;
  tint: number;
  phase: number;
};

export type GalaxyProjection = {
  x: number;
  y: number;
  scale: number;
  depth: number;
};

export type GalaxyShape = {
  arms: number;
  twist: number;
  bulgeRatio: number;
  fieldRatio: number;
};

export const DEFAULT_GALAXY_SHAPE: GalaxyShape = {
  arms: 2,
  twist: 3.5,
  bulgeRatio: 0.18,
  fieldRatio: 0.35,
};

/** 每次进入登录页换一个银河形态：大多数是双旋臂，偶尔三臂。 */
export function randomGalaxyShape(random: () => number = Math.random): GalaxyShape {
  return {
    arms: random() < 0.22 ? 3 : 2,
    twist: 2.8 + random() * 1.6,
    bulgeRatio: 0.14 + random() * 0.1,
    fieldRatio: 0.28 + random() * 0.18,
  };
}

/**
 * 归一化银河盘：x/z 为盘面坐标，y 为薄盘高度。
 * 大部分星落在旋臂上，另有一部分填充盘面与中心核球。
 */
export function buildGalaxy(
  count: number,
  random: () => number = Math.random,
  shape: GalaxyShape = DEFAULT_GALAXY_SHAPE,
): GalaxyStar[] {
  const stars: GalaxyStar[] = [];

  for (let i = 0; i < count; i += 1) {
    const bulge = random() < shape.bulgeRatio;
    const field = !bulge && random() < shape.fieldRatio;
    const r = bulge
      ? Math.pow(random(), 2.2) * 0.3
      : 0.08 + Math.pow(random(), 0.85) * 0.92;
    const spread = (0.1 + r * 0.22) * (field ? 1.7 : 1);
    const theta = bulge || field
      ? random() * Math.PI * 2
      : (Math.floor(random() * shape.arms) / shape.arms) * Math.PI * 2 + r * shape.twist + (random() - 0.5) * spread;
    const thickness = bulge ? 0.16 : 0.035 / (0.35 + r);
    const tintRoll = random();

    stars.push({
      x: Math.cos(theta) * r,
      y: (random() - 0.5) * thickness,
      z: Math.sin(theta) * r,
      size: 0.55 + random() * 1.35 + (random() < 0.035 ? 1.3 : 0),
      tint: tintRoll < 0.09 ? 2 : tintRoll < 0.4 ? 1 : 0,
      phase: random() * Math.PI * 2,
    });
  }

  return stars;
}

/**
 * 先绕盘心 y 轴旋转，再按相机俯角倾斜，最后做透视投影。
 * focal 越大透视越弱；radius 是银河盘在屏幕上的基准半径。
 */
export function projectGalaxy(
  star: GalaxyStar,
  angle: number,
  tilt: number,
  focal: number,
  radius: number,
  centerX: number,
  centerY: number,
): GalaxyProjection {
  const cosA = Math.cos(angle);
  const sinA = Math.sin(angle);
  const rx = star.x * cosA - star.z * sinA;
  const rz = star.x * sinA + star.z * cosA;

  const cosT = Math.cos(tilt);
  const sinT = Math.sin(tilt);
  const ry = star.y * cosT - rz * sinT;
  const depth = star.y * sinT + rz * cosT;
  const scale = focal / (focal + depth);

  return {
    x: centerX + rx * radius * scale,
    y: centerY + ry * radius * scale,
    scale,
    depth,
  };
}
