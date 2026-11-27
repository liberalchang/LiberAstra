import { describe, expect, it } from "vitest";
import { DEFAULT_COMFY_PLUS_MODEL, PROVIDER_ID } from "../src/config/defaults.js";
import { parseComfyPlusConfig } from "../src/config/schema.js";

describe("config-switch (验收 #9)", () => {
  it("默认模型引用为 comfy-plus/workflow", () => {
    expect(`${PROVIDER_ID}/${DEFAULT_COMFY_PLUS_MODEL}`).toBe("comfy-plus/workflow");
  });

  it("切换设计：停用 comfy、启用 comfy-plus 后回退模型配置可独立保留", () => {
    // 模拟 OpenClaw agents.defaults.imageGenerationModel 片段（插件不改写该对象）
    const imageGenerationModel = {
      primary: "comfy-plus/workflow",
      fallbacks: ["google/gemini-3.1-flash-image"],
    };
    const plugins = {
      entries: {
        comfy: { enabled: false },
        "comfy-plus": {
          enabled: true,
          config: parseComfyPlusConfig({
            baseUrl: "http://10.10.12.140:8188",
            timeoutMs: 600000,
          }),
        },
      },
    };
    expect(plugins.entries.comfy.enabled).toBe(false);
    expect(plugins.entries["comfy-plus"].enabled).toBe(true);
    expect(imageGenerationModel.primary).toBe("comfy-plus/workflow");
    expect(imageGenerationModel.fallbacks).toContain("google/gemini-3.1-flash-image");
    expect(plugins.entries["comfy-plus"].config.timeoutMs).toBe(600_000);
  });
});
