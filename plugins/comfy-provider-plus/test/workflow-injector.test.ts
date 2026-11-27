import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { DEFAULT_COMFY_PLUS_CONFIG, EDIT_NODE_BINDINGS, T2I_NODE_BINDINGS } from "../src/config/defaults.js";
import { injectWorkflowParams } from "../src/workflow/injector.js";
import { assertBindingsExist, loadWorkflowFromObject } from "../src/workflow/loader.js";
import { parseComfyPlusConfig } from "../src/config/schema.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function loadJson(name: string) {
  return JSON.parse(fs.readFileSync(path.join(root, "workflows", name), "utf8"));
}

describe("workflow-injector", () => {
  it("T2I 提交 JSON 无 LoadImage 与 images.*", () => {
    const template = loadWorkflowFromObject(loadJson("qwen-image-t2i.json"));
    assertBindingsExist(template, T2I_NODE_BINDINGS);
    const wf = injectWorkflowParams({
      workflow: template,
      bindings: T2I_NODE_BINDINGS,
      defaults: DEFAULT_COMFY_PLUS_CONFIG.defaults,
      overrides: { steps: 20, cfg: 1.5, width: 768, height: 1024, negativePrompt: "blur", seed: 42 },
      prompt: "a cat",
      uploadedFilenames: [],
      loraEnabled: true,
      mode: "t2i",
    });
    expect(Object.values(wf).some((n) => n.class_type === "LoadImage")).toBe(false);
    expect(Object.values(wf).some((n) => Object.keys(n.inputs).some((k) => k.startsWith("images.")))).toBe(
      false,
    );
    expect(wf["5"].inputs.prompt).toBe("a cat");
    expect(wf["5"].inputs.negative_prompt).toBe("blur");
    expect(wf["7"].inputs.steps).toBe(20);
    expect(wf["7"].inputs.cfg).toBe(1.5);
    expect(wf["7"].inputs.seed).toBe(42);
    expect(wf["6"].inputs.width).toBe(768);
    expect(wf["6"].inputs.height).toBe(1024);
  });

  it("Edit N=1/2/16 接线正确；KSampler latent 接 [5,2]", () => {
    for (const n of [1, 2, 16]) {
      const template = loadWorkflowFromObject(loadJson("qwen-image-edit.json"));
      const names = Array.from({ length: n }, (_, i) => `f${i + 1}.png`);
      const wf = injectWorkflowParams({
        workflow: template,
        bindings: EDIT_NODE_BINDINGS,
        defaults: DEFAULT_COMFY_PLUS_CONFIG.defaults,
        overrides: {},
        prompt: "edit",
        uploadedFilenames: names,
        loraEnabled: true,
        mode: "edit",
      });
      expect(wf["6"].inputs.latent_image).toEqual(["5", 2]);
      for (let i = 1; i <= n; i += 1) {
        const loadId = String(100 + i);
        expect(wf[loadId].class_type).toBe("LoadImage");
        expect(wf[loadId].inputs.image).toBe(`f${i}.png`);
        expect(wf["5"].inputs[`images.image_${i}`]).toEqual([loadId, 0]);
      }
      expect(wf["5"].inputs["images.image_17"]).toBeUndefined();
    }
  });

  it("loraEnabled=false 旁路并删除 LoRA 节点", () => {
    const template = loadWorkflowFromObject(loadJson("qwen-image-t2i.json"));
    const wf = injectWorkflowParams({
      workflow: template,
      bindings: T2I_NODE_BINDINGS,
      defaults: DEFAULT_COMFY_PLUS_CONFIG.defaults,
      overrides: {},
      prompt: "x",
      uploadedFilenames: [],
      loraEnabled: false,
      mode: "t2i",
    });
    expect(wf["200"]).toBeUndefined();
    expect(wf["7"].inputs.model).toEqual(["4", 0]);
  });

  it("拒绝官方单图旧键", () => {
    expect(() =>
      parseComfyPlusConfig({ inputImageNodeId: "10", baseUrl: "http://x" }),
    ).toThrow(/不兼容官方单图旧键/);
  });
});
