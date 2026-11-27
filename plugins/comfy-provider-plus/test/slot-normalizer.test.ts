import { describe, expect, it } from "vitest";
import { __testables, normalizePromptSlots } from "../src/prompt/slot-normalizer.js";

describe("slot-normalizer", () => {
  it("把第二张图的衣服换到第一张人物身上 → 保留人物", () => {
    const r = normalizePromptSlots({
      prompt: "把第二张图的衣服换到第一张人物身上",
      actualImageCount: 2,
    });
    expect(r.normalizedPrompt).toBe("把image_2的衣服换到image_1人物身上");
    expect(r.referencedSlots).toEqual([1, 2]);
  });

  it("独立第一张/第二张合并；第二十张越界", () => {
    const r = normalizePromptSlots({
      prompt: "把第一张和第二张合并",
      actualImageCount: 2,
    });
    expect(r.normalizedPrompt).toContain("image_1");
    expect(r.normalizedPrompt).toContain("image_2");
    expect(() =>
      normalizePromptSlots({ prompt: "参考第二十张", actualImageCount: 16 }),
    ).toThrow(/image_20|不存在的图片槽位/);
  });

  it("图一百越界拒绝", () => {
    expect(() =>
      normalizePromptSlots({ prompt: "用图一百的风格", actualImageCount: 16 }),
    ).toThrow(/image_100|不存在的图片槽位/);
  });

  it("图3 仅传 2 张被拒绝", () => {
    expect(() =>
      normalizePromptSlots({ prompt: "保留图3的风格", actualImageCount: 2 }),
    ).toThrow(/不存在的图片槽位|image_3/);
  });

  it("两个人、1024 宽保护生效且不被替换", () => {
    const protected_ = __testables.applyProtect("两个人站在一起，1024 宽，CFG 1，25 步");
    expect(protected_.masked).toMatch(/__OCP_PROTECT_\d+__/);
    expect(protected_.masked).not.toContain("两个人");
    expect(protected_.masked).not.toContain("1024 宽");
    expect(protected_.masked).not.toContain("25 步");

    const r = normalizePromptSlots({
      prompt: "两个人站在一起，1024 宽，CFG 1，25 步",
      actualImageCount: 0,
    });
    expect(r.normalizedPrompt).toContain("两个人");
    expect(r.normalizedPrompt).toContain("1024 宽");
    expect(r.normalizedPrompt).toContain("CFG 1");
    expect(r.normalizedPrompt).toContain("25 步");
    expect(r.referencedSlots).toEqual([]);
  });

  it("第一张桌子不被当作图片指代", () => {
    const r = normalizePromptSlots({
      prompt: "房间里有第一张桌子",
      actualImageCount: 2,
    });
    expect(r.normalizedPrompt).toContain("第一张桌子");
    expect(r.referencedSlots).toEqual([]);
  });

  it("左边那张不猜测", () => {
    const r = normalizePromptSlots({
      prompt: "把左边那张的背景换成白墙",
      actualImageCount: 2,
    });
    expect(r.normalizedPrompt).toContain("左边那张");
    expect(r.warnings.some((w) => w.includes("模糊"))).toBe(true);
  });

  it("无图却含图1 拒绝", () => {
    expect(() =>
      normalizePromptSlots({ prompt: "参考图1修脸", actualImageCount: 0 }),
    ).toThrow(/无参考图/);
  });

  it("imageRoles 显式映射", () => {
    const r = normalizePromptSlots({
      prompt: "把服装参考的衣服换到人物原图上",
      actualImageCount: 2,
      imageRoles: ["人物原图", "服装参考"],
    });
    expect(r.normalizedPrompt).toContain("image_2");
    expect(r.normalizedPrompt).toContain("image_1");
  });

  it("图十七 / 第二十张图 越界捕获", () => {
    expect(() =>
      normalizePromptSlots({ prompt: "使用图17", actualImageCount: 16 }),
    ).toThrow(/image_17/);
    expect(() =>
      normalizePromptSlots({ prompt: "参考第二十张图", actualImageCount: 16 }),
    ).toThrow(/image_20/);
  });

  it("英文 first image / 2nd reference image", () => {
    const r = normalizePromptSlots({
      prompt: "swap clothes from the 2nd reference image onto the first image",
      actualImageCount: 2,
    });
    expect(r.normalizedPrompt).toContain("image_2");
    expect(r.normalizedPrompt).toContain("image_1");
  });
});
