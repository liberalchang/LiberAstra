/**
 * 140 联调：设置 RUN_COMFY_140=1 时执行；默认跳过以免 CI 无网失败。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ComfyClient } from "../src/comfy/client.js";
import { DEFAULT_COMFY_PLUS_CONFIG, EDIT_NODE_BINDINGS, T2I_NODE_BINDINGS } from "../src/config/defaults.js";
import { injectWorkflowParams } from "../src/workflow/injector.js";
import { loadWorkflowFromObject } from "../src/workflow/loader.js";

const enabled = process.env.RUN_COMFY_140 === "1";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baseUrl = process.env.COMFY_BASE_URL || DEFAULT_COMFY_PLUS_CONFIG.baseUrl;

describe.runIf(enabled)("integration-140", () => {
  it("T2I 实跑：history 无 LoadImage", async () => {
    const template = loadWorkflowFromObject(
      JSON.parse(fs.readFileSync(path.join(root, "workflows/qwen-image-t2i.json"), "utf8")),
    );
    const wf = injectWorkflowParams({
      workflow: template,
      bindings: T2I_NODE_BINDINGS,
      defaults: DEFAULT_COMFY_PLUS_CONFIG.defaults,
      overrides: { seed: 1, steps: 4 },
      prompt: "a simple red apple, studio photo",
      uploadedFilenames: [],
      loraEnabled: true,
      mode: "t2i",
    });
    const client = new ComfyClient({
      baseUrl,
      timeoutMs: 600_000,
      pollIntervalMs: 1500,
      maxUploadBytes: 25 * 1024 * 1024,
    });
    const promptId = await client.submitPrompt(wf);
    const history = await client.waitForHistory(promptId);
    const statusMessages = JSON.stringify(history);
    expect(statusMessages.includes("LoadImage")).toBe(false);
    const files = client.extractImages(history, "9");
    expect(files.length).toBeGreaterThan(0);
  }, 600_000);

  it("单图 Edit 接线 images.image_1", async () => {
    const sample = fs.readFileSync(
      path.join(root, "docs/phase0-raw/qwen-image-uc_00060_.png"),
    );
    const client = new ComfyClient({
      baseUrl,
      timeoutMs: 600_000,
      pollIntervalMs: 1500,
      maxUploadBytes: 25 * 1024 * 1024,
    });
    const uploaded = await client.uploadImages([
      { buffer: sample, mimeType: "image/png", fileName: "ref60.png" },
    ]);
    const template = loadWorkflowFromObject(
      JSON.parse(fs.readFileSync(path.join(root, "workflows/qwen-image-edit.json"), "utf8")),
    );
    const wf = injectWorkflowParams({
      workflow: template,
      bindings: EDIT_NODE_BINDINGS,
      defaults: DEFAULT_COMFY_PLUS_CONFIG.defaults,
      overrides: { seed: 1, steps: 4 },
      prompt: "keep the subject, plain light gray background",
      uploadedFilenames: uploaded.map((u) => u.filename),
      loraEnabled: true,
      mode: "edit",
    });
    expect(wf["5"].inputs["images.image_1"]).toEqual(["101", 0]);
    expect(wf["6"].inputs.latent_image).toEqual(["5", 2]);
    const promptId = await client.submitPrompt(wf);
    const history = await client.waitForHistory(promptId);
    const files = client.extractImages(history, "8");
    expect(files.length).toBeGreaterThan(0);
  }, 600_000);
});

describe("integration-140-gated", () => {
  it("默认跳过实机（无 RUN_COMFY_140）", () => {
    if (!enabled) expect(enabled).toBe(false);
  });
});
