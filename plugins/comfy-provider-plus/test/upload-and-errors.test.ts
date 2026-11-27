import { describe, expect, it, vi } from "vitest";
import { ComfyClient } from "../src/comfy/client.js";
import { createComfyError, isComfyPlusError, redactSensitive } from "../src/comfy/errors.js";
import { routeOperation } from "../src/router/operation-router.js";
import { loadWorkflowTemplate } from "../src/workflow/loader.js";
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

  it("未知 operation inpaint/123 抛 VALIDATION_FAILED 不回退", () => {
    expect(() =>
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 0,
        requestedOperation: "inpaint",
      }),
    ).toThrow(/未识别的 operation/);
    try {
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 0,
        requestedOperation: "inpaint",
      });
      expect.unreachable();
    } catch (e) {
      expect((e as { code?: string }).code).toBe("VALIDATION_FAILED");
    }
    expect(() =>
      routeOperation({
        config: DEFAULT_COMFY_PLUS_CONFIG,
        imageCount: 1,
        requestedOperation: 123,
      }),
    ).toThrow(/未识别的 operation/);
  });

  it("预检空文件返回序号，不发网络", () => {
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

  it("预检拒绝伪造 PNG（纯文本 + image/png）", () => {
    const client = new ComfyClient({
      baseUrl: "http://127.0.0.1:9",
      timeoutMs: 600_000,
      pollIntervalMs: 100,
      maxUploadBytes: 1024,
    });
    expect(() =>
      client.preflightImages([
        { buffer: Buffer.from("THIS IS NOT A PNG"), mimeType: "image/png", fileName: "fake.png" },
      ]),
    ).toThrow(/魔数/);
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

  it("四类错误码与脱敏（Bearer/Basic/路径/URL 保留）", () => {
    expect(createComfyError("COMFY_UNREACHABLE", "down").code).toBe("COMFY_UNREACHABLE");
    expect(createComfyError("UPLOAD_FAILED", "u", { index: 1 }).code).toBe("UPLOAD_FAILED");
    expect(createComfyError("EXECUTION_FAILED", "e").code).toBe("EXECUTION_FAILED");
    expect(createComfyError("EXECUTION_TIMEOUT", "t").code).toBe("EXECUTION_TIMEOUT");
    expect(isComfyPlusError(createComfyError("VALIDATION_FAILED", "v"))).toBe(true);
    expect(isComfyPlusError(Object.assign(new Error("ENOENT"), { code: "ENOENT" }))).toBe(false);

    const redacted = redactSensitive(
      "Authorization: Bearer sk-live-999999 and Bearer sk-raw-888888 and Authorization: Basic YWRtaW46c2VjcmV0 and access_token=tok-abc and C:/Users/liber/secret.png and D:/foo/bar.png and C:\\Users\\Administrator\\secret\\file.png /home/ps/workspace/x",
    );
    expect(redacted).not.toMatch(/sk-live-999999/);
    expect(redacted).not.toMatch(/sk-raw-888888/);
    expect(redacted).not.toMatch(/Bearer sk-/i);
    expect(redacted).not.toMatch(/YWRtaW46c2VjcmV0/);
    expect(redacted).not.toMatch(/tok-abc/);
    expect(redacted).not.toMatch(/C:\/Users\/liber/);
    expect(redacted).not.toMatch(/D:\/foo/);
    expect(redacted).not.toMatch(/C:\\Users\\Administrator/);
    expect(redacted).not.toMatch(/\/home\/ps\//);

    // PATH_RE 不得误伤 http(s)://
    const urlKept = redactSensitive("fetch failed http://10.10.12.140:8188/prompt");
    expect(urlKept).toContain("http://10.10.12.140:8188/prompt");
    expect(urlKept).not.toMatch(/htt\[REDACTED_PATH\]/);
    const credUrl = redactSensitive("http://u:p@10.10.12.140:8188/prompt");
    expect(credUrl).toContain("http://[REDACTED_SECRET]@10.10.12.140:8188/prompt");
    expect(credUrl).not.toMatch(/htt\[REDACTED_PATH\]/);

    const err = createComfyError("EXECUTION_FAILED", "x", {
      msg: 'api_key="sk-123"',
      api_key: "sk-456",
      access_token: "tok-789",
    });
    expect(err.details?.msg).not.toMatch(/sk-123/);
    expect(err.details?.api_key).toBe("[REDACTED_SECRET]");
    expect(err.details?.access_token).toBe("[REDACTED_SECRET]");
  });

  it("loadWorkflowTemplate ENOENT 不泄露本机绝对路径", async () => {
    await expect(
      loadWorkflowTemplate("D:/nonexistent/secret-dir/wf.json"),
    ).rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    try {
      await loadWorkflowTemplate("D:/nonexistent/secret-dir/wf.json");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      expect(msg).not.toMatch(/D:[\\/]nonexistent/);
      expect(msg).not.toMatch(/secret-dir/);
      expect(isComfyPlusError(e)).toBe(true);
    }
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
