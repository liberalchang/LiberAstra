import { expect, test } from "@playwright/test";

import { gotoApp, TINY_PNG } from "./helpers";

const BACKEND = "http://127.0.0.1:8010";

test("角色库图片请求带版本且要求重新验证", async ({ page, request }) => {
  await gotoApp(page);
  const token = await page.evaluate(() => {
    const raw = localStorage.getItem("liberastra-auth");
    return raw ? (JSON.parse(raw) as { state?: { token?: string } }).state?.token ?? "" : "";
  });
  expect(token).not.toBe("");

  const image = { name: "view.png", mimeType: "image/png", buffer: TINY_PNG };
  const created = await request.post(`${BACKEND}/api/v1/characters`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      name: "缓存回归角色",
      auto_split: "false",
      portrait: image,
      front: image,
      side: image,
      back: image,
    },
  });
  expect(created.ok()).toBeTruthy();
  const character = (await created.json()) as { id: number };

  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes(`/api/v1/characters/${character.id}/image/front`) &&
      resp.request().method() === "GET",
  );
  await page.goto("/resources/characters");
  const response = await responsePromise;
  const version = new URL(response.url()).searchParams.get("v");
  expect(version).toMatch(/^characters\//);
  expect(response.headers()["cache-control"]).toBe("private, no-cache");
  await expect(page.getByText("缓存回归角色")).toBeVisible();
});
