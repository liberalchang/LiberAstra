import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { request, type APIRequestContext } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");
const root = path.resolve(frontend, "..");
const dataDir = path.join(frontend, ".e2e-data");
const authDir = path.join(here, ".auth");
const BACKEND = "http://127.0.0.1:8010";
const FRONTEND = "http://127.0.0.1:5180";
const USERNAME = "e2e";
const PASSWORD = "e2e-pass-123";

function spawnBackend(): ChildProcess {
  const exe = path.join(
    root,
    "backend",
    ".venv",
    process.platform === "win32" ? "Scripts/astra.exe" : "bin/astra",
  );
  return spawn(exe, ["serve", "--port", "8010"], {
    cwd: root,
    env: {
      ...process.env,
      LIBERASTRA_DATA_DIR: dataDir,
      LIBERASTRA_SECRET_KEY: "e2e-secret-key-padded-to-32-bytes!!",
    },
    stdio: "inherit",
  });
}

function spawnFrontend(): ChildProcess {
  return spawn(
    process.execPath,
    [path.join(frontend, "node_modules", "vite", "bin", "vite.js"), "--config", "vite.e2e.config.ts"],
    {
      cwd: frontend,
      env: process.env,
      stdio: "inherit",
    },
  );
}

async function waitFor(ctx: APIRequestContext, url: string, timeoutMs = 120_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await ctx.get(url, { timeout: 2000 });
      if (response.ok()) return;
    } catch {
      /* server not ready */
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`等待服务超时: ${url}`);
}

async function stop(child: ChildProcess): Promise<void> {
  if (!child.pid) return;
  if (process.platform === "win32") {
    try {
      execFileSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } catch {
      /* already exited */
    }
  } else {
    child.kill("SIGTERM");
  }
  await new Promise((resolve) => setTimeout(resolve, 500));
}

export default async function globalSetup() {
  rmSync(dataDir, { recursive: true, force: true });
  rmSync(authDir, { recursive: true, force: true });
  const backend = spawnBackend();
  const vite = spawnFrontend();
  const ctx = await request.newContext();
  try {
    await waitFor(ctx, `${BACKEND}/healthz`);
    await waitFor(ctx, FRONTEND);

    const setup = await ctx.post(`${BACKEND}/api/v1/auth/setup`, {
      data: { username: USERNAME, password: PASSWORD },
    });
    if (![201, 409].includes(setup.status())) {
      throw new Error(`E2E 初始化失败: ${setup.status()} ${await setup.text()}`);
    }
    const login = await ctx.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USERNAME, password: PASSWORD },
    });
    if (!login.ok()) throw new Error(`E2E 登录失败: ${login.status()} ${await login.text()}`);
    const token = (await login.json()).access_token as string;
    const me = await ctx.get(`${BACKEND}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!me.ok()) throw new Error(`E2E 获取用户失败: ${me.status()}`);
    const user = await me.json();

    const python = path.join(
      root,
      "backend",
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
    execFileSync(python, [path.join(here, "seed.py")], {
      cwd: root,
      env: { ...process.env, LIBERASTRA_DATA_DIR: dataDir },
      stdio: "inherit",
    });

    mkdirSync(authDir, { recursive: true });
    writeFileSync(
      path.join(authDir, "state.json"),
      JSON.stringify({
        cookies: [],
        origins: [
          {
            origin: FRONTEND,
            localStorage: [
              {
                name: "liberastra-auth",
                value: JSON.stringify({ state: { token, user }, version: 0 }),
              },
              { name: "liberastra-lang", value: "zh" },
            ],
          },
        ],
      }),
    );
  } finally {
    await ctx.dispose();
  }

  return async () => {
    await stop(vite);
    await stop(backend);
    rmSync(dataDir, { recursive: true, force: true });
    rmSync(authDir, { recursive: true, force: true });
  };
}
