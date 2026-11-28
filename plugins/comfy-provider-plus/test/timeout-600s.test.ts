import { describe, expect, it } from "vitest";
import { ComfyClient } from "../src/comfy/client.js";
import { DEFAULT_COMFY_PLUS_CONFIG } from "../src/config/defaults.js";
import { parseComfyPlusConfig } from "../src/config/schema.js";

describe("timeout-600s", () => {
  it("默认配置 timeoutMs 为真实值 600000", () => {
    const cfg = parseComfyPlusConfig({});
    expect(cfg.timeoutMs).toBe(600_000);
    expect(DEFAULT_COMFY_PLUS_CONFIG.timeoutMs).toBe(600_000);
  });

  it("使用真实 timeoutMs: 600000，注入时钟验证超时文案", async () => {
    let now = 0;
    const fetchImpl = async () =>
      new Response(JSON.stringify({ "prompt-x": { status: { completed: false } } }), {
        status: 200,
      });

    const client = new ComfyClient({
      baseUrl: "http://example.invalid",
      timeoutMs: 600_000,
      pollIntervalMs: 1_000,
      maxUploadBytes: 1024,
      pollRequestTimeoutMs: 5_000,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      now: () => now,
      sleep: async (ms) => {
        now += ms;
      },
    });

    await expect(client.waitForHistory("prompt-x")).rejects.toMatchObject({
      code: "EXECUTION_TIMEOUT",
      message: expect.stringMatching(/600s/),
      details: expect.objectContaining({ timeoutMs: 600_000 }),
    });
    expect(now).toBeGreaterThanOrEqual(600_000);
  });

  it("waitForHistory 响应 AbortSignal，立即中止且 history 轮询 ≤ 2", async () => {
    const ac = new AbortController();
    let historyFetches = 0;
    let sleeps = 0;
    const fetchImpl = async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/history/")) {
        historyFetches += 1;
        return new Response(
          JSON.stringify({ "prompt-abort": { status: { completed: false } } }),
          { status: 200 },
        );
      }
      // tryCleanup 的 /queue /interrupt
      return new Response(JSON.stringify({ queue_running: [] }), { status: 200 });
    };

    const client = new ComfyClient({
      baseUrl: "http://example.invalid",
      timeoutMs: 600_000,
      pollIntervalMs: 1_000,
      maxUploadBytes: 1024,
      pollRequestTimeoutMs: 5_000,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      signal: ac.signal,
      sleep: async () => {
        sleeps += 1;
        ac.abort();
        throw Object.assign(new Error("aborted"), { name: "AbortError" });
      },
    });

    await expect(client.waitForHistory("prompt-abort")).rejects.toMatchObject({
      code: "EXECUTION_TIMEOUT",
      message: expect.stringMatching(/取消|aborted/),
    });
    expect(historyFetches).toBeLessThanOrEqual(2);
    expect(sleeps).toBeLessThanOrEqual(2);
  });
});
