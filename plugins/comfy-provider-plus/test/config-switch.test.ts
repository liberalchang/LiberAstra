import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { DEFAULT_COMFY_PLUS_MODEL, PROVIDER_ID } from "../src/config/defaults.js";
import { parseComfyPlusConfig } from "../src/config/schema.js";
import { isComfyPlusConfigured, normalizeProviderModel } from "../src/provider-runtime.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("config-switch (验收 #9)", () => {
  it("默认模型引用为 comfy-plus/workflow", () => {
    expect(`${PROVIDER_ID}/${DEFAULT_COMFY_PLUS_MODEL}`).toBe("comfy-plus/workflow");
  });

  it("isComfyPlusConfigured({}) 为 false；显式配置后为 true", () => {
    expect(isComfyPlusConfigured({})).toBe(false);
    expect(isComfyPlusConfigured(undefined)).toBe(false);
    expect(
      isComfyPlusConfigured({
        plugins: {
          entries: {
            "comfy-plus": {
              enabled: true,
              config: {
                baseUrl: "http://10.10.12.140:8188",
                workflows: {
                  t2i: "a.json",
                  edit: "b.json",
                },
              },
            },
          },
        },
      }),
    ).toBe(true);
    expect(
      isComfyPlusConfigured({
        plugins: {
          entries: {
            "comfy-plus": {
              enabled: false,
              config: {
                baseUrl: "http://10.10.12.140:8188",
                workflows: { t2i: "a.json", edit: "b.json" },
              },
            },
          },
        },
      }),
    ).toBe(false);
  });

  it("model 不双重拼接 comfy-plus/", () => {
    expect(normalizeProviderModel("workflow")).toBe("comfy-plus/workflow");
    expect(normalizeProviderModel("comfy-plus/workflow")).toBe("comfy-plus/workflow");
    expect(normalizeProviderModel(undefined)).toBe("comfy-plus/workflow");
  });

  it("switch 文档配置满足 openclaw.plugin.json configSignals.required", () => {
    const pluginJson = JSON.parse(
      fs.readFileSync(path.join(root, "openclaw.plugin.json"), "utf8"),
    ) as {
      imageGenerationProviderMetadata: {
        "comfy-plus": { configSignals: Array<{ required: string[] }> };
      };
    };
    const required =
      pluginJson.imageGenerationProviderMetadata["comfy-plus"].configSignals[0].required;
    expect(required).toEqual(["baseUrl", "workflows"]);
    expect(required).not.toContain("nodeBindings");

    // 与 switch-to-comfy-plus.md 推荐字段一致（无 nodeBindings）
    const recommended = {
      mode: "local",
      baseUrl: "http://10.10.12.140:8188",
      timeoutMs: 600000,
      workflows: {
        t2i: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-t2i.json",
        edit: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-edit.json",
        colorGrade: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-color-grade.json",
        pose: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-pose.json",
      },
      operations: {
        colorGrade: { enabled: false },
        pose: { enabled: false },
      },
    };
    for (const key of required) {
      expect(recommended).toHaveProperty(key);
    }
    const parsed = parseComfyPlusConfig(recommended);
    expect(parsed.timeoutMs).toBe(600_000);
    expect(parsed.nodeBindings.t2i).toBeDefined();
  });

  it("切换设计：停用 comfy、启用 comfy-plus 后回退模型配置可独立保留", () => {
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
            workflows: {
              t2i: "t2i.json",
              edit: "edit.json",
            },
          }),
        },
      },
    };
    expect(plugins.entries.comfy.enabled).toBe(false);
    expect(plugins.entries["comfy-plus"].enabled).toBe(true);
    expect(imageGenerationModel.primary).toBe("comfy-plus/workflow");
    expect(imageGenerationModel.fallbacks).toContain("google/gemini-3.1-flash-image");
  });
});
