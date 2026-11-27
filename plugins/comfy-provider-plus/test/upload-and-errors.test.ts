import { describe, expect, it, vi } from "vitest";
import { ComfyClient } from "../src/comfy/client.js";
import { createComfyError, redactSensitive } from "../src/comfy/errors.js";
import { routeOperation } from "../src/router/operation-router.js";
import { DEFAULT_COMFY_PLUS_CONFIG } from "../src/config/defaults.js";

describe("upload-and-errors", () => {
  it("N=17 本地拒绝且 0 网络请求", () => {
    const fetchImpl = vi.fn();
    expect(() =>
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 17,
      }),
    ).toThrow(/超过上限/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("预检空文件返回序号，不发网络", async () => {
    const fetchImpl = vi.fn();
    const client = new ComfyClient({
      baseUrl: "http://127.0.0.1:9",
      timeoutMs: 600_000,
      pollIntervalMs: 100,
      maxUploadBytes: 1024,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    expect(() =>
      client.preflightImages([{ buffer: Buffer.alloc(0), mimeType: "image/png", fileName: "a.png" }]),
    ).toThrow(/第 1 张/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("上传第 2 张失败则中止（事务性）", async () => {
    let calls = 0;
    const fetchImpl = vi.fn(async () => {
      calls += 1;
      if (calls === 1) {
        return new Response(JSON.stringify({ name: "ok1.png" }), { status: 200 });
      }
      return new Response("boom", { status: 500 });
    });
    const client = new ComfyClient({
      baseUrl: "http://example.invalid",
      timeoutMs: 600_000,
      pollIntervalMs: 100,
      maxUploadBytes: 1024 * 1024,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);
    await expect(
      client.uploadImages([
        { buffer: png, mimeType: "image/png", fileName: "a.png" },
        { buffer: png, mimeType: "image/png", fileName: "b.png" },
      ]),
    ).rejects.toMatchObject({ code: "UPLOAD_FAILED" });
    expect(calls).toBe(2);
  });

  it("四类错误码与脱敏", () => {
    expect(createComfyError("COMFY_UNREACHABLE", "down").code).toBe("COMFY_UNREACHABLE");
    expect(createComfyError("UPLOAD_FAILED", "u", { index: 1 }).code).toBe("UPLOAD_FAILED");
    expect(createComfyError("EXECUTION_FAILED", "e").code).toBe("EXECUTION_FAILED");
    expect(createComfyError("EXECUTION_TIMEOUT", "t").code).toBe("EXECUTION_TIMEOUT");
    const redacted = redactSensitive(
      'api_key=sk-secret token=abc Authorization: Bearer xyz C:\\Users\\Administrator\\secret\\file.png /home/ps/workspace/x stack\n    at Object.foo (C:\\Users\\Administrator\\app.js:1:1)',
    );
    expect(redacted).not.toMatch(/sk-secret/);
    expect(redacted).not.toMatch(/Bearer xyz/i);
    expect(redacted).not.toMatch(/C:\\Users\\Administrator/);
    expect(redacted).not.toMatch(/\/home\/ps\//);
  });

  it("调色/换姿关闭时不可调用", () => {
    expect(() =>
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 2,
        requestedOperation: "color-grade",
      }),
    ).toThrow(/调色工作流未验证/);
    expect(() =>
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 2,
        requestedOperation: "pose-transfer",
      }),
    ).toThrow(/换姿工作流未验证/);
  });
});
