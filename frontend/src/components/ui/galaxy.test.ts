import assert from "node:assert/strict";
import { test } from "node:test";

import { buildGalaxy, projectGalaxy, randomGalaxyShape, type GalaxyStar } from "./galaxy.ts";

function seeded(seed: number): () => number {
  let value = seed;
  return () => {
    value |= 0;
    value = (value + 0x6d2b79f5) | 0;
    let t = Math.imul(value ^ (value >>> 15), 1 | value);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function star(overrides: Partial<GalaxyStar> = {}): GalaxyStar {
  return { x: 0, y: 0, z: 0, size: 1, tint: 0, phase: 0, ...overrides };
}

test("buildGalaxy 生成指定数量且坐标有界", () => {
  const stars = buildGalaxy(200, seeded(42));
  assert.equal(stars.length, 200);
  for (const item of stars) {
    assert.ok(Math.hypot(item.x, item.z) <= 1.001);
    assert.ok(Math.abs(item.y) < 0.12);
    assert.ok(item.size > 0);
    assert.ok(item.tint >= 0 && item.tint <= 2);
  }
});

test("相同随机种子生成相同的银河", () => {
  assert.deepEqual(buildGalaxy(80, seeded(7)), buildGalaxy(80, seeded(7)));
});

test("随机银河形态在合理范围", () => {
  const shape = randomGalaxyShape(seeded(3));
  assert.ok(shape.arms === 2 || shape.arms === 3);
  assert.ok(shape.twist >= 2.8 && shape.twist <= 4.4);
  assert.ok(shape.bulgeRatio >= 0.14 && shape.bulgeRatio <= 0.24);
  assert.ok(shape.fieldRatio >= 0.28 && shape.fieldRatio <= 0.46);
});

test("盘心投影到屏幕中心且 scale 为 1", () => {
  const projection = projectGalaxy(star(), 0, 0, 2, 100, 50, 60);
  assert.equal(projection.x, 50);
  assert.equal(projection.y, 60);
  assert.equal(projection.scale, 1);
});

test("绕 y 轴旋转会改变盘面 x 坐标", () => {
  const point = star({ x: 1 });
  const atZero = projectGalaxy(point, 0, 0, 2, 100, 0, 0);
  const atQuarter = projectGalaxy(point, Math.PI / 2, 0, 2, 100, 0, 0);
  assert.ok(Math.abs(atZero.x - 100) < 1e-9);
  assert.ok(Math.abs(atQuarter.x) < 1e-9);
});

test("离相机更远的星透视缩小", () => {
  const near = projectGalaxy(star({ z: -0.5 }), 0, 0, 2, 100, 0, 0);
  const far = projectGalaxy(star({ z: 0.5 }), 0, 0, 2, 100, 0, 0);
  assert.ok(near.scale > 1);
  assert.ok(far.scale < 1);
});
