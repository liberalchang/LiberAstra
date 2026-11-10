import { expect, test } from "@playwright/test";

import { gotoApp, openNav } from "./helpers";

test("通知页：通用设置、渠道、规则和投递记录", async ({ page }) => {
  const channels: Record<string, unknown>[] = [];
  const rules: Record<string, unknown>[] = [];
  const chatLookups: Record<string, unknown>[] = [];
  let preferencePatch: Record<string, unknown> | null = null;

  await page.route("**/api/v1/system/preferences", async (route) => {
    if (route.request().method() === "PATCH") {
      preferencePatch = route.request().postDataJSON() as Record<string, unknown>;
    }
    await route.fulfill({
      json: {
        comfy_wait_timeout_seconds: 3600,
        api_wait_timeout_seconds: 300,
        llm_request_timeout_seconds: 300,
        asr_request_timeout_seconds: 1800,
        serial_same_host: 0,
        default_llm_provider_id: 0,
        default_llm_model: "",
        default_depth_provider_id: 0,
        default_depth_model: "",
        default_character_provider_id: 0,
        default_character_workflow: "qwen_image_21",
        default_character_i2i_workflow: "qwen_image_21_edit",
        default_character_i2i_multi_workflow: "qwen_image_21_edit_multi",
        default_speech_model: "multilingual_v3",
        default_asr_model: "",
        default_vc_model: "",
        notification_language: "zh-CN",
        notification_proxy: "",
        notification_public_base_url: "",
      },
    });
  });

  await page.route("**/api/v1/notifications/telegram/chats", async (route) => {
    chatLookups.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      json: {
        items:
          chatLookups.length === 1
            ? [
                { id: "100200300", type: "private", title: "测试私聊" },
                { id: "-100123", type: "supergroup", title: "测试群" },
              ]
            : [],
      },
    });
  });

  await page.route("**/api/v1/notifications/channels", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const created = {
        id: 1,
        type: body.type,
        name: body.name,
        config: { bot_token: "****ABCD", chat_id: "-1001" },
        enabled: true,
        max_attempts: 3,
        backoff_seconds: 30,
        timeout_seconds: 10,
        last_error: null,
        created_at: "2026-11-10T00:00:00Z",
        updated_at: "2026-11-10T00:00:00Z",
      };
      channels.push(created);
      await route.fulfill({ status: 201, json: created });
      return;
    }
    await route.fulfill({ json: channels });
  });

  await page.route("**/api/v1/notifications/channels/1", async (route) => {
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      Object.assign(channels[0], body);
      await route.fulfill({ json: channels[0] });
      return;
    }
    await route.fulfill({ status: 404 });
  });

  await page.route("**/api/v1/notifications/channels/1/test", async (route) => {
    await route.fulfill({ json: { ok: true, message: "测试消息已发送" } });
  });

  await page.route("**/api/v1/notifications/rules", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const created = {
        id: 1,
        name: body.name,
        enabled: true,
        enabled_since: "2026-11-10T00:00:00Z",
        events: body.events,
        progress_interval_seconds: 900,
        job_kinds: [],
        max_jobs_per_digest: 10,
        quiet_hours: null,
        include_outputs: true,
        template_succeeded: null,
        template_failed: null,
        template_progress: null,
        channel_ids: body.channel_ids,
        created_at: "2026-11-10T00:00:00Z",
        updated_at: "2026-11-10T00:00:00Z",
      };
      rules.push(created);
      await route.fulfill({ status: 201, json: created });
      return;
    }
    await route.fulfill({ json: rules });
  });

  const deliveries = [
    {
      id: 7,
      rule_id: 1,
      channel_id: 1,
      job_id: "job-1",
      event: "job.failed",
      bucket: "failed",
      title: "[失败] 测试任务",
      body: "错误: mock failure",
      status: "failed",
      attempts: 3,
      max_attempts: 3,
      next_attempt_at: null,
      response_status: 500,
      last_error: "boom",
      created_at: "2026-11-10T00:00:00Z",
      sent_at: null,
    },
  ];
  await page.route("**/api/v1/notifications/deliveries**", async (route) => {
    if (route.request().method() === "POST") {
      deliveries[0].status = "pending";
      await route.fulfill({ json: deliveries[0] });
      return;
    }
    await route.fulfill({ json: { items: deliveries, total: 1, limit: 100, offset: 0 } });
  });

  await gotoApp(page);
  await openNav(page, "设置", "settings", "通知");

  await expect(page.getByRole("heading", { name: "通知", exact: true })).toBeVisible();
  await expect(page.getByText("推送语言", { exact: true })).toBeVisible();

  await page.getByLabel("出站代理").fill("http://127.0.0.1:7890");
  const prefReq = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/v1/system/preferences") &&
      request.method() === "PATCH",
  );
  await page.getByRole("button", { name: "保存通用设置" }).click();
  await prefReq;
  expect(preferencePatch).toMatchObject({ notification_proxy: "http://127.0.0.1:7890" });

  await page.getByRole("button", { name: "新建渠道" }).click();
  await page.getByLabel("名称").fill("测试 Telegram");
  await expect(page.getByRole("checkbox", { name: "使用全局代理" })).toBeChecked();
  await page.getByRole("button", { name: "自动获取会话 ID" }).click();
  await expect(page.getByText("请先填写 Bot Token")).toBeVisible();
  await page.getByLabel("Bot Token").fill("123456:TEST-TOKEN");
  await page.getByRole("button", { name: "自动获取会话 ID" }).click();
  await expect(page.getByText("选择要填入的会话")).toBeVisible();
  await page.getByRole("button", { name: /测试私聊/ }).click();
  await expect(page.getByLabel("Chat ID")).toHaveValue("100200300");
  expect(chatLookups[0]).toMatchObject({ bot_token: "123456:TEST-TOKEN" });
  expect(chatLookups[0].channel_id).toBeUndefined();
  const channelReq = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/v1/notifications/channels") &&
      request.method() === "POST",
  );
  await page.getByRole("button", { name: "保存渠道" }).click();
  const channelBody = (await channelReq).postDataJSON() as Record<string, unknown>;
  expect(channelBody).toMatchObject({ type: "telegram", name: "测试 Telegram" });
  await expect(page.getByText("测试 Telegram", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "编辑" }).click();
  const tokenInput = page.getByLabel("Bot Token");
  await expect(tokenInput).toHaveValue("");
  await expect(tokenInput).toHaveAttribute("placeholder", "****ABCD");
  await page.getByRole("button", { name: "自动获取会话 ID" }).click();
  await expect(
    page.getByText("没有找到最近会话。请先给 bot 发送 /start，或把 bot 拉进群后再试。"),
  ).toBeVisible();
  expect(chatLookups[1]).toMatchObject({ channel_id: 1 });
  expect(chatLookups[1].bot_token).toBeUndefined();
  await page.getByRole("button", { name: "取消" }).click();

  const toggleReq = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/v1/notifications/channels/1") &&
      request.method() === "PATCH",
  );
  await page.getByRole("switch", { name: "启用渠道" }).click();
  expect((await toggleReq).postDataJSON()).toMatchObject({ enabled: false });
  await expect(page.getByRole("status")).toContainText("渠道已停用");

  await page.getByRole("button", { name: "测试" }).click();
  await expect(page.getByRole("status")).toContainText("测试消息已发送");

  await page.getByRole("tab", { name: "规则" }).click();
  await page.getByRole("button", { name: "新建规则" }).click();
  await page.getByLabel("名称").fill("默认规则");
  await page.getByRole("checkbox", { name: "测试 Telegram" }).check();
  const ruleReq = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/v1/notifications/rules") &&
      request.method() === "POST",
  );
  await page.getByRole("button", { name: "保存规则" }).click();
  const ruleBody = (await ruleReq).postDataJSON() as Record<string, unknown>;
  expect(ruleBody).toMatchObject({ name: "默认规则", channel_ids: [1] });
  await expect(page.getByText("默认规则", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "投递记录" }).click();
  await expect(page.getByText("[失败] 测试任务")).toBeVisible();
  await expect(page.getByText("boom", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByRole("status")).toContainText("已加入重试队列");
});
